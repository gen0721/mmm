"""
🤖 AI — Провайдеры искусственного интеллекта
Groq, Gemini, Claude, GPT, Mistral, Together, HuggingFace, Polza.ai
"""

import asyncio
import logging
import aiohttp
from typing import Callable

log = logging.getLogger("AI")


async def ask_groq(messages: list, system: str) -> str:
    from bot.config import GROQ_API_KEY
    if not GROQ_API_KEY:
        raise Exception("GROQ_API_KEY не задан")
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "system", "content": system}] + messages,
        "max_tokens": 1000, "temperature": 0.7,
    }
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.groq.com/openai/v1/chat/completions",
                          json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"Groq {r.status}: {data.get('error', {}).get('message', data)}")
            return data["choices"][0]["message"]["content"]


async def ask_gemini(messages: list, system: str) -> str:
    from bot.config import GEMINI_API_KEY
    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY не задан")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    parts = [{"text": f"System: {system}\n\n"}]
    for m in messages:
        parts.append({"text": f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}\n"})
    body = {"contents": [{"parts": parts}], "generationConfig": {"maxOutputTokens": 1000}}
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=body, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"Gemini {r.status}: {data}")
            return data["candidates"][0]["content"]["parts"][0]["text"]


async def ask_claude(messages: list, system: str) -> str:
    from bot.config import CLAUDE_API_KEY
    if not CLAUDE_API_KEY:
        raise Exception("CLAUDE_API_KEY не задан")
    headers = {"x-api-key": CLAUDE_API_KEY, "Content-Type": "application/json",
               "anthropic-version": "2023-06-01"}
    body = {"model": "claude-3-haiku-20240307", "max_tokens": 1000,
            "system": system, "messages": messages}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.anthropic.com/v1/messages",
                          json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"Claude {r.status}: {data}")
            return data["content"][0]["text"]


async def ask_deepseek(messages: list, system: str) -> str:
    from bot.config import DEEPSEEK_API_KEY
    if not DEEPSEEK_API_KEY:
        raise Exception("DEEPSEEK_API_KEY не задан")
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    body = {"model": "deepseek-chat",
            "messages": [{"role": "system", "content": system}] + messages, "max_tokens": 1000}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.deepseek.com/v1/chat/completions",
                          json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"DeepSeek {r.status}: {data}")
            return data["choices"][0]["message"]["content"]


async def ask_gpt(messages: list, system: str) -> str:
    from bot.config import OPENAI_API_KEY
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY не задан")
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {"model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": system}] + messages, "max_tokens": 1000}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.openai.com/v1/chat/completions",
                          json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"GPT {r.status}: {data}")
            return data["choices"][0]["message"]["content"]


async def ask_mistral(messages: list, system: str) -> str:
    from bot.config import MISTRAL_API_KEY
    if not MISTRAL_API_KEY:
        raise Exception("MISTRAL_API_KEY не задан")
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    body = {"model": "mistral-small-latest",
            "messages": [{"role": "system", "content": system}] + messages, "max_tokens": 1000}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.mistral.ai/v1/chat/completions",
                          json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"Mistral {r.status}: {data}")
            return data["choices"][0]["message"]["content"]


async def ask_cohere(messages: list, system: str) -> str:
    from bot.config import COHERE_API_KEY
    if not COHERE_API_KEY:
        raise Exception("COHERE_API_KEY не задан")
    headers = {"Authorization": f"Bearer {COHERE_API_KEY}", "Content-Type": "application/json"}
    chat_history = []
    for m in messages[:-1]:
        role = "USER" if m["role"] == "user" else "CHATBOT"
        chat_history.append({"role": role, "message": m["content"]})
    body = {"model": "command-r-plus",
            "message": messages[-1]["content"] if messages else "",
            "chat_history": chat_history, "preamble": system, "max_tokens": 1000}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.cohere.ai/v1/chat",
                          json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"Cohere {r.status}: {data}")
            return data["text"]


