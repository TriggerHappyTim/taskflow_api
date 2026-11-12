"""Эмулятор событий MAX — проверка логики бота без токена и без сети.

Формирует фейковые Update (bot_started, message_created) в формате платформы
MAX и прогоняет их через app.services.max_handlers.process_update():
разбор события → messenger.handle_message → сервисы → та же БД, что у API.

Запуск:  python emulate_max_update.py
Сценарий: /login → /task → /tasks (с реальным пользователем из taskflow.db).

Если пользователя demo/demo1234 нет — он создаётся автоматически.
"""
import asyncio

from sqlalchemy import select

from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models.models import User
from app.services import users as users_service
from app.services.max_handlers import process_update

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo1234"
DEMO_EMAIL = "demo@example.com"
EXTERNAL_USER_ID = "900000000001"  # фейковый user_id в MAX


def make_message_update(text: str, update_id: int) -> dict:
    """Конструирует фейковое событие message_created в формате MAX API."""
    return {
        "update_id": update_id,
        "message_created": {
            "chat_id": 777000000001,
            "sender_user_id": int(EXTERNAL_USER_ID),
            "message": {"text": text},
        },
    }


async def ensure_demo_user(db) -> None:
    existing = (await db.execute(select(User).where(User.username == DEMO_USERNAME))).scalar_one_or_none()
    if existing is not None:
        print(f"Пользователь '{DEMO_USERNAME}' уже существует (id={existing.id}).")
        return
    user, error = await users_service.register_user(
        db, username=DEMO_USERNAME, email=DEMO_EMAIL, password=DEMO_PASSWORD
    )
    if user is None:
        raise RuntimeError(f"Не удалось создать демо-пользователя: {error}")
    print(f"Создан демо-пользователь '{DEMO_USERNAME}' (id={user.id}).")


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        await ensure_demo_user(db)

        scenario = [
            "/login demo demo1234",   # привязка аккаунта MAX → TaskFlow
            "/task Позвонить в банк", # создание задачи через MAX
            "/task Купить продукты",
            "/tasks",                 # список задач
            "/done 1",                # отметить выполненной (id может отличаться)
            "/tasks",
        ]

        for i, text in enumerate(scenario, start=1):
            update = make_message_update(text, update_id=i)
            result = await process_update(db, update)
            print(f"\n>>> {text}")
            if result is None:
                print("<нет ответа>")
            else:
                reply, chat_id = result
                print(f"<<< [чат {chat_id}] {reply}")

        print("\nСценарий пройден без токена и без сети.")
        print("Задачи, созданные здесь, видны в Swagger под тем же пользователем.")


if __name__ == "__main__":
    asyncio.run(main())
