import json, os, datetime, asyncio, tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import Conflict, BadRequest

# ───── УБИВАЕМ 409 CONFLICT НАВСЕГДА ─────
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 737408288

async def kill_old_sessions():
    for _ in range(3):
        try:
            app = Application.builder().token(TOKEN).build()
            await app.initialize()
            await app.bot.get_updates(offset=-1, timeout=1)
            for _ in range(30):
                await app.bot.get_updates(offset=999999999, timeout=1)
            await app.shutdown()
        except:
            await asyncio.sleep(1)

asyncio.run(kill_old_sessions())

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
                schedule[day] = [n for n in data.get(day, []) if "GroupAnonymousBot" not in n and "1087968824" not in n]
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

# ───── ПРОВЕРКА НА АНОНИМНОГО АДМИНА ─────
def is_anonymous_admin(user):
    return (user.id == 1087968824 or 
            (user.username and "GroupAnonymousBot" in user.username) or
            user.first_name == "Group")

# ───── + / - : МОЖНО ДОБАВЛЯТЬ ГОСТЕЙ ДО 12 СКОЛЬКО УГОДНО РАЗ ─────
async def plus_minus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_anonymous_admin(user):
        return

    text = update.message.text.strip()
    if not text or text[0] not in "+-":
        return

    try:
        count = 1 if len(text) == 1 else int(text[1:] or "1")
        if count < 1 or count > 20: count = 1
    except:
        return

    is_plus = text[0] == "+"
    d = day()
    base_name = user.first_name + (f" (@{user.username})" if user.username and "GroupAnonymousBot" not in user.username else "")
    main_name = f"{base_name} ({user.id})"

    added = removed = 0

    if is_plus:
        # Определяем, сколько уже занято этим человеком (включая гостей)
        current_guests = sum(1 for x in schedule[d] if x.startswith(base_name + " +") or x == main_name)
        available_slots = MAX - len(schedule[d])

        # Сколько реально можем добавить
        can_add = min(count, available_slots)

        if can_add == 0:
            await update.message.reply_text("Мест нет!")
            return

        # Добавляем гостей по порядку: +1, +2, +3...
        next_guest_num = current_guests + 1 if current_guests > 0 else 1
        for i in range(can_add):
            guest_name = f"{base_name} +{next_guest_num + i}"
            if guest_name not in schedule[d]:
                schedule[d].append(guest_name)
                added += 1

        save()
        await update.message.reply_text(f"Добавил +{added}!\nСейчас: {len(schedule[d])}/12")

    else:  # отмена
        # Удаляем последних гостей (с конца), потом основного
        removed_names = []
        for i in range(20, 0, -1):
            guest_name = f"{base_name} +{i}" if i > 1 else main_name
            if guest_name in schedule[d]:
                schedule[d].remove(guest_name)
                removed_names.append(guest_name)
                removed += 1
                if removed >= count:
                    break
        if removed:
            save()
            await update.message.reply_text(f"Отменил -{removed}\nСейчас: {len(schedule[d])}/12")
        else:
            await update.message.reply_text("Ты не был записан")

# ───── МЕНЮ И СТАРТ ─────
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_anonymous_admin(update.effective_user):
        return
    d = day()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("ЗАПИСАТЬСЯ", callback_data="join"),
         InlineKeyboardButton("ОТМЕНИТЬ", callback_data="cancel")],
        [InlineKeyboardButton("РАСПИСАНИЕ", callback_data="view")]
    ])
    await update.message.reply_text(
        f"Волейбол — {d} в {'21:00' if d=='Вторник' else '20:00'}\n\n"
        "Можешь добавлять гостей сколько угодно раз: +1 +2 +3\n"
        "До 12 человек всего!\n"
        "Пиши: +  +1  +3  +6  -  -2",
        reply_markup=kb
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        context.application.bot_data["group_chat_id"] = update.effective_chat.id
    await menu(update, context)

# ───── АДМИНКА В ЛИЧКЕ ─────
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or update.effective_chat.type != "private":
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Очистить ВТ", callback_data="clear_Вторник"),
         InlineKeyboardButton("Очистить ЧТ", callback_data="clear_Четверг")],
        [InlineKeyboardButton("Напомнить СЕЙЧАС", callback_data="remind_now")]
    ])
    await update.message.reply_text(
        f"АДМИНКА\nВТ: {len(schedule['Вторник'])}/12 | ЧТ: {len(schedule['Четверг'])}/12",
        reply_markup=kb
    )

