from typing import AsyncIterable

SENTENCE_BOUNDARIES = {"।", "!", "?", ".", "|"}
MIN_SEGMENT_LENGTH = 30
MAX_SEGMENT_LENGTH = 150


def split_at_danda(text: str) -> list[str]:
    """
    Split text at Devanagari danda (।) and other sentence boundaries.
    Returns list of segments. Last segment may be incomplete (buffer).
    """
    segments = []
    buffer = ""

    for char in text:
        buffer += char

        if char in SENTENCE_BOUNDARIES and len(buffer) >= MIN_SEGMENT_LENGTH:
            segments.append(buffer)
            buffer = ""
        elif len(buffer) >= MAX_SEGMENT_LENGTH:
            last_space = buffer.rfind(" ")
            if last_space > MIN_SEGMENT_LENGTH:
                segments.append(buffer[:last_space])
                buffer = buffer[last_space:]
            else:
                segments.append(buffer)
                buffer = ""

    segments.append(buffer)
    return segments


async def async_iter(text: str) -> AsyncIterable[str]:
    """Convert a string into an async iterable yielding the full string once."""
    yield text
