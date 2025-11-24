import os
import threading
from dotenv import load_dotenv

# Імпорти для Flask
from flask import Flask, jsonify, request, abort
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update

# Імпорти ваших модулів
from app.core.database import init_db
from app.bot.handlers import start_command, generate_command, message_handler

# Завантажуємо змінні середовища
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL_PATH = f'/{TELEGRAM_BOT_TOKEN}'  # Унікальний шлях для Webhook

# 1. Ініціалізація застосунку Flask
app = Flask(__name__)

# Створення об'єкта Application PTB
tg_application = None


def init_telegram_bot_handlers(application: Application):
    """Додає обробники команд до Telegram Application."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("generate", generate_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))


def setup_telegram_bot(url_path: str):
    """Налаштовує бота та встановлює Webhook URL."""
    global tg_application
    if not TELEGRAM_BOT_TOKEN:
        print("Помилка: Токен Telegram-бота не знайдено.")
        return

    tg_application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    init_telegram_bot_handlers(tg_application)

    # 1. Запуск в асинхронному режимі (PTB)
    # Ми використовуємо tg_application.run_in_thread для роботи з PTB у синхронному циклі Flask
    tg_application.run_in_thread()

    # 2. Встановлення Webhook URL (Потрібно вказати зовнішню URL!)
    # Цей крок не виконуємо в MVP, але він обов'язковий для продакшену
    # tg_application.bot.set_webhook(url=f"https://ВАШ_ДОМЕН/{url_path}")
    print("Telegram-бот налаштовано для Webhook Mode.")


# 2. ПОДІЇ ЗАПУСКУ
with app.app_context():
    # 1. Ініціалізація БД (Створення таблиць)
    print("Ініціалізація бази даних...")
    init_db()
    print("База даних ініціалізована.")

    # 2. Налаштування бота
    setup_telegram_bot(WEBHOOK_URL_PATH)


# 3. Webhook Endpoint (Точка прийому POST-запитів від Telegram)
@app.route(WEBHOOK_URL_PATH, methods=['POST'])
def telegram_webhook():
    """Обробляє вхідні оновлення від Telegram."""
    if tg_application is None:
        return jsonify({'status': 'error', 'message': 'Bot not initialized'}), 500

    # Отримання JSON-даних від Telegram
    update_data = request.get_json()

    # Передача оновлення в Telegram Application
    update = Update.de_json(update_data, tg_application.bot)

    # Обробка оновлення (запускається синхронно)
    tg_application.update_queue.put(update)

    return jsonify({'status': 'ok'})


# 4. Базовий API роут
@app.route('/')
def read_root():
    return jsonify({"status": "ok", "service": "CV on the Go (Webhook Mode) is running"})

if __name__ == '__main__':
    # Запуск Gunicorn (для продакшен-середовища)
    # Ми запускаємо app.run() тільки для розробки.
    # Для тестування Webhook краще використовувати Gunicorn.
    print(f"WEBHOOK URL PATH: http://0.0.0.0:8000{WEBHOOK_URL_PATH}")
    app.run(host='0.0.0.0', port=8000)