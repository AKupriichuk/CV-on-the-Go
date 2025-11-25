from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from app.core.database import get_db
from app.logic import session_manager
from app.pdf_generator.generator import generate_pdf_from_data
from app.logic.session_manager import (
    STEP_START, STEP_WAITING_NAME, STEP_WAITING_CONTACTS,
    STEP_WAITING_SUMMARY, STEP_IDLE,
    # Нові кроки
    STEP_WAITING_EXP_COMPANY, STEP_WAITING_EXP_POSITION,
    STEP_WAITING_EXP_PERIOD, STEP_WAITING_EXP_DESC,
    transform_session_to_resume_data
)

# ----------------------------------------------------------------------
# СЛОВНИК КРОКІВ
# ----------------------------------------------------------------------

DIALOG_STEPS = {
    # ... (Старі кроки залишаються такими ж) ...
    STEP_START: {
        "prompt": "Привіт! Я бот для створення резюме. Введіть ваше повне ім'я (ПІБ):",
        "next_step": STEP_WAITING_NAME,
        "context_key": None
    },
    STEP_WAITING_NAME: {
        "prompt": "Введіть ваше повне ім'я (ПІБ):",
        "next_step": STEP_WAITING_CONTACTS,
        "context_key": "full_name"
    },
    STEP_WAITING_CONTACTS: {
        "prompt": "Чудово! Тепер введіть вашу електронну пошту та телефон (email, телефон):",
        "next_step": STEP_WAITING_SUMMARY,
        "context_key": "contacts"
    },
    STEP_WAITING_SUMMARY: {
        "prompt": "Опишіть ваше професійне резюме (summary) одним абзацом:",
        "next_step": STEP_IDLE,
        "context_key": "summary"
    },
    STEP_IDLE: {
        "prompt": "Дані збережено! Використовуйте /add_experience для додавання досвіду або /generate для PDF.",
        "next_step": STEP_IDLE,
        "context_key": None
    },

    # --- НОВІ КРОКИ ДЛЯ ДОСВІДУ ---
    STEP_WAITING_EXP_COMPANY: {
        "prompt": "Введіть назву компанії:",
        "next_step": STEP_WAITING_EXP_POSITION,
        "context_key": "temp_experience.company"
    },
    STEP_WAITING_EXP_POSITION: {
        "prompt": "Введіть вашу посаду:",
        "next_step": STEP_WAITING_EXP_PERIOD,
        "context_key": "temp_experience.position"
    },
    STEP_WAITING_EXP_PERIOD: {
        "prompt": "Введіть період роботи (наприклад: 2020-2023 або 'Вересень 2021 - Зараз'):",
        "next_step": STEP_WAITING_EXP_DESC,
        "context_key": "temp_experience.period"
    },
    STEP_WAITING_EXP_DESC: {
        "prompt": "Опишіть ваші обов'язки та досягнення:",
        "next_step": STEP_IDLE,  # Після цього кроку ми фіналізуємо запис
        "context_key": "temp_experience.description"
    }
}


def get_next_prompt(current_step):
    return DIALOG_STEPS.get(current_step, DIALOG_STEPS[STEP_IDLE])["prompt"]


# ----------------------------------------------------------------------
# ОБРОБНИКИ КОМАНД
# ----------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # (Код без змін - як у вас було)
    user = update.effective_user
    bot = context.bot
    db = get_db()
    try:
        telegram_data = {"first_name": user.first_name, "last_name": user.last_name, "username": user.username}
        db_user = session_manager.get_or_create_user(db, user.id, telegram_data)
        session_manager.update_session_context(db, db_user.id, {}, next_step=STEP_WAITING_NAME)
    finally:
        db.close()
    await bot.send_message(chat_id=update.effective_chat.id, text=f"Ласкаво просимо! {get_next_prompt(STEP_START)}")


