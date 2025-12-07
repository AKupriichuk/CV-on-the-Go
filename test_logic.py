import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models.orm import User, Session
from app.logic import session_manager


# Фікстура: створює тимчасову БД в оперативній пам'яті
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_create_user_logic(db_session):
    """Перевірка створення нового користувача"""
    tg_id = 123456
    user_data = {"first_name": "Test", "username": "tester"}
    user = session_manager.get_or_create_user(db_session, tg_id, user_data)
    assert user.telegram_id == tg_id
    assert user.username == "tester"


def test_add_experience_logic(db_session):
    """Перевірка складної логіки додавання досвіду"""
    # 1. Підготовка
    tg_id = 999
    user = session_manager.get_or_create_user(db_session, tg_id, {})

    # 2. Емуляція введення даних користувачем (Temp Storage)
    temp_data = {
        "temp_experience": {
            "company": "Google",
            "position": "Senior Dev",
            "period": "2020-2024",
            "description": "Backend development"
        }
    }
    session_manager.update_session_context(db_session, user.id, temp_data)

    # 3. Виклик функції фіналізації (збереження)
    session_manager.add_experience_item(db_session, tg_id)

    # 4. Перевірка результату
    session_obj = session_manager.get_session_by_user(db_session, user.id)
    # Список досвіду не має бути пустим
    assert len(session_obj.context["experience"]) == 1
    # Дані мають відповідати введеним
    assert session_obj.context["experience"][0]["company"] == "Google"
    # Тимчасовий буфер має очиститися
    assert "temp_experience" not in session_obj.context
