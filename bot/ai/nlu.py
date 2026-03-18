"""
🧠 NLU — Natural Language Understanding
Двухслойная система: AI парсинг + keyword fallback
81+ интент на русском языке
"""

import re
import json
import logging
from typing import Tuple

log = logging.getLogger("NLU")


# ═══════════════════════════════════════════════
# KEYWORD FALLBACK — все интенты
# ═══════════════════════════════════════════════

INTENT_KEYWORDS: dict[str, list[str]] = {
    # Группы/каналы
    "create_group":      ["создай группу","создай чат","новая группа","create group"],
    "create_supergroup": ["создай супергруппу","супергруппа","supergroup"],
    "create_channel":    ["создай канал","новый канал","create channel"],

    # OSINT
    "osint":             ["разведка","пробей","досье","кто это","вычисли","осинт","osint"],
    "osint_phone":       ["пробей номер","по номеру телефона","кто звонил","найди по номеру","чей номер"],
    "osint_email":       ["пробей email","найди по почте","кто это по email","владелец email"],
    "osint_ip":          ["пробей ip","чей это ip","найди по ip","откуда этот ip","ip lookup"],
    "osint_domain":      ["пробей сайт","чей сайт","whois","домен разведка","кому принадлежит"],

    # Доступ
    "whitelist_add":     ["дай доступ","впусти","разреши пользователю","whitelist add"],
    "blacklist_add":     ["запрети","заблокируй пользователя","в чёрный список","blacklist"],
    "access_open":       ["открой для всех","открыть доступ","access open","открой бота"],
    "access_close":      ["закрой для всех","закрыть доступ","access close"],

    # Сообщения
    "delete_messages":   ["удали сообщения","удалить сообщения","очисти чат","delete messages"],
    "delete_chat":       ["покинь чат","удали переписку","выйди из чата"],

    # Базовые
    "weather":           ["погода","температура","прогноз погоды","сколько градусов","холодно","жарко","идёт дождь"],
    "search":            ["загугли","поищи","погугли","найди в интернете","поиск"],
    "image":             ["нарисуй","сгенерируй картинку","создай изображение","нарисовать","img"],
    "news":              ["новости","последние новости","что нового","news"],
    "block_user":        ["заблокируй","block","забань"],
    "unblock_user":      ["разблокируй","unblock","разбань"],
    "download":          ["скачай","скачать","download"],
    "digest":            ["дайджест","что нового везде","digest","обзор чатов"],
    "copy":              ["скопируй","copy","скопировать сообщения"],
    "send":              ["отправь сообщение","send","перешли в"],
    "forward":           ["пересылай","forward","перенаправляй"],

    # Память
    "remember_fact":     ["запомни что","запомни факт","не забудь что","зафиксируй"],
    "remember_task":     ["добавь задачу","добавь дело","запиши задачу","надо сделать"],
    "remember_name":     ["меня зовут","моё имя","зови меня","my name is"],
    "remember_diary":    ["запиши в дневник","дневник:","diary:","личная запись"],
    "show_brain":        ["что ты обо мне знаешь","покажи мозг","мои задачи","мои факты","show brain"],
    "show_people":       ["кого ты помнишь","список людей","мои контакты в памяти"],
    "show_person":       ["расскажи про","что знаешь о нём","профиль пользователя","досье на"],
    "forget_chat":       ["забудь этот чат","очисти память чата","стёрли диалог"],
    "show_episodes":     ["что мы обсуждали","история разговоров","прошлые темы"],
    "summary":           ["сделай саммари","кратко перескажи","подведи итог","summary"],

    # Саморазвитие
    "self_reflect":      ["проведи рефлексию","проанализируй себя","самоанализ","self reflect"],
    "self_study":        ["изучи тему","узнай про","исследуй","self study"],
    "self_evolve":       ["улучши себя","развивайся","эволюционируй","self evolve"],
    "show_learn":        ["покажи прогресс","что изучил","твоё развитие","learn"],
    "show_kb":           ["база знаний","что знаешь","твои знания","knowledge base"],

    # Напоминания
    "remind_set":        ["напомни","remind","не забудь напомнить","через","скажи мне потом"],
    "remind_list":       ["мои напоминания","покажи напоминания","когда напомнишь"],

    # Мониторинг
    "monitor_add":       ["следи за","мониторь канал","добавь в слежку","отслеживай"],
    "monitor_list":      ["что мониторишь","за чем следишь","список слежки"],

    # Анализ
    "lie_detect":        ["проверь на ложь","это манипуляция","он манипулирует","ложь","манипуляция"],
    "chat_stat":         ["статистика чата","кто активный","топ участников","кто пишет больше"],
    "social_search":     ["найди в соцсетях","есть ли у него инста","найди его аккаунты"],

    # Контент
    "content_gen":       ["напиши пост","придумай пост","сгенерируй контент","пост для канала"],
    "content_plan":      ["контент-план","план постов","что постить","о чём писать"],
    "content_hooks":     ["придумай заголовки","цепляющие заголовки","как назвать пост"],

    # Безопасность
    "security_status":   ["статус безопасности","кто атаковал","были атаки","лог атак"],
    "security_clear":    ["очисти лог атак","удали лог атак","clear security"],
    "mat_on":            ["включи фильтр матов","запрети маты","цензура матов"],
    "mat_off":           ["выключи фильтр матов","разреши маты","убери цензуру"],

    # Клон
    "clone_scan":        ["собери мой стиль","изучи как я пишу","учись писать как я"],
    "clone_analyze":     ["проанализируй мой стиль","создай мой клон","сделай клон"],
    "clone_on":          ["включи клон","отвечай как я","имитируй меня","клон вкл"],
    "clone_off":         ["выключи клон","перестань имитировать","клон выкл"],
    "clone_test":        ["протестируй клон","как бы я ответил","тест клона"],

    # Предсказатель
    "predict":           ["предскажи разговор","что напишет дальше","чем закончится","предсказание"],

    # Переговоры
    "nego_start":        ["автопилот переговоров","веди переговоры","добейся цели","цель:"],
    "nego_stop":         ["стоп переговоры","отключи автопилот переговоров"],

    # Мультиперсона
    "multipersona_set":  ["стиль для этого чата","веди себя как","деловой стиль","дружеский стиль"],

    # Сканер намерений
    "scan_intent":       ["что он хочет","сканируй намерение","его настоящая цель","анализ намерения"],

    # Финансы
    "finance_crypto":    ["цена биткоина","курс ethereum","крипто цена","btc цена","eth цена"],
    "finance_stock":     ["цена акций","курс tesla","stock price","акции apple"],
    "finance_alert":     ["алерт на цену","уведоми когда btc","ценовой алерт"],
    "finance_portfolio": ["обзор рынка","портфолио","что с крипто","состояние рынка"],

    # Бэкап/Дашборд
    "backup_now":        ["сделай бэкап","резервная копия","бэкап","backup now"],
    "dashboard":         ["дашборд","отчёт активности","dashboard","моя статистика"],

    # Мониторинг упоминаний
    "mentions_add":      ["следи за упоминаниями","мониторь упоминания","если меня упомянут"],
    "mentions_list":     ["мои упоминания","список упоминаний"],

    # Редактор
    "edit_grammar":      ["исправь грамматику","орфография","проверь правописание","grammar"],
    "edit_style":        ["улучши текст","исправь стиль","отредактируй","редактура"],
    "edit_short":        ["сократи текст","сделай короче","убери воду","покороче"],
    "edit_formal":       ["сделай официальным","деловой стиль","формальный"],
    "edit_casual":       ["сделай неформальным","как другу","разговорный стиль"],
    "edit_translate":    ["переведи на русский","перевод","translate"],

    # Dark Web / Face / Graph
    "darkweb_check":     ["проверь утечки","dark web","был ли взлом","утечки данных","hibp"],
    "faceosint":         ["найди по фото","кто на фото","face осинт","анализ лица","reverse image"],
    "graph_relations":   ["граф связей","кто с кем общается","кто кому отвечает","социальный граф"],

    # Паранойя/Шифрование
    "paranoia_now":      ["удали все мои сообщения","режим паранойи","зачисти чат","убери мои следы"],
    "encrypt_status":    ["статус шифрования","шифрование памяти","зашифрованы ли данные"],
}

