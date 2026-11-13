"""Сервисный слой задач.

Правило архитектуры: в роутерах нет db.execute/add/commit — вся работа с БД
сосредоточена здесь. Это позволяет ботам-адаптерам (Telegram/MAX) вызывать те
же операции напрямую, без HTTP и JWT.

Изоляция данных: каждая операция принимает owner_id и фильтрует по нему.
Чужая задача для сервиса неотличима от несуществующей (возвращается None).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Task


async def create_task(
    db: AsyncSession,
    owner_id: int,
    title: str,
    description: str | None = None,
) -> Task:
    task = Task(title=title, description=description, owner_id=owner_id)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def list_tasks(
    db: AsyncSession,
    owner_id: int,
    is_completed: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Task]:
    query = select(Task).where(Task.owner_id == owner_id)
    if is_completed is not None:
        query = query.where(Task.is_completed == is_completed)
    query = query.order_by(Task.id).offset(offset).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_task(db: AsyncSession, owner_id: int, task_id: int) -> Task | None:
    """Возвращает задачу, только если она принадлежит owner_id."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.owner_id == owner_id)
    )
    return result.scalar_one_or_none()


async def update_task(
    db: AsyncSession,
    owner_id: int,
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    is_completed: bool | None = None,
) -> Task | None:
    task = await get_task(db, owner_id, task_id)
    if task is None:
        return None
    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if is_completed is not None:
        task.is_completed = is_completed
    await db.commit()
    await db.refresh(task)
    return task


async def complete_task(db: AsyncSession, owner_id: int, task_id: int) -> Task | None:
    return await update_task(db, owner_id, task_id, is_completed=True)


async def delete_task(db: AsyncSession, owner_id: int, task_id: int) -> bool:
    task = await get_task(db, owner_id, task_id)
    if task is None:
        return False
    await db.delete(task)
    await db.commit()
    return True
