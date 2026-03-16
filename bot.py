"""
AI Telegram Bot v4.0 — ЧИСТАЯ ВЕРСИЯ
Только рабочие команды + новые фичи
Админ: 7750512181
"""

import os
import logging
import json
import aiohttp
import random
import asyncio
import uuid
from collections import defaultdict, deque
from datetime import datetime
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent, ReactionTypeEmoji
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters, InlineQueryHandler
from telegram.request import HTTPXRequest

# ══════════════════════════ ENV ══════════════════════════════════════
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

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
COHERE_API_KEY     = os.getenv("COHERE_API_KEY", "")
CLAUDE_API_KEY     = os.getenv("CLAUDE_API_KEY", "")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY   = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")
MISTRAL_API_KEY    = os.getenv("MISTRAL_API_KEY", "")
TOGETHER_API_KEY   = os.getenv("TOGETHER_API_KEY", "")
HF_API_KEY         = os.getenv("HF_API_KEY", "")

CONFIG_FILE = "config.json"
MEMORY_FILE = "memory.json"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", level=logging.INFO)
log = logging.getLogger("AIBot")

# ══════════════════════════ АДМИН ════════════════════════════════════
ADMIN_IDS = [7750512181] + [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

def is_admin(update) -> bool:
    user = update.effective_user
    return user and user.id in ADMIN_IDS

def admin_only(func):
    async def wrapper(update, ctx):
        if not is_admin(update):
            await update.message.reply_text("⛔ Нет доступа")
            return
        return await func(update, ctx)
    return wrapper

# ══════════════════════════ ПРОМПТЫ ══════════════════════════════════
SYSTEM_PROMPT = """Ты — умный, точный и серьёзный ассистент.

Правила:
- Отвечаешь только правдиво и точно — никакой выдумки
- Если не знаешь — честно говоришь "не знаю" или "не уверен"
- Отвечаешь кратко и по делу — без воды и лишних слов
- Только русский язык
- Никаких шуток, сарказма, характера — только факты
- Если вопрос сложный — структурируй ответ чётко
- Никогда не говоришь что ты ИИ если не спрашивают"""

# ══════════════════════════ КОНФИГ ═══════════════════════════════════
def load_config() -> dict:
    default = {
        "active_ai": "groq",
        "trigger": "+",
        "memory_on": True,
        "memory_depth": 8,
        "react_on": True,
        "antispam_sec": 3,
        "banned_users": [],
        "stats": {"total": 0, "groq": 0, "cohere": 0, "claude": 0, "gemini": 0, "deepseek": 0, "gpt": 0},
        "top_users": {},
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                default.update(json.load(f))
            except: pass
    return default

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

config = load_config()

# ══════════════════════════ ПАМЯТЬ ═══════════════════════════════════
chat_memory: dict = defaultdict(lambda: deque(maxlen=20))

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                for cid, msgs in json.load(f).items():
                    chat_memory[int(cid)] = deque(msgs, maxlen=20)
        except: pass

def save_memory():
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): list(v) for k, v in chat_memory.items()}, f, ensure_ascii=False)

load_memory()

# ══════════════════════════ АНТИСПАМ ═════════════════════════════════
last_request: dict = {}

def is_spam(user_id: int) -> bool:
    delay = config.get("antispam_sec", 3)
    now = datetime.now()
    last = last_request.get(user_id)
    if last and (now - last).total_seconds() < delay:
        return True
    last_request[user_id] = now
    return False

# ══════════════════════════ AI КЛИЕНТЫ ═══════════════════════════════
async def ask_groq(messages, system):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    body = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system}] + messages, "max_tokens": 600}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.groq.com/openai/v1/chat/completions", json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200: raise Exception(f"Groq {r.status}: {data.get('error', {}).get('message', data)}")
            return data["choices"][0]["message"]["content"]

