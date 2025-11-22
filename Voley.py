import json, os, asyncio, logging, datetime as dt
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from telegram.ext import Application, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 737408288
FILE = "/data/data.json"
MAX = 12
BLOCKED_IDS = {1087968824, 136817688}

schedule = {"Вторник": [], "Четверг": []}

# Удаляем старый файл — убиваем GroupAnonymousBot навсегда
if os.path.exists(FILE):
    try: os.remove(FILE); logging.info("Старый data.json удалён — чистый старт")
    except: pass

def load():
    global schedule
    try:
        data = json.load(open(FILE, "r", encoding="utf-8"))
        for day in schedule:
            schedule[day] = [e for e in data.get(day, []) if int(e.split("(")[-1].split(")")[0]) not in BLOCKED_IDS]
        save()
    except:
        schedule = {"Вторник": [], "Четверг": []}
        save()

def save():
    try:
        open(FILE, "w", encoding="utf-8").write(json.dumps(schedule, ensure_ascii=False, indent=2))
    except: pass

load()

def day():
    now = dt.datetime.utcnow() + dt.timedelta(hours=5)
    w = now.weekday()
    if w in [0, 1]: return "Вторник"
    if w in [2, 3]: return "Четверг"
    return "Вторник"

def blocked(u):
    return u.id in BLOCKED_IDS or u.first_name == "Group" or "GroupAnonymousBot" in (u.username or "")

# Автоочистка 00:01 по ЕКБ
async def auto_clear_task():
    while True:
        now = dt.datetime.utcnow() + dt.timedelta(hours=5)
        if now.hour == 0 and now.minute == 1 and now.second < 10:
            if now.weekday() == 2: schedule["Вторник"].clear(); save(); logging.info("ОЧИСТКА ВТ 00:01 ЕКБ")
            if now.weekday() == 4: schedule["Четверг"].clear(); save(); logging.info("ОЧИСТКА ЧТ 00:01 ЕКБ")
        await asyncio.sleep(10)

# Хендлеры
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        context.application.bot_data["group"] = update.effective_chat.id
    await update.message.reply_text(
        f"Волейбол — {day()} в {'21:00' if day()=='Вторник' else '20:00'}\n\nПиши + или кнопки",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ЗАПИСАТЬСЯ", callback_data="j"), InlineKeyboardButton("ОТМЕНИТЬ", callback_data="c")],
            [InlineKeyboardButton("РАСПИСАНИЕ", callback_data="v")]
        ]))

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or update.effective_chat.type != "private": return
    await update.message.reply_text(
        f"АДМИНКА\nВТ: {len(schedule['Вторник'])}/12 | ЧТ: {len(schedule['Четверг'])}/12",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Очистить ВТ", callback_data="clear_Вторник"), InlineKeyboardButton("Очистить ЧТ", callback_data="clear_Четверг")],
            [InlineKeyboardButton("Напомнить СЕЙЧАС", callback_data="remind")]
        ]))

async def plus_minus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if blocked(update.effective_user): return
    text = update.message.text.strip()
    if text[0] not in "+-": return
    cnt = min(int(text[1:]) if text[1:].isdigit() else 1, 20)
    d = day()
    name = update.effective_user.first_name + (f" (@{update.effective_user.username})" if update.effective_user.username else "")
    entry = f"{name} ({update.effective_user.id})"

    if text[0] == "+":
        if len(schedule[d]) >= MAX: await update.message.reply_text("Мест нет!"); return
        added = 0
        for _ in range(cnt):
            if len(schedule[d]) >= MAX: break
            schedule[d].append(entry); added += 1
        save()
        await update.message.reply_text(f"Добавил +{added} → {len(schedule[d])}/12")
    else:
        removed = 0
        while entry in schedule[d] and removed < cnt:
            schedule[d].remove(entry); removed += 1
        if removed: save()
        await update.message.reply_text(f"Отменил -{removed} → {len(schedule[d])}/12" if removed else "Ты не записан")

async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if blocked(q.from_user): return
    d = day()
    name = q.from_user.first_name + (f" (@{q.from_user.username})" if q.from_user.username else "")
    entry = f"{name} ({q.from_user.id})"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("ЗАПИСАТЬСЯ",callback_data="j"), InlineKeyboardButton("ОТМЕНИТЬ",callback_data="c")],[InlineKeyboardButton("РАСПИСАНИЕ",callback_data="v")]])

    if q.from_user.id == ADMIN_ID:
        if q.data.startswith("clear_"):
            schedule[q.data.split("_")[1]].clear(); save(); await q.edit_message_text("Очищено!")
            return
        if q.data == "remind":
            if g := context.application.bot_data.get("group"):
                msg = f"*ТРЕНИРОВКА СЕЙЧАС!*\n{d} в {'21:00' if d=='Вторник' else '20:00'}\n\nИдут: {len(schedule[d])}/12\n" + "\n".join(f"{i}. {x.split(' (')[0]}" for i,x in enumerate(schedule[d],1))
                await context.bot.send_message(g, msg, parse_mode="Markdown")
                await q.edit_message_text("Напомнил!")
            return

    if q.data == "j":
        if any(entry in x for x in schedule[d]): await q.edit_message_text("Ты уже записан!", reply_markup=kb)
        elif len(schedule[d]) >= MAX: await q.edit_message_text("Мест нет!", reply_markup=kb)
        else: schedule[d].append(entry); save(); await q.edit_message_text(f"Записан → {len(schedule[d])}/12", reply_markup=kb)
    elif q.data == "c":
        was = entry in schedule[d]
        while entry in schedule[d]: schedule[d].remove(entry)
        if was: save()
        await q.edit_message_text(f"Отменено → {len(schedule[d])}/12" if was else "Ты не записан", reply_markup=kb)
    elif q.data == "v":
        txt = "*РАСПИСАНИЕ*\n\n"
        for день in ["Вторник","Четверг"]:
            txt += f"*{день} {'21:00' if день=='Вторник' else '20:00'}* — {len(schedule[день])}/12\n"
            for i,x in enumerate(schedule[день],1): txt += f"{i}. {x.split(' (')[0]}\n"
            txt += "\n"
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)

# НЕПАДАЮЩИЙ ЗАПУСК
async def main():
    while True:
        try:
            app = Application.builder().token(TOKEN).concurrent_updates(False).build()
            await app.initialize()
            await app.bot.set_my_commands([BotCommand("start","Меню"), BotCommand("admin","Админка")])

            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("admin", admin_panel))
            app.add_handler(CallbackQueryHandler(btn))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, plus_minus))

            asyncio.create_task(auto_clear_task())

            await app.start()
            await app.updater.start_polling(drop_pending_updates=True, poll_interval=1.0)
            logging.info("БОТ ЗАПУЩЕН — 409 УБИТ НАВСЕГДА")
            await asyncio.Event().wait()

        except Exception as e:
            if "Conflict" in str(e):
                logging.warning("409 Conflict — перезапускаемся через 15 сек...")
                await asyncio.sleep(15)
            else:
                logging.error(f"Ошибка: {e} — перезапуск через 10 сек")
                await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
