from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# URL берём из настроек (.env): SQLite локально, PostgreSQL в Docker
DATABASE_URL = settings.DATABASE_URL

# Создаём "движок" — он управляет соединениями с БД
engine = create_async_engine(settings.database_url, echo=False)

# Фабрика сессий — через неё будем делать запросы
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Зависимость FastAPI: даёт сессию БД каждому запросу
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

"""
Что тут происходит:
engine — это "менеджер подключений". Он не подключается сразу, а создаёт пул соединений по мере необходимости.
AsyncSessionLocal — фабрика, которая создаёт сессии. Одна сессия = одна "транзакция" (набор операций с БД).
get_db — это Dependency Injection (внедрение зависимости). FastAPI автоматически вызовет эту функцию перед каждым запросом и передаст сессию в роутер.
"""