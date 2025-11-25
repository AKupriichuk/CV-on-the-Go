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
    transform_session_to_resume_data
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
        "prompt": "Дані збережено! Використовуйте /add_experience або /generate.",
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
    }
}

def get_next_prompt(current_step):
    return DIALOG_STEPS.get(current_step, DIALOG_STEPS[STEP_IDLE])["prompt"]


# --- ОБРОБНИКИ ---

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
            caption="Готово!",
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
            await bot.send_message(chat_id=update.effective_chat.id, text="Використовуйте /generate або /add_experience.")
            return

        dialog_info = DIALOG_STEPS.get(current_step)
        next_step = dialog_info["next_step"] if dialog_info else STEP_IDLE
        
        # --- СПЕЦІАЛЬНА ОБРОБКА ДЛЯ ОСТАННЬОГО КРОКУ ДОСВІДУ ---
        if current_step == STEP_WAITING_EXP_DESC:
            # 1. Зберігаємо опис у temp
            print(f"DEBUG: Отримано опис: {text}")
            new_data = {"temp_experience": {"description": text}}
            session_manager.update_session_context(db, db_user.id, new_data, next_step=STEP_IDLE)
            
            # 2. МИТТЄВО зберігаємо у фінальний список
            print("DEBUG: ВИКЛИКАЮ add_experience_item (ПРЯМИЙ ВИКЛИК)!")
            session_manager.add_experience_item(db, user_id)
            
            # 3. Відповідаємо і виходимо
            await bot.send_message(chat_id=update.effective_chat.id, text="✅ Досвід роботи збережено! Можна /generate")
            return

        # --- ОБРОБКА ВСІХ ІНШИХ КРОКІВ ---
        new_context_data = {}
        
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
        elif current_step == STEP_WAITING_EXP_COMPANY:
            new_context_data = {"temp_experience": {"company": text}}
        elif current_step == STEP_WAITING_EXP_POSITION:
            new_context_data = {"temp_experience": {"position": text}}
        elif current_step == STEP_WAITING_EXP_PERIOD:
             new_context_data = {"temp_experience": {"period": text}}

        # Оновлюємо сесію і йдемо до наступного питання
        session_manager.update_session_context(db, db_user.id, new_context_data, next_step=next_step)
        await bot.send_message(chat_id=update.effective_chat.id, text=get_next_prompt(next_step))
            
    finally:
        db.close()
