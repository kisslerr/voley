import json
import datetime
import os
import asyncio
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
TIMEZONE_OFFSET = 5
ADMIN_ID = 737408288  # ← твой ID
BOT_TOKEN = os.getenv("BOT_TOKEN")

TRAINING_TIME = {"Вторник": 21, "Четверг": 20}
schedule = {"Вторник": [], "Четверг": []}

# ==================== ФАЙЛЫ =========================
def load_schedule():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"Вторник": [], "Четверг": []}

def save_schedule():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)

# ==================== ВРЕМЯ =========================
def now_utc5():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)

def get_nearest_day():
    wd = now_utc5().weekday()
    return "Вторник" if wd <= 1 or wd >= 4 else "Четверг"

def format_time(day):
    return f"{TRAINING_TIME[day]:02d}:00"

# ==================== КОМАНДЫ =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nearest = get_nearest_day()
    text = f"БЛИЖАЙШАЯ ТРЕНИРОВКА\n\n{nearest.upper()} в {format_time(nearest)}"
    kb = [[InlineKeyboardButton("ЗАПИСАТЬСЯ", callback_data="join")],
          [InlineKeyboardButton("ОТМЕНИТЬ", callback_data="cancel")],
          [InlineKeyboardButton("РАСПИСАНИЕ", callback_data="view")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
    if update.effective_chat.type in ["group", "supergroup"]:
        context.application.bot_data["chat_id"] = update.effective_chat.id

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Доступ запрещён.")
        return
    kb = [[InlineKeyboardButton("Очистить ВТОРНИК", callback_data="clear_Вторник")],
          [InlineKeyboardButton("Очистить ЧЕТВЕРГ", callback_data="clear_Четверг")],
          [InlineKeyboardButton("Напомнить СЕЙЧАС", callback_data="force_remind")]]
    msg = f"АДМИНКА\nВТ: {len(schedule['Вторник'])}/12\nЧТ: {len(schedule['Четверг'])}/12"
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

# ==================== КНОПКИ ========================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    day = get_nearest_day()
    name = user.first_name or ""
    if user.username: name += f" (@{user.username})"
    uid = f"{name} ({user.id})"

    if q.data == "join":
        if uid in schedule[day]:
            return await q.edit_message_text("Уже записан!")
        if len(schedule[day]) >= MAX_PARTICIPANTS:
            return await q.edit_message_text("Мест нет!")
        schedule[day].append(uid)
        save_schedule()
        await q.edit_message_text(f"Записан на {day}!\n{len(schedule[day])}/12",
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ОТМЕНИТЬ", callback_data="cancel")]]))

    elif q.data == "cancel":
        if uid not in schedule[day]:
            return await q.edit_message_text("Ты не записан.")
        schedule[day].remove(uid)
        save_schedule()
        await q.edit_message_text(f"Отменено.\n{len(schedule[day])}/12",
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЗАПИСАТЬСЯ", callback_data="join")]]))

    elif q.data == "view":
        msg = "*РАСПИСАНИЕ*\n\n"
        for d in ["Вторник", "Четверг"]:
            msg += f"*{d} {format_time(d)}* — {len(schedule[d])}/12\n"
            for i, u in enumerate(schedule[d], 1):
                msg += f"{i}. {u.split(' (')[0]}\n"
            msg += "\n"
        await q.edit_message_text(msg, parse_mode="Markdown")

    elif q.data.startswith("clear_"):
        if user.id != ADMIN_ID: return await q.answer("Ты не админ!", show_alert=True)
        day = q.data.split("_", 1)[1]
        schedule[day].clear()
        save_schedule()
        await q.edit_message_text(f"{day} очищен!")

    elif q.data == "force_remind":
        if user.id != ADMIN_ID: return await q.answer("Нет доступа", show_alert=True)
        chat_id = context.application.bot_data.get("chat_id")
        if not chat_id:
            return await q.edit_message_text("Сначала /start в группе!")
        await send_reminder(context, get_nearest_day())
        await q.edit_message_text("Напоминание отправлено!")

async def send_reminder(context, day):
    chat_id = context.application.bot_data.get("chat_id")
    if not chat_id: return
    msg = f"*ТРЕНИРОВКА ЧЕРЕЗ ЧАС!*\n{day.upper()} в {format_time(day)}\n\nИдут: {len(schedule[day])}/12\n"
    for i, u in enumerate(schedule[day], 1):
        msg += f"{i}. {u.split(' (')[0]}\n"
    kb = [[InlineKeyboardButton("ЗАПИСАТЬСЯ", callback_data="join")],
          [InlineKeyboardButton("ОТМЕНИТЬ", callback_data="cancel")]]
    await context.bot.send_message(chat_id, msg, "Markdown", reply_markup=InlineKeyboardMarkup(kb))

# ==================== MAIN =========================
async def main():
    global schedule
    schedule = load_schedule()

    if not BOT_TOKEN:
        print("ОШИБКА: BOT_TOKEN не найден!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(button))

    print("БОТ ЗАПУЩЕН НА BOTHOST.RU | Админ 737408288")
    print("Напоминания за час — используй кнопку 'Напомнить СЕЙЧАС' в админке")

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    
    # Держим бота живым
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
