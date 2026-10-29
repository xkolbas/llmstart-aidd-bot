import asyncio
from unittest.mock import AsyncMock

import pytest

from bot.dialogue_service import DialogueService
from bot.history_store import HistoryStore
from bot.llm_client import LlmClient


def test_includes_prompt_current_question_and_user_history():
    client = AsyncMock(spec=LlmClient)
    client.complete.return_value = "Ответ"
    store = HistoryStore(10)
    service = DialogueService(client, "Отвечай кратко", store)

    async def check():
        assert await service.reply(1, "Первый вопрос") == "Ответ"
        assert await service.reply(1, "Второй вопрос") == "Ответ"
        assert await service.reply(2, "Другой пользователь") == "Ответ"

    asyncio.run(check())
    assert client.complete.await_count == 3
    assert client.complete.await_args_list[0].args[0] == [
        {"role": "system", "content": "Отвечай кратко"},
        {"role": "user", "content": "Первый вопрос"},
    ]
    assert client.complete.await_args_list[1].args[0] == [
        {"role": "system", "content": "Отвечай кратко"},
        {"role": "user", "content": "Первый вопрос"},
        {"role": "assistant", "content": "Ответ"},
        {"role": "user", "content": "Второй вопрос"},
    ]
    assert client.complete.await_args_list[2].args[0] == [
        {"role": "system", "content": "Отвечай кратко"},
        {"role": "user", "content": "Другой пользователь"},
    ]
    assert len(store.get(1)) == 4
    assert len(store.get(2)) == 2


def test_clear_starts_new_context():
    client = AsyncMock(spec=LlmClient)
    client.complete.return_value = "Ответ"
    store = HistoryStore(10)
    service = DialogueService(client, "Роль", store)

    async def check():
        await service.reply(1, "До очистки")
        service.clear(1)
        assert store.get(1) == []
        await service.reply(1, "После очистки")

    asyncio.run(check())
    client.complete.assert_awaited_with(
        [{"role": "system", "content": "Роль"}, {"role": "user", "content": "После очистки"}]
    )


def test_failed_request_keeps_history_unchanged():
    client = AsyncMock(spec=LlmClient)
    client.complete.side_effect = RuntimeError("Тестовый сбой")
    store = HistoryStore(1)
    store.append(1, {"role": "user", "content": "Старый вопрос"})
    store.append(1, {"role": "assistant", "content": "Старый ответ"})
    previous = store.get(1)
    service = DialogueService(client, "Роль", store)
    with pytest.raises(RuntimeError):
        asyncio.run(service.reply(1, "Новый вопрос"))
    assert store.get(1) == previous


@pytest.mark.parametrize("reply", ["", " \n "])
def test_empty_response_keeps_history_unchanged(reply):
    client = AsyncMock(spec=LlmClient)
    client.complete.return_value = reply
    store = HistoryStore(1)
    store.append(1, {"role": "user", "content": "Старый вопрос"})
    store.append(1, {"role": "assistant", "content": "Старый ответ"})
    previous = store.get(1)
    service = DialogueService(client, "Роль", store)
    assert asyncio.run(service.reply(1, "Новый вопрос")) == reply
    assert store.get(1) == previous
