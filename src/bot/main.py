"""Точка входа приложения."""

import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.handlers import router
from bot.settings import Settings


async def main() -> None:
    settings = Settings.load()
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    async with Bot(token=settings.telegram_bot_token) as bot:
        await dispatcher.start_polling(bot)


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
