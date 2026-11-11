from sqlalchemy import String, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class User(Base):
    """Таблица пользователей"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="owner",
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

"""
Разбор важных моментов:
Mapped[int] — современный синтаксис SQLAlchemy 2.0. Указывает тип поля.
mapped_column(...) — настройки колонки (длина, уникальность и т.д.).
ForeignKey("users.id") — говорит БД, что это ссылка на таблицу users, поле id.
relationship — позволяет обращаться к связанным объектам как к атрибутам: task.owner.username.
"""