"""
🎛️ CONTROL BOT — Управление юзерботом через Telegram бот
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Отдельный бот (@BotFather) который управляет userbot.py.
Только ты (OWNER_ID) можешь управлять.

Переменные в .env:
  BOT_TOKEN=токен_от_BotFather
  OWNER_ID=твой_telegram_id
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    BufferedInputFile
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from database import (
    init_db, kv_get, kv_set,
    people_all, security_log_get, security_log_count, security_log_clear,
    db_stats, reminders_get_active, alerts_get_active,
    monitors_get_all, monitor_set, monitor_delete,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("ControlBot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID  = int(os.getenv("OWNER_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в .env")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp  = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

CONFIG_FILE = "userbot_config.json"

# ══════════════════════════════════════════════════════
# УТИЛИТЫ
# ══════════════════════════════════════════════════════

def owner_only(func):
    """Декоратор — только владелец"""
    async def wrapper(event, *args, **kwargs):
        uid = event.from_user.id if hasattr(event, 'from_user') else 0
        if uid != OWNER_ID:
            if hasattr(event, 'answer'):
                await event.answer("⛔ Нет доступа", show_alert=True)
            return
        return await func(event, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def kb(*rows):
    """Быстрое создание inline клавиатуры"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row]
        for row in rows
    ])

