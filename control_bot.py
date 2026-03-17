"""
╔══════════════════════════════════════════════════════╗
║     🎛️  USERBOT CONTROL PANEL  v6.0                 ║
║     Красивая панель управления через Telegram        ║
╚══════════════════════════════════════════════════════╝
"""

import os, json, asyncio, logging, aiohttp, re
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from database import (
    init_db, kv_get, kv_set,
    people_all, security_log_get, security_log_count, security_log_clear,
    db_stats, reminders_get_active, reminder_add,
    alerts_get_active, monitors_get_all, monitor_set, monitor_delete,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("ControlBot")

BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
OWNER_ID    = int(os.getenv("OWNER_ID", "0"))
CONFIG_FILE = "userbot_config.json"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в .env")

bot    = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp     = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

LINE  = "━━━━━━━━━━━━━━━━━━━━━━━━"
LINE2 = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"
ON    = "🟢"
OFF   = "🔴"

def status(val): return ON if val else OFF
def header(icon, title): return f"{icon} <b>{title}</b>\n{LINE}"
def back(to="back_main"): return [("◀️  Назад", to)]

# ── Дефолтный конфиг ──
DEFAULT_CONFIG = {
    "active_ai": "groq", "trigger": "+", "whitelist_on": False,
    "whitelist": [], "blacklist": [], "all_blocked": False,
    "memory_on": True, "memory_depth": 8, "history_depth": 20,
    "autoreply_on": False, "autoreply_text": "сейчас нет, напишу позже",
    "mention_reply": True, "translate_on": True, "voice_reply": True,
    "photo_analysis": True, "antispam_delay": 6, "spy_mode": False,
    "auto_status": False, "link_summary": True, "pm_autoreply": False,
    "people_memory": True, "auto_summary": True, "persona_name": "",
    "persona_desc": "", "persona_on": False, "tts_reply": False,
    "autodestruct": 0, "mat_filter": True, "2fa_on": False,
    "sticker_reply": True, "call_reply": True, "auto_join": False,
    "stats": {"total": 0, "voice": 0, "photo": 0, "translate": 0},
}

# Кэш конфига в памяти — единый источник правды
_config_cache: dict = dict(DEFAULT_CONFIG)

async def load_config_async() -> dict:
    """Читает СВЕЖИЙ конфиг из PostgreSQL — всегда актуальные данные"""
    cfg = dict(DEFAULT_CONFIG)
    # JSON как fallback
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                file_data = json.load(f)
                if isinstance(file_data, dict):
                    cfg.update(file_data)
        except: pass
    # DB — самые актуальные данные (приоритет)
    try:
        db_cfg = await kv_get("config")
        if db_cfg and isinstance(db_cfg, dict) and len(db_cfg) > 3:
            cfg.update(db_cfg)
    except Exception as e:
        log.debug(f"DB config read error: {e}")
    # Обновляем кэш
    _config_cache.clear()
    _config_cache.update(cfg)
    return dict(_config_cache)

def load_config() -> dict:
    """Возвращает кэш конфига (обновляется через load_config_async каждые 30 сек)"""
    return dict(_config_cache) if _config_cache else dict(DEFAULT_CONFIG)

def save_config(cfg: dict):
    """Сохраняет конфиг: кэш → JSON → PostgreSQL (userbot подхватит за 3 сек)"""
    # 1. Обновляем кэш немедленно
    _config_cache.clear()
    _config_cache.update(cfg)
    # 2. JSON
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.debug(f"Config JSON error: {e}")
    # 3. DB — асинхронно
    try:
        asyncio.create_task(_save_config_db(cfg))
    except Exception as e:
        log.debug(f"Config DB task error: {e}")

async def _save_config_db(cfg: dict):
    """Асинхронно записывает конфиг в PostgreSQL"""
    try:
        await kv_set("config", cfg)
        log.info(f"✅ DB: autoreply={cfg.get('autoreply_on')} pm={cfg.get('pm_autoreply')} ai={cfg.get('active_ai')}")
    except Exception as e:
        log.error(f"Config DB save error: {e}")

def kb(*rows):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row]
        for row in rows
    ])

def owner_only(func):
    import functools
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Находим event — первый аргумент (Message или CallbackQuery)
        event = args[0] if args else None
        uid = getattr(getattr(event, 'from_user', None), 'id', 0)
        if uid != OWNER_ID:
            if hasattr(event, 'answer'): await event.answer("⛔️ Только для владельца", show_alert=True)
            elif hasattr(event, 'reply'): await event.reply("⛔️ Нет доступа")
            return
        return await func(*args, **kwargs)
    return wrapper

class S(StatesGroup):
    autoreply_text = State()
    persona_name   = State()
    persona_desc   = State()
    remind_text    = State()
    remind_time    = State()
    monitor_chan   = State()
    monitor_kw     = State()
    ai_question    = State()
    numeric_input  = State()
    whitelist_add  = State()
    blacklist_add  = State()

def build_main_menu():
    cfg = _config_cache if _config_cache else load_config()
    ai  = cfg.get("active_ai", "groq").upper()
    ar  = ON if cfg.get("autoreply_on") else OFF
    mem = ON if cfg.get("memory_on", True) else OFF
    sec = ON if cfg.get("mat_filter", True) else OFF
    return kb(
        [(f"🤖 ИИ: {ai}",        "menu_ai"),      (f"💬 Ответ: {ar}",     "menu_reply")],
        [(f"🧠 Память: {mem}",    "menu_memory"),  (f"🛡️ Защита: {sec}",   "menu_security")],
        [("🎭  Персона",          "menu_persona"),  ("🔐  Доступ",          "menu_access")],
        [("📡  Мониторинг",       "menu_monitor"),  ("⏰  Напоминания",     "menu_reminders")],
        [("💰  Финансы",          "menu_finance"),  ("👥  Люди",            "menu_people")],
        [("📊  Статистика",       "menu_stats"),    ("🗄️  База данных",    "menu_db")],
        [("⚙️  Настройки",        "menu_settings"), ("🆘  Помощь",         "menu_help")],
        [("🔄  Обновить",         "refresh_main"),  ("🤖  Спросить ИИ",    "quick_ask")],
    )

