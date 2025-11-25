import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from app.models.schemas import ResumeData
from typing import Optional

# Визначаємо шлях до поточного файлу (generator.py)
current_dir = os.path.dirname(os.path.abspath(__file__))

# Піднімаємося на два рівні вгору: app -> root
# Потім заходимо в templates
TEMPLATE_DIR = os.path.join(current_dir, '..', '..', 'templates')
# Нормалізуємо шлях (прибираємо .., щоб він виглядав гарно)
TEMPLATE_DIR = os.path.normpath(TEMPLATE_DIR)

print(f"DEBUG: Шлях до шаблонів: {TEMPLATE_DIR}")

# Створюємо середовище Jinja2
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def generate_pdf_from_data(resume_data: ResumeData) -> Optional[bytes]:
    """
    Рендерить HTML-шаблон з даними та конвертує його в PDF.
    """
    try:
        # Завантажуємо шаблон
        template = jinja_env.get_template('resume_template.html')

        # Рендеримо HTML
        html_output = template.render(data=resume_data.model_dump())

        # Генеруємо PDF
        pdf_bytes = HTML(string=html_output).write_pdf()

        return pdf_bytes
    except Exception as e:
        print(f"Помилка при генерації PDF: {e}")
        raise e