"""MAX-бот: long polling для локальной разработки.

Запуск: python run_max_polling.py
Токен берётся из .env (MAX_BOT_TOKEN). ВАЖНО: MAX одновременно позволяет
только один тип уведомлений — либо вебхук, либо polling. Если зарегистрирован
вебхук, сначала отпишитесь: await max_client.unsubscribe_webhook().

Для теста без токена используйте emulate_max_update.py.
"""
import asyncio
import logging

from app.services.max_client import MaxAPIError, max_client
from app.services.max_handlers import handle_update_with_reply

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("max_polling")


async def main() -> None:
    if not max_client.configured:
        print(
            "MAX_BOT_TOKEN не задан.\n"
            "Получите токен бота на платформе MAX для партнёров (dev.max.ru),\n"
            "положите его в .env (см. .env.example) и перезапустите.\n"
            "Без токена можно проверить логику через: python emulate_max_update.py"
        )
        return

    me = await max_client.get_me()
    logger.info("Подключились к MAX как: %s", me.get("user", me))

    marker = None
    while True:
        try:
            updates = await max_client.get_updates(marker=marker, timeout=30)
        except MaxAPIError as exc:
            logger.error("get_updates failed: %s (код=%s) — повтор через 5с", exc, exc.code)
            await asyncio.sleep(5)
            continue

        for update in updates:
            update_id = str(update.get("update_id"))
            logger.info("Событие %s: %s", update_id, list(k for k in update if k != "update_id"))
            try:
                await handle_update_with_reply(update)
            except Exception:  # noqa: BLE001
                logger.exception("Ошибка обработки update %s", update_id)
            marker = update_id  # продвигаем курсор даже при ошибке —避免 эхо-шторма


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Остановлено.")
