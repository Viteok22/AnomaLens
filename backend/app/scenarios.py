"""Сценарии: встроенные SKAB + пользовательские CSV из data/custom."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .config import CALIBRATION_ROWS, DATA_DIR
from .features import FAULT_LABELS, SENSORS

CUSTOM_DIR = DATA_DIR.parent / "custom"
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
CUSTOM_PREFIX = "custom:"

SCENARIOS = [
    {
        "id": "valve_in",
        "file": "valve1/10.csv",
        "label": FAULT_LABELS["valve_in"],
        "short": "Входной клапан",
        "description": "Клапан на входе насоса закрывается: падает расход, меняется давление и ток.",
    },
    {
        "id": "valve_out",
        "file": "valve2/0.csv",
        "label": FAULT_LABELS["valve_out"],
        "short": "Выходной клапан",
        "description": "Клапан на выходе закрывается: растёт давление в контуре, падает расход.",
    },
    {
        "id": "leak",
        "file": "other/2.csv",
        "label": FAULT_LABELS["leak"],
        "short": "Утечка",
        "description": "Утечка или изменение количества жидкости: давление и расход уходят от нормы.",
    },
    {
        "id": "rotor_imbalance",
        "file": "other/6.csv",
        "label": FAULT_LABELS["rotor_imbalance"],
        "short": "Дисбаланс ротора",
        "description": "Дисбаланс ротора: растёт вибрация, меняется ток двигателя.",
    },
    {
        "id": "cavitation_overheat",
        "file": "other/14.csv",
        "label": FAULT_LABELS["cavitation_overheat"],
        "short": "Кавитация / перегрев",
        "description": "Кавитация или перегрев: растёт температура, меняется давление.",
    },
]

SCENARIO_ORDER = [item["id"] for item in SCENARIOS]
SCENARIO_BY_ID = {item["id"]: item for item in SCENARIOS}


def _custom_id(stem: str) -> str:
    return f"{CUSTOM_PREFIX}{stem}"


def _custom_path(scenario_id: str) -> Path:
    stem = scenario_id.split(":", 1)[1]
    return CUSTOM_DIR / f"{stem}.csv"


def _fill_metrics(scenario: dict, path: Path) -> dict:
    if not path.exists():
        raise KeyError(path.name)
    df = pd.read_csv(path, sep=";", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)

    missing = [sensor for sensor in SENSORS if sensor not in df.columns]
    if missing:
        raise ValueError(f"{path.name}: нет датчиков {missing}")

    if "anomaly" not in df.columns:
        df["anomaly"] = 0
    anomaly = df["anomaly"].astype(int).to_numpy()
    first_anomaly = int(anomaly.argmax()) if anomaly.any() else None

    start_index = max(
        CALIBRATION_ROWS,
        (first_anomaly - 60) if first_anomaly is not None else CALIBRATION_ROWS,
    )
    scenario.update(
        {
            "first_anomaly": first_anomaly,
            "rows": int(len(df)),
            "duration_s": int(len(df)),
            "start_index": start_index,
        }
    )

    # Для загруженных файлов старт берём из предварительного сканирования
    # моделью, а не из разметки (она может быть вся нулевая).
    if scenario.get("custom"):
        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                scenario["start_index"] = int(meta.get("start_index", start_index))
                scenario["first_alarm"] = meta.get("first_alarm")
                scenario["scanned"] = bool(meta.get("scanned", False))
                scenario["labels_used"] = bool(meta.get("labels_used", False))
                scenario["label"] = f"Загружено · {path.stem}"
                scenario["uploaded"] = True
                scenario["description"] = (
                    "Загруженный CSV: 8 датчиков, 1 Гц. Разметка не используется — "
                    "модель ищет аномалии сама."
                )
            except Exception:
                pass

    return scenario


@lru_cache(maxsize=32)
def scenario_info(scenario_id: str) -> dict:
    if scenario_id.startswith(CUSTOM_PREFIX):
        path = _custom_path(scenario_id)
        if not path.exists():
            raise KeyError(scenario_id)
        scenario = {
            "id": scenario_id,
            "file": f"custom/{path.name}",
            "label": f"Синтетика · {path.stem}",
            "short": path.stem,
            "description": "Пользовательский CSV: 8 датчиков, 1 Гц, разметка anomaly/changepoint.",
            "custom": True,
        }
        return _fill_metrics(scenario, path)

    if scenario_id not in SCENARIO_BY_ID:
        raise KeyError(scenario_id)
    scenario = dict(SCENARIO_BY_ID[scenario_id])
    return _fill_metrics(scenario, DATA_DIR / scenario["file"])


def list_scenarios() -> list[dict]:
    result = [scenario_info(item) for item in SCENARIO_ORDER]
    for path in sorted(CUSTOM_DIR.glob("*.csv")):
        try:
            result.append(scenario_info(_custom_id(path.stem)))
        except Exception:
            # Битый или неполный CSV не должен ломать весь список.
            continue
    return result


def scenario_path(scenario_id: str) -> Path:
    if scenario_id.startswith(CUSTOM_PREFIX):
        return _custom_path(scenario_id)
    return DATA_DIR / SCENARIO_BY_ID[scenario_id]["file"]


def is_valid_scenario(scenario_id: str) -> bool:
    try:
        scenario_info(scenario_id)
        return True
    except Exception:
        return False
