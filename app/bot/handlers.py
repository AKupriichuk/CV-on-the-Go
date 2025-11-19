from telegram import Update, ReplyKeyboardRemove, File
from telegram.ext import ContextTypes
from app.core.database import get_db
from app.logic import session_manager
from app.logic.session_manager import (
    STEP_START, STEP_WAITING_NAME, STEP_WAITING_CONTACTS,
    STEP_WAITING_SUMMARY, STEP_IDLE,
    transform_session_to_resume_data
)
from app.pdf_generator.generator import generate_pdf_from_data

# ----------------------------------------------------------------------
# КРОКИ ДІАЛОГУ ТА ФУНКЦІЇ ЗАПИТУ
# ----------------------------------------------------------------------

# Зіставлення станів з наступним кроком та необхідним запитом
DIALOG_STEPS = {
    STEP_START: {
        "prompt": "Привіт! Я бот для швидкого створення резюме. Введіть ваше повне ім'я (ПІБ):",
        "next_step": STEP_WAITING_NAME,
        "context_key": None  # Початковий крок
    },
    STEP_WAITING_NAME: {
        "prompt": "Чудово! Тепер введіть вашу електронну пошту та телефон (наприклад: email@example.com, 0991234567):",
        "next_step": STEP_WAITING_CONTACTS,
        "context_key": "full_name"
    },
    STEP_WAITING_CONTACTS: {
        "prompt": "Дякую за контакти. Опишіть ваше професійне резюме (summary) одним абзацом:",
        "next_step": STEP_WAITING_SUMMARY,
        "context_key": "contacts"  # Обробляється у message_handler
    },
    STEP_WAITING_SUMMARY: {
        "prompt": "Дякую, основні дані зібрано! Натисніть /generate, щоб створити PDF-файл резюме, або почніть додавати досвід роботи /add_experience.",
        "next_step": STEP_IDLE,
        "context_key": "summary"
    },
    STEP_IDLE: {
        "prompt": "Ви перебуваєте в режимі очікування команди. Використовуйте /generate або /add_experience.",
        "next_step": STEP_IDLE,
        "context_key": None
    },
}


def get_next_prompt(current_step):
    """Повертає повідомлення для наступного кроку."""
    return DIALOG_STEPS.get(current_step, DIALOG_STEPS[STEP_IDLE])["prompt"]


def get_next_step(current_step):
    """Повертає наступний крок у State Machine."""
    return DIALOG_STEPS.get(current_step, DIALOG_STEPS[STEP_IDLE])["next_step"]


# ----------------------------------------------------------------------
# ОСНОВНІ ОБРОБНИКИ КОМАНД
# ----------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробляє команду /start. Створює або знаходить користувача та сесію."""
    user = update.effective_user
    with get_db() as db:
        telegram_data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
        }
        # Створюємо або отримуємо користувача та його сесію
        db_user = session_manager.get_or_create_user(db, user.id, telegram_data)
        db_session = session_manager.get_session_by_user(db, db_user.id)

        # Переводимо сесію на перший крок діалогу
        next_step = STEP_WAITING_NAME
        db_session = session_manager.update_session_context(
            db, db_user.id, {}, next_step=next_step
        )

    await update.message.reply_text(
        f"Ласкаво просимо, {user.first_name}! {get_next_prompt(STEP_START)}"
    )


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробляє команду /generate. Запускає генерацію PDF."""
    user_id = update.effective_user.id
    await update.message.reply_text("Починаю генерацію вашого резюме...")

    with get_db() as db:
        db_user = session_manager.get_or_create_user(db, user_id, {})
        db_session = session_manager.get_session_by_user(db, db_user.id)

        if not db_session or db_session.current_step != STEP_IDLE:
            await update.message.reply_text("Спочатку потрібно заповнити основні дані. Будь ласка, почніть з /start.")
            return

        try:
            # 1. Трансформація та валідація даних
            resume_data = transform_session_to_resume_data(db_session)

            # 2. Генерація PDF-файлу
            pdf_bytes = generate_pdf_from_data(resume_data)

            # 3. Відправка файлу користувачу
            await update.message.reply_document(
                document=pdf_bytes,
                filename=f"CV_{db_user.first_name}_{db_user.last_name}.pdf",
                caption="Ваше резюме готове! Щоб оновити, використовуйте команди додавання.",
                reply_markup=ReplyKeyboardRemove(),
            )
        except ValueError as e:
            await update.message.reply_text(f"Помилка: Недостатньо даних для генерації. {e}")
        except Exception:
            await update.message.reply_text("Виникла внутрішня помилка при створенні PDF. Спробуйте пізніше.")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Головний обробник текстових повідомлень, що керує станом діалогу."""
    user_id = update.effective_user.id
    text = update.message.text

    with get_db() as db:
        db_user = session_manager.get_or_create_user(db, user_id, {})
        db_session = session_manager.get_session_by_user(db, db_user.id)
        current_step = db_session.current_step

        if current_step not in DIALOG_STEPS or current_step == STEP_IDLE:
            await update.message.reply_text(get_next_prompt(STEP_IDLE))
            return

        # Визначаємо ключ, під яким зберегти дані, та наступний крок
        dialog_info = DIALOG_STEPS[current_step]
        context_key = dialog_info["context_key"]
        next_step = dialog_info["next_step"]

        new_context_data = {}

        # 1. Обробка введених даних залежно від кроку
        if current_step == STEP_WAITING_NAME:
            new_context_data = {"personal": {"full_name": text}}

        elif current_step == STEP_WAITING_CONTACTS:
            # Припускаємо, що контакти розділені комою
            parts = [p.strip() for p in text.split(',')]
            email = parts[0] if len(parts) > 0 else None
            phone = parts[1] if len(parts) > 1 else None

            new_context_data = {"personal": {"email": email, "phone": phone, "telegram_username": db_user.username}}

        elif current_step == STEP_WAITING_SUMMARY:
            new_context_data = {"personal": {"summary": text}}

        # 2. Оновлення сесії та перехід до наступного кроку

        # Ми повинні об'єднати дані з контекстом, якщо це не перше збереження
        # Проте, оскільки ми переходимо від кроку до кроку, просто оновлюємо
        # контекст, використовуючи загальний метод.
        if new_context_data:
            # Отримаємо поточний контекст
            current_context = db_session.context or {}

            # Якщо ми на кроці, де потрібно оновити вкладений словник 'personal'
            if 'personal' in new_context_data:
                # Оновлюємо вкладений 'personal'
                personal_info = current_context.get('personal', {})
                personal_info.update(new_context_data['personal'])
                new_context_data = {'personal': personal_info}

            # Оновлюємо сесію
            db_session = session_manager.update_session_context(
                db, db_user.id, new_context_data, next_step=next_step
            )

        # 3. Відправка наступного повідомлення
        await update.message.reply_text(get_next_prompt(next_step))