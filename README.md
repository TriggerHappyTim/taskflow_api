# TaskFlow API

[![CI](https://github.com/TriggerHappyTim/taskflow_api/actions/workflows/ci.yml/badge.svg)](https://github.com/TriggerHappyTim/taskflow_api/actions/workflows/ci.yml)

Бэкенд для управления задачами с JWT-авторизацией и интеграцией мессенджеров.
Один API обслуживает и HTTP-клиентов (веб/мобилка), и чат-бота в мессенджере MAX.

## Возможности

- Регистрация и вход по OAuth2 Password Flow, JWT-токены
- CRUD задач с пагинацией и фильтром по статусу
- **Изоляция данных**: пользователь видит и меняет только свои задачи
- Чат-бот MAX: создание и просмотр задач прямо из мессенджера
- Привязка аккаунта мессенджера к пользователю — бот помнит вас после перезапуска
- Асинхронная работа с БД (SQLAlchemy 2.0 async), миграции Alembic
- Запуск одной командой через Docker + PostgreSQL
- Автоматические тесты (pytest) и CI на GitHub Actions

## Стек

| Слой | Технология |
|------|-----------|
| API | FastAPI, Pydantic v2 |
| БД | SQLAlchemy 2.0 (async) + SQLite (dev) / PostgreSQL 16 (prod) |
| Миграции | Alembic |
| Авторизация | python-jose (JWT), passlib + bcrypt |
| Конфиг | pydantic-settings (.env) |
| HTTP-клиент | httpx |
| Инфраструктура | Docker, Docker Compose |
| Тесты | pytest, pytest-asyncio |
| CI | GitHub Actions |

## Архитектура

```mermaid
flowchart LR
    Web[Веб / мобильный клиент] -->|HTTP + JWT| R[Routers]
    MAX[Чат-бот MAX] -->|Webhook / Long polling| H[MAX Adapter]
    R --> S[Services]
    H --> S
    S --> DB[(База данных)]
```

**Принципы:**

- **Роутеры тонкие** — только HTTP-логика: валидация, статусы, зависимости. Никаких запросов к БД.
- **Сервисный слой** — вся бизнес-логика и работа с БД (`app/services`).
- **Боты — внутренние адаптеры.** Они вызывают сервисы напрямую, а `owner_id` берут из таблицы `messenger_links`. JWT им не нужен: токен не истекает каждые 30 минут, пользователь не вводит его вручную.
- **Общий обработчик команд** (`messenger.py`) не знает, из какого мессенджера пришло сообщение. Добавить новую платформу = написать один адаптер.

## Структура проекта

```
app/
  core/config.py          # настройки из .env
  db/                     # engine, сессии, Base
  models/models.py        # User, Task, MessengerLink
  schemas/schemas.py      # Pydantic-схемы
  security/security.py    # хеширование паролей, JWT
  routers/                # auth, tasks, max_bot
  services/               # users, tasks, links, messenger, max_client, max_handlers
alembic/                  # миграции
tests/                    # pytest
.github/workflows/ci.yml  # CI
Dockerfile
docker-compose.yml        # API + PostgreSQL
emulate_max_update.py     # эмулятор событий MAX (без токена и сети)
run_max_polling.py        # MAX long polling для разработки
check_db.py               # инспекция БД
```

## Быстрый старт через Docker (рекомендуется)

Требуется Docker Desktop (или Docker Engine + Compose).

```bash
git clone https://github.com/TriggerHappyTim/taskflow_api.git
cd taskflow_api

# 1. Настроить окружение
cp .env.example .env          # Windows: copy .env.example .env
# вписать SECRET_KEY в .env (генерация ниже)

# 2. Поднять стек
docker-compose up --build
```

Поднимется PostgreSQL 16 и API, миграции применятся автоматически.
Swagger: **http://127.0.0.1:8000/docs**

Полезные команды:

```bash
docker-compose up -d                                   # в фоне
docker-compose logs -f api                             # логи API
docker-compose down                                    # остановить (данные сохраняются)
docker-compose exec db psql -U taskflow -d taskflow    # консоль БД
docker-compose exec db psql -U taskflow -d taskflow -c "\dt"   # список таблиц
```

> Внутри compose база доступна по имени сервиса `db`, а не `localhost`.
> `DATABASE_URL` переопределяется в `docker-compose.yml`.

## Быстрый старт локально

Требуется Python 3.12+.

```bash
# 1. Клонировать и создать окружение
git clone https://github.com/TriggerHappyTim/taskflow_api.git
cd taskflow_api
python -m venv venv

# 2. Активировать
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
venv\Scripts\activate.bat
# macOS / Linux:
source venv/bin/activate

# 3. Установить зависимости
python -m pip install -r requirements-dev.txt

# 4. Настроить окружение
cp .env.example .env        # Windows: copy .env.example .env
# Сгенерировать SECRET_KEY и вписать в .env:
python -c "import secrets; print(secrets.token_hex(32))"

# 5. Применить миграции
python -m alembic upgrade head

# 6. Запустить
python -m uvicorn app.main:app --reload
```

Документация: **http://127.0.0.1:8000/docs** (Swagger UI) и `/redoc`.

> Локально используется SQLite (`taskflow.db`), в Docker — PostgreSQL.
> Это разные базы, данные между ними не синхронизируются.

## Переменные окружения

| Переменная | Назначение |
|-----------|-----------|
| `DATABASE_URL` | строка подключения к БД |
| `SECRET_KEY` | ключ подписи JWT (обязательно свой!) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | время жизни токена |
| `MAX_BOT_TOKEN` | токен бота MAX |
| `MAX_API_URL` | `https://platform-api2.max.ru` |
| `MAX_WEBHOOK_SECRET` | секрет для проверки входящих вебхуков |

Секреты хранятся только в `.env` (файл в `.gitignore`). Шаблон — `.env.example`.

## API

| Метод | Путь | Описание | Auth |
|-------|------|----------|------|
| POST | `/auth/register` | регистрация | — |
| POST | `/auth/login` | вход, выдача JWT (form-data) | — |
| GET | `/auth/me` | текущий пользователь | JWT |
| POST | `/tasks/` | создать задачу | JWT |
| GET | `/tasks/` | список своих задач (пагинация, фильтр) | JWT |
| GET | `/tasks/{id}` | получить задачу | JWT |
| PATCH | `/tasks/{id}` | обновить задачу | JWT |
| DELETE | `/tasks/{id}` | удалить задачу | JWT |
| POST | `/webhooks/max` | приём событий от MAX | secret |
| GET | `/health` | проверка работоспособности | — |

`owner_id` не передаётся клиентом — он определяется из JWT. Попытка обратиться к чужой задаче возвращает `404`.

## Чат-бот MAX

Команды бота:

```
/login <логин> <пароль>   — привязать аккаунт TaskFlow
/task <название>          — создать задачу
/tasks [N]                — список задач (страница N)
/done <id>                — отметить выполненной
/del <id>                 — удалить задачу
/logout                   — отвязать аккаунт
/help                     — справка
```

### Проверка без токена и без интернета

```bash
python emulate_max_update.py
```

Скрипт генерирует события в реальном формате платформы MAX и прогоняет их через
адаптер → общий обработчик → сервисы → ту же БД, что

### Линтер

```bash
python -m ruff check .        # проверка
python -m ruff check . --fix  # автоисправление безопасных замечаний
```

Конфигурация — в `pyproject.toml`. Правило B008 отключено для `Depends`/`Query`:
это стандартный механизм внедрения зависимостей FastAPI.