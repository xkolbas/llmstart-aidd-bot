"""Подготовка запроса и получение ответа ассистента."""

import asyncio

from bot.history_store import HistoryStore
from bot.image_client import ImageClient
from bot.llm_client import LlmClient


class DialogueService:
    def __init__(
        self,
        llm_client: LlmClient,
        system_prompt: str,
        history_store: HistoryStore,
        *,
        image_client: ImageClient,
        image_prompt: str,
    ) -> None:
        self.llm_client = llm_client
        self.system_prompt = system_prompt
        self.history_store = history_store
        self.image_client = image_client
        self.image_prompt = image_prompt

    async def reply(self, user_id: int, text: str) -> str:
        history = await asyncio.to_thread(self.history_store.get, user_id)
        reply = await self.llm_client.complete(
            [
                {"role": "system", "content": self.system_prompt},
                *history,
                {"role": "user", "content": text},
            ]
        )
        if reply.strip():
            await asyncio.to_thread(self.history_store.append_exchange, user_id, text, reply)
        return reply

    async def reply_photo(
        self,
        user_id: int,
        image: bytes,
        mime_type: str,
        caption: str | None = None,
    ) -> str:
        text = (caption or "").strip() or "Фото"
        history = await asyncio.to_thread(self.history_store.get, user_id)
        reply = await self.image_client.analyze(
            image=image,
            mime_type=mime_type,
            caption=text,
            messages=[
                {"role": "system", "content": f"{self.system_prompt}\n\n{self.image_prompt}"},
                *history,
            ],
        )
        if reply.strip():
            await asyncio.to_thread(self.history_store.append_exchange, user_id, text, reply)
        return reply

    async def clear(self, user_id: int) -> None:
        await asyncio.to_thread(self.history_store.clear, user_id)
