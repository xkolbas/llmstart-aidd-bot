"""Ограниченная история пользователей в памяти процесса."""

from collections import deque

from openai.types.chat import ChatCompletionMessageParam


class HistoryStore:
    def __init__(self, max_exchanges: int) -> None:
        if max_exchanges <= 0:
            raise ValueError("Лимит истории должен быть положительным")
        self.max_messages = max_exchanges * 2
        self._histories: dict[int, deque[ChatCompletionMessageParam]] = {}

    def get(self, user_id: int) -> list[ChatCompletionMessageParam]:
        return [message.copy() for message in self._histories.get(user_id, ())]

    def append(self, user_id: int, message: ChatCompletionMessageParam) -> None:
        history = self._histories.setdefault(user_id, deque(maxlen=self.max_messages))
        history.append(message.copy())

    def clear(self, user_id: int) -> None:
        self._histories.pop(user_id, None)
