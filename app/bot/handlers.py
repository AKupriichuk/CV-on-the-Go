from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from app.core.database import get_db
from app.logic import session_manager
from app.pdf_generator.generator import generate_pdf_from_data
from app.logic.session_manager import (
    STEP_START, STEP_WAITING_NAME, STEP_WAITING_CONTACTS,
    STEP_WAITING_SUMMARY, STEP_IDLE,
    STEP_WAITING_EXP_COMPANY, STEP_WAITING_EXP_POSITION,
    STEP_WAITING_EXP_PERIOD, STEP_WAITING_EXP_DESC,
    STEP_WAITING_EDU_INSTITUTION, STEP_WAITING_EDU_DEGREE, STEP_WAITING_EDU_YEAR,
    STEP_WAITING_SKILL, # Навички
    transform_session_to_resume_data,
    add_experience_item, add_education_item, add_skill_item
)

# --- СЛОВНИК КРОКІВ ---
DIALOG_STEPS = {
    STEP_START: {
        "prompt": "Привіт! Я бот для створення резюме. Введіть ваше повне ім'я (ПІБ):",
        "next_step": STEP_WAITING_NAME
    },
    STEP_WAITING_NAME: {
        "prompt": "Введіть ваше повне ім'я (ПІБ):", 
        "next_step": STEP_WAITING_CONTACTS
    },
    STEP_WAITING_CONTACTS: {
        "prompt": "Чудово! Тепер введіть вашу електронну пошту та телефон (email, телефон):",
        "next_step": STEP_WAITING_SUMMARY
    },
    STEP_WAITING_SUMMARY: {
        "prompt": "Опишіть ваше професійне резюме (summary) одним абзацом:",
        "next_step": STEP_IDLE
    },
    STEP_IDLE: {
        "prompt": "Дані збережено! Доступні команди: /add_experience, /add_education, /add_skill, /generate.",
        "next_step": STEP_IDLE
    },
    # Досвід
    STEP_WAITING_EXP_COMPANY: {
        "prompt": "Введіть назву компанії:",
        "next_step": STEP_WAITING_EXP_POSITION
    },
    STEP_WAITING_EXP_POSITION: {
        "prompt": "Введіть вашу посаду:",
        "next_step": STEP_WAITING_EXP_PERIOD
    },
    STEP_WAITING_EXP_PERIOD: {
        "prompt": "Введіть період роботи (наприклад: '2021-2023'):",
        "next_step": STEP_WAITING_EXP_DESC
    },
    STEP_WAITING_EXP_DESC: {
        "prompt": "Опишіть ваші обов'язки:",
        "next_step": STEP_IDLE 
    },
    # Освіта
    STEP_WAITING_EDU_INSTITUTION: {
        "prompt": "Введіть назву навчального закладу:",
        "next_step": STEP_WAITING_EDU_DEGREE
    },
    STEP_WAITING_EDU_DEGREE: {
        "prompt": "Введіть спеціальність/ступінь:",
        "next_step": STEP_WAITING_EDU_YEAR
    },
    STEP_WAITING_EDU_YEAR: {
        "prompt": "Введіть рік закінчення:",
        "next_step": STEP_IDLE
    },
    # Навички
    STEP_WAITING_SKILL: {
        "prompt": "Введіть одну навичку або мову (наприклад: 'Python' або 'English B2'):",
        "next_step": STEP_IDLE
    }
}

def get_next_prompt(current_step):
    return DIALOG_STEPS.get(current_step, DIALOG_STEPS[STEP_IDLE])["prompt"]


# --- КОМАНДИ ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


async def add_experience_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    bot = context.bot
    db = get_db()
    try:
        db_user = session_manager.get_or_create_user(db, user_id, {})
        initial_data = {"temp_experience": {}} 
        session_manager.update_session_context(db, db_user.id, initial_data, next_step=STEP_WAITING_EXP_COMPANY)
        await bot.send_message(chat_id=update.effective_chat.id, text="Додавання роботи. " + get_next_prompt(STEP_WAITING_EXP_COMPANY))
    finally:
        db.close()


async def add_education_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    bot = context.bot
    db = get_db()
    try:
        db_user = session_manager.get_or_create_user(db, user_id, {})
        initial_data = {"temp_education": {}}
        session_manager.update_session_context(db, db_user.id, initial_data, next_step=STEP_WAITING_EDU_INSTITUTION)
        await bot.send_message(chat_id=update.effective_chat.id, text="Додавання освіти. " + get_next_prompt(STEP_WAITING_EDU_INSTITUTION))
    finally:
        db.close()


