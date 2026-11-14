"""Telegram-уведомления."""
from __future__ import annotations

import logging

import httpx

from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_PROXY

logger = logging.getLogger(__name__)

RISK_RU = {"high": "Высокий", "medium": "Средний", "low": "Низкий"}


def telegram_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def format_alert(alert: dict) -> str:
    sensors = ", ".join(
        f"{item['label']} (z={item['z']})" for item in alert.get("top_sensors", [])[:3]
    )
    recommendation = (alert.get("recommendation") or "").strip()
    if len(recommendation) > 900:
        recommendation = recommendation[:900] + "..."
    return (
        f"🚨 {RISK_RU.get(alert.get('risk_level'), alert.get('risk_level'))} риск: "
        f"{alert.get('fault_label')}\n"
        f"Сценарий: {alert.get('scenario')}\n"
        f"Уверенность: {alert.get('confidence')}\n"
        f"Датчики: {sensors}\n\n"
        f"{recommendation}"
    )


async def send_telegram(text: str) -> bool:
    if not telegram_configured():
        return False
    try:
        client_kwargs = {"timeout": 6.0}
        if TELEGRAM_PROXY:
            client_kwargs["proxy"] = TELEGRAM_PROXY
        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": text[:3900]},
            )
            response.raise_for_status()
            return True
    except Exception as exc:
        logger.warning("Telegram недоступен: %s", exc)
        return False
