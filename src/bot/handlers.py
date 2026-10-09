"""Telegram-обработчики."""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.dialogue_service import DialogueService

router = Router()


@router.message(CommandStart(), F.chat.type == "private")
async def start(message: Message) -> None:
    await message.answer(
        "Привет! Я бот-ассистент.\n"
        "Отправь текстовый вопрос, и я отвечу. "
        "Пока каждый вопрос обрабатывается отдельно, без истории диалога."
    )


@router.message(F.chat.type == "private", F.text, ~F.text.startswith("/"))
async def answer(message: Message, dialogue_service: DialogueService) -> None:
    reply = await dialogue_service.reply(message.text)
    await message.answer(reply)
