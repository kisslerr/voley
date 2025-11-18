import json, os, datetime, asyncio, tempfile, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import Conflict, BadRequest

# Логи
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 737408288

# ───── САМЫЙ ЖЁСТКИЙ УБИЙЦА 409 В 2025 ГОДУ (РАБОТАЕТ НА BOTHOST.RU) ─────
async def kill_409_forever():
    for _ in range(8):  # 8 попыток — точно убьёт всё
        try:
            app = Application.builder().token(TOKEN).concurrent_updates(False).build()
            await app.initialize()
            await app.start()
            # Это ломает ВСЕ старые сессии
            for i in range(200):
                try:
                    await app.bot.get_updates(offset=999999999 if i > 0 else -1, timeout=1)
                except:
                    pass
            await app.stop()
            await app.shutdown()
            logger.info("Все старые сессии убиты")
        except:
            pass
        await asyncio.sleep(0.7)

# Запускаем перед стартом
try:
    asyncio.run(kill_409_forever())
except:
    pass

# ───── ДАННЫЕ ─────
FILE = "/data/data.json"
MAX = 12
schedule = {"Вторник": [], "Четверг": []}

def load():
    global schedule
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for day in schedule:
                old = data.get(day, [])
                schedule[day] = [n for n in old if "1087968824" not in n and "GroupAnonymousBot" not in n]
            save()  # Сразу перезаписываем чистым
    except:
        schedule = {"Вторник": [], "Четверг": []}

def save():
    try:
        with tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8', dir='/data') as f:
            json.dump(schedule, f, ensure_ascii=False, indent=2)
            temp_name = f.name
        os.replace(temp_name, FILE)
    except: pass

load()

def day():
    w = datetime.datetime.utcnow().weekday()
    return "Вторник" if w in [0,1,4,5,6] else "Четверг"

def is_anon(user):
    return user.id == 1087968824 or (user.username and "GroupAnonymousBot" in user.username) or user.first_name == "Group"

# ───── + / - ─────
async def plus_minus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_anon(update.effective_user): return
    text = update.message.text.strip()
    if not text or text[0] not in "+-": return
    try: count = 1 if len(text) == 1 else int(text[1:] or "1")
    except: return
    if count < 1 or count > 20: count = 1

    is_plus = text[0] == "+"
    d = day()
    base = update.effective_user.first_name + (f" (@{update.effective_user.username})" if update.effective_user.username else "")
    main = f"{base} ({update.effective_user.id})"

    if is_plus:
        if len(schedule[d]) >= MAX:
            await update.message.reply_text("Мест нет!")
            return
        can_add = min(count, MAX - len(schedule[d]))
        next_num = 1
        while any(f"{base} +{next_num}" in x for x in schedule[d]):
            next_num += 1
        added = 0
        for i in range(can_add):
            schedule[d].append(f"{base} +{next_num + i}")
            added += 1
        if main not in schedule[d] and not any(x.startswith(base + " +") for x in schedule[d]):
            if len(schedule[d]) < MAX:
                schedule[d].append(main)
                added += 1
        save()
        await update.message.reply_text(f"Добавил +{added}!\nСейчас: {len(schedule[d])}/12")
    else:
        removed = 0
        for i in range(99, 0, -1):
            g = f"{base} +{i}"
            if g in schedule[d]:
                schedule[d].remove(g)
                removed += 1
                if removed >= count: break
        if removed < count and main in schedule[d]:
            schedule[d].remove(main)
            removed += 1
        if removed:
            save()
            await update.message.reply_text(f"Отменил -{removed}\nСейчас: {len(schedule[d])}/12")
        else:
            await update.message.reply_text("Ты не был записан")

