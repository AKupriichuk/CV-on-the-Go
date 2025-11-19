from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. Визначення шляху до бази даних SQLite
# У моноліті для MVP використовуємо SQLite як файл у корені проєкту.
SQL_DATABASE_URL = "sqlite:///./cv_on_the_go.db"

# 2. Створення рушія (Engine)
# connect_args потрібні для SQLite, оскільки FastAPI є асинхронним
# (це дозволяє SQLite працювати в окремому потоці, не блокуючи основний цикл)
engine = create_engine(
    SQL_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 3. Створення класу сесій
# Кожен запит до бази даних буде використовувати об'єкт SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Створення базового класу для моделей ORM
# Усі наші моделі у файлі orm.py будуть успадковувати цей клас
Base = declarative_base()


def get_db():
    """Dependency для FastAPI, яка надає сесію БД та гарантує її закриття."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Функція для створення таблиць у базі даних (викликається при запуску застосунку)."""
    # Це імпортує всі моделі ORM, щоб Base їх "знала"
    from app.models.orm import User, Session, Resume, Template, PDFFile

    # Створює всі таблиці, визначені через Base
    Base.metadata.create_all(bind=engine)