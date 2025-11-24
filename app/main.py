import os
import threading
from dotenv import load_dotenv

# Імпорти для Flask
from flask import Flask, jsonify
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Імпорти ваших модулів
from app.core.database import init_db, SessionLocal
from app.bot.handlers import start_command, generate_command, message_handler

# Завантажуємо змінні середовища
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# 1. Ініціалізація застосунку Flask
app = Flask(__name__)

# Створення об'єкта Application PTB
if TELEGRAM_BOT_TOKEN:
    tg_application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
else:
    print("Помилка: Токен Telegram-бота не знайдено.")
    tg_application = None


def init_telegram_bot_handlers(application: Application):
    """Додає обробники команд до Telegram Application."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("generate", generate_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))


def start_bot_polling(application: Application):
    """Функція для запуску бота в окремому потоці."""
    print("Запуск Telegram-бота в окремому потоці...")
    # run_polling є блокуючим, тому його треба запускати в потоці/процесі
    application.run_polling(poll_interval=3.0, drop_pending_updates=True)


# 2. ПОДІЇ ЗАПУСКУ (Налаштування)
with app.app_context():
    # 1. Ініціалізація БД (Створення таблиць)
    print("Ініціалізація бази даних...")
    init_db()
    print("База даних ініціалізована.")

    if tg_application:
        # 2. Додавання обробників
        init_telegram_bot_handlers(tg_application)

        # 3. Запуск бота у фоновому потоці (Threading)
        # Це вирішує проблему Runtime Error, оскільки потік Flask не блокується
        bot_thread = threading.Thread(target=start_bot_polling, args=(tg_application,))
        bot_thread.start()
        print("Telegram-бот ініціалізовано в окремому потоці.")


# 3. Базовий API роут (для перевірки Flask)
@app.route('/')
def read_root():
    return jsonify({"status": "ok", "service": "CV on the Go (Flask) is running"})


if __name__ == '__main__':
    # Запуск вбудованого сервера Flask для розробки
    app.run(host='0.0.0.0', port=8000)