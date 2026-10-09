"""Telegram-обработчики."""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router()


@router.message(CommandStart(), F.chat.type == "private")
async def start(message: Message) -> None:
    await message.answer(
        "Привет! Я бот-ассистент.\n"
        "Сейчас доступна команда /start. "
        "Ответы на вопросы появятся на следующем этапе."
    )
