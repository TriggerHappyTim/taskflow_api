# Базовый образ: официальный Python 3.12 на минимальном Debian.
# 3.12, а не 3.14 — стабильнее и все библиотеки имеют готовые сборки.
FROM python:3.12-slim

# PYTHONDONTWRITEBYTECODE — не создавать .pyc
# PYTHONUNBUFFERED — логи сразу в консоль, без буферизации
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Компилятор нужен, если какая-то библиотека собирается из исходников
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Сначала только зависимости — этот слой кэшируется.
# Пока requirements.txt не меняется, сборка занимает секунды.
COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

# Теперь код
COPY . .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]