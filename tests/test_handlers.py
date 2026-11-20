import asyncio
import logging
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, call, patch

import pytest
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.methods import SendMessage
from aiogram.types import Chat, Document, Message, PhotoSize, Update, User

from bot.dialogue_service import DialogueService
from bot.handlers import (
    ERROR_MESSAGE,
    PHOTO_ALBUM_MESSAGE,
    PHOTO_DOCUMENT_MESSAGE,
    PHOTO_FORMAT_MESSAGE,
    TELEGRAM_MESSAGE_LIMIT,
    answer,
    answer_photo,
    router,
)
from bot.photo_buffer import MAX_PHOTO_BYTES


def test_start_and_text_replies_are_sent_only_in_private_chat():
    async def check():
        session = AsyncMock()
        bot = Bot(token="123456:test-token", session=session)
        dispatcher = Dispatcher()
        dispatcher.include_router(router)
        dialogue_service = AsyncMock(spec=DialogueService)
        dialogue_service.reply.return_value = "• **Творог 5%**: сколько граммов?\n<100 г & более"

        for update_id, (chat_type, text) in enumerate(
            [
                ("private", "/start"),
                ("group", "/start"),
                ("private", "Привет"),
                ("group", "Привет"),
                ("private", "/unknown"),
                ("private", None),
                ("group", "/clear"),
                ("private", "/clear"),
            ],
            start=1,
        ):
            update = Update(
                update_id=update_id,
                message=Message(
                    message_id=update_id,
                    date=datetime.now(UTC),
                    chat=Chat(id=1, type=chat_type),
                    from_user=User(id=1, is_bot=False, first_name="Тест"),
                    text=text,
                ),
            )
            await dispatcher.feed_update(bot, update, dialogue_service=dialogue_service)

        assert session.await_count == 5
        method = session.await_args_list[0].args[1]
        assert isinstance(method, SendMessage)
        assert method.chat_id == 1
        assert method.text.startswith("Привет! Я бот-нутрициолог.")
        assert "Оцени мой рацион за день" in method.text
        assert "Что приготовить из гречки, яиц и овощей?" in method.text
        assert "с учётом твоей цели" in method.text
        assert "список продуктов с количеством" in method.text
        assert "Расчёты ориентировочные" in method.text
        assert "уточнение" in method.text
        assert "фотографию еды или холодильника" in method.text
        assert "Альбомы не поддерживаются" in method.text
        assert "/clear" in method.text
        reply = session.await_args_list[1].args[1]
        assert isinstance(reply, SendMessage)
        assert reply.chat_id == 1
        assert reply.text == "• <b>Творог 5%</b>: сколько граммов?\n&lt;100 г &amp; более"
        assert reply.parse_mode == ParseMode.HTML
        dialogue_service.reply.assert_awaited_once_with(1, "Привет")
        dialogue_service.clear.assert_called_once_with(1)
        assert session.await_args_list[2].args[1].text.startswith("Неизвестная команда")
        assert session.await_args_list[3].args[1].text == (
            "Я поддерживаю текст и одиночные фотографии еды или холодильника."
        )
        assert session.await_args_list[4].args[1].text.startswith("История очищена")

        photo = PhotoSize(file_id="photo", file_unique_id="unique", width=100, height=100)
        dialogue_service.reply_photo.return_value = "Вижу **овощи**. Какая цель?"

        async def download(file, destination, **kwargs):
            destination.write(b"\xff\xd8\xffphoto")

        with patch.object(bot, "download", new=AsyncMock(side_effect=download)) as download_mock:
            for update_id, fields in enumerate(
                [
                    {"chat_type": "private", "photo": [photo], "caption": "Холодильник"},
                    {"chat_type": "group", "photo": [photo]},
                    {"chat_type": "private", "photo": [photo], "media_group_id": "album"},
                    {
                        "chat_type": "private",
                        "document": Document(
                            file_id="document", file_unique_id="document", mime_type="image/png"
                        ),
                    },
                ],
                start=20,
            ):
                chat_type = fields.pop("chat_type")
                update = Update(
                    update_id=update_id,
                    message=Message(
                        message_id=update_id,
                        date=datetime.now(UTC),
                        chat=Chat(id=1, type=chat_type),
                        from_user=User(id=1, is_bot=False, first_name="Тест"),
                        **fields,
                    ),
                )
                await dispatcher.feed_update(bot, update, dialogue_service=dialogue_service)
        download_mock.assert_awaited_once()
        dialogue_service.reply_photo.assert_awaited_once_with(
            1, b"\xff\xd8\xffphoto", "image/jpeg", "Холодильник"
        )
        assert session.await_count == 8
        assert session.await_args_list[5].args[1].text == "Вижу <b>овощи</b>. Какая цель?"
        assert session.await_args_list[6].args[1].text == PHOTO_ALBUM_MESSAGE
        assert session.await_args_list[7].args[1].text == PHOTO_DOCUMENT_MESSAGE

    asyncio.run(check())


