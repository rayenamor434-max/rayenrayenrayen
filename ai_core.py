"""
JARVIS OMEGA — AI Core
Handles: chat, streaming, quick queries, tool registration, intent classification.

CRITICAL FIX: Removed _maybe_run_tools() which made a second LLM call to
"decide" which tool to use. Free models returned theatrical garbage instead of
NO_TOOL, injecting fake "TOOL RESULTS" into every response. Tool routing is
now done deterministically in the orchestrator based on intent classification.
"""
import re
import time
from typing import Dict, Any, Optional, List, Iterator, Callable

from openai import OpenAI, APIConnectionError, RateLimitError, APIStatusError

from config import (
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    JARVIS_MODEL, FAST_MODEL, MODEL_FALLBACKS,
    MAX_TOKENS, TEMPERATURE, MAX_HISTORY_MESSAGES,
    JARVIS_PERSONA,
)

# ── Intent classification ─────────────────────────────────────────────────────
# DIRECT_COMMANDS: matched first, trigger tool execution without LLM involvement.
# A message matching any of these goes straight to the automation layer.
DIRECT_COMMANDS = {
    "browser": [
        "open ", "launch ", "go to ", "navigate to ", "visit ",
        "youtube", "google.com", "github.com", "twitter", "reddit",
        "stackoverflow", "wikipedia.org", "facebook", "instagram",
        "linkedin", "gmail", "docs.google", "drive.google",
    ],
    "screenshot": ["screenshot", "capture screen", "sawwer"],
    "system":     ["cpu usage", "ram usage", "disk usage", "system status",
                   "battery status", "running processes"],
}

INTENT_KEYWORDS = {
    # English
    "code":     ["write code", "python script", "write a function", "implement",
                 "write a program", "algorithm", "debug this", "fix this code",
                 "execute this", "run this code",
                 "5dm", "5dem", "ikteb code"],
    "research": ["search for", "look up", "what is", "who is", "when did",
                 "tell me about", "find information", "wikipedia", "latest news",
                 "lawj 3la", "3mel research", "chnowa", "chnou"],
    "weather":  ["weather in", "temperature in", "will it rain", "forecast for"],
    "file":     ["read file", "open file", "write to file", "save to file",
                 "list files", "show me the file", "create a file"],
    "system":   ["system info", "hardware info", "check performance",
                 "what processes", "how much ram", "how much cpu"],
    "task":     ["add task", "create task", "new todo", "remind me to",
                 "add to my list", "task list"],
    "plan":     ["make a plan", "create a roadmap", "break down", "plan for",
                 "project plan", "steps to"],
    "learn":    ["i want to learn", "help me learn", "teach me", "study",
                 "explain how", "tutorial on", "how does", "how do i",
                 "n7b net3allem", "3aweni bch", "fassarli", "shr7li", "net3allem"],
    "memory":   ["remember that", "store this", "don't forget", "note that",
                 "save this", "keep track of"],
    "project":  ["scan this project", "analyze this folder", "run the project",
                 "debug the project", "check the code"],
    "fix":      ["7ell", "3addel", "fix the", "repair"],
}

# Trivial messages that need no memory context and no tools
_TRIVIAL = {
    "hi", "hello", "hey", "ok", "okay", "yes", "no", "sure", "thanks",
    "thank you", "bye", "good", "cool", "nice", "great", "alright",
    "yep", "nope", "got it", "perfect", "fine", "k", "lol", "haha",
    "ahlan", "salam", "mrigel", "barka", "yezzi", "waw", "oui", "non",
    "merci", "d'accord", "bien",
}


