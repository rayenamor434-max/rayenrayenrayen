"""
JARVIS OMEGA — Main Orchestrator
Routes user intents to appropriate handlers.
Manages memory, tools, LLM calls, and response synthesis.
"""
import asyncio
from typing import Dict, List, Optional, Iterator
from datetime import datetime

from config import SAFE_MODE
from ai_core import AICore
from automation import AutomationEngine
from browser import BrowserAgent
from executor import CodeExecutor
from files import FilesAgent
from learning import LearningAgent
from planner import Planner
from system_monitor import SystemMonitor
from derja import normalize_derja, classify_derja_intent, build_derja_system_prompt_addon, detect_language

try:
    from agents.memory import MemorySystem
except ImportError:
    # Fallback if agents/memory not available
    class MemorySystem:
        def __init__(self):
            self.sessions = {}
        def get_session_history(self, session_id: str) -> List[Dict]:
            return self.sessions.get(session_id, [])
        def add_to_history(self, session_id: str, role: str, content: str) -> None:
            if session_id not in self.sessions:
                self.sessions[session_id] = []
            self.sessions[session_id].append({"role": role, "content": content, "timestamp": datetime.now().isoformat()})
        def search_memories(self, query: str) -> List[Dict]:
            return []
        def get_all_memories(self) -> List[Dict]:
            return []
        def add_memory(self, content: str, category: str = "general", tags: Optional[List[str]] = None, importance: int = 2) -> int:
            return 1
        def delete_memory(self, memory_id: int) -> bool:
            return True
        def get_tasks(self, status: Optional[str] = None, project: Optional[str] = None) -> List[Dict]:
            return []
        def update_task(self, task_id: int, **kwargs) -> bool:
            return True
        def delete_task(self, task_id: int) -> bool:
            return True
        def add_task(self, title: str, description: str = "", priority: str = "normal", project: str = "inbox", due_date: Optional[str] = None) -> int:
            return 1
        def clear_history(self, session_id: str) -> None:
            if session_id in self.sessions:
                del self.sessions[session_id]
        def clear_all(self) -> None:
            self.sessions.clear()
        def log_event(self, event_type: str, description: str, metadata: Optional[Dict] = None) -> None:
            pass
        def task_summary(self) -> Dict:
            return {"total": 0, "pending": 0, "done": 0, "high_priority": 0}
        def get_all_learning(self) -> List[Dict]:
            return []
        def get_recent_events(self, limit: int = 30, event_type: Optional[str] = None) -> List[Dict]:
            return []
        def get_learning_session(self, topic: str) -> Optional[Dict]:
            return None
        def get_study_notes(self, topic: str) -> List[Dict]:
            return []

try:
    from agents.research import ResearchAgent
except ImportError:
    class ResearchAgent:
        def search(self, query: str) -> Dict:
            return {"results": []}
        def weather(self, location: str) -> Dict:
            return {"error": "Research agent not available"}
        def wikipedia(self, query: str) -> Dict:
            return {"error": "Research agent not available"}
        def format_search_results(self, data: Dict) -> str:
            return ""


