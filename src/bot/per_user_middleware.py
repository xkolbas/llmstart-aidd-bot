"""Последовательное выполнение обработчиков одного пользователя."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message


class PerUserMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if event.chat.type != "private" or event.from_user is None:
            return await handler(event, data)

        lock = self._locks.setdefault(event.from_user.id, asyncio.Lock())
        async with lock:
            return await handler(event, data)
