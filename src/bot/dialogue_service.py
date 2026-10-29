"""Подготовка запроса и получение ответа ассистента."""

from bot.history_store import HistoryStore
from bot.llm_client import LlmClient


class DialogueService:
    def __init__(
        self, llm_client: LlmClient, system_prompt: str, history_store: HistoryStore
    ) -> None:
        self.llm_client = llm_client
        self.system_prompt = system_prompt
        self.history_store = history_store

    async def reply(self, user_id: int, text: str) -> str:
        reply = await self.llm_client.complete(
            [
                {"role": "system", "content": self.system_prompt},
                *self.history_store.get(user_id),
                {"role": "user", "content": text},
            ]
        )
        if reply.strip():
            self.history_store.append(user_id, {"role": "user", "content": text})
            self.history_store.append(user_id, {"role": "assistant", "content": reply})
        return reply

    def clear(self, user_id: int) -> None:
        self.history_store.clear(user_id)
