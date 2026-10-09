"""Запросы к LLM через OpenRouter."""

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam


class LlmClient:
    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self.client = client
        self.model = model

    async def complete(self, messages: list[ChatCompletionMessageParam]) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content or ""
