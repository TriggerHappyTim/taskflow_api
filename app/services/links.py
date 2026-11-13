"""Сервис привязки аккаунтов мессенджеров к пользователям TaskFlow.

Привязка хранится в таблице messenger_links и переживает перезапуск
приложения (в отличие от памяти процесса). Один внешний id может быть
привязан к одному пользователю на платформу.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import MessengerLink, User


async def get_owner_id(
    db: AsyncSession, platform: str, external_user_id: str
) -> int | None:
    """Кто этот пользователь мессенджера в TaskFlow? None — если не привязан."""
    result = await db.execute(
        select(MessengerLink).where(
            MessengerLink.platform == platform,
            MessengerLink.external_user_id == str(external_user_id),
        )
    )
    link = result.scalar_one_or_none()
    return link.user_id if link else None


async def link_account(
    db: AsyncSession,
    platform: str,
    external_user_id: str,
    user: User,
) -> MessengerLink:
    """Привязывает (или перепривязывает) аккаунт мессенджера к пользователю."""
    result = await db.execute(
        select(MessengerLink).where(
            MessengerLink.platform == platform,
            MessengerLink.external_user_id == str(external_user_id),
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        link = MessengerLink(
            platform=platform,
            external_user_id=str(external_user_id),
            user_id=user.id,
        )
        db.add(link)
    else:
        link.user_id = user.id
    await db.commit()
    await db.refresh(link)
    return link


async def unlink_account(db: AsyncSession, platform: str, external_user_id: str) -> bool:
    result = await db.execute(
        select(MessengerLink).where(
            MessengerLink.platform == platform,
            MessengerLink.external_user_id == str(external_user_id),
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        return False
    await db.delete(link)
    await db.commit()
    return True
