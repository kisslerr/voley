import json
import datetime
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ==================== НАСТРОЙКИ ====================
MAX_PARTICIPANTS = 12
DATA_FILE = "schedule.json"
TIMEZONE_OFFSET = 5  # UTC+5 (Екатеринбург / Челябинск и т.д.)

# ВНИМАНИЕ! УКАЖИ СВОЙ TELEGRAM ID ЗДЕСЬ (обязательно!)
# Как узнать: напиши @userinfobot или добавь временно команду /id внизу
ADMIN_ID = 737408288  # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Время тренировок по местному времени (UTC+5)
TRAINING_TIME = {
    "Вторник": 21,   # 21:00
    "Четверг": 20,   # 20:00
}

# ===================================================
schedule = {"Вторник": [], "Четверг": []}


# ==================== ФАЙЛЫ =========================
def load_schedule():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"Вторник": [], "Четверг": []}


def save_schedule():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)


# ==================== ВРЕМЯ =========================
def now_utc5():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)


def get_nearest_day():
    weekday = now_utc5().weekday()  # 0=Пн, 1=Вт, 2=Ср, 3=Чт, 4=Пт, 5=Сб, 6=Вс
    if weekday <= 1:        # Пн или Вт → ближайший Вт
        return "Вторник"
    elif weekday <= 3:      # Ср или Чт → ближайший Чт
        return "Четверг"
    else:                   # Пт–Вс → следующий Вт
        return "Вторник"


def format_time(day):
    return f"{TRAINING_TIME[day]:02d}:00"


# ==================== КОМАНДЫ =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nearest = get_nearest_day()
    time_str = format_time(nearest)

    keyboard = [
        [InlineKeyboardButton("ЗАПИСАТЬСЯ", callback_data="join")],
        [InlineKeyboardButton("ОТМЕНИТЬ ЗАПИСЬ", callback_data="cancel")],
        [InlineKeyboardButton("РАСПИСАНИЕ", callback_data="view")],
    ]

    text = f"БЛИЖАЙШАЯ ТРЕНИРОВКА\n\n{nearest.upper()} в {time_str}"

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # Сохраняем chat_id группы для напоминаний
    if update.effective_chat.type in ["group", "supergroup"]:
        context.application.bot_data["chat_id"] = update.effective_chat.id


# ==================== АДМИНКА =======================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Доступ запрещён.")
        return

    keyboard = [
        [InlineKeyboardButton("Очистить ВТОРНИК", callback_data="clear_Вторник")],
        [InlineKeyboardButton("Очистить ЧЕТВЕРГ", callback_data="clear_Четверг")],
        [InlineKeyboardButton("Мой ID", callback_data="show_id")],
        [InlineKeyboardButton("Принудительно напомнить", callback_data="force_remind")],
    ]

    msg = (
        f"АДМИН-ПАНЕЛЬ\n\n"
        f"Вторник {format_time('Вторник')} → {len(schedule['Вторник'])}/{MAX_PARTICIPANTS}\n"
        f"Четверг {format_time('Четверг')} → {len(schedule['Четверг'])}/{MAX_PARTICIPANTS}"
    )

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