# ───── КНОПКИ (с защитой от ошибок) ─────
async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    if is_anonymous_admin(user):
        return

    d = day()
    base_name = user.first_name + (f" (@{user.username})" if user.username and "GroupAnonymousBot" not in user.username else "")
    name = f"{base_name} ({user.id})"

    main_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("ЗАПИСАТЬСЯ", callback_data="join"),
         InlineKeyboardButton("ОТМЕНИТЬ", callback_data="cancel")],
        [InlineKeyboardButton("РАСПИСАНИЕ", callback_data="view")]
    ])

    current_text = (q.message.text or "").strip()

    try:
        if user.id == ADMIN_ID:
            if q.data.startswith("clear_"):
                день = q.data.split("_", 1)[1]
                schedule[день].clear()
                save()
                new_text = f"{день} очищен!"
                if new_text != current_text:
                    await q.edit_message_text(new_text)
                return
            if q.data == "remind_now":
                chat_id = context.application.bot_data.get("group_chat_id")
                if not chat_id:
                    await q.edit_message_text("Группа не найдена")
                    return
                msg = f"*ТРЕНИРОВКА СЕЙЧАС!*\n{d} в {'21:00' if d=='Вторник' else '20:00'}\n\nИдут: {len(schedule[d])}/12\n"
                for i, u in enumerate(schedule[d], 1):
                    msg += f"{i}. {u.split(' (')[0]}\n"
                await context.bot.send_message(chat_id, msg, parse_mode="Markdown")
                await q.edit_message_text("Напоминание отправлено!")
                return

        if q.data == "join":
            if name in schedule[d] or any(x.startswith(base_name + " +") for x in schedule[d]):
                new_text = "Ты уже записан!\nДобавляй гостей: +1 +2 +3"
            elif len(schedule[d]) >= MAX:
                new_text = "Мест нет!"
            else:
                schedule[d].append(name)
                save()
                new_text = f"Записан на {d}!\n{len(schedule[d])}/{MAX}"
            if new_text != current_text:
                await q.edit_message_text(new_text, reply_markup=main_kb)

        elif q.data == "cancel":
            removed = False
            for entry in list(schedule[d]):
                if entry == name or entry.startswith(base_name + " +"):
                    schedule[d].remove(entry)
                    removed = True
            if removed:
                save()
                new_text = f"Отменено\n{len(schedule[d])}/{MAX}"
            else:
                new_text = "Ты не записан."
            if new_text != current_text:
                await q.edit_message_text(new_text, reply_markup=main_kb)

        elif q.data == "view":
            txt = "*РАСПИСАНИЕ*\n\n"
            for день in ["Вторник", "Четверг"]:
                time = "21:00" if день == "Вторник" else "20:00"
                txt += f"*{день} {time}* — {len(schedule[день])}/12\n"
                for i, u in enumerate(schedule[день], 1):
                    txt += f"{i}. {u.split(' (')[0]}\n"
                txt += "\n"
            if txt.strip() != current_text:
                await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=main_kb)

    except BadRequest as e:
        if "message is not modified" not in str(e).lower():
            print(f"Ошибка: {e}")

# ───── ЗАПУСК ─────
async def main():
    app = Application.builder().token(TOKEN).concurrent_updates(True).build()

    try:
        await app.bot.set_my_commands([
            BotCommand("start", "Запись на волейбол"),
            BotCommand("menu", "Меню"),
            BotCommand("admin", "Админка")
        ])
        await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except: pass

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, plus_minus))

    await app.initialize()
    await app.start()

    while True:
        try:
            await app.updater.start_polling(drop_pending_updates=True, timeout=30)
            await asyncio.Event().wait()
        except Conflict:
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Ошибка: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
