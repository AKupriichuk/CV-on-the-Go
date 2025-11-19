import os
import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from app.core.database import init_db
from app.bot.handlers import start_command, generate_command, message_handler

# Завантажуємо змінні середовища з .env
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# 1. Ініціалізація застосунку FastAPI
app = FastAPI(title="CV on the Go Monolith")


def init_telegram_bot():
    """Створює та налаштовує Application для Telegram-бота."""
    if not TELEGRAM_BOT_TOKEN:
        print("Помилка: Токен Telegram-бота не знайдено.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Додавання обробників команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("generate", generate_command))
    # application.add_handler(CommandHandler("add_experience", add_experience_command)) # TODO: Додати обробники для досвіду/освіти

    # Додавання головного обробника текстових повідомлень
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Запускаємо бота в окремому потоці (для роботи в межах FastAPI)
    # Це спрощений спосіб для розробки.
    print("Запуск Telegram-бота...")
    application.run_polling(poll_interval=3.0)
    print("Telegram-бот ініціалізовано.")


# 2. Подія запуску: Створюємо таблиці в БД та запускаємо бота
@app.on_event("startup")
def on_startup():
    """Створює всі таблиці SQLite та запускає бота при старті застосунку."""
    print("Ініціалізація бази даних...")
    init_db()
    print("База даних ініціалізована.")

    # Запускаємо бота
    init_telegram_bot()


# 3. Базовий роут для перевірки працездатності
@app.get("/")
def read_root():
    return {"status": "ok", "service": "CV on the Go is running"}


# 4. Точка запуску
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)