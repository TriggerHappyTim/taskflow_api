"""Сервисный слой пользователей и авторизации."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User
from app.security.security import hash_password, verify_password


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def register_user(
    db: AsyncSession,
    username: str,
    email: str,
    password: str,
) -> tuple[User | None, str | None]:
    """Создаёт пользователя. Возвращает (user, error).

    error — текст ошибки, если пользователь/Email уже занят.
    """
    if await get_user_by_username(db, username) is not None:
        return None, "Пользователь с таким именем уже существует"
    if await get_user_by_email(db, email) is not None:
        return None, "Этот Email уже зарегистрирован"

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, None


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> User | None:
    user = await get_user_by_username(db, username)
    if user is None or not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
