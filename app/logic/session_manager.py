from sqlalchemy.orm import Session as DBSession
from app.models.orm import User, Session
from app.models.schemas import ResumeData
from datetime import datetime
import json

# Константи кроків
STEP_START = "START"
STEP_WAITING_NAME = "WAITING_NAME"
STEP_WAITING_CONTACTS = "WAITING_CONTACTS"
STEP_WAITING_SUMMARY = "WAITING_SUMMARY"
STEP_IDLE = "IDLE"


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

        # Створюємо сесію для нового користувача
        session = Session(user_id=user.id, current_step=STEP_START)
        db.add(session)
        db.commit()

    return user


def get_session_by_user(db: DBSession, user_id: int) -> Session:
    """Повертає активну сесію користувача."""
    return db.query(Session).filter(Session.user_id == user_id).first()


def update_session_context(db: DBSession, user_id: int, new_data: dict, next_step: str = None) -> Session:
    """Оновлює дані в контексті сесії та перемикає крок."""
    session = get_session_by_user(db, user_id)
    if not session:
        return None

    # Оновлення словника контексту
    current_context = dict(session.context) if session.context else {}

    # Глибоке злиття (merge) для словників (щоб не перезаписувати все personal)
    for key, value in new_data.items():
        if isinstance(value, dict) and key in current_context:
            current_context[key].update(value)
        else:
            current_context[key] = value

    session.context = current_context

    if next_step:
        session.current_step = next_step

    session.updated_at = datetime.utcnow()

    # Force update for SQLAlchemy JSON field detection
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def transform_session_to_resume_data(session: Session) -> ResumeData:
    """
    Перетворює "сирі" дані з сесії в валідований об'єкт ResumeData.
    Додає пусті списки для необов'язкових полів, щоб уникнути помилок.
    """
    context = session.context or {}
    personal = context.get("personal", {})

    # Мінімальна валідація
    if not personal.get("full_name"):
        raise ValueError("Відсутнє повне ім'я")

    # Формування словника для Pydantic
    # ВАЖЛИВО: Ми додаємо пусті списки [], якщо даних немає
    resume_dict = {
        "personal": {
            "full_name": personal.get("full_name"),
            "email": personal.get("email"),
            "phone": personal.get("phone"),
            "summary": personal.get("summary"),
            "telegram_username": personal.get("telegram_username"),
            # Інші поля можуть бути None
            "linkedin": personal.get("linkedin"),
            "github": personal.get("github"),
            "website": personal.get("website")
        },
        # ДОДАНО: Значення за замовчуванням для списків
        "experience": context.get("experience", []),
        "education": context.get("education", []),
        "skills": context.get("skills", []),
        "projects": context.get("projects", [])
    }

    try:
        return ResumeData(**resume_dict)
    except Exception as e:
        raise ValueError(f"Дані резюме неповні або некоректні: {e}")