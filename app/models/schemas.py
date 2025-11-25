from typing import List, Optional
from pydantic import BaseModel, Field

# --- Схеми для Складових Частин Резюме ---

class PersonalInfo(BaseModel):
    """Схема для особистої інформації користувача."""
    # Змінив EmailStr на str, щоб уникнути помилок, якщо користувач введе пробіл випадково
    full_name: str = Field(..., min_length=2, description="Повне ім'я та прізвище")
    email: Optional[str] = Field(None, description="Контактна електронна пошта")
    phone: Optional[str] = Field(None, description="Контактний телефон")
    # Змінив HttpUrl на str, бо користувачі часто лінуються писати https://
    linkedin: Optional[str] = Field(None, description="Посилання на профіль LinkedIn")
    github: Optional[str] = Field(None, description="Посилання на GitHub")
    website: Optional[str] = Field(None, description="Вебсайт")
    telegram_username: Optional[str] = Field(None, description="Telegram")
    summary: Optional[str] = Field(None, description="Коротке резюме")


class ExperienceItem(BaseModel):
    """Схема для одного запису досвіду роботи."""
    job_title: str = Field(..., description="Назва посади")
    company: str = Field(..., description="Назва компанії")
    # ВАЖЛИВО: Змінив date на str, щоб приймати текст "Вересень 2021"
    start_date: str = Field(..., description="Дата початку роботи")
    end_date: Optional[str] = Field(None, description="Дата завершення роботи")
    description: List[str] = Field(..., description="Список обов'язків")


class EducationItem(BaseModel):
    """Схема для одного запису про освіту."""
    degree: str = Field(..., description="Ступінь")
    institution: str = Field(..., description="Навчальний заклад")
    city: Optional[str] = Field(None, description="Місто")
    year_finished: str = Field(..., description="Рік завершення")


# --- Головна Схема Даних Резюме ---

class ResumeData(BaseModel):
    """Головна структура, що містить усі дані для генерації PDF."""
    personal: PersonalInfo
    experience: List[ExperienceItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    # Поки що зробимо skills простим списком рядків, бо ми ще не робили групування
    skills: List[str] = Field(default_factory=list)
    projects: List[dict] = Field(default_factory=list)