async def show_main(target, edit=True):
    cfg = await load_config_async()
    ai  = cfg.get("active_ai","groq")
    ar  = "вкл ✅" if cfg.get("autoreply_on") else "выкл ❌"
    mem = "вкл ✅" if cfg.get("memory_on",True) else "выкл ❌"
    mat = "вкл ✅" if cfg.get("mat_filter",True) else "выкл ❌"
    now = datetime.now().strftime("%d.%m.%Y  %H:%M")
    try:
        sl  = await kv_get("self_learning") or {}
        ver = sl.get("evolution_ver",1)
        tot = sl.get("total_messages",0)
    except:
        ver=1; tot=0

    text = (
        f"╔═══════════════════════════╗\n"
        f"║  🎛️  <b>USERBOT PANEL  v6.0</b>  ║\n"
        f"╚═══════════════════════════╝\n\n"
        f"🕐 <i>{now}</i>\n"
        f"{LINE}\n"
        f"🤖  ИИ модель:   <code>{ai}</code>\n"
        f"💬  Авто-ответ: {ar}\n"
        f"🧠  Память:     {mem}\n"
        f"🛡️  Мат-фильтр:{mat}\n"
        f"{LINE2}\n"
        f"🧬  Промпт: <code>v{ver}</code>  •  📨 <code>{tot}</code> запросов\n"
        f"{LINE}\n"
        f"<i>Выбери раздел 👇</i>"
    )
    markup = build_main_menu()
    if edit and hasattr(target,'message'):
        try: await target.message.edit_text(text, reply_markup=markup)
        except: await target.message.answer(text, reply_markup=markup)
    elif hasattr(target,'answer'):
        await target.answer(text, reply_markup=markup)

@router.message(CommandStart())
@owner_only
async def cmd_start(msg: Message):
    m = await msg.answer("⚡️ <i>Загружаю панель управления...</i>")
    await asyncio.sleep(0.5)
    await m.edit_text("🔧 <i>Подключаюсь к базе данных...</i>")
    await asyncio.sleep(0.4)
    await m.edit_text("✅ <i>Готово! Открываю панель...</i>")
    await asyncio.sleep(0.3)
    await m.delete()
    await show_main(msg, edit=False)

@router.message(Command("menu"))
@owner_only
async def cmd_menu(msg: Message):
    await show_main(msg, edit=False)

@router.callback_query(F.data == "back_main")
@owner_only
async def back_main(cb: CallbackQuery):
    await show_main(cb)

@router.callback_query(F.data == "refresh_main")
@owner_only
async def refresh_main(cb: CallbackQuery):
    await cb.answer("🔄 Обновлено", show_alert=False)
    await show_main(cb)

# ━━ ИИ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI_INFO = {
    "groq":        ("⚡️","Groq Llama","Бесплатно • Быстрый"),
    "gemini":      ("✨","Google Gemini","Бесплатно • Мощный"),
    "cohere":      ("🌊","Cohere","Бесплатно"),
    "claude":      ("🧠","Anthropic Claude","Платный • Умный"),
    "deepseek":    ("🔮","DeepSeek","Дешёвый"),
    "gpt":         ("🤖","OpenAI GPT","Платный"),
    "mistral":     ("💨","Mistral","Бесплатно"),
    "together":    ("🤝","Together AI","Бесплатно"),
    "huggingface":  ("🤗", "HuggingFace",    "Бесплатно"),
    "polza":        ("🇷🇺", "Polza.ai",       "Российский • Без VPN • Рубли"),
    "polza_gpt4o":  ("🇷🇺", "Polza → GPT-4o", "GPT-4o через Polza.ai"),
    "polza_claude": ("🇷🇺", "Polza → Claude", "Claude 3.5 через Polza.ai"),
    "polza_gemini": ("🇷🇺", "Polza → Gemini", "Gemini 2.0 через Polza.ai"),
    "polza_llama":  ("🇷🇺", "Polza → Llama",  "Llama 70B через Polza.ai"),
}

@router.callback_query(F.data == "menu_ai")
@owner_only
async def menu_ai(cb: CallbackQuery):
    cfg = await load_config_async()
    cur = cfg.get("active_ai","groq")
    info = AI_INFO.get(cur, ("❓",cur,""))
    flat = [(f"{e} {l}{' ✓' if n==cur else ''}", f"set_ai_{n}") for n,(e,l,d) in AI_INFO.items()]
    rows = [flat[i:i+3] for i in range(0,len(flat),3)]
    rows.append(back())
    await cb.message.edit_text(
        f"{header('🤖','Выбор ИИ модели')}\n\n"
        f"Активна: <b>{info[0]} {info[1]}</b>\n"
        f"<i>{info[2]}</i>\n\n<i>Нажми для переключения:</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t,callback_data=d) for t,d in row] for row in rows
        ])
    )

@router.callback_query(F.data.startswith("set_ai_"))
@owner_only
async def set_ai(cb: CallbackQuery):
    model = cb.data.replace("set_ai_","")
    model = cb.data.replace("set_ai_",""); cfg = await load_config_async(); cfg["active_ai"] = model; save_config(cfg)
    info = AI_INFO.get(model,("❓",model,""))
    await cb.answer(f"✅  {info[0]} {info[1]}", show_alert=True)
    await menu_ai(cb)

# ━━ АВТО-ОТВЕТЫ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "menu_reply")
@owner_only
async def menu_reply(cb: CallbackQuery):
    cfg = await load_config_async()
    ar=cfg.get("autoreply_on",False); pm=cfg.get("pm_autoreply",False)
    men=cfg.get("mention_reply",True); sti=cfg.get("sticker_reply",True)
    cal=cfg.get("call_reply",True); joi=cfg.get("auto_join",False)
    txt=cfg.get("autoreply_text","")[:50] or "<i>не задан</i>"
    await cb.message.edit_text(
        f"{header('💬','Авто-ответы')}\n\n"
        f"{status(ar)}  Офлайн ответ\n{status(pm)}  Авто-ответ в личках\n"
        f"{status(men)}  На упоминания\n{status(sti)}  На стикеры\n"
        f"{status(cal)}  На звонки\n{status(joi)}  Авто-вступление\n"
        f"{LINE2}\n📝  Текст: <i>{txt}</i>",
        reply_markup=kb(
            [(f"{status(ar)} Офлайн","tr_autoreply"),(f"{status(pm)} Личка","tr_pm")],
            [(f"{status(men)} Упоминание","tr_mention"),(f"{status(sti)} Стикеры","tr_sticker")],
            [(f"{status(cal)} Звонки","tr_call"),(f"{status(joi)} Вступление","tr_join")],
            [("✏️  Изменить текст ответа","edit_ar_text")],back()
        )
    )

