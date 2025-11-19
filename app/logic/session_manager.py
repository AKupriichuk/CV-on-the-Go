from sqlalchemy.orm import Session
from app.models.orm import User, Session as DBSession  # Перейменовуємо ORM-модель Session, щоб уникнути конфлікту імен
from app.models.schemas import PersonalInfo, ResumeData  # Імпорт Pydantic-схем
from datetime import datetime
from typing import Dict, Any, Optional

# --- ВАЖЛИВІ КОНСТАНТИ ДЛЯ STATE MACHINE ---
# Це кроки, які буде проходити користувач.
STEP_START = "START"
STEP_WAITING_NAME = "WAITING_FOR_NAME"
STEP_WAITING_CONTACTS = "WAITING_FOR_CONTACTS"
STEP_WAITING_SUMMARY = "WAITING_FOR_SUMMARY"
STEP_IDLE = "IDLE"  # Стан, коли резюме заповнено


# ----------------------------------------------------------------------
# 1. ФУНКЦІЇ КЕРУВАННЯ КОРИСТУВАЧАМИ
# ----------------------------------------------------------------------

def get_or_create_user(db: Session, telegram_id: int, user_data: Dict[str, Any]) -> User:
    """Знаходить користувача за ID Telegram або створює нового."""

    # 1. Шукаємо користувача
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if user:
        # Оновлюємо час останньої активності
        user.last_active_at = datetime.utcnow()
        db.commit()
        return user
    else:
        # 2. Якщо користувача немає, створюємо нового
        new_user = User(
            telegram_id=telegram_id,
            first_name=user_data.get('first_name'),
            last_name=user_data.get('last_name'),
            username=user_data.get('username')
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # Одночасно створюємо для нього порожню сесію
        create_initial_session(db, new_user.id)

        return new_user


def create_initial_session(db: Session, user_id: int):
    """Створює початкову сесію для нового користувача."""
    initial_session = DBSession(
        user_id=user_id,
        current_step=STEP_START,
        context={}
    )
    db.add(initial_session)
    db.commit()
    db.refresh(initial_session)


# ----------------------------------------------------------------------
# 2. ФУНКЦІЇ КЕРУВАННЯ СЕСІЯМИ ТА СТАНОМ (STATE MACHINE)
# ----------------------------------------------------------------------

def get_session_by_user(db: Session, user_id: int) -> Optional[DBSession]:
    """Повертає поточну активну сесію користувача."""
    return db.query(DBSession).filter(DBSession.user_id == user_id).first()


def update_session_context(db: Session, user_id: int, new_data: Dict[str, Any],
                           next_step: Optional[str] = None) -> DBSession:
    """
    Оновлює контекст (проміжні дані) поточної сесії та переводить її на наступний крок.

    :param db: Сесія БД
    :param user_id: ID користувача
    :param new_data: Дані, які потрібно додати/оновтити в контексті (JSON)
    :param next_step: Наступний стан діалогу
    :return: Оновлений об'єкт сесії
    """
    session = get_session_by_user(db, user_id)
    if not session:
        raise ValueError(f"Сесія для користувача {user_id} не знайдена.")

    # Оновлюємо контекст: додаємо нові дані до існуючого JSON
    current_context = session.context
    current_context.update(new_data)
    session.context = current_context

    # Оновлюємо крок, якщо він наданий
    if next_step:
        session.current_step = next_step

    session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(session)
    return session


# ----------------------------------------------------------------------
# 3. ФУНКЦІЯ ТРАНСФОРМАЦІЇ (КЛЮЧ ДО PDF-ГЕНЕРАЦІЇ)
# ----------------------------------------------------------------------

def transform_session_to_resume_data(session: DBSession) -> ResumeData:
    """
    Трансформує JSON-контекст сесії у валідований Pydantic об'єкт ResumeData.
    Це фінальна перевірка перед генерацією PDF.
    """
    context = session.context

    # На цьому етапі ми перевіряємо, чи всі ключові секції заповнені
    if 'personal' not in context or 'experience' not in context or 'education' not in context:
        raise ValueError("Дані резюме неповні для генерації.")

    # Створюємо фінальний об'єкт, використовуючи Pydantic для валідації
    # Якщо Pydantic не зможе створити об'єкт, він автоматично кине виняток.

    # Примітка: Оскільки контекст може містити дані в різних форматах,
    # ми припускаємо, що дані зберігаються у вигляді, сумісному з Pydantic.
    resume_data = ResumeData.model_validate(context)

    return resume_data