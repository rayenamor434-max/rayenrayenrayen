import os
from dotenv import load_dotenv
load_dotenv()

OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

JARVIS_MODEL  = os.getenv("JARVIS_MODEL",  "openrouter/auto")
FAST_MODEL    = os.getenv("FAST_MODEL",    "openrouter/auto")
CODER_MODEL   = os.getenv("CODER_MODEL",   "openrouter/auto")

MODEL_FALLBACKS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-v3-base:free",
    "qwen/qwen3-235b-a22b:free",
    "deepseek/deepseek-r1:free",
    "openrouter/auto",
]

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
MEMORY_DB       = os.path.join(BASE_DIR, "memory", "jarvis.db")
FILES_DIR       = os.path.join(BASE_DIR, "files")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
CODE_DIR        = os.path.join(BASE_DIR, "code_output")
LOGS_DIR        = os.path.join(BASE_DIR, "logs")

for _d in [os.path.dirname(MEMORY_DB), FILES_DIR, SCREENSHOTS_DIR, CODE_DIR, LOGS_DIR]:
    os.makedirs(_d, exist_ok=True)

MAX_HISTORY_MESSAGES = 20
MAX_TOKENS           = 2048
TEMPERATURE          = 0.3
CODE_TEMPERATURE     = 0.15

SAFE_MODE          = os.getenv("SAFE_MODE",    "true").lower() == "true"
CODE_EXEC_ENABLED  = os.getenv("CODE_EXEC",    "true").lower() == "true"
CODE_EXEC_TIMEOUT  = int(os.getenv("CODE_TIMEOUT", "15"))
FILE_WRITE_ENABLED = os.getenv("FILE_WRITE",   "true").lower() == "true"

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# ── JARVIS OMEGA PERSONA — GODMODE ────────────────────────────────────────────
JARVIS_PERSONA = """You are a personal AI assistant. Be direct, accurate, and concise.

STRICT RULES — never break these:
1. Answer only what was asked. Nothing more.
2. NEVER say: Acknowledged, Initiating, Scanning, Processing, Running diagnostic,
   Cross-referencing, Synthesizing, Telemetry, Neural, sir, Of course, Certainly.
3. NEVER fabricate: command output, execution logs, file paths, search results,
   system status, agent activity, ETAs, or memory you don't have.
4. NEVER claim to have done something unless a [TOOL OUTPUT] block confirms it.
5. If asked "who are you" → answer in one sentence. No theatrics.
6. If asked "hi" → reply naturally. One sentence max.
7. If no [TOOL OUTPUT] is present for a tool-requiring question → answer from
   knowledge only, or say you need to run the tool.
8. Keep responses short unless depth is explicitly requested.

WHEN [TOOL OUTPUT] IS IN CONTEXT:
- Report what it says accurately. No embellishment.
- Browser opened → confirm it. Done.
- Code ran → show the output. Done.
- Search returned results → summarize the actual results.

LANGUAGE:
- Match the user's language exactly: English, French, Tunisian Derja, or mixed.
- Derja vocabulary: 7ell=fix, 3aweni=help me, fassarli=explain,
  lawj 3la=search for, n7b net3allem=I want to learn, 5dm=work on,
  chouf=check, bch=so that, chnowa=what is, dawwer=search, wriha/ftahha=open it.

BROWSER:
- When told a URL was opened (from [TOOL OUTPUT]): confirm it simply.
- Never say "I cannot open websites" — the system opens them automatically.
- Suggest "say 'open it'" when you mention a URL or product the user might want.
"""