@router.callback_query(F.data.startswith("tr_"))
@owner_only
async def handle_reply_toggle(cb: CallbackQuery):
    cfg=await load_config_async()
    map_={"tr_autoreply":"autoreply_on","tr_pm":"pm_autoreply","tr_mention":"mention_reply",
          "tr_sticker":"sticker_reply","tr_call":"call_reply","tr_join":"auto_join"}
    key=map_.get(cb.data)
    if key:
        cfg[key]=not cfg.get(key,False); save_config(cfg)
        await cb.answer(f"{'✅' if cfg[key] else '❌'}", show_alert=False)
    await menu_reply(cb)

@router.callback_query(F.data == "edit_ar_text")
@owner_only
async def edit_ar_text(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text(
        f"✏️  <b>Текст авто-ответа</b>\n\nОтправь новый текст:",
        reply_markup=kb([("❌  Отмена","menu_reply")])
    )
    await state.set_state(S.autoreply_text)

@router.message(S.autoreply_text)
@owner_only
async def save_ar_text(msg: Message, state: FSMContext):
    cfg=await load_config_async(); cfg["autoreply_text"]=msg.text; save_config(cfg)
    await state.clear()
    await msg.answer(f"✅  Текст обновлён!\n\n<i>{msg.text[:200]}</i>",reply_markup=build_main_menu())

# ━━ ДОСТУП ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "menu_access")
@owner_only
async def menu_access(cb: CallbackQuery):
    cfg=await load_config_async()
    blocked=cfg.get("all_blocked",False); wl_on=cfg.get("whitelist_on",False)
    wl=cfg.get("whitelist",[]); bl=cfg.get("blacklist",[])
    if blocked: mi,mt="🔴","Закрыт для всех"
    elif wl_on: mi,mt="🔒","Только белый список"
    else:       mi,mt="🔓","Открыт для всех"
    await cb.message.edit_text(
        f"{header('🔐','Управление доступом')}\n\n"
        f"Режим:  {mi}  <b>{mt}</b>\n{LINE2}\n"
        f"✅  Белый список:  <code>{len(wl)}</code> чел.\n"
        f"🚫  Чёрный список: <code>{len(bl)}</code> чел.",
        reply_markup=kb(
            [("🔓  Открыть всем","acc_open"),("🔴  Закрыть всем","acc_close")],
            [("🔒  Только вайтлист","acc_wl_on"),("📋  Показать","acc_show")],
            [("➕  В белый","acc_wl_add"),("➕  В чёрный","acc_bl_add")],back()
        )
    )

@router.callback_query(F.data.startswith("acc_"))
@owner_only
async def handle_access(cb: CallbackQuery, state: FSMContext):
    cfg=await load_config_async(); act=cb.data
    if act=="acc_open":
        cfg["all_blocked"]=False; cfg["whitelist_on"]=False; save_config(cfg)
        await cb.answer("🔓  Открыто для всех",show_alert=True); await menu_access(cb)
    elif act=="acc_close":
        cfg["all_blocked"]=True; save_config(cfg)
        await cb.answer("🔴  Закрыто для всех",show_alert=True); await menu_access(cb)
    elif act=="acc_wl_on":
        cfg["whitelist_on"]=not cfg.get("whitelist_on",False); save_config(cfg)
        s="включён" if cfg["whitelist_on"] else "выключен"
        await cb.answer(f"🔒  Вайтлист {s}",show_alert=True); await menu_access(cb)
    elif act=="acc_show":
        wl=cfg.get("whitelist",[]); bl=cfg.get("blacklist",[])
        ws="\n".join(f"  ✅  <code>{u}</code>" for u in wl[:15]) or "  <i>пусто</i>"
        bs="\n".join(f"  🚫  <code>{u}</code>" for u in bl[:15]) or "  <i>пусто</i>"
        await cb.message.edit_text(
            f"{header('📋','Списки доступа')}\n\n<b>Белый ({len(wl)}):</b>\n{ws}\n\n<b>Чёрный ({len(bl)}):</b>\n{bs}",
            reply_markup=kb(back("menu_access"))
        )
    elif act=="acc_wl_add":
        await cb.message.edit_text("➕  Введи <b>user_id</b> для белого списка:",reply_markup=kb([("❌","menu_access")]))
        await state.set_state(S.whitelist_add)
    elif act=="acc_bl_add":
        await cb.message.edit_text("➕  Введи <b>user_id</b> для чёрного списка:",reply_markup=kb([("❌","menu_access")]))
        await state.set_state(S.blacklist_add)

@router.message(S.whitelist_add)
@owner_only
async def save_wl(msg: Message, state: FSMContext):
    try:
        uid=int(msg.text.strip()); cfg=await load_config_async()
        wl=cfg.get("whitelist",[]); 
        if uid not in wl: wl.append(uid)
        cfg["whitelist"]=wl; save_config(cfg); await state.clear()
        await msg.answer(f"✅  <code>{uid}</code> в белом списке",reply_markup=build_main_menu())
    except: await msg.answer("❌  Введи числовой ID")

@router.message(S.blacklist_add)
@owner_only
async def save_bl(msg: Message, state: FSMContext):
    try:
        uid=int(msg.text.strip()); cfg=await load_config_async()
        bl=cfg.get("blacklist",[]); 
        if uid not in bl: bl.append(uid)
        cfg["blacklist"]=bl; save_config(cfg); await state.clear()
        await msg.answer(f"🚫  <code>{uid}</code> в чёрном списке",reply_markup=build_main_menu())
    except: await msg.answer("❌  Введи числовой ID")

# ━━ ПЕРСОНА ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PERSONA_PRESETS = {
    "business":("💼","Деловой","Краткий, профессиональный"),
    "friend":  ("😎","Дружеский","Неформальный, с юмором"),
    "expert":  ("🎓","Эксперт","Глубокий анализ, факты"),
    "cold":    ("🧊","Холодный","Минимум слов, только суть"),
    "warm":    ("❤️","Тёплый","Заботливый, внимательный"),
}

@router.callback_query(F.data == "menu_persona")
@owner_only
async def menu_persona(cb: CallbackQuery):
    cfg=await load_config_async(); on=cfg.get("persona_on",False)
    name=cfg.get("persona_name","—"); desc=cfg.get("persona_desc","")[:80] or "—"
    toggle="🟢  Включить" if not on else "🔴  Выключить"
    await cb.message.edit_text(
        f"{header('🎭','Персона — Тайный режим')}\n\n"
        f"Статус:  {status(on)}  <b>{'Активна' if on else 'Выключена'}</b>\n{LINE2}\n"
        f"👤  Имя:  <code>{name}</code>\n📝  <i>{desc}</i>",
        reply_markup=kb(
            [(toggle,"persona_toggle")],[("✏️  Своя персона","persona_custom")],
            [("💼  Деловой","persona_p_business"),("😎  Дружеский","persona_p_friend")],
            [("🎓  Эксперт","persona_p_expert"),("🧊  Холодный","persona_p_cold")],
            [("❤️  Тёплый","persona_p_warm")],back()
        )
    )