# Расширенные NLU keywords (финальные)
FINAL_KEYWORDS: dict[str, list[str]] = {
    "backup_now":       ["сохрани копию","скопируй данные","backup"],
    "dashboard":        ["покажи отчёт","общая статистика","сводный отчёт"],
    "clone_scan":       ["scan style","собери образцы","запомни мой стиль письма"],
    "predict":          ["что он ответит","угадай следующее","что будет дальше"],
    "nego_start":       ["хочу скидку","убеди его","уговори их","переговорный режим"],
    "finance_crypto":   ["bitcoin price","ethereum price","crypto price","монета цена","курс крипты"],
    "finance_stock":    ["акции сейчас","биржа","фондовый рынок"],
    "osint_phone":      ["телефон разведка","найди владельца номера","lookup phone"],
    "osint_ip":         ["геолокация ip","ip osint","чей айпи"],
    "darkweb_check":    ["мои данные слили","взломан ли аккаунт","darkweb","проверка утечек"],
    "faceosint":        ["пробей по фото","найди этого человека","face recognition"],
    "graph_relations":  ["построй граф","кто дружит","отношения в чате"],
    "paranoia_now":     ["удали историю","зачисти переписку","стёрли всё"],
}


def nlu_fallback(text: str) -> Tuple[str, dict]:
    """Keyword-based NLU — резервный слой"""
    t = text.lower().strip()

    # Извлекаем мета-данные
    uname = re.search(r'@(\w+)', text)
    uid   = re.search(r'\b(\d{5,12})\b', text)
    nums  = re.findall(r'\d+', text)
    target = uname.group(1) if uname else (uid.group(1) if uid else None)

    params = {"target": target}
    if nums:
        params["count"] = nums[0]

    # Проверяем все интенты
    all_keywords = {**INTENT_KEYWORDS, **FINAL_KEYWORDS}

    for intent, words in all_keywords.items():
        if any(w in t for w in words):
            # Специфичные параметры
            if intent == "weather":
                wl = t.split()
                for i, w in enumerate(wl):
                    if w in ["погода","температура","прогноз","в"] and i+1 < len(wl):
                        params["city"] = wl[i+1]
                        break
                if not params.get("city"):
                    params["city"] = "Москва"

            elif intent in ("search", "image", "content_gen", "content_plan",
                            "content_hooks", "self_study"):
                # Извлекаем запрос
                for kw in words:
                    if kw in t:
                        q = t.replace(kw, "").strip()
                        if q:
                            params["query"] = q
                        break

            elif intent in ("remember_fact", "remember_task", "remember_name", "remember_diary"):
                for kw in words:
                    if kw in t:
                        content = t.replace(kw, "").strip()
                        if content:
                            params["content"] = content
                        break

            return intent, params

    return "ai", {}


