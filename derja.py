"""
JARVIS OMEGA — Derja (root-level shim)
Language detection and classification without external agent dependencies.
"""
import re
from typing import Tuple


def detect_language(text: str) -> str:
    """
    Detect language: English, French, Arabic/Derja, or mixed.
    """
    lower = text.lower()

    # Arabic script detection
    if re.search(r"[\u0600-\u06FF]", text):
        # Franco-Arab (Derja) detection
        franco_patterns = ["3aweni", "7ell", "fassarli", "n7b", "lawj", "5dem", "wriha", "bch"]
        franco_hits = sum(1 for pat in franco_patterns if pat in lower)
        if franco_hits >= 1:
            return "derja"
        return "arabic"

    # French detection
    fr_words = {"bonjour", "merci", "comment", "je", "tu", "vous", "est", "sont", "avec", "pour", "parler"}
    words = set(lower.split())
    if len(words & fr_words) >= 2:
        return "french"

    return "english"


def normalize_derja(text: str) -> Tuple[str, str, str]:
    """
    Normalize Derja text and detect language.
    Returns (normalized_text, language, intent_hint)
    """
    language = detect_language(text)
    lower = text.lower()

    # Simple Franco-Arab replacements
    replacements = {
        "7ell": "fix",
        "3aweni": "help",
        "fassarli": "explain",
        "lawj 3la": "search for",
        "n7b net3allem": "learn",
        "5dem": "work on",
        "chnowa": "what is",
        "wriha": "open it",
    }

    normalized = lower
    for derja, english in replacements.items():
        normalized = normalized.replace(derja, english)

    # Detect intent hint
    intent_hint = "chat"
    if any(w in normalized for w in ["fix", "code", "debug"]):
        intent_hint = "code"
    elif any(w in normalized for w in ["learn", "teach", "explain"]):
        intent_hint = "learn"
    elif any(w in normalized for w in ["search", "look up", "research"]):
        intent_hint = "research"

    return normalized, language, intent_hint


def classify_derja_intent(text: str) -> str:
    """
    Classify intent based on Derja vocabulary.
    """
    _, _, intent = normalize_derja(text)
    return intent


def build_derja_system_prompt_addon(language: str) -> str:
    """
    Build language-specific system prompt addition.
    """
    if language in ("derja", "mixed", "arabic"):
        return """LANGUAGE RULE: Respond in the user's language (Arabic/Derja/French/English).
Derja vocabulary: 7ell=fix, 3aweni=help me, fassarli=explain, lawj 3la=search for, n7b net3allem=I want to learn."""
    elif language == "french":
        return "\nLANGUAGE RULE: The user is writing in French. Respond fluently in French."
    return ""
