"""Запросы к LLM через OpenRouter."""

import asyncio

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

LLM_TIMEOUT_SECONDS = 60.0


class LlmClient:
    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self.client = client
        self.model = model

    async def complete(self, messages: list[ChatCompletionMessageParam]) -> str:
        async with asyncio.timeout(LLM_TIMEOUT_SECONDS):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
        return response.choices[0].message.content or ""
