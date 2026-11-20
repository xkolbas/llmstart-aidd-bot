"""Telegram-обработчики."""

import asyncio
import logging
import re
from collections.abc import Iterator
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.dialogue_service import DialogueService
from bot.per_user_middleware import PerUserMiddleware
from bot.photo_buffer import MAX_PHOTO_BYTES, LimitedPhotoBuffer

logger = logging.getLogger(__name__)

ERROR_MESSAGE = "Не удалось получить ответ. Попробуйте ещё раз"
UNKNOWN_COMMAND_MESSAGE = "Неизвестная команда. Доступные команды: /start и /clear."
UNSUPPORTED_MESSAGE = "Я поддерживаю текст и одиночные фотографии еды или холодильника."
PHOTO_ALBUM_MESSAGE = "Отправьте одну фотографию отдельным сообщением, без альбома."
PHOTO_FORMAT_MESSAGE = (
    "Не удалось принять фото. Отправьте меньший снимок (до 5 MiB) "
    "обычной фотографией в JPEG, PNG или WebP либо опишите продукты текстом."
)
PHOTO_DOCUMENT_MESSAGE = (
    "Отправьте изображение как обычную фотографию, а не как файл. "
    "Также можно описать продукты текстом."
)
PHOTO_DOWNLOAD_TIMEOUT_SECONDS = 30.0
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
        "Можно отправить одну фотографию еды или холодильника с подписью или без неё. "
        "Альбомы не поддерживаются; оценка по фото приблизительная.\n"
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


def photo_mime_type(image: bytes) -> str:
    if image.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image.startswith(b"RIFF") and image[8:12] == b"WEBP":
        return "image/webp"
    raise ValueError("Неподдерживаемый формат фотографии")


@router.message(F.chat.type == "private", F.from_user, F.photo)
async def answer_photo(message: Message, bot: Bot, dialogue_service: DialogueService) -> None:
    if message.media_group_id:
        await send_text(message, PHOTO_ALBUM_MESSAGE)
        return

    photos = [
        photo
        for photo in message.photo
        if photo.file_size is None or photo.file_size <= MAX_PHOTO_BYTES
    ]
    if not photos:
        await send_text(message, PHOTO_FORMAT_MESSAGE)
        return
    photo = max(photos, key=lambda item: item.width * item.height)

    try:
        with LimitedPhotoBuffer() as buffer:
            async with asyncio.timeout(PHOTO_DOWNLOAD_TIMEOUT_SECONDS):
                await bot.download(photo, destination=buffer, timeout=30)
            image = buffer.getvalue()
        mime_type = photo_mime_type(image)
    except ValueError as error:
        logger.error("Ошибка формата или размера фото: %s", type(error).__name__)
        await send_text(message, PHOTO_FORMAT_MESSAGE)
        return
    except Exception as error:
        logger.error("Ошибка скачивания фото: %s", type(error).__name__)
        await send_text(message, ERROR_MESSAGE)
        return

    try:
        reply = await dialogue_service.reply_photo(
            message.from_user.id, image, mime_type, message.caption
        )
    except Exception as error:
        logger.error("Ошибка анализа фото: %s", type(error).__name__)
        await send_text(message, ERROR_MESSAGE)
        return

    if not reply.strip():
        logger.error("Анализ фото вернул пустой ответ")
        await send_text(message, ERROR_MESSAGE)
        return

    await send_text(message, reply, format_reply=True)


@router.message(F.chat.type == "private", F.from_user, F.text.startswith("/"))
async def unknown_command(message: Message) -> None:
    await send_text(message, UNKNOWN_COMMAND_MESSAGE)


@router.message(F.chat.type == "private", F.from_user, ~F.text)
async def unsupported_message(message: Message) -> None:
    if message.document and (message.document.mime_type or "").startswith("image/"):
        await send_text(message, PHOTO_DOCUMENT_MESSAGE)
        return
    await send_text(message, UNSUPPORTED_MESSAGE)
