import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from app.models.schemas import ResumeData

# Шлях до теки шаблонів (відносно кореня проєкту)
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates')
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def generate_pdf_from_data(resume_data: ResumeData) -> bytes:
    """
    Рендерить HTML-шаблон з даними та конвертує його в PDF.

    :param resume_data: Валідований об'єкт Pydantic з даними резюме.
    :return: Бінарний вміст PDF-файлу.
    """
    try:
        # 1. Завантаження шаблону
        template = jinja_env.get_template('resume_template.html')

        # 2. Рендеринг HTML: перетворюємо Pydantic-об'єкт на словник для Jinja
        html_output = template.render(data=resume_data.model_dump())

        # 3. Генерація PDF за допомогою WeasyPrint
        pdf_bytes = HTML(string=html_output).write_pdf()

        return pdf_bytes
    except Exception as e:
        print(f"Помилка при генерації PDF: {e}")
        raise