async def ask_together(messages: list, system: str) -> str:
    from bot.config import TOGETHER_API_KEY
    if not TOGETHER_API_KEY:
        raise Exception("TOGETHER_API_KEY не задан")
    headers = {"Authorization": f"Bearer {TOGETHER_API_KEY}", "Content-Type": "application/json"}
    body = {"model": "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
            "messages": [{"role": "system", "content": system}] + messages, "max_tokens": 500}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.together.xyz/v1/chat/completions",
                          json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"Together {r.status}: {data}")
            return data["choices"][0]["message"]["content"]


async def ask_huggingface(messages: list, system: str) -> str:
    from bot.config import HF_API_KEY
    if not HF_API_KEY:
        raise Exception("HF_API_KEY не задан")
    headers = {"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"}
    prompt = f"{system}\n\n"
    for m in messages:
        role = "Пользователь" if m["role"] == "user" else "Ассистент"
        prompt += f"{role}: {m['content']}\n"
    prompt += "Ассистент:"
    body = {"inputs": prompt, "parameters": {"max_new_tokens": 500, "return_full_text": False}}
    async with aiohttp.ClientSession() as s:
        async with s.post(
            "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3",
            json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as r:
            data = await r.json()
            if r.status != 200:
                raise Exception(f"HuggingFace {r.status}: {data}")
            if isinstance(data, list):
                return data[0].get("generated_text", "").strip()
            raise Exception(f"HF unexpected: {data}")


async def ask_polza(messages: list, system: str, model: str = None) -> str:
    """Polza.ai — российский агрегатор 400+ моделей. Оплата рублями, без VPN."""
    from bot.config import POLZA_API_KEY, POLZA_MODEL
    if not POLZA_API_KEY:
        raise Exception("POLZA_API_KEY не задан")
    use_model = model or POLZA_MODEL
    headers = {"Authorization": f"Bearer {POLZA_API_KEY}", "Content-Type": "application/json"}
    body = {"model": use_model,
            "messages": [{"role": "system", "content": system}] + messages, "max_tokens": 1000}
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.polza.ai/api/v1/chat/completions",
                          json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=40)) as r:
            data = await r.json()
            if r.status != 200:
                err = data.get("error", {})
                msg = err.get("message", str(data)) if isinstance(err, dict) else str(err)
                raise Exception(f"Polza.ai {r.status}: {msg}")
            return data["choices"][0]["message"]["content"]


async def ask_polza_gpt4o(messages: list, system: str) -> str:
    return await ask_polza(messages, system, "openai/gpt-4o")

async def ask_polza_claude(messages: list, system: str) -> str:
    return await ask_polza(messages, system, "anthropic/claude-3-5-sonnet-20241022")

async def ask_polza_gemini(messages: list, system: str) -> str:
    return await ask_polza(messages, system, "google/gemini-2.0-flash")

async def ask_polza_llama(messages: list, system: str) -> str:
    return await ask_polza(messages, system, "meta-llama/llama-3.1-70b-instruct")


# ── Карта всех провайдеров ──
AI_MAP: dict[str, Callable] = {
    "groq":         ask_groq,
    "gemini":       ask_gemini,
    "claude":       ask_claude,
    "deepseek":     ask_deepseek,
    "gpt":          ask_gpt,
    "mistral":      ask_mistral,
    "cohere":       ask_cohere,
    "together":     ask_together,
    "huggingface":  ask_huggingface,
    "hf":           ask_huggingface,
    "polza":        ask_polza,
    "polza_gpt4o":  ask_polza_gpt4o,
    "polza_claude": ask_polza_claude,
    "polza_gemini": ask_polza_gemini,
    "polza_llama":  ask_polza_llama,
}

AI_NAMES: dict[str, str] = {
    "groq":         "⚡ Groq Llama",
    "gemini":       "✨ Google Gemini",
    "claude":       "🧠 Anthropic Claude",
    "deepseek":     "🔮 DeepSeek",
    "gpt":          "🤖 OpenAI GPT",
    "mistral":      "💨 Mistral",
    "cohere":       "🌊 Cohere",
    "together":     "🤝 Together AI",
    "huggingface":  "🤗 HuggingFace",
    "polza":        "🇷🇺 Polza.ai",
    "polza_gpt4o":  "🇷🇺 Polza→GPT-4o",
    "polza_claude": "🇷🇺 Polza→Claude",
    "polza_gemini": "🇷🇺 Polza→Gemini",
    "polza_llama":  "🇷🇺 Polza→Llama",
}


