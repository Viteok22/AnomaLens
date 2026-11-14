"""SQLite: история тревог."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from .config import DB_PATH


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                scenario TEXT,
                fault_type TEXT,
                fault_label TEXT,
                confidence REAL,
                risk_level TEXT,
                risk_score REAL,
                top_sensors TEXT,
                recommendation TEXT,
                recommendation_source TEXT,
                acknowledged INTEGER NOT NULL DEFAULT 0,
                resolved_at TEXT
            )
            """
        )
        connection.commit()


def insert_alert(alert: dict) -> int:
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO alerts (
                created_at, scenario, fault_type, fault_label, confidence,
                risk_level, risk_score, top_sensors, recommendation,
                recommendation_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert.get("created_at", now_iso()),
                alert.get("scenario"),
                alert.get("fault_type"),
                alert.get("fault_label"),
                alert.get("confidence"),
                alert.get("risk_level"),
                alert.get("risk_score"),
                json.dumps(alert.get("top_sensors", []), ensure_ascii=False),
                alert.get("recommendation"),
                alert.get("recommendation_source"),
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def _to_dict(row: sqlite3.Row) -> dict:
    result = dict(row)
    try:
        result["top_sensors"] = json.loads(result.get("top_sensors") or "[]")
    except json.JSONDecodeError:
        result["top_sensors"] = []
    return result


def list_alerts(limit: int = 50) -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_to_dict(row) for row in rows]


def get_alert(alert_id: int) -> dict | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM alerts WHERE id = ?", (alert_id,)
        ).fetchone()
    return _to_dict(row) if row else None


def ack_alert(alert_id: int) -> bool:
    with connect() as connection:
        cursor = connection.execute(
            "UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,)
        )
        connection.commit()
        return cursor.rowcount > 0


def resolve_alert(alert_id: int) -> None:
    with connect() as connection:
        connection.execute(
            "UPDATE alerts SET resolved_at = ? WHERE id = ?",
            (now_iso(), alert_id),
        )
        connection.commit()


def update_alert_risk(alert_id: int, risk_level: str, risk_score: float) -> None:
    with connect() as connection:
        connection.execute(
            "UPDATE alerts SET risk_level = ?, risk_score = ? WHERE id = ?",
            (risk_level, risk_score, alert_id),
        )
        connection.commit()


def update_recommendation(alert_id: int, text: str, source: str) -> None:
    with connect() as connection:
        connection.execute(
            "UPDATE alerts SET recommendation = ?, recommendation_source = ? WHERE id = ?",
            (text, source, alert_id),
        )
        connection.commit()


def alert_counts() -> dict:
    with connect() as connection:
        total = connection.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        unacked = connection.execute(
            "SELECT COUNT(*) FROM alerts WHERE acknowledged = 0"
        ).fetchone()[0]
    return {"total": int(total), "unacknowledged": int(unacked)}
