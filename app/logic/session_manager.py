from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm.attributes import flag_modified
from app.models.orm import User, Session
from app.models.schemas import ResumeData
from datetime import datetime
import copy

# --- КОНСТАНТИ КРОКІВ (ОНОВЛЕНО) ---
STEP_START = "START"
STEP_WAITING_NAME = "WAITING_NAME"
STEP_WAITING_CONTACTS = "WAITING_CONTACTS"
STEP_WAITING_SUMMARY = "WAITING_SUMMARY"
STEP_IDLE = "IDLE"

# Нові кроки для досвіду роботи
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
    return db.query(Session).filter(Session.user_id == user_id).first()


def update_session_context(db: DBSession, user_id: int, new_data: dict, next_step: str = None) -> Session:
    """Оновлює дані в контексті сесії та перемикає крок."""
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
        print(f"Помилка при збереженні сесії: {e}")
        db.rollback()

    return session


def add_experience_item(db: DBSession, user_id: int) -> Session:
    """
    Переносить дані з 'temp_experience' у список 'experience' і очищає temp.
    Викликається, коли користувач завершив введення всіх полів для однієї роботи.
    """
    session = get_session_by_user(db, user_id)
    if not session:
        return None

    context = copy.deepcopy(session.context) or {}
    temp_exp = context.get("temp_experience", {})

    if temp_exp:
        # Отримуємо поточний список або створюємо новий
        experience_list = context.get("experience", [])

        # Формуємо фінальний об'єкт для роботи
        # Важливо: Pydantic схема може очікувати date об'єкти, але поки зберігаємо як рядки для простоти
        new_job = {
            "company": temp_exp.get("company"),
            "job_title": temp_exp.get("position"),  # у Pydantic схемі це job_title
            # Для спрощення MVP зберігаємо дати як один рядок або просто текст,
            # але в ідеалі треба парсити дати. Поки запишемо в start_date як текст.
            "start_date": temp_exp.get("period"),
            "end_date": None,
            "description": [temp_exp.get("description")]  # Опис як список (пунктів)
        }

        experience_list.append(new_job)
        context["experience"] = experience_list

        # Видаляємо тимчасові дані
        if "temp_experience" in context:
            del context["temp_experience"]

        session.context = context
        flag_modified(session, "context")
        session.current_step = STEP_IDLE  # Повертаємось в режим очікування

        db.add(session)
        db.commit()

    return session


def transform_session_to_resume_data(session: Session) -> ResumeData:
    """Перетворює дані сесії в ResumeData."""
    context = session.context or {}
    personal = context.get("personal", {})

    # Очищення даних перед валідацією (handling None)
    resume_dict = {
        "personal": {
            "full_name": personal.get("full_name") or "User",
            "email": personal.get("email") or "",
            "phone": personal.get("phone") or "",
            "summary": personal.get("summary") or "",
            "telegram_username": personal.get("telegram_username"),
            "linkedin": personal.get("linkedin"),
            "github": personal.get("github"),
            "website": personal.get("website")
        },
        # Тут ми беремо вже готовий список experience
        "experience": context.get("experience", []),
        "education": context.get("education", []),
        "skills": context.get("skills", []),
        "projects": context.get("projects", [])
    }

    try:
        # Примітка: Pydantic може лаятися на дати, якщо вони не в форматі YYYY-MM-DD.
        # Для MVP ми можемо спробувати передати, але якщо будуть помилки,
        # треба буде підправити schemas.py, щоб поля дат приймали str.
        return ResumeData(**resume_dict)
    except Exception as e:
        print(f"Validation Error Data: {resume_dict}")
        raise ValueError(f"{e}")