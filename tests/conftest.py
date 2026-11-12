"""Общие фикстуры тестов.

Тестовая БД — временный файл SQLite (виден всем соединениям test-движка),
схема создаётся через Base.metadata.create_all. Зависимость get_db в
приложении переопределяется на тестовую сессию (dependency_overrides).
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture()
async def db_engine(tmp_path):
    """Свежий движок + схема для каждого теста (изоляция данных тестов)."""
    db_file = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def session(db_engine) -> AsyncSession:
    maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s


@pytest_asyncio.fixture()
async def client(db_engine):
    """HTTP-клиент поверх приложения (ASGITransport, без сетевого сервера)."""
    maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def register_and_login(client: AsyncClient, username: str = "alice",
                             password: str = "secret123", email: str = None):
    """Вспомогательная: регистрация + логин, возвращает (user_json, headers)."""
    email = email or f"{username}@example.com"
    r = await client.post("/auth/register",
                          json={"username": username, "email": email, "password": password})
    assert r.status_code == 201, r.text
    r = await client.post("/auth/login",
                          data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return r.json(), {"Authorization": f"Bearer {token}"}
