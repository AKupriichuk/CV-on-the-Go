from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr, HttpUrl


# --- Схеми для Складових Частин Резюме (використовуються в ResumeData) ---

class PersonalInfo(BaseModel):
    """Схема для особистої інформації користувача."""
    full_name: str = Field(..., min_length=2, description="Повне ім'я та прізвище")
    email: EmailStr = Field(..., description="Контактна електронна пошта")
    phone: str = Field(..., description="Контактний телефон")
    linkedin_url: Optional[HttpUrl] = Field(None, description="Посилання на профіль LinkedIn")
    github_url: Optional[HttpUrl] = Field(None, description="Посилання на GitHub")
    summary: str = Field(..., description="Коротке резюме/огляд професійних цілей")


class Experience(BaseModel):
    """Схема для одного запису досвіду роботи."""
    job_title: str = Field(..., description="Назва посади")
    company: str = Field(..., description="Назва компанії")
    start_date: date = Field(..., description="Дата початку роботи (формат YYYY-MM-DD)")
    end_date: Optional[date] = Field(None, description="Дата завершення роботи. Null, якщо працює зараз.")
    description: List[str] = Field(..., description="Список ключових досягнень або обов'язків")


class Education(BaseModel):
    """Схема для одного запису про освіту."""
    degree: str = Field(..., description="Отриманий ступінь (наприклад, Магістр, Бакалавр)")
    institution: str = Field(..., description="Назва навчального закладу")
    city: str = Field(..., description="Місто")
    year_finished: int = Field(..., ge=1900, description="Рік завершення навчання")


class SkillGroup(BaseModel):
    """Схема для групи навичок (наприклад, 'Мови програмування')."""
    group_name: str = Field(..., description="Назва групи навичок (наприклад, 'Frontend', 'Databases')")
    skills: List[str] = Field(..., description="Список навичок у групі")


# --- Головна Схема Даних Резюме ---

class ResumeData(BaseModel):
    """Головна структура, що містить усі дані для генерації PDF."""

    # Використовуємо вкладені схеми, визначені вище
    personal: PersonalInfo
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    skills: List[SkillGroup] = Field(default_factory=list)

    # Додаткові дані, які можуть знадобитися для шаблону
    template_name: str = "cv_basic"
    language: str = "uk"