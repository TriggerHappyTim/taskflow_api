"""Эмулятор событий MAX — проверка логики бота без токена и без сети.

Формирует события в РЕАЛЬНОМ формате платформы MAX и прогоняет их через
process_update(): разбор → messenger.handle_message → сервисы → та же БД, что у API.

Запуск:  python emulate_max_update.py
Пользователь demo/demo1234 создаётся автоматически, если его нет.
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
EXTERNAL_USER_ID = 900000000001
CHAT_ID = 777000000001


def make_message_update(text: str, seq: int = 1) -> dict:
    """Событие message_created в реальном формате MAX."""
    return {
        "update_type": "message_created",
        "timestamp": 1700000000000 + seq,
        "chat_id": CHAT_ID,
        "user": {
            "user_id": EXTERNAL_USER_ID,
            "first_name": "Тим",
            "username": "tim",
            "is_bot": False,
        },
        "message": {
            "body": {"mid": f"mid_{seq}", "seq": seq, "text": text}
        },
    }


def make_bot_started_update() -> dict:
    """Событие bot_started (пользователь нажал «Начать»)."""
    return {
        "update_type": "bot_started",
        "timestamp": 1700000000000,
        "chat_id": CHAT_ID,
        "user": {
            "user_id": EXTERNAL_USER_ID,
            "first_name": "Тим",
            "is_bot": False,
        },
        "payload": None,
    }


async def ensure_demo_user(db) -> None:
    existing = (
        await db.execute(select(User).where(User.username == DEMO_USERNAME))
    ).scalar_one_or_none()
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
            make_bot_started_update(),
            make_message_update("/login demo demo1234", seq=1),
            make_message_update("/task Позвонить в банк", seq=2),
            make_message_update("/task Купить продукты", seq=3),
            make_message_update("/tasks", seq=4),
        ]

        for update in scenario:
            label = update.get("update_type")
            if label == "message_created":
                label = update["message"]["body"]["text"]

            result = await process_update(db, update)
            print(f"\n>>> [{label}]")
            if result is None:
                print("<нет ответа>")
            else:
                reply, chat_id = result
                print(f"<<< [чат {chat_id}] {reply}")

        # отмечаем первую созданную задачу выполненной
        from app.services import tasks as tasks_service
        from app.services import links as links_service

        owner_id = await links_service.get_owner_id(db, "max", str(EXTERNAL_USER_ID))
        items = await tasks_service.list_tasks(db, owner_id=owner_id, limit=1, offset=0)
        if items:
            done_update = make_message_update(f"/done {items[0].id}", seq=5)
            reply, chat_id = await process_update(db, done_update)
            print(f"\n>>> [/done {items[0].id}]")
            print(f"<<< [чат {chat_id}] {reply}")

        print("\nСценарий пройден без токена и без сети.")
        print("Задачи видны в Swagger под пользователем demo.")


if __name__ == "__main__":
    asyncio.run(main())