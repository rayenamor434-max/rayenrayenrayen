cat > /home/claude/jarvis_omega_v4/orchestrator.py << 'PYEOF'
"""
OMEGA — Orchestrator
Deterministic routing. No LLM used to decide tool calls.
"""
from typing import Dict, Optional, Iterator, Tuple
from datetime import datetime
import re as _re
import urllib.parse as _urlparse

from ai_core import AICore
from agents.memory import MemorySystem
from planner import Planner
from automation import AutomationEngine
from agents.research import ResearchAgent
from agents.coder import CodingAgent
from files import FilesAgent
from system_monitor import SystemMonitor
from derja import detect_language, classify_derja_intent, normalize_derja, build_derja_system_prompt_addon
from learning import LearningAgent
from agents.browser import BrowserAgent

# ── URL/Platform routing tables ───────────────────────────────────────────────
_PLATFORM_BASES = {
    "youtube"    : "https://www.youtube.com/results?search_query=",
    "spotify"    : "https://open.spotify.com/search/",
    "soundcloud" : "https://soundcloud.com/search?q=",
    "deezer"     : "https://www.deezer.com/search/",
    "google"     : "https://www.google.com/search?q=",
    "amazon"     : "https://www.amazon.com/s?k=",
    "wikipedia"  : "https://en.wikipedia.org/wiki/Special:Search?search=",
    "github"     : "https://github.com/search?q=",
    "linkedin"   : "https://www.linkedin.com/search/results/all/?keywords=",
    "twitter"    : "https://twitter.com/search?q=",
    "reddit"     : "https://www.reddit.com/search/?q=",
    "ebay"       : "https://www.ebay.com/sch/i.html?_nkw=",
    "bing"       : "https://www.bing.com/search?q=",
    "duckduckgo" : "https://duckduckgo.com/?q=",
}

_SITES = {
    "youtube"      : "https://youtube.com",
    "google"       : "https://google.com",
    "github"       : "https://github.com",
    "twitter"      : "https://twitter.com",
    "reddit"       : "https://reddit.com",
    "stackoverflow": "https://stackoverflow.com",
    "wikipedia"    : "https://wikipedia.org",
    "facebook"     : "https://facebook.com",
    "instagram"    : "https://instagram.com",
    "linkedin"     : "https://linkedin.com",
    "gmail"        : "https://mail.google.com",
    "docs"         : "https://docs.google.com",
    "drive"        : "https://drive.google.com",
    "openai"       : "https://openai.com",
    "spotify"      : "https://open.spotify.com",
    "soundcloud"   : "https://soundcloud.com",
    "amazon"       : "https://amazon.com",
    "ebay"         : "https://ebay.com",
    "deezer"       : "https://deezer.com",
    "tiktok"       : "https://tiktok.com",
    "twitch"       : "https://twitch.tv",
    "discord"      : "https://discord.com",
    "notion"       : "https://notion.so",
    "figma"        : "https://figma.com",
}

_OPEN_PREFIXES = ("open ", "launch ", "go to ", "navigate to ", "visit ")

_PLATFORM_PAT    = "|".join(_re.escape(k) for k in _PLATFORM_BASES)
_PLAY_PLATFORM_RE = _re.compile(
    r'^(?:open|play|search|listen\s+to|find|look\s+up)\s+(.+?)\s+(?:in|on|at)\s+(' + _PLATFORM_PAT + r')',
    _re.I
)
_PLAY_RE   = _re.compile(r'^(?:play|listen\s+to)\s+(.+)', _re.I)
_OPEN_IT_RE = _re.compile(
    r'^(?:open|go\s+to|take\s+me\s+to|show\s+me|navigate\s+to|launch)\s+'
    r'(?:it|that|the\s+(?:link|url|site|page|result|video|song|track)|there)'
    r'(?:\s+(?:in|on|at|with)\s+(' + _PLATFORM_PAT + r'))?',
    _re.I
)

_DERJA_OPEN   = {"7ollha","7ol","7olha","wriha","ftahha","shottha","shotha","3ardhali"}
_DERJA_SEARCH = {"dawwer","dowwer"}
_DERJA_PLAY   = {"chaghghel","shagghel","chaghel","shaghel"}