@router.callback_query(F.data == "persona_toggle")
@owner_only
async def persona_toggle(cb: CallbackQuery):
    cfg=await load_config_async()
    if not cfg.get("persona_name") and not cfg.get("persona_on"):
        await cb.answer("⚠️  Сначала задай персону!",show_alert=True); return
    cfg["persona_on"]=not cfg.get("persona_on",False); save_config(cfg)
    s="активирована ✅" if cfg["persona_on"] else "деактивирована ❌"
    await cb.answer(f"🎭  Персона {s}",show_alert=True); await menu_persona(cb)

@router.callback_query(F.data.startswith("persona_p_"))
@owner_only
async def persona_preset(cb: CallbackQuery):
    p=cb.data.replace("persona_p_","")
    if p not in PERSONA_PRESETS: return
    emoji,name,desc=PERSONA_PRESETS[p]; cfg=await load_config_async()
    cfg["persona_name"]=name
    cfg["persona_desc"]=f"Ты {name.lower()}. {desc}. Отвечай естественно, не говори что ты ИИ."
    save_config(cfg); await cb.answer(f"✅  {emoji} {name}",show_alert=True); await menu_persona(cb)

@router.callback_query(F.data == "persona_custom")
@owner_only
async def persona_custom(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text(f"{header('🎭','Своя персона')}\n\nВведи <b>имя</b>:",reply_markup=kb([("❌","menu_persona")]))
    await state.set_state(S.persona_name)

@router.message(S.persona_name)
@owner_only
async def save_persona_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text)
    await msg.answer(f"👤  <b>{msg.text}</b>\n\nТеперь введи <b>описание</b> (характер, стиль):")
    await state.set_state(S.persona_desc)

@router.message(S.persona_desc)
@owner_only
async def save_persona_desc(msg: Message, state: FSMContext):
    data=await state.get_data(); cfg=await load_config_async()
    cfg["persona_name"]=data["name"]; cfg["persona_desc"]=msg.text; save_config(cfg)
    await state.clear()
    await msg.answer(f"✅  <b>Персона создана!</b>\n\n👤  {data['name']}\n📝  <i>{msg.text[:150]}</i>",reply_markup=build_main_menu())

# ━━ ПАМЯТЬ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "menu_memory")
@owner_only
async def menu_memory(cb: CallbackQuery):
    cfg=await load_config_async()
    mem=cfg.get("memory_on",True); depth=cfg.get("memory_depth",8)
    hdepth=cfg.get("history_depth",20); summ=cfg.get("auto_summary",True)
    people=cfg.get("people_memory",True)
    try: pcount=len(await people_all())
    except: pcount="?"
    await cb.message.edit_text(
        f"{header('🧠','Система памяти')}\n\n"
        f"{status(mem)}  Память диалогов\n{status(summ)}  Авто-саммари\n{status(people)}  О людях\n{LINE2}\n"
        f"🔢  Глубина памяти:  <code>{depth}</code> сообщений\n"
        f"📜  История чата:    <code>{hdepth}</code> сообщений\n"
        f"👥  Людей в памяти:  <code>{pcount}</code>",
        reply_markup=kb(
            [(f"{status(mem)} Память","tmem_memory"),(f"{status(summ)} Саммари","tmem_summary")],
            [(f"{status(people)} О людях","tmem_people")],
            [("🔢  Глубина памяти","nmem_depth"),("📜  История","nmem_hist")],
            [("👥  Список людей","mem_people_list")],
            [("🗑️  Очистить память","mem_clear_confirm")],back()
        )
    )

@router.callback_query(F.data.startswith("tmem_"))
@owner_only
async def toggle_mem(cb: CallbackQuery):
    cfg=await load_config_async()
    map_={"tmem_memory":"memory_on","tmem_summary":"auto_summary","tmem_people":"people_memory"}
    key=map_.get(cb.data)
    if key: cfg[key]=not cfg.get(key,True); save_config(cfg); await cb.answer(f"{'✅' if cfg[key] else '❌'}",show_alert=False)
    await menu_memory(cb)

@router.callback_query(F.data.startswith("nmem_"))
@owner_only
async def num_mem(cb: CallbackQuery, state: FSMContext):
    labels={"nmem_depth":("🔢  Глубина памяти","memory_depth",5,64),"nmem_hist":("📜  Глубина истории","history_depth",10,200)}
    label,key,mn,mx=labels[cb.data]; cfg=await load_config_async(); cur=cfg.get(key,8)
    await cb.message.edit_text(f"{label}\n\nСейчас: <code>{cur}</code>  •  Диапазон: {mn}–{mx}\n\nВведи значение:",reply_markup=kb([("❌","menu_memory")]))
    await state.update_data(num_key=key,num_min=mn,num_max=mx,num_back="menu_memory"); await state.set_state(S.numeric_input)

@router.callback_query(F.data == "mem_people_list")
@owner_only
async def mem_people_list(cb: CallbackQuery):
    try:
        people=await people_all()
        if not people: await cb.answer("👥  Пусто",show_alert=True); return
        sorted_p=sorted(people.items(),key=lambda x:x[1].get("messages_count",0),reverse=True)
        lines=[f"{header('👥',f'Люди ({len(people)})')}\n"]
        for uid,p in sorted_p[:12]:
            name=p.get("name","?"); cnt=p.get("messages_count",0)
            prof=f"  •  {p['profession']}" if p.get("profession") else ""
            lines.append(f"👤  <b>{name}</b>{prof}  •  <code>{cnt}</code> смс")
        if len(people)>12: lines.append(f"\n<i>...и ещё {len(people)-12}</i>")
        await cb.message.edit_text("\n".join(lines),reply_markup=kb(back("menu_memory")))
    except Exception as e: await cb.answer(f"❌  {e}",show_alert=True)

@router.callback_query(F.data == "mem_clear_confirm")
@owner_only
async def mem_clear_confirm(cb: CallbackQuery):
    await cb.message.edit_text(
        f"⚠️  <b>Очистить всю память?</b>\n\nУдалятся все диалоги, история и профили людей.\n<i>Действие нельзя отменить!</i>",
        reply_markup=kb([("✅  Да, очистить","mem_clear_do")],[("❌  Отмена","menu_memory")])
    )

