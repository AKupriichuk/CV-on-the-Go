import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from app.models.schemas import ResumeData
from typing import Optional

# Шлях до теки шаблонів (відносно кореня проєкту)
# Використовуємо ../templates, оскільки код знаходиться у app/pdf_generator/
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates')
# Створюємо інстанс Jinja2 для завантаження шаблонів
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def generate_pdf_from_data(resume_data: ResumeData) -> Optional[bytes]:
    """
    Рендерить HTML-шаблон з даними та конвертує його в PDF.

    :param resume_data: Валідований об'єкт Pydantic з даними резюме.
    :return: Бінарний вміст PDF-файлу.
    """
    try:
        # 1. Завантаження шаблону
        template = jinja_env.get_template('resume_template.html')

        # 2. Рендеринг HTML: перетворюємо Pydantic-об'єкт на словник для Jinja
        # Використовуємо .model_dump() для перетворення Pydantic-схеми в словник
        html_output = template.render(data=resume_data.model_dump())

        # 3. Генерація PDF за допомогою WeasyPrint (СИНХРОННИЙ БЛОКУЮЧИЙ ВИКЛИК)
        pdf_bytes = HTML(string=html_output).write_pdf()

        return pdf_bytes
    except Exception as e:
        print(f"Помилка при генерації PDF: {e}")
        # Помилка генерації PDF повертає None або re-raise, щоб обробити її в handlers.py
        raise