class Orchestrator:
    def __init__(self):
        self.ai       = AICore()
        self.memory   = MemorySystem()
        self.planner  = Planner(self.memory, self.ai)
        self.auto     = AutomationEngine()
        self.research = ResearchAgent()
        self.coder    = CodingAgent()
        self.files    = FilesAgent()
        self.sysmon   = SystemMonitor()
        self.learning = LearningAgent(self.memory, self.ai)
        self.browser  = BrowserAgent()

    # ── Public ────────────────────────────────────────────────────────────────

    def process(self, user_message: str, session_id: str = "default",
                context: dict = None) -> Dict:
        # 1. Direct command fast-path (no LLM)
        direct = self._direct_execute(user_message, context)
        if direct is not None:
            self.memory.add_message(session_id, "user",      user_message, direct["intent"])
            self.memory.add_message(session_id, "assistant", direct["response"])
            return {**direct, "session_id": session_id}

        # 2. Normalise language
        normalized, lang = normalize_derja(user_message)
        lang_addon        = build_derja_system_prompt_addon(lang)
        derja_intent      = classify_derja_intent(user_message)
        intent = derja_intent if derja_intent != "chat" else self.ai.classify_intent(user_message)

        # 3. Trivial messages — skip memory + tools
        is_trivial  = self.ai.is_trivial(user_message)
        mem_context = "" if is_trivial else self.memory.get_context(limit=15)
        history     = self.memory.get_history(session_id, limit=4 if is_trivial else 14)

        # 4. Pre-execute deterministic tool
        tool_result, tool_log, system_extra, first_url = ("", [], lang_addon, None) \
            if is_trivial else \
            self._route_tool(intent, normalized, user_message, lang_addon)

        # 5. LLM
        result = self.ai.chat(
            user_message  = normalized,
            session_id    = session_id,
            history       = history,
            memory_context= mem_context,
            system_extra  = system_extra,
            tool_result   = tool_result,
        )

        # 6. Persist
        learned = self.memory.auto_learn(user_message, result["response"], lang)
        self.memory.add_message(session_id, "user",      user_message, intent, lang)
        self.memory.add_message(session_id, "assistant", result["response"])
        if tool_log:
            self.memory.log_event("tool_use", user_message[:80],
                                  {"tools": [t["tool"] for t in tool_log]})

        return {
            "response"        : result["response"],
            "intent"          : intent,
            "language"        : lang,
            "tool_calls"      : tool_log,
            "memory_learned"  : learned,
            "model_used"      : result["model_used"],
            "tokens"          : result["tokens"],
            "session_id"      : session_id,
            "first_result_url": first_url,
        }

    def stream(self, user_message: str, session_id: str = "default",
               context: dict = None) -> Iterator[str]:
        direct = self._direct_execute(user_message, context)
        if direct is not None:
            self.memory.add_message(session_id, "user",      user_message, direct["intent"])
            self.memory.add_message(session_id, "assistant", direct["response"])
            yield direct["response"]
            if direct.get("frontend_action"):
                import json
                yield f"\n\x00OMEGA_ACTION:{json.dumps(direct['frontend_action'])}"
            return

        normalized, lang  = normalize_derja(user_message)
        lang_addon         = build_derja_system_prompt_addon(lang)
        intent             = self.ai.classify_intent(user_message)
        is_trivial         = self.ai.is_trivial(user_message)
        mem_context        = "" if is_trivial else self.memory.get_context(limit=15)
        history            = self.memory.get_history(session_id, limit=4 if is_trivial else 14)

        tool_result, tool_log, system_extra, _ = ("", [], lang_addon, None) \
            if is_trivial else \
            self._route_tool(intent, normalized, user_message, lang_addon)

        full = ""
        for chunk in self.ai.stream_chat(normalized, history, mem_context,
                                          system_extra, tool_result=tool_result):
            full += chunk
            yield chunk

        self.memory.add_message(session_id, "user",      user_message)
        self.memory.add_message(session_id, "assistant", full)
        self.memory.auto_learn(user_message, full, lang)

    # ── Direct execution ──────────────────────────────────────────────────────

    def _direct_execute(self, message: str, context: dict = None) -> Optional[Dict]:
        lower   = message.lower().strip()
        context = context or {}

        last_url    = context.get("last_url", "")
        last_song   = context.get("last_song", "")
        last_artist = context.get("last_artist", "")
        last_topic  = context.get("last_topic", "")
        last_domain = context.get("last_domain", "") or self._domain(last_url)

        # screenshot
        if lower in ("screenshot", "sawwer", "take screenshot", "capture screen"):
            r = self.auto.take_screenshot()
            return self._wrap(r, "screenshot")

        # Derja open words
        if lower in _DERJA_OPEN:
            target = last_url or (
                (_PLATFORM_BASES["youtube"] + _urlparse.quote_plus(last_song or last_artist))
                if (last_song or last_artist) else
                (_PLATFORM_BASES["google"] + _urlparse.quote_plus(last_topic))
                if last_topic else None
            )
            if target:
                label = last_domain or last_topic or "page"
                return {**self._wrap(f"Opening {label}…", "browser"),
                        "frontend_action": {"type": "open_url", "url": target, "label": label}}
            return None

        # Derja search
        if lower in _DERJA_SEARCH or lower.startswith("dawwer "):
            q = lower.replace("dawwer", "").strip() or last_topic
            if q:
                url = _PLATFORM_BASES["google"] + _urlparse.quote_plus(q)
                return {**self._wrap(f"Searching: {q}", "browser"),
                        "frontend_action": {"type": "open_url", "url": url, "label": q}}

        # Derja play
        if lower in _DERJA_PLAY:
            q = last_song or last_artist or last_topic
            if q:
                url = _PLATFORM_BASES["youtube"] + _urlparse.quote_plus(q)
                return {**self._wrap(f"Playing {q} on YouTube…", "browser"),
                        "frontend_action": {"type": "open_url", "url": url, "label": q}}

        # Named site
        for site, url in _SITES.items():
            if lower == site or f"open {site}" in lower or f"launch {site}" in lower:
                return {**self._wrap(f"Opening {site.title()}…", "browser"),
                        "frontend_action": {"type": "open_url", "url": url, "label": site.title()}}

        # Explicit URL
        for prefix in _OPEN_PREFIXES:
            if lower.startswith(prefix):
                target = message[len(prefix):].strip()
                if target and ("." in target or target.startswith("http")):
                    if not target.startswith("http"):
                        target = "https://" + target
                    label = self._domain(target)
                    return {**self._wrap(f"Opening {label}…", "browser"),
                            "frontend_action": {"type": "open_url", "url": target, "label": label}}

        # "play X in/on PLATFORM"
        m = _PLAY_PLATFORM_RE.match(lower)
        if m:
            query, platform = m.group(1).strip(), m.group(2).lower()
            base = _PLATFORM_BASES.get(platform, _PLATFORM_BASES["google"])
            url  = base + _urlparse.quote_plus(query)
            return {**self._wrap(f"Opening {query} on {platform.title()}…", "browser"),
                    "frontend_action": {"type": "open_url", "url": url,
                                        "label": f"{query} on {platform.title()}"}}

        # "play X" → YouTube
        m = _PLAY_RE.match(lower)
        if m:
            query = m.group(1).strip()
            url   = _PLATFORM_BASES["youtube"] + _urlparse.quote_plus(query)
            return {**self._wrap(f"Playing {query} on YouTube…", "browser"),
                    "frontend_action": {"type": "open_url", "url": url,
                                        "label": f"{query} on YouTube"}}

        # Pronoun resolution: "open it"
        m = _OPEN_IT_RE.match(lower)
        if m:
            ep = (m.group(1) or "").lower()
            if ep:
                base  = _PLATFORM_BASES.get(ep)
                query = last_song or last_artist or last_topic
                if base and query:
                    url = base + _urlparse.quote_plus(query)
                    return {**self._wrap(f"Opening {query} on {ep.title()}…", "browser"),
                            "frontend_action": {"type": "open_url", "url": url,
                                                "label": f"{query} on {ep.title()}"}}
                home = _SITES.get(ep, "https://" + ep + ".com")
                return {**self._wrap(f"Opening {ep.title()}…", "browser"),
                        "frontend_action": {"type": "open_url", "url": home, "label": ep.title()}}
            if last_url:
                return {**self._wrap(f"Opening {last_domain or last_url}…", "browser"),
                        "frontend_action": {"type": "open_url", "url": last_url,
                                            "label": last_domain or last_url}}
            if last_song or last_artist:
                q   = last_song or last_artist
                url = _PLATFORM_BASES["youtube"] + _urlparse.quote_plus(q)
                return {**self._wrap(f"Opening {q} on YouTube…", "browser"),
                        "frontend_action": {"type": "open_url", "url": url,
                                            "label": f"{q} on YouTube"}}
            if last_topic:
                url = _PLATFORM_BASES["google"] + _urlparse.quote_plus(last_topic)
                return {**self._wrap(f"Searching {last_topic}…", "browser"),
                        "frontend_action": {"type": "open_url", "url": url, "label": last_topic}}
            return {**self._wrap("Opening Google…", "browser"),
                    "frontend_action": {"type": "open_url", "url": "https://google.com", "label": "Google"}}

        return None

    # ── Tool routing ──────────────────────────────────────────────────────────

    def _route_tool(self, intent: str, normalized: str, original: str,
                    lang_addon: str) -> Tuple[str, list, str, Optional[str]]:
        result, log, extra, url = "", [], lang_addon, None

        if intent == "research":
            query = self._xq(normalized)
            data  = self.research.search(query)
            result = self.research.format_search_results(data)
            log    = [{"tool": "web_search", "args": {"query": query}}]
            if isinstance(data, dict):
                rs  = data.get("results") or []
                url = rs[0].get("url") if rs and isinstance(rs[0], dict) else None

        elif intent == "weather":
            city   = self._xcity(normalized)
            result = self.research.weather(city)
            log    = [{"tool": "weather", "args": {"city": city}}]

        elif intent == "system":
            report = self.sysmon.get_full_report()
            result = self.sysmon.format_report(report)
            log    = [{"tool": "system_status"}]

        elif intent == "learn":
            topic  = self.learning.detect_topic_from_message(original)
            rdmap  = self.learning.get_roadmap(topic)
            extra  = lang_addon + self.learning.build_study_context(topic)
            if rdmap:
                result = self.learning.format_roadmap(topic, rdmap)
                log    = [{"tool": "learning", "args": {"topic": topic}}]

        elif intent in ("code", "fix"):
            code = self.coder.extract_code_from_message(normalized)
            if code:
                exec_r = self.coder.execute_raw(code)
                result = self.coder.format_result(exec_r)
                log    = [{"tool": "execute_python"}]
                self.memory.log_event("code_execution", normalized[:80],
                                      {"success": exec_r["success"]})

        elif intent == "memory":
            fact = normalized.replace("remember", "").replace("store this", "").strip()
            if fact:
                mid    = self.memory.add_memory(fact, category="user_request", importance=3)
                result = f'Stored: "{fact[:100]}"'
                log    = [{"tool": "remember"}]

        elif intent == "task":
            tasks = self.memory.get_tasks(status="pending")
            if tasks:
                lines  = "\n".join(f"- [{t['priority']}] #{t['id']} {t['title']}" for t in tasks[:10])
                result = f"Pending tasks:\n{lines}"
                log    = [{"tool": "task_list"}]

        elif intent == "project":
            path = self._xpath(normalized)
            if path:
                scan = self.files.scan_project(path)
                if "error" not in scan:
                    lines  = [f"Project: {scan['folder']}", f"Type: {scan['project_type']}",
                               f"Files: {scan['total_files']}"]
                    result = "\n".join(lines)
                    log    = [{"tool": "scan_project", "args": {"path": path}}]
                    self.memory.log_event("project_scanned", path, {"type": scan["project_type"]})

        return result, log, extra, url

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _wrap(msg: str, intent: str) -> Dict:
        return {"response": msg, "intent": intent, "language": "english",
                "tool_calls": [{"tool": intent}], "memory_learned": False,
                "model_used": "direct", "tokens": 0}

    @staticmethod
    def _domain(url: str) -> str:
        try:
            from urllib.parse import urlparse
            h = urlparse(url).netloc
            return h.lstrip("www.") if h else url[:40]
        except Exception:
            return url[:40]

    @staticmethod
    def _xq(msg: str) -> str:
        for p in ("search for ", "look up ", "find ", "what is ", "who is ",
                  "lawj 3la ", "3mel research ", "chnowa ", "tell me about "):
            if msg.lower().startswith(p):
                return msg[len(p):].strip()
        return msg.strip()

    @staticmethod
    def _xcity(msg: str) -> str:
        for phrase in ("weather in ", "weather for ", "temperature in "):
            if phrase in msg.lower():
                i = msg.lower().index(phrase) + len(phrase)
                return msg[i:].split("?")[0].strip()
        return msg.strip()

    @staticmethod
    def _xpath(msg: str) -> str:
        import re
        m = re.search(r'[A-Za-z]:\\[^\s"\']+|/[^\s"\']{3,}|\.{0,2}/[^\s"\']{2,}', msg)
        return m.group(0) if m else ""

    # ── Pass-throughs ─────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        s = self.memory.get_stats()
        s["ai_ready"] = self.ai.is_ready()
        s["model"]    = self.ai.current_model
        s["tools"]    = 12
        return s

    def generate_plan(self, goal):    return self.planner.ai_breakdown(goal)
    def get_memories(self):           return self.memory.get_all_memories()
    def get_recent_events(self, n=20): return self.memory.get_recent_events(n)
    def clear_history(self, sid):     self.memory.clear_history(sid)
    def delete_task(self, tid):       return self.memory.delete_task(tid)
    def update_task(self, tid, **kw): return self.memory.update_task(tid, **kw)
    def search_memories(self, q):     return self.memory.search_memories(q)