@router.callback_query(F.data == "mem_clear_do")
@owner_only
async def mem_clear_do(cb: CallbackQuery):
    for f in ["userbot_memory.json","chat_history.json","people_memory.json","episodic_memory.json","dialog_summaries.json"]:
        try: os.remove(f)
        except: pass
    await cb.answer("🗑️  Память очищена",show_alert=True); await menu_memory(cb)

# ━━ БЕЗОПАСНОСТЬ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "menu_security")
@owner_only
async def menu_security(cb: CallbackQuery):
    cfg=await load_config_async(); mat=cfg.get("mat_filter",True); fa2=cfg.get("2fa_on",False)
    enc=bool(os.getenv("MEMORY_KEY",""))
    try: total=await security_log_count(); inj=await security_log_count("injection"); code=await security_log_count("code")
    except: total=inj=code=0
    risk="🟢 Низкий" if total<5 else ("🟡 Средний" if total<20 else "🔴 Высокий")
    await cb.message.edit_text(
        f"{header('🛡️','Безопасность')}\n\n"
        f"{status(mat)}  Фильтр матов\n{status(fa2)}  2FA защита\n{status(enc)}  Шифрование памяти\n{LINE2}\n"
        f"⚠️  Уровень угрозы:   {risk}\n📊  Всего атак:       <code>{total}</code>\n"
        f"💉  Prompt injection: <code>{inj}</code>\n💻  Code injection:   <code>{code}</code>",
        reply_markup=kb(
            [(f"{status(mat)} Мат-фильтр","tsec_mat"),(f"{status(fa2)} 2FA","tsec_2fa")],
            [("📋  Лог атак","sec_log"),("🗑️  Очистить лог","sec_clear")],back()
        )
    )

@router.callback_query(F.data.startswith("tsec_"))
@owner_only
async def toggle_sec(cb: CallbackQuery):
    cfg=await load_config_async()
    map_={"tsec_mat":("mat_filter",True),"tsec_2fa":("2fa_on",False)}
    if cb.data in map_:
        key,default=map_[cb.data]; cfg[key]=not cfg.get(key,default); save_config(cfg)
        await cb.answer(f"{'✅' if cfg[key] else '❌'}  {key}",show_alert=False)
    await menu_security(cb)

@router.callback_query(F.data == "sec_log")
@owner_only
async def sec_log(cb: CallbackQuery):
    try:
        logs=await security_log_get(10)
        if not logs: await cb.answer("📋  Лог пуст",show_alert=True); return
        lines=[f"{header('🛡️',f'Атаки ({len(logs)})')}\n"]
        for e in logs:
            emoji="💉" if "injection" in e.get("type","") else "💻"
            lines.append(f"{emoji}  <b>{e['type']}</b>\n   🕐 {e['date']}  •  ID: <code>{e['uid']}</code>\n   <i>{e['text'][:60]}</i>")
        await cb.message.edit_text("\n\n".join(lines),reply_markup=kb(back("menu_security")))
    except Exception as e: await cb.answer(f"❌  {e}",show_alert=True)

@router.callback_query(F.data == "sec_clear")
@owner_only
async def sec_clear(cb: CallbackQuery):
    try: await security_log_clear(); await cb.answer("🗑️  Лог очищен",show_alert=True)
    except Exception as e: await cb.answer(f"❌  {e}",show_alert=True)
    await menu_security(cb)

# ━━ МОНИТОРИНГ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "menu_monitor")
@owner_only
async def menu_monitor(cb: CallbackQuery):
    try: channels=await monitors_get_all()
    except: channels={}
    lines=[f"{header('📡',f'Мониторинг ({len(channels)})')}\n"]
    for ch,s in list(channels.items())[:8]:
        active=ON if s.get("active",True) else "⏸"
        kws="  •  ".join(s.get("keywords",[])) or "<i>все посты</i>"
        lines.append(f"{active}  <code>{ch}</code>\n    🔑  {kws[:60]}")
    del_btns=[(f"🗑️  {ch}",f"mon_del_{ch}") for ch in list(channels.keys())[:4]]
    rows=[del_btns[i:i+2] for i in range(0,len(del_btns),2)]
    rows.append([("➕  Добавить","mon_add")]); rows.append(back())
    await cb.message.edit_text(
        "\n\n".join(lines) if len(lines)>1 else f"{header('📡','Мониторинг')}\n\n<i>Нет мониторов</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t,callback_data=d) for t,d in row] for row in rows])
    )

