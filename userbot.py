"""
AI Userbot v4.0 — ФИНАЛЬНАЯ ВЕРСИЯ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Отвечает на + везде (личка, группы, каналы)
✅ Автоответ когда офлайн
✅ Авто перевод иностранных сообщений
✅ Голосовые сообщения — распознаёт речь и отвечает
✅ Анализ фото через Gemini Vision
✅ Память чата и история группы
✅ Ответ на упоминание имени в группе
✅ Обход антиспама
"""

import os
import asyncio
import logging
import json
import aiohttp
import random
import base64
import io
from collections import defaultdict, deque
from datetime import datetime
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.enums import ChatType

# ══════════════════════════ .ENV ════════════════════════════════════
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

# ══════════════════════════ ENV ══════════════════════════════════════
API_ID         = int(os.getenv("API_ID", "0"))
API_HASH       = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "")
COHERE_API_KEY   = os.getenv("COHERE_API_KEY", "")
CLAUDE_API_KEY   = os.getenv("CLAUDE_API_KEY", "")
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
MISTRAL_API_KEY  = os.getenv("MISTRAL_API_KEY", "")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")
HF_API_KEY       = os.getenv("HF_API_KEY", "")

CONFIG_FILE  = "userbot_config.json"
MEMORY_FILE  = "userbot_memory.json"
HISTORY_FILE = "chat_history.json"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.CRITICAL)
logging.getLogger("pyrogram.client").setLevel(logging.CRITICAL)
logging.getLogger("pyrogram.connection").setLevel(logging.CRITICAL)
logging.getLogger("pyrogram.dispatcher").setLevel(logging.CRITICAL)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

# Подавляем Task exception was never retrieved
import warnings
warnings.filterwarnings("ignore")

import sys
original_excepthook = sys.excepthook
def custom_excepthook(type, value, tb):
    if "Peer id invalid" in str(value) or "ID not found" in str(value):
        return
    original_excepthook(type, value, tb)
sys.excepthook = custom_excepthook
log = logging.getLogger("Userbot")

# ══════════════════════════ КОНФИГ ═══════════════════════════════════
def load_config() -> dict:
    default = {
        "active_ai":        "groq",
        "trigger":          "+",
        "memory_on":        True,
        "memory_depth":     8,
        "history_depth":    20,
        "autoreply_on":     False,
        "autoreply_text":   "сейчас нет, напишу позже",
        "mention_reply":    True,
        "translate_on":     True,    # авто перевод иностранных
        "voice_reply":      True,    # отвечать на голосовые
        "photo_analysis":   True,    # анализ фото
        "antispam_delay":   6,
        "spy_mode":         False,
        "auto_status":      False,
        "link_summary":     True,
        "mention_notify":   True,
        "copy_target":      "givi_iu",
        "pm_autoreply":     False,
        "contacts_file":    "contacts.json",
        "mood_analysis":    True,
        "people_memory":    True,
        "auto_summary":     True,
        "schedule_channel": "",
        "schedule_posts":   [],
        "persona_name":     "",      # тайный режим — имя персоны
        "persona_desc":     "",      # описание персоны
        "persona_on":       False,   # тайный режим включён
        "tts_reply":        False,   # отвечать голосовыми через TTS
        "voice_answer":     False,   # авто ответ на звонки голосовым
        "face_analysis":    True,    # анализ лиц на фото
        "autodestruct":     0,       # авто удаление через N секунд (0=выкл)
        "stats":            {"total": 0, "voice": 0, "photo": 0, "translate": 0},
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                default.update(json.load(f))
            except:
                pass
    return default

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

config = load_config()

# ══════════════════════════ ПАМЯТЬ ═══════════════════════════════════
chat_memory: dict = defaultdict(lambda: deque(maxlen=16))
group_history: dict = defaultdict(lambda: deque(maxlen=100))
autoreply_sent: dict = {}

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                for cid, msgs in json.load(f).items():
                    chat_memory[int(cid)] = deque(msgs, maxlen=16)
        except: pass

def save_memory():
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): list(v) for k, v in chat_memory.items()}, f, ensure_ascii=False)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                for cid, msgs in json.load(f).items():
                    group_history[int(cid)] = deque(msgs, maxlen=100)
        except: pass

def save_history():
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): list(v) for k, v in group_history.items()}, f, ensure_ascii=False)

load_memory()
load_history()

# ══════════════════════════ ПАМЯТЬ О ЛЮДЯХ ═══════════════════════════
PEOPLE_FILE = "people_memory.json"

def load_people() -> dict:
    if os.path.exists(PEOPLE_FILE):
        try:
            with open(PEOPLE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_people(data: dict):
    with open(PEOPLE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

people_memory = load_people()

def update_people_memory(user_id: int, name: str, text: str, mood: str = None):
    """Обновляем что знаем о человеке"""
    key = str(user_id)
    if key not in people_memory:
        people_memory[key] = {
            "name": name,
            "messages_count": 0,
            "topics": [],
            "last_mood": None,
            "last_seen": None,
            "notes": []
        }
    p = people_memory[key]
    p["name"] = name
    p["messages_count"] = p.get("messages_count", 0) + 1
    p["last_seen"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    if mood:
        p["last_mood"] = mood
    # Сохраняем последние 5 тем
    if text and len(text) > 10:
        p["notes"] = (p.get("notes", []) + [text[:100]])[-5:]
    save_people(people_memory)

def get_person_context(user_id: int) -> str:
    """Получаем что знаем о человеке для промпта"""
    key = str(user_id)
    if key not in people_memory:
        return ""
    p = people_memory[key]
    parts = [f"Собеседник: {p.get('name', '?')}"]
    if p.get("messages_count"):
        parts.append(f"Сообщений от него: {p['messages_count']}")
    if p.get("last_mood"):
        parts.append(f"Последнее настроение: {p['last_mood']}")
    if p.get("last_seen"):
        parts.append(f"Последний раз: {p['last_seen']}")
    if p.get("notes"):
        parts.append(f"О чём писал раньше: {'; '.join(p['notes'][-3:])}")
    return "\n".join(parts)

# ══════════════════════════ АНАЛИЗ НАСТРОЕНИЯ ════════════════════════
async def analyze_mood(text: str) -> str:
    """Определяет настроение по тексту"""
    if len(text) < 5:
        return "нейтральное"
    # Простой анализ по ключевым словам
    text_lower = text.lower()
    positive = ["спасибо", "отлично", "хорошо", "супер", "класс", "ок", "👍", "😊", "❤", "🔥", "круто", "молодец"]
    negative = ["плохо", "ужас", "бесит", "злой", "angry", "грустно", "😢", "😠", "😡", "блин", "черт", "надоел"]
    urgent = ["срочно", "помоги", "быстро", "важно", "asap", "помощь"]

    pos = sum(1 for w in positive if w in text_lower)
    neg = sum(1 for w in negative if w in text_lower)
    urg = sum(1 for w in urgent if w in text_lower)

    if urg > 0: return "срочное/тревожное"
    if neg > pos: return "негативное"
    if pos > neg: return "позитивное"
    return "нейтральное"

# ══════════════════════════ АВТО САММАРИ ═════════════════════════════
SUMMARY_FILE = "dialog_summaries.json"

def load_summaries() -> dict:
    if os.path.exists(SUMMARY_FILE):
        try:
            with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_summaries(data: dict):
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

dialog_summaries = load_summaries()

async def auto_summarize(chat_id: int) -> str | None:
    """Если диалог длинный — делает саммари и сжимает"""
    msgs = list(chat_memory[chat_id])
    if len(msgs) < 20:
        return None
    active = config.get("active_ai", "groq")
    ai_fn = AI_MAP.get(active)
    if not ai_fn:
        return None
    try:
        dialog_text = "\n".join([f"{'Я' if m['role']=='assistant' else 'Собеседник'}: {m['content']}" for m in msgs[-20:]])
        summary = await ai_fn(
            [{"role": "user", "content": f"Сделай краткое изложение этого диалога (3-4 предложения):\n{dialog_text}"}],
            "Ты мастер кратких пересказов. Только суть."
        )
        # Сохраняем саммари
        dialog_summaries[str(chat_id)] = {
            "summary": summary,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "messages_count": len(msgs)
        }
        save_summaries(dialog_summaries)
        # Сжимаем память — оставляем только саммари + последние 5 сообщений
        last_5 = list(chat_memory[chat_id])[-5:]
        chat_memory[chat_id].clear()
        chat_memory[chat_id].append({"role": "system", "content": f"Краткое изложение предыдущего разговора: {summary}"})
        for m in last_5:
            chat_memory[chat_id].append(m)
        save_memory()
        log.info(f"Авто саммари для чата {chat_id}")
        return summary
    except Exception as e:
        log.error(f"Summary error: {e}")
        return None

# ══════════════════════════ РАСПИСАНИЕ ПОСТОВ ════════════════════════
schedule_tasks: dict = {}  # chat_id → task

async def schedule_loop(client, channel: str, posts: list):
    """Фоновая задача — постит по расписанию"""
    while True:
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_day = now.strftime("%A").lower()

        for post in posts:
            if post.get("time") == current_time:
                day = post.get("day", "daily")
                if day == "daily" or day == current_day:
                    try:
                        text = post.get("text", "")
                        # Если текст содержит {ai} — генерируем контент
                        if "{ai}" in text:
                            topic = text.replace("{ai}", "").strip() or "интересный пост для канала"
                            active = config.get("active_ai", "groq")
                            ai_fn = AI_MAP.get(active)
                            if ai_fn:
                                text = await ai_fn(
                                    [{"role": "user", "content": f"Напиши интересный пост для Telegram канала на тему: {topic}"}],
                                    "Пиши живо, интересно, кратко. Без хэштегов."
                                )
                        await client.send_message(channel, text)
                        log.info(f"Пост отправлен в {channel}: {text[:50]}")
                    except Exception as e:
                        log.error(f"Schedule post error: {e}")

        await asyncio.sleep(60)  # проверяем каждую минуту

def add_to_history(chat_id: int, name: str, text: str):
    group_history[chat_id].append({
        "name": name, "text": text[:300],
        "time": datetime.now().strftime("%H:%M")
    })
    save_history()

def get_chat_context(chat_id: int, depth: int = 20) -> str:
    history = list(group_history[chat_id])[-depth:]
    if not history:
        return ""
    return "\n".join([f"{m['name']} [{m['time']}]: {m['text']}" for m in history])

def clean_text(text: str) -> str:
    return text.replace("**", "").replace("__", "").replace("~~", "").strip()

# Чаты которые уже просканированы
scanned_chats: set = set()

# ══════════════════════════ КОНТАКТЫ ═════════════════════════════════
CONTACTS_FILE = "contacts.json"

def load_contacts() -> dict:
    if os.path.exists(CONTACTS_FILE):
        try:
            with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_contacts(contacts: dict):
    with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(contacts, f, ensure_ascii=False, indent=2)

contacts_db = load_contacts()

async def scan_chat_history(client, chat_id: int, limit: int = 40):
    """Загружает историю чата если ещё не сканировали"""
    if chat_id in scanned_chats:
        return
    scanned_chats.add(chat_id)
    try:
        count = 0
        async for msg in client.get_chat_history(chat_id, limit=limit):
            if msg.text and msg.from_user:
                name = msg.from_user.first_name or "Аноним"
                time_str = msg.date.strftime("%H:%M") if msg.date else ""
                group_history[chat_id].appendleft({
                    "name": name,
                    "text": msg.text[:300],
                    "time": time_str
                })
                count += 1
        if count > 0:
            save_history()
            log.info(f"Просканировано {count} сообщений из чата {chat_id}")
    except Exception as e:
        log.error(f"Scan error: {e}")

# ══════════════════════════ ПРОМПТЫ ══════════════════════════════════
BASE_PROMPT = """Ты — умный, точный и серьёзный ассистент.

Правила:
- Отвечаешь только правдиво и точно — никакой выдумки
- Если не знаешь — честно говоришь "не знаю" или "не уверен"
- Отвечаешь кратко и по делу — без воды и лишних слов
- Только русский язык
- Никаких шуток, сарказма, характера — только факты
- Если вопрос сложный — структурируй ответ чётко
- Никогда не говоришь что ты ИИ если не спрашивают"""

def build_prompt(chat_id: int, is_group: bool, extra: dict = None) -> str:
    extra = extra or {}
    chat_name = extra.get("chat_name", "")
    chat_type = extra.get("chat_type", "")
    sender_name = extra.get("sender_name", "")
    members_count = extra.get("members_count", "")
    chat_desc = extra.get("chat_desc", "")
    my_name = extra.get("my_name", "Я")

    base = """Ты — умный, точный и серьёзный ассистент.
Отвечаешь только правдиво и точно. Если не знаешь — говоришь честно.
Отвечаешь кратко и по делу. Только русский язык.
Никогда не говоришь что ты ИИ если не спрашивают."""

    context_parts = []

    if not is_group and sender_name:
        # Личка — чётко указываем кто в чате
        context_parts.append(f"Это личная переписка между {my_name} и {sender_name}.")
        context_parts.append(f"В чате только двое: {my_name} (хозяин) и {sender_name} (собеседник).")
    else:
        if chat_name:
            context_parts.append(f"Чат: {chat_name}")
        if chat_type:
            context_parts.append(f"Тип: {chat_type}")
        if members_count:
            context_parts.append(f"Участников: {members_count}")
        if chat_desc:
            context_parts.append(f"Описание чата: {chat_desc}")
        if sender_name:
            context_parts.append(f"Собеседник: {sender_name}")

    if is_group:
        history = get_chat_context(chat_id, config.get("history_depth", 40))
        if history:
            context_parts.append(f"История чата:\n{history}")

    if context_parts:
        return base + "\n\nКонтекст:\n" + "\n".join(context_parts)
    return base

# ══════════════════════════ AI КЛИЕНТЫ ═══════════════════════════════
async def ask_groq(messages: list, system: str) -> str:
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    body = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system}] + messages, "max_tokens": 500}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.groq.com/openai/v1/chat/completions", json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"Groq {r.status}: {data.get('error', {}).get('message', data)}")
            return data["choices"][0]["message"]["content"]

