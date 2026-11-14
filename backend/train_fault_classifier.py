"""Обучение классификатора типа неисправности на окнах SKAB."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict

from app.features import (
    FAULT_LABELS,
    FAULT_ORDER,
    FEATURE_NAMES,
    fault_class_from_path,
    load_skab,
    window_features,
)

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT.parent / "data" / "skab"
ARTIFACTS = ROOT / "artifacts"
WINDOW = 30
STRIDE = 5


def build_dataset():
    files = load_skab(DATA_DIR)
    rows: list[np.ndarray] = []
    labels: list[str] = []
    groups: list[str] = []

    for rel, df in files.items():
        if rel.startswith("anomaly-free/"):
            continue
        fault = fault_class_from_path(rel)
        if fault is None:
            continue
        anomaly = df["anomaly"].astype(int).to_numpy()
        for start in range(0, len(df) - WINDOW + 1, STRIDE):
            end = start + WINDOW
            # Берём окна, где аномалия занимает хотя бы половину окна.
            if anomaly[start:end].mean() < 0.5:
                continue
            rows.append(window_features(df.iloc[start:end]))
            labels.append(fault)
            groups.append(rel)

    return np.vstack(rows), np.asarray(labels), np.asarray(groups)


def main() -> None:
    print("Сбор окон...")
    X, y, groups = build_dataset()
    print(f"  окон: {len(X)}, признаков: {X.shape[1]}, файлов: {len(set(groups))}")
    print("  классы:", dict(Counter(y)))

    model = RandomForestClassifier(
        n_estimators=400,
        max_depth=None,
        min_samples_leaf=2,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )

    cv = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=42)
    print("Кросс-валидация по файлам (3 фолда)...")
    predictions = cross_val_predict(model, X, y, groups=groups, cv=cv, n_jobs=-1)

    accuracy = float(accuracy_score(y, predictions))
    macro_f1 = float(f1_score(y, predictions, average="macro", zero_division=0))
    report = classification_report(
        y,
        predictions,
        labels=FAULT_ORDER,
        target_names=[FAULT_LABELS[name] for name in FAULT_ORDER],
        zero_division=0,
        output_dict=True,
    )
    matrix = confusion_matrix(y, predictions, labels=FAULT_ORDER).tolist()

    print(f"  accuracy={accuracy:.3f}, macro_f1={macro_f1:.3f}")
    print(
        classification_report(
            y,
            predictions,
            labels=FAULT_ORDER,
            target_names=[FAULT_LABELS[name] for name in FAULT_ORDER],
            zero_division=0,
        )
    )

    model.fit(X, y)
    payload = {
        "model": model,
        "feature_names": FEATURE_NAMES,
        "classes": list(model.classes_),
        "labels": FAULT_LABELS,
        "window": WINDOW,
    }
    joblib.dump(payload, ARTIFACTS / "fault_model.joblib")

    metrics = {
        "cv_accuracy": accuracy,
        "cv_macro_f1": macro_f1,
        "n_samples": int(len(X)),
        "n_files": int(len(set(groups))),
        "class_counts": dict(Counter(y)),
        "classification_report": report,
        "confusion_matrix": matrix,
        "labels_order": FAULT_ORDER,
        "window": WINDOW,
        "stride": STRIDE,
    }
    (ARTIFACTS / "fault_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Модель: {ARTIFACTS / 'fault_model.joblib'}")
    print(f"Метрики: {ARTIFACTS / 'fault_metrics.json'}")


if __name__ == "__main__":
    main()
