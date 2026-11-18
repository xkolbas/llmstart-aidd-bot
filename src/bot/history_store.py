"""Ограниченная история пользователей в JSON-файлах."""

import json
import os
import tempfile
from pathlib import Path

from openai.types.chat import ChatCompletionMessageParam


class HistoryStore:
    def __init__(self, max_exchanges: int, directory: Path) -> None:
        if max_exchanges <= 0:
            raise ValueError("Лимит истории должен быть положительным")
        self.max_messages = max_exchanges * 2
        self.directory = directory

    def _path(self, user_id: int) -> Path:
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("Некорректный user_id")
        return self.directory / f"{user_id}.json"

    def get(self, user_id: int) -> list[ChatCompletionMessageParam]:
        try:
            content = self._path(user_id).read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        messages = json.loads(content)
        if not isinstance(messages, list) or any(
            not isinstance(message, dict)
            or set(message) != {"role", "content"}
            or message["role"] not in ("user", "assistant")
            or not isinstance(message["content"], str)
            for message in messages
        ):
            raise ValueError("Некорректный формат файла истории")
        return messages[-self.max_messages :]

    def append(self, user_id: int, message: ChatCompletionMessageParam) -> None:
        self._save(user_id, [*self.get(user_id), message])

    def append_exchange(self, user_id: int, text: str, reply: str) -> None:
        self._save(
            user_id,
            [
                *self.get(user_id),
                {"role": "user", "content": text},
                {"role": "assistant", "content": reply},
            ],
        )

    def _save(self, user_id: int, messages: list[ChatCompletionMessageParam]) -> None:
        path = self._path(user_id)
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.directory, delete=False
            ) as stream:
                temporary = Path(stream.name)
                json.dump(messages[-self.max_messages :], stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def clear(self, user_id: int) -> None:
        self._path(user_id).unlink(missing_ok=True)
