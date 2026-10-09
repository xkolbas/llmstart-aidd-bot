import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from aiogram import Bot, Dispatcher
from aiogram.methods import SendMessage
from aiogram.types import Chat, Message, Update, User

from bot.dialogue_service import DialogueService
from bot.handlers import router


def test_start_and_text_replies_are_sent_only_in_private_chat():
    async def check():
        session = AsyncMock()
        bot = Bot(token="123456:test-token", session=session)
        dispatcher = Dispatcher()
        dispatcher.include_router(router)
        dialogue_service = AsyncMock(spec=DialogueService)
        dialogue_service.reply.return_value = "Ответ ассистента"

        for update_id, (chat_type, text) in enumerate(
            [
                ("private", "/start"),
                ("group", "/start"),
                ("private", "Привет"),
                ("group", "Привет"),
                ("private", "/unknown"),
                ("private", None),
            ],
            start=1,
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
            await dispatcher.feed_update(bot, update, dialogue_service=dialogue_service)

        assert session.await_count == 2
        method = session.await_args_list[0].args[1]
        assert isinstance(method, SendMessage)
        assert method.chat_id == 1
        assert method.text.startswith("Привет! Я бот-ассистент.")
        assert "текстовый вопрос" in method.text
        assert "без истории диалога" in method.text
        reply = session.await_args_list[1].args[1]
        assert isinstance(reply, SendMessage)
        assert reply.chat_id == 1
        assert reply.text == "Ответ ассистента"
        dialogue_service.reply.assert_awaited_once_with("Привет")

    asyncio.run(check())
