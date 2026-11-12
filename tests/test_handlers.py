import asyncio
import logging
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

from aiogram import Bot, Dispatcher
from aiogram.methods import SendMessage
from aiogram.types import Chat, Message, Update, User

from bot.dialogue_service import DialogueService
from bot.handlers import ERROR_MESSAGE, TELEGRAM_MESSAGE_LIMIT, answer, router


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
                ("group", "/clear"),
                ("private", "/clear"),
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

        assert session.await_count == 5
        method = session.await_args_list[0].args[1]
        assert isinstance(method, SendMessage)
        assert method.chat_id == 1
        assert method.text.startswith("Привет! Я бот-ассистент.")
        assert "текстовый вопрос" in method.text
        assert "/clear" in method.text
        reply = session.await_args_list[1].args[1]
        assert isinstance(reply, SendMessage)
        assert reply.chat_id == 1
        assert reply.text == "Ответ ассистента"
        dialogue_service.reply.assert_awaited_once_with(1, "Привет")
        dialogue_service.clear.assert_called_once_with(1)
        assert session.await_args_list[2].args[1].text.startswith("Неизвестная команда")
        assert session.await_args_list[3].args[1].text == (
            "Я поддерживаю только текстовые сообщения."
        )
        assert session.await_args_list[4].args[1].text.startswith("История очищена")

    asyncio.run(check())


def test_long_reply_is_sent_completely_and_in_order():
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        text="Вопрос",
        answer=AsyncMock(),
    )
    dialogue_service = AsyncMock(spec=DialogueService)
    reply = "а" * TELEGRAM_MESSAGE_LIMIT + "б" * 10
    dialogue_service.reply.return_value = reply

    asyncio.run(answer(message, dialogue_service))

    assert message.answer.await_args_list == [
        call("а" * TELEGRAM_MESSAGE_LIMIT),
        call("б" * 10),
    ]
    assert "".join(item.args[0] for item in message.answer.await_args_list) == reply


def test_llm_error_is_hidden_from_user_and_logs(caplog):
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        text="Секретный вопрос",
        answer=AsyncMock(),
    )
    dialogue_service = AsyncMock(spec=DialogueService)
    dialogue_service.reply.side_effect = RuntimeError("Секретный ответ сервиса")

    with caplog.at_level(logging.ERROR, logger="bot.handlers"):
        asyncio.run(answer(message, dialogue_service))

    message.answer.assert_awaited_once_with(ERROR_MESSAGE)
    assert "RuntimeError" in caplog.text
    assert "Секретный вопрос" not in caplog.text
    assert "Секретный ответ сервиса" not in caplog.text


def test_empty_llm_reply_shows_error_message(caplog):
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        text="Вопрос",
        answer=AsyncMock(),
    )
    dialogue_service = AsyncMock(spec=DialogueService)
    dialogue_service.reply.return_value = " \n "

    with caplog.at_level(logging.ERROR, logger="bot.handlers"):
        asyncio.run(answer(message, dialogue_service))

    message.answer.assert_awaited_once_with(ERROR_MESSAGE)
    assert "пустой ответ" in caplog.text


def test_telegram_error_is_logged_without_response_text(caplog):
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        text="Вопрос",
        answer=AsyncMock(side_effect=RuntimeError("Секретный ответ")),
    )
    dialogue_service = AsyncMock(spec=DialogueService)
    dialogue_service.reply.return_value = "Секретный ответ"

    with caplog.at_level(logging.ERROR, logger="bot.handlers"):
        asyncio.run(answer(message, dialogue_service))

    assert "RuntimeError" in caplog.text
    assert "Секретный ответ" not in caplog.text
