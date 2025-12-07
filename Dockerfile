# 1. Build Stage
FROM python:3.11-slim

# Встановлення робочої директорії
WORKDIR /app

# 2. Встановлення системних залежностей (Критично для WeasyPrint)
# Ми встановлюємо Pango, Cairo та інші бібліотеки, яких немає в базовому Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# 3. Копіювання та встановлення Python-залежностей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Копіювання коду застосунку
COPY . .

# 5. Налаштування змінних оточення (щоб Python не буферизував вивід)
ENV PYTHONUNBUFFERED=1

# 6. Команда запуску
# Для MVP ми запускаємо run_bot.py (Polling Mode), щоб бот працював відразу
CMD ["python", "run_bot.py"]

