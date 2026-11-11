from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.models import Task, User
from app.schemas.schemas import TaskCreate, TaskUpdate, TaskResponse

router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ===== СОЗДАНИЕ задачи =====
@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(task_data: TaskCreate, db: AsyncSession = Depends(get_db)):
    # 1. Проверяем, что пользователь существует
    user = await db.get(User, task_data.owner_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Создаём объект задачи
    new_task = Task(
        title=task_data.title,
        description=task_data.description,
        owner_id=task_data.owner_id,
    )

    # 3. Сохраняем в БД
    db.add(new_task)
    await db.commit()        # Фиксируем изменения
    await db.refresh(new_task)  # Подгружаем id и другие поля из БД

    return new_task


# ===== ПОЛУЧИТЬ все задачи =====
@router.get("/", response_model=list[TaskResponse])
async def get_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task))
    return result.scalars().all()


# ===== ПОЛУЧИТЬ одну задачу по ID =====
@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ===== ОБНОВИТЬ задачу =====
@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task_data: TaskUpdate, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Обновляем только те поля, которые пришли
    update_data = task_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    await db.commit()
    await db.refresh(task)
    return task


# ===== УДАЛИТЬ задачу =====
@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await db.delete(task)
    await db.commit()
    return None


"""
Разбор ключевых моментов:
@router.post("/") — декоратор, который регистрирует endpoint.
Depends(get_db) — FastAPI сам вызовет get_db() и передаст сессию.
await db.commit() — без этого изменения не сохранятся!
HTTPException — правильный способ вернуть ошибку с нужным HTTP-кодом.
"""