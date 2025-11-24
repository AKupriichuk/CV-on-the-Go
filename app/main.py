# app/main.py

import os
import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from app.core.database import init_db
from app.bot.handlers import start_command, generate_command, message_handler

# Встановлюємо asyncio для запуску бота в фоновому режимі
import asyncio
from typing import Dict

# Завантажуємо змінні середовища
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# 1. Ініціалізація застосунку FastAPI
app = FastAPI(title="CV on the Go Monolith")

# Словник для зберігання об'єкта бота, щоб мати до нього доступ
app.state.tg_bot_app: Application = None


def init_telegram_bot() -> Application:
    """Створює та налаштовує Application для Telegram-бота."""
    if not TELEGRAM_BOT_TOKEN:
        print("Помилка: Токен Telegram-бота не знайдено.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Додавання обробників команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("generate", generate_command))

    # Додавання головного обробника текстових повідомлень
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    return application


# 2. ПОДІЇ ЖИТТЄВОГО ЦИКЛУ (Lifespan Events)

@app.on_event("startup")
async def on_startup():
    """Створює таблиці БД та запускає бота як фонове завдання."""
    print("Ініціалізація бази даних...")
    init_db()
    print("База даних ініціалізована.")

    # Ініціалізуємо об'єкт Application
    tg_application = init_telegram_bot()
    app.state.tg_bot_app = tg_application

    if tg_application:
        print("Запуск Telegram-бота...")
        # Запускаємо бота асинхронно як фонове завдання (Background Task)
        # Це запобігає блокуванню головного циклу Uvicorn/FastAPI
        asyncio.create_task(
            tg_application.run_polling(
                poll_interval=3.0,
                drop_pending_updates=True,
                stop_signals=()  # Важливо, щоб Uvicorn міг сам контролювати зупинку
            )
        )
        print("Telegram-бот ініціалізовано.")


@app.on_event("shutdown")
async def on_shutdown():
    """Коректне завершення роботи бота при зупинці застосунку."""
    if app.state.tg_bot_app:
        print("Зупинка Telegram-бота...")
        await app.state.tg_bot_app.shutdown()


# 3. Базовий роут для перевірки працездатності
@app.get("/")
def read_root():
    return {"status": "ok", "service": "CV on the Go is running"}


# 4. Точка запуску
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)