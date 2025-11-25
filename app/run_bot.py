import os
import threading
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from app.core.database import init_db
# 1. ПЕРЕВІРТЕ ІМПОРТИ ТУТ
from app.bot.handlers import start_command, generate_command, message_handler, add_experience_command, \
    add_education_command

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def init_telegram_bot_handlers(application: Application):
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("generate", generate_command))
    application.add_handler(CommandHandler("add_experience", add_experience_command))

    # 2. ПЕРЕВІРТЕ, ЧИ Є ЦЕЙ РЯДОК:
    application.add_handler(CommandHandler("add_education", add_education_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("Помилка: Токен Telegram-бота не знайдено.")
        return

    print("Ініціалізація бази даних...")
    init_db()
    print("База даних ініціалізована.")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    init_telegram_bot_handlers(application)

    print("Запуск Telegram-бота у Pooling Mode...")
    application.run_polling(poll_interval=3.0, drop_pending_updates=True)


if __name__ == '__main__':
    main()