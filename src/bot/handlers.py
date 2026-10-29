"""Telegram-обработчики."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.dialogue_service import DialogueService
from bot.per_user_middleware import PerUserMiddleware

router = Router()
router.message.outer_middleware(PerUserMiddleware())


@router.message(CommandStart(), F.chat.type == "private")
async def start(message: Message) -> None:
    await message.answer(
        "Привет! Я бот-ассистент.\n"
        "Отправь текстовый вопрос, и я отвечу. "
        "Я учитываю историю нашего диалога.\n"
        "/clear — начать новый диалог."
    )


@router.message(Command("clear"), F.chat.type == "private", F.from_user)
async def clear(message: Message, dialogue_service: DialogueService) -> None:
    dialogue_service.clear(message.from_user.id)
    await message.answer("История очищена. Начинаем новый диалог.")


@router.message(F.chat.type == "private", F.from_user, F.text, ~F.text.startswith("/"))
async def answer(message: Message, dialogue_service: DialogueService) -> None:
    reply = await dialogue_service.reply(message.from_user.id, message.text)
    await message.answer(reply)
