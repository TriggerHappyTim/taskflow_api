from pydantic import BaseModel, EmailStr, ConfigDict


# ===== Схемы для User =====
class UserCreate(BaseModel):
    username: str
    email: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    # Позволяет Pydantic брать данные из SQLAlchemy-объекта
    model_config = ConfigDict(from_attributes=True)


# ===== Схемы для Task =====
class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    owner_id: int


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    is_completed: bool | None = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str | None
    is_completed: bool
    owner_id: int

    model_config = ConfigDict(from_attributes=True)


"""
Что тут важно:
TaskCreate — что клиент отправляет при создании.
TaskResponse — что мы возвращаем клиенту.
model_config = ConfigDict(from_attributes=True) — магия, которая позволяет вернуть SQLAlchemy-объект, а Pydantic сам превратит его в JSON.
"""