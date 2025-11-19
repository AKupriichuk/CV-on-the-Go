import pytest
from unittest.mock import MagicMock
from datetime import datetime, date
from app.logic.session_manager import (
    get_or_create_user,
    get_session_by_user,
    update_session_context,
    transform_session_to_resume_data,
    STEP_WAITING_NAME,
    STEP_IDLE
)
from app.models.orm import User, Session as DBSession  # Моделі ORM
from app.models.schemas import ResumeData  # Pydantic-схеми


# ----------------------------------------------------------------------
# ФІКСТУРИ (налаштування тестового середовища)
# ----------------------------------------------------------------------

# Фікстура для створення mock-об'єкта сесії бази даних
@pytest.fixture
def mock_db_session():
    """Створює Mock-об'єкт для сесії SQLAlchemy."""
    return MagicMock()


# Фікстура для імітації існуючого користувача
@pytest.fixture
def existing_user():
    """Повертає імітований об'єкт користувача."""
    user = User(
        id=101,
        telegram_id=12345,
        first_name="Олександр",
        last_name="Матвієнко"
    )
    return user


# Фікстура для імітації поточної сесії
@pytest.fixture
def current_db_session(existing_user):
    """Повертає імітований об'єкт сесії БД."""
    session = DBSession(
        id=1,
        user_id=existing_user.id,
        current_step=STEP_WAITING_NAME,
        context={"personal": {"full_name": "Олександр Матвієнко"}},
        updated_at=datetime.utcnow()
    )
    return session


# ----------------------------------------------------------------------
# ТЕСТИ ДЛЯ МОДУЛЯ КЕРУВАННЯ КОРИСТУВАЧАМИ
# ----------------------------------------------------------------------

def test_get_or_create_user_returns_existing(mock_db_session, existing_user):
    """Тест: Якщо користувач існує, він повинен бути повернутий, а не створений новий."""

    # Налаштовуємо Mock: при першому запиті повертаємо існуючого користувача
    mock_db_session.query().filter().first.return_value = existing_user

    user_data = {"first_name": "Олександр", "username": "oleksandr_m"}
    result = get_or_create_user(mock_db_session, 12345, user_data)

    # Перевіряємо, що новий користувач НЕ був доданий
    mock_db_session.add.assert_not_called()
    # Перевіряємо, що повернувся коректний об'єкт
    assert result.telegram_id == 12345
    assert result.first_name == "Олександр"


def test_get_or_create_user_creates_new(mock_db_session):
    """Тест: Якщо користувач не існує, він повинен бути створений."""

    # Налаштовуємо Mock: запит повертає None (користувача немає)
    mock_db_session.query().filter().first.return_value = None

    user_data = {"first_name": "Новий", "username": "new_user"}

    # Викликаємо функцію
    get_or_create_user(mock_db_session, 54321, user_data)

    # Перевіряємо, що:
    # 1. Був викликаний метод db.add()
    mock_db_session.add.assert_called()
    # 2. Був викликаний метод db.commit()
    mock_db_session.commit.assert_called()


# ----------------------------------------------------------------------
# ТЕСТИ ДЛЯ КЕРУВАННЯ СЕСІЯМИ ТА КОНТЕКСТОМ
# ----------------------------------------------------------------------

def test_get_session_by_user_success(mock_db_session, current_db_session):
    """Тест: Коректне отримання поточної сесії користувача."""

    # Налаштовуємо Mock: повертаємо імітовану сесію
    mock_db_session.query().filter().first.return_value = current_db_session

    session = get_session_by_user(mock_db_session, 101)

    assert session is not None
    assert session.current_step == STEP_WAITING_NAME


def test_update_session_context_changes_step_and_data(mock_db_session, current_db_session):
    """Тест: Оновлення контексту та перехід до наступного кроку."""

    # 1. Налаштовуємо Mock для отримання сесії
    mock_db_session.query().filter().first.return_value = current_db_session

    new_data = {"phone": "0991234567"}
    next_step = STEP_IDLE

    # 2. Викликаємо функцію оновлення
    updated_session = update_session_context(mock_db_session, 101, new_data, next_step)

    # 3. Перевірка:
    # Крок має змінитися
    assert updated_session.current_step == STEP_IDLE
    # Нові дані мають бути додані до контексту
    assert updated_session.context.get("phone") == "0991234567"
    # ВИПРАВЛЕНА ПЕРЕВІРКА:
    # 1. Перевіряємо, що існує секція 'personal'.
    assert 'personal' in updated_session.context
    # 2. Перевіряємо, що 'full_name' збережений всередині 'personal'.
    assert 'full_name' in updated_session.context['personal']

    mock_db_session.commit.assert_called_once()


# ----------------------------------------------------------------------
# ТЕСТИ ДЛЯ ТРАНСФОРМАЦІЇ ДАНИХ (ВАЛІДАЦІЯ Pydantic)
# ----------------------------------------------------------------------

def test_transform_session_to_resume_data_success():
    """Тест: Успішна трансформація повного контексту в Pydantic-об'єкт ResumeData."""

    # Імітація повного контексту сесії
    mock_session = MagicMock(spec=DBSession)
    mock_session.context = {
        "personal": {
            "full_name": "Олександр М.",
            "email": "test@example.com",
            "phone": "123",
            "summary": "Junior Developer"
        },
        "experience": [
            {
                "job_title": "Intern",
                "company": "Tech Corp",
                "start_date": date(2023, 1, 1),
                "end_date": None,
                "description": ["Code", "Test"]
            }
        ],
        "education": [
            {
                "degree": "Бакалавр",
                "institution": "Університет",
                "city": "Київ",
                "year_finished": 2024
            }
        ]
    }

    data_object = transform_session_to_resume_data(mock_session)

    # Перевіряємо, що повернутий об'єкт є коректною Pydantic-схемою
    assert isinstance(data_object, ResumeData)
    assert data_object.personal.full_name == "Олександр М."
    assert len(data_object.experience) == 1


def test_transform_session_to_resume_data_incomplete_data_raises_error():
    """Тест: Якщо не вистачає обов'язкових секцій, повинна виникнути помилка."""

    mock_session = MagicMock(spec=DBSession)
    # Відсутня секція 'education'
    mock_session.context = {
        "personal": {
            "full_name": "Іван",
            "email": "i@ua.com",
            "phone": "123",
            "summary": "Резюме"
        },
        "experience": []
    }

    # Очікуємо, що функція кине ValueError через відсутність обов'язкових полів
    with pytest.raises(ValueError, match="неповні"):
        transform_session_to_resume_data(mock_session)