def test_long_reply_is_sent_completely_and_in_order():
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        text="Вопрос",
        answer=AsyncMock(),
    )
    dialogue_service = AsyncMock(spec=DialogueService)
    prefix = "а" * (TELEGRAM_MESSAGE_LIMIT - 2)
    reply = prefix + "**бвгд** и **незакрытый фрагмент"
    dialogue_service.reply.return_value = reply

    asyncio.run(answer(message, dialogue_service))

    assert message.answer.await_args_list == [
        call(prefix + "<b>бв</b>", parse_mode=ParseMode.HTML),
        call("<b>гд</b> и **незакрытый фрагмент", parse_mode=ParseMode.HTML),
    ]


def test_llm_error_is_hidden_from_user_and_logs(caplog):
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        text="Секретный вопрос",
        answer=AsyncMock(),
    )
    dialogue_service = AsyncMock(spec=DialogueService)
    dialogue_service.reply.side_effect = RuntimeError("Секретный ответ сервиса")

    with caplog.at_level(logging.ERROR, logger="bot.handlers"):
        asyncio.run(answer(message, dialogue_service))

    message.answer.assert_awaited_once_with(ERROR_MESSAGE)
    assert "RuntimeError" in caplog.text
    assert "Секретный вопрос" not in caplog.text
    assert "Секретный ответ сервиса" not in caplog.text


def test_empty_llm_reply_shows_error_message(caplog):
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        text="Вопрос",
        answer=AsyncMock(),
    )
    dialogue_service = AsyncMock(spec=DialogueService)
    dialogue_service.reply.return_value = " \n "

    with caplog.at_level(logging.ERROR, logger="bot.handlers"):
        asyncio.run(answer(message, dialogue_service))

    message.answer.assert_awaited_once_with(ERROR_MESSAGE)
    assert "пустой ответ" in caplog.text


def test_telegram_error_is_logged_without_response_text(caplog):
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        text="Вопрос",
        answer=AsyncMock(side_effect=RuntimeError("Секретный ответ")),
    )
    dialogue_service = AsyncMock(spec=DialogueService)
    dialogue_service.reply.return_value = "Секретный ответ"

    with caplog.at_level(logging.ERROR, logger="bot.handlers"):
        asyncio.run(answer(message, dialogue_service))

    assert "RuntimeError" in caplog.text
    assert "Секретный ответ" not in caplog.text


def photo_message(**kwargs):
    fields = dict(
        from_user=SimpleNamespace(id=1),
        caption="Обед",
        media_group_id=None,
        photo=[PhotoSize(file_id="small", file_unique_id="small", width=100, height=100)],
        answer=AsyncMock(),
    )
    fields.update(kwargs)
    return SimpleNamespace(**fields)


