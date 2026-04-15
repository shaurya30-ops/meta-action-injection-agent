import re

USER_BLOCK_PATTERN = re.compile(
    r"<\|im_start\|>user\s*\n(.*?)(?=(?:<\|im_end\|>|$))",
    re.IGNORECASE | re.DOTALL,
)
CHAT_BLOCK_PATTERN = re.compile(
    r"<\|im_start\|>.*?<\|im_end\|>",
    re.IGNORECASE | re.DOTALL,
)
ROLE_PREFIX_PATTERN = re.compile(r"^(?:assistant|user)\b[:\s]*", re.IGNORECASE)


def sanitize_user_transcript(text: str) -> str:
    """
    Remove leaked chat-template markers and keep the latest user utterance.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    if "<|im_start|>" in cleaned or "<|im_end|>" in cleaned:
        user_blocks = USER_BLOCK_PATTERN.findall(cleaned)
        if user_blocks:
            cleaned = user_blocks[-1]
        else:
            cleaned = CHAT_BLOCK_PATTERN.sub(" ", cleaned)

    cleaned = cleaned.replace("<|im_start|>", " ").replace("<|im_end|>", " ")
    cleaned = ROLE_PREFIX_PATTERN.sub("", cleaned)
    cleaned = cleaned.strip().strip("\"'`{}[]()")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()
