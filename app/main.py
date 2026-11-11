from fastapi import FastAPI
from app.routers import tasks

app = FastAPI(
    title="TaskFlow API",
    description="API для управления задачами",
    version="1.0.0",
)

# Подключаем роутер задач
app.include_router(tasks.router)


@app.get("/")
async def root():
    return {"message": "Добро пожаловать в TaskFlow API!"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


