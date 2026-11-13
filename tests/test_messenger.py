"""Тесты общего обработчика чат-команд (messenger.handle_message) и адаптера MAX.

handle_message принимает db-сессию напрямую — тесты вызывают его без HTTP,
как это делают боты-адаптеры (без JWT).
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services import messenger
from app.services import users as users_service
from app.services.max_handlers import extract_event, process_update


async def _make_user(db: AsyncSession, username: str = "chatuser") -> None:
    user, error = await users_service.register_user(
        db, username=username, email=f"{username}@example.com", password="secret123"
    )
    assert user is not None, error


async def test_unlinked_user_asked_to_login(session):
    reply = await messenger.handle_message(session, platform="max", external_user_id="111", text="/tasks")
    assert reply == messenger.NOT_LINKED_TEXT


async def test_help_command(session):
    reply = await messenger.handle_message(session, platform="max", external_user_id="111", text="/help")
    assert "/login" in reply and "/task" in reply


async def test_login_task_tasks_flow(session):
    """После /login → создание задачи видно в /tasks."""
    await _make_user(session)

    reply = await messenger.handle_message(session, platform="max", external_user_id="222",
                                           text="/login chatuser secret123")
    assert "Привет, chatuser" in reply

    reply = await messenger.handle_message(session, platform="max", external_user_id="222",
                                           text="/task Позвонить маме")
    assert "Создана задача #" in reply

    reply = await messenger.handle_message(session, platform="max", external_user_id="222", text="/tasks")
    assert "Позвонить маме" in reply


async def test_wrong_password_not_linked(session):
    await _make_user(session)
    reply = await messenger.handle_message(session, platform="max", external_user_id="333",
                                           text="/login chatuser wrongpass")
    assert reply == "Неверный логин или пароль."
    # привязки нет → остальные команды просят /login
    reply = await messenger.handle_message(session, platform="max", external_user_id="333", text="/tasks")
    assert reply == messenger.NOT_LINKED_TEXT


async def test_link_survives_new_session(db_engine):
    """Привязка переживает перезапуск: новая сессия (и новый движок) видят её в БД."""
    maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        await _make_user(s, "persist")
        reply = await messenger.handle_message(s, platform="max", external_user_id="444",
                                               text="/login persist secret123")
        assert "привязан" in reply
        await messenger.handle_message(s, platform="max", external_user_id="444", text="/task Долгая задача")

    # «Перезапуск»: новый движок поверх того же файла БД (URL берём из фикстурного engine)
    url = str(db_engine.url)
    engine2 = create_async_engine(url)
    try:
        async with AsyncSession(engine2, expire_on_commit=False) as s2:
            reply = await messenger.handle_message(s2, platform="max", external_user_id="444", text="/tasks")
            assert "Долгая задача" in reply
    finally:
        await engine2.dispose()


async def test_logout_unlinks(session):
    await _make_user(session, "out")
    await messenger.handle_message(session, platform="max", external_user_id="555", text="/login out secret123")
    reply = await messenger.handle_message(session, platform="max", external_user_id="555", text="/logout")
    assert reply == "Аккаунт отвязан."
    reply = await messenger.handle_message(session, platform="max", external_user_id="555", text="/tasks")
    assert reply == messenger.NOT_LINKED_TEXT


# ===== Адаптер MAX: разбор Update =====

def test_extract_message_created():
    update = {
        "update_type": "message_created",
        "timestamp": 1700000000000,
        "chat_id": 777,
        "user": {"user_id": 900, "first_name": "Тим", "is_bot": False},
        "message": {"body": {"mid": "m1", "seq": 1, "text": "/tasks"}},
    }
    ev = extract_event(update)
    assert ev == {
        "platform": "max",
        "external_user_id": "900",
        "chat_id": 777,
        "text": "/tasks",
    }


def test_extract_bot_started_maps_to_start_command():
    update = {
        "update_type": "bot_started",
        "timestamp": 1700000000000,
        "chat_id": 777,
        "user": {"user_id": 900, "first_name": "Тим", "is_bot": False},
    }
    ev = extract_event(update)
    assert ev is not None and ev["text"] == "/start"


def test_extract_ignores_unknown_events():
    assert extract_event({"update_id": 3, "message_callback": {"payload": "x"}}) is None
    assert extract_event("не словарь") is None


async def test_process_update_end_to_end(session):
    """Реальный Update MAX → общий обработчик → задача в той же БД."""
    await _make_user(session, "maxuser")

    def upd(text: str, seq: int) -> dict:
        return {
            "update_type": "message_created",
            "timestamp": 1700000000000 + seq,
            "chat_id": 1000,
            "user": {"user_id": 888, "first_name": "Тим", "is_bot": False},
            "message": {"body": {"mid": f"m{seq}", "seq": seq, "text": text}},
        }

    result = await process_update(session, upd("/login maxuser secret123", 1))
    assert result is not None
    reply, chat_id = result
    assert chat_id == 1000
    assert "привязан" in reply.lower()

    reply, _ = await process_update(session, upd("/task Купить молоко", 2))
    assert "Создана задача" in reply

    reply, _ = await process_update(session, upd("/tasks", 3))
    assert "Купить молоко" in reply