async def ask_cohere(messages, system):
    headers = {"Authorization": f"Bearer {COHERE_API_KEY}", "Content-Type": "application/json"}
    chat_history = [{"role": "USER" if m["role"] == "user" else "CHATBOT", "message": m["content"]} for m in messages[:-1]]
    body = {"model": "command-r-plus-08-2024", "message": messages[-1]["content"] if messages else "привет", "preamble": system, "chat_history": chat_history, "max_tokens": 600}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.cohere.com/v1/chat", json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200: raise Exception(f"Cohere {r.status}: {data.get('message', data)}")
            return data["text"]

async def ask_claude(messages, system):
    headers = {"x-api-key": CLAUDE_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    body = {"model": "claude-opus-4-5", "max_tokens": 600, "system": system, "messages": messages}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.anthropic.com/v1/messages", json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200: raise Exception(f"Claude {r.status}: {data.get('error', {}).get('message', data)}")
            return data["content"][0]["text"]

async def ask_gemini(messages, system):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    contents = [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]} for m in messages]
    body = {"system_instruction": {"parts": [{"text": system}]}, "contents": contents}
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=body, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200: raise Exception(f"Gemini {r.status}: {data}")
            return data["candidates"][0]["content"]["parts"][0]["text"]

async def ask_deepseek(messages, system):
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    body = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system}] + messages, "max_tokens": 600}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.deepseek.com/v1/chat/completions", json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200: raise Exception(f"DeepSeek {r.status}: {data}")
            return data["choices"][0]["message"]["content"]

async def ask_gpt(messages, system):
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {"model": "gpt-4o-mini", "messages": [{"role": "system", "content": system}] + messages, "max_tokens": 600}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.openai.com/v1/chat/completions", json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200: raise Exception(f"GPT {r.status}: {data.get('error', {}).get('message', data)}")
            return data["choices"][0]["message"]["content"]

async def ask_mistral(messages, system):
    if not MISTRAL_API_KEY: raise Exception("MISTRAL_API_KEY не задан")
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    body = {"model": "mistral-small-latest", "messages": [{"role": "system", "content": system}] + messages, "max_tokens": 600}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.mistral.ai/v1/chat/completions", json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200: raise Exception(f"Mistral {r.status}: {data.get('message', data)}")
            return data["choices"][0]["message"]["content"]

async def ask_together(messages, system):
    if not TOGETHER_API_KEY: raise Exception("TOGETHER_API_KEY не задан")
    headers = {"Authorization": f"Bearer {TOGETHER_API_KEY}", "Content-Type": "application/json"}
    body = {"model": "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo", "messages": [{"role": "system", "content": system}] + messages, "max_tokens": 600}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.together.xyz/v1/chat/completions", json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200: raise Exception(f"Together {r.status}: {data.get('error', {}).get('message', data)}")
            return data["choices"][0]["message"]["content"]

async def ask_huggingface(messages, system):
    if not HF_API_KEY: raise Exception("HF_API_KEY не задан")
    headers = {"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"}
    prompt = f"{system}\n\n" + "\n".join([f"{'Пользователь' if m['role']=='user' else 'Ассистент'}: {m['content']}" for m in messages]) + "\nАссистент:"
    body = {"inputs": prompt, "parameters": {"max_new_tokens": 500, "return_full_text": False}}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3", json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as r:
            data = await r.json()
            if r.status != 200: raise Exception(f"HF {r.status}: {data}")
            if isinstance(data, list): return data[0].get("generated_text", "").strip()
            raise Exception(f"HF unexpected: {data}")

AI_MAP = {
    "groq": ask_groq, "cohere": ask_cohere, "claude": ask_claude,
    "gemini": ask_gemini, "deepseek": ask_deepseek, "gpt": ask_gpt,
    "mistral": ask_mistral, "together": ask_together,
    "huggingface": ask_huggingface, "hf": ask_huggingface,
}

