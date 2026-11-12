"""Тесты CRUD задач: owner_id из токена, изоляция пользователей, пагинация, фильтр."""
from tests.conftest import register_and_login


async def test_tasks_require_token(client):
    """Доступ к /tasks/ без токена → 401."""
    r = await client.get("/tasks/")
    assert r.status_code == 401
    r = await client.post("/tasks/", json={"title": "x"})
    assert r.status_code == 401


async def test_create_task_owner_from_token_ignores_body(client):
    """owner_id берётся из токена; переданный в теле игнорируется."""
    _, headers_a = await register_and_login(client, "alice")
    _, _ = await register_and_login(client, "mallory", email="m@example.com")

    r = await client.post("/tasks/", json={"title": "Задача", "owner_id": 999}, headers=headers_a)
    assert r.status_code == 201
    task = r.json()
    # владелец — id alice (первый пользователь), а не 999 из тела
    me = await client.get("/auth/me", headers=headers_a)
    assert task["owner_id"] == me.json()["id"] != 999


async def test_isolation_user_cannot_touch_other_tasks(client):
    """Пользователь A не видит и не может изменить/удалить задачу B → 404."""
    _, headers_a = await register_and_login(client, "anna")
    _, headers_b = await register_and_login(client, "boris")

    r = await client.post("/tasks/", json={"title": "Задача Бориса"}, headers=headers_b)
    assert r.status_code == 201
    task_id = r.json()["id"]

    # Список A пуст
    r = await client.get("/tasks/", headers=headers_a)
    assert r.status_code == 200 and r.json() == []

    # Читать / менять / удалять чужую задачу нельзя — 404 (не отличима от несуществующей)
    assert (await client.get(f"/tasks/{task_id}", headers=headers_a)).status_code == 404
    assert (await client.patch(f"/tasks/{task_id}", json={"title": "хак"}, headers=headers_a)).status_code == 404
    assert (await client.delete(f"/tasks/{task_id}", headers=headers_a)).status_code == 404

    # А своя задача доступна владельцу
    assert (await client.get(f"/tasks/{task_id}", headers=headers_b)).status_code == 200


async def test_pagination_and_filter(client):
    _, headers = await register_and_login(client, "peter")
    for i in range(5):
        r = await client.post("/tasks/", json={"title": f"Задача {i}"}, headers=headers)
        assert r.status_code == 201
        if i % 2 == 0:  # 0,2,4 — выполненные
            tid = r.json()["id"]
            assert (await client.patch(f"/tasks/{tid}", json={"is_completed": True}, headers=headers)).status_code == 200

    # Пагинация: limit=2 offset=2 → задачи 3 и 4 (i=2,3)
    r = await client.get("/tasks/?limit=2&offset=2", headers=headers)
    assert r.status_code == 200
    titles = [t["title"] for t in r.json()]
    assert titles == ["Задача 2", "Задача 3"]

    # Фильтр is_completed=true → 3 задачи (i=0,2,4)
    r = await client.get("/tasks/?is_completed=true&limit=100", headers=headers)
    done = r.json()
    assert len(done) == 3 and all(t["is_completed"] for t in done)

    # Фильтр is_completed=false → 2 задачи
    r = await client.get("/tasks/?is_completed=false&limit=100", headers=headers)
    open_tasks = r.json()
    assert len(open_tasks) == 2 and not any(t["is_completed"] for t in open_tasks)


async def test_delete_own_task(client):
    _, headers = await register_and_login(client, "dora")
    r = await client.post("/tasks/", json={"title": "Временная"}, headers=headers)
    tid = r.json()["id"]
    assert (await client.delete(f"/tasks/{tid}", headers=headers)).status_code == 204
    assert (await client.get(f"/tasks/{tid}", headers=headers)).status_code == 404