async def ask_cohere(messages: list, system: str) -> str:
    headers = {"Authorization": f"Bearer {COHERE_API_KEY}", "Content-Type": "application/json"}
    chat_history = [{"role": "USER" if m["role"] == "user" else "CHATBOT", "message": m["content"]} for m in messages[:-1]]
    body = {"model": "command-r-plus-08-2024", "message": messages[-1]["content"] if messages else "привет", "preamble": system, "chat_history": chat_history, "max_tokens": 500}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.cohere.com/v1/chat", json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"Cohere {r.status}: {data.get('message', data)}")
            return data["text"]

async def ask_claude(messages: list, system: str) -> str:
    headers = {"x-api-key": CLAUDE_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    body = {"model": "claude-opus-4-5", "max_tokens": 500, "system": system, "messages": messages}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.anthropic.com/v1/messages", json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"Claude {r.status}: {data.get('error', {}).get('message', data)}")
            return data["content"][0]["text"]

async def ask_gemini(messages: list, system: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    contents = [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]} for m in messages]
    body = {"system_instruction": {"parts": [{"text": system}]}, "contents": contents}
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=body, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"Gemini {r.status}: {data}")
            return data["candidates"][0]["content"]["parts"][0]["text"]

async def ask_deepseek(messages: list, system: str) -> str:
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    body = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system}] + messages, "max_tokens": 500}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.deepseek.com/v1/chat/completions", json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"DeepSeek {r.status}: {data}")
            return data["choices"][0]["message"]["content"]

async def ask_gpt(messages: list, system: str) -> str:
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {"model": "gpt-4o-mini", "messages": [{"role": "system", "content": system}] + messages, "max_tokens": 500}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.openai.com/v1/chat/completions", json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"GPT {r.status}: {data.get('error', {}).get('message', data)}")
            return data["choices"][0]["message"]["content"]

async def ask_mistral(messages: list, system: str) -> str:
    if not MISTRAL_API_KEY:
        raise Exception("MISTRAL_API_KEY не задан")
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": "mistral-small-latest",
        "messages": [{"role": "system", "content": system}] + messages,
        "max_tokens": 500
    }
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.mistral.ai/v1/chat/completions", json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"Mistral {r.status}: {data.get('message', data)}")
            return data["choices"][0]["message"]["content"]

async def ask_together(messages: list, system: str) -> str:
    if not TOGETHER_API_KEY:
        raise Exception("TOGETHER_API_KEY не задан")
    headers = {"Authorization": f"Bearer {TOGETHER_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
        "messages": [{"role": "system", "content": system}] + messages,
        "max_tokens": 500
    }
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.together.xyz/v1/chat/completions", json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"Together {r.status}: {data.get('error', {}).get('message', data)}")
            return data["choices"][0]["message"]["content"]

async def ask_huggingface(messages: list, system: str) -> str:
    if not HF_API_KEY:
        raise Exception("HF_API_KEY не задан")
    headers = {"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"}
    # Объединяем все сообщения в один текст
    prompt = f"{system}\n\n"
    for m in messages:
        role = "Пользователь" if m["role"] == "user" else "Ассистент"
        prompt += f"{role}: {m['content']}\n"
    prompt += "Ассистент:"
    body = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 500, "return_full_text": False}
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(
            "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3",
            json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=60)
        ) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"HuggingFace {r.status}: {data}")
            if isinstance(data, list):
                return data[0].get("generated_text", "").strip()
            raise Exception(f"HF unexpected response: {data}")

AI_MAP = {
    "groq": ask_groq,
    "cohere": ask_cohere,
    "claude": ask_claude,
    "gemini": ask_gemini,
    "deepseek": ask_deepseek,
    "gpt": ask_gpt,
    "mistral": ask_mistral,
    "together": ask_together,
    "huggingface": ask_huggingface,
    "hf": ask_huggingface,
}

async def ensemble_request(question: str, messages: list, system: str) -> str:
    """3 ИИ отвечают одновременно → Groq выбирает лучший ответ"""

    # Три бойца
    FIGHTERS = [
        ("groq",     ask_groq),
        ("cohere",   ask_cohere),
        ("mistral",  ask_mistral),
        ("together", ask_together),
    ]

    # Берём только те у которых есть ключ
    available = []
    for name, fn in FIGHTERS:
        key = os.getenv(f"{name.upper()}_API_KEY", "")
        if key:
            available.append((name, fn))

    # Если меньше 2 доступных — просто отвечает один
    if len(available) < 2:
        if available:
            return await available[0][1](messages, system)
        return await ask_groq(messages, system)

    # Берём 3 бойца (или сколько есть)
    fighters = available[:3]

    # Все отвечают параллельно
    tasks = [fn(messages, system) for _, fn in fighters]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Собираем успешные ответы
    answers = []
    for i, res in enumerate(results):
        if not isinstance(res, Exception) and res:
            answers.append({
                "ai": fighters[i][0],
                "text": clean_text(res)
            })

    if not answers:
        raise Exception("Все ИИ не ответили")

    if len(answers) == 1:
        return answers[0]["text"]

    # Groq судит — выбирает лучший ответ
    judge_prompt = """Ты судья. Тебе дали несколько ответов от разных ИИ на один вопрос.
Выбери ЛУЧШИЙ ответ — самый точный, полный и полезный.
Верни ТОЛЬКО текст лучшего ответа без изменений. Не добавляй ничего от себя."""

    answers_text = "\n\n".join([
        f"[{a['ai'].upper()}]: {a['text']}" for a in answers
    ])

    judge_messages = [{"role": "user", "content": f"Вопрос: {question}\n\nОтветы:\n{answers_text}"}]

    try:
        best = await ask_groq(judge_messages, judge_prompt)
        return clean_text(best)
    except:
        # Если судья упал — возвращаем первый ответ
        return answers[0]["text"]


async def ai_request(question: str, chat_id: int, is_group: bool = False, client=None, message=None) -> str:
    active = config.get("active_ai", "groq")
    ai_fn = AI_MAP.get(active)
    if not ai_fn:
        raise Exception(f"Неизвестный ИИ: {active}")

    # Собираем контекст о чате
    extra = {}
    if client and message:
        try:
            chat = message.chat
            extra["chat_name"] = chat.title or chat.first_name or ""
            extra["chat_type"] = str(chat.type.value) if chat.type else ""
            if hasattr(chat, "members_count") and chat.members_count:
                extra["members_count"] = str(chat.members_count)
            if hasattr(chat, "description") and chat.description:
                extra["chat_desc"] = chat.description[:200]
            if message.from_user:
                name = message.from_user.first_name or ""
                username = f"@{message.from_user.username}" if message.from_user.username else ""
                extra["sender_name"] = f"{name} {username}".strip()
        except:
            pass

    system = build_prompt(chat_id, is_group, extra)

    # Для личной переписки — добавляем имя собеседника в промпт
    if not is_group and client and message:
        try:
            chat = message.chat
            partner_name = chat.first_name or chat.username or str(chat.id)
            partner_username = f"@{chat.username}" if chat.username else ""
            me = await client.get_me()
            my_name = me.first_name or "Я"
            extra["chat_name"] = f"Личный чат с {partner_name}"
            extra["sender_name"] = f"{partner_name} {partner_username}".strip()
            extra["my_name"] = my_name
            system = build_prompt(chat_id, is_group, extra)
        except:
            pass

    if config.get("memory_on"):
        depth = config.get("memory_depth", 8)
        chat_memory[chat_id].append({"role": "user", "content": question})
        msgs = list(chat_memory[chat_id])[-depth:]
    else:
        msgs = [{"role": "user", "content": question}]

    # Ensemble mode — всегда включён
    answer = await ensemble_request(question, msgs, system)

    if config.get("memory_on"):
        chat_memory[chat_id].append({"role": "assistant", "content": answer})
        save_memory()

    config["stats"]["total"] = config["stats"].get("total", 0) + 1
    save_config(config)
    return answer

# ══════════════════════════ TTS — голосовые ответы ═══════════════════
async def text_to_speech(text: str) -> bytes | None:
    """Конвертирует текст в голосовое через бесплатный TTS"""
    try:
        import urllib.parse
        # Используем Google TTS (бесплатно)
        text_encoded = urllib.parse.quote(text[:200])
        url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={text_encoded}&tl=ru&client=tw-ob"
        async with aiohttp.ClientSession() as s:
            async with s.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                if r.status == 200:
                    data = await r.read()
                    if len(data) > 100:
                        return data
    except Exception as e:
        log.error(f"TTS error: {e}")
    return None

# ══════════════════════════ АНАЛИЗ ЛИЦА ══════════════════════════════
async def analyze_face(photo_bytes: bytes) -> str:
    """Анализ лица на фото через Gemini Vision"""
    if not GEMINI_API_KEY:
        # Используем HuggingFace если нет Gemini
        if HF_API_KEY:
            try:
                import base64
                img_b64 = base64.b64encode(photo_bytes).decode()
                headers = {"Authorization": f"Bearer {HF_API_KEY}"}
                async with aiohttp.ClientSession() as s:
                    async with s.post(
                        "https://router.huggingface.co/hf-inference/models/Salesforce/blip-image-captioning-large",
                        json={"inputs": img_b64},
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as r:
                        if r.status == 200:
                            data = await r.json()
                            if isinstance(data, list):
                                return data[0].get("generated_text", "не удалось определить")
            except Exception as e:
                log.error(f"HF face error: {e}")
        return "GEMINI_API_KEY не задан для анализа лиц"

    import base64
    img_b64 = base64.b64encode(photo_bytes).decode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    body = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                {"text": "Опиши людей на этом фото подробно: внешность, примерный возраст, эмоции, одежда. Если это известная личность — скажи кто это. Отвечай на русском."}
            ]
        }]
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=body, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status == 200:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            raise Exception(f"Gemini {r.status}")

