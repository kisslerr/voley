import json
import datetime
import re
import os  # <-- Добавлено
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

# Токен из переменной окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Ошибка: Переменная окружения BOT_TOKEN не установлена!")

# Стартовая структура
schedule = {
    "Вторник": [],
    "Четверг": []
}

# ====================================
# ЗАГРУЗКА / СОХРАНЕНИЕ
# ====================================
def load_schedule():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = {}
    if "Вторник" not in data:
        data["Вторник"] = []
    if "Четверг" not in data:
        data["Четверг"] = []
    return data

def save_schedule():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)

# ====================================
# БЛИЖАЙШИЙ ДЕНЬ
# ====================================
def get_nearest_day():
    today = datetime.datetime.today().weekday()
    if today <= 1:  # Пн–Вт → ближайший вторник
        return "Вторник"
    elif 1 < today <= 3:  # Ср–Чт → ближайший четверг
        return "Четверг"
    else:  # Пт–Сб–Вс → следующий вторник
        return "Вторник"

# ====================================
# START
# ====================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nearest = get_nearest_day()
    keyboard = [
        [InlineKeyboardButton(f"Записаться ({nearest})", callback_data=f"reg_{nearest}")],
        [InlineKeyboardButton("Расписание", callback_data="view")],
        [InlineKeyboardButton("Отменить запись", callback_data="cancel_menu")],
    ]
    await update.message.reply_text(
        f"Привет! Ближайшая тренировка: {nearest}.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ====================================
# ФОРМАТИРОВАНИЕ РАСПИСАНИЯ
# ====================================
def format_schedule():
    msg = "📅 *Текущее расписание:*\n"
    for day in ["Вторник", "Четверг"]:
        msg += f"\n*{day}:* {len(schedule[day])}/{MAX_PARTICIPANTS}\n"
        for user in schedule[day]:
            msg += f"▪ {user}\n"
    return msg

# ====================================
# ОБРАБОТКА КНОПОК
# ====================================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ---------------------------
    # ЗАПИСАТЬСЯ
    # ---------------------------
    if data.startswith("reg_"):
        day = data.split("_")[1]
        user = query.from_user
        uid = f"{user.first_name} {user.last_name or ''} ({user.id})"
        if uid in schedule[day]:
            await query.edit_message_text(f"Вы уже записаны на {day}.")
            return
        if len(schedule[day]) >= MAX_PARTICIPANTS:
            await query.edit_message_text(f"❌ На {day} нет мест.")
            return
        schedule[day].append(uid)
        save_schedule()
        await query.edit_message_text(
            f"✅ Вы записаны на {day}.\n"
            f"Записано: {len(schedule[day])}/{MAX_PARTICIPANTS}"
        )

    # ---------------------------
    # ПОКАЗАТЬ РАСПИСАНИЕ
    # ---------------------------
    elif data == "view":
        await query.edit_message_text(
            format_schedule(),
            parse_mode="Markdown"
        )

    # ---------------------------
    # МЕНЮ ОТМЕНЫ
    # ---------------------------
    elif data == "cancel_menu":
        keyboard = [
            [InlineKeyboardButton("Отменить (Вторник)", callback_data="cancel_Вторник")],
            [InlineKeyboardButton("Отменить (Четверг)", callback_data="cancel_Четверг")],
        ]
        await query.edit_message_text(
            "Выберите день:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ---------------------------
    # ОТМЕНА ЗАПИСИ
    # ---------------------------
    elif data.startswith("cancel_"):
        day = data.split("_")[1]
        user = query.from_user
        uid = f"{user.first_name} {user.last_name or ''} ({user.id})"
        if uid not in schedule[day]:
            await query.edit_message_text(f"❌ Вы не записаны на {day}.")
            return
        schedule[day].remove(uid)
        save_schedule()
        await query.edit_message_text(
            f"❗ Запись отменена на {day}.\n"
            f"Записано: {len(schedule[day])}/{MAX_PARTICIPANTS}"
        )

# ====================================
# АВТОЗАПИСЬ (+1 ... -3)
# ====================================
async def auto_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = re.match(r"^([+-])(\d)(?:\s*(Вторник|Четверг))?$", text, re.IGNORECASE)
    if not match:
        return
    sign, count, day = match.groups()
    count = int(count)
    if not day:
        day = get_nearest_day()
    day = day.capitalize()
    if day not in schedule:
        schedule[day] = []

    user = update.message.from_user
    uid = f"{user.first_name} {user.last_name or ''} ({user.id})"

    # ---------------------------
    # ДОБАВЛЕНИЕ (+)
    # ---------------------------
    if sign == "+":
        if len(schedule[day]) + count > MAX_PARTICIPANTS:
            free = MAX_PARTICIPANTS - len(schedule[day])
            await update.message.reply_text(f"❌ Недостаточно мест! Свободно: {free}.")
            return
        if uid not in schedule[day]:
            schedule[day].append(uid)
        for i in range(count - 1):
            schedule[day].append(f"Гость {uid} #{i+1}")
        save_schedule()
        await update.message.reply_text(
            f"✅ Записано {count} человек на {day}.\n"
            f"Сейчас: {len(schedule[day])}/{MAX_PARTICIPANTS}"
        )

    # ---------------------------
    # СНЯТИЕ (-)
    # ---------------------------
    if sign == "-":
        if uid not in schedule[day]:
            await update.message.reply_text(f"❌ Вы не записаны на {day}.")
            return
        removed = 1
        schedule[day].remove(uid)
        for i in range(count - 1):
            guest = f"Гость {uid} #{i+1}"
            if guest in schedule[day]:
                schedule[day].remove(guest)
                removed += 1
        save_schedule()
        await update.message.reply_text(
            f"❗ Снято {removed} человек.\n"
            f"Сейчас: {len(schedule[day])}/{MAX_PARTICIPANTS}"
        )

# ====================================
# MAIN
# ====================================
from dotenv import load_dotenv
import os

def main():
    global schedule
    schedule = load_schedule()

    # Загружаем .env
    load_dotenv()
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        raise RuntimeError("Ошибка: BOT_TOKEN не найден! Проверь .env файл.")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_register))

    print("Бот запущен.")
    app.run_polling()
