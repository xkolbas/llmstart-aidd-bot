import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from aiogram.types import Chat, Message, User

from bot.dialogue_service import DialogueService
from bot.history_store import HistoryStore
from bot.image_client import ImageClient
from bot.llm_client import LlmClient
from bot.per_user_middleware import PerUserMiddleware


def message(user_id, text):
    return Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=user_id, type="private"),
        from_user=User(id=user_id, is_bot=False, first_name="Тест"),
        text=text,
    )


def test_clear_and_next_message_wait_until_previous_reply_is_sent(tmp_path):
    async def check():
        middleware = PerUserMiddleware()
        client = AsyncMock(spec=LlmClient)
        client.complete.return_value = "Ответ"
        service = DialogueService(
            client,
            "Роль",
            HistoryStore(10, tmp_path),
            image_client=AsyncMock(spec=ImageClient),
            image_prompt="Фотоинструкции",
        )
        sending = asyncio.Event()
        release = asyncio.Event()
        events = []

        async def handler(event, data):
            events.append(f"{event.text}:start")
            if event.text == "/clear":
                await service.clear(event.from_user.id)
            else:
                await service.reply(event.from_user.id, event.text)
            if event.text == "Первый":
                sending.set()
                await release.wait()
            events.append(f"{event.text}:sent")

        first = asyncio.create_task(middleware(handler, message(1, "Первый"), {}))
        await sending.wait()
        clear = asyncio.create_task(middleware(handler, message(1, "/clear"), {}))
        next_message = asyncio.create_task(middleware(handler, message(1, "Следующий"), {}))
        await asyncio.sleep(0)
        assert events == ["Первый:start"]
        assert len(service.history_store.get(1)) == 2
        release.set()
        await asyncio.gather(first, clear, next_message)
        assert events == [
            "Первый:start",
            "Первый:sent",
            "/clear:start",
            "/clear:sent",
            "Следующий:start",
            "Следующий:sent",
        ]
        assert client.complete.await_args_list[1].args[0] == [
            {"role": "system", "content": "Роль"},
            {"role": "user", "content": "Следующий"},
        ]
        assert service.history_store.get(1) == [
            {"role": "user", "content": "Следующий"},
            {"role": "assistant", "content": "Ответ"},
        ]

    asyncio.run(asyncio.wait_for(check(), timeout=3))


def test_different_users_are_processed_concurrently(tmp_path):
    async def check():
        middleware = PerUserMiddleware()
        first_started = asyncio.Event()
        second_finished = asyncio.Event()

        async def handler(event, data):
            if event.from_user.id == 1:
                first_started.set()
                await second_finished.wait()
            else:
                second_finished.set()

        first = asyncio.create_task(middleware(handler, message(1, "Первый"), {}))
        await first_started.wait()
        await middleware(handler, message(2, "Другой пользователь"), {})
        await first

    asyncio.run(asyncio.wait_for(check(), timeout=3))


def test_exception_releases_user_lock(tmp_path):
    async def check():
        middleware = PerUserMiddleware()
        handler = AsyncMock(side_effect=[RuntimeError("Тестовый сбой"), "Ответ"])
        with pytest.raises(RuntimeError):
            await middleware(handler, message(1, "Первый"), {})
        assert await middleware(handler, message(1, "Следующий"), {}) == "Ответ"

    asyncio.run(asyncio.wait_for(check(), timeout=3))


def test_photo_download_send_text_and_clear_are_serialized(tmp_path):
    async def check():
        middleware = PerUserMiddleware()
        client = AsyncMock(spec=LlmClient)
        client.complete.return_value = "Текстовый ответ"
        image_client = AsyncMock(spec=ImageClient)
        image_client.analyze.return_value = "Описание фото"
        store = HistoryStore(10, tmp_path)
        service = DialogueService(
            client, "Роль", store, image_client=image_client, image_prompt="Фото"
        )
        downloading = asyncio.Event()
        release_download = asyncio.Event()
        sending = asyncio.Event()
        release_send = asyncio.Event()
        events = []

        async def handler(event, data):
            events.append((event.from_user.id, event.text, "start"))
            if event.text == "Фото":
                downloading.set()
                await release_download.wait()
                await service.reply_photo(event.from_user.id, b"photo", "image/jpeg")
                sending.set()
                await release_send.wait()
            elif event.text == "/clear":
                await service.clear(event.from_user.id)
            else:
                await service.reply(event.from_user.id, event.text)
            events.append((event.from_user.id, event.text, "sent"))

        first = asyncio.create_task(middleware(handler, message(1, "Фото"), {}))
        await downloading.wait()
        text = asyncio.create_task(middleware(handler, message(1, "Уточнение"), {}))
        clear = asyncio.create_task(middleware(handler, message(1, "/clear"), {}))
        await asyncio.sleep(0)
        await middleware(handler, message(2, "Другой пользователь"), {})
        assert events == [
            (1, "Фото", "start"),
            (2, "Другой пользователь", "start"),
            (2, "Другой пользователь", "sent"),
        ]
        release_download.set()
        await sending.wait()
        await asyncio.sleep(0)
        assert not text.done()
        assert not clear.done()
        assert len(store.get(1)) == 2
        release_send.set()
        await asyncio.gather(first, text, clear)
        assert events[3:] == [
            (1, "Фото", "sent"),
            (1, "Уточнение", "start"),
            (1, "Уточнение", "sent"),
            (1, "/clear", "start"),
            (1, "/clear", "sent"),
        ]
        assert store.get(1) == []
        assert len(store.get(2)) == 2
        assert client.complete.await_args_list[-1].args[0] == [
            {"role": "system", "content": "Роль"},
            {"role": "user", "content": "Фото"},
            {"role": "assistant", "content": "Описание фото"},
            {"role": "user", "content": "Уточнение"},
        ]

    asyncio.run(asyncio.wait_for(check(), timeout=3))