@pytest.mark.parametrize(
    "image,mime_type",
    [
        (b"\xff\xd8\xffprivate-photo", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\nprivate-photo", "image/png"),
        (b"RIFF\x00\x00\x00\x00WEBPprivate-photo", "image/webp"),
    ],
)
def test_downloads_largest_allowed_photo_and_sends_full_reply(image, mime_type):
    chosen = PhotoSize(
        file_id="large", file_unique_id="large", width=500, height=500, file_size=MAX_PHOTO_BYTES
    )
    oversized = PhotoSize(
        file_id="huge",
        file_unique_id="huge",
        width=1000,
        height=1000,
        file_size=MAX_PHOTO_BYTES + 1,
    )
    message = photo_message(caption=None)
    message.photo.extend([oversized, chosen])
    service = AsyncMock(spec=DialogueService)
    service.reply_photo.return_value = "а" * TELEGRAM_MESSAGE_LIMIT + "**Ответ**"
    buffers = []

    async def download(photo, destination, **kwargs):
        assert photo is chosen
        assert kwargs == {"timeout": 30}
        buffers.append(destination)
        destination.write(image)

    bot = SimpleNamespace(download=AsyncMock(side_effect=download))
    asyncio.run(answer_photo(message, bot, service))
    bot.download.assert_awaited_once()
    service.reply_photo.assert_awaited_once_with(1, image, mime_type, None)
    assert message.answer.await_args_list == [
        call("а" * TELEGRAM_MESSAGE_LIMIT, parse_mode=ParseMode.HTML),
        call("<b>Ответ</b>", parse_mode=ParseMode.HTML),
    ]
    assert buffers[0].closed


@pytest.mark.parametrize(
    "file_size,media_group_id,expected",
    [
        (MAX_PHOTO_BYTES + 1, None, PHOTO_FORMAT_MESSAGE),
        (100, "album", PHOTO_ALBUM_MESSAGE),
    ],
)
def test_rejected_photo_does_not_download_or_call_service(file_size, media_group_id, expected):
    message = photo_message(
        media_group_id=media_group_id,
        photo=[
            PhotoSize(
                file_id="photo", file_unique_id="photo", width=100, height=100, file_size=file_size
            )
        ],
    )
    bot = SimpleNamespace(download=AsyncMock())
    service = AsyncMock(spec=DialogueService)
    asyncio.run(answer_photo(message, bot, service))
    bot.download.assert_not_awaited()
    service.reply_photo.assert_not_awaited()
    message.answer.assert_awaited_once_with(expected)


@pytest.mark.parametrize("image", [b"", b"private-invalid-photo", b"GIF89a"])
def test_empty_or_unsupported_download_does_not_call_service(image):
    message = photo_message()
    service = AsyncMock(spec=DialogueService)
    buffers = []

    async def download(photo, destination, **kwargs):
        buffers.append(destination)
        destination.write(image)

    asyncio.run(answer_photo(message, SimpleNamespace(download=download), service))
    message.answer.assert_awaited_once_with(PHOTO_FORMAT_MESSAGE)
    service.reply_photo.assert_not_awaited()
    assert buffers[0].closed


def test_download_limit_is_enforced_without_file_size():
    message = photo_message()
    service = AsyncMock(spec=DialogueService)
    buffers = []

    async def download(photo, destination, **kwargs):
        assert photo.file_size is None
        buffers.append(destination)
        destination.write(b"x" * MAX_PHOTO_BYTES)
        destination.write(b"x")

    asyncio.run(answer_photo(message, SimpleNamespace(download=download), service))
    service.reply_photo.assert_not_awaited()
    message.answer.assert_awaited_once_with(PHOTO_FORMAT_MESSAGE)
    assert buffers[0].closed


@pytest.mark.parametrize("stage", ["download", "analysis"])
def test_photo_errors_hide_payload_and_next_text_still_works(stage, caplog):
    message = photo_message(caption="private-caption")
    service = AsyncMock(spec=DialogueService)
    service.reply.return_value = "Следующий ответ"
    service.reply_photo.return_value = "Фотоответ"
    buffers = []
    private_error = "private-caption data:image/jpeg;base64,cHJpdmF0ZQ== bot123456:secret"

    async def download(photo, destination, **kwargs):
        buffers.append(destination)
        if stage == "download":
            raise RuntimeError(private_error)
        destination.write(b"\xff\xd8\xffprivate-image")

    if stage == "analysis":
        service.reply_photo.side_effect = RuntimeError(private_error)

    async def check():
        await answer_photo(message, SimpleNamespace(download=download), service)
        message.answer.assert_awaited_once_with(ERROR_MESSAGE)
        message.text = "Следующий вопрос"
        await answer(message, service)

    with caplog.at_level(logging.ERROR):
        asyncio.run(check())
    assert "RuntimeError" in caplog.text
    for secret in ("private-caption", "private-image", "cHJpdmF0ZQ==", "123456:secret"):
        assert secret not in caplog.text
    assert buffers[0].closed
    service.reply.assert_awaited_once_with(1, "Следующий вопрос")
    if stage == "download":
        service.reply_photo.assert_not_awaited()


@pytest.mark.parametrize("reply", ["", " \n "])
def test_empty_photo_response_shows_error(reply):
    message = photo_message()
    service = AsyncMock(spec=DialogueService)
    service.reply_photo.return_value = reply

    async def download(photo, destination, **kwargs):
        destination.write(b"\xff\xd8\xffphoto")

    asyncio.run(answer_photo(message, SimpleNamespace(download=download), service))
    message.answer.assert_awaited_once_with(ERROR_MESSAGE)


def test_photo_timeout_covers_download_and_closes_buffer(monkeypatch):
    message = photo_message()
    service = AsyncMock(spec=DialogueService)
    buffers = []

    async def download(photo, destination, **kwargs):
        buffers.append(destination)
        await asyncio.Event().wait()

    monkeypatch.setattr("bot.handlers.PHOTO_DOWNLOAD_TIMEOUT_SECONDS", 0.01)
    asyncio.run(answer_photo(message, SimpleNamespace(download=download), service))
    message.answer.assert_awaited_once_with(ERROR_MESSAGE)
    service.reply_photo.assert_not_awaited()
    assert buffers[0].closed


def test_photo_send_error_keeps_saved_exchange(tmp_path, caplog):
    from bot.history_store import HistoryStore
    from bot.image_client import ImageClient
    from bot.llm_client import LlmClient

    message = photo_message(caption="Обед", answer=AsyncMock(side_effect=RuntimeError("secret")))
    image_client = AsyncMock(spec=ImageClient)
    image_client.analyze.return_value = "Вижу овощи"
    store = HistoryStore(10, tmp_path)
    service = DialogueService(
        AsyncMock(spec=LlmClient),
        "Роль",
        store,
        image_client=image_client,
        image_prompt="Фото",
    )

    async def download(photo, destination, **kwargs):
        destination.write(b"\xff\xd8\xffphoto")

    with caplog.at_level(logging.ERROR):
        asyncio.run(answer_photo(message, SimpleNamespace(download=download), service))
    assert store.get(1) == [
        {"role": "user", "content": "Обед"},
        {"role": "assistant", "content": "Вижу овощи"},
    ]
    assert "secret" not in caplog.text
