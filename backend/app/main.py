"""FastAPI: real-time реплей SKAB, детекция, тревоги и рекомендации."""
from __future__ import annotations

import asyncio
import copy
import json
import logging
import re
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
from fastapi import (
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import (
    ALERT_PERSISTENCE,
    ARTIFACTS,
    CALIBRATION_ROWS,
    DATA_DIR,
    DEFAULT_SPEED,
    DEEPSEEK_API_KEY,
    MAX_SPEED,
    RESOLVE_PERSISTENCE,
)
from .db import (
    ack_alert,
    alert_counts,
    get_alert,
    init_db,
    insert_alert,
    list_alerts,
    now_iso,
    resolve_alert,
    update_alert_risk,
    update_recommendation,
)
from .detector import FaultClassifier, PCADetector
from .features import SENSORS, SENSOR_META
from .notifier import format_alert, send_telegram, telegram_configured
from .recommendations import build_recommendation, rule_recommendation
from .scenarios import (
    CUSTOM_DIR,
    is_valid_scenario,
    list_scenarios,
    scenario_info,
    scenario_path,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
# httpx пишет полный URL запроса, а в Telegram URL входит токен бота.
logging.getLogger("httpx").setLevel(logging.WARNING)

FAULT_WINDOW = 30
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_UPLOAD_ROWS = 200_000
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    normal_path = DATA_DIR / "anomaly-free" / "anomaly-free.csv"
    normal = pd.read_csv(normal_path, sep=";", parse_dates=["datetime"])
    detector = PCADetector()
    detector.fit_normal(normal)
    app.state.detector = detector
    app.state.fault = FaultClassifier()

    anomaly_metrics_path = ARTIFACTS / "anomaly_metrics.json"
    if anomaly_metrics_path.exists():
        app.state.anomaly_metrics = json.loads(
            anomaly_metrics_path.read_text(encoding="utf-8")
        )
    else:
        app.state.anomaly_metrics = {}

    fault_metrics_path = ARTIFACTS / "fault_metrics.json"
    if fault_metrics_path.exists():
        app.state.fault_metrics = json.loads(
            fault_metrics_path.read_text(encoding="utf-8")
        )
    else:
        app.state.fault_metrics = {}

    yield


app = FastAPI(title="AnomaLens", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "deepseek_configured": bool(DEEPSEEK_API_KEY),
        "telegram_configured": telegram_configured(),
    }


@app.get("/api/sensors")
async def sensors():
    return [
        {"name": name, "label": meta["label"], "unit": meta["unit"]}
        for name, meta in SENSOR_META.items()
    ]


@app.get("/api/scenarios")
async def scenarios():
    return list_scenarios()


@app.get("/api/metrics")
async def metrics():
    fault = app.state.fault_metrics
    return {
        "detector": app.state.anomaly_metrics,
        "fault_classifier": {
            "accuracy": fault.get("cv_accuracy"),
            "macro_f1": fault.get("cv_macro_f1"),
            "n_samples": fault.get("n_samples"),
            "n_files": fault.get("n_files"),
        },
        "alerts": alert_counts(),
    }


@app.get("/api/alerts")
async def alerts(limit: int = 50):
    return list_alerts(limit=min(max(limit, 1), 200))


@app.post("/api/alerts/{alert_id}/ack")
async def acknowledge(alert_id: int):
    if not ack_alert(alert_id):
        raise HTTPException(status_code=404, detail="alert not found")
    return {"ok": True}


@app.post("/api/alerts/{alert_id}/close")
async def close_alert(alert_id: int):
    if get_alert(alert_id) is None:
        raise HTTPException(status_code=404, detail="alert not found")
    ack_alert(alert_id)
    resolve_alert(alert_id)
    return {"ok": True}


@app.post("/api/telegram/test")
async def telegram_test():
    sent = await send_telegram("✅ Тест уведомлений AnomaLens: канал работает.")
    return {"sent": sent, "configured": telegram_configured()}


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Загрузить CSV и найти старт аномалии моделью, без разметки."""
    filename = Path(file.filename or "upload.csv").name
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", filename)
    if not safe.lower().endswith(".csv"):
        safe += ".csv"

    target = CUSTOM_DIR / safe
    if target.exists():
        target = CUSTOM_DIR / f"{target.stem}_{int(time.time())}.csv"

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file too large")
    target.write_bytes(content)

    try:
        df = pd.read_csv(target, sep=";", parse_dates=["datetime"])
    except Exception:
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail="CSV должен быть с разделителем ';' и колонкой datetime",
        )

    missing = [sensor for sensor in SENSORS if sensor not in df.columns]
    if missing:
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Нет датчиков: {', '.join(missing)}",
        )
    if len(df) < CALIBRATION_ROWS + 20:
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Слишком мало строк: нужно минимум {CALIBRATION_ROWS + 20}",
        )
    if len(df) > MAX_UPLOAD_ROWS:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=413, detail="too many rows")

    df = df.sort_values("datetime").reset_index(drop=True)

    # Предварительное сканирование моделью. Разметка anomaly/changepoint
    # намеренно не используется: файл может быть полностью нулевым.
    detector: PCADetector = copy.deepcopy(app.state.detector)
    try:
        detector.calibrate_session(df)
        persistence = 0
        first_alarm = None
        for index, (_, row) in enumerate(df.iterrows()):
            if detector.score_row(row) > detector.threshold:
                persistence += 1
                if persistence >= ALERT_PERSISTENCE:
                    first_alarm = index - ALERT_PERSISTENCE + 1
                    break
            else:
                persistence = 0
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Не удалось обработать CSV: {exc}")

    start_index = max(
        CALIBRATION_ROWS,
        (first_alarm - 60) if first_alarm is not None else CALIBRATION_ROWS,
    )
    meta = {
        "start_index": start_index,
        "first_alarm": first_alarm,
        "scanned": True,
        "labels_used": False,
    }
    target.with_suffix(".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )
    scenario_info.cache_clear()

    scenario_id = f"custom:{target.stem}"
    return {
        "ok": True,
        "scenario": scenario_info(scenario_id),
        "first_alarm": first_alarm,
        "start_index": start_index,
    }


def _sensor_row(row: pd.Series) -> dict:
    return {sensor: float(row[sensor]) for sensor in SENSORS}


async def _update_recommendation(
    alert_id: int,
    fault_type: str,
    top_sensors: list[dict],
    risk_level: str,
    risk_score: float,
    websocket: WebSocket,
    send_lock: asyncio.Lock,
) -> None:
    text, source = await build_recommendation(
        fault_type, top_sensors, risk_level, risk_score
    )
    update_recommendation(alert_id, text, source)
    try:
        async with send_lock:
            await websocket.send_json(
                {
                    "type": "recommendation",
                    "alert_id": alert_id,
                    "recommendation": text,
                    "source": source,
                }
            )
    except Exception:
        pass

    alert = get_alert(alert_id)
    if alert:
        await send_telegram(format_alert(alert))


@app.websocket("/ws/stream")
async def stream(websocket: WebSocket):
    await websocket.accept()
    send_lock = asyncio.Lock()

    try:
        payload = await websocket.receive_json()
    except Exception:
        await websocket.close()
        return

    scenario_id = payload.get("scenario", "valve_in")
    if not is_valid_scenario(scenario_id):
        await websocket.send_json({"type": "error", "message": "unknown scenario"})
        await websocket.close()
        return

    info = scenario_info(scenario_id)
    df = pd.read_csv(scenario_path(scenario_id), sep=";", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)

    detector: PCADetector = copy.deepcopy(websocket.app.state.detector)
    detector.calibrate_session(df)
    fault_classifier: FaultClassifier = websocket.app.state.fault

    jump = bool(payload.get("jump", True))
    start = info["start_index"] if jump else CALIBRATION_ROWS
    start = max(CALIBRATION_ROWS, min(int(start), len(df) - 1))
    speed = float(payload.get("speed", DEFAULT_SPEED))
    speed = max(1.0, min(speed, MAX_SPEED))

    fault_window: deque[dict] = deque(maxlen=FAULT_WINDOW)
    for _, row in df.iloc[max(0, start - FAULT_WINDOW) : start].iterrows():
        fault_window.append(_sensor_row(row))

    async with send_lock:
        await websocket.send_json(
            {
                "type": "started",
                "scenario": info,
                "start_index": start,
                "rows": len(df),
                "speed": speed,
            }
        )

    persistence = 0
    below = 0
    cooldown = 0
    active_alert: dict | None = None
    fault: dict | None = None

    try:
        for index in range(start, len(df)):
            await asyncio.sleep(1.0 / speed)
            row = df.iloc[index]
            score = detector.score_row(row)
            zscores = detector.zscores(row)
            max_abs_z = max((abs(value) for value in zscores.values()), default=0.0)
            level, risk_score = detector.risk(score, persistence, max_abs_z)
            # Гистерезис: если тревога уже стала высокой, не понижаем её
            # до закрытия, иначе бейдж риска «мигает» на каждом колебании.
            if (
                active_alert is not None
                and active_alert.get("risk_level") == "high"
                and level != "high"
            ):
                level = "high"
                risk_score = max(
                    risk_score,
                    float(active_alert.get("risk_score") or 65.0),
                )

            if score > detector.threshold:
                persistence += 1
                below = 0
            else:
                persistence = 0
                below += 1

            fault_window.append(_sensor_row(row))
            if (score > detector.threshold or active_alert) and index % 5 == 0:
                fault = fault_classifier.predict(pd.DataFrame(list(fault_window)))
            elif score <= detector.threshold and active_alert is None:
                fault = None

            top_sensors = detector.top_sensors(row)

            # Раз в 5 тиков подтягиваем подтверждение/закрытие из SQLite:
            # оператор мог нажать кнопку в интерфейсе.
            if active_alert is not None and index % 5 == 0:
                db_alert = get_alert(active_alert["id"])
                if db_alert is not None:
                    active_alert["acknowledged"] = db_alert["acknowledged"]
                    if db_alert.get("resolved_at"):
                        active_alert = None
                        cooldown = 15

            if active_alert is not None:
                if level != active_alert.get("risk_level"):
                    active_alert["risk_level"] = level
                    active_alert["risk_score"] = risk_score
                    update_alert_risk(active_alert["id"], level, risk_score)
                else:
                    active_alert["risk_score"] = risk_score
                if fault:
                    active_alert["fault_type"] = fault["type"]
                    active_alert["fault_label"] = fault["label"]
                    active_alert["confidence"] = fault["confidence"]

            if (
                active_alert is None
                and persistence >= ALERT_PERSISTENCE
                and cooldown == 0
            ):
                fault_data = fault or {
                    "type": "unknown",
                    "label": "Аномалия",
                    "confidence": 0.0,
                }
                recommendation = rule_recommendation(
                    fault_data["type"], top_sensors, level
                )
                alert = {
                    "created_at": now_iso(),
                    "scenario": scenario_id,
                    "fault_type": fault_data["type"],
                    "fault_label": fault_data["label"],
                    "confidence": fault_data["confidence"],
                    "risk_level": level,
                    "risk_score": risk_score,
                    "top_sensors": top_sensors,
                    "recommendation": recommendation,
                    "recommendation_source": "Правила",
                }
                alert_id = insert_alert(alert)
                alert["id"] = alert_id
                active_alert = alert
                async with send_lock:
                    await websocket.send_json({"type": "alert", "alert": alert})
                asyncio.create_task(
                    _update_recommendation(
                        alert_id,
                        fault_data["type"],
                        top_sensors,
                        level,
                        risk_score,
                        websocket,
                        send_lock,
                    )
                )

            if (
                active_alert is not None
                and below >= RESOLVE_PERSISTENCE
                and active_alert.get("acknowledged")
            ):
                resolve_alert(active_alert["id"])
                async with send_lock:
                    await websocket.send_json(
                        {"type": "resolved", "alert_id": active_alert["id"]}
                    )
                active_alert = None
                cooldown = 15

            if cooldown > 0:
                cooldown -= 1

            async with send_lock:
                await websocket.send_json(
                    {
                        "type": "tick",
                        "timestamp": row["datetime"].isoformat(),
                        "sensors": {
                            sensor: round(float(row[sensor]), 4) for sensor in SENSORS
                        },
                        "zscores": {
                            sensor: round(value, 3)
                            for sensor, value in zscores.items()
                        },
                        "score": round(score, 3),
                        "threshold": round(detector.threshold, 3),
                        "ratio": round(
                            score / detector.threshold if detector.threshold else 0, 2
                        ),
                        "risk_level": level,
                        "risk_score": risk_score,
                        "persistence": persistence,
                        "normal_seconds": below,
                        "auto_close_seconds": RESOLVE_PERSISTENCE,
                        "top_sensors": top_sensors,
                        "fault": fault,
                        "alert_id": active_alert["id"] if active_alert else None,
                    }
                )

        async with send_lock:
            await websocket.send_json({"type": "finished"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("Ошибка стрима: %s", exc)
        try:
            async with send_lock:
                await websocket.send_json(
                    {"type": "error", "message": "stream failed"}
                )
        except Exception:
            pass
    # Тревога не закрывается автоматически при остановке потока:
    # оператор должен подтвердить и закрыть её после проверки.


if FRONTEND_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets"),
        name="assets",
    )

    @app.get("/")
    async def index():
        return FileResponse(FRONTEND_DIST / "index.html")
else:

    @app.get("/")
    async def index_placeholder():
        return {
            "message": "Frontend не собран. Выполните `npm run build` в frontend/."
        }
