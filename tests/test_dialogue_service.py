import asyncio
from unittest.mock import AsyncMock

from bot.dialogue_service import DialogueService
from bot.llm_client import LlmClient


def test_includes_prompt_and_current_question_without_history():
    client = AsyncMock(spec=LlmClient)
    client.complete.return_value = "Ответ"
    service = DialogueService(client, "Отвечай кратко")

    async def check():
        assert await service.reply("Первый вопрос") == "Ответ"
        assert await service.reply("Второй вопрос") == "Ответ"

    asyncio.run(check())
    assert client.complete.await_count == 2
    assert client.complete.await_args_list[0].args[0] == [
        {"role": "system", "content": "Отвечай кратко"},
        {"role": "user", "content": "Первый вопрос"},
    ]
    assert client.complete.await_args_list[1].args[0] == [
        {"role": "system", "content": "Отвечай кратко"},
        {"role": "user", "content": "Второй вопрос"},
    ]
