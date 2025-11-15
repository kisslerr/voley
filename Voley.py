import json
import datetime
import re
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ==== НАСТРОЙКИ ====
MAX_PARTICIPANTS = 12
DATA_FILE = "schedule.json"
TIMEZONE_OFFSET = 5  # UTC+5
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Время тренировок (UTC+5)
TRAINING_TIME = {
    "Вторник": 21,  # 21:00
    "Четверг": 20   # 20:00
}

# Загрузка .env (если есть)
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# Стартовая структура
schedule = {"Вторник": [], "Четверг": []}

# ====================================
# ЗАГРУЗКА / СОХРАНЕНИЕ
# ====================================
def load_schedule():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = {}
    for day in ["Вторник", "Четверг"]:
        if day not in data:
            data[day] = []
    return data

def save_schedule():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)

# ====================================
# ВРЕМЯ UTC+5
# ====================================
def now_utc5():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)

def get_nearest_day():
    today = now_utc5().weekday()
    if today <= 1: return "Вторник"
    elif 1 < today <= 3: return "Четверг"
    else: return "Вторник"

def format_time(day):
    return f"{TRAINING_TIME[day]:02d}:00"

# ====================================
# ЕЖЕДНЕВНЫЕ КНОПКИ (9:00)
# ====================================
async def daily_buttons(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.application.bot_data.get("chat_id")
    if not chat_id:
        return
    nearest = get_nearest_day()
    time_str = format_time(nearest)
    keyboard = [
        [InlineKeyboardButton("Я ИДУ", callback_data="group_join")],
        [InlineKeyboardButton("ОТМЕНИТЬ", callback_data="group_cancel")],
        [InlineKeyboardButton("РАСПИСАНИЕ", callback_data="view")],
    ]
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"БЛИЖАЙШАЯ ТРЕНИРОВКА\n{nearest.upper()} {time_str}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ====================================
# /start
# ====================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ["group", "supergroup"]:
        context.application.bot_data["chat_id"] = update.effective_chat.id
    nearest = get_nearest_day()
    time_str = format_time(nearest)
    keyboard = [
        [InlineKeyboardButton("Я ИДУ", callback_data="group_join")],
        [InlineKeyboardButton("ОТМЕНИТЬ", callback_data="group_cancel")],
        [InlineKeyboardButton("РАСПИСАНИЕ", callback_data="view")],
    ]
    await update.message.reply_text(
        f"Ближайшая тренировка:\n{nearest.upper()} {time_str} (UTC+5)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ====================================
# КНОПКИ
# ====================================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user
    uid = f"{user.first_name}".strip()
    if user.username:
        uid += f" (@{user.username})"
    uid += f" ({user.id})"
    day = get_nearest_day()

    if data == "group_join":
        if uid in schedule[day]:
            await query.edit_message_text(f"Ты уже записан на {day}!")
            return
        if len(schedule[day]) >= MAX_PARTICIPANTS:
            await query.edit_message_text(f"Мест нет на {day}!")
            return
        schedule[day].append(uid)
        save_schedule()
        keyboard = [
            [InlineKeyboardButton("ЗАПИСАН", callback_data="none")],
            [InlineKeyboardButton("ОТМЕНИТЬ", callback_data="group_cancel")],
        ]
        await query.edit_message_text(
            f"{user.first_name} записан на {day}!\nСейчас: {len(schedule[day])}/{MAX_PARTICIPANTS}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "group_cancel":
        if uid not in schedule[day]:
            await query.edit_message_text(f"Ты не записан на {day}.")
            return
        schedule[day].remove(uid)
        save_schedule()
        keyboard = [[InlineKeyboardButton("Я ИДУ", callback_data="group_join")]]
        await query.edit_message_text(
            f"Запись отменена.\nСейчас: {len(schedule[day])}/{MAX_PARTICIPANTS}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "view":
        msg = "РАСПИСАНИЕ:\n\n"
        for d in ["Вторник", "Четверг"]:
            msg += f"**{d} {format_time(d)}** — {len(schedule[d])}/{MAX_PARTICIPANTS}\n"
            for u in schedule[d]:
                name = u.split(" (")[0]
                msg += f"• {name}\n"
            msg += "\n"
        await query.edit_message_text(msg.strip(), parse_mode="Markdown")

# ====================================
# УВЕДОМЛЕНИЕ ЗА ЧАС
# ====================================
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    day = job.name
    chat_id = job.data
    time_str = format_time(day)
    count = len(schedule[day])
    msg = f"ТРЕНИРОВКА ЧЕРЕЗ 1 ЧАС!\n{day.upper()} {time_str}\n\nИДУТ: {count}/{MAX_PARTICIPANTS}\n"
    for i, user in enumerate(schedule[day], 1):
        name = user.split(" (")[0]
        msg += f"{i}. {name}\n"
    keyboard = [
        [InlineKeyboardButton("Я ИДУ", callback_data="group_join")],
        [InlineKeyboardButton("ОТМЕНИТЬ", callback_data="group_cancel")],
    ]
    await context.bot.send_message(
        chat_id=chat_id,
        text=msg.strip(),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ====================================
# АДМИН-ПАНЕЛЬ
# ====================================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 123456789:  # ← ЗАМЕНИ НА СВОЙ ID!
        return
    keyboard = [
        [InlineKeyboardButton("ОЧИСТИТЬ ВТ", callback_data="clear_Вторник")],
        [InlineKeyboardButton("ОЧИСТИТЬ ЧТ", callback_data="clear_Четверг")],
    ]
    msg = f"АДМИН\nВТ: {len(schedule['Вторник'])}/12\nЧТ: {len(schedule['Четверг'])}/12"
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def clear_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 123456789: return
    query = update.callback_query
    day = query.data.split("_")[1]
    schedule[day].clear()
    save_schedule()
    await query.edit_message_text(f"{day} очищен!")

# ====================================
# MAIN
# ====================================
def main():
    global schedule
    schedule = load_schedule()

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не найден! Укажи в переменных bothost.ru")

    app = Application.builder().token(BOT_TOKEN).build()

    # Хендлеры
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(button, pattern="^(group_join|group_cancel|view)$"))
    app.add_handler(CallbackQueryHandler(clear_day, pattern="^clear_"))

    # Сохраняем ID группы
    async def save_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type in ["group", "supergroup"]:
            context.application.bot_data["chat_id"] = update.effective_chat.id
    app.add_handler(CommandHandler("start", save_chat, filters.ChatType.GROUPS))

    # Ежедневно в 9:00 — кнопки
    now = now_utc5()
    target = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now > target:
        target += datetime.timedelta(days=1)
    app.job_queue.run_daily(
        daily_buttons,
        time=target.time(),
        days=(0,1,2,3,4,5,6)
    )

    # Уведомления за час (один раз на тренировку)
    for day_name, hour in TRAINING_TIME.items():
        target = now.replace(hour=hour - 1, minute=0, second=0, microsecond=0)
        if now > target:
            days_ahead = 7 + (1 if day_name == "Вторник" else 3)
            target += datetime.timedelta(days=days_ahead)
        app.job_queue.run_once(
            send_reminder,
            when=target,
            name=day_name,
            data=app.bot_data.get("chat_id")
        )

    print("БОТ ЗАПУЩЕН (UTC+5)")
    app.run_polling()

if __name__ == "__main__":
    main()
