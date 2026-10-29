import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from aiogram.types import Chat, Message, User

from bot.dialogue_service import DialogueService
from bot.history_store import HistoryStore
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


def test_clear_and_next_message_wait_until_previous_reply_is_sent():
    async def check():
        middleware = PerUserMiddleware()
        client = AsyncMock(spec=LlmClient)
        client.complete.return_value = "Ответ"
        service = DialogueService(client, "Роль", HistoryStore(10))
        sending = asyncio.Event()
        release = asyncio.Event()
        events = []

        async def handler(event, data):
            events.append(f"{event.text}:start")
            if event.text == "/clear":
                service.clear(event.from_user.id)
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


def test_different_users_are_processed_concurrently():
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


def test_exception_releases_user_lock():
    async def check():
        middleware = PerUserMiddleware()
        handler = AsyncMock(side_effect=[RuntimeError("Тестовый сбой"), "Ответ"])
        with pytest.raises(RuntimeError):
            await middleware(handler, message(1, "Первый"), {})
        assert await middleware(handler, message(1, "Следующий"), {}) == "Ответ"

    asyncio.run(asyncio.wait_for(check(), timeout=3))
