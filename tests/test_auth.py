"""Тесты авторизации: регистрация → логин → /auth/me, конфликты, неверный пароль."""


async def test_register_login_me_flow(client):
    """Сценарий из плана: регистрация → логин (OAuth2 form) → /auth/me."""
    r = await client.post("/auth/register", json={
        "username": "alice", "email": "alice@example.com", "password": "secret123",
    })
    assert r.status_code == 201
    user = r.json()
    assert user["username"] == "alice"
    assert "hashed_password" not in user  # хэш не должен утекать в API

    r = await client.post("/auth/login", data={"username": "alice", "password": "secret123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    token = body["access_token"]

    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"id": user["id"], "username": "alice", "email": "alice@example.com"}


async def test_register_duplicate_username(client):
    r = await client.post("/auth/register", json={
        "username": "bob", "email": "bob@example.com", "password": "secret123",
    })
    assert r.status_code == 201
    r = await client.post("/auth/register", json={
        "username": "bob", "email": "other@example.com", "password": "secret123",
    })
    assert r.status_code == 409


async def test_login_wrong_password(client):
    await client.post("/auth/register", json={
        "username": "carol", "email": "carol@example.com", "password": "secret123",
    })
    r = await client.post("/auth/login", data={"username": "carol", "password": "wrong-pass"})
    assert r.status_code == 401


async def test_me_without_token_returns_401(client):
    r = await client.get("/auth/me")
    assert r.status_code == 401


async def test_me_with_garbage_token_returns_401(client):
    r = await client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
