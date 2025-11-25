from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQL_DATABASE_URL = "sqlite:///./cv_on_the_go.db"

# connect_args потрібні для SQLite
engine = create_engine(
    SQL_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ЗМІНЕНО: Прибираємо генератор (yield) для синхронної роботи
def get_db():
    """Повертає нову сесію БД.
    Тепер функція, що викликає, має сама закрити сесію.
    """
    return SessionLocal()


def init_db():
    """Функція для створення таблиць у базі даних (викликається при запуску застосунку)."""
    # Це імпортує всі моделі ORM, щоб Base їх "знала"
    from app.models.orm import User, Session, Resume, Template, PDFFile

    # Створює всі таблиці, визначені через Base
    Base.metadata.create_all(bind=engine)