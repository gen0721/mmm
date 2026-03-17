"""
🗄️ DATABASE LAYER — PostgreSQL для Userbot
Полностью заменяет все JSON файлы.
Использует asyncpg для async работы с PostgreSQL.
Fallback на JSON если DATABASE_URL не задан.
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Any

log = logging.getLogger("DB")

DATABASE_URL = os.getenv("DATABASE_URL", "")

# ── Глобальный пул соединений ──
_pool = None

async def get_pool():
    global _pool
    if _pool is None and DATABASE_URL:
        try:
            import asyncpg
            _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
            log.info("✅ PostgreSQL пул создан")
        except Exception as e:
            log.error(f"❌ PostgreSQL недоступен: {e}. Fallback на JSON.")
            _pool = False
    return _pool if _pool else None

async def init_db():
    """Создаёт все таблицы если не существуют"""
    pool = await get_pool()
    if not pool:
        log.info("📁 Используется JSON хранилище")
        return False

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS kv_store (
                key     TEXT PRIMARY KEY,
                value   JSONB NOT NULL,
                updated TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS chat_memory (
                chat_id  BIGINT,
                role     TEXT,
                content  TEXT,
                ts       TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (chat_id, ts)
            );

            CREATE TABLE IF NOT EXISTS group_history (
                chat_id  BIGINT,
                name     TEXT,
                text     TEXT,
                time     TEXT,
                ts       TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_gh_chat ON group_history(chat_id);

            CREATE TABLE IF NOT EXISTS people (
                user_id  BIGINT PRIMARY KEY,
                data     JSONB NOT NULL,
                updated  TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS episodes (
                id       SERIAL PRIMARY KEY,
                chat_id  BIGINT,
                type     TEXT,
                content  TEXT,
                meta     JSONB DEFAULT '{}',
                ts       TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_ep_chat ON episodes(chat_id);

            CREATE TABLE IF NOT EXISTS reminders (
                id        SERIAL PRIMARY KEY,
                text      TEXT,
                fire_at   DOUBLE PRECISION,
                done      BOOLEAN DEFAULT FALSE,
                created   TEXT
            );

            CREATE TABLE IF NOT EXISTS price_alerts (
                id           SERIAL PRIMARY KEY,
                symbol       TEXT,
                target_price DOUBLE PRECISION,
                direction    TEXT,
                done         BOOLEAN DEFAULT FALSE,
                type         TEXT DEFAULT 'crypto'
            );

            CREATE TABLE IF NOT EXISTS security_log (
                id    SERIAL PRIMARY KEY,
                uid   BIGINT,
                type  TEXT,
                text  TEXT,
                ts    TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS channel_monitors (
                channel   TEXT PRIMARY KEY,
                settings  JSONB,
                last_id   BIGINT DEFAULT 0
            );
        """)
    log.info("✅ Таблицы инициализированы")
    return True

# ═══════════════════════════════════════════════════════════
# УНИВЕРСАЛЬНОЕ KV ХРАНИЛИЩЕ
# Хранит: config, global_memory, self_learning, knowledge_base,
#         clone_style, negotiation, multipersona, mention_monitor,
#         dialog_summaries, feedback
# ═══════════════════════════════════════════════════════════

