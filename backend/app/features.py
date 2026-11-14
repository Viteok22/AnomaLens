"""Общие признаки и классы неисправностей для обучения и инференса."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SENSORS = [
    "Accelerometer1RMS",
    "Accelerometer2RMS",
    "Current",
    "Pressure",
    "Temperature",
    "Thermocouple",
    "Voltage",
    "Volume Flow RateRMS",
]

SENSOR_META = {
    "Accelerometer1RMS": {"label": "Вибрация 1", "unit": "g"},
    "Accelerometer2RMS": {"label": "Вибрация 2", "unit": "g"},
    "Current": {"label": "Ток", "unit": "A"},
    "Pressure": {"label": "Давление", "unit": "бар"},
    "Temperature": {"label": "Температура двигателя", "unit": "°C"},
    "Thermocouple": {"label": "Температура жидкости", "unit": "°C"},
    "Voltage": {"label": "Напряжение", "unit": "В"},
    "Volume Flow RateRMS": {"label": "Расход", "unit": "л/мин"},
}

FAULT_LABELS = {
    "valve_in": "Закрытие входного клапана",
    "valve_out": "Закрытие выходного клапана",
    "leak": "Утечка / изменение уровня",
    "rotor_imbalance": "Дисбаланс ротора",
    "cavitation_overheat": "Кавитация / перегрев",
}

FAULT_ORDER = [
    "valve_in",
    "valve_out",
    "leak",
    "rotor_imbalance",
    "cavitation_overheat",
]

FEATURE_NAMES: list[str] = []
for sensor in SENSORS:
    FEATURE_NAMES.extend(
        [
            f"{sensor}_mean",
            f"{sensor}_std",
            f"{sensor}_min",
            f"{sensor}_max",
            f"{sensor}_last",
            f"{sensor}_slope",
        ]
    )


def fault_class_from_path(relative_path: str) -> str | None:
    """Определяет класс неисправности по имени файла SKAB."""
    path = Path(relative_path)
    parent = path.parent.as_posix()
    name = path.stem
    if parent == "valve1":
        return "valve_in"
    if parent == "valve2":
        return "valve_out"
    if parent == "other":
        try:
            number = int(name)
        except ValueError:
            return None
        if number in {1, 2, 3, 4, 10, 11}:
            return "leak"
        if number in {5, 6, 7, 8, 9}:
            return "rotor_imbalance"
        if number in {12, 13, 14}:
            return "cavitation_overheat"
    return None


def window_features(window: pd.DataFrame) -> np.ndarray:
    """48 признаков окна: mean/std/min/max/last/slope по 8 датчикам."""
    values: list[float] = []
    for sensor in SENSORS:
        series = window[sensor].to_numpy(dtype=float)
        values.extend(
            [
                float(np.mean(series)),
                float(np.std(series)),
                float(np.min(series)),
                float(np.max(series)),
                float(series[-1]),
                float((series[-1] - series[0]) / max(len(series) - 1, 1)),
            ]
        )
    return np.asarray(values, dtype=float)


def load_skab(data_dir: Path) -> dict[str, pd.DataFrame]:
    files: dict[str, pd.DataFrame] = {}
    for path in sorted(data_dir.rglob("*.csv")):
        rel = path.relative_to(data_dir).as_posix()
        df = pd.read_csv(path, sep=";", parse_dates=["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        for column in ("anomaly", "changepoint"):
            if column not in df.columns:
                df[column] = 0
        missing = [sensor for sensor in SENSORS if sensor not in df.columns]
        if missing:
            raise ValueError(f"{rel}: нет датчиков {missing}")
        files[rel] = df
    return files
