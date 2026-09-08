from aiogram.types import Message

from .config import config
from . import db


async def owner_inbox_cmd(message: Message):
    """Bind Inna's private Telegram chat as the only owner inbox.

    Telegram bots cannot create a private chat on their own, so Inna opens the
    bot once and runs /inbox. After that all booking/application notifications
    are routed to this private chat via owner_chat_id.
    """
    if message.chat.type != "private":
        await message.answer("🔐 Служебный inbox Инны настраивается только в личном чате с ботом.")
        return

    username = (message.from_user.username or "").lower()
    if username != config.owner_username:
        await message.answer("Команда доступна только Инне.")
        return

    await db.setting_set("owner_chat_id", str(message.chat.id))
    await message.answer(
        "🔐 <b>Служебный inbox Инны активирован</b>\n\n"
        "Сюда бот будет присылать новые записи, заявки, переносы, отмены, "
        "подтверждения и вопросы клиентов.\n\n"
        "Эти уведомления не публикуются в группе и не зависят от OpenRouter/AI."
    )
