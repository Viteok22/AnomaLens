"""Потоковый детектор: PCA T2+Q, z-скоры датчиков и классификатор типа."""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import RobustScaler

from .config import ARTIFACTS, CALIBRATION_ROWS
from .features import FAULT_LABELS, SENSOR_META, SENSORS, window_features


class PCADetector:
    """Глобальная модель PCA + калибровка на первые 100 точек сессии."""

    def __init__(self) -> None:
        self.scaler = RobustScaler()
        self.pca = PCA(n_components=0.95, random_state=42)
        self.t2_scale: float = 1.0
        self.q_scale: float = 1.0
        self.threshold: float = 1.0
        self.sensor_median: dict[str, float] = {}
        self.sensor_scale: dict[str, float] = {}
        self.is_fitted = False

    def fit_normal(self, normal: pd.DataFrame) -> None:
        x = self.scaler.fit_transform(normal[SENSORS])
        self.pca.fit(x)
        self.is_fitted = True

    def _raw(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        latent = self.pca.transform(x)
        reconstructed = self.pca.inverse_transform(latent)
        t2 = np.sum(latent**2 / self.pca.explained_variance_, axis=1)
        q = np.sum((x - reconstructed) ** 2, axis=1)
        return t2, q

    def calibrate_session(self, session: pd.DataFrame) -> None:
        calibration = session.iloc[:CALIBRATION_ROWS]
        x = self.scaler.transform(calibration[SENSORS])
        t2, q = self._raw(x)
        self.t2_scale = max(float(np.percentile(t2, 99)), 1e-9)
        self.q_scale = max(float(np.percentile(q, 99)), 1e-9)
        scores = np.maximum(t2 / self.t2_scale, q / self.q_scale)
        self.threshold = float(np.percentile(scores, 99))

        self.sensor_median = {
            sensor: float(calibration[sensor].median()) for sensor in SENSORS
        }
        # Для постоянных датчиков MAD = 0. Добавляем нижнюю границу масштаба,
        # иначе z-скор становится астрономическим.
        self.sensor_scale = {}
        for sensor in SENSORS:
            median = self.sensor_median[sensor]
            mad = float((calibration[sensor] - median).abs().median())
            self.sensor_scale[sensor] = max(
                1.4826 * mad,
                0.01 * abs(median),
                1e-3,
            )

    def score_row(self, row: pd.Series) -> float:
        x = self.scaler.transform(pd.DataFrame([row[SENSORS].astype(float)]))
        t2, q = self._raw(x)
        return float(max(t2[0] / self.t2_scale, q[0] / self.q_scale))

    def zscores(self, row: pd.Series) -> dict[str, float]:
        result = {}
        for sensor in SENSORS:
            value = float(row[sensor])
            median = self.sensor_median[sensor]
            scale = self.sensor_scale[sensor]
            zscore = (value - median) / scale
            result[sensor] = float(max(-25.0, min(25.0, zscore)))
        return result

    def top_sensors(self, row: pd.Series, limit: int = 3) -> list[dict]:
        zscores = self.zscores(row)
        ordered = sorted(zscores.items(), key=lambda item: abs(item[1]), reverse=True)
        result = []
        for sensor, zscore in ordered[:limit]:
            result.append(
                {
                    "name": sensor,
                    "label": SENSOR_META[sensor]["label"],
                    "unit": SENSOR_META[sensor]["unit"],
                    "value": float(row[sensor]),
                    "z": round(float(zscore), 2),
                }
            )
        return result

    def risk(
        self,
        score: float,
        persistence: int,
        max_abs_z: float = 0.0,
    ) -> tuple[str, float]:
        ratio = score / self.threshold if self.threshold > 0 else 0.0
        if ratio < 1.0 and max_abs_z < 4.0:
            return "low", 0.0

        ratio_factor = min(1.0, max(0.0, (ratio - 1.0) / 2.0))
        sensor_factor = min(1.0, max_abs_z / 8.0)
        persistence_factor = min(1.0, persistence / 30.0)
        risk_score = 100.0 * (
            0.45 * sensor_factor
            + 0.35 * ratio_factor
            + 0.20 * persistence_factor
        )

        high = (max_abs_z >= 6.0 and persistence >= 10) or ratio >= 2.0
        level = "high" if high else "medium"
        if high:
            risk_score = max(risk_score, 65.0)
        return level, round(risk_score, 1)


class FaultClassifier:
    """Классификатор типа неисправности по окну 30 секунд."""

    def __init__(self) -> None:
        payload = joblib.load(ARTIFACTS / "fault_model.joblib")
        self.model = payload["model"]
        self.labels: dict[str, str] = payload["labels"]
        self.classes: list[str] = list(payload["classes"])
        self.window: int = int(payload["window"])

    def predict(self, window: pd.DataFrame) -> dict | None:
        if len(window) < 5:
            return None
        features = window_features(window).reshape(1, -1)
        probabilities = self.model.predict_proba(features)[0]
        index = int(np.argmax(probabilities))
        fault_type = str(self.model.classes_[index])
        return {
            "type": fault_type,
            "label": self.labels.get(fault_type, fault_type),
            "confidence": round(float(probabilities[index]), 3),
            "probabilities": {
                str(cls): round(float(prob), 3)
                for cls, prob in zip(self.model.classes_, probabilities)
            },
        }
