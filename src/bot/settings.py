"""Загрузка и проверка настроек приложения."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True, repr=False)
class Settings:
    telegram_bot_token: str
    openrouter_api_key: str
    openrouter_model: str
    history_max_exchanges: int
    system_prompt: str

    @classmethod
    def load(cls, root: Path | None = None) -> "Settings":
        root = root if root is not None else Path(__file__).resolve().parents[2]
        values = {**dotenv_values(root / ".env"), **os.environ}
        required = ("TELEGRAM_BOT_TOKEN", "OPENROUTER_API_KEY", "OPENROUTER_MODEL")
        missing = [name for name in required if not (values.get(name) or "").strip()]
        if missing:
            raise ValueError(f"Не заданы обязательные настройки: {', '.join(missing)}")

        try:
            limit = int(values.get("HISTORY_MAX_EXCHANGES", "10"))
        except (ValueError, TypeError) as error:
            raise ValueError(
                "HISTORY_MAX_EXCHANGES должен быть положительным целым числом"
            ) from error
        if limit <= 0:
            raise ValueError("HISTORY_MAX_EXCHANGES должен быть положительным целым числом")

        try:
            prompt = (root / "prompts/system.txt").read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as error:
            raise ValueError("Не удалось прочитать системный промпт prompts/system.txt") from error
        if not prompt:
            raise ValueError("Системный промпт prompts/system.txt не должен быть пустым")

        return cls(
            telegram_bot_token=values["TELEGRAM_BOT_TOKEN"].strip(),
            openrouter_api_key=values["OPENROUTER_API_KEY"].strip(),
            openrouter_model=values["OPENROUTER_MODEL"].strip(),
            history_max_exchanges=limit,
            system_prompt=prompt,
        )