async def ensemble_request_bot(question: str, messages: list, system: str) -> str:
    """3 ИИ отвечают одновременно → Groq судит"""
    FIGHTERS = [
        ("groq",     ask_groq),
        ("cohere",   ask_cohere),
        ("mistral",  ask_mistral),
        ("together", ask_together),
    ]
    available = [(n, f) for n, f in FIGHTERS if os.getenv(f"{n.upper()}_API_KEY", "")]
    if len(available) < 2:
        fn = available[0][1] if available else ask_groq
        return await fn(messages, system)

    fighters = available[:3]
    results = await asyncio.gather(*[fn(messages, system) for _, fn in fighters], return_exceptions=True)
    answers = [{"ai": fighters[i][0], "text": r} for i, r in enumerate(results) if not isinstance(r, Exception) and r]

    if not answers:
        raise Exception("Все ИИ не ответили")
    if len(answers) == 1:
        return answers[0]["text"]

    judge_prompt = """Ты судья. Выбери ЛУЧШИЙ ответ из нескольких — самый точный и полезный.
Верни ТОЛЬКО текст лучшего ответа без изменений."""
    answers_text = "\n\n".join([f"[{a['ai'].upper()}]: {a['text']}" for a in answers])
    try:
        best = await ask_groq(
            [{"role": "user", "content": f"Вопрос: {question}\n\nОтветы:\n{answers_text}"}],
            judge_prompt
        )
        return best.strip()
    except:
        return answers[0]["text"]


async def ai_request(question, system=None, chat_id=None, use_memory=True):
    sys_prompt = system or SYSTEM_PROMPT
    if use_memory and chat_id and config.get("memory_on"):
        chat_memory[chat_id].append({"role": "user", "content": question})
        messages = list(chat_memory[chat_id])[-config.get("memory_depth", 8):]
    else:
        messages = [{"role": "user", "content": question}]

    # Ensemble mode — всегда включён
    answer = await ensemble_request_bot(question, messages, sys_prompt)

    if use_memory and chat_id and config.get("memory_on"):
        chat_memory[chat_id].append({"role": "assistant", "content": answer})
        save_memory()
    config["stats"]["total"] = config["stats"].get("total", 0) + 1
    save_config(config)
    return answer

# ══════════════════════════ ХЕЛПЕРЫ ══════════════════════════════════
REACTIONS_LIST = ["🔥", "👀", "🤔", "😂", "💀", "👍", "🤡", "😈", "⚡"]
THINKING = ["думаю...", "ща...", "соображаю", "хм...", "погоди", "обрабатываю"]
EMPTY_TRIGGER = ["и? вопрос где?", "плюсик поставил, молодец. дальше?", "стесняешься?", "жду продолжения"]
SPAM_PHRASES = ["не части", "подожди немного", "охолони"]

async def set_reaction(msg):
    if not config.get("react_on"): return
    try: await msg.set_reaction([ReactionTypeEmoji(random.choice(REACTIONS_LIST))])
    except: pass

def update_user_stats(uid):
    config["top_users"][str(uid)] = config["top_users"].get(str(uid), 0) + 1
    save_config(config)

# ══════════════════════════ ОСНОВНОЙ ХЕНДЛЕР ═════════════════════════
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text: return
    text = msg.text.strip()
    trigger = config.get("trigger", "+")

    # Автоответ на упоминание
    if ctx.bot.username and f"@{ctx.bot.username}" in text:
        question = text.replace(f"@{ctx.bot.username}", "").strip() or "что скажешь?"
        await set_reaction(msg)
        thinking = await msg.reply_text(random.choice(THINKING))
        try:
            answer = await ai_request(question, chat_id=msg.chat_id)
            await thinking.edit_text(answer)
        except Exception as e:
            await thinking.edit_text(f"сломался: {str(e)[:100]}")
        return

    if not text.startswith(trigger): return
    question = text[len(trigger):].strip()
    if not question:
        await msg.reply_text(random.choice(EMPTY_TRIGGER))
        return

    uid = msg.from_user.id
    if uid in config.get("banned_users", []): return
    if is_spam(uid):
        await msg.reply_text(random.choice(SPAM_PHRASES))
        return

    await set_reaction(msg)
    thinking = await msg.reply_text(random.choice(THINKING))
    try:
        answer = await ai_request(question, chat_id=msg.chat_id)
        update_user_stats(uid)
        await thinking.edit_text(answer)
    except Exception as e:
        log.error(f"AI Error: {e}")
        await thinking.edit_text(f"сломалось: {str(e)[:100]}")