class AICore:
    def __init__(self):
        self.current_model = JARVIS_MODEL
        self._tool_handlers: Dict[str, Callable] = {}
        self._client = OpenAI(
            api_key=OPENROUTER_API_KEY or "no-key",
            base_url=OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "https://jarvis-omega.local",
                "X-Title": "JARVIS OMEGA",
            },
        )

    def register_tools(self, tools: Dict[str, Callable]):
        self._tool_handlers.update(tools)

    def is_ready(self) -> bool:
        return bool(OPENROUTER_API_KEY)

    # ── Intent ────────────────────────────────────────────────────────────────

    def classify_intent(self, message: str) -> str:
        """
        Two-pass deterministic classification. No LLM call.
        Pass 1: DIRECT_COMMANDS — unambiguous single-action phrases.
        Pass 2: INTENT_KEYWORDS — scored keyword matching.
        """
        lower = message.lower().strip()

        # Pass 1: direct commands
        for intent, patterns in DIRECT_COMMANDS.items():
            for pat in patterns:
                if lower.startswith(pat) or (len(pat) > 5 and pat in lower):
                    return intent

        # Pass 2: keyword scoring
        scores: Dict[str, int] = {}
        for intent, keywords in INTENT_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    scores[intent] = scores.get(intent, 0) + 1

        return max(scores, key=scores.get) if scores else "chat"

    def is_trivial(self, message: str) -> bool:
        """True for short greetings and acks that need no memory or tool context."""
        cleaned = message.lower().strip().rstrip("!?.")
        return cleaned in _TRIVIAL or (len(cleaned) <= 4 and cleaned.isalpha())

    # ── Main Chat ──────────────────────────────────────────────────────────────

    def chat(
        self,
        user_message: str,
        session_id: str = "default",
        history: Optional[List[Dict]] = None,
        memory_context: str = "",
        system_extra: str = "",
        use_tools: bool = False,
        tool_result: str = "",      # pre-computed tool result from orchestrator
    ) -> Dict:
        """
        Chat with the LLM.
        tool_result: already-executed tool output injected as context.
                     The LLM should REPORT it, not re-run it.
        use_tools is now ignored (kept for API compat) — tool routing is
        done deterministically in orchestrator before calling chat().
        """
        effective_context = memory_context
        if tool_result:
            effective_context = (memory_context + "\n\n[TOOL OUTPUT]\n" + tool_result).strip()

        messages = self._build_messages(user_message, history, effective_context, system_extra)
        raw, model, tokens = self._call_api(messages)
        response = raw.strip() if raw else "I couldn't generate a response."

        return {
            "response"  : response,
            "tool_calls": [{"tool": "external", "result": tool_result}] if tool_result else [],
            "model_used": model,
            "tokens"    : tokens,
        }

    # ── Streaming ─────────────────────────────────────────────────────────────

    def stream_chat(
        self,
        user_message: str,
        history: Optional[List[Dict]] = None,
        memory_context: str = "",
        system_extra: str = "",
        tool_result: str = "",
    ) -> Iterator[str]:
        effective_context = memory_context
        if tool_result:
            effective_context = (memory_context + "\n\n[TOOL OUTPUT]\n" + tool_result).strip()
        messages = self._build_messages(user_message, history, effective_context, system_extra)
        yield from self._stream_api(messages)

    # ── Quick query ───────────────────────────────────────────────────────────

    def quick(self, prompt: str, system: str = "") -> str:
        msgs = [
            {"role": "system", "content": system or "You are a helpful AI assistant."},
            {"role": "user",   "content": prompt},
        ]
        raw, _, _ = self._call_api(msgs, model=FAST_MODEL, max_tokens=1024)
        return raw.strip() if raw else ""

    # ── Private ───────────────────────────────────────────────────────────────

    def _build_messages(
        self,
        user_message: str,
        history: Optional[List[Dict]],
        memory_context: str,
        system_extra: str,
    ) -> List[Dict]:
        system_content = JARVIS_PERSONA
        if memory_context:
            system_content += f"\n\n[MEMORY]\n{memory_context[:1200]}"
        if system_extra:
            system_content += f"\n\n{system_extra[:600]}"

        messages = [{"role": "system", "content": system_content}]
        if history:
            for msg in history[-(MAX_HISTORY_MESSAGES * 2):]:
                role    = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": str(content)})

        messages.append({"role": "user", "content": user_message})
        return messages

    def _call_api(self, messages, model=None, max_tokens=None, temperature=None):
        model       = model or self.current_model
        max_tokens  = max_tokens or MAX_TOKENS
        temperature = temperature if temperature is not None else TEMPERATURE

        if model in MODEL_FALLBACKS:
            start         = MODEL_FALLBACKS.index(model)
            models_to_try = MODEL_FALLBACKS[start:]
        else:
            models_to_try = [model] + MODEL_FALLBACKS

        for attempt_model in models_to_try:
            try:
                resp = self._client.chat.completions.create(
                    model=attempt_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                content = resp.choices[0].message.content or ""
                tokens  = resp.usage.total_tokens if resp.usage else 0
                self.current_model = attempt_model
                return content, attempt_model, tokens
            except RateLimitError:
                time.sleep(1); continue
            except APIConnectionError as e:
                return f"Connection error: {e}", attempt_model, 0
            except APIStatusError as e:
                if e.status_code in (429, 503):
                    time.sleep(1); continue
                continue
            except Exception:
                continue

        return (
            "Cannot reach the AI service. Check OPENROUTER_API_KEY and internet.",
            model, 0
        )

    def _stream_api(self, messages) -> Iterator[str]:
        if self.current_model in MODEL_FALLBACKS:
            start = MODEL_FALLBACKS.index(self.current_model)
            models_to_try = MODEL_FALLBACKS[start:]
        else:
            models_to_try = [self.current_model] + MODEL_FALLBACKS

        for attempt_model in models_to_try:
            try:
                stream = self._client.chat.completions.create(
                    model=attempt_model,
                    messages=messages,
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
                self.current_model = attempt_model
                return
            except (RateLimitError, APIStatusError):
                time.sleep(1)
                continue
            except Exception as e:
                yield f"\n[Stream error: {e}]"
                return
        yield "\n[All models unavailable. Check OPENROUTER_API_KEY and internet connection.]"
