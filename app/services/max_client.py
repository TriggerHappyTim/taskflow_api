"""HTTP-клиент API мессенджера MAX (https://dev.max.ru/docs-api/).

Особенности платформы:
- Авторизация заголовком `Authorization: <access_token>` (без префикса Bearer).
- Базовый URL: https://platform-api2.max.ru
- POST /messages: получатель в query (chat_id или user_id), тело {text, format}.
- GET /updates: курсор следующей страницы возвращается в поле `marker`.
- Часть ошибок приходит с HTTP 200 и телом {"success": false, "code": ...}.
- Лимиты: до 30 rps, не более 2 сообщений в секунду в один чат.
"""
import asyncio
import logging
import time
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("taskflow.max")

MAX_TEXT_LIMIT = 4000          # символов в одном сообщении
MIN_SEND_INTERVAL = 0.5        # 2 сообщения/сек в один чат


class MaxAPIError(Exception):
    """Ошибка MAX API. .code — машинночитаемый код ошибки платформы."""

    def __init__(self, message: str, code: Any | None = None,
                 http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.message = message


class MaxClient:
    """Тонкая обёртка над REST API MAX на httpx."""

    def __init__(self, token: str | None = None, base_url: str | None = None):
        self.token = token if token is not None else settings.MAX_BOT_TOKEN
        self.base_url = (base_url or settings.MAX_API_URL).rstrip("/")
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_sent: dict[str, float] = {}

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": self.token}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        if not self.configured:
            raise MaxAPIError("MAX_BOT_TOKEN не задан — добавьте его в .env")

        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.request(
                    method, url, headers=self._headers(),
                    params=params, json=json_body,
                )
            except httpx.HTTPError as exc:
                logger.error("MAX network error %s %s: %s", method, url, exc)
                raise MaxAPIError(f"Сетевая ошибка при запросе к MAX: {exc}") from exc

        try:
            data = resp.json()
        except ValueError:
            data = {}

        if isinstance(data, dict):
            # часть методов отдаёт HTTP 200 с success:false
            if data.get("success") is False:
                code = data.get("code")
                logger.warning("MAX API error: %s %s code=%s", method, url, code)
                raise MaxAPIError(f"MAX API вернул ошибку (code={code})",
                                  code=code, http_status=resp.status_code)
            if resp.status_code >= 400:
                code = data.get("code")
                raise MaxAPIError(f"MAX API HTTP {resp.status_code} (code={code})",
                                  code=code, http_status=resp.status_code)
            return data

        if resp.status_code >= 400:
            raise MaxAPIError(f"MAX API HTTP {resp.status_code}", http_status=resp.status_code)
        return {"raw": data}

    async def _throttle(self, key: str) -> None:
        """Не чаще двух сообщений в секунду в один чат."""
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            last = self._last_sent.get(key, 0.0)
            delay = MIN_SEND_INTERVAL - (time.monotonic() - last)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_sent[key] = time.monotonic()

    # ===== Методы API =====

    async def get_me(self) -> dict[str, Any]:
        """GET /me — проверка токена, данные бота."""
        return await self._request("GET", "/me")

    async def send_message(
        self,
        chat_id: int | str | None = None,
        text: str = "",
        *,
        user_id: int | str | None = None,
    ) -> dict[str, Any]:
        """POST /messages — отправка текста.

        Получатель передаётся в query: chat_id (чат/канал) либо user_id (диалог).
        Тело: {"text": ..., "format": "markdown"}.
        """
        if chat_id is None and user_id is None:
            raise MaxAPIError("Не указан получатель: нужен chat_id или user_id")

        params: dict[str, Any] = {}
        if chat_id is not None:
            params["chat_id"] = int(chat_id)
            throttle_key = f"chat:{chat_id}"
        else:
            params["user_id"] = int(user_id)
            throttle_key = f"user:{user_id}"

        body = {"text": (text or "")[:MAX_TEXT_LIMIT], "format": "markdown"}

        await self._throttle(throttle_key)
        return await self._request("POST", "/messages", params=params, json_body=body)

    async def get_updates(
        self,
        marker: str | None = None,
        timeout: int = 30,
        limit: int = 100,
        types: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """GET /updates — long polling (dev-режим).

        Возвращает (список событий, новый marker).
        marker — курсор из ответа платформы, НЕ id события.
        """
        timeout = max(0, min(90, int(timeout)))
        limit = max(1, min(1000, int(limit)))

        params: dict[str, Any] = {"timeout": timeout, "limit": limit}
        if marker:
            params["marker"] = marker
        if types:
            params["types"] = ",".join(types)

        data = await self._request("GET", "/updates", params=params, timeout=timeout + 15)
        updates = data.get("updates") or []
        new_marker = data.get("marker")
        return (
            [u for u in updates if isinstance(u, dict)],
            str(new_marker) if new_marker is not None else None,
        )

    async def subscribe_webhook(self, url: str) -> dict[str, Any]:
        """POST /subscriptions — регистрация HTTPS-вебхука."""
        return await self._request("POST", "/subscriptions", json_body={"url": url})

    async def list_subscriptions(self) -> dict[str, Any]:
        """GET /subscriptions — список зарегистрированных вебхуков."""
        return await self._request("GET", "/subscriptions")

    async def unsubscribe_webhook(self) -> dict[str, Any]:
        """DELETE /subscriptions — отписка от вебхука."""
        return await self._request("DELETE", "/subscriptions")


max_client = MaxClient()