# ══════════════════════════ INLINE ═══════════════════════════════════
async def handle_inline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query
    if not query: return
    q = query.query.strip()
    if len(q) < 2: return
    try:
        answer = await ai_request(q, use_memory=False)
        results = [InlineQueryResultArticle(id=str(uuid.uuid4()), title=f"🤖 {q[:40]}", description=answer[:100], input_message_content=InputTextMessageContent(answer))]
        await query.answer(results, cache_time=10)
    except: pass

# ══════════════════════════ КОМАНДЫ ══════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("👋 Пиши `+вопрос` чтобы спросить ИИ.", parse_mode="Markdown")
        return
    await update.message.reply_text(
        f"*🤖 AI Bot v5.0 — Полная панель*\n\n"
        f"ИИ: *{config['active_ai']}* (Ensemble: 3 ИИ + судья)\n\n"

        "━━━━ 🤖 БОТ (группы) ━━━━\n"
        "`+вопрос` — спросить ИИ\n"
        "`/ai` groq|cohere|mistral|together|hf|claude|gemini|gpt\n"
        "`/ask` <вопрос> — без триггера\n"
        "`/joke` — анекдот 😂\n"
        "`/fact` — интересный факт 🧠\n"
        "`/quiz` — викторина с голосованием ❓\n"
        "`/coin` — орёл/решка 🪙\n"
        "`/dice` — кубик 🎲\n"
        "`/memory` on|off — память\n"
        "`/forget` — стереть память\n"
        "`/react` on|off — реакции\n"
        "`/ban` <id> | `/unban` <id>\n"
        "`/broadcast` <текст> — рассылка\n"
        "`/stats` — статистика\n"
        "`/top` — топ юзеров\n"
        "`/status` — статус ключей\n\n"

        "━━━━ 👤 USERBOT (везде) ━━━━\n"
        "*Триггер `+` — пишешь в любом чате:*\n"
        "`+вопрос` — ИИ отвечает (3 ИИ + судья)\n"
        "`+` на reply — ответить на чужое смс\n"
        "`+нарисуй кот` — генерация картинки 🎨\n"
        "`+найди котики` — поиск в Google 🔍\n"
        "`+погода Ташкент` — погода 🌤\n"
        "`+новости` — последние новости 📰\n"
        "`+кто такой Паштет` — инфо о юзере 👤\n"
        "`+скопировать 20` — скопировать смс 📋\n"
        "`+скачай` — скачать медиа ⬇️\n"
        "`+дайджест` — обзор всех чатов 📖\n"
        "`+send @chat текст` — отправить смс 📤\n"
        "`+заблокируй @user` — блокировка 🚫\n"
        "`+создай группу Название` — новая группа 👥\n"
        "`+пересылай @target` — авто пересылка 🔄\n"
        "`+удали чат` — удалить/покинуть чат 🗑\n"
        "`+удали 10 смс` — удалить свои смс\n"
        "`+сохрани мои данные` — в избранное 💾\n\n"

        "━━━━ ⚙️ НАСТРОЙКИ ━━━━\n"
        "*Пишешь себе в избранное:*\n"
        "`.autoreply on|off` — автоответ в личке\n"
        "`.spy on|off` — 🕵️ шпион удалённых\n"
        "`.react on|off` — авто реакции\n"
        "`.join on|off` — авто вступление в разговор\n"
        "`.autostatus on|off` — авто bio\n"
        "`.translate on|off` — авто перевод\n"
        "`.voice on|off` — голосовые → текст\n"
        "`.photo on|off` — анализ фото\n"
        "`.doc on|off` — анализ PDF/Word\n"
        "`.link on|off` — саммари ссылок\n"
        "`.schedule 09:00 текст` — пост в канал 📅\n"
        "`.schedule channel @канал`\n"
        "`.people` — память о людях 🧠\n"
        "`.mood` — анализ настроения 🎭\n"
        "`.summary` — саммари диалога 📝\n"
        "`.status` — полный статус\n"
        "`.help` — все команды\n\n"

        "━━━━ 🎛 УПРАВЛЕНИЕ ━━━━\n"
        "`/ub` — управление userbot\n"
        "`/ub autoreply on` — автоответ\n"
        "`/ub spy on` — шпион\n"
        "`/ub react on` — реакции\n"
        "`/ub join on` — авто вступление\n"
        "`/ub translate on` — перевод\n"
        "`/ub voice on` — голосовые\n"
        "`/ub ai mistral` — сменить ИИ\n"
        "`/ub delay 7` — задержка антиспама",
        parse_mode="Markdown"
    )

