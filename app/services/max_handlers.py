"""Адаптер MAX: разбор Update → общий обработчик messenger.handle_message.

MAX присылает события (message_created, bot_started и т.д.) в формате:
  {"update_id": ..., "message_created": {"message": {...}, "sender_user_id": ..., "chat_id": ...}}
Здесь вытаскиваем platform/external_user_id/chat_id/text и вызываем сервисы
через messenger.handle_message — та же логика, что у Telegram-адаптера.
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

    Возвращает None для событий без текста (message_callback, bot_removed и т.п.).
    """
    if not isinstance(update, dict):
        return None

    # message_created — основное текстовое событие
    mc = update.get("message_created")
    if isinstance(mc, dict):
        message = mc.get("message") or {}
        text = message.get("text") or ""
        sender_id = mc.get("sender_user_id") or message.get("sender_user_id") or (mc.get("user") or {}).get("user_id")
        chat_id = mc.get("chat_id") or message.get("chat_id")
        if sender_id is None or chat_id is None:
            logger.warning("MAX update без sender/chat: %s", update)
            return None
        return {
            "platform": PLATFORM,
            "external_user_id": str(sender_id),
            "chat_id": chat_id,
            "text": text.strip(),
        }

    # bot_started / bot_added — приветствие
    for key in ("bot_started", "bot_added"):
        ev = update.get(key)
        if isinstance(ev, dict):
            user = ev.get("user") or {}
            ctx = ev.get("chat_context") or {}
            sender_id = user.get("user_id") or ev.get("user_id")
            chat_id = ctx.get("chat_id") or ev.get("chat_id")
            if sender_id is None:
                return None
            return {
                "platform": PLATFORM,
                "external_user_id": str(sender_id),
                "chat_id": chat_id if chat_id is not None else sender_id,
                "text": "/start",
            }

    return None


async def process_update(db: AsyncSession, update: dict[str, Any]) -> Optional[tuple[str, Any]]:
    """Обрабатывает один Update и возвращает (текст ответа, chat_id) или None.

    Используется эмулятором и тестами; вебхук/polling вызывают
    handle_update_with_reply(), который дополнительно отправляет ответ в MAX.
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
    """Полный цикл: Update → ответ → отправка через MAX API.

    Используется и вебхуком (в background task), и polling-раннером.
    """
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
            logger.exception("Ошибка обработки MAX update %s", update.get("update_id"))
            return

    if event.get("chat_id") is None:
        return
    try:
        await max_client.send_message(event["chat_id"], reply)
    except MaxAPIError as exc:
        logger.error("Не удалось отправить ответ в MAX: %s", exc)