async def kv_get(key: str, default=None) -> Any:
    """Получить значение по ключу"""
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT value FROM kv_store WHERE key=$1", key)
            if row:
                val = row["value"]
                # asyncpg может вернуть JSONB как строку — парсим явно
                if isinstance(val, str):
                    try:
                        val = json.loads(val)
                    except Exception:
                        pass
                log.debug(f"kv_get OK: key={key} type={type(val).__name__}")
                return val
        log.debug(f"kv_get MISS: key={key}")
        return default
    # Fallback JSON
    fname = f"{key}.json"
    if os.path.exists(fname):
        try:
            with open(fname, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return default

async def kv_set(key: str, value: Any):
    """Сохранить значение по ключу"""
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            json_str = json.dumps(value, ensure_ascii=False)
            await conn.execute("""
                INSERT INTO kv_store (key, value, updated)
                VALUES ($1, $2::jsonb, NOW())
                ON CONFLICT (key) DO UPDATE
                SET value=$2::jsonb, updated=NOW()
            """, key, json_str)
        log.debug(f"kv_set OK: key={key} len={len(json_str)}")
        return
    # Fallback JSON
    fname = f"{key}.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
    log.debug(f"kv_set JSON fallback: {fname}")

# ═══════════════════════════════════════════════════════════
# CHAT MEMORY (рабочая память диалогов)
# ═══════════════════════════════════════════════════════════

async def memory_get(chat_id: int, limit: int = 32) -> list:
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT role, content FROM chat_memory
                WHERE chat_id=$1
                ORDER BY ts DESC LIMIT $2
            """, chat_id, limit)
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    # Fallback — читаем из старого in-memory (будет передан снаружи)
    return []

async def memory_add(chat_id: int, role: str, content: str):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chat_memory (chat_id, role, content) VALUES ($1,$2,$3)",
                chat_id, role, content
            )
            # Оставляем только последние 32 сообщения
            await conn.execute("""
                DELETE FROM chat_memory WHERE chat_id=$1 AND ts NOT IN (
                    SELECT ts FROM chat_memory WHERE chat_id=$1
                    ORDER BY ts DESC LIMIT 32
                )
            """, chat_id)

async def memory_clear(chat_id: int):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM chat_memory WHERE chat_id=$1", chat_id)

# ═══════════════════════════════════════════════════════════
# GROUP HISTORY (история группы)
# ═══════════════════════════════════════════════════════════

async def history_add(chat_id: int, name: str, text: str, time: str):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO group_history (chat_id,name,text,time) VALUES ($1,$2,$3,$4)",
                chat_id, name, text[:300], time
            )
            # Оставляем последние 200
            await conn.execute("""
                DELETE FROM group_history WHERE chat_id=$1 AND ts NOT IN (
                    SELECT ts FROM group_history WHERE chat_id=$1
                    ORDER BY ts DESC LIMIT 200
                )
            """, chat_id)

async def history_get(chat_id: int, limit: int = 40) -> list:
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT name,text,time FROM group_history
                WHERE chat_id=$1 ORDER BY ts DESC LIMIT $2
            """, chat_id, limit)
            return [{"name":r["name"],"text":r["text"],"time":r["time"]} for r in reversed(rows)]
    return []

async def history_clear(chat_id: int):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM group_history WHERE chat_id=$1", chat_id)

# ═══════════════════════════════════════════════════════════
# PEOPLE MEMORY (профили людей)
# ═══════════════════════════════════════════════════════════

async def people_get(user_id: int) -> dict | None:
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT data FROM people WHERE user_id=$1", user_id)
            if row:
                d = row["data"]
                if isinstance(d, str):
                    try: d = json.loads(d)
                    except: d = {}
                return d if isinstance(d, dict) else None
    return None

async def people_set(user_id: int, data: dict):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO people (user_id, data, updated)
                VALUES ($1, $2::jsonb, NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET data=$2::jsonb, updated=NOW()
            """, user_id, json.dumps(data, ensure_ascii=False))

async def people_all() -> dict:
    """Возвращает всех людей как {str(user_id): data}"""
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id, data FROM people")
            result = {}
            for r in rows:
                d = r["data"]
                if isinstance(d, str):
                    try: d = json.loads(d)
                    except: d = {}
                result[str(r["user_id"])] = d if isinstance(d, dict) else {}
            return result
    return {}

# ═══════════════════════════════════════════════════════════
# EPISODES (эпизодическая память)
# ═══════════════════════════════════════════════════════════

async def episode_add(chat_id: int, ep_type: str, content: str, meta: dict = None):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO episodes (chat_id,type,content,meta) VALUES ($1,$2,$3,$4::jsonb)",
                chat_id, ep_type, content[:500], json.dumps(meta or {})
            )
            # Оставляем последние 50 на чат
            await conn.execute("""
                DELETE FROM episodes WHERE chat_id=$1 AND id NOT IN (
                    SELECT id FROM episodes WHERE chat_id=$1
                    ORDER BY ts DESC LIMIT 50
                )
            """, chat_id)

async def episodes_get(chat_id: int, limit: int = 5) -> list:
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT type,content,ts FROM episodes
                WHERE chat_id=$1 ORDER BY ts DESC LIMIT $2
            """, chat_id, limit)
            return [{"type": str(r["type"]),
                     "content": str(r["content"]),
                     "date": r["ts"].strftime("%d.%m.%Y %H:%M")} for r in reversed(rows)]
    return []

async def episodes_clear(chat_id: int):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM episodes WHERE chat_id=$1", chat_id)