# НОВА КОМАНДА: /add_experience
async def add_experience_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Починає процес додавання досвіду роботи."""
    user_id = update.effective_user.id
    bot = context.bot

    db = get_db()
    try:
        # Знаходимо користувача
        db_user = session_manager.get_or_create_user(db, user_id, {})

        # Ініціалізуємо додавання досвіду: очищаємо temp_experience і ставимо перший крок
        initial_data = {"temp_experience": {}}
        session_manager.update_session_context(
            db, db_user.id, initial_data, next_step=STEP_WAITING_EXP_COMPANY
        )

        await bot.send_message(
            chat_id=update.effective_chat.id,
            text="Додавання нового місця роботи. " + get_next_prompt(STEP_WAITING_EXP_COMPANY)
        )
    finally:
        db.close()


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # (Код майже без змін, тільки текст помилки можемо покращити)
    user_id = update.effective_user.id
    bot = context.bot
    await bot.send_message(chat_id=update.effective_chat.id, text="Починаю генерацію вашого резюме...")

    db = get_db()
    try:
        db_user = session_manager.get_or_create_user(db, user_id, {})
        db_session = session_manager.get_session_by_user(db, db_user.id)

        try:
            resume_data = transform_session_to_resume_data(db_session)
            pdf_bytes = generate_pdf_from_data(resume_data)
            await bot.send_document(
                chat_id=update.effective_chat.id,
                document=pdf_bytes,
                filename=f"CV_{db_user.first_name}.pdf",
                caption="Ваше резюме готове!",
                reply_markup=ReplyKeyboardRemove(),
            )
        except ValueError as e:
            await bot.send_message(chat_id=update.effective_chat.id, text=f"Помилка даних: {e}")
        except Exception as e:
            print(f"Error: {e}")
            await bot.send_message(chat_id=update.effective_chat.id, text="Помилка генерації. Перевірте шаблони.")
    finally:
        db.close()


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text
    bot = context.bot

    db = get_db()
    try:
        db_user = session_manager.get_or_create_user(db, user_id, {})
        db_session = session_manager.get_session_by_user(db, db_user.id)
        current_step = db_session.current_step

        if current_step == STEP_IDLE:
            await bot.send_message(chat_id=update.effective_chat.id,
                                   text="Використовуйте /generate або /add_experience.")
            return

        dialog_info = DIALOG_STEPS.get(current_step)
        if not dialog_info:
            await bot.send_message(chat_id=update.effective_chat.id, text="Сталася помилка стану. Натисніть /start.")
            return

        next_step = dialog_info["next_step"]
        new_context_data = {}

        # --- ЛОГІКА ЗБОРУ ДАНИХ ---

        if current_step == STEP_WAITING_NAME:
            new_context_data = {"personal": {"full_name": text}}

        elif current_step == STEP_WAITING_CONTACTS:
            parts = [p.strip() for p in text.split(',')]
            email = parts[0] if len(parts) > 0 else ""
            phone = parts[1] if len(parts) > 1 else ""
            username = db_user.username or ""
            new_context_data = {"personal": {"email": email, "phone": phone, "telegram_username": username}}

        elif current_step == STEP_WAITING_SUMMARY:
            new_context_data = {"personal": {"summary": text}}

        # --- ЛОГІКА ДЛЯ ДОСВІДУ ---
        elif current_step == STEP_WAITING_EXP_COMPANY:
            new_context_data = {"temp_experience": {"company": text}}

        elif current_step == STEP_WAITING_EXP_POSITION:
            new_context_data = {"temp_experience": {"position": text}}

        elif current_step == STEP_WAITING_EXP_PERIOD:
            new_context_data = {"temp_experience": {"period": text}}

        elif current_step == STEP_WAITING_EXP_DESC:
            new_context_data = {"temp_experience": {"description": text}}

        # Оновлюємо сесію
        session_manager.update_session_context(db, db_user.id, new_context_data, next_step=next_step)

        # Якщо ми тільки що закінчили введення опису (останній крок досвіду), треба зберегти запис у список
        if current_step == STEP_WAITING_EXP_DESC:
            session_manager.add_experience_item(db, user_id)
            await bot.send_message(chat_id=update.effective_chat.id, text="Досвід роботи додано! ✅")
            await bot.send_message(chat_id=update.effective_chat.id,
                                   text="Можете додати ще один (/add_experience) або згенерувати PDF (/generate).")
        else:
            # Інакше просто йдемо далі
            await bot.send_message(chat_id=update.effective_chat.id, text=get_next_prompt(next_step))

    finally:
        db.close()