# ══════════════════════════ ПЕРСОНА (тайный режим) ════════════════════
def get_persona_prompt() -> str:
    """Промпт для тайного режима"""
    name = config.get("persona_name", "")
    desc = config.get("persona_desc", "")
    if not name:
        return ""
    return f"""Ты отвечаешь от имени человека по имени {name}.
{desc}
Отвечай от первого лица как {name}. Никогда не говори что ты ИИ.
Веди себя естественно как живой человек."""
async def transcribe_voice(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Распознавание речи через Groq Whisper (бесплатно)"""
    if not GROQ_API_KEY:
        raise Exception("GROQ_API_KEY не задан для распознавания речи")
    data = aiohttp.FormData()
    data.add_field("file", audio_bytes, filename=filename, content_type="audio/ogg")
    data.add_field("model", "whisper-large-v3")
    data.add_field("language", "ru")
    data.add_field("response_format", "text")
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.groq.com/openai/v1/audio/transcriptions", data=data, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as r:
            if r.status != 200:
                err = await r.text()
                raise Exception(f"Whisper {r.status}: {err[:100]}")
            return await r.text()

# ══════════════════════════ АНАЛИЗ ФОТО — Gemini Vision ══════════════
async def analyze_photo(photo_bytes: bytes, question: str = "Что на этом фото? Опиши подробно на русском.") -> str:
    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY не задан")
    img_b64 = base64.b64encode(photo_bytes).decode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    body = {"contents": [{"parts": [{"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}, {"text": question}]}]}
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=body, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"Gemini Vision {r.status}: {data}")
            return data["candidates"][0]["content"]["parts"][0]["text"]

# ══════════════════════════ ОПРЕДЕЛЕНИЕ ЯЗЫКА ════════════════════════
async def detect_and_translate(text: str) -> str | None:
    """Определяет язык и переводит если не русский"""
    # Простая проверка — если есть кириллица то русский
    cyrillic = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
    if cyrillic > len(text) * 0.3:
        return None  # русский, не переводим
    if len(text) < 5:
        return None  # слишком короткое

    translate_prompt = "Переведи этот текст на русский язык. Отвечай ТОЛЬКО переводом без пояснений."
    try:
        answer = await ai_request(text, chat_id=0, is_group=False)
        # Используем отдельный запрос для перевода
        active = config.get("active_ai", "groq")
        ai_fn = AI_MAP.get(active)
        if ai_fn:
            result = await ai_fn([{"role": "user", "content": text}], translate_prompt)
            return result
    except:
        pass
    return None

# ══════════════════════════ АВТО СТАТУС ══════════════════════════════
AUTO_STATUS_SCHEDULE = [
    (6,  12, "☀️ Доброе утро! Онлайн"),
    (12, 17, "💼 Работаю"),
    (17, 21, "🌆 Вечером онлайн"),
    (21, 24, "🌙 Поздно, но читаю"),
    (0,  6,  "😴 Сплю, напишу утром"),
]

async def update_status(client: Client):
    """Меняет bio по времени суток"""
    hour = datetime.now().hour
    for start, end, text in AUTO_STATUS_SCHEDULE:
        if start <= hour < end:
            try:
                await client.update_profile(bio=text)
                log.info(f"Статус обновлён: {text}")
            except Exception as e:
                log.error(f"Ошибка смены статуса: {e}")
            break

async def auto_status_loop(client: Client):
    """Фоновая задача — меняет статус каждый час"""
    while True:
        if config.get("auto_status"):
            await update_status(client)
        await asyncio.sleep(3600)  # раз в час

# ══════════════════════════ АВТО САММАРИ ССЫЛОК ═══════════════════════
import re

URL_PATTERN = re.compile(r'https?://[^\s]+')

async def fetch_url_content(url: str) -> str:
    """Скачиваем содержимое страницы"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    return ""
                html = await r.text()
                # Убираем HTML теги
                clean = re.sub(r'<[^>]+>', ' ', html)
                clean = re.sub(r'\s+', ' ', clean).strip()
                return clean[:3000]  # первые 3000 символов
    except:
        return ""

async def summarize_url(url: str) -> str | None:
    """Делает саммари страницы по ссылке"""
    content = await fetch_url_content(url)
    if not content or len(content) < 100:
        return None
    active = config.get("active_ai", "groq")
    ai_fn = AI_MAP.get(active)
    if not ai_fn:
        return None
    try:
        summary = await ai_fn(
            [{"role": "user", "content": f"Сделай краткое изложение этого текста на русском (3-5 предложений):\n\n{content}"}],
            "Ты мастер кратких пересказов. Только суть, без воды."
        )
        return summary
    except:
        return None

# ══════════════════════════ PYROGRAM CLIENT ═══════════════════════════
app = Client(name="userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

# ══════════════════ ШПИОН — удалённые сообщения ═══════════════════════
@app.on_deleted_messages()
async def handle_deleted(client: Client, messages):
    global config
    config = load_config()
    """Сохраняем удалённые сообщения в избранное"""
    if not config.get("spy_mode"):
        return
    for message in messages:
        try:
            if not message.text and not message.caption:
                continue
            text = message.text or message.caption or ""
            if not text.strip():
                continue
            sender = "Неизвестно"
            if message.from_user:
                sender = f"{message.from_user.first_name or ''} (@{message.from_user.username or message.from_user.id})"
            chat_name = ""
            if message.chat:
                chat_name = message.chat.title or message.chat.first_name or str(message.chat.id)
            time_str = datetime.now().strftime("%d.%m %H:%M")
            spy_text = (
                f"🕵️ **Удалённое сообщение**\n"
                f"👤 {sender}\n"
                f"💬 {chat_name}\n"
                f"🕐 {time_str}\n\n"
                f"{text}"
            )
            await client.send_message("me", spy_text)
            log.info(f"Шпион: сохранено удалённое от {sender}")
        except Exception as e:
            log.error(f"Spy error: {e}")

# Счётчик сообщений для авто вступления в разговор
# chat_id → {"count": int, "last_reply": datetime}
chat_activity: dict = defaultdict(lambda: {"count": 0, "last_reply": None})

# ══════════════════ ВХОДЯЩИЕ ТЕКСТОВЫЕ ═══════════════════════════════
@app.on_message(filters.incoming & filters.group & filters.text)
async def listen_group(client: Client, message: Message):
    """Записываем сообщения группы + авто вступление в разговор"""
    if not message.text or message.text.startswith("/"):
        return

    # Перечитываем конфиг — бот мог изменить его
    global config
    config = load_config()

    # Автосканирование истории при первом входе в чат
    asyncio.create_task(scan_chat_history(client, message.chat.id, 40))

    log.info(f"📨 GROUP: {message.chat.title or message.chat.id} | {message.text[:40]}")

    name = message.from_user.first_name if message.from_user else "Аноним"
    add_to_history(message.chat.id, name, message.text)

    # Авто вступление в разговор
    if config.get("auto_join", False):
        chat_id = message.chat.id
        activity = chat_activity[chat_id]
        activity["count"] += 1
        now = datetime.now()
        last = activity.get("last_reply")
        min_interval = config.get("auto_join_interval", 60)  # минимум секунд между ответами
        min_messages = config.get("auto_join_messages", 3)   # минимум сообщений перед ответом

        # Отвечаем если: прошло достаточно времени И накопилось достаточно сообщений
        should_reply = (
            activity["count"] >= min_messages and
            (last is None or (now - last).total_seconds() >= min_interval)
        )

        if should_reply:
            # Сбрасываем счётчик
            activity["count"] = 0
            activity["last_reply"] = now

            await asyncio.sleep(config.get("antispam_delay", 6))
            try:
                context = get_chat_context(chat_id, 10)
                prompt = f"""Ты участник группового чата. Вступи в разговор естественно и коротко.
Отвечай на последнее сообщение или на тему беседы. По-русски, 1-2 предложения.
Не говори что ты ИИ. Веди себя как живой человек."""
                active = config.get("active_ai", "groq")
                ai_fn = AI_MAP.get(active)
                if ai_fn:
                    me = await client.get_me()
                    answer = await ai_fn(
                        [{"role": "user", "content": f"Вот последние сообщения чата:\n{context}\n\nВступи в разговор:"}],
                        prompt
                    )
                    clean = clean_text(answer)
                    add_to_history(chat_id, me.first_name or "Я", clean)
                    await client.send_message(
                        chat_id=chat_id,
                        text=clean,
                        reply_to_message_id=message.id
                    )
                    log.info(f"Авто вступление в {chat_id}: {clean[:40]}")
            except Exception as e:
                log.error(f"Auto join error: {e}")

    # Авто саммари ссылок
    if config.get("link_summary"):
        urls = URL_PATTERN.findall(message.text)
        if urls:
            url = urls[0]
            try:
                summary = await summarize_url(url)
                if summary:
                    await asyncio.sleep(config.get("antispam_delay", 6))
                    await message.reply(f"🔗 *Саммари ссылки:*\n\n{clean_text(summary)}")
            except Exception as e:
                log.error(f"Link summary error: {e}")

    # Авто перевод иностранных сообщений
    if config.get("translate_on") and len(message.text) > 10:
        cyrillic = sum(1 for c in message.text if '\u0400' <= c <= '\u04FF')
        latin = sum(1 for c in message.text if c.isalpha() and c.isascii())
        if latin > cyrillic and latin > 5:
            try:
                active = config.get("active_ai", "groq")
                ai_fn = AI_MAP.get(active)
                if ai_fn:
                    translation = await ai_fn(
                        [{"role": "user", "content": message.text}],
                        "Переведи на русский язык. Отвечай ТОЛЬКО переводом."
                    )
                    config["stats"]["translate"] = config["stats"].get("translate", 0) + 1
                    save_config(config)
                    await message.reply(f"🌐 {clean_text(translation)}")
            except Exception as e:
                log.error(f"Translate error: {e}")

    # Уведомление когда упоминают имя
    if config.get("mention_notify", True):
        me = await client.get_me()
        my_names = [me.first_name or "", me.username or ""]
        if any(n.lower() in message.text.lower() for n in my_names if n):
            chat_name = message.chat.title or str(message.chat.id)
            sender = message.from_user.first_name if message.from_user else "Кто-то"
            notify_text = (
                f"🔔 **Тебя упомянули!**\n"
                f"👤 {sender}\n"
                f"💬 {chat_name}\n"
                f"🕐 {datetime.now().strftime('%H:%M')}\n\n"
                f"📝 {message.text[:200]}"
            )
            try:
                await client.send_message("me", notify_text)
                log.info(f"Уведомление: упомянули в {chat_name}")
            except Exception as e:
                log.error(f"Mention notify error: {e}")

    # Авто ответ на упоминание имени
    if config.get("mention_reply"):
        me = await client.get_me()
        my_names = [me.first_name or "", me.username or ""]
        if any(n.lower() in message.text.lower() for n in my_names if n):
            await asyncio.sleep(config.get("antispam_delay", 6))
            try:
                answer = await ai_request(message.text, message.chat.id, is_group=True)
                add_to_history(message.chat.id, me.first_name or "Я", answer)
                await client.send_message(
                    chat_id=message.chat.id,
                    text=clean_text(answer),
                    reply_to_message_id=message.id
                )
            except Exception as e:
                log.error(f"Mention reply error: {e}")

    # Авто пересылка сообщений
    if config.get("forward_from", {}).get(str(message.chat.id)):
        target = config["forward_from"][str(message.chat.id)]
        try:
            await client.forward_messages(target, message.chat.id, message.id)
        except:
            pass

    # Авто реакции на сообщения
    if config.get("auto_react", False) and len(message.text) >= 5:
        if random.random() <= 0.3:
            try:
                emoji = random.choice(REACTIONS_POOL)
                await message.react(emoji)
            except:
                pass

@app.on_message(filters.incoming & filters.private & filters.text)
async def handle_incoming_pm(client: Client, message: Message):
    """Автоответ в личке — на языке собеседника"""
    global config
    config = load_config()

    if message.from_user and message.from_user.is_bot:
        return

    # Всегда записываем входящие в память чата — чтобы бот видел контекст
    chat_id = message.chat.id
    sender_name = message.from_user.first_name if message.from_user else "Собеседник"
    chat_memory[chat_id].append({"role": "user", "content": f"{sender_name}: {message.text}"})
    save_memory()

    log.info(f"Входящее ЛС от {message.from_user.id if message.from_user else '?'}: {message.text[:40]} | autoreply={config.get('autoreply_on')} pm_autoreply={config.get('pm_autoreply')}")

    # Авто ответ на ВСЕ лички без +
    should_reply = config.get("autoreply_on") or config.get("pm_autoreply")
    if not should_reply:
        return

    try:
        # Анализ настроения
        mood = await analyze_mood(message.text)

        # Память о человеке
        if config.get("people_memory") and message.from_user:
            name = message.from_user.first_name or "Собеседник"
            update_people_memory(message.from_user.id, name, message.text, mood)

        chat_id = message.chat.id

        # Авто саммари если диалог длинный
        if config.get("auto_summary") and len(list(chat_memory[chat_id])) >= 20:
            asyncio.create_task(auto_summarize(chat_id))

        # Контекст о человеке
        person_ctx = get_person_context(message.from_user.id) if message.from_user else ""
        mood_hint = {
            "позитивное": "Собеседник в хорошем настроении.",
            "негативное": "Собеседник расстроен — отвечай мягко.",
            "срочное/тревожное": "Срочный запрос — отвечай быстро и по делу.",
        }.get(mood, "")

        prompt = f"""Ты отвечаешь на сообщение в личке вместо хозяина.
Отвечай на том же языке что и собеседник.
Отвечай естественно и коротко. Не говори что ты ИИ.
{mood_hint}
{person_ctx}"""

        if config.get("memory_on"):
            msgs = list(chat_memory[chat_id])[-config.get("memory_depth", 8):]
        else:
            msgs = [{"role": "user", "content": f"{sender_name}: {message.text}"}]

        # Персона — тайный режим
        if config.get("persona_on") and config.get("persona_name"):
            persona_prompt = get_persona_prompt()
            if persona_prompt:
                prompt = persona_prompt

        answer = await ensemble_request(message.text, msgs, prompt)
        clean = clean_text(answer)

        if config.get("memory_on"):
            chat_memory[chat_id].append({"role": "assistant", "content": clean})
            save_memory()

        # TTS — отвечаем голосовым если включён
        if config.get("tts_reply"):
            audio = await text_to_speech(clean)
            if audio:
                import io
                await client.send_voice(chat_id=message.chat.id, voice=io.BytesIO(audio))
                return

        await message.reply(clean)
        log.info(f"Автоответ [{mood}] → {chat_id}: {clean[:40]}")
    except Exception as e:
        log.error(f"Autoreply error: {e}")
        if config.get("autoreply_on"):
            await message.reply(config.get("autoreply_text", "сейчас занят, напишу позже"))

# ══════════════════ ВХОДЯЩИЕ СТИКЕРЫ ════════════════════════════════
@app.on_message((filters.incoming & filters.private & filters.sticker) |
                (filters.incoming & filters.group & filters.sticker))
async def handle_sticker(client: Client, message: Message):
    global config
    config = load_config()
    """Авто ответ на стикеры"""
    if not config.get("sticker_reply", True):
        return
    try:
        emoji = message.sticker.emoji or "🤔"
        name = message.from_user.first_name if message.from_user else "кто-то"
        is_group = message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)
        if is_group:
            await asyncio.sleep(config.get("antispam_delay", 6))
        answer = await ai_request(
            f"{name} прислал стикер {emoji}. Ответь коротко и остро.",
            message.chat.id, is_group
        )
        await client.send_message(
            chat_id=message.chat.id,
            text=clean_text(answer),
            reply_to_message_id=message.id
        )
    except Exception as e:
        log.error(f"Sticker reply error: {e}")

# ══════════════════ ВХОДЯЩИЕ ЗВОНКИ ══════════════════════════════════
@app.on_message(filters.incoming & filters.private & filters.service)
async def handle_call(client: Client, message: Message):
    global config
    config = load_config()
    """Авто ответ на пропущенные звонки — текстом или голосовым"""
    if not config.get("call_reply", True):
        return
    try:
        if not message.phone_call_discarded:
            return
        answer = await ai_request(
            "Мне пропустили звонок. Напиши короткое сообщение что увидел звонок и перезвоню позже.",
            message.chat.id, False
        )
        text = clean_text(answer)

        # Если включён TTS — отправляем голосовым
        if config.get("voice_answer") or config.get("tts_reply"):
            audio = await text_to_speech(text)
            if audio:
                import io
                await client.send_voice(
                    chat_id=message.chat.id,
                    voice=io.BytesIO(audio)
                )
                return

        await message.reply(text)
        log.info(f"Авто ответ на звонок от {message.chat.id}")
    except Exception as e:
        log.error(f"Call reply error: {e}")


@app.on_message((filters.incoming & filters.private & filters.voice) |
                (filters.incoming & filters.group & filters.voice))
async def handle_incoming_voice(client: Client, message: Message):
    global config
    config = load_config()
    """Распознаёт входящие голосовые и отвечает на них"""
    if not config.get("voice_reply"):
        return
    try:
        # Скачиваем голосовое
        audio = await client.download_media(message.voice, in_memory=True)
        audio_bytes = bytes(audio.getbuffer())

        # Распознаём речь
        text = await transcribe_voice(audio_bytes)
        text = text.strip()
        if not text:
            return

        log.info(f"Голосовое распознано: {text[:50]}")
        config["stats"]["voice"] = config["stats"].get("voice", 0) + 1
        save_config(config)

        is_group = message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)

        # Добавляем в историю группы
        if is_group:
            name = message.from_user.first_name if message.from_user else "Аноним"
            add_to_history(message.chat.id, name, f"[голосовое]: {text}")

        # Отвечаем от ИИ
        answer = await ai_request(f"[голосовое сообщение]: {text}", message.chat.id, is_group)

        if is_group:
            await asyncio.sleep(config.get("antispam_delay", 6))

        await client.send_message(
            chat_id=message.chat.id,
            text=f"🎤 _{text}_\n\n{clean_text(answer)}",
            reply_to_message_id=message.id
        )

    except Exception as e:
        log.error(f"Voice error: {e}")

# ══════════════════ ВХОДЯЩИЕ ФОТО ════════════════════════════════════
@app.on_message((filters.incoming & filters.private & filters.photo) |
                (filters.incoming & filters.group & filters.photo))
async def handle_incoming_photo(client: Client, message: Message):
    global config
    config = load_config()
    """Анализирует входящие фото + анализ лиц"""
    if not config.get("photo_analysis"):
        return
    try:
        photo = await client.download_media(message.photo, in_memory=True)
        photo_bytes = bytes(photo.getbuffer())
        question = message.caption or "Что на этом фото? Опиши подробно на русском."
        config["stats"]["photo"] = config["stats"].get("photo", 0) + 1
        save_config(config)

        # Анализ лиц если включён
        if config.get("face_analysis") and ("кто" in question.lower() or "лицо" in question.lower() or not message.caption):
            try:
                face_result = await analyze_face(photo_bytes)
                await message.reply(f"👤 {clean_text(face_result)}")
                return
            except:
                pass

        # Обычный анализ фото
        if GEMINI_API_KEY:
            answer = await analyze_photo(photo_bytes, question)
            await message.reply(f"🖼 {clean_text(answer)}")
    except Exception as e:
        log.error(f"Photo error: {e}")