# ───── МЕНЮ / СТАРТ / АДМИНКА / КНОПКИ ─────
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_anon(update.effective_user): return
    d = day()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("ЗАПИСАТЬСЯ", callback_data="join"), InlineKeyboardButton("ОТМЕНИТЬ", callback_data="cancel")],
        [InlineKeyboardButton("РАСПИСАНИЕ", callback_data="view")]
    ])
    await update.message.reply_text(
        f"Волейбол — {d} в {'21:00' if d=='Вторник' else '20:00'}\n\n"
        "Пиши + +1 +2 +5 — добавляй сколько угодно!\n"
        "До 12 человек!",
        reply_markup=kb
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        context.application.bot_data["group_chat_id"] = update.effective_chat.id
    await menu(update, context)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or update.effective_chat.type != "private":
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Очистить ВТ", callback_data="clear_Вторник"), InlineKeyboardButton("Очистить ЧТ", callback_data="clear_Четверг")],
        [InlineKeyboardButton("Напомнить СЕЙЧАС", callback_data="remind_now")]
    ])
    await update.message.reply_text(
        f"АДМИНКА\nВТ: {len(schedule['Вторник'])}/12 | ЧТ: {len(schedule['Четверг'])}/12",
        reply_markup=kb
    )

async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if is_anon(q.from_user): return

    d = day()
    base = q.from_user.first_name + (f" (@{q.from_user.username})" if q.from_user.username else "")
    name = f"{base} ({q.from_user.id})"
    main_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("ЗАПИСАТЬСЯ", callback_data="join"), InlineKeyboardButton("ОТМЕНИТЬ", callback_data="cancel")],
        [InlineKeyboardButton("РАСПИСАНИЕ", callback_data="view")]
    ])

    try:
        if q.from_user.id == ADMIN_ID:
            if q.data.startswith("clear_"):
                day_name = q.data.split("_", 1)[1]
                schedule[day_name].clear()
                save()
                await q.edit_message_text(f"{day_name} очищен!")
                return
            if q.data == "remind_now":
                chat_id = context.application.bot_data.get("group_chat_id")
                if chat_id:
                    msg = f"*ТРЕНИРОВКА СЕЙЧАС!*\n{d} в {'21:00' if d=='Вторник' else '20:00'}\n\nИдут: {len(schedule[d])}/12\n"
                    for i, u in enumerate(schedule[d], 1):
                        msg += f"{i}. {u.split(' (')[0]}\n"
                    await context.bot.send_message(chat_id, msg, parse_mode="Markdown")
                    await q.edit_message_text("Напоминание отправлено!")
                return

        text = (q.message.text or "").strip()

        if q.data == "join":
            if name in schedule[d] or any(x.startswith(base + " +") for x in schedule[d]):
                new = "Ты уже записан!\nПиши +1 +2 +3"
            elif len(schedule[d]) >= MAX:
                new = "Мест нет!"
            else:
                schedule[d].append(name)
                save()
                new = f"Записан на {d}!\n{len(schedule[d])}/{MAX}"
            if new != text:
                await q.edit_message_text(new, reply_markup=main_kb)

        elif q.data == "cancel":
            removed = any(schedule[d].remove(x) for x in list(schedule[d]) if x == name or x.startswith(base + " +"))
            new = f"Отменено\n{len(schedule[d])}/{MAX}" if removed else "Ты не записан."
            if removed: save()
            if new != text:
                await q.edit_message_text(new, reply_markup=main_kb)

        elif q.data == "view":
            txt = "*РАСПИСАНИЕ*\n\n"
            for день in ["Вторник", "Четверг"]:
                t = "21:00" if день == "Вторник" else "20:00"
                txt += f"*{день} {t}* — {len(schedule[день])}/12\n"
                for i, u in enumerate(schedule[день], 1):
                    txt += f"{i}. {u.split(' (')[0]}\n"
                txt += "\n"
            if txt.strip() != text:
                await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=main_kb)

    except BadRequest as e:
        if "not modified" not in str(e).lower():
            pass

# ───── НЕПАДАЮЩИЙ ЦИКЛ ─────
async def main():
    while True:
        app = None
        try:
            app = Application.builder().token(TOKEN).concurrent_updates(False).build()

            await app.bot.set_my_commands([
                BotCommand("start", "Запись"), BotCommand("menu", "Меню"), BotCommand("admin", "Админка")
            ], scope={"type": "all_private_chats"})

            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("menu", menu))
            app.add_handler(CommandHandler("admin", admin_command))
            app.add_handler(CallbackQueryHandler(btn))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, plus_minus))

            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True, timeout=30)
            logger.info("БОТ ЖИВ И РАБОТАЕТ!")
            await asyncio.Event().wait()

        except Exception as e:
            logger.warning(f"Перезапуск из-за: {e}")
            if app:
                try: await app.stop(); await app.shutdown()
                except: pass
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
