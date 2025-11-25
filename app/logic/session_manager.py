from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm.attributes import flag_modified
from app.models.orm import User, Session
from app.models.schemas import ResumeData
from datetime import datetime
import copy
import json

# --- КОНСТАНТИ КРОКІВ ---
STEP_START = "START"
STEP_WAITING_NAME = "WAITING_NAME"
STEP_WAITING_CONTACTS = "WAITING_CONTACTS"
STEP_WAITING_SUMMARY = "WAITING_SUMMARY"
STEP_IDLE = "IDLE"

# Кроки для досвіду роботи
STEP_WAITING_EXP_COMPANY = "WAITING_EXP_COMPANY"
STEP_WAITING_EXP_POSITION = "WAITING_EXP_POSITION"
STEP_WAITING_EXP_PERIOD = "WAITING_EXP_PERIOD"
STEP_WAITING_EXP_DESC = "WAITING_EXP_DESC"


def get_or_create_user(db: DBSession, telegram_id: int, user_data: dict) -> User:
    """Знаходить користувача за telegram_id або створює нового."""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            first_name=user_data.get("first_name"),
            last_name=user_data.get("last_name"),
            username=user_data.get("username")
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        session = Session(user_id=user.id, current_step=STEP_START, context={})
        db.add(session)
        db.commit()
    
    return user


def get_session_by_user(db: DBSession, user_id: int) -> Session:
    """Повертає сесію за ВНУТРІШНІМ user_id (не Telegram ID)."""
    return db.query(Session).filter(Session.user_id == user_id).first()


def update_session_context(db: DBSession, user_id: int, new_data: dict, next_step: str = None) -> Session:
    """Оновлює дані в контексті сесії та перемикає крок."""
    # Тут user_id - це внутрішній ID, бо ми його отримуємо з get_or_create_user в handlers
    session = get_session_by_user(db, user_id)
    if not session:
        return None
    
    current_context = copy.deepcopy(session.context) if session.context else {}
    
    # Merge логіка
    for key, value in new_data.items():
        if isinstance(value, dict) and key in current_context and isinstance(current_context[key], dict):
            current_context[key].update(value)
        else:
            current_context[key] = value
            
    session.context = current_context
    flag_modified(session, "context")
    
    if next_step:
        session.current_step = next_step
        
    session.updated_at = datetime.utcnow()
    
    try:
        db.add(session)
        db.commit()
        db.refresh(session)
    except Exception as e:
        print(f"CRITICAL ERROR SAVING SESSION: {e}")
        db.rollback()
        
    return session


def add_experience_item(db: DBSession, telegram_id: int) -> Session:
    """
    Переносить дані з 'temp_experience' у список 'experience'.
    Приймає telegram_id, знаходить user.id і тоді шукає сесію.
    """
    print(f"--- STARTING add_experience_item for Telegram ID: {telegram_id} ---")
    
    # 1. Спочатку знайдемо користувача за Telegram ID
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        print(f"ERROR: User with telegram_id {telegram_id} not found")
        return None
        
    # 2. Тепер шукаємо сесію за внутрішнім ID користувача (user.id)
    session = get_session_by_user(db, user.id)
    
    if not session:
        print(f"ERROR: No session found for internal user_id {user.id}")
        return None
        
    context = copy.deepcopy(session.context) or {}
    temp_exp = context.get("temp_experience", {})
    print(f"DEBUG: temp_experience content: {temp_exp}")
    
    if temp_exp:
        experience_list = context.get("experience", [])
        
        new_job = {
            "company": temp_exp.get("company"),
            "job_title": temp_exp.get("position"),
            "start_date": temp_exp.get("period"),
            "end_date": None,
            "description": [temp_exp.get("description")]
        }
        
        experience_list.append(new_job)
        context["experience"] = experience_list
        
        # Очищаємо тимчасові дані
        if "temp_experience" in context:
            del context["temp_experience"]
            
        session.context = context
        flag_modified(session, "context")
        session.current_step = STEP_IDLE
        
        db.add(session)
        db.commit()
        print(f"SUCCESS: JOB ADDED TO DB: {new_job}")
    else:
        print(f"ERROR: TEMP_EXP IS EMPTY! NOTHING TO ADD.")
        
    return session


def transform_session_to_resume_data(session: Session) -> ResumeData:
    """Готує дані для генерації PDF."""
    context = session.context or {}
    personal = context.get("personal", {})

    resume_dict = {
        "personal": {
            "full_name": personal.get("full_name") or "User",
            "email": personal.get("email"),
            "phone": personal.get("phone"),
            "summary": personal.get("summary"),
            "telegram_username": personal.get("telegram_username"),
            "linkedin": personal.get("linkedin"),
            "github": personal.get("github"),
            "website": personal.get("website")
        },
        "experience": context.get("experience", []),
        "education": context.get("education", []),
        "skills": context.get("skills", []),
        "projects": context.get("projects", [])
    }
    
    print(f"DEBUG DATA FOR PDF: {resume_dict}")

    try:
        return ResumeData(**resume_dict)
    except Exception as e:
        print(f"Validation Error: {e}")
        raise ValueError(f"{e}")
