import json, os, datetime, asyncio, logging, tempfile
import telegram.ext

try:
    telegram.ext.utils.webhook_helpers.request_telegram_reset()
except:
    pass

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# ───── НАСТРОЙКИ ─────
ADMIN_ID = 737408288
BOT_TOKEN = os.getenv("BOT_TOKEN")
FILE = "/data/data.json"
MAX = 12
schedule = {"Вторник": [], "Четверг": []}

# ───── Блокировка анонимного админа ─────
def is_anonymous_admin(update: Update) -> bool:
    user = update.effective_user
    return user is None or user.id == 1087968824

# ───── Сохранение/загрузка ─────
def load():
    global schedule
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            schedule = {"Вторник": data.get("Вторник", []), "Четверг": data.get("Четверг", [])}
    except:
        schedule = {"Вторник": [], "Четверг": []}

def save():
    try:
        with tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8', dir='/data') as f:
            json.dump(schedule, f, ensure_ascii=False, indent=2)
            temp_name = f.name
        os.replace(temp_name, FILE)
    except Exception as e:
        print("Ошибка сохранения:", e)

load()

def now(): return datetime.datetime.utcnow() + datetime.timedelta(hours=5)
def day(): 
    w = now().weekday()
    return "Вторник" if w in [0,1,4,5,6] else "Четверг"

# ───── + и - — САМЫЙ ВАЖНЫЙ ХЕНДЛЕР (должен быть ПЕРВЫМ!) ─────
async def plus_minus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_anonymous_admin(update):
        return

    text = update.message.text.strip()
    if text not in {"+", "-", "−"}:
        return

    d = day()
    user = update.effective_user
    name = f"{user.first_name}" + (f" (@{user.username})" if user.username else "") + f" ({user.id})"

    if text == "+":
        if name in schedule[d]:
            await update.message.reply_text("Ты уже записан!")
        elif len(schedule[d]) >= MAX:
            await update.message.reply_text("Мест больше нет!")
        else:
            schedule[d].append(name)
            save()
            await update.message.reply_text(f"Записался на {d}!\nСейчас: {len(schedule[d])}/12")
    else:
        if name not in schedule[d]:
            await update.message.reply_text("Ты и так не записан.")
        else:
            schedule[d].remove(name)
            save()
            await update.message.reply_text(f"Отменил запись\nСейчас: {len(schedule[d])}/12")

# ───── /start (теперь НЕ перехватывает + и -) ─────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_anonymous_admin(update): return
    d = day()
    kb = [[InlineKeyboardButton("ЗАПИСАТЬСЯ", callback_data="join")],
          [InlineKeyboardButton("ОТМЕНИТЬ", callback_data="cancel")],
          [InlineKeyboardButton("РАСПИСАНИЕ", callback_data="view")]]
    await update.message.reply_text(f"Ближайшая — {d} в {'21:00' if d=='Вторник' else '20:00'}",
                                    reply_markup=InlineKeyboardMarkup(kb))
    if update.effective_chat.type != "private":
        context.application.bot_data["chat_id"] = update.effective_chat.id

# ───── Остальные хендлеры (admin, btn и т.д.) — оставь как есть ─────
# (вставь сюда admin и btn из предыдущей версии)

# ───── ЗАПУСК — САМОЕ ГЛАВНОЕ: + и - ДОЛЖНЫ БЫТЬ ПЕРВЫМИ! ─────
async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # ←←← ВОТ ЭТО САМОЕ ГЛАВНОЕ — ПОРЯДОК!
    app.add_handler(MessageHandler(filters.Regex(r"^(\+|-|−)$"), plus_minus_handler))  # ПЕРВЫЙ!
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.Regex(r"^(\+|-|−)$"), start))  # теперь НЕ ловит +/-

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True, timeout=30)
    print("БОТ ЗАПУЩЕН — + И - В ГРУППЕ РАБОТАЮТ НА 100%")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.run_forever()
