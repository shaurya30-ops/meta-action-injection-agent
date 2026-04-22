from __future__ import annotations

import re
import unicodedata


_MOJIBAKE_MARKERS = ("à¤", "à¥", "Ã", "â€™", "â€œ", "â€", "ðŸ")


def _repair_mojibake(text: str) -> str:
    if not text:
        return text
    if not any(marker in text for marker in _MOJIBAKE_MARKERS):
        return text

    original_marker_count = sum(marker in text for marker in _MOJIBAKE_MARKERS)
    for encoding in ("latin-1", "cp1252"):
        try:
            repaired = text.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue

        repaired_marker_count = sum(marker in repaired for marker in _MOJIBAKE_MARKERS)
        if repaired_marker_count < original_marker_count:
            return repaired

    return text


_PUNCT_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
    }
)


def normalize_transcript(text: str) -> str:
    compact = _repair_mojibake(text or "")
    compact = unicodedata.normalize("NFKC", compact).translate(_PUNCT_TRANSLATION)
    compact = compact.replace("\r", " ").replace("\n", " ")
    compact = re.sub(r"\s+", " ", compact).strip()
    return compact.casefold()


__all__ = ["normalize_transcript"]
