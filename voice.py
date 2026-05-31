"""
OMEGA — Voice Agent
Natural text-to-speech using Microsoft Edge TTS (edge-tts).
Streams audio directly to the browser. No permanent MP3 files stored.
"""
import asyncio
import os
import re
import tempfile
from typing import AsyncIterator

# ── Voice profiles ────────────────────────────────────────────────────────────
VOICES = {
    "en"   : "en-US-JennyNeural",      # natural female, US English
    "en-gb": "en-GB-SoniaNeural",       # UK female
    "ar"   : "ar-SA-ZariyahNeural",     # Arabic female
    "fr"   : "fr-FR-DeniseNeural",      # French female
    "derja": "ar-SA-ZariyahNeural",     # Tunisian → Arabic voice
}
DEFAULT_VOICE = "en-US-JennyNeural"

# Characters to strip before TTS (markdown, URLs, code blocks)
_CLEAN_RE = re.compile(
    r"```[\s\S]*?```"           # code blocks
    r"|`[^`]+`"                 # inline code
    r"|https?://\S+"            # URLs
    r"|\*\*([^*]+)\*\*"         # bold → keep text
    r"|\*([^*]+)\*"             # italic → keep text
    r"|#{1,6}\s"                # headings
    r"|\[([^\]]+)\]\([^)]+\)",  # markdown links → keep text
    re.S
)


def _clean_for_tts(text: str) -> str:
    """Strip markdown/code/URLs from text before speaking."""
    text = _CLEAN_RE.sub(
        lambda m: m.group(1) or m.group(2) or m.group(3) or "",
        text
    )
    text = re.sub(r"\s+", " ", text).strip()
    # Truncate very long responses (TTS of 2000+ chars is slow)
    return text[:800] if len(text) > 800 else text


def _detect_lang(text: str) -> str:
    """Detect language for voice selection."""
    # Arabic script
    if re.search(r"[\u0600-\u06FF]", text):
        return "ar"
    # Franco-Arab (Derja) detection
    franco_hits = sum(1 for pat in ["3aweni", "7ell", "fassarli", "n7b", "lawj", "5dem", "wriha"]
                      if pat in text.lower())
    if franco_hits >= 2:
        return "derja"
    # French
    fr_words = {"bonjour", "merci", "comment", "je", "tu", "vous", "est", "sont", "avec", "pour"}
    word_set = set(text.lower().split())
    if len(word_set & fr_words) >= 2:
        return "fr"
    return "en"


async def synthesize_stream(text: str, lang: str = None) -> AsyncIterator[bytes]:
    """
    Stream TTS audio bytes (MP3) for the given text.
    Use in a FastAPI StreamingResponse.
    No temp file created when streaming.
    """
    try:
        import edge_tts
    except ImportError:
        raise RuntimeError("edge-tts not installed. Run: pip install edge-tts")

    if not text.strip():
        return

    clean   = _clean_for_tts(text)
    if not clean:
        return

    lang_key = lang or _detect_lang(text)
    voice    = VOICES.get(lang_key, DEFAULT_VOICE)

    communicate = edge_tts.Communicate(clean, voice, rate="+0%", volume="+0%")
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            yield chunk["data"]


async def synthesize_to_bytes(text: str, lang: str = None) -> bytes:
    """Collect full TTS audio as bytes (for non-streaming use)."""
    chunks = []
    async for chunk in synthesize_stream(text, lang):
        chunks.append(chunk)
    return b"".join(chunks)


def is_available() -> bool:
    """Check if edge-tts is installed."""
    try:
        import edge_tts  # noqa
        return True
    except ImportError:
        return False


def list_voices() -> list:
    """Return available voice profiles."""
    return [
        {"lang": k, "voice": v, "label": v.split("-")[2] if "-" in v else v}
        for k, v in VOICES.items()
    ]
