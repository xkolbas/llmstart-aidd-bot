import asyncio
from unittest.mock import AsyncMock

import pytest

from bot.dialogue_service import DialogueService
from bot.history_store import HistoryStore
from bot.image_client import ImageClient
from bot.llm_client import LlmClient


def test_includes_prompt_current_question_and_user_history(tmp_path):
    client = AsyncMock(spec=LlmClient)
    client.complete.return_value = "Ответ"
    store = HistoryStore(10, tmp_path)
    service = DialogueService(
        client,
        "Отвечай кратко",
        store,
        image_client=AsyncMock(spec=ImageClient),
        image_prompt="Фотоинструкции",
    )

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


def test_clear_starts_new_context(tmp_path):
    client = AsyncMock(spec=LlmClient)
    client.complete.return_value = "Ответ"
    store = HistoryStore(10, tmp_path)
    service = DialogueService(
        client,
        "Роль",
        store,
        image_client=AsyncMock(spec=ImageClient),
        image_prompt="Фотоинструкции",
    )

    async def check():
        await service.reply(1, "До очистки")
        await service.clear(1)
        assert store.get(1) == []
        await service.reply(1, "После очистки")

    asyncio.run(check())
    client.complete.assert_awaited_with(
        [{"role": "system", "content": "Роль"}, {"role": "user", "content": "После очистки"}]
    )


def test_failed_request_keeps_history_unchanged(tmp_path):
    client = AsyncMock(spec=LlmClient)
    client.complete.side_effect = RuntimeError("Тестовый сбой")
    store = HistoryStore(1, tmp_path)
    store.append(1, {"role": "user", "content": "Старый вопрос"})
    store.append(1, {"role": "assistant", "content": "Старый ответ"})
    previous = store.get(1)
    service = DialogueService(
        client,
        "Роль",
        store,
        image_client=AsyncMock(spec=ImageClient),
        image_prompt="Фотоинструкции",
    )
    with pytest.raises(RuntimeError):
        asyncio.run(service.reply(1, "Новый вопрос"))
    assert store.get(1) == previous


@pytest.mark.parametrize("reply", ["", " \n "])
def test_empty_response_keeps_history_unchanged(reply, tmp_path):
    client = AsyncMock(spec=LlmClient)
    client.complete.return_value = reply
    store = HistoryStore(1, tmp_path)
    store.append(1, {"role": "user", "content": "Старый вопрос"})
    store.append(1, {"role": "assistant", "content": "Старый ответ"})
    previous = store.get(1)
    service = DialogueService(
        client,
        "Роль",
        store,
        image_client=AsyncMock(spec=ImageClient),
        image_prompt="Фотоинструкции",
    )
    assert asyncio.run(service.reply(1, "Новый вопрос")) == reply
    assert store.get(1) == previous


@pytest.mark.parametrize("caption,stored", [(None, "Фото"), (" \n ", "Фото"), (" Обед ", "Обед")])
def test_photo_uses_prompts_history_and_saves_only_text(caption, stored, tmp_path):
    text_client = AsyncMock(spec=LlmClient)
    text_client.complete.return_value = "Рецепт"
    image_client = AsyncMock(spec=ImageClient)
    image_client.analyze.return_value = "Вижу яйца и овощи. Какая цель?"
    store = HistoryStore(10, tmp_path)
    store.append_exchange(1, "Без молока", "Учту ограничение")
    store.append_exchange(2, "Чужой вопрос", "Чужой ответ")
    history = store.get(1)
    service = DialogueService(
        text_client, "Роль", store, image_client=image_client, image_prompt="Анализ фото"
    )

    async def check():
        reply = await service.reply_photo(1, b"private-image", "image/jpeg", caption)
        assert reply == "Вижу яйца и овощи. Какая цель?"
        image_client.analyze.assert_awaited_once_with(
            image=b"private-image",
            mime_type="image/jpeg",
            caption=stored,
            messages=[{"role": "system", "content": "Роль\n\nАнализ фото"}, *history],
        )
        assert store.get(1) == [
            *history,
            {"role": "user", "content": stored},
            {"role": "assistant", "content": reply},
        ]
        assert store.get(2) == [
            {"role": "user", "content": "Чужой вопрос"},
            {"role": "assistant", "content": "Чужой ответ"},
        ]
        text_client.complete.assert_not_awaited()
        photo_history = store.get(1)
        await service.reply(1, "Хочу поддерживать вес")
        text_client.complete.assert_awaited_once_with(
            [
                {"role": "system", "content": "Роль"},
                *photo_history,
                {"role": "user", "content": "Хочу поддерживать вес"},
            ]
        )

    asyncio.run(check())
    assert sorted(path.name for path in tmp_path.iterdir()) == ["1.json", "2.json"]
    content = (tmp_path / "1.json").read_text()
    assert "private-image" not in content
    assert "base64" not in content
    assert "image_url" not in content


@pytest.mark.parametrize("outcome", [RuntimeError("сбой"), "", " \n "])
def test_failed_photo_preserves_file_and_next_text_works(outcome, tmp_path):
    text_client = AsyncMock(spec=LlmClient)
    text_client.complete.return_value = "Текст работает"
    image_client = AsyncMock(spec=ImageClient)
    if isinstance(outcome, Exception):
        image_client.analyze.side_effect = outcome
    else:
        image_client.analyze.return_value = outcome
    store = HistoryStore(1, tmp_path)
    store.append_exchange(1, "Старый вопрос", "Старый ответ")
    original = (tmp_path / "1.json").read_bytes()
    service = DialogueService(
        text_client, "Роль", store, image_client=image_client, image_prompt="Фото"
    )

    async def check():
        if isinstance(outcome, Exception):
            with pytest.raises(RuntimeError):
                await service.reply_photo(1, b"private", "image/png")
        else:
            assert await service.reply_photo(1, b"private", "image/png") == outcome
        assert (tmp_path / "1.json").read_bytes() == original
        assert await service.reply(1, "Новый вопрос") == "Текст работает"

    asyncio.run(check())
    assert store.get(1) == [
        {"role": "user", "content": "Новый вопрос"},
        {"role": "assistant", "content": "Текст работает"},
    ]


def test_corrupt_history_is_not_overwritten_or_sent_to_image_client(tmp_path):
    path = tmp_path / "1.json"
    path.write_text("corrupt-history")
    image_client = AsyncMock(spec=ImageClient)
    service = DialogueService(
        AsyncMock(spec=LlmClient),
        "Роль",
        HistoryStore(10, tmp_path),
        image_client=image_client,
        image_prompt="Фото",
    )
    with pytest.raises(ValueError):
        asyncio.run(service.reply_photo(1, b"photo", "image/jpeg"))
    image_client.analyze.assert_not_awaited()
    assert path.read_text() == "corrupt-history"
