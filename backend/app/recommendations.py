"""Гибридные рекомендации: правила + DeepSeek (с fallback)."""
from __future__ import annotations

import logging

import httpx

from .config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
)
from .features import FAULT_LABELS

logger = logging.getLogger(__name__)

RISK_RU = {"high": "высокий", "medium": "средний", "low": "низкий"}

RULES: dict[str, list[str]] = {
    "valve_in": [
        "Проверить, открыт ли входной клапан и не заблокирован ли его привод.",
        "Сверить давление на входе и расход; при падении расхода снизить нагрузку на насос.",
        "Если клапан не реагирует — остановить насос по регламенту и вызвать бригаду.",
    ],
    "valve_out": [
        "Проверить выходной клапан и линию сброса: не закрыты ли они.",
        "Сверить давление в контуре и расход; при росте давления снизить подачу.",
        "При подтверждении отказа клапана остановить насос и передать заявку на ремонт.",
    ],
    "leak": [
        "Проверить герметичность контура, соединения и уровень жидкости в резервуаре.",
        "Зафиксировать падение давления и расход; при утечке перекрыть подачу.",
        "Если утечка продолжается — остановить оборудование и вызвать ремонтную бригаду.",
    ],
    "rotor_imbalance": [
        "Проверить вибрацию, крепления и состояние подшипников.",
        "Снизить обороты насоса до выяснения причины дисбаланса.",
        "При росте вибрации остановить агрегат и провести балансировку ротора.",
    ],
    "cavitation_overheat": [
        "Проверить температуру, давление на входе и наличие кавитации.",
        "Снизить нагрузку и обеспечить нормальное охлаждение/подпор.",
        "Если температура не стабилизируется — остановить насос по регламенту.",
    ],
}

_cache: dict[tuple, tuple[str, str]] = {}


def rule_recommendation(
    fault_type: str, top_sensors: list[dict], risk_level: str
) -> str:
    steps = RULES.get(
        fault_type,
        [
            "Проверить показания датчиков и убедиться в отсутствии внешних помех.",
            "Снизить нагрузку и наблюдать за развитием отклонения.",
            "При сохранении аномалии остановить оборудование и вызвать специалиста.",
        ],
    )
    return "\n".join(
        f"{index}. {step}" for index, step in enumerate(steps, start=1)
    )


async def llm_recommendation(
    fault_type: str,
    top_sensors: list[dict],
    risk_level: str,
    risk_score: float,
) -> str | None:
    if not DEEPSEEK_API_KEY:
        return None

    sensor_text = ", ".join(
        f"{item['label']} (z={item['z']})" for item in top_sensors[:3]
    )
    values_text = ", ".join(
        f"{item['label']}={item['value']} {item['unit']}" for item in top_sensors[:3]
    )
    prompt = (
        "Ты — инженер по техническому обслуживанию промышленного насосного "
        "оборудования. Система мониторинга обнаружила аномалию.\n\n"
        f"Тип неисправности: {FAULT_LABELS.get(fault_type, fault_type)}.\n"
        f"Уровень риска: {RISK_RU.get(risk_level, risk_level)} ({risk_score}/100).\n"
        f"Датчики с наибольшим отклонением: {sensor_text}.\n"
        f"Текущие значения: {values_text}.\n\n"
        "Дай ровно 3 конкретных шага для предотвращения аварии. "
        "Кратко, по-русски, без вступления и общих фраз. "
        "Не предлагай автоматически останавливать оборудование — только "
        "рекомендации оператору. Это учебный прототип, не заменяй регламент."
    )
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Ты — опытный инженер по предиктивному обслуживанию.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 260,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            return content or None
    except Exception as exc:
        logger.warning("DeepSeek недоступен: %s", exc)
        return None


async def build_recommendation(
    fault_type: str,
    top_sensors: list[dict],
    risk_level: str,
    risk_score: float,
) -> tuple[str, str]:
    key = (
        fault_type,
        tuple(item["name"] for item in top_sensors[:3]),
        risk_level,
    )
    if key in _cache:
        return _cache[key]

    text = await llm_recommendation(fault_type, top_sensors, risk_level, risk_score)
    if text:
        result = (text, "DeepSeek")
    else:
        result = (rule_recommendation(fault_type, top_sensors, risk_level), "Правила")
    _cache[key] = result
    return result