def get_available_ai() -> list[str]:
    """Возвращает список доступных провайдеров (у которых есть ключи)"""
    from bot.config import (GROQ_API_KEY, GEMINI_API_KEY, CLAUDE_API_KEY,
                             DEEPSEEK_API_KEY, OPENAI_API_KEY, MISTRAL_API_KEY,
                             COHERE_API_KEY, TOGETHER_API_KEY, HF_API_KEY, POLZA_API_KEY)
    key_map = {
        "groq": GROQ_API_KEY, "gemini": GEMINI_API_KEY, "claude": CLAUDE_API_KEY,
        "deepseek": DEEPSEEK_API_KEY, "gpt": OPENAI_API_KEY, "mistral": MISTRAL_API_KEY,
        "cohere": COHERE_API_KEY, "together": TOGETHER_API_KEY,
        "huggingface": HF_API_KEY, "polza": POLZA_API_KEY,
    }
    return [name for name, key in key_map.items() if key]


async def smart_request(messages: list, system: str, preferred: str = None) -> str:
    """
    Умный запрос — пробует провайдеры по приоритету.
    Автоматически переключается при ошибке.
    """
    from bot.config import config
    active = preferred or config.get("active_ai", "groq")
    available = get_available_ai()

    # Приоритетный список: сначала выбранный, потом остальные
    priority = [active] + [a for a in ["groq", "gemini", "mistral", "polza", "cohere"] if a != active]

    for provider in priority:
        if provider not in available:
            continue
        fn = AI_MAP.get(provider)
        if not fn:
            continue
        try:
            result = await fn(messages, system)
            if result and result.strip():
                if provider != active:
                    log.info(f"AI fallback: {active} → {provider}")
                return result
        except Exception as e:
            log.debug(f"AI {provider} error: {e}")
            continue

    raise Exception("Все AI провайдеры недоступны")


async def ensemble_request(question: str, messages: list, system: str) -> str:
    """
    Ensemble режим — 3 ИИ параллельно, Groq выбирает лучший ответ.
    Если только один доступен — просто отвечает он.
    """
    from bot.config import GROQ_API_KEY, GEMINI_API_KEY, MISTRAL_API_KEY
    from bot.config import TOGETHER_API_KEY, POLZA_API_KEY, COHERE_API_KEY

    fighters = [
        ("groq",    ask_groq,    GROQ_API_KEY),
        ("gemini",  ask_gemini,  GEMINI_API_KEY),
        ("mistral", ask_mistral, MISTRAL_API_KEY),
        ("polza",   ask_polza,   POLZA_API_KEY),
        ("cohere",  ask_cohere,  COHERE_API_KEY),
    ]
    available = [(n, fn) for n, fn, k in fighters if k]

    if not available:
        raise Exception("Нет доступных AI провайдеров")

    if len(available) == 1:
        return await available[0][1](messages, system)

    # Берём до 3 провайдеров
    fighters_3 = available[:3]

    tasks = [fn(messages, system) for _, fn in fighters_3]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    answers = [(name, r) for (name, _), r in zip(fighters_3, results)
               if isinstance(r, str) and r.strip()]

    if not answers:
        raise Exception("Все провайдеры вернули ошибку")

    if len(answers) == 1:
        return answers[0][1]

    # Groq выбирает лучший ответ
    if GROQ_API_KEY:
        try:
            variants = "\n\n".join([f"[{i+1}] {name}: {ans[:300]}"
                                    for i, (name, ans) in enumerate(answers)])
            judge_prompt = (
                "Ты судья. Выбери ЛУЧШИЙ ответ на вопрос пользователя.\n"
                "Критерии: точность, полезность, естественность.\n"
                "Ответь ТОЛЬКО номером: 1, 2 или 3"
            )
            choice = await ask_groq(
                [{"role": "user", "content": f"Вопрос: {question}\n\nВарианты:\n{variants}"}],
                judge_prompt
            )
            idx = int(choice.strip()[0]) - 1
            if 0 <= idx < len(answers):
                return answers[idx][1]
        except Exception:
            pass

    return answers[0][1]
