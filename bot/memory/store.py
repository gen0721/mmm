"""
🧠 MEMORY — Система памяти
4 слоя: рабочая / эпизодическая / семантическая / глобальная
"""

import json
import logging
import asyncio
from collections import defaultdict, deque
from datetime import datetime
from typing import Optional

log = logging.getLogger("Memory")

# ── Файлы хранения ──
MEMORY_FILE   = "userbot_memory.json"
HISTORY_FILE  = "chat_history.json"
EPISODIC_FILE = "episodic_memory.json"
PEOPLE_FILE   = "people_memory.json"
GLOBAL_FILE   = "global_memory.json"
SUMMARIES_FILE = "dialog_summaries.json"

# ── In-memory хранилища ──
chat_memory:    dict[int, deque] = defaultdict(lambda: deque(maxlen=32))
group_history:  dict[int, deque] = defaultdict(lambda: deque(maxlen=200))
episodic_memory: dict = {}
people_memory:   dict = {}
global_memory:   dict = {}
dialog_summaries: dict = {}


# ═══════════════════════════════════════════════
# ИНИЦИАЛИЗАЦИЯ
# ═══════════════════════════════════════════════

def init_memory():
    """Загружает всю память при старте"""
    global episodic_memory, people_memory, global_memory, dialog_summaries

    # Рабочая память
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            for cid, msgs in json.load(f).items():
                chat_memory[int(cid)] = deque(msgs, maxlen=32)
    except: pass

    # История групп
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for cid, msgs in json.load(f).items():
                group_history[int(cid)] = deque(msgs, maxlen=200)
    except: pass

    # Эпизодическая
    try:
        with open(EPISODIC_FILE, "r", encoding="utf-8") as f:
            episodic_memory = json.load(f)
    except: pass

    # Люди
    try:
        with open(PEOPLE_FILE, "r", encoding="utf-8") as f:
            people_memory = json.load(f)
    except: pass

    # Глобальная
    default_global = {
        "owner_name":       "",
        "active_tasks":     [],
        "important_facts":  [],
        "diary":            [],
        "projects":         {},
        "preferences":      {},
    }
    try:
        with open(GLOBAL_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            default_global.update(loaded)
    except: pass
    global_memory.update(default_global)

    # Саммари
    try:
        with open(SUMMARIES_FILE, "r", encoding="utf-8") as f:
            dialog_summaries = json.load(f)
    except: pass

    log.info(f"🧠 Память загружена: {len(chat_memory)} чатов, {len(people_memory)} людей")


# ═══════════════════════════════════════════════
# РАБОЧАЯ ПАМЯТЬ
# ═══════════════════════════════════════════════

def add_to_chat_memory(chat_id: int, role: str, content: str):
    chat_memory[chat_id].append({"role": role, "content": content})
    save_chat_memory()
    from bot.config import USE_DB
    if USE_DB:
        try:
            asyncio.create_task(_db_memory_add(chat_id, role, content))
        except RuntimeError:
            pass


async def _db_memory_add(chat_id: int, role: str, content: str):
    try:
        from database import memory_add
        await memory_add(chat_id, role, content)
    except: pass


def save_chat_memory():
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): list(v) for k, v in chat_memory.items()}, f, ensure_ascii=False)
    except: pass


def get_chat_messages(chat_id: int, depth: int = 8) -> list:
    return list(chat_memory[chat_id])[-depth:]


def clear_chat_memory(chat_id: int):
    chat_memory[chat_id].clear()
    save_chat_memory()


# ═══════════════════════════════════════════════
# ИСТОРИЯ ГРУПП
# ═══════════════════════════════════════════════

def add_to_history(chat_id: int, name: str, text: str):
    time_str = datetime.now().strftime("%H:%M")
    group_history[chat_id].append({"name": name, "text": text[:300], "time": time_str})
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): list(v) for k, v in group_history.items()}, f, ensure_ascii=False)
    except: pass


def get_chat_context(chat_id: int, depth: int = 20) -> str:
    msgs = list(group_history[chat_id])[-depth:]
    return "\n".join([f"[{m['time']}] {m['name']}: {m['text']}" for m in msgs])


# ═══════════════════════════════════════════════
# ЭПИЗОДИЧЕСКАЯ ПАМЯТЬ
# ═══════════════════════════════════════════════

def add_episode(chat_id: int, event_type: str, content: str, meta: dict = None):
    key = str(chat_id)
    if key not in episodic_memory:
        episodic_memory[key] = []
    episode = {
        "type":    event_type,
        "content": content[:500],
        "date":    datetime.now().strftime("%d.%m.%Y %H:%M"),
        "meta":    meta or {}
    }
    episodic_memory[key].append(episode)
    episodic_memory[key] = episodic_memory[key][-50:]
    _save_episodic()

    from bot.config import USE_DB
    if USE_DB:
        try:
            asyncio.create_task(_db_episode_add(chat_id, event_type, content, meta))
        except RuntimeError:
            pass


def _save_episodic():
    try:
        with open(EPISODIC_FILE, "w", encoding="utf-8") as f:
            json.dump(episodic_memory, f, ensure_ascii=False, indent=2)
    except: pass


async def _db_episode_add(chat_id: int, ep_type: str, content: str, meta: dict):
    try:
        from database import episode_add
        await episode_add(chat_id, ep_type, content, meta)
    except: pass


