
from pydantic import BaseModel, ConfigDict, field_validator


# ===== Схемы для User =====
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

    @field_validator("username")
    @classmethod
    def username_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("username не может быть пустым")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 4:
            raise ValueError("пароль должен быть не короче 4 символов")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    # Позволяет Pydantic брать данные из SQLAlchemy-объекта
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ===== Схемы для Task =====
class TaskCreate(BaseModel):
    """owner_id НЕ принимается от клиента — владелец берётся из токена."""
    title: str
    description: str | None = None


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