"""Вебхук MAX: POST /webhooks/max.

Требования из плана (M1):
- защищён секретом MAX_WEBHOOK_SECRET (сверка query-параметра secret);
- если токен пустой — не падать, отдавать 503;
- отвечать быстро ({"ok": true}), обработку выносить в background task.
"""
import logging
import secrets as secrets_module
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status

from app.core.config import settings
from app.services.max_client import max_client
from app.services.max_handlers import handle_update_with_reply

logger = logging.getLogger("taskflow.max")

router = APIRouter(prefix="/webhooks", tags=["MAX bot"])


@router.post("/max")
async def max_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    secret: str = Query("", description="Должен совпадать с MAX_WEBHOOK_SECRET из .env"),
):
    # 1. Без настроенного токена приём событий невозможен — но приложение не падает
    if not max_client.configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MAX_BOT_TOKEN не задан. Вебхук недоступен.",
        )

    # 2. Проверка секрета (постоянное сравнение — против timing-атак)
    expected = settings.MAX_WEBHOOK_SECRET
    if not expected or not secrets_module.compare_digest(secret, expected):
        logger.warning("MAX webhook: секрет не задан или не совпадает")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Неверный секрет вебхука")

    # 3. Быстрый ответ: обновление уходит в background task
    try:
        update: dict[str, Any] = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный JSON")

    if not isinstance(update, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ожидался объект Update")

    background_tasks.add_task(handle_update_with_reply, update)
    return {"ok": True}
