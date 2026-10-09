import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from aiogram import Bot, Dispatcher
from aiogram.methods import SendMessage
from aiogram.types import Chat, Message, Update, User

from bot.handlers import router


def test_start_reply_is_sent_only_in_private_chat():
    async def check():
        session = AsyncMock()
        bot = Bot(token="123456:test-token", session=session)
        dispatcher = Dispatcher()
        dispatcher.include_router(router)

        for update_id, (chat_type, text) in enumerate(
            [("private", "/start"), ("group", "/start"), ("private", "Привет")], start=1
        ):
            update = Update(
                update_id=update_id,
                message=Message(
                    message_id=update_id,
                    date=datetime.now(UTC),
                    chat=Chat(id=1, type=chat_type),
                    from_user=User(id=1, is_bot=False, first_name="Тест"),
                    text=text,
                ),
            )
            await dispatcher.feed_update(bot, update)

        session.assert_awaited_once()
        method = session.call_args.args[1]
        assert isinstance(method, SendMessage)
        assert method.chat_id == 1
        assert method.text.startswith("Привет! Я бот-ассистент.")
        assert "/start" in method.text
        assert "на следующем этапе" in method.text

    asyncio.run(check())
