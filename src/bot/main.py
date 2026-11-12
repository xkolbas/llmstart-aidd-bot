"""Точка входа приложения."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from openai import AsyncOpenAI

from bot.dialogue_service import DialogueService
from bot.handlers import router
from bot.history_store import HistoryStore
from bot.llm_client import LlmClient
from bot.settings import Settings

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = Settings.load()
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    async with (
        AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=60.0,
            max_retries=0,
        ) as client,
        Bot(token=settings.telegram_bot_token) as bot,
    ):
        dialogue_service = DialogueService(
            LlmClient(client, settings.openrouter_model),
            settings.system_prompt,
            HistoryStore(settings.history_max_exchanges),
        )
        logger.info("Бот запускается")
        try:
            await dispatcher.start_polling(bot, dialogue_service=dialogue_service)
        finally:
            logger.info("Бот остановлен")


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except ValueError as error:
        raise SystemExit(f"Ошибка настройки: {error}") from None
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
