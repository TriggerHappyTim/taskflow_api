from fastapi import FastAPI
from app.routers import tasks, auth, max_bot

app = FastAPI(
    title="TaskFlow API",
    description="API для управления задачами: JWT для внешних клиентов, "
                "адаптеры мессенджеров (Telegram/MAX) работают через сервисный слой.",
    version="1.0.0",
)

# HTTP-роуты
app.include_router(auth.router)
app.include_router(tasks.router)
# Внутренний адаптер MAX (вебхук POST /webhooks/max)
app.include_router(max_bot.router)


@app.get("/")
async def root():
    return {"message": "Добро пожаловать в TaskFlow API!"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}