def get_episodes_str(chat_id: int, limit: int = 5) -> str:
    episodes = episodic_memory.get(str(chat_id), [])[-limit:]
    if not episodes:
        return ""
    lines = ["📖 История разговоров:"]
    for ep in episodes:
        lines.append(f"  [{ep['date']}] {ep['type']}: {ep['content'][:100]}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════
# ПАМЯТЬ О ЛЮДЯХ
# ═══════════════════════════════════════════════

def update_people_memory(user_id: int, name: str, text: str, mood: str = None):
    key = str(user_id)
    if key not in people_memory:
        people_memory[key] = {
            "name": name, "messages_count": 0, "last_seen": "",
            "mood_history": [], "key_facts": [], "profession": "",
            "location": "", "interests": [], "last_mood": "",
        }
    p = people_memory[key]
    p["name"]            = name
    p["messages_count"]  = p.get("messages_count", 0) + 1
    p["last_seen"]       = datetime.now().strftime("%d.%m %H:%M")
    if mood:
        p["last_mood"] = mood
        mh = p.get("mood_history", [])
        mh.append(mood)
        p["mood_history"] = mh[-10:]

    _save_people()

    from bot.config import USE_DB
    if USE_DB:
        try:
            asyncio.create_task(_db_people_set(user_id, dict(p)))
        except RuntimeError:
            pass


def _save_people():
    try:
        with open(PEOPLE_FILE, "w", encoding="utf-8") as f:
            json.dump(people_memory, f, ensure_ascii=False, indent=2)
    except: pass


async def _db_people_set(user_id: int, data: dict):
    try:
        from database import people_set
        await people_set(user_id, data)
    except: pass


def get_person_context(user_id: int) -> str:
    p = people_memory.get(str(user_id), {})
    if not p:
        return ""
    lines = [f"О собеседнике ({p.get('name','?')}):"]
    if p.get("profession"):  lines.append(f"  Профессия: {p['profession']}")
    if p.get("location"):    lines.append(f"  Город: {p['location']}")
    if p.get("interests"):   lines.append(f"  Интересы: {', '.join(p['interests'][:3])}")
    if p.get("last_mood"):   lines.append(f"  Настроение: {p['last_mood']}")
    if p.get("key_facts"):   lines.append(f"  Факты: {'; '.join(p['key_facts'][:3])}")
    return "\n".join(lines) if len(lines) > 1 else ""


# ═══════════════════════════════════════════════
# ГЛОБАЛЬНАЯ ПАМЯТЬ
# ═══════════════════════════════════════════════

def add_to_global_memory(category: str, content: str):
    cats = {
        "fact":  ("important_facts", 50),
        "task":  ("active_tasks",    20),
        "diary": ("diary",           30),
    }
    key, limit = cats.get(category, ("important_facts", 50))
    lst = global_memory.get(key, [])
    lst.append({"content": content, "date": datetime.now().strftime("%d.%m.%Y")})
    global_memory[key] = lst[-limit:]
    _save_global()


def _save_global():
    try:
        with open(GLOBAL_FILE, "w", encoding="utf-8") as f:
            json.dump(global_memory, f, ensure_ascii=False, indent=2)
    except: pass


def get_global_context() -> str:
    lines = []
    if global_memory.get("owner_name"):
        lines.append(f"Хозяина зовут: {global_memory['owner_name']}")
    tasks = [t for t in global_memory.get("active_tasks", []) if not t.get("done")]
    if tasks:
        lines.append(f"Активные задачи: {'; '.join([t['content'] for t in tasks[:3]])}")
    facts = global_memory.get("important_facts", [])
    if facts:
        lines.append(f"Важные факты: {'; '.join([f['content'] for f in facts[-3:]])}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════
# АВТО-САММАРИ
# ═══════════════════════════════════════════════

async def auto_summarize(chat_id: int) -> Optional[str]:
    """Сжимает длинный диалог в краткое саммари"""
    msgs = list(chat_memory[chat_id])
    if len(msgs) < 20:
        return None
    try:
        from bot.ai.providers import smart_request
        text = "\n".join([f"{m['role']}: {m['content'][:200]}" for m in msgs[-20:]])
        summary = await smart_request(
            [{"role": "user", "content": f"Диалог:\n{text}"}],
            "Сделай краткое саммари диалога в 2-3 предложения. Только суть."
        )
        # Сохраняем саммари
        dialog_summaries[str(chat_id)] = {
            "summary": summary,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "msg_count": len(msgs)
        }
        try:
            with open(SUMMARIES_FILE, "w", encoding="utf-8") as f:
                json.dump(dialog_summaries, f, ensure_ascii=False, indent=2)
        except: pass

        # Очищаем старые сообщения, оставляем только последние 8
        recent = list(chat_memory[chat_id])[-8:]
        chat_memory[chat_id].clear()
        for m in recent:
            chat_memory[chat_id].append(m)
        save_chat_memory()
        add_episode(chat_id, "summary", summary)
        return summary
    except Exception as e:
        log.debug(f"Auto summarize error: {e}")
        return None


def clean_text(text: str) -> str:
    """Очищает текст от markdown артефактов"""
    import re
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'#+\s', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    return text.strip()
