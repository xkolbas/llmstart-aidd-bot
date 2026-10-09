import asyncio
from unittest.mock import AsyncMock, Mock, patch

from bot.main import main
from bot.settings import Settings


def test_configures_clients_injects_service_and_closes_sessions():
    settings = Settings(
        telegram_bot_token="123456:test-token",
        openrouter_api_key="test-key",
        openrouter_model="test-model",
        history_max_exchanges=10,
        system_prompt="Тестовая роль",
    )
    sdk_context = AsyncMock()
    bot_context = AsyncMock()
    dispatcher = Mock()
    dispatcher.start_polling = AsyncMock()

    with (
        patch("bot.main.Settings.load", return_value=settings),
        patch("bot.main.AsyncOpenAI", return_value=sdk_context) as sdk_factory,
        patch("bot.main.Bot", return_value=bot_context) as bot_factory,
        patch("bot.main.Dispatcher", return_value=dispatcher),
    ):
        asyncio.run(main())

    sdk_factory.assert_called_once_with(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        timeout=60.0,
        max_retries=0,
    )
    bot_factory.assert_called_once_with(token="123456:test-token")
    dispatcher.start_polling.assert_awaited_once()
    assert dispatcher.start_polling.await_args.args == (bot_context.__aenter__.return_value,)
    service = dispatcher.start_polling.await_args.kwargs["dialogue_service"]
    assert service.system_prompt == "Тестовая роль"
    assert service.llm_client.model == "test-model"
    assert service.llm_client.client is sdk_context.__aenter__.return_value
    sdk_context.__aexit__.assert_awaited_once()
    bot_context.__aexit__.assert_awaited_once()
