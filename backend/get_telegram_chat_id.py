"""Получить chat_id для Telegram-бота.

1. Создайте бота через @BotFather и вставьте токен в backend/.env.
2. Откройте бота по ссылке https://t.me/<username> и нажмите Start.
3. Запустите: .\\.venv\\Scripts\\python.exe get_telegram_chat_id.py
4. Скопируйте chat_id в TELEGRAM_CHAT_ID в backend/.env.
"""
from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

load_dotenv(".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
PROXY = os.getenv("TELEGRAM_PROXY", "").strip() or None


def main() -> None:
    if not TOKEN:
        print("TELEGRAM_BOT_TOKEN не задан в backend/.env")
        return

    client_kwargs = {"timeout": 20.0}
    if PROXY:
        client_kwargs["proxy"] = PROXY
    base = f"https://api.telegram.org/bot{TOKEN}"

    with httpx.Client(**client_kwargs) as client:
        try:
            me = client.get(f"{base}/getMe")
            me.raise_for_status()
            username = me.json()["result"].get("username")
        except Exception as exc:
            print(f"Telegram API недоступен: {type(exc).__name__}: {exc}")
            print("Если Telegram заблокирован, укажите TELEGRAM_PROXY в backend/.env.")
            return

        print(f"Бот: @{username}")
        print("Если вы ещё не открывали бота — сделайте это и нажмите Start.")

        try:
            updates = client.get(f"{base}/getUpdates").json().get("result", [])
        except Exception as exc:
            print(f"Не удалось получить updates: {type(exc).__name__}: {exc}")
            return

    if not updates:
        print("Сообщений пока нет. Откройте бота, нажмите Start и запустите скрипт снова.")
        return

    seen: set[int] = set()
    for update in updates:
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None or chat_id in seen:
            continue
        seen.add(chat_id)
        name = chat.get("username") or chat.get("first_name") or chat.get("title")
        print(f"chat_id={chat_id}  type={chat.get('type')}  name={name}")

    print("Скопируйте chat_id в TELEGRAM_CHAT_ID в backend/.env и перезапустите backend.")


if __name__ == "__main__":
    main()
