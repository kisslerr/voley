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
TIMEZONE_OFFSET = 5  # UTC+5 (Екатеринбург / Челябинск)

# ТВОЙ РЕАЛЬНЫЙ ID — админка теперь работает только у тебя
ADMIN_ID = 737408288

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Время тренировок (местное время UTC+5)
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
    wd = now_utc5().weekday()  # 0=Пн, 1=Вт, 2=Ср, 3=Чт, 4=Пт, 5=Сб, 6=Вс
    if wd <= 1:        # Пн–Вт
        return "Вторник"
    elif wd <= 3:      # Ср–Чт
        return "Четверг"
    else:              # Пт–Вс
        return "Вторник"


def format_time(day):
    return f"{TRAINING_TIME[day]:02d}:00"


# ==================== КОМАНДЫ =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nearest = get_nearest_day()
    text = f"БЛИЖАЙШАЯ ТРЕНИРОВКА\n\n{nearest.upper()} в {format_time(nearest)}"

    keyboard = [
        [InlineKeyboardButton("ЗАПИСАТЬСЯ", callback_data="join")],
        [InlineKeyboardButton("ОТМЕНИТЬ ЗАПИСЬ", callback_data="cancel")],
        [InlineKeyboardButton("РАСПИСАНИЕ", callback_data="view")],
    ]

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    # Запоминаем ID группы для напоминаний
    if update.effective_chat.type in ["group", "supergroup"]:
        context.application.bot_data["chat_id"] = update.effective_chat.id


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Доступ запрещён.")
        return

    keyboard = [
        [InlineKeyboardButton("Очистить ВТОРНИК", callback_data="clear_Вторник")],
        [InlineKeyboardButton("Очистить ЧЕТВЕРГ", callback_data="clear_Четверг")],
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

    name = user.first_name or "Аноним"
    if user.username:
        name += f" (@{user.username})"
    uid = f"{name} ({user.id})"

    # ——— ЗАПИСЬ ———
    if query.data == "join":
        if uid in schedule[day]:
            await query.edit_message_text("Ты уже записан!")
            return
        if len(schedule[day]) >= MAX_PARTICIPANTS:
            await query.edit_message_text("Мест нет! (12/12)")
            return

        schedule[day].append(uid)
        save_schedule()

        await query.edit_message_text(
            f"Записан на {day}!\nУчастников: {len(schedule[day])}/{MAX_PARTICIPANTS}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ОТМЕНИТЬ", callback_data="cancel")]])
        )

    # ——— ОТМЕНА ———
    elif query.data == "cancel":
        if uid not in schedule[day]:
            await query.edit_message_text("Ты и так не записан.")
            return

        schedule[day].remove(uid)
        save_schedule()

        await query.edit_message_text(
            f"Запись отменена.\nУчастников: {len(schedule[day])}/{MAX_PARTICIPANTS}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЗАПИСАТЬСЯ", callback_data="join")]])
        )

    # ——— РАСПИСАНИЕ ———
    elif query.data == "view":
        msg = "*РАСПИСАНИЕ ТРЕНИРОВОК*\n\n"
        for d in ["Вторник", "Четверг"]:
            msg += f"*{d} {format_time(d)}* — {len(schedule[d])}/{MAX_PARTICIPANTS}\n"
            if schedule[d]:
                for i, u in enumerate(schedule[d], 1):
                    clean = u.split(" (")[0]
                    msg += f"{i}. {clean}\n"
            else:
                msg += "—\n"
            msg += "\n"
        await query.edit_message_text(msg, parse_mode="Markdown")

    # ——— АДМИНСКИЕ КНОПКИ ———
    elif query.data.startswith("clear_"):
        if user.id != ADMIN_ID:
            await query.answer("Ты не админ!", show_alert=True)
            return
        day_clear = query.data.split("_", 1)[1]
        schedule[day_clear].clear()
        save_schedule()
        await query.edit_message_text(f"{day_clear} очищен!")

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
    chat_id = context.application.bot_data.get("chat_id")
    if not chat_id:
        return

    msg = f"*ТРЕНИРОВКА ЧЕРЕЗ 1 ЧАС!*\n\n{day.upper()} в {format_time(day)}\n\nИдут: {len(schedule[day])}/{MAX_PARTICIPANTS}\n"
    if schedule[day]:
        for i, u in enumerate(schedule[day], 1):
            msg += f"{i}. {u.split(' (')[0]}\n"
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
    day_map = {"Вторник": 1, "Четверг": 3}  # понедельник = 0

    for day_name, hour in TRAINING_TIME.items():
        target = now.replace(hour=hour - 1, minute=0, second=0, microsecond=0)

        # Переводим на нужный день недели
        while target.weekday() != day_map[day_name]:
            target += datetime.timedelta(days=1)

        # Если уже прошло — переносим на следующую неделю
        if target <= now:
            target += datetime.timedelta(days=7)

        app.job_queue.run_once(
            send_reminder,
            when=target,
            name=day_name,
            data=None  # chat_id берём из bot_data
        )
        print(f"Напоминание запланировано: {day_name} в {target.strftime('%d.%m.%Y %H:%M')} (UTC+5)")


# ==================== MAIN =========================
def main():
    global schedule
    schedule = load_schedule()

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не найден!")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(button))

    schedule_reminders(app)

    print("БОТ УСПЕШНО ЗАПУЩЕН | Админ (ID 737408288) — только ты!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
