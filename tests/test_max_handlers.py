"""Тесты адаптера MAX: разбор реального формата событий и сквозная логика."""
from app.services import users as users_service
from app.services.max_handlers import extract_event, process_update

USER_ID = 900000000001
CHAT_ID = 777000000001


def make_message(text: str, user_id: int = USER_ID, is_bot: bool = False) -> dict:
    return {
        "update_type": "message_created",
        "timestamp": 1700000000000,
        "chat_id": CHAT_ID,
        "user": {"user_id": user_id, "first_name": "Тим", "is_bot": is_bot},
        "message": {"body": {"mid": "m1", "seq": 1, "text": text}},
    }


def make_bot_started(user_id: int = USER_ID) -> dict:
    return {
        "update_type": "bot_started",
        "timestamp": 1700000000000,
        "chat_id": CHAT_ID,
        "user": {"user_id": user_id, "first_name": "Тим", "is_bot": False},
    }


# ---------- Разбор формата ----------

def test_extract_message_created():
    event = extract_event(make_message("/task Купить молоко"))
    assert event is not None
    assert event["platform"] == "max"
    assert event["external_user_id"] == str(USER_ID)
    assert event["chat_id"] == CHAT_ID
    assert event["text"] == "/task Купить молоко"


def test_extract_ignores_bot_messages():
    assert extract_event(make_message("привет", is_bot=True)) is None


def test_extract_ignores_empty_text():
    assert extract_event(make_message("   ")) is None


def test_extract_bot_started():
    event = extract_event(make_bot_started())
    assert event is not None
    assert event["text"] == "/start"


def test_extract_unknown_type():
    assert extract_event({"update_type": "dialog_cleared"}) is None
    assert extract_event({}) is None
    assert extract_event("не словарь") is None


# ---------- Сквозная логика через БД ----------

async def test_process_update_requires_link(session):
    reply, chat_id = await process_update(session, make_message("/tasks"))
    assert "не привязан" in reply.lower()
    assert chat_id == CHAT_ID


async def test_login_and_create_task(session):
    user, error = await users_service.register_user(
        session, username="maxuser", email="max@example.com", password="secret123"
    )
    assert user is not None, error

    reply, _ = await process_update(session, make_message("/login maxuser secret123"))
    assert "привязан" in reply.lower()

    reply, _ = await process_update(session, make_message("/task Купить молоко"))
    assert "Создана задача" in reply

    reply, _ = await process_update(session, make_message("/tasks"))
    assert "Купить молоко" in reply


async def test_isolation_between_max_users(session):
    user, error = await users_service.register_user(
        session, username="owner1", email="o1@example.com", password="secret123"
    )
    assert user is not None, error

    await process_update(session, make_message("/login owner1 secret123", user_id=111))
    await process_update(session, make_message("/task Секретная задача", user_id=111))

    # другой пользователь MAX не видит чужие задачи
    reply, _ = await process_update(session, make_message("/tasks", user_id=222))
    assert "не привязан" in reply.lower()