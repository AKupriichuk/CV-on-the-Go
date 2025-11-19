from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

# Імпортуємо Base із app.core.database для наслідування
from app.core.database import Base


# -------------------- 1. МОДЕЛІ КОРИСТУВАЧІВ ТА СЕСІЙ --------------------

class User(Base):
    """Таблиця users: зберігає дані користувачів Telegram."""
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)  # ID користувача Telegram
    telegram_id = Column(BigInteger, unique=True, nullable=False)  # Дублювання для зручності
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Зв'язки
    sessions = relationship("Session", back_populates="user")
    resumes = relationship("Resume", back_populates="user")


class Session(Base):
    """Таблиця sessions: зберігає поточний стан діалогу (State Machine)."""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    current_step = Column(String, default="START")  # Поточний крок діалогу (START, WAITING_FOR_NAME, etc.)
    context = Column(JSON, default={})  # Зберігає проміжні введені дані у форматі JSON
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Зв'язки
    user = relationship("User", back_populates="sessions")


# -------------------- 2. МОДЕЛІ РЕЗЮМЕ ТА ШАБЛОНІВ --------------------

class Template(Base):
    """Таблиця templates: зберігає HTML/CSS шаблони оформлення."""
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    language = Column(String, default="uk")
    html = Column(Text, nullable=False)  # HTML-розмітка
    css = Column(Text, nullable=True)  # CSS-стилі
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Зв'язки
    resumes = relationship("Resume", back_populates="template")


class Resume(Base):
    """Таблиця resumes: зберігає фінальні структуровані дані резюме."""
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=False)

    title = Column(String, default="Мій Профіль")
    language = Column(String, default="uk")
    # Зберігаємо структуровані дані резюме (відповідно до Pydantic-схем)
    data = Column(JSON, nullable=False)

    is_draft = Column(Boolean, default=True)  # Чернетка чи фінальна версія
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Зв'язки
    user = relationship("User", back_populates="resumes")
    template = relationship("Template", back_populates="resumes")
    pdf_files = relationship("PDFFile", back_populates="resume")


class PDFFile(Base):
    """Таблиця pdf_files: зберігає метадані згенерованих файлів."""
    __tablename__ = "pdf_files"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False)

    # Шлях до файлу у файловій системі або у сховищі
    storage_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Зв'язки
    resume = relationship("Resume", back_populates="pdf_files")