class Orchestrator:
    """Main orchestration engine for JARVIS OMEGA."""

    def __init__(self):
        self.ai = AICore()
        self.auto = AutomationEngine()
        self.browser = BrowserAgent()
        self.coder = CodeExecutor()
        self.files = FilesAgent()
        self.learning = LearningAgent() if hasattr(self, '__init__') else None
        self.memory = MemorySystem()
        self.planner = Planner(self.memory, self.ai)
        self.sysmon = SystemMonitor()
        self.research = ResearchAgent()

    def process(self, user_message: str, session_id: str = "default", context: Optional[Dict] = None) -> Dict:
        """Main entry point for processing user messages."""
        context = context or {}

        # Normalize language (FIX: unpack 3 values, ignore intent_hint)
        normalized, language, _ = normalize_derja(user_message)
        system_addon = build_derja_system_prompt_addon(language)

        # Check if trivial (no processing needed)
        if self.ai.is_trivial(normalized):
            return {
                "response": self._trivial_response(normalized),
                "session_id": session_id,
                "model": self.ai.current_model,
            }

        # Get history
        history = self.memory.get_session_history(session_id)

        # Classify intent
        intent = self.ai.classify_intent(normalized)

        # Route to handler
        tool_result = self._route_intent(intent, normalized, session_id)

        # Call chat with tool result
        response = self.ai.chat(
            normalized,
            session_id=session_id,
            history=history,
            memory_context="",
            system_extra=system_addon,
            tool_result=tool_result,
        )

        # Store in history
        self.memory.add_to_history(session_id, "user", user_message)
        self.memory.add_to_history(session_id, "assistant", response["response"])

        return response

    def stream(self, user_message: str, session_id: str = "default", context: Optional[Dict] = None) -> Iterator[str]:
        """Stream response chunks."""
        context = context or {}
        # FIX: unpack 3 values, ignore intent_hint
        normalized, language, _ = normalize_derja(user_message)
        system_addon = build_derja_system_prompt_addon(language)
        history = self.memory.get_session_history(session_id)

        # Route to handler
        tool_result = self._route_intent(self.ai.classify_intent(normalized), normalized, session_id)

        # Stream
        for chunk in self.ai.stream_chat(
            normalized,
            history=history,
            memory_context="",
            system_extra=system_addon,
            tool_result=tool_result,
        ):
            yield chunk

        self.memory.add_to_history(session_id, "user", user_message)

    def generate_plan(self, goal: str) -> Dict:
        """Generate a plan for a goal."""
        return self.planner.ai_breakdown(goal)

    def get_stats(self) -> Dict:
        """Get system stats."""
        return {
            "ai_ready": self.ai.is_ready(),
            "automation": self.auto.is_ready(),
            "timestamp": datetime.now().isoformat(),
        }

    def _route_intent(self, intent: str, message: str, session_id: str) -> str:
        """Route message to appropriate handler and return tool result."""
        try:
            if intent == "browser":
                return self._handle_browser(message)
            elif intent == "screenshot":
                return self._handle_screenshot()
            elif intent == "system":
                return self._handle_system()
            elif intent == "file":
                return self._handle_file(message)
            elif intent == "code":
                return self._handle_code(message)
            elif intent == "research":
                return self._handle_research(message)
            elif intent == "learn":
                return self._handle_learning(message)
        except Exception as e:
            return f"Error: {str(e)}"
        return ""

    def _handle_browser(self, message: str) -> str:
        """Handle browser commands."""
        try:
            if any(word in message.lower() for word in ["open", "go to", "navigate", "visit"]):
                # Extract URL
                words = message.split()
                for i, word in enumerate(words):
                    if word.lower() in ["open", "go", "navigate", "visit"]:
                        url = " ".join(words[i+1:]).strip()
                        if url:
                            result = asyncio.run(self.browser.open(url))
                            return f"Opened: {result.get('title', url)}"
        except Exception as e:
            return f"Browser error: {str(e)}"
        return ""

    def _handle_screenshot(self) -> str:
        """Handle screenshot command."""
        try:
            return self.auto.take_screenshot()
        except Exception as e:
            return f"Screenshot error: {str(e)}"

    def _handle_system(self) -> str:
        """Handle system info command."""
        try:
            report = self.sysmon.get_full_report()
            return self.sysmon.format_report(report)
        except Exception as e:
            return f"System error: {str(e)}"

    def _handle_file(self, message: str) -> str:
        """Handle file operations."""
        return "File operation result"

    def _handle_code(self, message: str) -> str:
        """Handle code execution."""
        try:
            code = CodeExecutor.extract_code_block(message)
            if code:
                result = self.coder.execute(code)
                return self.coder.format_result(result)
        except Exception as e:
            return f"Code error: {str(e)}"
        return ""

    def _handle_research(self, message: str) -> str:
        """Handle research requests."""
        return "Research result"

    def _handle_learning(self, message: str) -> str:
        """Handle learning requests."""
        return "Learning started"

    @staticmethod
    def _trivial_response(message: str) -> str:
        """Generate trivial responses for simple inputs."""
        responses = {
            "hi": "Hey! What's up?",
            "hello": "Hi there!",
            "hey": "What can I do for you?",
            "bye": "See you later!",
            "ok": "Done.",
            "thanks": "Anytime!",
        }
        return responses.get(message.lower().strip(), "Got it.")
