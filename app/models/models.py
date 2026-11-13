from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    """Таблица пользователей"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    # ВАЖНО: без `| None` и без Optional в Mapped — только nullable=True
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=True)

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    messenger_links: Mapped[list["MessengerLink"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"


class Task(Base):
    """Таблица задач"""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))

    # ВАЖНО: без `| None` и без Optional — только nullable=True
    description: Mapped[str] = mapped_column(Text, nullable=True)

    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    owner: Mapped["User"] = relationship(back_populates="tasks")

    def __repr__(self):
        return f"<Task(id={self.id}, title={self.title})>"


class MessengerLink(Base):
    """Привязка аккаунта мессенджера к пользователю TaskFlow.

    Боты (Telegram/MAX) — внутренние адаптеры: они определяют owner_id
    по (platform, external_user_id) и вызывают сервисы напрямую, без JWT.
    """
    __tablename__ = "messenger_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), index=True)   # telegram / max
    external_user_id: Mapped[str] = mapped_column(String(64), index=True)  # id пользователя в мессенджере
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="messenger_links")

    def __repr__(self):
        return (
            f"<MessengerLink(platform={self.platform!r}, "
            f"external_user_id={self.external_user_id!r}, user_id={self.user_id})>"
        )


"""
Разбор важных моментов:
Mapped[int] — современный синтаксис SQLAlchemy 2.0. Указывает тип поля.
mapped_column(...) — настройки колонки (длина, уникальность и т.д.).
ForeignKey("users.id") — говорит БД, что это ссылка на таблицу users, поле id.
relationship — позволяет обращаться к связанным объектам как к атрибутам: task.owner.username.
"""