def rkb(*buttons, one_time=False):
    """Reply клавиатура"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in buttons],
        resize_keyboard=True,
        one_time_keyboard=one_time
    )

# ══════════════════════════════════════════════════════
# STATES
# ══════════════════════════════════════════════════════

class Form(StatesGroup):
    waiting_autoreply_text = State()
    waiting_persona_name   = State()
    waiting_persona_desc   = State()
    waiting_remind_text    = State()
    waiting_remind_time    = State()
    waiting_monitor_chan   = State()
    waiting_monitor_kw     = State()
    waiting_broadcast      = State()
    waiting_ai_question    = State()

# ══════════════════════════════════════════════════════
# ГЛАВНОЕ МЕНЮ
# ══════════════════════════════════════════════════════

MAIN_MENU = kb(
    [("🤖 ИИ настройки",    "menu_ai"),    ("🔒 Доступ",         "menu_access")],
    [("💬 Авто-ответы",     "menu_reply"), ("🎭 Персона",         "menu_persona")],
    [("🧠 Память",          "menu_memory"),("🛡️ Безопасность",   "menu_security")],
    [("📡 Мониторинг",      "menu_monitor"),("⏰ Напоминания",    "menu_reminders")],
    [("💰 Финансы",         "menu_finance"),("📊 Статистика",     "menu_stats")],
    [("👥 Люди в памяти",   "menu_people"), ("📁 База данных",   "menu_db")],
    [("⚙️ Настройки",       "menu_settings"),("🆘 Помощь",       "menu_help")],
)

@router.message(CommandStart())
@owner_only
async def cmd_start(msg: Message):
    cfg = load_config()
    ai  = cfg.get("active_ai", "groq")
    ar  = "✅" if cfg.get("autoreply_on") else "❌"
    mat = "✅" if cfg.get("mat_filter", True) else "❌"
    await msg.answer(
        f"🎛️ **Панель управления Userbot v6.0**\n\n"
        f"🤖 Активный ИИ: `{ai}`\n"
        f"💬 Авто-ответ: {ar}\n"
        f"🛡️ Фильтр матов: {mat}\n\n"
        f"Выбери раздел:",
        reply_markup=MAIN_MENU
    )

@router.message(Command("menu"))
@owner_only
async def cmd_menu(msg: Message):
    await msg.answer("🎛️ Главное меню:", reply_markup=MAIN_MENU)

# ══════════════════════════════════════════════════════
# ИИ НАСТРОЙКИ
# ══════════════════════════════════════════════════════

AI_MODELS = ["groq","gemini","cohere","claude","deepseek","gpt","mistral","together","huggingface"]
AI_EMOJI  = {"groq":"⚡","gemini":"✨","cohere":"🌊","claude":"🧠","deepseek":"🔮",
             "gpt":"🤖","mistral":"💨","together":"🤝","huggingface":"🤗"}

@router.callback_query(F.data == "menu_ai")
@owner_only
async def menu_ai(cb: CallbackQuery):
    cfg = load_config()
    cur = cfg.get("active_ai","groq")
    buttons = []
    for i in range(0, len(AI_MODELS), 3):
        row = []
        for m in AI_MODELS[i:i+3]:
            e = AI_EMOJI.get(m,"")
            check = " ✓" if m == cur else ""
            row.append((f"{e}{m}{check}", f"set_ai_{m}"))
        buttons.append(row)
    buttons.append([("◀️ Назад", "back_main")])
    await cb.message.edit_text(
        f"🤖 **Выбор ИИ модели**\n\nСейчас: `{cur}`\n\nВыбери:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=d) for t,d in row]
            for row in buttons
        ])
    )

@router.callback_query(F.data.startswith("set_ai_"))
@owner_only
async def set_ai(cb: CallbackQuery):
    model = cb.data.replace("set_ai_","")
    cfg = load_config()
    cfg["active_ai"] = model
    save_config(cfg)
    await cb.answer(f"✅ Переключено на {model}", show_alert=True)
    await menu_ai(cb)

# ══════════════════════════════════════════════════════
# ДОСТУП — whitelist/blacklist
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "menu_access")
@owner_only
async def menu_access(cb: CallbackQuery):
    cfg = load_config()
    wl_on     = cfg.get("whitelist_on", False)
    blocked   = cfg.get("all_blocked", False)
    wl        = cfg.get("whitelist", [])
    bl        = cfg.get("blacklist", [])

    if blocked:       mode = "🔴 Закрыт для всех"
    elif wl_on:       mode = "🔒 Только белый список"
    else:             mode = "🔓 Открыт для всех"

    await cb.message.edit_text(
        f"🔐 **Управление доступом**\n\n"
        f"Режим: {mode}\n"
        f"✅ Белый список: {len(wl)} чел.\n"
        f"🚫 Чёрный список: {len(bl)} чел.",
        reply_markup=kb(
            [("🔓 Открыть для всех",  "access_open"),  ("🔴 Закрыть для всех", "access_close")],
            [("🔒 Только белый список","access_wl_on"), ("📋 Показать списки",  "access_show")],
            [("◀️ Назад", "back_main")]
        )
    )

@router.callback_query(F.data.startswith("access_"))
@owner_only
async def handle_access(cb: CallbackQuery):
    cfg = load_config()
    action = cb.data

    if action == "access_open":
        cfg["all_blocked"] = False; cfg["whitelist_on"] = False
        save_config(cfg)
        await cb.answer("🔓 Открыто для всех", show_alert=True)

    elif action == "access_close":
        cfg["all_blocked"] = True
        save_config(cfg)
        await cb.answer("🔴 Закрыто для всех", show_alert=True)

    elif action == "access_wl_on":
        cfg["whitelist_on"] = not cfg.get("whitelist_on", False)
        save_config(cfg)
        state = "включён" if cfg["whitelist_on"] else "выключен"
        await cb.answer(f"🔒 Вайтлист {state}", show_alert=True)

    elif action == "access_show":
        wl = cfg.get("whitelist", [])
        bl = cfg.get("blacklist", [])
        wl_str = "\n".join(f"  • `{uid}`" for uid in wl[:10]) or "  пусто"
        bl_str = "\n".join(f"  • `{uid}`" for uid in bl[:10]) or "  пусто"
        await cb.message.edit_text(
            f"📋 **Списки доступа**\n\n"
            f"✅ **Белый список:**\n{wl_str}\n\n"
            f"🚫 **Чёрный список:**\n{bl_str}",
            reply_markup=kb([("◀️ Назад", "menu_access")])
        )
        return

    await menu_access(cb)

# ══════════════════════════════════════════════════════
# АВТО-ОТВЕТЫ
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "menu_reply")
@owner_only
async def menu_reply(cb: CallbackQuery):
    cfg = load_config()
    ar  = "✅" if cfg.get("autoreply_on") else "❌"
    pm  = "✅" if cfg.get("pm_autoreply") else "❌"
    men = "✅" if cfg.get("mention_reply") else "❌"
    sti = "✅" if cfg.get("sticker_reply", True) else "❌"
    cal = "✅" if cfg.get("call_reply", True) else "❌"
    joi = "✅" if cfg.get("auto_join") else "❌"
    txt = cfg.get("autoreply_text","")[:40] or "не задан"

    await cb.message.edit_text(
        f"💬 **Авто-ответы**\n\n"
        f"Офлайн ответ: {ar}\n"
        f"Авто-ответ в личках: {pm}\n"
        f"Ответ на упоминание: {men}\n"
        f"Ответ на стикеры: {sti}\n"
        f"Ответ на звонки: {cal}\n"
        f"Авто-вступление в разговор: {joi}\n\n"
        f"Текст ответа: _{txt}_",
        reply_markup=kb(
            [("💬 Офлайн " + ar,      "toggle_autoreply"),  ("📱 Личка " + pm,    "toggle_pm")],
            [("📣 Упоминание " + men,  "toggle_mention"),    ("😀 Стикеры " + sti, "toggle_sticker")],
            [("📞 Звонки " + cal,      "toggle_call"),       ("💭 Авто-вступление " + joi, "toggle_join")],
            [("✏️ Изменить текст ответа", "edit_autoreply_text")],
            [("◀️ Назад", "back_main")]
        )
    )

@router.callback_query(F.data.startswith("toggle_"))
@owner_only
async def handle_toggle(cb: CallbackQuery):
    cfg = load_config()
    key_map = {
        "toggle_autoreply": "autoreply_on",
        "toggle_pm":        "pm_autoreply",
        "toggle_mention":   "mention_reply",
        "toggle_sticker":   "sticker_reply",
        "toggle_call":      "call_reply",
        "toggle_join":      "auto_join",
        "toggle_translate": "translate_on",
        "toggle_voice":     "voice_reply",
        "toggle_photo":     "photo_analysis",
        "toggle_spy":       "spy_mode",
        "toggle_mat":       "mat_filter",
        "toggle_autostatus":"auto_status",
        "toggle_link":      "link_summary",
        "toggle_tts":       "tts_reply",
    }
    key = key_map.get(cb.data)
    if key:
        cfg[key] = not cfg.get(key, False)
        save_config(cfg)
        state = "✅" if cfg[key] else "❌"
        await cb.answer(f"{key}: {state}", show_alert=True)
    await menu_reply(cb)

@router.callback_query(F.data == "edit_autoreply_text")
@owner_only
async def edit_autoreply_text(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text(
        "✏️ Отправь новый текст для авто-ответа:",
        reply_markup=kb([("❌ Отмена", "menu_reply")])
    )
    await state.set_state(Form.waiting_autoreply_text)

@router.message(Form.waiting_autoreply_text)
@owner_only
async def save_autoreply_text(msg: Message, state: FSMContext):
    cfg = load_config()
    cfg["autoreply_text"] = msg.text
    save_config(cfg)
    await state.clear()
    await msg.answer(f"✅ Текст авто-ответа обновлён:\n_{msg.text[:100]}_",
                     reply_markup=MAIN_MENU)

# ══════════════════════════════════════════════════════
# ПЕРСОНА
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "menu_persona")
@owner_only
async def menu_persona(cb: CallbackQuery):
    cfg  = load_config()
    on   = cfg.get("persona_on", False)
    name = cfg.get("persona_name","не задана")
    desc = cfg.get("persona_desc","")[:60] or "нет"
    await cb.message.edit_text(
        f"🎭 **Персона (тайный режим)**\n\n"
        f"Статус: {'✅ активна' if on else '❌ выключена'}\n"
        f"Имя: `{name}`\n"
        f"Описание: _{desc}_",
        reply_markup=kb(
            [("✅ Включить" if not on else "❌ Выключить", "toggle_persona")],
            [("✏️ Задать персону", "set_persona")],
            [("◀️ Назад", "back_main")]
        )
    )

@router.callback_query(F.data == "toggle_persona")
@owner_only
async def toggle_persona(cb: CallbackQuery):
    cfg = load_config()
    if not cfg.get("persona_name") and not cfg.get("persona_on"):
        await cb.answer("Сначала задай персону!", show_alert=True)
        return
    cfg["persona_on"] = not cfg.get("persona_on", False)
    save_config(cfg)
    await menu_persona(cb)

@router.callback_query(F.data == "set_persona")
@owner_only
async def set_persona_start(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text(
        "✏️ Введи **имя** персоны:",
        reply_markup=kb([("❌ Отмена", "menu_persona")])
    )
    await state.set_state(Form.waiting_persona_name)

@router.message(Form.waiting_persona_name)
@owner_only
async def save_persona_name(msg: Message, state: FSMContext):
    await state.update_data(persona_name=msg.text)
    await msg.answer("✏️ Теперь введи **описание** персоны (характер, стиль):")
    await state.set_state(Form.waiting_persona_desc)

@router.message(Form.waiting_persona_desc)
@owner_only
async def save_persona_desc(msg: Message, state: FSMContext):
    data = await state.get_data()
    cfg = load_config()
    cfg["persona_name"] = data["persona_name"]
    cfg["persona_desc"] = msg.text
    save_config(cfg)
    await state.clear()
    await msg.answer(
        f"✅ Персона задана!\n👤 **{data['persona_name']}**\n_{msg.text[:100]}_",
        reply_markup=MAIN_MENU
    )

# ══════════════════════════════════════════════════════
# ПАМЯТЬ
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "menu_memory")
@owner_only
async def menu_memory(cb: CallbackQuery):
    cfg     = load_config()
    mem_on  = "✅" if cfg.get("memory_on") else "❌"
    depth   = cfg.get("memory_depth", 8)
    hdepth  = cfg.get("history_depth", 20)
    summary = "✅" if cfg.get("auto_summary") else "❌"
    people  = "✅" if cfg.get("people_memory") else "❌"

    try:
        all_people = await people_all()
        pcount = len(all_people)
    except:
        pcount = "?"

    await cb.message.edit_text(
        f"🧠 **Память**\n\n"
        f"Память диалогов: {mem_on}\n"
        f"Глубина памяти: {depth} сообщений\n"
        f"История чата: {hdepth} сообщений\n"
        f"Авто-саммари: {summary}\n"
        f"Память о людях: {people} ({pcount} чел.)\n",
        reply_markup=kb(
            [("🧠 Память " + mem_on,       "toggle_memory"),   ("👥 Память о людях " + people, "toggle_people_mem")],
            [("📝 Авто-саммари " + summary, "toggle_summary")],
            [("🔢 Глубина памяти",          "set_mem_depth"),   ("📜 Глубина истории", "set_hist_depth")],
            [("👥 Список людей",            "show_people_list")],
            [("🗑️ Очистить всю память",     "clear_all_memory")],
            [("◀️ Назад", "back_main")]
        )
    )

@router.callback_query(F.data == "toggle_memory")
@owner_only
async def toggle_memory(cb: CallbackQuery):
    cfg = load_config()
    cfg["memory_on"] = not cfg.get("memory_on", True)
    save_config(cfg)
    await menu_memory(cb)

@router.callback_query(F.data == "toggle_people_mem")
@owner_only
async def toggle_people_mem(cb: CallbackQuery):
    cfg = load_config()
    cfg["people_memory"] = not cfg.get("people_memory", True)
    save_config(cfg)
    await menu_memory(cb)

@router.callback_query(F.data == "toggle_summary")
@owner_only
async def toggle_summary(cb: CallbackQuery):
    cfg = load_config()
    cfg["auto_summary"] = not cfg.get("auto_summary", True)
    save_config(cfg)
    await menu_memory(cb)

@router.callback_query(F.data == "show_people_list")
@owner_only
async def show_people_list(cb: CallbackQuery):
    try:
        people = await people_all()
        if not people:
            await cb.answer("Память о людях пуста", show_alert=True)
            return
        lines = [f"👥 **Люди в памяти ({len(people)}):**\n"]
        for uid, p in list(people.items())[:15]:
            name = p.get("name","?")
            cnt  = p.get("messages_count",0)
            prof = p.get("profession","")
            line = f"👤 **{name}** | {cnt} смс"
            if prof: line += f" | {prof}"
            lines.append(line)
        if len(people) > 15:
            lines.append(f"\n_...и ещё {len(people)-15}_")
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=kb([("◀️ Назад", "menu_memory")])
        )
    except Exception as e:
        await cb.answer(f"Ошибка: {e}", show_alert=True)

@router.callback_query(F.data == "clear_all_memory")
@owner_only
async def clear_all_memory(cb: CallbackQuery):
    await cb.message.edit_text(
        "⚠️ **Точно очистить всю память?**\nЭто удалит все диалоги, историю и профили людей.",
        reply_markup=kb(
            [("✅ Да, очистить", "confirm_clear_memory")],
            [("❌ Отмена", "menu_memory")]
        )
    )

@router.callback_query(F.data == "confirm_clear_memory")
@owner_only
async def confirm_clear_memory(cb: CallbackQuery):
    import os
    for f in ["userbot_memory.json","chat_history.json","people_memory.json",
              "episodic_memory.json","dialog_summaries.json"]:
        try: os.remove(f)
        except: pass
    await cb.answer("🗑️ Память очищена", show_alert=True)
    await menu_memory(cb)

# ══════════════════════════════════════════════════════
# БЕЗОПАСНОСТЬ
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "menu_security")
@owner_only
async def menu_security(cb: CallbackQuery):
    cfg = load_config()
    mat = "✅" if cfg.get("mat_filter", True) else "❌"
    fa2 = "✅" if cfg.get("2fa_on") else "❌"
    try:
        total      = await security_log_count()
        injections = await security_log_count("injection")
        code_att   = await security_log_count("code")
    except:
        total = injections = code_att = 0
    await cb.message.edit_text(
        f"🛡️ **Безопасность**\n\n"
        f"Фильтр матов: {mat}\n"
        f"2FA: {fa2}\n\n"
        f"📊 Атак заблокировано: {total}\n"
        f"💉 Prompt injection: {injections}\n"
        f"💻 Code injection: {code_att}",
        reply_markup=kb(
            [("🚫 Мат фильтр " + mat, "toggle_mat"),  ("🔐 2FA " + fa2, "toggle_2fa")],
            [("📋 Лог атак",          "show_attack_log")],
            [("🗑️ Очистить лог",       "clear_attack_log")],
            [("◀️ Назад", "back_main")]
        )
    )

@router.callback_query(F.data == "toggle_mat")
@owner_only
async def toggle_mat(cb: CallbackQuery):
    cfg = load_config()
    cfg["mat_filter"] = not cfg.get("mat_filter", True)
    save_config(cfg)
    await menu_security(cb)

@router.callback_query(F.data == "toggle_2fa")
@owner_only
async def toggle_2fa(cb: CallbackQuery):
    cfg = load_config()
    cfg["2fa_on"] = not cfg.get("2fa_on", False)
    save_config(cfg)
    await menu_security(cb)

@router.callback_query(F.data == "show_attack_log")
@owner_only
async def show_attack_log(cb: CallbackQuery):
    try:
        logs = await security_log_get(10)
        if not logs:
            await cb.answer("Лог пуст", show_alert=True)
            return
        lines = [f"🛡️ **Последние атаки ({len(logs)}):**\n"]
        for e in logs:
            lines.append(f"[{e['date']}] **{e['type']}**\nID:{e['uid']} | {e['text'][:60]}")
        await cb.message.edit_text(
            "\n\n".join(lines),
            reply_markup=kb([("◀️ Назад", "menu_security")])
        )
    except Exception as e:
        await cb.answer(f"Ошибка: {e}", show_alert=True)

@router.callback_query(F.data == "clear_attack_log")
@owner_only
async def clear_attack_log(cb: CallbackQuery):
    try:
        await security_log_clear()
        await cb.answer("✅ Лог очищен", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ {e}", show_alert=True)
    await menu_security(cb)

# ══════════════════════════════════════════════════════
# МОНИТОРИНГ КАНАЛОВ
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "menu_monitor")
@owner_only
async def menu_monitor(cb: CallbackQuery):
    try:
        channels = await monitors_get_all()
    except:
        channels = {}
    lines = [f"📡 **Мониторинг каналов ({len(channels)})**\n"]
    for ch, s in list(channels.items())[:8]:
        active = "✅" if s.get("active", True) else "⏸"
        kws = ", ".join(s.get("keywords", [])) or "все посты"
        lines.append(f"{active} `{ch}` — {kws[:30]}")

    buttons = []
    for ch in list(channels.keys())[:5]:
        buttons.append([(f"🗑️ {ch}", f"del_monitor_{ch}")])
    buttons.append([("➕ Добавить канал", "add_monitor"), ("◀️ Назад", "back_main")])

    await cb.message.edit_text(
        "\n".join(lines) if lines[1:] else "📡 Нет активных мониторов\n\nДобавь канал:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=d) for t,d in row]
            for row in buttons
        ])
    )

@router.callback_query(F.data == "add_monitor")
@owner_only
async def add_monitor_start(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text(
        "📡 Введи **@username** канала для мониторинга:",
        reply_markup=kb([("❌ Отмена", "menu_monitor")])
    )
    await state.set_state(Form.waiting_monitor_chan)

@router.message(Form.waiting_monitor_chan)
@owner_only
async def save_monitor_chan(msg: Message, state: FSMContext):
    chan = msg.text.strip()
    if not chan.startswith("@"): chan = "@" + chan
    await state.update_data(monitor_chan=chan)
    await msg.answer(
        f"📡 Канал: `{chan}`\n\nВведи ключевые слова через пробел (или /skip для всех постов):"
    )
    await state.set_state(Form.waiting_monitor_kw)

@router.message(Form.waiting_monitor_kw)
@owner_only
async def save_monitor_kw(msg: Message, state: FSMContext):
    data = await state.get_data()
    chan = data["monitor_chan"]
    kws  = [] if msg.text == "/skip" else msg.text.split()
    try:
        await monitor_set(chan, {"active": True, "keywords": kws, "added": datetime.now().strftime("%d.%m.%Y")})
    except:
        pass
    await state.clear()
    kw_str = ", ".join(kws) if kws else "все посты"
    await msg.answer(f"✅ Монитор добавлен!\n📡 `{chan}` — {kw_str}", reply_markup=MAIN_MENU)

@router.callback_query(F.data.startswith("del_monitor_"))
@owner_only
async def del_monitor(cb: CallbackQuery):
    chan = cb.data.replace("del_monitor_","")
    try:
        await monitor_delete(chan)
        await cb.answer(f"✅ Удалён: {chan}", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ {e}", show_alert=True)
    await menu_monitor(cb)

# ══════════════════════════════════════════════════════
# НАПОМИНАНИЯ
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "menu_reminders")
@owner_only
async def menu_reminders(cb: CallbackQuery):
    try:
        active = await reminders_get_active()
    except:
        active = []
    lines = [f"⏰ **Напоминания ({len(active)})**\n"]
    for r in active[:8]:
        fire = datetime.fromtimestamp(r["fire_at"]).strftime("%d.%m %H:%M")
        lines.append(f"🕐 {fire} — {r['text'][:50]}")

    await cb.message.edit_text(
        "\n".join(lines) if active else "⏰ Нет активных напоминаний",
        reply_markup=kb(
            [("➕ Добавить напоминание", "add_reminder")],
            [("🗑️ Удалить все",          "clear_reminders")],
            [("◀️ Назад", "back_main")]
        )
    )

@router.callback_query(F.data == "add_reminder")
@owner_only
async def add_reminder_start(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text(
        "⏰ Введи текст напоминания:",
        reply_markup=kb([("❌ Отмена", "menu_reminders")])
    )
    await state.set_state(Form.waiting_remind_text)

@router.message(Form.waiting_remind_text)
@owner_only
async def save_remind_text(msg: Message, state: FSMContext):
    await state.update_data(remind_text=msg.text)
    await msg.answer(
        "⏰ Через сколько напомнить?\n\nПримеры: `30m`, `2h`, `1d`, `15:30`"
    )
    await state.set_state(Form.waiting_remind_time)

@router.message(Form.waiting_remind_time)
@owner_only
async def save_remind_time(msg: Message, state: FSMContext):
    import re
    data = await state.get_data()
    text = data["remind_text"]
    t    = msg.text.strip().lower()

    # Парсим время
    secs = None
    m = re.match(r'^(\d+)\s*(m|м|min|мин)$', t)
    if m: secs = int(m.group(1)) * 60
    m = re.match(r'^(\d+)\s*(h|ч|час)$', t)
    if m: secs = int(m.group(1)) * 3600
    m = re.match(r'^(\d+)\s*(d|д|день)$', t)
    if m: secs = int(m.group(1)) * 86400
    m = re.match(r'^(\d{1,2}):(\d{2})$', t)
    if m:
        now = datetime.now()
        target = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0)
        if target <= now: target = target.replace(day=target.day+1)
        secs = int((target - now).total_seconds())

    if not secs:
        await msg.answer("❌ Не понял время. Попробуй: `30m`, `2h`, `15:30`")
        return

    fire_at  = datetime.now().timestamp() + secs
    fire_str = datetime.fromtimestamp(fire_at).strftime("%d.%m.%Y %H:%M")
    try:
        await reminder_add(text, fire_at, datetime.now().strftime("%d.%m %H:%M"))
    except:
        pass
    await state.clear()
    await msg.answer(f"✅ Напомню в **{fire_str}**\n📝 {text}", reply_markup=MAIN_MENU)

@router.callback_query(F.data == "clear_reminders")
@owner_only
async def clear_reminders_cb(cb: CallbackQuery):
    import os
    try: os.remove("reminders.json")
    except: pass
    await cb.answer("🗑️ Напоминания удалены", show_alert=True)
    await menu_reminders(cb)

# ══════════════════════════════════════════════════════
# ФИНАНСЫ — алерты
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "menu_finance")
@owner_only
async def menu_finance(cb: CallbackQuery):
    try:
        alerts = await alerts_get_active()
    except:
        alerts = []
    lines = [f"💰 **Ценовые алерты ({len(alerts)})**\n"]
    for a in alerts[:8]:
        arrow = "📈" if a["direction"]=="above" else "📉"
        lines.append(f"{arrow} {a['symbol'].upper()} {'>' if a['direction']=='above' else '<'} ${a['target_price']:,.2f}")

    await cb.message.edit_text(
        "\n".join(lines) if alerts else "💰 Нет активных алертов",
        reply_markup=kb(
            [("🗑️ Удалить все алерты", "clear_alerts")],
            [("◀️ Назад", "back_main")]
        )
    )

@router.callback_query(F.data == "clear_alerts")
@owner_only
async def clear_alerts_cb(cb: CallbackQuery):
    import os
    try: os.remove("price_alerts.json")
    except: pass
    await cb.answer("🗑️ Алерты удалены", show_alert=True)
    await menu_finance(cb)

# ══════════════════════════════════════════════════════
# СТАТИСТИКА
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "menu_stats")
@owner_only
async def menu_stats(cb: CallbackQuery):
    cfg = load_config()
    s   = cfg.get("stats", {})

    # Загружаем self_learning
    sl = {}
    try:
        sl = await kv_get("self_learning") or {}
    except: pass

    await cb.message.edit_text(
        f"📊 **Статистика**\n\n"
        f"📨 Запросов к ИИ: {s.get('total',0)}\n"
        f"🎤 Голосовых: {s.get('voice',0)}\n"
        f"🖼 Фото: {s.get('photo',0)}\n"
        f"🌐 Переводов: {s.get('translate',0)}\n\n"
        f"🧬 Версия промпта: v{sl.get('evolution_ver',1)}\n"
        f"📚 Изучено тем: {len(sl.get('learned_topics',[]))}\n"
        f"💡 Рефлексий: {len(sl.get('improvements',[]))}\n"
        f"🕐 Сессий: {sl.get('sessions',0)}",
        reply_markup=kb(
            [("📊 Дашборд HTML",  "gen_dashboard")],
            [("◀️ Назад", "back_main")]
        )
    )

@router.callback_query(F.data == "gen_dashboard")
@owner_only
async def gen_dashboard(cb: CallbackQuery):
    await cb.answer("📊 Генерирую дашборд...", show_alert=False)
    # Простой текстовый дашборд через бота
    try:
        stats = await db_stats()
        lines = ["📊 **DB Stats:**\n"]
        if stats.get("backend") == "PostgreSQL":
            for t, c in stats.get("tables",{}).items():
                lines.append(f"  `{t}`: {c}")
        else:
            lines.append("📁 JSON файлы")
        await cb.message.answer("\n".join(lines))
    except Exception as e:
        await cb.message.answer(f"❌ {e}")

# ══════════════════════════════════════════════════════
# БАЗА ДАННЫХ
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "menu_db")
@owner_only
async def menu_db(cb: CallbackQuery):
    try:
        stats = await db_stats()
        backend = stats.get("backend","?")
        if backend == "PostgreSQL":
            tables = stats.get("tables",{})
            lines  = [f"🗄️ **База данных: PostgreSQL ✅**\n"]
            total  = sum(tables.values())
            lines.append(f"Всего записей: {total}\n")
            for t, c in tables.items():
                lines.append(f"  `{t}`: {c}")
        else:
            lines = ["📁 **Хранилище: JSON файлы**\n",
                     "Добавь `DATABASE_URL` для PostgreSQL"]
    except Exception as e:
        lines = [f"❌ Ошибка: {e}"]

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=kb([("◀️ Назад", "back_main")])
    )

# ══════════════════════════════════════════════════════
# НАСТРОЙКИ
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "menu_settings")
@owner_only
async def menu_settings(cb: CallbackQuery):
    cfg   = load_config()
    trans = "✅" if cfg.get("translate_on") else "❌"
    voice = "✅" if cfg.get("voice_reply") else "❌"
    photo = "✅" if cfg.get("photo_analysis") else "❌"
    spy   = "✅" if cfg.get("spy_mode") else "❌"
    tts   = "✅" if cfg.get("tts_reply") else "❌"
    status= "✅" if cfg.get("auto_status") else "❌"
    link  = "✅" if cfg.get("link_summary") else "❌"
    delay = cfg.get("antispam_delay", 6)
    dest  = cfg.get("autodestruct", 0)

    await cb.message.edit_text(
        f"⚙️ **Настройки**\n\n"
        f"🌐 Авто-перевод: {trans}\n"
        f"🎤 Голосовые: {voice}\n"
        f"📸 Анализ фото: {photo}\n"
        f"🕵️ Шпион удалённых: {spy}\n"
        f"🔊 TTS ответы: {tts}\n"
        f"⏰ Авто-статус: {status}\n"
        f"🔗 Саммари ссылок: {link}\n"
        f"⏱ Задержка: {delay}с\n"
        f"💣 Авто-удаление: {f'{dest}с' if dest else 'выкл'}",
        reply_markup=kb(
            [("🌐 Перевод " + trans,  "toggle_translate"), ("🎤 Голос " + voice, "toggle_voice")],
            [("📸 Фото " + photo,     "toggle_photo"),     ("🕵️ Шпион " + spy,  "toggle_spy")],
            [("🔊 TTS " + tts,        "toggle_tts"),       ("⏰ Статус " + status, "toggle_autostatus")],
            [("🔗 Ссылки " + link,    "toggle_link")],
            [("⏱ Задержка антиспама", "set_delay"),        ("💣 Авто-удаление", "set_autodestruct")],
            [("◀️ Назад", "back_main")]
        )
    )

@router.callback_query(F.data.startswith("toggle_translate") |
                       F.data.startswith("toggle_voice") |
                       F.data.startswith("toggle_photo") |
                       F.data.startswith("toggle_spy") |
                       F.data.startswith("toggle_tts") |
                       F.data.startswith("toggle_autostatus") |
                       F.data.startswith("toggle_link"))
@owner_only
async def handle_settings_toggle(cb: CallbackQuery):
    cfg = load_config()
    key_map = {
        "toggle_translate":  "translate_on",
        "toggle_voice":      "voice_reply",
        "toggle_photo":      "photo_analysis",
        "toggle_spy":        "spy_mode",
        "toggle_tts":        "tts_reply",
        "toggle_autostatus": "auto_status",
        "toggle_link":       "link_summary",
    }
    key = key_map.get(cb.data)
    if key:
        cfg[key] = not cfg.get(key, False)
        save_config(cfg)
        state = "✅" if cfg[key] else "❌"
        await cb.answer(f"{key}: {state}", show_alert=True)
    await menu_settings(cb)

# ══════════════════════════════════════════════════════
# ПОМОЩЬ
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "menu_help")
@owner_only
async def menu_help(cb: CallbackQuery):
    await cb.message.edit_text(
        "🆘 **Справка**\n\n"
        "**Команды бота:**\n"
        "/start — главное меню\n"
        "/menu — главное меню\n"
        "/status — быстрый статус\n"
        "/ask [вопрос] — спросить ИИ\n\n"
        "**Управление userbot напрямую:**\n"
        "В Telegram пиши `.help` для списка всех команд\n"
        "Или используй натуральный язык: `+вопрос`\n\n"
        "**Файлы:**\n"
        "`userbot.py` — основной бот\n"
        "`database.py` — слой PostgreSQL\n"
        "`control_bot.py` — этот бот\n\n"
        "**Railway:**\n"
        "Добавь `BOT_TOKEN` в Variables",
        reply_markup=kb([("◀️ Назад", "back_main")])
    )

# ══════════════════════════════════════════════════════
# БЫСТРЫЕ КОМАНДЫ
# ══════════════════════════════════════════════════════

@router.message(Command("status"))
@owner_only
async def cmd_status(msg: Message):
    cfg = load_config()
    ai  = cfg.get("active_ai","groq")
    ar  = "✅" if cfg.get("autoreply_on") else "❌"
    mem = "✅" if cfg.get("memory_on") else "❌"
    mat = "✅" if cfg.get("mat_filter",True) else "❌"
    try:
        stats = await db_stats()
        db_str = f"PostgreSQL ✅" if stats.get("backend")=="PostgreSQL" else "JSON 📁"
    except:
        db_str = "?"
    await msg.answer(
        f"📊 **Статус Userbot**\n\n"
        f"🤖 ИИ: `{ai}`\n"
        f"💬 Авто-ответ: {ar}\n"
        f"🧠 Память: {mem}\n"
        f"🛡️ Мат-фильтр: {mat}\n"
        f"🗄️ БД: {db_str}",
        reply_markup=MAIN_MENU
    )

@router.message(Command("ask"))
@owner_only
async def cmd_ask(msg: Message):
    """Задать вопрос ИИ напрямую через бота"""
    question = msg.text.replace("/ask","").strip()
    if not question:
        await msg.answer("Использование: /ask твой вопрос")
        return
    await msg.answer("🤔 Думаю...")
    # Простой запрос через Groq
    try:
        import aiohttp
        GROQ_KEY = os.getenv("GROQ_API_KEY","")
        if not GROQ_KEY:
            await msg.answer("❌ GROQ_API_KEY не задан")
            return
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":question}],"max_tokens":800},
                headers={"Authorization":f"Bearer {GROQ_KEY}"},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as r:
                data = await r.json()
                answer = data["choices"][0]["message"]["content"]
                await msg.answer(f"🤖 {answer[:4000]}")
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}")

# ══════════════════════════════════════════════════════
# НАВИГАЦИЯ
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "back_main")
@owner_only
async def back_main(cb: CallbackQuery):
    await cb.message.edit_text("🎛️ Главное меню:", reply_markup=MAIN_MENU)

@router.callback_query(F.data.startswith("set_mem_depth") |
                       F.data.startswith("set_hist_depth") |
                       F.data.startswith("set_delay") |
                       F.data.startswith("set_autodestruct"))
@owner_only
async def handle_set_numeric(cb: CallbackQuery):
    labels = {
        "set_mem_depth":    ("🔢 Введи глубину памяти (5-50 сообщений):", "memory_depth"),
        "set_hist_depth":   ("📜 Введи глубину истории (10-100):", "history_depth"),
        "set_delay":        ("⏱ Введи задержку антиспама в секундах (0-60):", "antispam_delay"),
        "set_autodestruct": ("💣 Авто-удаление через N секунд (0=выкл):", "autodestruct"),
    }
    label, key = labels[cb.data]
    await cb.message.edit_text(label)
    # Используем FSM для получения числа
    # Простой вариант — просим ввести и обрабатываем в следующем сообщении
    await cb.answer(f"Отправь число в чат")

# ══════════════════════════════════════════════════════
# ЗАПУСК
# ══════════════════════════════════════════════════════

async def main():
    log.info("🎛️ Control Bot запускается...")
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    log.info(f"🎛️ Control Bot запущен! OWNER_ID={OWNER_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