# ═══════════════════════════════════════════════════════════
# REMINDERS
# ═══════════════════════════════════════════════════════════

async def reminders_get_active() -> list:
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id,text,fire_at,created FROM reminders WHERE done=FALSE")
            return [{"id":r["id"],"text":r["text"],"fire_at":r["fire_at"],"done":False,"created":r["created"]} for r in rows]
    return []

async def reminder_add(text: str, fire_at: float, created: str):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO reminders (text,fire_at,created) VALUES ($1,$2,$3)",
                text, fire_at, created
            )

async def reminder_done(reminder_id: int):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute("UPDATE reminders SET done=TRUE WHERE id=$1", reminder_id)

async def reminders_clear_done():
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM reminders WHERE done=TRUE")

# ═══════════════════════════════════════════════════════════
# PRICE ALERTS
# ═══════════════════════════════════════════════════════════

async def alerts_get_active() -> list:
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id,symbol,target_price,direction,type FROM price_alerts WHERE done=FALSE")
            return [{"id":r["id"],"symbol":r["symbol"],"target_price":r["target_price"],
                     "direction":r["direction"],"type":r["type"],"done":False} for r in rows]
    return []

async def alert_add(symbol: str, target_price: float, direction: str, asset_type: str = "crypto"):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO price_alerts (symbol,target_price,direction,type) VALUES ($1,$2,$3,$4)",
                symbol, target_price, direction, asset_type
            )

async def alert_done(alert_id: int):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute("UPDATE price_alerts SET done=TRUE WHERE id=$1", alert_id)

# ═══════════════════════════════════════════════════════════
# SECURITY LOG
# ═══════════════════════════════════════════════════════════

async def security_log_add(uid: int, attack_type: str, text: str):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO security_log (uid,type,text) VALUES ($1,$2,$3)",
                uid, attack_type, text[:200]
            )

async def security_log_get(limit: int = 50) -> list:
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT uid,type,text,ts FROM security_log ORDER BY ts DESC LIMIT $1", limit
            )
            return [{"uid":r["uid"],"type":r["type"],"text":r["text"],
                     "date":r["ts"].strftime("%d.%m.%Y %H:%M")} for r in rows]
    return []

async def security_log_clear():
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM security_log")

async def security_log_count(attack_type: str = None) -> int:
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            if attack_type:
                return await conn.fetchval(
                    "SELECT COUNT(*) FROM security_log WHERE type LIKE $1", f"%{attack_type}%"
                )
            return await conn.fetchval("SELECT COUNT(*) FROM security_log")
    return 0

# ═══════════════════════════════════════════════════════════
# CHANNEL MONITORS
# ═══════════════════════════════════════════════════════════

async def monitors_get_all() -> dict:
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT channel,settings FROM channel_monitors")
            result = {}
            for r in rows:
                s = r["settings"]
                if isinstance(s, str):
                    try: s = json.loads(s)
                    except: s = {}
                result[r["channel"]] = s if isinstance(s, dict) else {}
            return result
    return {}

async def monitor_set(channel: str, settings: dict):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO channel_monitors (channel,settings) VALUES ($1,$2::jsonb)
                ON CONFLICT (channel) DO UPDATE SET settings=$2::jsonb
            """, channel, json.dumps(settings, ensure_ascii=False))

async def monitor_delete(channel: str):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM channel_monitors WHERE channel=$1", channel)

async def monitor_get_last_id(channel: str) -> int:
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT last_id FROM channel_monitors WHERE channel=$1", channel)
            return row["last_id"] if row else 0
    return 0

async def monitor_set_last_id(channel: str, last_id: int):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE channel_monitors SET last_id=$2 WHERE channel=$1",
                channel, last_id
            )

# ═══════════════════════════════════════════════════════════
# УТИЛИТЫ
# ═══════════════════════════════════════════════════════════

async def db_stats() -> dict:
    """Статистика базы данных"""
    pool = await get_pool()
    if not pool:
        return {"backend": "JSON files"}
    async with pool.acquire() as conn:
        tables = ["kv_store","chat_memory","group_history","people",
                  "episodes","reminders","price_alerts","security_log","channel_monitors"]
        counts = {}
        for t in tables:
            counts[t] = await conn.fetchval(f"SELECT COUNT(*) FROM {t}")
        return {"backend": "PostgreSQL", "tables": counts}

async def close_pool():
    global _pool
    if _pool and _pool is not False:
        await _pool.close()
        _pool = None
