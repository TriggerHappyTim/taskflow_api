"""MAX-бот: long polling для локальной разработки.

Запуск: python run_max_polling.py
Токен берётся из .env (MAX_BOT_TOKEN).

ВАЖНО: MAX одновременно позволяет только один тип уведомлений —
либо вебхук, либо polling. Если вебхук зарегистрирован, сначала отпишитесь.
Без токена логику можно проверить через: python emulate_max_update.py
"""
import asyncio
import logging

from app.services.max_client import MaxAPIError, max_client
from app.services.max_handlers import handle_update_with_reply

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("max_polling")


async def main() -> None:
    if not max_client.configured:
        print(
            "MAX_BOT_TOKEN не задан.\n"
            "Получите токен на платформе MAX для партнёров (dev.max.ru),\n"
            "положите его в .env (см. .env.example) и перезапустите.\n"
            "Без токена: python emulate_max_update.py"
        )
        return

    me = await max_client.get_me()
    logger.info("Подключились к MAX как: %s", me)

    marker = None
    while True:
        try:
            updates, new_marker = await max_client.get_updates(marker=marker, timeout=30)
        except MaxAPIError as exc:
            logger.error("get_updates failed: %s (код=%s) — повтор через 5с", exc, exc.code)
            await asyncio.sleep(5)
            continue

        for update in updates:
            logger.info("Событие: %s", update.get("update_type"))
            try:
                await handle_update_with_reply(update)
            except Exception:  # noqa: BLE001
                logger.exception("Ошибка обработки события")

        # курсор двигает платформа, а не мы
        if new_marker:
            marker = new_marker


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Остановлено.")