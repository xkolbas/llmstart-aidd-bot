import pytest

from bot.photo_buffer import LimitedPhotoBuffer


def test_buffer_accepts_chunks_up_to_exact_limit():
    with LimitedPhotoBuffer(max_bytes=5) as buffer:
        assert buffer.write(b"12") == 2
        assert buffer.write(b"345") == 3
        assert buffer.getvalue() == b"12345"
    assert buffer.closed


def test_overflow_is_rejected_before_writing_and_buffer_is_closed():
    buffer = LimitedPhotoBuffer(max_bytes=5)
    with pytest.raises(ValueError), buffer:
        buffer.write(b"123")
        try:
            buffer.write(b"456")
        except ValueError:
            assert buffer.getvalue() == b"123"
            raise
    assert buffer.closed