async def nlu_parse_ai(text: str) -> Tuple[str, dict]:
    """AI-based NLU — основной слой"""
    from bot.config import GROQ_API_KEY, COHERE_API_KEY, GEMINI_API_KEY

    intents_list = "\n".join([f"- {k}" for k in INTENT_KEYWORDS.keys()])

    system = f"""Ты — система распознавания намерений (NLU) для Telegram userbot.
Определи intent и параметры из фразы пользователя.

Доступные intents:
{intents_list}
- ai — обычный вопрос (всё остальное)

Параметры:
- target: @username, ID, номер телефона, email, IP или домен
- city: город (для погоды)
- query: поисковый запрос
- content: текст для запоминания
- count: число

Отвечай ТОЛЬКО валидным JSON:
{{"intent": "...", "params": {{...}}}}"""

    try:
        from bot.ai.providers import ask_groq, ask_gemini, ask_cohere
        if GROQ_API_KEY:       fn = ask_groq
        elif GEMINI_API_KEY:   fn = ask_gemini
        elif COHERE_API_KEY:   fn = ask_cohere
        else:
            raise Exception("Нет AI для NLU")

        response = await fn([{"role": "user", "content": f"Фраза: {text}"}], system)
        clean = response.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        intent = data.get("intent", "ai")
        params = data.get("params", {})

        # Доизвлекаем target если AI не нашёл
        if not params.get("target"):
            uname = re.search(r'@(\w+)', text)
            uid   = re.search(r'\b(\d{5,12})\b', text)
            tme   = re.search(r't\.me/([a-zA-Z0-9_]+)', text)
            if uname: params["target"] = uname.group(1)
            elif uid: params["target"] = uid.group(1)
            elif tme: params["target"] = tme.group(1)

        return intent, params

    except Exception as e:
        log.debug(f"NLU AI error: {e}, fallback to keywords")
        return nlu_fallback(text)


async def parse_intent(text: str) -> Tuple[str, dict]:
    """Главная функция — пробует AI потом fallback"""
    try:
        return await nlu_parse_ai(text)
    except Exception:
        return nlu_fallback(text)
