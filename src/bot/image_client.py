"""Анализ изображений через OpenRouter Chat Completions."""

import asyncio
import base64

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

IMAGE_TIMEOUT_SECONDS = 60.0


class ImageClient:
    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self.client = client
        self.model = model

    async def analyze(
        self,
        image: bytes,
        mime_type: str,
        caption: str,
        messages: list[ChatCompletionMessageParam],
    ) -> str:
        async with asyncio.timeout(IMAGE_TIMEOUT_SECONDS):
            encoded = (await asyncio.to_thread(base64.b64encode, image)).decode("ascii")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    *messages,
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": caption},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                            },
                        ],
                    },
                ],
            )
        return response.choices[0].message.content or ""