@admin_only
async def cmd_ai(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(f"сейчас: *{config['active_ai']}*\n/ai groq|cohere|claude|gemini|deepseek|gpt", parse_mode="Markdown")
        return
    ai = ctx.args[0].lower()
    if ai not in AI_MAP:
        await update.message.reply_text("некорректно. groq, cohere, claude, gemini, deepseek или gpt")
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
    await update.message.reply_text(f"переключился на *{desc.get(ai, ai)}* ✅", parse_mode="Markdown")

async def cmd_ask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("использование: /ask <вопрос>")
        return
    question = " ".join(ctx.args)
    thinking = await update.message.reply_text(random.choice(THINKING))
    try:
        answer = await ai_request(question, chat_id=update.message.chat_id)
        await thinking.edit_text(answer)
    except Exception as e:
        await thinking.edit_text(f"ошибка: {str(e)[:100]}")

async def cmd_joke(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    thinking = await update.message.reply_text("💀 загружаю...")
    try:
        answer = await ai_request("Расскажи один короткий хакерский анекдот или тёмную IT шутку на русском. Только шутка без предисловий.", use_memory=False)
        await thinking.edit_text(f"💀 {answer}")
    except Exception as e:
        await thinking.edit_text(f"ошибка: {str(e)[:100]}")

async def cmd_fact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    thinking = await update.message.reply_text("🔍 сканирую базу...")
    try:
        answer = await ai_request("Расскажи один интересный малоизвестный факт про хакеров, кибербезопасность или IT на русском. Коротко, 2-3 предложения.", use_memory=False)
        await thinking.edit_text(f"[+] {answer}")
    except Exception as e:
        await thinking.edit_text(f"ошибка: {str(e)[:100]}")

async def cmd_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    thinking = await update.message.reply_text("❓ готовлю вопрос...")
    try:
        # Просим ИИ вернуть структурированный JSON
        prompt = """Придумай вопрос викторины. Верни ТОЛЬКО JSON без markdown:
{"question": "вопрос", "options": ["вариант1", "вариант2", "вариант3", "вариант4"], "correct": 0}
correct — индекс правильного ответа (0-3). Только JSON, без пояснений."""
        raw = await ai_request(prompt, use_memory=False)
        # Убираем markdown если есть
        raw = raw.replace("```json", "").replace("```", "").strip()
        import json as _json
        data = _json.loads(raw)
        question = data["question"]
        options = data["options"]
        correct = int(data["correct"])
        await thinking.delete()
        # Отправляем как Telegram Poll
        await update.message.reply_poll(
            question=f"❓ {question}",
            options=options,
            type="quiz",
            correct_option_id=correct,
            is_anonymous=False,
            explanation=f"Правильный ответ: {options[correct]}"
        )
    except Exception as e:
        # Если не удалось — текстовый формат
        try:
            answer = await ai_request("Придумай один интересный вопрос викторины с 4 вариантами ответа (А, Б, В, Г) и укажи правильный. На русском.", use_memory=False)
            await thinking.edit_text(f"❓ {answer}")
        except Exception as e2:
            await thinking.edit_text(f"ошибка: {str(e2)[:100]}")

async def cmd_coin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    result = random.choice(["🦅 Орёл!", "🔵 Решка!"])
    await update.message.reply_text(f"🪙 Бросаю монету...\n\n{result}")

async def cmd_dice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    result = random.randint(1, 6)
    faces = ["", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]
    await update.message.reply_text(f"🎲 Бросаю кубик...\n\n{faces[result]} — выпало {result}!")

@admin_only
async def cmd_memory(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        state = "вкл" if config.get("memory_on") else "выкл"
        await update.message.reply_text(f"память: *{state}*\n/memory on|off", parse_mode="Markdown")
        return
    config["memory_on"] = ctx.args[0].lower() == "on"
    save_config(config)
    await update.message.reply_text(f"память {'включена ✅' if config['memory_on'] else 'выключена ❌'}")

@admin_only
async def cmd_forget(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_memory[update.message.chat_id].clear()
    save_memory()
    await update.message.reply_text("память стёрта 🗑")

@admin_only
async def cmd_react(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        state = "вкл" if config.get("react_on") else "выкл"
        await update.message.reply_text(f"реакции: *{state}*\n/react on|off", parse_mode="Markdown")
        return
    config["react_on"] = ctx.args[0].lower() == "on"
    save_config(config)
    await update.message.reply_text(f"реакции {'включены ✅' if config['react_on'] else 'выключены ❌'}")

@admin_only
async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        banned = config.get("banned_users", [])
        await update.message.reply_text("Забаненные:\n" + "\n".join([f"`{u}`" for u in banned]) if banned else "забаненных нет", parse_mode="Markdown")
        return
    try: uid = int(ctx.args[0])
    except: await update.message.reply_text("некорректный ID"); return
    banned = config.get("banned_users", [])
    if uid not in banned:
        banned.append(uid)
        config["banned_users"] = banned
        save_config(config)
    await update.message.reply_text(f"🚫 `{uid}` забанен", parse_mode="Markdown")

@admin_only
async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args: await update.message.reply_text("использование: /unban <id>"); return
    try: uid = int(ctx.args[0])
    except: await update.message.reply_text("некорректный ID"); return
    banned = config.get("banned_users", [])
    if uid in banned:
        banned.remove(uid)
        config["banned_users"] = banned
        save_config(config)
    await update.message.reply_text(f"✅ `{uid}` разбанен", parse_mode="Markdown")

@admin_only
async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args: await update.message.reply_text("использование: /broadcast <текст>"); return
    text = " ".join(ctx.args)
    sent = failed = 0
    for uid_str in config.get("top_users", {}):
        try:
            await ctx.bot.send_message(chat_id=int(uid_str), text=f"📢 {text}")
            sent += 1
            await asyncio.sleep(0.1)
        except: failed += 1
    await update.message.reply_text(f"📢 Готово\nОтправлено: {sent} | Ошибок: {failed}")

@admin_only
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = config.get("stats", {})
    total = s.get("total", 0)
    comment = "🔥 неплохо" if total > 100 else ("разгоняемся" if total > 20 else "👶 только начали")
    await update.message.reply_text(
        f"📊 *Статистика*\n\n"
        f"Всего: *{total}* — {comment}\n"
        f"🆓 Groq: {s.get('groq', 0)}\n"
        f"🆓 Cohere: {s.get('cohere', 0)}\n"
        f"🧠 Claude: {s.get('claude', 0)}\n"
        f"✨ Gemini: {s.get('gemini', 0)}\n"
        f"🔮 DeepSeek: {s.get('deepseek', 0)}\n"
        f"🤖 GPT: {s.get('gpt', 0)}\n"
        f"🚫 Забанено: {len(config.get('banned_users', []))}",
        parse_mode="Markdown"
    )

@admin_only
async def cmd_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    top = config.get("top_users", {})
    if not top: await update.message.reply_text("пока никого нет"); return
    sorted_top = sorted(top.items(), key=lambda x: x[1], reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"] + ["👤"] * 10
    lines = [f"{medals[i]} `{uid}` — {cnt}" for i, (uid, cnt) in enumerate(sorted_top)]
    await update.message.reply_text("*Топ:*\n" + "\n".join(lines), parse_mode="Markdown")

@admin_only
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keys = {k: "✅" if os.getenv(f"{k.upper()}_API_KEY") else "❌" for k in ["groq","cohere","claude","gemini","deepseek","gpt","mistral","together"]}
    keys["huggingface"] = "✅" if HF_API_KEY else "❌"
    await update.message.reply_text(
        f"*🔧 Статус*\n\n"
        f"ИИ: *{config['active_ai']}*\n"
        f"🆓 Groq: {keys['groq']} | Cohere: {keys['cohere']}\n"
        f"🆓 Mistral: {keys['mistral']} | Together: {keys['together']}\n"
        f"🆓 HuggingFace: {keys['huggingface']}\n"
        f"🧠 Claude: {keys['claude']} | Gemini: {keys['gemini']}\n"
        f"🔮 DeepSeek: {keys['deepseek']} | GPT: {keys['gpt']}\n\n"
        f"Триггер: `{config['trigger']}`\n"
        f"Память: {'✅' if config.get('memory_on') else '❌'}\n"
        f"Реакции: {'✅' if config.get('react_on') else '❌'}",
        parse_mode="Markdown"
    )

USERBOT_CONFIG = "userbot_config.json"

def load_userbot_config() -> dict:
    if os.path.exists(USERBOT_CONFIG):
        try:
            with open(USERBOT_CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_userbot_config(cfg: dict):
    with open(USERBOT_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

@admin_only
async def cmd_ub(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Управление userbot через бота"""
    ucfg = load_userbot_config()
    if not ctx.args:
        await update.message.reply_text(
            f"*👤 Userbot управление*\n\n"
            f"ИИ: *{ucfg.get('active_ai', 'groq')}*\n"
        f"🆓 Groq: {'✅' if os.getenv('GROQ_API_KEY') else '❌'} | Cohere: {'✅' if os.getenv('COHERE_API_KEY') else '❌'}\n"
        f"🆓 Mistral: {'✅' if MISTRAL_API_KEY else ' ❌'} | Together: {'✅' if TOGETHER_API_KEY else '❌'}\n"
        f"🆓 HuggingFace: {'✅' if HF_API_KEY else '❌'}\n"
            f"Автоответ: {'✅' if ucfg.get('autoreply_on') else '❌'}\n"
        f"📱 Авто ответ на все лички: {'✅' if ucfg.get('pm_autoreply') else '❌'}\n"
            f"Голосовые: {'✅' if ucfg.get('voice_reply', True) else '❌'}\n"
            f"Перевод: {'✅' if ucfg.get('translate_on', True) else '❌'}\n"
            f"Фото: {'✅' if ucfg.get('photo_analysis', True) else '❌'}\n"
            f"📄 Документы: {'✅' if ucfg.get('doc_analysis', True) else '❌'}\n"
            f"Стикеры: {'✅' if ucfg.get('sticker_reply', True) else '❌'}\n"
            f"Упоминание: {'✅' if ucfg.get('mention_reply', True) else '❌'}\n"
            f"Звонки: {'✅' if ucfg.get('call_reply', True) else '❌'}\n"
            f"⚡ Авто реакции: {'✅' if ucfg.get('auto_react') else '❌'}\n"
            f"🕵️ Шпион: {'✅' if ucfg.get('spy_mode') else '❌'}\n"
            f"⏰ Авто статус: {'✅' if ucfg.get('auto_status') else '❌'}\n"
            f"🔗 Саммари ссылок: {'✅' if ucfg.get('link_summary', True) else '❌'}\n"
            f"💬 Авто вступление: {'✅' if ucfg.get('auto_join') else '❌'}\n"
            f"Задержка: {ucfg.get('antispam_delay', 6)}с\n\n"
            "*Команды:*\n"
            "`/ub ai` groq|cohere|mistral|together|hf|claude|gemini|gpt\n"
            "`/ub autoreply` on|off\n"
            "`/ub voice` on|off\n"
            "`/ub translate` on|off\n"
            "`/ub photo` on|off\n"
            "`/ub doc` on|off\n"
            "`/ub sticker` on|off\n"
            "`/ub mention` on|off\n"
            "`/ub call` on|off\n"
            "`/ub react` on|off\n"
            "`/ub spy` on|off\n"
            "`/ub autostatus` on|off\n"
            "`/ub link` on|off\n"
            "`/ub join` on|off\n"
            "`/ub join_interval` <сек>\n"
            "`/ub join_messages` <кол-во>\n"
            "`/ub delay` <сек>",
            parse_mode="Markdown"
        )
        return

    cmd = ctx.args[0].lower()
    val = ctx.args[1].lower() if len(ctx.args) > 1 else None

    BOOL_CMDS = {
        "autoreply":  "autoreply_on",
        "pmreply":    "pm_autoreply",
        "voice":      "voice_reply",
        "translate":  "translate_on",
        "photo":      "photo_analysis",
        "doc":        "doc_analysis",
        "sticker":    "sticker_reply",
        "mention":    "mention_reply",
        "call":       "call_reply",
        "react":      "auto_react",
        "spy":        "spy_mode",
        "autostatus": "auto_status",
        "link":       "link_summary",
        "join":       "auto_join",
    }

    BOOL_LABELS = {
        "autoreply":  "Автоответ",
        "voice":      "Голосовые",
        "translate":  "Перевод",
        "photo":      "Фото",
        "doc":        "📄 Документы",
        "sticker":    "Стикеры",
        "mention":    "Упоминание",
        "call":       "Звонки",
        "react":      "⚡ Авто реакции",
        "spy":        "🕵️ Шпион",
        "autostatus": "⏰ Авто статус",
        "link":       "🔗 Саммари ссылок",
        "join":       "💬 Авто вступление",
    }

    if cmd in BOOL_CMDS and val in ("on", "off"):
        ucfg[BOOL_CMDS[cmd]] = val == "on"
        save_userbot_config(ucfg)
        label = BOOL_LABELS.get(cmd, cmd)
        await update.message.reply_text(f"✅ {label} {'включён' if val == 'on' else 'выключен'}")
    elif cmd == "ai" and val:
        ucfg["active_ai"] = val
        save_userbot_config(ucfg)
        await update.message.reply_text(f"✅ Userbot ИИ → *{val}*", parse_mode="Markdown")
    elif cmd == "delay" and val:
        try:
            ucfg["antispam_delay"] = int(val)
            save_userbot_config(ucfg)
            await update.message.reply_text(f"✅ Задержка → {val}с")
        except:
            await update.message.reply_text("укажи число секунд")
    elif cmd == "join_interval" and val:
        try:
            ucfg["auto_join_interval"] = int(val)
            save_userbot_config(ucfg)
            await update.message.reply_text(f"✅ Интервал вступления → {val}с")
        except:
            await update.message.reply_text("укажи число секунд")
    elif cmd == "join_messages" and val:
        try:
            ucfg["auto_join_messages"] = int(val)
            save_userbot_config(ucfg)
            await update.message.reply_text(f"✅ Мин. сообщений → {val}")
        except:
            await update.message.reply_text("укажи число")
    else:
        await update.message.reply_text("неизвестная команда. напиши /ub для списка")

# ══════════════════════════ ЗАПУСК ════════════════════════════════════
def main():
    if not TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN не задан!")
        return
    request = HTTPXRequest(connect_timeout=30, read_timeout=30, write_timeout=30, pool_timeout=30)
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).build()

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("ai",        cmd_ai))
    app.add_handler(CommandHandler("ask",       cmd_ask))
    app.add_handler(CommandHandler("joke",      cmd_joke))
    app.add_handler(CommandHandler("fact",      cmd_fact))
    app.add_handler(CommandHandler("quiz",      cmd_quiz))
    app.add_handler(CommandHandler("coin",      cmd_coin))
    app.add_handler(CommandHandler("dice",      cmd_dice))
    app.add_handler(CommandHandler("memory",    cmd_memory))
    app.add_handler(CommandHandler("forget",    cmd_forget))
    app.add_handler(CommandHandler("react",     cmd_react))
    app.add_handler(CommandHandler("ban",       cmd_ban))
    app.add_handler(CommandHandler("unban",     cmd_unban))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("stats",     cmd_stats))
    app.add_handler(CommandHandler("top",       cmd_top))
    app.add_handler(CommandHandler("status",    cmd_status))
    app.add_handler(CommandHandler("ub",        cmd_ub))
    app.add_handler(InlineQueryHandler(handle_inline))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info(f"🚀 Bot v4.0 запущен! Админ: {ADMIN_IDS}")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
