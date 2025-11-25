from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm.attributes import flag_modified  # ВАЖЛИВО: для фіксації змін в JSON
from app.models.orm import User, Session
from app.models.schemas import ResumeData
from datetime import datetime
import copy

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
        session = Session(user_id=user.id, current_step=STEP_START, context={})
        db.add(session)
        db.commit()

    return user


def get_session_by_user(db: DBSession, user_id: int) -> Session:
    """Повертає активну сесію користувача."""
    return db.query(Session).filter(Session.user_id == user_id).first()


def update_session_context(db: DBSession, user_id: int, new_data: dict, next_step: str = None) -> Session:
    """
    Оновлює дані в контексті сесії та перемикає крок.
    Використовує глибоке копіювання та flag_modified для надійності.
    """
    session = get_session_by_user(db, user_id)
    if not session:
        return None

    # 1. Беремо поточний контекст (глибока копія, щоб не було проблем з посиланнями)
    current_context = copy.deepcopy(session.context) if session.context else {}

    # 2. Розумне об'єднання (Deep Merge) для словників (зокрема ключа 'personal')
    for key, value in new_data.items():
        if isinstance(value, dict) and key in current_context and isinstance(current_context[key], dict):
            current_context[key].update(value)
        else:
            current_context[key] = value

    # 3. Записуємо оновлений контекст назад
    session.context = current_context

    # 4. ВАЖЛИВО: Явно повідомляємо SQLAlchemy, що поле JSON змінилося
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


def transform_session_to_resume_data(session: Session) -> ResumeData:
    """
    Перетворює "сирі" дані з сесії в валідований об'єкт ResumeData.
    """
    context = session.context or {}
    personal = context.get("personal", {})

    # Додаємо порожні значення, якщо їх немає, щоб уникнути помилок NoneType
    resume_dict = {
        "personal": {
            "full_name": personal.get("full_name") or "",
            "email": personal.get("email") or "",
            "phone": personal.get("phone") or "",
            "summary": personal.get("summary") or "",
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

    try:
        return ResumeData(**resume_dict)
    except Exception as e:
        # Для дебагу виведемо, що саме ми намагалися запхати в модель
        print(f"DEBUG DATA: {resume_dict}")
        raise ValueError(f"{e}")