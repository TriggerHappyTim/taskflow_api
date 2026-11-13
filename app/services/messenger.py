"""Общий обработчик команд чат-бота (не зависит от мессенджера).

Платформенные адаптеры (Telegram, MAX) извлекают из своего Update:
  - platform ("telegram" / "max")
  - external_user_id (id пользователя в мессенджере)
  - chat_id (куда отправить ответ)
и вызывают handle_message(). Ответ возвращается текстом; адаптер сам
доставляет его (send_message). JWT не используется: owner_id берётся
из таблицы messenger_links.

Команды: /login <user> <pass>, /task <название>, /tasks, /done <id>,
/del <id>, /logout, /help.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import links as links_service
from app.services import tasks as tasks_service
from app.services import users as users_service

HELP_TEXT = (
    "TaskFlow бот. Команды:\n"
    "/login <логин> <пароль> — привязать аккаунт\n"
    "/task <название> — создать задачу\n"
    "/tasks [N] — список задач (страница N)\n"
    "/done <id> — отметить выполненной\n"
    "/del <id> — удалить задачу\n"
    "/logout — отвязать аккаунт\n"
    "/help — эта справка"
)

NOT_LINKED_TEXT = "Аккаунт не привязан. Сначала выполните /login <логин> <пароль>."

PAGE_SIZE = 10


def _format_task_line(task) -> str:
    mark = "✅" if task.is_completed else "⬜"
    return f"{mark} #{task.id} {task.title}"


async def handle_message(
    db: AsyncSession,
    platform: str,
    external_user_id: str,
    text: str,
) -> str:
    """Обрабатывает текст сообщения и возвращает строку-ответ."""
    text = (text or "").strip()
    if not text:
        return HELP_TEXT

    # Разбиваем: команда + аргументы
    parts = text.split(maxsplit=2)
    command = parts[0].lower()
    args = parts[1:]

    if command in ("/help", "/start"):
        return HELP_TEXT

    if command == "/login":
        if len(args) < 2:
            return "Формат: /login <логин> <пароль>"
        username, password = args[0], args[1]
        user = await users_service.authenticate_user(db, username, password)
        if user is None:
            return "Неверный логин или пароль."
        await links_service.link_account(db, platform, external_user_id, user)
        return f"Привет, {user.username}! Аккаунт привязан. Теперь доступны команды /task, /tasks, /done, /del."

    if command == "/logout":
        unlinked = await links_service.unlink_account(db, platform, external_user_id)
        return "Аккаунт отвязан." if unlinked else "Вы и не были привязаны."

    # Остальные команды требуют привязки
    owner_id: int | None = await links_service.get_owner_id(db, platform, external_user_id)
    if owner_id is None:
        return NOT_LINKED_TEXT

    if command == "/task":
        if not args:
            return "Формат: /task <название задачи>"
        title = " ".join(parts[1:]) if len(parts) > 1 else ""
        if not title:
            return "Название задачи не может быть пустым."
        task = await tasks_service.create_task(db, owner_id=owner_id, title=title)
        return f"Создана задача #{task.id}: {task.title}"

    if command == "/tasks":
        page = 0
        if args:
            try:
                page = max(0, int(args[0]) - 1)
            except ValueError:
                return "Страница должна быть числом. Формат: /tasks [N]"
        items = await tasks_service.list_tasks(
            db, owner_id=owner_id, limit=PAGE_SIZE, offset=page * PAGE_SIZE
        )
        if not items:
            return "Задач нет." if page == 0 else "На этой странице задач нет."
        lines = [_format_task_line(t) for t in items]
        return "\n".join(lines)

    if command in ("/done", "/del"):
        if not args:
            return f"Формат: {command} <id задачи>"
        try:
            task_id = int(args[0])
        except ValueError:
            return "ID задачи должен быть числом."
        if command == "/done":
            task = await tasks_service.complete_task(db, owner_id=owner_id, task_id=task_id)
            return f"Задача #{task.id} выполнена ✅" if task else f"Задача #{task_id} не найдена."
        deleted = await tasks_service.delete_task(db, owner_id=owner_id, task_id=task_id)
        return f"Задача #{task_id} удалена." if deleted else f"Задача #{task_id} не найдена."

    return f"Неизвестная команда: {command}. Напишите /help."
