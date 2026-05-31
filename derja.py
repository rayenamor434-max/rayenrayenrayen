"""
JARVIS OMEGA — Derja (root-level shim)
Exports the 4 functions expected by orchestrator.py,
adapting the richer tools/derja.py API where signatures differ.
"""
from tools.derja import (
    detect_language,
    normalize_derja as _normalize_derja,
    build_derja_system_addendum,
    DERJA_VOCAB,
    DERJA_PHRASES,
)
import re
from typing import Tuple


def normalize_derja(text: str) -> Tuple[str, str]:
    """
    Adapter for orchestrator.py which expects (normalized_text, language).
    tools/derja.normalize_derja returns (text, lang, intent) — we drop intent here.
    """
    normalized, lang, _intent = _normalize_derja(text)
    return normalized, lang


def classify_derja_intent(text: str) -> str:
    """
    Classify the primary intent of a message using Derja vocabulary and phrases.
    Returns an intent string like 'code', 'fix', 'learn', 'research', 'chat', etc.
    """
    lower = text.lower().strip()

    # Check multi-word phrases first (higher precision)
    for pattern, intent in DERJA_PHRASES:
        if re.search(pattern, lower):
            return intent

    # Single-word vocab lookup
    parts = lower.split()
    for word in parts:
        clean = re.sub(r"[^\w3245678]", "", word)
        if clean in DERJA_VOCAB:
            vocab_intent = DERJA_VOCAB[clean].get("intent")
            if vocab_intent:
                return vocab_intent

    return "chat"


def build_derja_system_prompt_addon(language: str) -> str:
    """
    Build a language-specific system prompt addition.
    For Derja/mixed/Arabic: return the full Derja addendum.
    For French: return a French-mode instruction.
    For English: return empty string.
    """
    if language in ("derja", "mixed", "arabic"):
        return build_derja_system_addendum()
    elif language == "french":
        return "\nLANGUAGE RULE: The user is writing in French. Respond fluently in French."
    return ""


# Re-export detect_language so orchestrator can also use it if needed
__all__ = [
    "detect_language",
    "normalize_derja",
    "classify_derja_intent",
    "build_derja_system_prompt_addon",
]