# ══════════════════ ВХОДЯЩИЕ ДОКУМЕНТЫ (PDF/Word) ════════════════════
@app.on_message((filters.incoming & filters.private & filters.document) |
                (filters.incoming & filters.group & filters.document))
async def handle_document(client: Client, message: Message):
    global config
    config = load_config()
    if not config.get("doc_analysis", True):
        return
    if not message.document:
        return
    mime = message.document.mime_type or ""
    fname = message.document.file_name or ""
    # Только PDF и Word
    if not any(x in mime or fname.lower().endswith(x) for x in ["pdf", "word", "docx", "doc", "text"]):
        return
    try:
        file = await client.download_media(message.document, in_memory=True)
        file_bytes = bytes(file.getbuffer())
        text_content = ""

        if "pdf" in mime or fname.lower().endswith(".pdf"):
            # Читаем PDF
            try:
                import io
                # Простое извлечение текста из PDF без библиотек
                text_raw = file_bytes.decode("latin-1", errors="ignore")
                # Ищем текстовые блоки
                import re as _re
                chunks = _re.findall(r'\(([^)]{3,200})\)', text_raw)
                text_content = " ".join(chunks[:200])[:3000]
            except:
                text_content = ""
        elif any(x in mime or fname.lower().endswith(x) for x in ["word", "docx", "doc"]):
            # Простое извлечение из docx (zip)
            try:
                import zipfile, io as _io
                z = zipfile.ZipFile(_io.BytesIO(file_bytes))
                xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
                import re as _re
                text_content = " ".join(_re.findall(r'<w:t[^>]*>([^<]+)</w:t>', xml))[:3000]
            except:
                text_content = ""

        if not text_content or len(text_content) < 50:
            await message.reply("📄 Не удалось прочитать документ — возможно он защищён или повреждён")
            return

        active = config.get("active_ai", "groq")
        ai_fn = AI_MAP.get(active)
        if not ai_fn:
            return
        summary = await ai_fn(
            [{"role": "user", "content": f"Сделай краткое изложение документа на русском (5-7 предложений):\n\n{text_content}"}],
            "Ты мастер кратких пересказов. Только суть, без воды."
        )
        await message.reply(f"📄 **{fname}**\n\n{clean_text(summary)}")
        log.info(f"Документ проанализирован: {fname}")
    except Exception as e:
        log.error(f"Doc error: {e}")

# ══════════════════ АВТО РЕАКЦИИ ═════════════════════════════════════
REACTIONS_POOL = ["👍", "❤", "🔥", "🎉", "👏", "😁", "🤔", "💯"]

