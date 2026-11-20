"""Telegram-обработчики."""

import logging
import re
from collections.abc import Iterator
from html import escape

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.dialogue_service import DialogueService
from bot.per_user_middleware import PerUserMiddleware

logger = logging.getLogger(__name__)

ERROR_MESSAGE = "Не удалось получить ответ. Попробуйте ещё раз"
UNKNOWN_COMMAND_MESSAGE = "Неизвестная команда. Доступные команды: /start и /clear."
UNSUPPORTED_MESSAGE = "Я поддерживаю только текстовые сообщения."
TELEGRAM_MESSAGE_LIMIT = 4096
BOLD_MARKUP = re.compile(r"(?<!\*)\*\*(?=\S)([^*\r\n]+?)(?<=\S)\*\*(?!\*)")

router = Router()
router.message.outer_middleware(PerUserMiddleware())


def reply_html_chunks(text: str) -> Iterator[str]:
    parts: list[str] = []
    remaining = TELEGRAM_MESSAGE_LIMIT
    for index, fragment in enumerate(BOLD_MARKUP.split(text)):
        bold = index % 2 == 1
        while fragment:
            segment, fragment = fragment[:remaining], fragment[remaining:]
            safe_text = escape(segment, quote=False)
            parts.append(f"<b>{safe_text}</b>" if bold else safe_text)
            remaining -= len(segment)
            if remaining == 0:
                yield "".join(parts)
                parts.clear()
                remaining = TELEGRAM_MESSAGE_LIMIT
    if parts:
        yield "".join(parts)


async def send_text(message: Message, text: str, *, format_reply: bool = False) -> None:
    chunks = (
        reply_html_chunks(text)
        if format_reply
        else (
            text[i : i + TELEGRAM_MESSAGE_LIMIT]
            for i in range(0, len(text), TELEGRAM_MESSAGE_LIMIT)
        )
    )
    for chunk in chunks:
        try:
            if format_reply:
                await message.answer(chunk, parse_mode=ParseMode.HTML)
            else:
                await message.answer(chunk)
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
        "Привет! Я бот-нутрициолог.\n"
        "Помогу разобрать рацион с учётом твоей цели и подобрать блюдо из продуктов дома.\n"
        "Например, напиши «Оцени мой рацион за день» или "
        "«Что приготовить из гречки, яиц и овощей?».\n"
        "Отправь список продуктов с количеством в граммах, миллилитрах или порциях — "
        "я оценю калорийность каждого продукта и общий итог. Расчёты ориентировочные.\n"
        "Учитываю историю диалога. Если данных не хватит, попрошу уточнение.\n"
        "/clear — начать новый диалог.",
    )


@router.message(Command("clear"), F.chat.type == "private", F.from_user)
async def clear(message: Message, dialogue_service: DialogueService) -> None:
    try:
        await dialogue_service.clear(message.from_user.id)
    except Exception as error:
        logger.error("Ошибка очистки истории: %s", type(error).__name__)
        await send_text(message, "Не удалось очистить историю. Попробуйте ещё раз")
        return
    await send_text(message, "История очищена. Начинаем новый диалог.")


@router.message(F.chat.type == "private", F.from_user, F.text, ~F.text.startswith("/"))
async def answer(message: Message, dialogue_service: DialogueService) -> None:
    try:
        reply = await dialogue_service.reply(message.from_user.id, message.text)
    except Exception as error:
        logger.error("Ошибка обработки диалога: %s", type(error).__name__)
        await send_text(message, ERROR_MESSAGE)
        return

    if not reply.strip():
        logger.error("LLM вернула пустой ответ")
        await send_text(message, ERROR_MESSAGE)
        return

    await send_text(message, reply, format_reply=True)


@router.message(F.chat.type == "private", F.from_user, F.text.startswith("/"))
async def unknown_command(message: Message) -> None:
    await send_text(message, UNKNOWN_COMMAND_MESSAGE)


@router.message(F.chat.type == "private", F.from_user, ~F.text)
async def unsupported_message(message: Message) -> None:
    await send_text(message, UNSUPPORTED_MESSAGE)
