"""Подготовка запроса и получение ответа ассистента."""

from bot.llm_client import LlmClient


class DialogueService:
    def __init__(self, llm_client: LlmClient, system_prompt: str) -> None:
        self.llm_client = llm_client
        self.system_prompt = system_prompt

    async def reply(self, text: str) -> str:
        return await self.llm_client.complete(
            [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": text},
            ]
        )