async def add_skill_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    bot = context.bot
    db = get_db()
    try:
        db_user = session_manager.get_or_create_user(db, user_id, {})
        session_manager.update_session_context(db, db_user.id, {}, next_step=STEP_WAITING_SKILL)
        await bot.send_message(chat_id=update.effective_chat.id, text="Додавання навички. " + get_next_prompt(STEP_WAITING_SKILL))
    finally:
        db.close()


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    bot = context.bot
    await bot.send_message(chat_id=update.effective_chat.id, text="Генерую PDF...")
    db = get_db()
    try:
        db_user = session_manager.get_or_create_user(db, user_id, {})
        db_session = session_manager.get_session_by_user(db, db_user.id)
        resume_data = transform_session_to_resume_data(db_session)
        pdf_bytes = generate_pdf_from_data(resume_data)
        await bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_bytes,
            filename=f"CV_{db_user.first_name}.pdf",
            caption="Ось ваше резюме!",
            reply_markup=ReplyKeyboardRemove(),
        )
    except Exception as e:
        print(f"Error PDF: {e}")
        await bot.send_message(chat_id=update.effective_chat.id, text=f"Помилка: {e}")
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
            await bot.send_message(chat_id=update.effective_chat.id, text="Використовуйте меню команд (/add...).")
            return

        dialog_info = DIALOG_STEPS.get(current_step)
        next_step = dialog_info["next_step"] if dialog_info else STEP_IDLE
        
        # --- ФІНАЛІЗАЦІЯ ДОСВІДУ ---
        if current_step == STEP_WAITING_EXP_DESC:
            new_data = {"temp_experience": {"description": text}}
            session_manager.update_session_context(db, db_user.id, new_data, next_step=STEP_IDLE)
            session_manager.add_experience_item(db, user_id)
            await bot.send_message(chat_id=update.effective_chat.id, text="✅ Досвід роботи збережено!")
            return

        # --- ФІНАЛІЗАЦІЯ ОСВІТИ ---
        if current_step == STEP_WAITING_EDU_YEAR:
            new_data = {"temp_education": {"year": text}}
            session_manager.update_session_context(db, db_user.id, new_data, next_step=STEP_IDLE)
            session_manager.add_education_item(db, user_id)
            await bot.send_message(chat_id=update.effective_chat.id, text="✅ Освіту збережено!")
            return

        # --- ФІНАЛІЗАЦІЯ НАВИЧКИ ---
        if current_step == STEP_WAITING_SKILL:
            session_manager.add_skill_item(db, user_id, text)
            await bot.send_message(chat_id=update.effective_chat.id, text=f"✅ Навичку '{text}' додано!")
            return

        # --- ІНШІ КРОКИ ---
        new_context_data = {}
        
        if current_step == STEP_WAITING_NAME:
            new_context_data = {"personal": {"full_name": text}}
        elif current_step == STEP_WAITING_CONTACTS:
            parts = [p.strip() for p in text.split(',')]
            email = parts[0] if len(parts) > 0 else ""
            phone = parts[1] if len(parts) > 1 else ""
            new_context_data = {"personal": {"email": email, "phone": phone}}
        elif current_step == STEP_WAITING_SUMMARY:
            new_context_data = {"personal": {"summary": text}}
        elif current_step == STEP_WAITING_EXP_COMPANY:
            new_context_data = {"temp_experience": {"company": text}}
        elif current_step == STEP_WAITING_EXP_POSITION:
            new_context_data = {"temp_experience": {"position": text}}
        elif current_step == STEP_WAITING_EXP_PERIOD:
             new_context_data = {"temp_experience": {"period": text}}
        elif current_step == STEP_WAITING_EDU_INSTITUTION:
            new_context_data = {"temp_education": {"institution": text}}
        elif current_step == STEP_WAITING_EDU_DEGREE:
            new_context_data = {"temp_education": {"degree": text}}

        session_manager.update_session_context(db, db_user.id, new_context_data, next_step=next_step)
        await bot.send_message(chat_id=update.effective_chat.id, text=get_next_prompt(next_step))
            
    finally:
        db.close()
