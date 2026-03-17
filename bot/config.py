"""
⚙️ CONFIG — Конфигурация и синхронизация
Единый источник правды для userbot и control_bot через PostgreSQL
"""

import os
import json
import asyncio
import logging

log = logging.getLogger("Config")

CONFIG_FILE = "userbot_config.json"

# ── Переменные окружения ──
API_ID         = int(os.getenv("API_ID", "0"))
API_HASH       = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
OWNER_ID       = int(os.getenv("OWNER_ID", "0"))

# AI ключи
GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "")
COHERE_API_KEY   = os.getenv("COHERE_API_KEY", "")
CLAUDE_API_KEY   = os.getenv("CLAUDE_API_KEY", "")
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
MISTRAL_API_KEY  = os.getenv("MISTRAL_API_KEY", "")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")
HF_API_KEY       = os.getenv("HF_API_KEY", "")
POLZA_API_KEY    = os.getenv("POLZA_API_KEY", "")
POLZA_MODEL      = os.getenv("POLZA_MODEL", "openai/gpt-4o-mini")

DATABASE_URL     = os.getenv("DATABASE_URL", "")
USE_DB           = bool(DATABASE_URL)
ENCRYPT_KEY      = os.getenv("MEMORY_KEY", "")
WEBHOOK_PORT     = int(os.getenv("WEBHOOK_PORT", "8080"))
WEBHOOK_TOKEN    = os.getenv("WEBHOOK_TOKEN", "")

# ── Дефолтный конфиг ──
DEFAULT_CONFIG: dict = {
    "active_ai":        "groq",
    "trigger":          "+",
    "owner_trigger":    ".",
    "public_trigger":   "+",
    "whitelist_on":     False,
    "whitelist":        [],
    "blacklist":        [],
    "all_blocked":      False,
    "memory_on":        True,
    "memory_depth":     8,
    "history_depth":    20,
    "autoreply_on":     False,
    "autoreply_text":   "сейчас нет, напишу позже",
    "mention_reply":    True,
    "translate_on":     True,
    "voice_reply":      True,
    "photo_analysis":   True,
    "antispam_delay":   6,
    "spy_mode":         False,
    "auto_status":      False,
    "link_summary":     True,
    "mention_notify":   True,
    "copy_target":      "me",
    "pm_autoreply":     False,
    "contacts_file":    "contacts.json",
    "mood_analysis":    True,
    "people_memory":    True,
    "auto_summary":     True,
    "schedule_channel": "",
    "schedule_posts":   [],
    "persona_name":     "",
    "persona_desc":     "",
    "persona_on":       False,
    "tts_reply":        False,
    "voice_answer":     False,
    "face_analysis":    True,
    "autodestruct":     0,
    "mat_filter":       True,
    "2fa_on":           False,
    "paranoia_hours":   0,
    "sticker_reply":    True,
    "call_reply":       True,
    "auto_join":        False,
    "auto_join_interval": 60,
    "auto_join_messages": 3,
    "stats":            {"total": 0, "voice": 0, "photo": 0, "translate": 0},
}

# Глобальный объект конфига — единственный экземпляр
config: dict = dict(DEFAULT_CONFIG)


def load_config_from_file() -> dict:
    """Читает конфиг из JSON файла"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            log.debug(f"Config file read error: {e}")
    return {}


def save_config_to_file(cfg: dict):
    """Сохраняет конфиг в JSON файл"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.debug(f"Config file write error: {e}")


def init_config():
    """Инициализация конфига при старте — читает из файла"""
    global config
    file_cfg = load_config_from_file()
    if file_cfg:
        config.update(file_cfg)
    log.info(f"⚙️ Конфиг загружен: ai={config['active_ai']} autoreply={config['autoreply_on']}")


def save_config(cfg: dict = None):
    """Сохраняет конфиг в файл + DB"""
    global config
    if cfg is not None:
        config.update(cfg)
    save_config_to_file(config)
    if USE_DB:
        try:
            asyncio.create_task(_async_save_config(config.copy()))
        except RuntimeError:
            pass


async def _async_save_config(cfg: dict):
    """Асинхронно сохраняет в PostgreSQL"""
    try:
        from database import kv_set
        await kv_set("config", cfg)
        log.debug(f"Config saved to DB: autoreply={cfg.get('autoreply_on')} ai={cfg.get('active_ai')}")
    except Exception as e:
        log.debug(f"DB config save error: {e}")


async def load_config_from_db() -> dict:
    """Загружает конфиг из PostgreSQL"""
    try:
        from database import kv_get
        data = await kv_get("config")
        if data and isinstance(data, dict) and len(data) > 3:
            return data
    except Exception as e:
        log.debug(f"DB config load error: {e}")
    return {}


async def sync_config_once():
    """Разовая синхронизация из DB"""
    global config
    db_cfg = await load_config_from_db()
    if db_cfg:
        changed = [k for k in db_cfg if db_cfg.get(k) != config.get(k)]
        config.update(db_cfg)
        if changed:
            log.info(f"🔄 Конфиг из DB: {', '.join(changed[:5])}")
        return True
    return False


async def config_sync_loop():
    """Фоновая синхронизация конфига из DB каждые 3 секунды"""
    global config
    await asyncio.sleep(3)
    while True:
        try:
            db_cfg = await load_config_from_db()
            if db_cfg:
                changed = []
                for key in ["autoreply_on", "pm_autoreply", "active_ai", "mat_filter",
                            "all_blocked", "whitelist_on", "persona_on", "memory_on",
                            "translate_on", "voice_reply", "photo_analysis", "spy_mode",
                            "tts_reply", "auto_status", "link_summary", "autoreply_text",
                            "memory_depth", "antispam_delay", "autodestruct",
                            "sticker_reply", "call_reply", "auto_join", "whitelist", "blacklist"]:
                    old_val = config.get(key)
                    new_val = db_cfg.get(key)
                    if old_val != new_val:
                        changed.append(f"{key}:{old_val}→{new_val}")
                config.update(db_cfg)
                if changed:
                    log.info(f"🔄 Конфиг применён: {' | '.join(changed)}")
        except Exception as e:
            log.debug(f"Config sync error: {e}")
        await asyncio.sleep(3)
