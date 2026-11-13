"""Адаптер MAX: разбор Update → общий обработчик messenger.handle_message.

Реальный формат события платформы MAX:
{
  "update_type": "message_created",
  "timestamp": 1573226679188,
  "chat_id": 1234567890,
  "user": {"user_id": 1234567890, "first_name": "Иван", "is_bot": false},
  "message": {"body": {"mid": "...", "seq": 1, "text": "/task Купить молоко"}}
}

Тип события лежит в поле update_type, текст — в message.body.text.
"""
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.services import messenger
from app.services.max_client import MaxAPIError, max_client

logger = logging.getLogger("taskflow.max")

PLATFORM = "max"


def extract_event(update: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Достаёт из Update поля, нужные общему обработчику.

    Возвращает None для событий, на которые отвечать не нужно.
    """
    if not isinstance(update, dict):
        return None

    update_type = update.get("update_type")

    # --- Текстовое сообщение ---
    if update_type == "message_created":
        message = update.get("message") or {}
        body = message.get("body") or {}
        text = (body.get("text") or "").strip()

        user = update.get("user") or message.get("sender") or {}
        sender_id = user.get("user_id")
        chat_id = update.get("chat_id") or (message.get("recipient") or {}).get("chat_id")

        if sender_id is None:
            logger.warning("MAX update без user_id: %s", update)
            return None
        if user.get("is_bot"):
            return None          # не отвечаем на собственные сообщения
        if not text:
            return None          # вложения без текста пока не обрабатываем

        return {
            "platform": PLATFORM,
            "external_user_id": str(sender_id),
            "chat_id": chat_id,
            "text": text,
        }

    # --- Пользователь запустил бота ---
    if update_type in ("bot_started", "bot_added"):
        user = update.get("user") or {}
        sender_id = user.get("user_id")
        if sender_id is None:
            return None
        return {
            "platform": PLATFORM,
            "external_user_id": str(sender_id),
            "chat_id": update.get("chat_id"),
            "text": "/start",
        }

    # Остальные типы (message_callback, bot_removed, dialog_cleared...) игнорируем
    return None


async def process_update(
    db: AsyncSession, update: dict[str, Any]
) -> Optional[tuple[str, Any]]:
    """Обрабатывает один Update и возвращает (текст ответа, chat_id) или None.

    Используется эмулятором и тестами — без обращения к сети.
    """
    event = extract_event(update)
    if event is None:
        return None
    reply = await messenger.handle_message(
        db,
        platform=event["platform"],
        external_user_id=event["external_user_id"],
        text=event["text"],
    )
    return reply, event["chat_id"]


async def handle_update_with_reply(update: dict[str, Any]) -> None:
    """Полный цикл: Update → ответ → отправка через MAX API."""
    event = extract_event(update)
    if event is None:
        return

    async with AsyncSessionLocal() as db:
        try:
            reply = await messenger.handle_message(
                db,
                platform=event["platform"],
                external_user_id=event["external_user_id"],
                text=event["text"],
            )
        except Exception:  # noqa: BLE001 — не роняем вебхук из-за ошибки логики
            logger.exception("Ошибка обработки MAX update: %s", update.get("update_type"))
            return

    try:
        if event.get("chat_id") is not None:
            await max_client.send_message(chat_id=event["chat_id"], text=reply)
        else:
            # диалог без chat_id — пишем пользователю напрямую
            await max_client.send_message(user_id=event["external_user_id"], text=reply)
    except MaxAPIError as exc:
        logger.error("Не удалось отправить ответ в MAX: %s", exc)