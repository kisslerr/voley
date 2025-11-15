import json
import datetime
import re
import os
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ==== НАСТРОЙКИ ====
MAX_PARTICIPANTS = 12
DATA_FILE = "schedule.json"
TIMEZONE_OFFSET = 5  # UTC+5
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Время тренировок (по UTC+5)
TRAINING_TIME = {
    "Вторник": 21,  # 21:00
    "Четверг": 20   # 20:00
}

# Загрузка .env
from dotenv import load_dotenv
load_dotenv()

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
# ВРЕМЯ ПО UTC+5
# ====================================
def now_utc5():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)

# Ближайший день
def get_nearest_day():
    today = now_utc5().weekday()
    if today <= 1:  # Пн–Вт → Вторник
        return "Вторник"
    elif 1 < today <= 3:  # Ср–Чт → Четверг
        return "Четверг"
    else:
        return "Вторник"

# Форматировать время
def format_time(day):
    return f"{TRAINING_TIME[day]:02d}:00"

# ====================================
# START
# ====================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nearest = get_nearest_day()
    time_str = format_time(nearest)
    keyboard = [
        [InlineKeyboardButton("Я ИДУ", callback_data="group_join")],
        [InlineKeyboardButton("ОТМЕНИТЬ", callback_data="group_cancel")],
        [InlineKeyboardButton("РАСПИСАНИЕ", callback_data="view")],
    ]
    text = f"Ближайшая тренировка:\n{nearest.upper()} {time_str} (UTC+5)"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ====================================
# РАСПИСАНИЕ
# ====================================
def format_schedule():
    msg = "РАСПИСАНИЕ:\n\n"
    for day in ["Вторник", "Четверг"]:
        msg += f"**{day} {format_time(day)}** — {len(schedule[day])}/{MAX_PARTICIPANTS}\n"
        for user in schedule[day]:
            msg += f"• {user}\n"
        msg += "\n"
    return msg.strip()

# ====================================
# КНОПКИ
# ====================================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user
    uid = f"{user.first_name} {user.last_name or ''}".strip()
    if user.username:
        uid += f" (@{user.username})"
    uid += f" ({user.id})"
    day = get_nearest_day()

    if data == "group_join":
        if uid in schedule[day]:
            await query.edit_message_text(f"Ты уже записан на {day}!", reply_markup=None)
            return
        if len(schedule[day]) >= MAX_PARTICIPANTS:
            await query.edit_message_text(f"Мест нет на {day}!", reply_markup=None)
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
            await query.edit_message_text(f"Ты не записан на {day}.", reply_markup=None)
            return
        schedule[day].remove(uid)
        save_schedule()
        keyboard = [[InlineKeyboardButton("Я ИДУ", callback_data="group_join")]]
        await query.edit_message_text(
            f"Запись отменена.\nСейчас: {len(schedule[day])}/{MAX_PARTICIPANTS}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "view":
        await query.edit_message_text(format_schedule(), parse_mode="Markdown")

# ====================================
# АВТОЗАПИСЬ (+1, -1, @user)
# ====================================
async def auto_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = re.match(r"^([+-])(\d)(?:\s+@?(\w+))?$", text, re.IGNORECASE)
    if not match:
        return
    sign, count, mention = match.groups()
    count = int(count)
    day = get_nearest_day()

    # Определяем пользователя
    target_user = update.message.from_user
    if mention:
        # По упоминанию
        for member in await update.message.chat.get_members():
            if member.user.username and member.user.username.lower() == mention.lower():
                target_user = member.user
                break
        else:
            await update.message.reply_text(f"Пользователь @{mention} не найден.")
            return

    uid = f"{target_user.first_name} {target_user.last_name or ''}".strip()
    if target_user.username:
        uid += f" (@{target_user.username})"
    uid += f" ({target_user.id})"

    if sign == "+":
        if len(schedule[day]) + count > MAX_PARTICIPANTS:
            free = MAX_PARTICIPANTS - len(schedule[day])
            await update.message.reply_text(f"Свободно только {free} мест!")
            return
        if uid not in schedule[day]:
            schedule[day].append(uid)
        for i in range(1, count):
            schedule[day].append(f"Гость {uid} #{i}")
        save_schedule()
        await update.message.reply_text(
            f"Записано {count} на {day}!\nСейчас: {len(schedule[day])}/{MAX_PARTICIPANTS}"
        )
    elif sign == "-":
        if uid not in schedule[day]:
            await update.message.reply_text(f"Ты не записан на {day}.")
            return
        removed = 0
        if uid in schedule[day]:
            schedule[day].remove(uid)
            removed += 1
        for i in range(1, count):
            guest = f"Гость {uid} #{i}"
            if guest in schedule[day]:
                schedule[day].remove(guest)
                removed += 1
        save_schedule()
        await update.message.reply_text(
            f"Снято {removed} с {day}.\nСейчас: {len(schedule[day])}/{MAX_PARTICIPANTS}"
        )

# ====================================
# УВЕДОМЛЕНИЯ ЗА ЧАС
# ====================================
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    day = job.name
    chat_id = job.data
    time_str = format_time(day)
    count = len(schedule[day])
    msg = f"ТРЕНИРОВКА ЧЕРЕЗ 1 ЧАС!\n{day.upper()} {time_str}\n\nИДУТ: {count}/{MAX_PARTICIPANTS}\n"
    for i, user in enumerate(schedule[day], 1):
        msg += f"{i}. {user.split(' (')[0]}\n"
    keyboard = [
        [InlineKeyboardButton("Я ИДУ", callback_data="group_join")],
        [InlineKeyboardButton("ОТМЕНИТЬ", callback_data="group_cancel")],
    ]
    await context.bot.send_message(
        chat_id=chat_id,
        text=msg.strip(),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def schedule_reminders(app):
    now = now_utc5()
    for day_name, hour in TRAINING_TIME.items():
        # Сегодня
        target = now.replace(hour=hour - 1, minute=0, second=0, microsecond=0)
        if now > target:
            # Следующая неделя
            days_ahead = (1 if day_name == "Вторник" else 3) + 7
            target += datetime.timedelta(days=days_ahead)
        app.job_queue.run_once(
            send_reminder,
            when=target,
            name=day_name,
            data=app.bot_data.get("chat_id", -1001234567890),  # Замени на ID группы
            chat_id=app.bot_data.get("chat_id")
        )

# ====================================
# ADMIN
# ====================================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 123456789:  # ← ТВОЙ ID
        return
    keyboard = [
        [InlineKeyboardButton("ОЧИСТИТЬ ВТ", callback_data="clear_Вторник")],
        [InlineKeyboardButton("ОЧИСТИТЬ ЧТ", callback_data="clear_Четверг")],
    ]
    msg = f"АДМИН\nВТ: {len(schedule['Вторник'])}/12\nЧТ: {len(schedule['Четверг'])}/12"
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def clear_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 123456789:
        return
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
        raise RuntimeError("BOT_TOKEN не найден!")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(button, pattern="^(group_join|group_cancel|view)$"))
    app.add_handler(CallbackQueryHandler(clear_day, pattern="^clear_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_register))

    # Сохраняем chat_id при первом /start в группе
    async def save_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type in ["group", "supergroup"]:
            context.application.bot_data["chat_id"] = update.effective_chat.id
            schedule_reminders(context.application)
    app.add_handler(CommandHandler("start", save_chat_id, filters.ChatType.GROUPS))

    print("БОТ ЗАПУЩЕН (UTC+5)")
    app.run_polling()

if __name__ == "__main__":
    main()
