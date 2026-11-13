"""HTTP-слой задач. Только разбор запроса и вызов сервисов — без работы с БД.

Владелец всегда берётся из токена (get_current_user), изоляция данных
обеспечивает сервисный слой: чужая задача = 404.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.schemas import TaskCreate, TaskResponse, TaskUpdate
from app.security.security import get_current_user
from app.services import tasks as tasks_service

router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ===== СОЗДАНИЕ задачи =====
@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await tasks_service.create_task(
        db, owner_id=current_user.id, title=task_data.title, description=task_data.description
    )


# ===== СПИСОК задач (пагинация + фильтр) =====
@router.get("/", response_model=list[TaskResponse])
async def get_tasks(
    is_completed: bool | None = Query(None, description="Фильтр по статусу"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await tasks_service.list_tasks(
        db, owner_id=current_user.id, is_completed=is_completed, limit=limit, offset=offset
    )


# ===== ОДНА задача =====
@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    task = await tasks_service.get_task(db, owner_id=current_user.id, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ===== ОБНОВЛЕНИЕ =====
@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = task_data.model_dump(exclude_unset=True)
    task = await tasks_service.update_task(
        db,
        owner_id=current_user.id,
        task_id=task_id,
        title=data.get("title"),
        description=data.get("description"),
        is_completed=data.get("is_completed"),
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ===== УДАЛЕНИЕ =====
@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    deleted = await tasks_service.delete_task(db, owner_id=current_user.id, task_id=task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
