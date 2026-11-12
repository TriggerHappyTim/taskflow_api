"""HTTP-клиент API мессенджера MAX (https://dev.max.ru/docs-api/).

Особенности платформы (см. раздел 6 плана):
- Авторизация заголовком `Authorization: <access_token>` (query-параметры не поддерживаются).
- Базовый URL: https://platform-api2.max.ru (старый platform-api.max.ru устарел).
- Часть ошибок приходит с HTTP 200 и телом {"success": false, "code": ...} —
  поэтому проверяем и код, и тело; ориентироваться надо на code, не на message.
- Одновременно работает только один тип уведомлений: webhook ИЛИ long polling.
"""
import logging
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("taskflow.max")


class MaxAPIError(Exception):
    """Ошибка MAX API. .code — машинночитаемый код ошибки платформы."""

    def __init__(self, message: str, code: Optional[int] = None, http_status: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.message = message


class MaxClient:
    """Тонкая обёртка над REST API MAX на httpx."""

    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None):
        self.token = token if token is not None else settings.MAX_BOT_TOKEN
        self.base_url = (base_url or settings.MAX_API_URL).rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict[str, str]:
        # Только заголовок Authorization, без префикса Bearer (так требует MAX)
        return {"Authorization": self.token}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        if not self.configured:
            raise MaxAPIError("MAX_BOT_TOKEN не задан — добавьте его в .env")

        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.request(method, url, headers=self._headers(),
                                            params=params, json=json_body)
            except httpx.HTTPError as exc:
                logger.error("MAX network error %s %s: %s", method, url, exc)
                raise MaxAPIError(f"Сетевая ошибка при запросе к MAX: {exc}") from exc

        # Разбираем тело: часть методов отдаёт HTTP 200 с success:false и полем code
        try:
            data = resp.json()
        except ValueError:
            data = {}

        if isinstance(data, dict):
            if data.get("success") is False:
                code = data.get("code")
                logger.warning("MAX API error: %s %s code=%s", method, url, code)
                raise MaxAPIError(f"MAX API вернул ошибку (code={code})",
                                  code=code, http_status=resp.status_code)
            if resp.status_code >= 400:
                code = data.get("code") if isinstance(data, dict) else None
                raise MaxAPIError(f"MAX API HTTP {resp.status_code} (code={code})",
                                  code=code, http_status=resp.status_code)
            result = data.get("result", data)
            return result if isinstance(result, dict) else data
        if resp.status_code >= 400:
            raise MaxAPIError(f"MAX API HTTP {resp.status_code}", http_status=resp.status_code)
        return {"raw": data}

    # ===== Методы API =====
    async def get_me(self) -> dict[str, Any]:
        """GET /me — проверка токена, данные бота."""
        return await self._request("GET", "/me")

    async def send_message(self, chat_id: int | str, text: str) -> dict[str, Any]:
        """POST /messages — отправка текста в чат."""
        body = {
            "chat_id": int(chat_id),
            "text": text,
            "markdown": True,
        }
        return await self._request("POST", "/messages", json_body=body)

    async def get_updates(
        self,
        marker: Optional[str] = None,
        timeout: int = 30,
        limit: int = 100,
        types: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """GET /updates — long polling (dev-режим).

        marker — курсор (update_id последнего обработанного события),
        timeout 0..90 сек, limit 1..1000.
        """
        timeout = max(0, min(90, int(timeout)))
        limit = max(1, min(1000, int(limit)))
        params: dict[str, Any] = {"timeout": timeout, "limit": limit}
        if marker:
            params["marker"] = marker
        if types:
            params["types"] = ",".join(types)
        data = await self._request("GET", "/updates", params=params, timeout=timeout + 15)
        updates = data.get("updates", []) if isinstance(data, dict) else []
        return [u for u in updates if isinstance(u, dict)]

    async def subscribe_webhook(self, url: str) -> dict[str, Any]:
        """POST /subscriptions — регистрация HTTPS-вебхука."""
        return await self._request("POST", "/subscriptions", json_body={"url": url})

    async def list_subscriptions(self) -> dict[str, Any]:
        """GET /subscriptions — список зарегистрированных вебхуков."""
        return await self._request("GET", "/subscriptions")

    async def unsubscribe_webhook(self) -> dict[str, Any]:
        """DELETE /subscriptions — отписка от вебхука."""
        return await self._request("DELETE", "/subscriptions")


# Экземпляр по умолчанию для приложения (токен подтянется из settings)
max_client = MaxClient()