# ══════════════════════════ ИСХОДЯЩИЕ — триггер ══════════════════════════════
@app.on_message(filters.outgoing & filters.text)
async def handle_outgoing(client: Client, message: Message):
    global config
    config = load_config()
    """Когда ТЫ пишешь + — отвечает reply"""
    trigger = config.get("trigger", "+")
    text = message.text.strip()
    if not text.startswith(trigger):
        return
    question = text[len(trigger):].strip()
    # Если пустой + но есть reply — разрешаем (ответим на reply)
    if not question and not message.reply_to_message:
        return
    if not question:
        question = ""  # будет заполнен из reply ниже

    # ══ Распознавание команд через естественный язык ══
    import re as _re
    q_lower = question.lower().strip()
    SKIP = ("copy","google ","img ","image ","weather ","погода ","news","deletechat","deletemsg","info","send ","block ","unblock ","download","digest","forward ","creategroup ","saveinfo","search ","contact","contacts","forward","schedule","people","mood","summary","мем ","meme ")
    if not any(q_lower.startswith(s) for s in SKIP):
        # Мем
        if any(w in q_lower for w in ["найди мем", "покажи мем", "скинь мем", "хочу мем"]):
            for w in ["найди мем", "покажи мем", "скинь мем", "хочу мем"]:
                q_lower = q_lower.replace(w, "").strip()
            question = f"мем {q_lower}"
        # Удаление сообщений
        elif any(w in q_lower for w in ["удали сообщения","удалить сообщения","удали смс","удалить смс","удали последние","сотри мои смс","удали мои смс"]):
            nums = _re.findall(r'\d+', q_lower)
            question = f"deletemsg {nums[0] if nums else '10'}"
        # Удаление чата
        elif any(w in q_lower for w in ["удали чат","очисти чат","покинь чат","выйди из чата","удали переписку","очисти переписку","удалить чат","покинуть чат","выйти из группы","выйди из группы"]):
            question = "deletechat"
        # Заблокировать
        elif any(w in q_lower for w in ["заблокируй","заблокировать","добавь в чёрный список","забань","заблок"]):
            parts = question.split()
            for p in parts:
                if p.startswith("@") or (p.lstrip("@").isdigit() and len(p) > 4):
                    question = f"block {p}"; break
        # Разблокировать
        elif any(w in q_lower for w in ["разблокируй","разблокировать","убери из чёрного списка","разблок"]):
            parts = question.split()
            for p in parts:
                if p.startswith("@") or (p.lstrip("@").isdigit() and len(p) > 4):
                    question = f"unblock {p}"; break
        # Скачать медиа
        elif any(w in q_lower for w in ["скачай","скачать это","сохрани это","сохрани медиа","скачай файл","скачай фото","скачай видео","скачать файл"]):
            question = "download"
        # Дайджест
        elif any(w in q_lower for w in ["читай все чаты","дайджест","что пишут везде","покажи все чаты","что нового везде","обзор чатов","сводка чатов"]):
            question = "digest"
        # Мои данные
        elif any(w in q_lower for w in ["сохрани мои данные","запомни меня","мои данные","покажи мои данные","сохрани инфо обо мне","запомни мои данные"]):
            question = "saveinfo"
        # Создать группу
        elif any(w in q_lower for w in ["создай группу","создать группу","сделай группу","новая группа","создай чат"]):
            for w in ["создай группу","создать группу","сделай группу","новая группа","создай чат"]:
                if w in q_lower:
                    name = q_lower.replace(w,"").strip() or "Новая группа"
                    question = f"creategroup {name}"; break
        # Пересылать
        elif any(w in q_lower for w in ["пересылай","пересылать сообщения","форвард в","пересылай в"]):
            parts = question.split()
            target = next((p for p in parts if p.startswith("@")), None)
            if target:
                question = f"forward {target}"
        # Инфо о пользователе
        elif any(w in q_lower for w in ["кто это","кто такой","кто такая","инфо о","информация о","расскажи о","кто он","кто она","узнай кто","покажи инфо","данные о","расскажи про"]):
            question = "info"
        # Поиск
        elif any(w in q_lower for w in ["найди","загугли","поищи","погугли","поиск по","найти в интернете","нагугли"]):
            for w in ["найди","загугли","поищи","погугли","поиск по","найти в интернете","нагугли"]:
                q_lower = q_lower.replace(w,"").strip()
            question = f"google {q_lower}"
        # Картинка
        elif any(w in q_lower for w in ["нарисуй","сгенерируй картинку","создай картинку","нарисовать","сделай картинку","нарисуй мне","сгенерируй изображение","сделай изображение","нарисуй изображение"]):
            for w in ["нарисуй мне","нарисуй","сгенерируй картинку","создай картинку","нарисовать","сделай картинку","сгенерируй изображение","сделай изображение","нарисуй изображение"]:
                q_lower = q_lower.replace(w,"").strip()
            question = f"img {q_lower}"
        # Погода
        elif any(w in q_lower for w in ["погода","какая погода","температура в","погоду в","прогноз погоды","сколько градусов","какой климат"]):
            words = q_lower.split()
            city = "Ташкент"
            for i, w in enumerate(words):
                if w in ["погода","температура","прогноз","градусов"] and i+1 < len(words):
                    city = words[i+1]; break
                elif w == "в" and i+1 < len(words):
                    city = words[i+1]; break
            question = f"weather {city}"
        # Новости
        elif any(w in q_lower for w in ["новости","что случилось","последние события","новости сегодня","что происходит в мире","последние новости"]):
            question = "news"
        # Копировать
        elif any(w in q_lower for w in ["скопируй","скопировать","перенеси сообщения","скопируй сообщения","копируй"]):
            nums = _re.findall(r'\d+', q_lower)
            question = f"copy {nums[0] if nums else '20'}"

    # ══ Специальные команды через триггер ══
    # +deletemsg 10 — удалить последние N своих сообщений
    if question.lower().startswith("deletemsg"):
        parts = question.split()
        count = 10
        if len(parts) > 1:
            try:
                count = min(int(parts[1]), 200)
            except:
                pass
        await message.edit_text(f"🗑 удаляю {count} своих сообщений...")
        try:
            msg_ids = []
            async for msg in client.get_chat_history(message.chat.id, limit=500):
                if msg.from_user and msg.from_user.is_self and msg.id != message.id:
                    msg_ids.append(msg.id)
                    if len(msg_ids) >= count:
                        break
            if msg_ids:
                await client.delete_messages(message.chat.id, msg_ids)
            await message.edit_text(f"✅ Удалено {len(msg_ids)} сообщений")
        except Exception as e:
            await message.edit_text(f"ошибка: {str(e)[:100]}")
        return

    # +search запрос — умный поиск по чатам и участникам
    if question.lower().startswith("search ") or question.lower().startswith("поиск "):
        query = question.split(" ", 1)[1].strip().lower()
        await message.edit_text(f"🔍 ищу '{query}' по всем чатам...")
        try:
            found_msgs = []
            found_users = []
            # Ищем в истории текущего чата
            async for msg in client.get_chat_history(message.chat.id, limit=500):
                if msg.text and query in msg.text.lower():
                    sender = msg.from_user.first_name if msg.from_user else "?"
                    t = msg.date.strftime("%d.%m %H:%M") if msg.date else ""
                    found_msgs.append(f"👤 {sender} [{t}]: {msg.text[:100]}")
                    if len(found_msgs) >= 5:
                        break
                # Ищем участника по имени
                if msg.from_user:
                    name = f"{msg.from_user.first_name or ''} {msg.from_user.last_name or ''}".lower()
                    if query in name and msg.from_user.id not in [u["id"] for u in found_users]:
                        found_users.append({
                            "id": msg.from_user.id,
                            "name": f"{msg.from_user.first_name or ''} {msg.from_user.last_name or ''}".strip(),
                            "username": msg.from_user.username or ""
                        })

            result = f"🔍 **Поиск: {query}**\n\n"
            if found_users:
                result += "**👥 Пользователи:**\n"
                for u in found_users[:3]:
                    uname = f"@{u['username']}" if u['username'] else f"ID: {u['id']}"
                    result += f"• {u['name']} {uname}\n"
                result += "\n"
            if found_msgs:
                result += "**💬 Сообщения:**\n"
                result += "\n".join(found_msgs)
            if not found_users and not found_msgs:
                result += "ничего не найдено"
            await message.edit_text(result)
        except Exception as e:
            await message.edit_text(f"ошибка поиска: {str(e)[:100]}")
        return

    # +contact имя | описание — сохранить контакт
    if question.lower().startswith("contact ") or question.lower().startswith("контакт "):
        parts = question.split(" ", 1)[1].strip()
        await message.edit_text("💾 сохраняю контакт...")
        try:
            # Если ответ на сообщение — берём данные автора
            if message.reply_to_message and message.reply_to_message.from_user:
                u = message.reply_to_message.from_user
                name = f"{u.first_name or ''} {u.last_name or ''}".strip()
                username = u.username or ""
                user_id = u.id
                note = parts  # всё после команды — описание
            else:
                # Парсим формат: "имя | описание"
                if "|" in parts:
                    name, note = [p.strip() for p in parts.split("|", 1)]
                else:
                    name, note = parts, ""
                username = ""
                user_id = None

            contacts_db[name.lower()] = {
                "name": name,
                "username": username,
                "id": user_id,
                "note": note,
                "added": datetime.now().strftime("%d.%m.%Y %H:%M")
            }
            save_contacts(contacts_db)
            await message.edit_text(
                f"✅ Контакт сохранён:\n"
                f"👤 {name}\n"
                f"{'🔗 @' + username if username else ''}"
                f"{'🆔 ' + str(user_id) if user_id else ''}\n"
                f"{'📝 ' + note if note else ''}"
            )
        except Exception as e:
            await message.edit_text(f"ошибка: {str(e)[:100]}")
        return

    # +contacts — показать все контакты
    if question.lower() in ("contacts", "контакты", "мои контакты"):
        if not contacts_db:
            await message.edit_text("📋 Контактов нет\n\nДобавь: +contact имя | описание")
            return
        lines = ["📋 **Мои контакты:**\n"]
        for key, c in list(contacts_db.items())[:20]:
            line = f"👤 {c['name']}"
            if c.get("username"): line += f" @{c['username']}"
            if c.get("id"): line += f" [{c['id']}]"
            if c.get("note"): line += f"\n   📝 {c['note']}"
            lines.append(line)
        await message.edit_text("\n".join(lines))
        return

    # +copy 20 — скопировать сообщения
    if question.lower().startswith("copy"):
        parts = question.split()
        count = 20
        if len(parts) > 1:
            try:
                count = min(int(parts[1]), 100)
            except:
                pass
        target = config.get("copy_target", "givi_iu")
        chat_name = message.chat.title or str(message.chat.id)
        # Удаляем своё сообщение с командой чтобы не засорять чат
        try:
            await message.delete()
        except:
            pass
        status_msg = await client.send_message("me", f"📋 копирую {count} сообщений из {chat_name}...")
        try:
            msgs = []
            # offset_id=0 начинает с самого последнего сообщения
            async for msg in client.get_chat_history(
                message.chat.id,
                limit=count,
                offset_id=0,
                offset=0
            ):
                msgs.append(msg)

            if not msgs:
                await status_msg.edit_text("сообщений не найдено")
                return

            msgs.reverse()
            log.info(f"Copy: найдено {len(msgs)} сообщений в {chat_name}")

            await client.send_message(
                target,
                f"📋 **Из:** {chat_name}\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n📨 {len(msgs)} сообщений"
            )
            copied = 0
            for msg in msgs:
                try:
                    await asyncio.sleep(0.3)
                    if msg.text:
                        sender = msg.from_user.first_name if msg.from_user else "Аноним"
                        t = msg.date.strftime("%H:%M") if msg.date else ""
                        await client.send_message(target, f"👤 **{sender}** [{t}]\n{msg.text[:1000]}")
                        copied += 1
                    elif msg.photo or msg.video or msg.document or msg.sticker:
                        try:
                            await client.forward_messages(target, message.chat.id, msg.id)
                            copied += 1
                        except:
                            pass
                except:
                    pass
            await status_msg.edit_text(f"✅ Скопировано {copied} из {len(msgs)} в @{target}")
        except Exception as e:
            await status_msg.edit_text(f"ошибка: {str(e)[:100]}")
        return

    # +weather город — погода
    if question.lower().startswith("weather ") or question.lower().startswith("погода "):
        city = question.split(" ", 1)[1].strip()
        await message.edit_text(f"🌤 получаю погоду для {city}...")
        try:
            url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status == 200:
                        data = await r.json(content_type=None)
                        current = data["current_condition"][0]
                        temp = current["temp_C"]
                        feels = current["FeelsLikeC"]
                        desc = current["weatherDesc"][0]["value"]
                        humidity = current["humidity"]
                        wind = current["windspeedKmph"]
                        await message.edit_text(
                            f"🌤 **{city}**\n\n"
                            f"🌡 Температура: {temp}°C (ощущается {feels}°C)\n"
                            f"☁️ {desc}\n"
                            f"💧 Влажность: {humidity}%\n"
                            f"💨 Ветер: {wind} км/ч"
                        )
                    else:
                        await message.edit_text(f"не удалось получить погоду для {city}")
        except Exception as e:
            await message.edit_text(f"ошибка: {str(e)[:100]}")
        return

    # +news — последние новости
    if question.lower() in ("news", "новости"):
        await message.edit_text("📰 получаю новости...")
        try:
            url = "https://api.duckduckgo.com/?q=последние+новости+сегодня&format=json&no_html=1"
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    data = await r.json(content_type=None)
            topics = data.get("RelatedTopics", [])[:5]
            lines = []
            for t in topics:
                if isinstance(t, dict) and t.get("Text"):
                    lines.append(f"• {t['Text'][:150]}")
            if lines:
                await message.edit_text("📰 **Новости:**\n\n" + "\n\n".join(lines))
            else:
                # Спрашиваем ИИ
                answer = await ai_request("Расскажи кратко о главных мировых новостях сегодня", message.chat.id, False)
                await message.edit_text(f"📰 {clean_text(answer)}")
        except Exception as e:
            await message.edit_text(f"ошибка: {str(e)[:100]}")
        return


    if question.lower().startswith("google "):
        query = question[7:].strip()
        await message.edit_text(f"🔍 ищу: {query}...")
        try:
            # DuckDuckGo API (бесплатно, без ключа)
            encoded = query.replace(" ", "+")
            url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    data = await r.json(content_type=None)

            results = []
            # Основной ответ
            if data.get("AbstractText"):
                results.append(f"📖 {data['AbstractText'][:500]}")
            # Связанные темы
            for topic in data.get("RelatedTopics", [])[:3]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append(f"• {topic['Text'][:150]}")

            if results:
                answer = f"🔍 **{query}**\n\n" + "\n\n".join(results)
            else:
                # Если DuckDuckGo не дал результат — спрашиваем ИИ
                answer = await ai_request(f"Найди информацию по запросу: {query}", message.chat.id, False)
                answer = f"🔍 **{query}**\n\n{answer}"

            await message.edit_text(clean_text(answer))
        except Exception as e:
            await message.edit_text(f"ошибка поиска: {str(e)[:100]}")
        return

    # +img описание — генерация картинки
    if question.lower().startswith("img ") or question.lower().startswith("image "):
        prompt = question.split(" ", 1)[1].strip()
        status = await client.send_message(message.chat.id, f"🎨 генерирую: {prompt}... (до 60 сек)")
        try:
            await message.delete()
        except:
            pass
        try:
            img_bytes = None

            async with aiohttp.ClientSession() as s:

                # Метод 1: HuggingFace — реальная генерация
                if HF_API_KEY:
                    models = [
                        "stabilityai/stable-diffusion-xl-base-1.0",
                        "runwayml/stable-diffusion-v1-5",
                        "stabilityai/stable-diffusion-2-1",
                    ]
                    for model in models:
                        try:
                            headers = {"Authorization": f"Bearer {HF_API_KEY}"}
                            body = {"inputs": prompt}
                            for attempt in range(3):
                                async with s.post(
                                    f"https://router.huggingface.co/hf-inference/models/{model}",
                                    json=body, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=120)
                                ) as r:
                                    ct = r.headers.get("content-type", "")
                                    log.info(f"HF {model} attempt {attempt}: status={r.status} ct={ct}")
                                    if r.status == 200 and "image" in ct:
                                        data = await r.read()
                                        log.info(f"HF image size: {len(data)} bytes")
                                        if len(data) > 100:  # снижаем порог
                                            img_bytes = data
                                            break
                                    elif r.status == 503:
                                        await asyncio.sleep(15)
                                        continue
                                    else:
                                        err = await r.text()
                                        log.info(f"HF error {r.status}: {err[:200]}")
                                        break
                            if img_bytes:
                                break
                        except Exception as e:
                            log.error(f"HF exception: {e}")
                            continue

                # Метод 2: Lexica — поиск похожих
                if not img_bytes:
                    try:
                        import urllib.parse
                        encoded = urllib.parse.quote(prompt[:200])
                        url = f"https://lexica.art/api/v1/search?q={encoded}"
                        async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                            if r.status == 200:
                                data = await r.json()
                                images = data.get("images", [])
                                if images:
                                    img_url = images[0].get("src")
                                    if img_url:
                                        async with s.get(img_url, timeout=aiohttp.ClientTimeout(total=30)) as ir:
                                            if ir.status == 200:
                                                img_bytes = await ir.read()
                    except:
                        pass

            if img_bytes and len(img_bytes) > 100:
                import io
                await status.delete()
                await client.send_photo(
                    chat_id=message.chat.id,
                    photo=io.BytesIO(img_bytes),
                    caption=f"🎨 {prompt[:100]}"
                )
            else:
                await status.edit_text("⚠️ Не удалось сгенерировать. Попробуй другое описание.")
        except Exception as e:
            await status.edit_text(f"ошибка: {str(e)[:100]}")
        return

    # +мем / +meme — поиск мема
    if question.lower().startswith("мем ") or question.lower().startswith("meme ") or question.lower().startswith("мем"):
        query = question.split(" ", 1)[1].strip() if " " in question else question.replace("мем", "").replace("meme", "").strip()
        if not query:
            query = "funny"
        status = await client.send_message(message.chat.id, f"😂 ищу мем: {query}...")
        try:
            await message.delete()
        except:
            pass
        try:
            import urllib.parse
            encoded = urllib.parse.quote(query + " meme")
            img_bytes = None

            async with aiohttp.ClientSession() as s:
                # Основной метод: HuggingFace генерация мема
                if HF_API_KEY:
                    try:
                        headers = {"Authorization": f"Bearer {HF_API_KEY}"}
                        meme_prompt = f"funny meme image about {query}, humorous cartoon style, text meme format"
                        body = {"inputs": meme_prompt}
                        for model in ["stabilityai/stable-diffusion-xl-base-1.0", "runwayml/stable-diffusion-v1-5"]:
                            async with s.post(
                                f"https://router.huggingface.co/hf-inference/models/{model}",
                                json=body, headers=headers,
                                timeout=aiohttp.ClientTimeout(total=120)
                            ) as r:
                                ct = r.headers.get("content-type", "")
                                log.info(f"HF meme {model}: status={r.status} ct={ct}")
                                if r.status == 200 and "image" in ct:
                                    d = await r.read()
                                    log.info(f"HF meme size: {len(d)}")
                                    if len(d) > 100:
                                        img_bytes = d
                                        break
                                elif r.status == 503:
                                    await asyncio.sleep(10)
                    except Exception as e:
                        log.error(f"HF meme error: {e}")

                # Запасной: meme-api.com
                if not img_bytes:
                    try:
                        async with s.get(
                            "https://meme-api.com/gimme/5",
                            timeout=aiohttp.ClientTimeout(total=15)
                        ) as r:
                            if r.status == 200:
                                data = await r.json()
                                for meme in data.get("memes", []):
                                    img_url = meme.get("url", "")
                                    if img_url.endswith((".jpg", ".jpeg", ".png")):
                                        async with s.get(img_url, timeout=aiohttp.ClientTimeout(total=20)) as ir:
                                            if ir.status == 200:
                                                d = await ir.read()
                                                if len(d) > 1000:
                                                    img_bytes = d
                                                    break
                    except Exception as e:
                        log.error(f"meme-api error: {e}")

                # Метод 3: HuggingFace генерация
                if not img_bytes and HF_API_KEY:
                    try:
                        headers = {"Authorization": f"Bearer {HF_API_KEY}"}
                        body = {"inputs": f"funny meme about {query}, humorous, viral meme style"}
                        async with s.post(
                            "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-base-1.0",
                            json=body, headers=headers,
                            timeout=aiohttp.ClientTimeout(total=120)
                        ) as r:
                            if r.status == 200 and "image" in r.headers.get("content-type", ""):
                                d = await r.read()
                                if len(d) > 100:
                                    img_bytes = d
                    except Exception as e:
                        log.error(f"HF meme error: {e}")

            if img_bytes and len(img_bytes) > 1000:
                import io
                await status.delete()
                await client.send_photo(
                    chat_id=message.chat.id,
                    photo=io.BytesIO(img_bytes),
                    caption=f"😂 {query}"
                )
            else:
                await status.edit_text(f"мем не найден 😢 попробуй другое название")
        except Exception as e:
            await status.edit_text(f"ошибка: {str(e)[:100]}")
        return

    # +send @chat текст — отправить сообщение в любой чат
    if question.lower().startswith("send ") or question.lower().startswith("отправь "):
        parts = question.split(None, 2)
        if len(parts) >= 3:
            target = parts[1].replace("@", "")
            text_to_send = parts[2]
            await message.edit_text(f"📤 отправляю в {target}...")
            try:
                await client.send_message(target, text_to_send)
                await message.edit_text(f"✅ Отправлено в @{target}")
            except Exception as e:
                await message.edit_text(f"ошибка: {str(e)[:100]}")
        else:
            await message.edit_text("Формат: +send @username текст сообщения")
        return

    # +block @user — заблокировать
    if question.lower().startswith("block ") or question.lower().startswith("блок "):
        parts = question.split()
        if len(parts) > 1:
            target = parts[1].replace("@", "")
            await message.edit_text(f"🚫 блокирую {target}...")
            try:
                await client.block_user(target)
                await message.edit_text(f"✅ {target} заблокирован")
            except Exception as e:
                await message.edit_text(f"ошибка: {str(e)[:100]}")
        return

    # +unblock @user — разблокировать
    if question.lower().startswith("unblock ") or question.lower().startswith("разблок "):
        parts = question.split()
        if len(parts) > 1:
            target = parts[1].replace("@", "")
            await message.edit_text(f"✅ разблокирую {target}...")
            try:
                await client.unblock_user(target)
                await message.edit_text(f"✅ {target} разблокирован")
            except Exception as e:
                await message.edit_text(f"ошибка: {str(e)[:100]}")
        return

    # +download — скачать медиа из сообщения
    if question.lower() in ("download", "скачай", "скачать"):
        if not message.reply_to_message:
            await message.edit_text("ответь на сообщение с медиа командой +скачай")
            return
        replied = message.reply_to_message
        media = replied.photo or replied.video or replied.document or replied.audio or replied.voice
        if not media:
            await message.edit_text("в сообщении нет медиа")
            return
        await message.edit_text("⬇️ скачиваю...")
        try:
            path = await client.download_media(media, file_name=f"/sdcard/Download/")
            await message.edit_text(f"✅ Сохранено: {path}")
        except Exception as e:
            await message.edit_text(f"ошибка: {str(e)[:100]}")
        return

    # +digest — читать все чаты и делать дайджест
    if question.lower() in ("digest", "дайджест", "читай все", "что нового везде"):
        await message.edit_text("📖 читаю все чаты... (займёт 30-60 сек)")
        try:
            summaries = []
            count = 0
            async for dialog in client.get_dialogs(limit=20):
                try:
                    chat = dialog.chat
                    chat_name = chat.title or chat.first_name or str(chat.id)
                    msgs = []
                    async for msg in client.get_chat_history(chat.id, limit=5):
                        if msg.text:
                            sender = msg.from_user.first_name if msg.from_user else "?"
                            msgs.append(f"{sender}: {msg.text[:100]}")
                    if msgs:
                        summaries.append(f"💬 **{chat_name}**: {msgs[0]}")
                        count += 1
                    if count >= 10:
                        break
                except:
                    continue
            if summaries:
                result = f"📰 **Дайджест чатов:**\n\n" + "\n\n".join(summaries)
                await client.send_message("me", result)
                await message.edit_text(f"✅ Дайджест {count} чатов → в избранное")
            else:
                await message.edit_text("нет активных чатов")
        except Exception as e:
            await message.edit_text(f"ошибка: {str(e)[:100]}")
        return

    # +forward @target — пересылать все сообщения из этого чата в другой
    if question.lower().startswith("forward ") or question.lower().startswith("пересылай "):
        parts = question.split()
        if len(parts) > 1:
            target = parts[1].replace("@", "")
            config["forward_from"] = config.get("forward_from", {})
            chat_id_str = str(message.chat.id)
            if config["forward_from"].get(chat_id_str) == target:
                del config["forward_from"][chat_id_str]
                save_config(config)
                await message.edit_text(f"❌ Пересылка из этого чата в @{target} отключена")
            else:
                config["forward_from"][chat_id_str] = target
                save_config(config)
                await message.edit_text(f"✅ Все сообщения из этого чата → @{target}")
        return

    # +creategroup название — создать супергруппу
    if question.lower().startswith("creategroup ") or question.lower().startswith("создай группу "):
        for w in ["creategroup ", "создай группу "]:
            if question.lower().startswith(w):
                group_name = question[len(w):].strip()
                break
        await message.edit_text(f"👥 создаю группу {group_name}...")
        try:
            chat = await client.create_group(group_name, [])
            await client.promote_chat_member(chat.id, (await client.get_me()).id,
                can_change_info=True, can_invite_users=True, can_delete_messages=True)
            await message.edit_text(f"✅ Группа создана: **{group_name}**\nID: `{chat.id}`")
        except Exception as e:
            await message.edit_text(f"ошибка: {str(e)[:100]}")
        return

    # +saveinfo — сохранить мои данные в избранное
    if question.lower() in ("saveinfo", "сохрани мои данные", "запомни меня"):
        await message.edit_text("💾 сохраняю твои данные...")
        try:
            me = await client.get_me()
            info = (
                f"👤 **Мои данные**\n\n"
                f"Имя: {me.first_name or ''} {me.last_name or ''}\n"
                f"Username: @{me.username or 'нет'}\n"
                f"ID: `{me.id}`\n"
                f"Телефон: {me.phone_number or 'скрыт'}\n"
                f"Premium: {'✅' if me.is_premium else '❌'}\n"
                f"DC: {me.dc_id}\n"
                f"Дата сохранения: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            await client.send_message("me", info)
            await message.edit_text("✅ Данные сохранены в избранное")
        except Exception as e:
            await message.edit_text(f"ошибка: {str(e)[:100]}")
        return

    # +info / кто это / кто такой — полная информация о пользователе
    q_info = question.lower()
    is_info_cmd = (
        q_info.startswith("info") or
        q_info == "info" or
        any(w in q_info for w in ["кто такой", "кто такая", "кто это"]) or
        "t.me/" in question or
        "https://t.me/" in question
    )
    if is_info_cmd:
        target_user = None
        target_id = None

        # Если ответ на чьё-то сообщение — берём автора
        if message.reply_to_message and message.reply_to_message.from_user:
            target_user = message.reply_to_message.from_user
            target_id = target_user.id
        else:
            import re as _re
            # Парсим t.me ссылки
            tme_match = _re.search(r't\.me/([a-zA-Z0-9_+]+)', question)
            mentions = _re.findall(r'@(\w+)', message.text)
            ids = _re.findall(r'\b(\d{5,12})\b', message.text)

            if tme_match:
                username = tme_match.group(1)
                try:
                    # Пробуем как пользователя
                    target_user = await client.get_users(username)
                    target_id = target_user.id
                except:
                    # Пробуем как чат/группу
                    try:
                        chat = await client.get_chat(username)
                        # Показываем инфо о чате
                        chat_lines = [f"💬 **Информация о чате**\n"]
                        chat_lines.append(f"📛 Название: {chat.title or chat.first_name or '?'}")
                        if chat.username:
                            chat_lines.append(f"🔗 Username: @{chat.username}")
                        chat_lines.append(f"🆔 ID: `{chat.id}`")
                        chat_lines.append(f"📂 Тип: {str(chat.type.value)}")
                        if hasattr(chat, 'members_count') and chat.members_count:
                            chat_lines.append(f"👥 Участников: {chat.members_count}")
                        if hasattr(chat, 'description') and chat.description:
                            chat_lines.append(f"📝 Описание: {chat.description[:200]}")
                        if hasattr(chat, 'invite_link') and chat.invite_link:
                            chat_lines.append(f"🔗 Ссылка: {chat.invite_link}")
                        await message.edit_text("\n".join(chat_lines))
                        return
                    except Exception as e:
                        await message.edit_text(f"не удалось получить инфо: {str(e)[:100]}")
                        return
            elif mentions:
                try:
                    target_user = await client.get_users(mentions[0])
                    target_id = target_user.id
                except:
                    pass
            elif ids:
                try:
                    target_user = await client.get_users(int(ids[0]))
                    target_id = target_user.id
                except:
                    pass
            else:
                # Поиск по имени
                q_clean = q_info
                for w in ["кто такой", "кто такая", "кто это", "инфо о", "информация о", "расскажи о", "info", "узнай кто", "данные о"]:
                    q_clean = q_clean.replace(w, "").strip()
                search_name = q_clean.strip()

                if search_name and len(search_name) > 1:
                    await message.edit_text(f"🔍 ищу {search_name} в чате...")

                    # Сначала ищем в истории сообщений
                    found_id = None
                    async for msg in client.get_chat_history(message.chat.id, limit=300):
                        if msg.from_user:
                            full_name = f"{msg.from_user.first_name or ''} {msg.from_user.last_name or ''}".strip().lower()
                            uname = (msg.from_user.username or "").lower()
                            if search_name in full_name or search_name in uname:
                                found_id = msg.from_user.id
                                break

                    # Если не нашли — ищем в участниках группы
                    if not found_id and message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                        try:
                            async for member in client.get_chat_members(message.chat.id):
                                u = member.user
                                full_name = f"{u.first_name or ''} {u.last_name or ''}".strip().lower()
                                uname = (u.username or "").lower()
                                if search_name in full_name or search_name in uname:
                                    found_id = u.id
                                    break
                        except:
                            pass

                    if found_id:
                        try:
                            target_user = await client.get_users(found_id)
                            target_id = found_id
                        except:
                            pass

                    if not target_user:
                        await message.edit_text(f"пользователь '{search_name}' не найден в этом чате")
                        return
                else:
                    await message.edit_text(
                        "напиши имя пользователя:\n"
                        "+кто такой Паштет\n"
                        "+info @username\n"
                        "или ответь на сообщение и напиши +info"
                    )
                    return

        await message.edit_text("🔍 собираю информацию...")

        try:
            # Получаем полные данные
            full_user = await client.get_users(target_id)

            info_lines = []
            info_lines.append(f"👤 **Информация о пользователе**\n")

            # Имя
            first = getattr(full_user, 'first_name', '') or ''
            last = getattr(full_user, 'last_name', '') or ''
            name = f"{first} {last}".strip()
            info_lines.append(f"📛 Имя: {name}")

            # Username
            username = getattr(full_user, 'username', None)
            if username:
                info_lines.append(f"🔗 Username: @{username}")

            # ID
            info_lines.append(f"🆔 ID: `{full_user.id}`")

            # Флаги
            if getattr(full_user, 'is_bot', False):
                info_lines.append(f"🤖 Тип: Бот")
            if getattr(full_user, 'is_verified', False):
                info_lines.append(f"✅ Верифицирован: Да")
            if getattr(full_user, 'is_scam', False):
                info_lines.append(f"⚠️ Скам аккаунт!")
            if getattr(full_user, 'is_fake', False):
                info_lines.append(f"⚠️ Фейк аккаунт!")
            if getattr(full_user, 'is_premium', False):
                info_lines.append(f"⭐ Premium: Да")
            if getattr(full_user, 'is_deleted', False):
                info_lines.append(f"🗑 Аккаунт удалён")

            # Телефон
            phone = getattr(full_user, 'phone_number', None)
            if phone:
                info_lines.append(f"📱 Телефон: {phone}")

            # Bio — пробуем все возможные атрибуты
            bio = None
            for attr in ['bio', 'about', 'description', 'status']:
                val = getattr(full_user, attr, None)
                if val and isinstance(val, str) and len(val) > 1:
                    bio = val
                    break
            if bio:
                info_lines.append(f"📝 Bio: {bio[:200]}")

            # DC (датацентр — страна)
            dc = getattr(full_user, 'dc_id', None)
            if dc:
                dc_countries = {1: "🇺🇸 США", 2: "🇳🇱 Нидерланды", 3: "🇺🇸 США", 4: "🇳🇱 Нидерланды", 5: "🇸🇬 Сингапур"}
                info_lines.append(f"🌍 Сервер: DC{dc} {dc_countries.get(dc, '')}")

            # Сообщения в текущем чате
            if message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                info_lines.append(f"\n💬 **В чате {message.chat.title}:**")
                msg_count = 0
                last_msg = ""
                async for msg in client.get_chat_history(message.chat.id, limit=500):
                    if msg.from_user and msg.from_user.id == target_id:
                        msg_count += 1
                        if not last_msg and msg.text:
                            last_msg = msg.text[:100]
                if msg_count > 0:
                    info_lines.append(f"📊 Сообщений: {msg_count}")
                if last_msg:
                    info_lines.append(f"✉️ Последнее: {last_msg}")

            await message.edit_text("\n".join(info_lines))
            log.info(f"Info: {name} (ID: {target_id})")

        except Exception as e:
            await message.edit_text(f"не удалось получить инфо: {str(e)[:150]}")
        return


    if question.lower() in ("deletechat", "удалить чат", "покинуть чат"):
        chat_id = message.chat.id
        chat_type = message.chat.type
        chat_name = message.chat.title or message.chat.first_name or str(chat_id)
        await message.edit_text(f"🗑 обрабатываю {chat_name}...")
        try:
            if chat_type == ChatType.PRIVATE:
                # Личка — удаляем ВСЕ сообщения с обеих сторон через revoke
                deleted = 0
                msg_ids = []
                async for msg in client.get_chat_history(chat_id):
                    msg_ids.append(msg.id)
                    if len(msg_ids) >= 100:
                        try:
                            await client.delete_messages(chat_id, msg_ids, revoke=True)
                            deleted += len(msg_ids)
                            msg_ids = []
                            await asyncio.sleep(0.5)
                        except:
                            pass
                # Удаляем остаток
                if msg_ids:
                    try:
                        await client.delete_messages(chat_id, msg_ids, revoke=True)
                        deleted += len(msg_ids)
                    except:
                        pass
                await message.edit_text(f"✅ Удалено {deleted} сообщений в {chat_name}")
            elif chat_type in (ChatType.GROUP, ChatType.SUPERGROUP):
                # Удаляем свои сообщения потом выходим
                deleted = 0
                async for msg in client.get_chat_history(chat_id, limit=200):
                    try:
                        if msg.from_user and msg.from_user.is_self:
                            await msg.delete()
                            deleted += 1
                            await asyncio.sleep(0.05)
                    except:
                        pass
                await client.leave_chat(chat_id)
                await client.send_message("me", f"✅ Удалено {deleted} сообщений и покинул группу: {chat_name}")
            elif chat_type == ChatType.CHANNEL:
                await client.leave_chat(chat_id)
                await client.send_message("me", f"✅ Покинул канал: {chat_name}")
            log.info(f"Удалён/покинут: {chat_name}")
        except Exception as e:
            await message.edit_text(f"ошибка: {str(e)[:150]}")
        return

    is_group = message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL)

    # Автосканирование при первом использовании в этом чате
    asyncio.create_task(scan_chat_history(client, message.chat.id, 40))

    # Если это reply на чьё-то сообщение — добавляем его контекст
    full_question = question
    if message.reply_to_message:
        replied = message.reply_to_message
        replied_text = replied.text or replied.caption or ""
        replied_name = ""
        if replied.from_user:
            replied_name = replied.from_user.first_name or "Собеседник"

        log.info(f"Reply detected: from={replied_name} text={replied_text[:50]}")

        if replied_text:
            if question:
                full_question = f"Сообщение от {replied_name}: «{replied_text}»\n\nМой вопрос: {question}"
            else:
                full_question = f"Ответь на это сообщение от {replied_name}: «{replied_text}»"
        log.info(f"full_question: {full_question[:80]}")
    elif not question:
        # Нет reply и нет вопроса — молчим
        return

    if is_group:
        me = await client.get_me()
        my_name = me.first_name or "Я"
        add_to_history(message.chat.id, my_name, question)
        delay = config.get("antispam_delay", 6)
        if delay > 0:
            await asyncio.sleep(delay)

    # Надёжный ответ с повторной попыткой
    max_retries = 3
    answer = None
    last_error = None

    for attempt in range(max_retries):
        try:
            answer = await ai_request(full_question, message.chat.id, is_group, client=client, message=message)
            break
        except Exception as e:
            last_error = e
            log.warning(f"AI попытка {attempt+1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                # Переключаемся на запасной ИИ
                fallback = {"groq": "cohere", "cohere": "groq", "claude": "groq",
                           "gemini": "groq", "deepseek": "groq", "gpt": "groq"}
                old_ai = config.get("active_ai", "groq")
                config["active_ai"] = fallback.get(old_ai, "groq")
                await asyncio.sleep(2)

    if answer:
        clean = clean_text(answer)

        # TTS — отвечаем голосовым
        if config.get("tts_reply"):
            audio = await text_to_speech(clean)
            if audio:
                import io
                try:
                    await client.send_voice(
                        chat_id=message.chat.id,
                        voice=io.BytesIO(audio),
                        reply_to_message_id=message.id
                    )
                    if is_group:
                        add_to_history(message.chat.id, my_name, answer)
                    return
                except:
                    pass

        # Обычный текстовый ответ
        try:
            sent = await client.send_message(
                chat_id=message.chat.id,
                text=clean,
                reply_to_message_id=message.id
            )
        except Exception:
            sent = await client.send_message(chat_id=message.chat.id, text=clean)

        # Авто удаление если включено
        autodestruct = config.get("autodestruct", 0)
        if autodestruct > 0 and sent:
            async def delete_later(msg, delay):
                await asyncio.sleep(delay)
                try:
                    await msg.delete()
                except:
                    pass
            asyncio.create_task(delete_later(sent, autodestruct))

        if is_group:
            add_to_history(message.chat.id, my_name, answer)
        log.info(f"[{config['active_ai']}] {message.chat.id}: {question[:40]}")
    else:
        log.error(f"AI Error после {max_retries} попыток: {last_error}")
        try:
            await client.send_message(
                chat_id=message.chat.id,
                text=f"не могу ответить сейчас, попробуй позже",
                reply_to_message_id=message.id
            )
        except:
            pass

@app.on_message(filters.outgoing & filters.photo)
async def handle_outgoing_photo(client: Client, message: Message):
    """Когда ТЫ отправляешь фото с подписью + — анализирует"""
    if not message.caption:
        return
    trigger = config.get("trigger", "+")
    if not message.caption.strip().startswith(trigger):
        return
    question = message.caption.strip()[len(trigger):].strip() or "Что на этом фото? Опиши подробно."
    try:
        photo = await client.download_media(message.photo, in_memory=True)
        photo_bytes = bytes(photo.getbuffer())
        answer = await analyze_photo(photo_bytes, question)
        await client.send_message(chat_id=message.chat.id, text=f"🖼 {clean_text(answer)}", reply_to_message_id=message.id)
    except Exception as e:
        await client.send_message(chat_id=message.chat.id, text=f"не смог: {str(e)[:80]}")

# ══════════════════════════ КОМАНДЫ ══════════════════════════════════
@app.on_message(filters.outgoing & filters.command("save", prefixes="."))
async def cmd_save(client: Client, message: Message):
    """Сохранить важное сообщение в избранное"""
    target = message.reply_to_message
    if not target:
        await message.edit_text("ответь на сообщение командой .save")
        return
    try:
        me = await client.get_me()
        saved_text = ""
        if target.text:
            saved_text = target.text
        elif target.caption:
            saved_text = target.caption
        elif target.sticker:
            saved_text = f"[стикер] {target.sticker.emoji or ''}"
        elif target.voice:
            saved_text = "[голосовое сообщение]"
        elif target.photo:
            saved_text = f"[фото] {target.caption or ''}"

        sender = target.from_user.first_name if target.from_user else "Неизвестно"
        chat_name = message.chat.title or message.chat.first_name or "Личка"
        time_str = datetime.now().strftime("%d.%m.%Y %H:%M")

        forward_text = (
            f"💾 **Сохранено**\n"
            f"👤 От: {sender}\n"
            f"💬 Чат: {chat_name}\n"
            f"🕐 {time_str}\n\n"
            f"{saved_text}"
        )

        # Пересылаем в избранное (saved messages)
        await client.send_message("me", forward_text)
        await message.edit_text("✅ Сохранено в избранное!")
        log.info(f"Сохранено сообщение от {sender}")
    except Exception as e:
        await message.edit_text(f"ошибка: {str(e)[:80]}")

@app.on_message(filters.outgoing & filters.command("react", prefixes="."))
async def cmd_react_toggle(client: Client, message: Message):
    args = message.text.split()[1:]
    if not args:
        state = "вкл" if config.get("auto_react") else "выкл"
        await message.edit_text(f"⚡ авто реакции: **{state}**\n.react on|off")
        return
    config["auto_react"] = args[0].lower() == "on"
    save_config(config)
    await message.edit_text(f"⚡ авто реакции {'включены ✅' if config['auto_react'] else 'выключены ❌'}")

@app.on_message(filters.outgoing & filters.command("doc", prefixes="."))
async def cmd_doc(client: Client, message: Message):
    args = message.text.split()[1:]
    if not args:
        state = "вкл" if config.get("doc_analysis", True) else "выкл"
        await message.edit_text(f"📄 анализ документов: **{state}**\n.doc on|off")
        return
    config["doc_analysis"] = args[0].lower() == "on"
    save_config(config)
    await message.edit_text(f"📄 анализ документов {'включён ✅' if config['doc_analysis'] else 'выключен ❌'}")

@app.on_message(filters.outgoing & filters.command("sticker", prefixes="."))
async def cmd_sticker(client: Client, message: Message):
    args = message.text.split()[1:]
    if not args:
        state = "вкл" if config.get("sticker_reply", True) else "выкл"
        await message.edit_text(f"ответ на стикеры: **{state}**\n.sticker on|off")
        return
    config["sticker_reply"] = args[0].lower() == "on"
    save_config(config)
    await message.edit_text(f"ответ на стикеры {'включён ✅' if config['sticker_reply'] else 'выключен ❌'}")

@app.on_message(filters.outgoing & filters.command("reaction", prefixes="."))
async def cmd_reaction(client: Client, message: Message):
    args = message.text.split()[1:]
    if not args:
        state = "вкл" if config.get("reaction_reply", True) else "выкл"
        await message.edit_text(f"ответ на реакции: **{state}**\n.reaction on|off")
        return
    config["reaction_reply"] = args[0].lower() == "on"
    save_config(config)
    await message.edit_text(f"ответ на реакции {'включён ✅' if config['reaction_reply'] else 'выключен ❌'}")

@app.on_message(filters.outgoing & filters.command("call", prefixes="."))
async def cmd_call(client: Client, message: Message):
    args = message.text.split()[1:]
    if not args:
        state = "вкл" if config.get("call_reply", True) else "выкл"
        await message.edit_text(f"ответ на звонки: **{state}**\n.call on|off")
        return
    config["call_reply"] = args[0].lower() == "on"
    save_config(config)
    await message.edit_text(f"ответ на звонки {'включён ✅' if config['call_reply'] else 'выключен ❌'}")


    args = message.text.split()[1:]
    if not args:
        await message.edit_text(f"сейчас: **{config['active_ai']}**\n.ai groq|cohere|claude|gemini|deepseek|gpt")
        return
    ai = args[0].lower()
    if ai not in AI_MAP:
        await message.edit_text("некорректно. groq, cohere, claude, gemini, deepseek или gpt")
        return
    config["active_ai"] = ai
    save_config(config)
    await message.edit_text(f"переключился на **{ai}** ✅")

@app.on_message(filters.outgoing & filters.command("ai", prefixes="."))
async def cmd_ai(client: Client, message: Message):
    args = message.text.split()[1:]
    if not args:
        await message.edit_text(
            f"сейчас: **{config['active_ai']}**\n"
            ".ai groq|cohere|claude|gemini|deepseek|gpt|mistral|together|huggingface"
        )
        return
    ai = args[0].lower()
    if ai not in AI_MAP:
        await message.edit_text("некорректно. groq, cohere, claude, gemini, deepseek, gpt, mistral, together, huggingface")
        return
    config["active_ai"] = ai
    save_config(config)
    desc = {
        "groq": "Groq Llama 🆓", "cohere": "Cohere 🆓",
        "claude": "Claude 🧠", "gemini": "Gemini ✨",
        "deepseek": "DeepSeek 🔮", "gpt": "GPT-4o mini 🤖",
        "mistral": "Mistral 🆓", "together": "Together AI 🆓",
        "huggingface": "HuggingFace 🆓", "hf": "HuggingFace 🆓",
    }
    await message.edit_text(f"переключился на **{desc.get(ai, ai)}** ✅")

@app.on_message(filters.outgoing & filters.command("autoreply", prefixes="."))
async def cmd_autoreply(client: Client, message: Message):
    log.info(f"CMD autoreply получена: {message.text}")
    args = message.text.split(None, 2)[1:]
    if not args:
        state = "вкл" if config.get("autoreply_on") else "выкл"
        await message.edit_text(f"автоответ: **{state}**\nтекст: {config.get('autoreply_text', '')}\n\n.autoreply on|off\n.autoreply text <текст>")
        return
    if args[0] == "on":
        config["autoreply_on"] = True
        save_config(config)
        log.info("Автоответ ВКЛЮЧЁН")
        await message.edit_text("автоответ включён ✅")
    elif args[0] == "off":
        config["autoreply_on"] = False
        save_config(config)
        log.info("Автоответ ВЫКЛЮЧЕН")
        await message.edit_text("автоответ выключен ❌")
    elif args[0] == "text" and len(args) > 1:
        config["autoreply_text"] = args[1]
        save_config(config)
        await message.edit_text(f"текст автоответа обновлён ✅")

@app.on_message(filters.outgoing & filters.command("voice", prefixes="."))
async def cmd_voice(client: Client, message: Message):
    args = message.text.split()[1:]
    if not args:
        state = "вкл" if config.get("voice_reply") else "выкл"
        await message.edit_text(f"распознавание голоса: **{state}**\n.voice on|off")
        return
    config["voice_reply"] = args[0].lower() == "on"
    save_config(config)
    await message.edit_text(f"распознавание голоса {'включено ✅' if config['voice_reply'] else 'выключено ❌'}")

@app.on_message(filters.outgoing & filters.command("translate", prefixes="."))
async def cmd_translate(client: Client, message: Message):
    args = message.text.split()[1:]
    if not args:
        state = "вкл" if config.get("translate_on") else "выкл"
        await message.edit_text(f"авто перевод: **{state}**\n.translate on|off")
        return
    config["translate_on"] = args[0].lower() == "on"
    save_config(config)
    await message.edit_text(f"авто перевод {'включён ✅' if config['translate_on'] else 'выключен ❌'}")

@app.on_message(filters.outgoing & filters.command("photo", prefixes="."))
async def cmd_photo(client: Client, message: Message):
    args = message.text.split()[1:]
    if not args:
        state = "вкл" if config.get("photo_analysis") else "выкл"
        await message.edit_text(f"анализ фото: **{state}**\n.photo on|off\n\nТребует GEMINI_API_KEY")
        return
    config["photo_analysis"] = args[0].lower() == "on"
    save_config(config)
    await message.edit_text(f"анализ фото {'включён ✅' if config['photo_analysis'] else 'выключен ❌'}")

@app.on_message(filters.outgoing & filters.command("copy", prefixes="."))
async def cmd_copy(client: Client, message: Message):
    """Скопировать последние N сообщений в твою группу"""
    log.info(f"COPY CMD получена: {message.text}")
    global config
    config = load_config()
    args = message.text.split()[1:]

    # Определяем количество
    count = 20
    if args:
        try:
            count = min(int(args[0]), 100)  # максимум 100
        except:
            pass

    target = config.get("copy_target", "givi_iu")
    chat_name = message.chat.title or str(message.chat.id)

    await message.edit_text(f"📋 копирую {count} сообщений из {chat_name}...")

    try:
        copied = 0
        failed = 0
        msgs = []

        # Собираем сообщения
        async for msg in client.get_chat_history(message.chat.id, limit=count):
            msgs.append(msg)

        msgs.reverse()  # от старых к новым

        # Отправляем заголовок
        await client.send_message(
            target,
            f"📋 **Скопировано из:** {chat_name}\n"
            f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"📨 Сообщений: {len(msgs)}"
        )

        for msg in msgs:
            try:
                await asyncio.sleep(0.5)  # небольшая задержка
                if msg.text:
                    sender = msg.from_user.first_name if msg.from_user else "Аноним"
                    time_str = msg.date.strftime("%H:%M") if msg.date else ""
                    await client.send_message(
                        target,
                        f"👤 **{sender}** [{time_str}]\n{msg.text[:1000]}"
                    )
                    copied += 1
                elif msg.photo:
                    await client.forward_messages(target, message.chat.id, msg.id)
                    copied += 1
                elif msg.video:
                    await client.forward_messages(target, message.chat.id, msg.id)
                    copied += 1
                elif msg.document:
                    await client.forward_messages(target, message.chat.id, msg.id)
                    copied += 1
            except:
                failed += 1

        await message.edit_text(
            f"✅ Скопировано {copied} сообщений в @{target}\n"
            f"❌ Ошибок: {failed}"
        )
        log.info(f"Copy: {copied} сообщений из {chat_name} → {target}")

    except Exception as e:
        await message.edit_text(f"ошибка копирования: {str(e)[:100]}")

@app.on_message(filters.outgoing & filters.command("setcopy", prefixes="."))
async def cmd_setcopy(client: Client, message: Message):
    """Установить целевую группу для копирования"""
    args = message.text.split()[1:]
    if not args:
        await message.edit_text(
            f"текущая группа: **@{config.get('copy_target', 'не задана')}**\n"
            ".setcopy username — сменить группу"
        )
        return
    username = args[0].replace("@", "").replace("https://t.me/", "")
    config["copy_target"] = username
    save_config(config)
    await message.edit_text(f"✅ группа для копирования: **@{username}**")

@app.on_message(filters.outgoing & filters.command("mention", prefixes="."))
async def cmd_mention(client: Client, message: Message):
    args = message.text.split()[1:]
    if not args:
        state = "вкл" if config.get("mention_reply") else "выкл"
        await message.edit_text(f"ответ на упоминание: **{state}**\n.mention on|off")
        return
    config["mention_reply"] = args[0].lower() == "on"
    save_config(config)
    await message.edit_text(f"ответ на упоминание {'включён ✅' if config['mention_reply'] else 'выключен ❌'}")

@app.on_message(filters.outgoing & filters.command("delay", prefixes="."))
async def cmd_delay(client: Client, message: Message):
    args = message.text.split()[1:]
    if not args:
        await message.edit_text(f"задержка: **{config.get('antispam_delay', 6)}с**\n.delay <секунды>")
        return
    try:
        config["antispam_delay"] = int(args[0])
        save_config(config)
        await message.edit_text(f"задержка: **{args[0]}с** ✅")
    except:
        await message.edit_text("укажи число")

@app.on_message(filters.outgoing & filters.command("join", prefixes="."))
async def cmd_join(client: Client, message: Message):
    """Авто вступление в разговор группы"""
    args = message.text.split()[1:]
    if not args:
        state = "вкл" if config.get("auto_join") else "выкл"
        interval = config.get("auto_join_interval", 60)
        msgs = config.get("auto_join_messages", 3)
        await message.edit_text(
            f"💬 авто вступление: **{state}**\n\n"
            f"Интервал: {interval}с\n"
            f"Мин. сообщений: {msgs}\n\n"
            ".join on|off\n"
            ".join interval <сек> — минимальный интервал\n"
            ".join messages <кол-во> — сообщений перед ответом"
        )
        return
    if args[0] == "on":
        config["auto_join"] = True
        save_config(config)
        await message.edit_text("💬 авто вступление включено ✅\nТеперь иногда буду сам вступать в разговор 😈")
    elif args[0] == "off":
        config["auto_join"] = False
        save_config(config)
        await message.edit_text("💬 авто вступление выключено ❌")
    elif args[0] == "interval" and len(args) > 1:
        try:
            config["auto_join_interval"] = int(args[1])
            save_config(config)
            await message.edit_text(f"✅ интервал: {args[1]}с")
        except:
            await message.edit_text("укажи число секунд")
    elif args[0] == "messages" and len(args) > 1:
        try:
            config["auto_join_messages"] = int(args[1])
            save_config(config)
            await message.edit_text(f"✅ мин. сообщений: {args[1]}")
        except:
            await message.edit_text("укажи число")

@app.on_message(filters.outgoing & filters.command("spy", prefixes="."))
async def cmd_spy(client: Client, message: Message):
    args = message.text.split()[1:]
    if not args:
        state = "вкл" if config.get("spy_mode") else "выкл"
        await message.edit_text(f"🕵️ шпион режим: **{state}**\n.spy on|off\n\nСохраняет удалённые сообщения в избранное")
        return
    config["spy_mode"] = args[0].lower() == "on"
    save_config(config)
    await message.edit_text(f"🕵️ шпион {'включён ✅' if config['spy_mode'] else 'выключен ❌'}")

@app.on_message(filters.outgoing & filters.command("persona", prefixes="."))
async def cmd_persona(client: Client, message: Message):
    """Тайный режим — отвечать как другой человек"""
    args = message.text.split(None, 2)[1:]
    if not args:
        state = "вкл" if config.get("persona_on") else "выкл"
        name = config.get("persona_name", "не задан")
        await message.edit_text(
            f"🎭 Тайный режим: **{state}**\n"
            f"Персона: {name}\n\n"
            ".persona on|off\n"
            ".persona set Имя | описание характера\n\n"
            "Пример: `.persona set Алексей | программист 25 лет, говорит коротко`"
        )
        return
    if args[0] == "on":
        if not config.get("persona_name"):
            await message.edit_text("Сначала задай персону: `.persona set Имя | описание`")
            return
        config["persona_on"] = True
        save_config(config)
        await message.edit_text(f"🎭 Тайный режим включён — отвечаю как **{config['persona_name']}** ✅")
    elif args[0] == "off":
        config["persona_on"] = False
        save_config(config)
        await message.edit_text("🎭 Тайный режим выключен ❌")
    elif args[0] == "set" and len(args) > 1:
        parts = args[1].split("|", 1)
        name = parts[0].strip()
        desc = parts[1].strip() if len(parts) > 1 else ""
        config["persona_name"] = name
        config["persona_desc"] = desc
        save_config(config)
        await message.edit_text(f"✅ Персона задана:\n👤 **{name}**\n📝 {desc}")

@app.on_message(filters.outgoing & filters.command("tts", prefixes="."))
async def cmd_tts(client: Client, message: Message):
    """TTS — голосовые ответы"""
    args = message.text.split()[1:]
    if not args:
        state = "вкл" if config.get("tts_reply") else "выкл"
        await message.edit_text(f"🎙 Голосовые ответы: **{state}**\n.tts on|off")
        return
    config["tts_reply"] = args[0].lower() == "on"
    save_config(config)
    await message.edit_text(f"🎙 Голосовые ответы {'включены ✅' if config['tts_reply'] else 'выключены ❌'}")

@app.on_message(filters.outgoing & filters.command("say", prefixes="."))
async def cmd_say(client: Client, message: Message):
    """Отправить голосовое сообщение с текстом"""
    args = message.text.split(None, 1)[1:]
    if not args:
        await message.edit_text("Использование: `.say текст`")
        return
    text = args[0]
    await message.edit_text("🎙 генерирую голосовое...")
    audio = await text_to_speech(text)
    if audio:
        import io
        await message.delete()
        await client.send_voice(chat_id=message.chat.id, voice=io.BytesIO(audio))
    else:
        await message.edit_text("не удалось сгенерировать голосовое")

@app.on_message(filters.outgoing & filters.command("autodestruct", prefixes="."))
async def cmd_autodestruct(client: Client, message: Message):
    """Авто удаление сообщений через N секунд"""
    args = message.text.split()[1:]
    if not args:
        secs = config.get("autodestruct", 0)
        state = f"{secs} сек" if secs else "выкл"
        await message.edit_text(
            f"💣 Авто удаление: **{state}**\n"
            ".autodestruct 30 — удалять через 30 сек\n"
            ".autodestruct 0 — выключить"
        )
        return
    try:
        secs = int(args[0])
        config["autodestruct"] = secs
        save_config(config)
        if secs:
            await message.edit_text(f"💣 Авто удаление через **{secs} сек** ✅")
        else:
            await message.edit_text("💣 Авто удаление выключено ❌")
    except:
        await message.edit_text("укажи число секунд")

@app.on_message(filters.outgoing & filters.command("autostatus", prefixes="."))
async def cmd_autostatus(client: Client, message: Message):
    args = message.text.split()[1:]
    if not args:
        state = "вкл" if config.get("auto_status") else "выкл"
        await message.edit_text(
            f"⏰ авто статус: **{state}**\n.autostatus on|off\n\n"
            "Расписание:\n"
            "06-12 ☀️ Доброе утро! Онлайн\n"
            "12-17 💼 Работаю\n"
            "17-21 🌆 Вечером онлайн\n"
            "21-24 🌙 Поздно, но читаю\n"
            "00-06 😴 Сплю, напишу утром"
        )
        return
    config["auto_status"] = args[0].lower() == "on"
    save_config(config)
    if config["auto_status"]:
        await update_status(client)
    await message.edit_text(f"⏰ авто статус {'включён ✅' if config['auto_status'] else 'выключен ❌'}")

@app.on_message(filters.outgoing & filters.command("link", prefixes="."))
async def cmd_link(client: Client, message: Message):
    args = message.text.split()[1:]
    # Если ответ на сообщение со ссылкой
    if message.reply_to_message and message.reply_to_message.text:
        urls = URL_PATTERN.findall(message.reply_to_message.text)
        if urls:
            await message.edit_text("🔗 читаю ссылку...")
            summary = await summarize_url(urls[0])
            if summary:
                await message.edit_text(f"🔗 **Саммари:**\n\n{clean_text(summary)}")
            else:
                await message.edit_text("не смог прочитать ссылку")
            return
    if not args:
        state = "вкл" if config.get("link_summary") else "выкл"
        await message.edit_text(f"🔗 авто саммари ссылок: **{state}**\n.link on|off\nИли ответь на сообщение со ссылкой командой .link")
        return
    if args[0] in ("on", "off"):
        config["link_summary"] = args[0] == "on"
        save_config(config)
        await message.edit_text(f"🔗 саммари ссылок {'включено ✅' if config['link_summary'] else 'выключено ❌'}")
    else:
        # Прямая ссылка
        url = args[0]
        await message.edit_text("🔗 читаю...")
        summary = await summarize_url(url)
        if summary:
            await message.edit_text(f"🔗 **Саммари:**\n\n{clean_text(summary)}")
        else:
            await message.edit_text("не смог прочитать")

@app.on_message(filters.outgoing & filters.command("memory", prefixes="."))
async def cmd_memory(client: Client, message: Message):
    args = message.text.split()[1:]
    if not args:
        state = "вкл" if config.get("memory_on") else "выкл"
        await message.edit_text(f"память: **{state}**\n.memory on|off")
        return
    config["memory_on"] = args[0].lower() == "on"
    save_config(config)
    await message.edit_text(f"память {'включена ✅' if config['memory_on'] else 'выключена ❌'}")

@app.on_message(filters.outgoing & filters.command("people", prefixes="."))
async def cmd_people(client: Client, message: Message):
    """Память о людях"""
    if not people_memory:
        await message.edit_text("👥 Никого не помню ещё")
        return
    lines = ["👥 **Память о людях:**\n"]
    for uid, p in list(people_memory.items())[:10]:
        line = f"👤 **{p.get('name','?')}**"
        if p.get("last_mood"): line += f" | настроение: {p['last_mood']}"
        if p.get("messages_count"): line += f" | сообщений: {p['messages_count']}"
        if p.get("last_seen"): line += f"\n   📅 {p['last_seen']}"
        if p.get("notes"): line += f"\n   💬 {p['notes'][-1]}"
        lines.append(line)
    await message.edit_text("\n\n".join(lines))

@app.on_message(filters.outgoing & filters.command("schedule", prefixes="."))
async def cmd_schedule(client: Client, message: Message):
    """Расписание постов: .schedule 09:00 текст поста"""
    args = message.text.split(None, 2)[1:]
    if not args:
        posts = config.get("schedule_posts", [])
        channel = config.get("schedule_channel", "не задан")
        if not posts:
            await message.edit_text(
                f"📅 **Расписание постов**\n\n"
                f"Канал: {channel}\n"
                f"Постов: нет\n\n"
                f"Добавить: `.schedule 09:00 текст`\n"
                f"С ИИ: `.schedule 09:00 {{ai}} тема поста`\n"
                f"Задать канал: `.schedule channel @username`\n"
                f"Очистить: `.schedule clear`"
            )
        else:
            lines = [f"📅 **Канал:** {channel}\n"]
            for i, p in enumerate(posts):
                lines.append(f"{i+1}. ⏰ {p['time']} — {p['text'][:60]}")
            lines.append(f"\nОчистить: `.schedule clear`")
            await message.edit_text("\n".join(lines))
        return

    if args[0] == "clear":
        config["schedule_posts"] = []
        save_config(config)
        await message.edit_text("✅ Расписание очищено")
        return

    if args[0] == "channel" and len(args) > 1:
        channel = args[1].replace("@", "")
        config["schedule_channel"] = channel
        save_config(config)
        await message.edit_text(f"✅ Канал для постов: @{channel}")
        return

    # .schedule 09:00 текст
    if len(args) >= 2:
        time_str = args[0]
        text = args[1] if len(args) > 1 else ""
        posts = config.get("schedule_posts", [])
        posts.append({"time": time_str, "text": text, "day": "daily"})
        config["schedule_posts"] = posts
        save_config(config)
        await message.edit_text(f"✅ Пост добавлен: {time_str} — {text[:50]}")
    else:
        await message.edit_text("Формат: `.schedule 09:00 текст поста`")

@app.on_message(filters.outgoing & filters.command("mood", prefixes="."))
async def cmd_mood(client: Client, message: Message):
    """Проверить настроение последних сообщений"""
    if message.reply_to_message and message.reply_to_message.text:
        text = message.reply_to_message.text
        mood = await analyze_mood(text)
        await message.edit_text(f"🎭 Настроение: **{mood}**\n\nТекст: {text[:100]}")
    else:
        # Анализируем последние сообщения чата
        history = list(group_history[message.chat.id])[-5:]
        if not history:
            await message.edit_text("нет истории для анализа")
            return
        results = []
        for m in history:
            mood = await analyze_mood(m["text"])
            results.append(f"**{m['name']}**: {mood}")
        await message.edit_text("🎭 **Настроение в чате:**\n\n" + "\n".join(results))

@app.on_message(filters.outgoing & filters.command("summary", prefixes="."))
async def cmd_summary(client: Client, message: Message):
    """Саммари текущего диалога"""
    await message.edit_text("📝 делаю саммари...")
    summary = await auto_summarize(message.chat.id)
    if summary:
        await message.edit_text(f"📝 **Саммари диалога:**\n\n{clean_text(summary)}")
    else:
        await message.edit_text("недостаточно сообщений для саммари (нужно 20+)")

@app.on_message(filters.outgoing & filters.command("forget", prefixes="."))
async def cmd_forget(client: Client, message: Message):
    chat_memory[message.chat.id].clear()
    group_history[message.chat.id].clear()
    save_memory()
    save_history()
    await message.edit_text("память стёрта 🗑")

@app.on_message(filters.outgoing & filters.command("history", prefixes="."))
async def cmd_history(client: Client, message: Message):
    history = list(group_history[message.chat.id])[-10:]
    if not history:
        await message.edit_text("история пуста")
        return
    lines = [f"**{m['name']}** [{m['time']}]: {m['text'][:80]}" for m in history]
    await message.edit_text("**Последние 10:**\n\n" + "\n".join(lines))

@app.on_message(filters.outgoing & filters.command("status", prefixes="."))
async def cmd_status(client: Client, message: Message):
    keys = {k: "✅" if os.getenv(f"{k.upper()}_API_KEY") else "❌" for k in AI_MAP}
    s = config.get("stats", {})
    await message.edit_text(
        f"**Userbot v4.0**\n\n"
        f"ИИ: **{config['active_ai']}**\n"
        f"Groq: {keys['groq']} | Cohere: {keys['cohere']}\n"
        f"Claude: {keys['claude']} | Gemini: {keys['gemini']}\n"
        f"DeepSeek: {keys['deepseek']} | GPT: {keys['gpt']}\n\n"
        f"Память: {'✅' if config.get('memory_on') else '❌'}\n"
        f"Автоответ: {'✅' if config.get('autoreply_on') else '❌'}\n"
        f"Перевод: {'✅' if config.get('translate_on') else '❌'}\n"
        f"Голосовые: {'✅' if config.get('voice_reply') else '❌'}\n"
        f"Анализ фото: {'✅' if config.get('photo_analysis') else '❌'}\n"
        f"Упоминание: {'✅' if config.get('mention_reply') else '❌'}\n"
        f"Задержка: {config.get('antispam_delay', 6)}с\n\n"
        f"Запросов: {s.get('total', 0)} | Голос: {s.get('voice', 0)}\n"
        f"Фото: {s.get('photo', 0)} | Переводов: {s.get('translate', 0)}"
    )

@app.on_message(filters.outgoing & filters.command("help", prefixes="."))
async def cmd_help(client: Client, message: Message):
    await message.edit_text(
        "**Userbot v4.0**\n\n"
        "`+вопрос` — спросить ИИ везде\n"
        "`+вопрос` на фото — анализ фото\n\n"
        "**ИИ:**\n"
        "`.ai` groq|cohere|... — сменить ИИ\n\n"
        "**Авто ответы:**\n"
        "`.autoreply` on|off — офлайн ответ\n"
        "`.autoreply text` <текст>\n"
        "`.sticker` on|off — стикеры\n"
        "`.call` on|off — звонки\n"
        "`.mention` on|off — упоминание\n\n"
        "**Новые фичи:**\n"
        "`.spy` on|off — 🕵️ шпион удалённых\n"
        "`.autostatus` on|off — ⏰ авто bio\n"
        "`.link` on|off — 🔗 саммари ссылок\n"
        "`.link` <url> — прочитать ссылку\n\n"
        "**Прочее:**\n"
        "`.save` — сохранить в избранное\n"
        "`.voice` on|off — голосовые\n"
        "`.translate` on|off — перевод\n"
        "`.photo` on|off — анализ фото\n"
        "`.delay` <сек> — антиспам\n"
        "`.memory` on|off — память\n"
        "`.forget` — стереть память\n"
        "`.history` — история чата\n"
        "`.status` — статус\n"
        "`.help` — эта справка"
    )

# ══════════════════════════ ЗАПУСК ════════════════════════════════════
if __name__ == "__main__":
    if not API_ID or not API_HASH or not SESSION_STRING:
        log.error("API_ID, API_HASH или SESSION_STRING не заданы!")
        exit(1)

    async def main():
        await app.start()
        log.info("😈 Userbot v5.0 запущен!")
        await update_status(app)
        asyncio.create_task(auto_status_loop(app))
        # Расписание постов
        channel = config.get("schedule_channel", "")
        posts = config.get("schedule_posts", [])
        if channel and posts:
            asyncio.create_task(schedule_loop(app, channel, posts))
            log.info(f"📅 Расписание: {len(posts)} постов → {channel}")
        await idle()
        await app.stop()

    app.run(main())
