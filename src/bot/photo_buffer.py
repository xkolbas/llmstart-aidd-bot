"""Буфер загрузки фото с ограничением размера в памяти."""

from io import BytesIO

MAX_PHOTO_BYTES = 5 * 1024 * 1024


class LimitedPhotoBuffer(BytesIO):
    def __init__(self, max_bytes: int = MAX_PHOTO_BYTES) -> None:
        super().__init__()
        self.max_bytes = max_bytes

    def write(self, data: bytes) -> int:
        if self.tell() + len(data) > self.max_bytes:
            raise ValueError("Превышен допустимый размер фотографии")
        return super().write(data)
