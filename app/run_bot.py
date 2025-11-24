import os
import threading
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from app.core.database import init_db
from app.bot.handlers import start_command, generate_command, message_handler

# Завантажуємо змінні середовища
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def init_telegram_bot_handlers(application: Application):
    """Додає обробники команд до Telegram Application."""
    # Обробники PTB тут мають бути синхронними
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("generate", generate_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))


def main():
    """Основна функція для запуску бота у Pooling Mode."""
    if not TELEGRAM_BOT_TOKEN:
        print("Помилка: Токен Telegram-бота не знайдено.")
        return

    # Ініціалізація бази даних
    print("Ініціалізація бази даних...")
    init_db()
    print("База даних ініціалізована.")

    # 1. Створення об'єкта Application PTB
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # 2. Додавання обробників
    init_telegram_bot_handlers(application)

    # 3. Запуск Pooling (БЛОКУЮЧИЙ ВИКЛИК)
    print("Запуск Telegram-бота у Pooling Mode...")
    application.run_polling(poll_interval=3.0, drop_pending_updates=True)


if __name__ == '__main__':
    # Ми запускаємо бота напряму (без Flask/Gunicorn)
    main()