import asyncio
import base64
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openai import AsyncOpenAI

from bot.image_client import ImageClient


def sdk_stub(content="Ответ по фото"):
    sdk = AsyncMock(spec=AsyncOpenAI)
    sdk.chat = SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
    sdk.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
    return sdk


@pytest.mark.parametrize("mime_type", ["image/jpeg", "image/png", "image/webp"])
def test_image_payload_preserves_history_and_sends_text_first(mime_type):
    image = b"private-image-\x00\xff"
    messages = [
        {"role": "system", "content": "Роль и фотоинструкции"},
        {"role": "user", "content": "Моя цель"},
        {"role": "assistant", "content": "Уточнение"},
    ]
    original = deepcopy(messages)
    sdk = sdk_stub()
    reply = asyncio.run(ImageClient(sdk, "image-model").analyze(image, mime_type, "Обед", messages))
    assert reply == "Ответ по фото"
    assert messages == original
    sdk.chat.completions.create.assert_awaited_once()
    kwargs = sdk.chat.completions.create.await_args.kwargs
    assert kwargs["model"] == "image-model"
    assert kwargs["messages"][:-1] == messages
    current = kwargs["messages"][-1]
    assert current["role"] == "user"
    assert current["content"][0] == {"type": "text", "text": "Обед"}
    assert current["content"][1]["type"] == "image_url"
    prefix, encoded = current["content"][1]["image_url"]["url"].split(",", 1)
    assert prefix == f"data:{mime_type};base64"
    assert base64.b64decode(encoded) == image


@pytest.mark.parametrize("content", [None, "", " \n "])
def test_empty_image_response(content):
    assert asyncio.run(
        ImageClient(sdk_stub(content), "vision").analyze(b"image", "image/jpeg", "Фото", [])
    ) == (content or "")


def test_failed_request_is_not_retried_or_logged(caplog):
    sdk = sdk_stub()
    sdk.chat.completions.create.side_effect = RuntimeError("private-response")
    with pytest.raises(RuntimeError):
        asyncio.run(
            ImageClient(sdk, "vision").analyze(
                b"private-image", "image/jpeg", "private-caption", []
            )
        )
    sdk.chat.completions.create.assert_awaited_once()
    assert not caplog.records


def test_total_timeout_cancels_image_request(monkeypatch):
    sdk = sdk_stub()

    async def wait_forever(**kwargs):
        await asyncio.Event().wait()

    sdk.chat.completions.create.side_effect = wait_forever
    monkeypatch.setattr("bot.image_client.IMAGE_TIMEOUT_SECONDS", 0.02)
    with pytest.raises(TimeoutError):
        asyncio.run(ImageClient(sdk, "vision").analyze(b"image", "image/jpeg", "Фото", []))
    sdk.chat.completions.create.assert_awaited_once()
