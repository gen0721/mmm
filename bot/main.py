"""
🚀 MAIN.PY — Точка входа модульного Userbot v7.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Структура:
  bot/
    config.py          — конфигурация и синхронизация с DB
    ai/
      providers.py     — все AI провайдеры (Groq, Gemini, Claude, Polza...)
      nlu.py           — NLU система (81+ интент)
    memory/
      store.py         — 4-слойная память
    security/
      guard.py         — защита от атак
    features/          — функциональные модули
    handlers/          — обработчики сообщений
"""

import os
import sys
import asyncio
import logging
import warnings

# ── Подавляем лишние логи ──
warnings.filterwarnings("ignore")
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logging.getLogger("pyrogram").setLevel(logging.CRITICAL)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
log = logging.getLogger("Userbot")


def load_env():
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())
load_env()


# ── Инициализация модулей ──
from bot.config import (
    API_ID, API_HASH, SESSION_STRING, OWNER_ID,
    config, init_config, save_config, config_sync_loop,
    load_config_from_db, USE_DB
)
from bot.memory.store import init_memory
from bot.security.guard import security_check
from bot.ai.providers import AI_MAP, smart_request, ensemble_request
from bot.ai.nlu import parse_intent, nlu_fallback


# ── Проверка обязательных переменных ──
if not API_ID or not API_HASH or not SESSION_STRING:
    log.error("❌ API_ID, API_HASH или SESSION_STRING не заданы!")
    sys.exit(1)


# ── Pyrogram клиент ──
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.enums import ChatType

app = Client(
    "userbot_v7",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    no_updates=False,
)


# ══════════════════════════════════════════════
# ИМПОРТ ОБРАБОТЧИКОВ
# После инициализации клиента
# ══════════════════════════════════════════════

# NOTE: handlers импортируются здесь чтобы они могли использовать `app`
# В будущем будут вынесены в bot/handlers/


# ══════════════════════════════════════════════
# ЗАПУСК
# ══════════════════════════════════════════════

async def main():
    """Главная функция запуска"""
    log.info("🚀 Userbot v7.0 — Модульная архитектура")

    await app.start()

    # 1. База данных
    from database import init_db
    db_ok = await init_db()
    log.info(f"🗄️ БД: {'PostgreSQL ✅' if db_ok else 'JSON 📁'}")

    # 2. Конфиг
    init_config()
    if USE_DB:
        await load_config_from_db()
        asyncio.create_task(config_sync_loop())

    # 3. Память
    init_memory()

    # 4. Фоновые задачи
    # asyncio.create_task(reminders_loop(app))
    # asyncio.create_task(channel_monitor_loop(app))
    # asyncio.create_task(price_alert_loop(app))
    # asyncio.create_task(backup_loop(app))
    # asyncio.create_task(mention_monitor_loop(app))
    # asyncio.create_task(self_development_loop(app))

    log.info(f"✅ Запущен! OWNER_ID={OWNER_ID} | AI={config.get('active_ai','groq')}")

    await idle()
    await app.stop()


if __name__ == "__main__":
    app.run(main())
