"""Telegram-обработчики."""

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.dialogue_service import DialogueService
from bot.per_user_middleware import PerUserMiddleware

logger = logging.getLogger(__name__)

ERROR_MESSAGE = "Не удалось получить ответ. Попробуйте ещё раз"
UNKNOWN_COMMAND_MESSAGE = "Неизвестная команда. Доступные команды: /start и /clear."
UNSUPPORTED_MESSAGE = "Я поддерживаю только текстовые сообщения."
TELEGRAM_MESSAGE_LIMIT = 4096

router = Router()
router.message.outer_middleware(PerUserMiddleware())


async def send_text(message: Message, text: str) -> None:
    for offset in range(0, len(text), TELEGRAM_MESSAGE_LIMIT):
        try:
            await message.answer(text[offset : offset + TELEGRAM_MESSAGE_LIMIT])
        except Exception as error:
            logger.error(
                "Не удалось отправить сообщение в Telegram: %s",
                type(error).__name__,
            )
            return


@router.message(CommandStart(), F.chat.type == "private")
async def start(message: Message) -> None:
    await send_text(
        message,
        "Привет! Я бот-ассистент.\n"
        "Отправь текстовый вопрос, и я отвечу. "
        "Я учитываю историю нашего диалога.\n"
        "/clear — начать новый диалог.",
    )


@router.message(Command("clear"), F.chat.type == "private", F.from_user)
async def clear(message: Message, dialogue_service: DialogueService) -> None:
    dialogue_service.clear(message.from_user.id)
    await send_text(message, "История очищена. Начинаем новый диалог.")


@router.message(F.chat.type == "private", F.from_user, F.text, ~F.text.startswith("/"))
async def answer(message: Message, dialogue_service: DialogueService) -> None:
    try:
        reply = await dialogue_service.reply(message.from_user.id, message.text)
    except Exception as error:
        logger.error("Ошибка запроса к LLM: %s", type(error).__name__)
        await send_text(message, ERROR_MESSAGE)
        return

    if not reply.strip():
        logger.error("LLM вернула пустой ответ")
        await send_text(message, ERROR_MESSAGE)
        return

    await send_text(message, reply)


@router.message(F.chat.type == "private", F.from_user, F.text.startswith("/"))
async def unknown_command(message: Message) -> None:
    await send_text(message, UNKNOWN_COMMAND_MESSAGE)


@router.message(F.chat.type == "private", F.from_user, ~F.text)
async def unsupported_message(message: Message) -> None:
    await send_text(message, UNSUPPORTED_MESSAGE)
