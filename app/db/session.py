from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Путь к файлу базы данных (создастся автоматически)
DATABASE_URL = "sqlite+aiosqlite:///./taskflow.db"

# Создаём "движок" — он управляет соединениями с БД
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Поставь True, чтобы видеть SQL-запросы в консоли (для отладки)
)

# Фабрика сессий — через неё будем делать запросы
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Зависимость FastAPI: даёт сессию БД каждому запросу
async def get_db():
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