# 1. Базовий образ: Використовуємо образ, який вже має Python та Debian Linux
FROM python:3.11-slim

# Встановлюємо робочу директорію
WORKDIR /app

# 2. Встановлення СИСТЕМНИХ залежностей для WeasyPrint (Критично!)
# Ці бібліотеки необхідні для рендерингу графіки та шрифтів.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    pkg-config && \
    rm -rf /var/lib/apt/lists/*

# 3. Копіювання файлу залежностей Python
COPY requirements.txt .

# 4. Встановлення Python-залежностей
RUN pip install --no-cache-dir -r requirements.txt

# 5. Копіювання коду застосунку
COPY . /app

# 6. Порт
EXPOSE 8000

# 7. Команда запуску (Entrypoint)
# Запускаємо Uvicorn для хостингу FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]