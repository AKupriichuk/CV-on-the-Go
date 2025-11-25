from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from app.core.database import get_db
from app.logic import session_manager
from app.pdf_generator.generator import generate_pdf_from_data
from app.logic.session_manager import (
    STEP_START, STEP_WAITING_NAME, STEP_WAITING_CONTACTS,
    STEP_WAITING_SUMMARY, STEP_IDLE,
    transform_session_to_resume_data
)

# ----------------------------------------------------------------------
# КРОКИ ДІАЛОГУ ТА ФУНКЦІЇ ЗАПИТУ
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# ВИПРАВЛЕНИЙ СЛОВНИК КРОКІВ
# ----------------------------------------------------------------------

DIALOG_STEPS = {
    STEP_START: {
        # Коли ми тільки починаємо, наступний крок - чекати ім'я.
        "prompt": "Привіт! Я бот для створення резюме. Введіть ваше повне ім'я (ПІБ):",
        "next_step": STEP_WAITING_NAME,
        "context_key": None
    },
    STEP_WAITING_NAME: {
        # Ми зараз чекаємо ім'я. Наступним кроком будемо чекати контакти.
        # Тому prompt тут має запитувати контакти.
        "prompt": "Чудово! Тепер введіть вашу електронну пошту та телефон (наприклад: email@example.com, 0991234567):",
        "next_step": STEP_WAITING_CONTACTS,
        "context_key": "full_name"
    },
    STEP_WAITING_CONTACTS: {
        # Ми зараз чекаємо контакти. Наступним кроком чекаємо Summary.
        # Тому prompt тут має запитувати Summary.
        "prompt": "Дякую за контакти. Опишіть ваше професійне резюме (summary) одним абзацом:",
        "next_step": STEP_WAITING_SUMMARY,
        "context_key": "contacts"
    },
    STEP_WAITING_SUMMARY: {
        # Ми зараз чекаємо Summary. Наступний крок - кінець (IDLE).
        # Prompt повідомляє, що все готово.
        "prompt": "Дякую, основні дані зібрано! Натисніть /generate, щоб створити PDF-файл резюме.",
        "next_step": STEP_IDLE,
        "context_key": "summary"
    },
    STEP_IDLE: {
        "prompt": "Ви перебуваєте в режимі очікування команди. Використовуйте /generate.",
        "next_step": STEP_IDLE,
        "context_key": None
    },
}

def get_next_prompt(current_step):
    """Повертає повідомлення для наступного кроку."""
    return DIALOG_STEPS.get(current_step, DIALOG_STEPS[STEP_IDLE])["prompt"]


# ----------------------------------------------------------------------
# ОСНОВНІ ОБРОБНИКИ КОМАНД (АСИНХРОННІ)
# ----------------------------------------------------------------------

# ЗМІНА 1: Додано async
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробляє команду /start. Створює або знаходить користувача та сесію."""
    user = update.effective_user
    bot = context.bot

    # Робота з БД залишається синхронною (блокуючою), але це допустимо для прототипу
    db = get_db()
    try:
        telegram_data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
        }
        db_user = session_manager.get_or_create_user(db, user.id, telegram_data)

        next_step = STEP_WAITING_NAME
        # Оновлюємо сесію
        session_manager.update_session_context(
            db, db_user.id, {}, next_step=next_step
        )
    finally:
        db.close()

    # ЗМІНА 2: Додано await
    await bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Ласкаво просимо, {user.first_name}! {get_next_prompt(STEP_START)}"
    )


# ЗМІНА 1: Додано async
async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробляє команду /generate. Запускає генерацію PDF."""
    user_id = update.effective_user.id
    bot = context.bot

    # ЗМІНА 2: Додано await
    await bot.send_message(chat_id=update.effective_chat.id, text="Починаю генерацію вашого резюме...")

    db = get_db()
    try:
        db_user = session_manager.get_or_create_user(db, user_id, {})
        db_session = session_manager.get_session_by_user(db, db_user.id)

        if not db_session or db_session.current_step != STEP_IDLE:
            await bot.send_message(chat_id=update.effective_chat.id,
                                   text="Спочатку потрібно заповнити основні дані. Будь ласка, почніть з /start.")
            return

        try:
            # 1. Трансформація та валідація даних
            resume_data = transform_session_to_resume_data(db_session)

            # 2. Генерація PDF-файлу
            pdf_bytes = generate_pdf_from_data(resume_data)

            # 3. Відправка файлу користувачу (ЗМІНА 2: Додано await)
            await bot.send_document(
                chat_id=update.effective_chat.id,
                document=pdf_bytes,
                filename=f"CV_{db_user.first_name or 'User'}.pdf",
                caption="Ваше резюме готове! Щоб оновити, використовуйте команди додавання.",
                reply_markup=ReplyKeyboardRemove(),
            )
        except ValueError as e:
            await bot.send_message(chat_id=update.effective_chat.id,
                                   text=f"Помилка: Недостатньо даних для генерації. {e}")
        except Exception as e:
            print(f"Помилка генерації PDF: {e}")
            await bot.send_message(chat_id=update.effective_chat.id,
                                   text="Виникла внутрішня помилка при створенні PDF. Спробуйте пізніше.")
    finally:
        db.close()


# ЗМІНА 1: Додано async
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Головний обробник текстових повідомлень, що керує станом діалогу."""
    user_id = update.effective_user.id
    text = update.message.text
    bot = context.bot

    db = get_db()
    try:
        db_user = session_manager.get_or_create_user(db, user_id, {})
        db_session = session_manager.get_session_by_user(db, db_user.id)
        current_step = db_session.current_step

        if current_step not in DIALOG_STEPS or current_step == STEP_IDLE:
            await bot.send_message(chat_id=update.effective_chat.id, text=get_next_prompt(STEP_IDLE))
            return

        dialog_info = DIALOG_STEPS[current_step]
        next_step = dialog_info["next_step"]

        new_context_data = {}

        # 1. Обробка введених даних залежно від кроку
        if current_step == STEP_WAITING_NAME:
            new_context_data = {"personal": {"full_name": text}}

        elif current_step == STEP_WAITING_CONTACTS:
            parts = [p.strip() for p in text.split(',')]
            email = parts[0] if len(parts) > 0 else None
            phone = parts[1] if len(parts) > 1 else None
            # Зберігаємо також username, якщо він є
            username = db_user.username or ""

            new_context_data = {"personal": {"email": email, "phone": phone, "telegram_username": username}}

        elif current_step == STEP_WAITING_SUMMARY:
            new_context_data = {"personal": {"summary": text}}

        # 2. Оновлення сесії та перехід до наступного кроку
        if new_context_data:
            current_context = db_session.context or {}

            if 'personal' in new_context_data:
                personal_info = current_context.get('personal', {})
                personal_info.update(new_context_data['personal'])
                new_context_data = {'personal': personal_info}

            session_manager.update_session_context(
                db, db_user.id, new_context_data, next_step=next_step
            )

        # 3. Відправка наступного повідомлення (ЗМІНА 2: Додано await)
        await bot.send_message(chat_id=update.effective_chat.id, text=get_next_prompt(next_step))
    finally:
        db.close()