@router.callback_query(F.data == "mon_add")
@owner_only
async def mon_add(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text(f"{header('📡','Добавить монитор')}\n\nВведи <b>@username</b> канала:",reply_markup=kb([("❌","menu_monitor")]))
    await state.set_state(S.monitor_chan)

@router.message(S.monitor_chan)
@owner_only
async def save_mon_chan(msg: Message, state: FSMContext):
    chan=msg.text.strip()
    if not chan.startswith("@"): chan="@"+chan
    await state.update_data(chan=chan)
    await msg.answer(f"📡  <code>{chan}</code>\n\nВведи ключевые слова через пробел или <code>/skip</code>:")
    await state.set_state(S.monitor_kw)

@router.message(S.monitor_kw)
@owner_only
async def save_mon_kw(msg: Message, state: FSMContext):
    data=await state.get_data(); chan=data["chan"]
    kws=[] if msg.text.strip()=="/skip" else msg.text.split()
    try: await monitor_set(chan,{"active":True,"keywords":kws,"added":datetime.now().strftime("%d.%m.%Y")})
    except: pass
    await state.clear()
    await msg.answer(f"✅  <b>Монитор добавлен!</b>\n\n📡  <code>{chan}</code>\n🔑  {'  •  '.join(kws) if kws else 'все посты'}",reply_markup=build_main_menu())

@router.callback_query(F.data.startswith("mon_del_"))
@owner_only
async def mon_del(cb: CallbackQuery):
    chan=cb.data.replace("mon_del_","")
    try: await monitor_delete(chan); await cb.answer(f"✅  Удалён: {chan}",show_alert=True)
    except Exception as e: await cb.answer(f"❌  {e}",show_alert=True)
    await menu_monitor(cb)

# ━━ НАПОМИНАНИЯ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "menu_reminders")
@owner_only
async def menu_reminders(cb: CallbackQuery):
    try: active=await reminders_get_active()
    except: active=[]
    lines=[f"{header('⏰',f'Напоминания ({len(active)})')}\n"]
    for r in active[:8]:
        fire=datetime.fromtimestamp(r["fire_at"]).strftime("%d.%m  %H:%M")
        lines.append(f"🕐  <code>{fire}</code>  —  {r['text'][:55]}")
    await cb.message.edit_text(
        "\n".join(lines) if active else f"{header('⏰','Напоминания')}\n\n<i>Нет активных</i>",
        reply_markup=kb([("➕  Добавить","rem_add")],[("🗑️  Удалить все","rem_clear")],back())
    )

@router.callback_query(F.data == "rem_add")
@owner_only
async def rem_add(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text(f"{header('⏰','Новое напоминание')}\n\n✏️  Введи текст:",reply_markup=kb([("❌","menu_reminders")]))
    await state.set_state(S.remind_text)

@router.message(S.remind_text)
@owner_only
async def save_rem_text(msg: Message, state: FSMContext):
    await state.update_data(text=msg.text)
    await msg.answer(f"📝  <i>{msg.text[:100]}</i>\n\n⏰  Через сколько?\n<code>30m</code>  <code>2h</code>  <code>1d</code>  <code>15:30</code>")
    await state.set_state(S.remind_time)

@router.message(S.remind_time)
@owner_only
async def save_rem_time(msg: Message, state: FSMContext):
    data=await state.get_data(); t=msg.text.strip().lower(); secs=None
    m=re.match(r'^(\d+)\s*(m|м|min|мин)$',t)
    if m: secs=int(m.group(1))*60
    m=re.match(r'^(\d+)\s*(h|ч|час)$',t)
    if m: secs=int(m.group(1))*3600
    m=re.match(r'^(\d+)\s*(d|д|день|дней)$',t)
    if m: secs=int(m.group(1))*86400
    m=re.match(r'^(\d{1,2}):(\d{2})$',t)
    if m:
        now=datetime.now(); tgt=now.replace(hour=int(m.group(1)),minute=int(m.group(2)),second=0)
        if tgt<=now: tgt=tgt.replace(day=tgt.day+1)
        secs=int((tgt-now).total_seconds())
    if not secs: await msg.answer("❌  Не понял. Пример: <code>30m</code>  <code>2h</code>  <code>15:30</code>"); return
    fire_at=datetime.now().timestamp()+secs
    fire_str=datetime.fromtimestamp(fire_at).strftime("%d.%m.%Y  %H:%M")
    try: await reminder_add(data["text"],fire_at,datetime.now().strftime("%d.%m %H:%M"))
    except: pass
    await state.clear()
    await msg.answer(f"✅  <b>Установлено!</b>\n\n🕐  <code>{fire_str}</code>\n📝  {data['text']}",reply_markup=build_main_menu())

@router.callback_query(F.data == "rem_clear")
@owner_only
async def rem_clear(cb: CallbackQuery):
    try: os.remove("reminders.json")
    except: pass
    await cb.answer("🗑️  Удалено",show_alert=True); await menu_reminders(cb)

# ━━ ФИНАНСЫ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "menu_finance")
@owner_only
async def menu_finance(cb: CallbackQuery):
    try: alerts=await alerts_get_active()
    except: alerts=[]
    lines=[f"{header('💰',f'Ценовые алерты ({len(alerts)})')}\n"]
    for a in alerts[:8]:
        arrow="📈" if a["direction"]=="above" else "📉"
        sign=">" if a["direction"]=="above" else "<"
        lines.append(f"{arrow}  <b>{a['symbol'].upper()}</b>  {sign}  <code>${a['target_price']:,.2f}</code>")
    await cb.message.edit_text(
        "\n".join(lines) if alerts else f"{header('💰','Финансы')}\n\n<i>Нет алертов</i>",
        reply_markup=kb([("📊  Обзор рынка","fin_market")],[("🗑️  Удалить алерты","fin_clear")],back())
    )

@router.callback_query(F.data == "fin_market")
@owner_only
async def fin_market(cb: CallbackQuery):
    await cb.answer("📊  Загружаю...",show_alert=False)
    coins=["bitcoin","ethereum","solana","the-open-network","binancecoin","ripple"]
    tickers=["BTC","ETH","SOL","TON","BNB","XRP"]
    lines=[f"{header('📊','Обзор рынка — Live')}\n"]
    try:
        url=f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(coins)}&vs_currencies=usd&include_24hr_change=true"
        async with aiohttp.ClientSession() as s:
            async with s.get(url,timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status==200:
                    data=await r.json()
                    for coin,ticker in zip(coins,tickers):
                        d=data.get(coin,{}); price=d.get("usd",0); change=d.get("usd_24h_change",0)
                        arrow="📈" if change>=0 else "📉"
                        lines.append(f"{arrow}  <b>{ticker}</b>  <code>${price:,.2f}</code>  <code>{change:+.1f}%</code>")
    except Exception as e: lines.append(f"<i>Ошибка: {e}</i>")
    lines.append(f"\n{LINE2}\n<i>Данные: CoinGecko</i>")
    await cb.message.edit_text("\n".join(lines),reply_markup=kb([("🔄  Обновить","fin_market")],back("menu_finance")))

@router.callback_query(F.data == "fin_clear")
@owner_only
async def fin_clear(cb: CallbackQuery):
    try: os.remove("price_alerts.json")
    except: pass
    await cb.answer("🗑️  Алерты удалены",show_alert=True); await menu_finance(cb)

# ━━ ЛЮДИ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "menu_people")
@owner_only
async def menu_people(cb: CallbackQuery):
    try: people=await people_all()
    except: people={}
    if not people:
        await cb.message.edit_text(f"{header('👥','Люди в памяти')}\n\n<i>Пока никого нет</i>",reply_markup=kb(back())); return
    sorted_p=sorted(people.items(),key=lambda x:x[1].get("messages_count",0),reverse=True)
    lines=[f"{header('👥',f'Люди ({len(people)})')}\n"]
    for uid,p in sorted_p[:10]:
        name=p.get("name","?"); cnt=p.get("messages_count",0)
        prof=f"  •  {p['profession']}" if p.get("profession") else ""
        mood=f"  {p['last_mood']}" if p.get("last_mood") else ""
        last=p.get("last_seen","")
        lines.append(f"👤  <b>{name}</b>{prof}\n    💬 {cnt} смс{mood}  •  <i>{last}</i>")
    if len(people)>10: lines.append(f"\n<i>...и ещё {len(people)-10}</i>")
    await cb.message.edit_text("\n\n".join(lines),reply_markup=kb(back()))

# ━━ СТАТИСТИКА ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "menu_stats")
@owner_only
async def menu_stats(cb: CallbackQuery):
    cfg=await load_config_async(); s=cfg.get("stats",{})
    try: sl=await kv_get("self_learning") or {}
    except: sl={}
    total=s.get("total",0); voice=s.get("voice",0); photo=s.get("photo",0); transl=s.get("translate",0)
    ver=sl.get("evolution_ver",1); topics=len(sl.get("learned_topics",[])); improv=len(sl.get("improvements",[])); sessions=sl.get("sessions",0)
    prog=min(10,ver); bar="▓"*prog+"░"*(10-prog)
    weak=sl.get("weak_areas",[]); strong=sl.get("strong_areas",[])
    text=(
        f"{header('📊','Статистика & Аналитика')}\n\n"
        f"<b>Активность:</b>\n"
        f"📨  ИИ запросов:   <code>{total}</code>\n🎤  Голосовых:     <code>{voice}</code>\n"
        f"🖼️  Фото:         <code>{photo}</code>\n🌐  Переводов:     <code>{transl}</code>\n"
        f"{LINE2}\n<b>Саморазвитие:</b>\n"
        f"🧬  Промпт: <code>v{ver}</code>  {bar}\n"
        f"📚  Тем: <code>{topics}</code>  •  💡 Рефлексий: <code>{improv}</code>  •  🔄 Сессий: <code>{sessions}</code>"
    )
    if strong: text+=f"\n{LINE2}\n✅  <b>Сильные:</b>\n"+"".join(f"  •  {s}\n" for s in strong[:3])
    if weak:   text+=f"⚠️  <b>Слабые:</b>\n"+"".join(f"  •  {w}\n" for w in weak[:3])
    await cb.message.edit_text(text,reply_markup=kb([("🗄️  DB статистика","stats_db")],back()))

@router.callback_query(F.data == "stats_db")
@owner_only
async def stats_db(cb: CallbackQuery):
    await cb.answer("🗄️  Загружаю...",show_alert=False)
    try:
        stats=await db_stats()
        if stats.get("backend")=="PostgreSQL":
            tables=stats.get("tables",{}); total=sum(tables.values())
            lines=[f"{header('🗄️','PostgreSQL — Live')}\n",f"📦  Всего записей: <code>{total}</code>\n"]
            for t,c in tables.items(): lines.append(f"  <code>{t:<22}</code>  {c}")
        else: lines=[f"{header('📁','JSON хранилище')}\n\n<i>PostgreSQL не подключён</i>"]
        await cb.message.edit_text("\n".join(lines),reply_markup=kb([("🔄  Обновить","stats_db")],back("menu_stats")))
    except Exception as e: await cb.answer(f"❌  {e}",show_alert=True)

# ━━ БАЗА ДАННЫХ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "menu_db")
@owner_only
async def menu_db(cb: CallbackQuery):
    try:
        stats=await db_stats(); backend=stats.get("backend","?")
        if backend=="PostgreSQL":
            tables=stats.get("tables",{}); total=sum(tables.values())
            lines=[f"{header('🗄️','PostgreSQL ✅')}\n",f"🔗  Railway  •  📦  <code>{total}</code> записей\n"]
            for t,c in tables.items(): lines.append(f"  •  <code>{t}</code>: {c}")
        else:
            lines=[f"{header('📁','JSON хранилище')}\n\n<i>PostgreSQL не подключён\nДобавь DATABASE_URL → Railway → New Plugin → PostgreSQL</i>"]
    except Exception as e: lines=[f"❌  Ошибка: {e}"]
    await cb.message.edit_text("\n".join(lines),reply_markup=kb([("🔄  Обновить","menu_db")],back()))

# ━━ НАСТРОЙКИ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "menu_settings")
@owner_only
async def menu_settings(cb: CallbackQuery):
    cfg=await load_config_async()
    tr=cfg.get("translate_on",False); vo=cfg.get("voice_reply",True); ph=cfg.get("photo_analysis",True)
    spy=cfg.get("spy_mode",False); tts=cfg.get("tts_reply",False); ast=cfg.get("auto_status",False)
    lnk=cfg.get("link_summary",True); delay=cfg.get("antispam_delay",6); dest=cfg.get("autodestruct",0)
    await cb.message.edit_text(
        f"{header('⚙️','Настройки')}\n\n"
        f"{status(tr)}   Авто-перевод\n{status(vo)}   Голосовые\n{status(ph)}   Анализ фото\n"
        f"{status(spy)}  Шпион удалённых\n{status(tts)}  TTS ответы\n{status(ast)}  Авто-статус\n{status(lnk)}  Саммари ссылок\n{LINE2}\n"
        f"⏱️   Задержка:      <code>{delay}с</code>\n💣   Авто-удаление: <code>{'выкл' if not dest else f'{dest}с'}</code>",
        reply_markup=kb(
            [(f"{status(tr)} Перевод","tset_translate"),(f"{status(vo)} Голос","tset_voice")],
            [(f"{status(ph)} Фото","tset_photo"),(f"{status(spy)} Шпион","tset_spy")],
            [(f"{status(tts)} TTS","tset_tts"),(f"{status(ast)} Статус","tset_autostatus")],
            [(f"{status(lnk)} Ссылки","tset_link")],
            [("⏱️  Задержка","nset_delay"),("💣  Авто-удаление","nset_autodestruct")],back()
        )
    )

@router.callback_query(F.data.startswith("tset_"))
@owner_only
async def toggle_settings(cb: CallbackQuery):
    cfg=await load_config_async()
    map_={"tset_translate":("translate_on",False),"tset_voice":("voice_reply",True),"tset_photo":("photo_analysis",True),
          "tset_spy":("spy_mode",False),"tset_tts":("tts_reply",False),"tset_autostatus":("auto_status",False),"tset_link":("link_summary",True)}
    if cb.data in map_:
        key,default=map_[cb.data]; cfg[key]=not cfg.get(key,default); save_config(cfg)
        await cb.answer(f"{'✅' if cfg[key] else '❌'}  {key}",show_alert=False)
    await menu_settings(cb)

@router.callback_query(F.data.startswith("nset_"))
@owner_only
async def num_settings(cb: CallbackQuery, state: FSMContext):
    labels={"nset_delay":("⏱️  Задержка антиспама","antispam_delay",0,60),"nset_autodestruct":("💣  Авто-удаление (сек)","autodestruct",0,86400)}
    label,key,mn,mx=labels[cb.data]; cfg=await load_config_async(); cur=cfg.get(key,0)
    await cb.message.edit_text(f"{label}\n\nСейчас: <code>{cur}</code>  •  Диапазон: {mn}–{mx}\n\nВведи значение:",reply_markup=kb([("❌","menu_settings")]))
    await state.update_data(num_key=key,num_min=mn,num_max=mx,num_back="menu_settings"); await state.set_state(S.numeric_input)

@router.message(S.numeric_input)
@owner_only
async def save_numeric(msg: Message, state: FSMContext):
    data=await state.get_data(); key=data.get("num_key",""); mn=data.get("num_min",0); mx=data.get("num_max",9999)
    try:
        val=int(msg.text.strip())
        if not (mn<=val<=mx): await msg.answer(f"❌  Введи число от {mn} до {mx}"); return
        cfg=await load_config_async(); cfg[key]=val; save_config(cfg); await state.clear()
        await msg.answer(f"✅  <b>{key}</b> = <code>{val}</code>",reply_markup=build_main_menu())
    except: await msg.answer("❌  Введи целое число")

# ━━ ПОМОЩЬ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "menu_help")
@owner_only
async def menu_help(cb: CallbackQuery):
    await cb.message.edit_text(
        f"{header('🆘','Справка')}\n\n"
        f"<b>Команды:</b>\n/start   — открыть панель\n/menu    — главное меню\n/status  — быстрый статус\n/ask     — спросить ИИ\n\n"
        f"{LINE2}\n<b>В юзерботе:</b>\n<code>.help</code>  — все команды\n<code>+вопрос</code>  — спросить ИИ\n<code>.</code>  на reply  — ответить за тебя\n\n"
        f"{LINE2}\n<b>Файлы:</b>\n<code>userbot.py</code>    — основной бот\n<code>database.py</code>   — PostgreSQL\n<code>control_bot.py</code> — эта панель",
        reply_markup=kb(back())
    )

# ━━ БЫСТРЫЙ ИИ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "quick_ask")
@owner_only
async def quick_ask(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text(f"{header('🤖','Спросить ИИ')}\n\nЗадай любой вопрос:",reply_markup=kb([("❌  Отмена","back_main")]))
    await state.set_state(S.ai_question)

@router.message(S.ai_question)
@owner_only
async def process_ai_q(msg: Message, state: FSMContext):
    await state.clear(); m=await msg.answer("🤔  <i>Думаю...</i>")
    try:
        GROQ_KEY=os.getenv("GROQ_API_KEY","")
        if not GROQ_KEY: await m.edit_text("❌  GROQ_API_KEY не задан"); return
        async with aiohttp.ClientSession() as s:
            async with s.post("https://api.groq.com/openai/v1/chat/completions",
                json={"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":msg.text}],"max_tokens":1000},
                headers={"Authorization":f"Bearer {GROQ_KEY}"},timeout=aiohttp.ClientTimeout(total=30)) as r:
                data=await r.json(); answer=data["choices"][0]["message"]["content"]
        await m.edit_text(f"🤖  <b>Ответ ИИ:</b>\n\n{answer[:3500]}",
            reply_markup=kb([("🔄  Ещё вопрос","quick_ask"),("🏠  Меню","back_main")]))
    except Exception as e: await m.edit_text(f"❌  Ошибка: {e}")

# ━━ КОМАНДЫ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.message(Command("status"))
@owner_only
async def cmd_status(msg: Message):
    cfg=await load_config_async(); ai=cfg.get("active_ai","groq")
    ar=status(cfg.get("autoreply_on",False)); mem=status(cfg.get("memory_on",True)); mat=status(cfg.get("mat_filter",True))
    now=datetime.now().strftime("%d.%m.%Y  %H:%M")
    try:
        s=await db_stats(); db_s="PostgreSQL ✅" if s.get("backend")=="PostgreSQL" else "JSON 📁"
    except: db_s="?"
    try: sl=await kv_get("self_learning") or {}; ver=sl.get("evolution_ver",1); tot=sl.get("total_messages",0)
    except: ver=1; tot=0
    await msg.answer(
        f"╔══════════════════════════╗\n║  🎛️  <b>USERBOT STATUS</b>       ║\n╚══════════════════════════╝\n\n"
        f"🕐  <i>{now}</i>\n{LINE}\n"
        f"🤖  ИИ:          <code>{ai.upper()}</code>\n💬  Авто-ответ:  {ar}\n🧠  Память:      {mem}\n🛡️  Мат-фильтр: {mat}\n🗄️  База:        {db_s}\n{LINE2}\n"
        f"🧬  Промпт: <code>v{ver}</code>  •  📨  <code>{tot}</code> запросов",
        reply_markup=build_main_menu()
    )

@router.message(Command("ask"))
@owner_only
async def cmd_ask(msg: Message):
    question=msg.text.replace("/ask","",1).strip()
    if not question: await msg.answer("Использование: <code>/ask твой вопрос</code>"); return
    m=await msg.answer("🤔  <i>Думаю...</i>")
    try:
        GROQ_KEY=os.getenv("GROQ_API_KEY","")
        if not GROQ_KEY: await m.edit_text("❌  GROQ_API_KEY не задан"); return
        async with aiohttp.ClientSession() as s:
            async with s.post("https://api.groq.com/openai/v1/chat/completions",
                json={"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":question}],"max_tokens":1000},
                headers={"Authorization":f"Bearer {GROQ_KEY}"},timeout=aiohttp.ClientTimeout(total=30)) as r:
                data=await r.json(); answer=data["choices"][0]["message"]["content"]
        await m.edit_text(f"🤖  <b>Ответ:</b>\n\n{answer[:3500]}")
    except Exception as e: await m.edit_text(f"❌  {e}")

# ━━ ЗАПУСК ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def config_refresh_loop():
    """Каждые 10 сек обновляет кэш конфига из DB"""
    while True:
        await asyncio.sleep(10)
        try:
            await load_config_async()
        except: pass

async def main():
    log.info("🎛️  Control Bot v6.0 запускается...")
    await init_db()
    # Загружаем конфиг из DB при старте
    await load_config_async()
    log.info("✅  Конфиг загружен из PostgreSQL")
    await bot.delete_webhook(drop_pending_updates=True)
    # Фоновое обновление кэша
    asyncio.create_task(config_refresh_loop())
    try:
        await bot.send_message(OWNER_ID,
            f"🟢  <b>Панель управления запущена!</b>\n\n🕐  {datetime.now().strftime('%d.%m.%Y  %H:%M')}\n\nНажми /start")
    except: pass
    log.info(f"✅  Control Bot запущен!  OWNER_ID={OWNER_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