# ==================== КНОПКИ ========================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    day = get_nearest_day()

    # Формируем красивое имя
    name = user.first_name or "Без имени"
    if user.username:
        name += f" (@{user.username})"
    uid = f"{name} ({user.id})"

    if query.data == "join":
        if uid in schedule[day]:
            await query.edit_message_text(f"Ты уже записан на {day}!")
            return
        if len(schedule[day]) >= MAX_PARTICIPANTS:
            await query.edit_message_text(f"Мест нет на {day}! (12/12)")
            return

        schedule[day].append(uid)
        save_schedule()

        keyboard = [[InlineKeyboardButton("ОТМЕНИТЬ ЗАПИСЬ", callback_data="cancel")]]
        await query.edit_message_text(
            f"Записан на {day}!\n"
            f"Участников: {len(schedule[day])}/{MAX_PARTICIPANTS}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "cancel":
        if uid not in schedule[day]:
            await query.edit_message_text(f"Ты и так не записан на {day}.")
            return

        schedule[day].remove(uid)
        save_schedule()

        keyboard = [[InlineKeyboardButton("ЗАПИСАТЬСЯ", callback_data="join")]]
        await query.edit_message_text(
            f"Запись на {day} отменена.\n"
            f"Участников: {len(schedule[day])}/{MAX_PARTICIPANTS}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "view":
        msg = "*РАСПИСАНИЕ ТРЕНИРОВОК*\n\n"
        for d in ["Вторник", "Четверг"]:
            msg += f"*{d} {format_time(d)}* — {len(schedule[d])}/{MAX_PARTICIPANTS}\n"
            if schedule[d]:
                for i, u in enumerate(schedule[d], 1):
                    clean_name = u.split(" (")[0]
                    msg += f"{i}. {clean_name}\n"
            else:
                msg += "—\n"
            msg += "\n"
        await query.edit_message_text(msg, parse_mode="Markdown")

    elif query.data == "show_id":
        await query.edit_message_text(f"Твой Telegram ID:\n`{user.id}`", parse_mode="MarkdownV2")

    # === Админские кнопки ===
    elif query.data.startswith("clear_"):
        if user.id != ADMIN_ID:
            await query.answer("Ты не админ!", show_alert=True)
            return
        day_to_clear = query.data.split("_", 1)[1]
        schedule[day_to_clear].clear()
        save_schedule()
        await query.edit_message_text(f"{day_to_clear} полностью очищен!")

    elif query.data == "force_remind":
        if user.id != ADMIN_ID:
            await query.answer("Нет доступа", show_alert=True)
            return
        chat_id = context.application.bot_data.get("chat_id")
        if not chat_id:
            await query.edit_message_text("Бот не знает ID группы. Напиши /start в группе.")
            return
        await send_reminder(context, force_day=get_nearest_day())
        await query.edit_message_text("Напоминание отправлено принудительно!")


# ==================== НАПОМИНАНИЕ ЗА ЧАС ============
async def send_reminder(context: ContextTypes.DEFAULT_TYPE, force_day=None):
    day = force_day or context.job.name
    chat_id = context.job.data if not force_day else context.application.bot_data.get("chat_id")
    if not chat_id:
        return

    count = len(schedule[day])
    msg = f"*ТРЕНИРОВКА ЧЕРЕЗ 1 ЧАС!*\n\n" \
          f"{day.upper()} в {format_time(day)}\n\n" \
          f"Идут: {count}/{MAX_PARTICIPANTS}\n"

    if count > 0:
        for i, u in enumerate(schedule[day], 1):
            name = u.split(" (")[0]
            msg += f"{i}. {name}\n"
    else:
        msg += "Пока никто не записался\n"

    keyboard = [
        [InlineKeyboardButton("ЗАПИСАТЬСЯ", callback_data="join")],
        [InlineKeyboardButton("ОТМЕНИТЬ", callback_data="cancel")],
    ]

    await context.bot.send_message(
        chat_id=chat_id,
        text=msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==================== ПЛАНИРОВЩИК ==================
def schedule_reminders(app):
    now = now_utc5()
    days_map = {"Вторник": 1, "Четверг": 3}  # понедельник = 0

    for day_name, hour in TRAINING_TIME.items():
        target = now.replace(hour=hour - 1, minute=0, second=0, microsecond=0)

        # Если время уже прошло — переносим на следующую неделю
        while target <= now or target.weekday() != days_map[day_name]:
            target += datetime.timedelta(days=1)

        # Если всё ещё не то число недели — подгоняем
        while target.weekday() != days_map[day_name]:
            target += datetime.timedelta(days=1)

        app.job_queue.run_once(
            callback=send_reminder,
            when=target,
            name=day_name,
            data=app.bot.booking_data.get("chat_id")
        )
        print(f"Напоминание на {day_name} {target.strftime('%d.%m %H:%M')} (UTC+5) запланировано")


# ==================== MAIN =========================
def main():
    global schedule
    schedule = load_schedule()

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не найден! Установи переменную окружения.")

    if ADMIN_ID == 123456789:
        print("\nВНИМАНИЕ! Ты забыл поменять ADMIN_ID! Бот НЕ будет работать с админкой!\n")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(button))

    # Планируем напоминания при старте
    schedule_reminders(app)

    print("Бот запущен! Админка работает только для ID:", ADMIN_ID)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

