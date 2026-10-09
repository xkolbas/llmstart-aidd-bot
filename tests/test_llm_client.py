import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openai import AsyncOpenAI

from bot.llm_client import LlmClient


def test_sends_model_and_messages_and_returns_response():
    sdk = AsyncMock(spec=AsyncOpenAI)
    sdk.chat = SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
    sdk.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Ответ"))]
    )
    messages = [
        {"role": "system", "content": "Роль"},
        {"role": "user", "content": "Вопрос"},
    ]
    reply = asyncio.run(LlmClient(sdk, "test-model").complete(messages))
    assert reply == "Ответ"
    sdk.chat.completions.create.assert_awaited_once_with(model="test-model", messages=messages)


def test_does_not_retry_failed_request():
    sdk = AsyncMock(spec=AsyncOpenAI)
    sdk.chat = SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
    sdk.chat.completions.create.side_effect = RuntimeError("Тестовый сбой")
    with pytest.raises(RuntimeError, match="Тестовый сбой"):
        asyncio.run(LlmClient(sdk, "test-model").complete([]))
    sdk.chat.completions.create.assert_awaited_once()
