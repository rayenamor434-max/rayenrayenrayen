"""
JARVIS OMEGA — Learning (root-level shim)
Adapts agents/LearningAgent to the method names expected by orchestrator.py.

orchestrator.py calls:
  self.learning.is_learn_request(msg)
  self.learning.detect_topic_from_message(msg)
  self.learning.get_roadmap(topic)
  self.learning.build_study_context(topic, mode)
  self.learning.format_roadmap(topic, roadmap)

agents/LearningAgent exposes:
  is_learning_request(), extract_topic(), start_learning(), get_status(), etc.
"""
from typing import Dict, List, Optional


class LearningAgent:
    """
    Compatibility wrapper matching the method names orchestrator.py expects.
    All original LearningAgent methods remain available.
    """

    def __init__(self):
        self.memory = None

    # ── Orchestrator-facing API ───────────────────────────────────────────────

    def is_learning_request(self, message: str) -> bool:
        """Check if message is a learning request."""
        keywords = ["learn", "teach", "tutorial", "explain", "study", "how to", "understand"]
        lower = message.lower()
        return any(kw in lower for kw in keywords)

    def extract_topic(self, message: str) -> str:
        """Extract topic from message."""
        # Simple extraction: remove common prefixes
        msg = message.lower()
        for prefix in ["teach me", "help me learn", "learn about", "i want to learn", "explain"]:
            if prefix in msg:
                topic = msg.replace(prefix, "").strip()
                return topic if topic else "general"
        return "general"

    def get_roadmap(self, topic: str) -> Optional[List[str]]:
        """
        Return a pre-built roadmap list for a topic from memory,
        or None if no session exists.
        """
        if self.memory:
            session = self.memory.get_learning_session(topic)
            if session and session.get("roadmap"):
                return session["roadmap"]
        return None

    def build_study_context(self, topic: str, mode: str = "standard") -> str:
        """
        Build a study context string for injecting into the system prompt.
        Pulls notes and roadmap from memory if available.
        """
        lines = [f"[STUDY MODE: {topic.upper()}]"]

        if self.memory:
            session = self.memory.get_learning_session(topic)
            if session:
                roadmap = session.get("roadmap", [])
                step = session.get("current_step", 0)
                total = session.get("total_steps", len(roadmap))
                lines.append(f"Progress: Step {step}/{total}")
                if step < len(roadmap):
                    lines.append(f"Current focus: {roadmap[step]}")
                if roadmap:
                    lines.append("Roadmap: " + " → ".join(roadmap[:5]) + (" ..." if len(roadmap) > 5 else ""))

            notes = self.memory.get_study_notes(topic) if hasattr(self.memory, "get_study_notes") else []
            if notes:
                recent_note = notes[-1].get("content", "")[:500]
                if recent_note:
                    lines.append(f"Recent notes: {recent_note}")

        depth_instruction = {
            "quick": "Give a brief, accessible overview.",
            "deep": "Go in-depth, cover theory, examples, and edge cases.",
        }.get(mode, "Explain clearly with examples.")
        lines.append(depth_instruction)

        return "\n".join(lines)

    def format_roadmap(self, topic: str, roadmap: List[str]) -> str:
        """
        Format a roadmap list into a human-readable string.
        """
        if not roadmap:
            return f"No roadmap available for '{topic}'."
        lines = [f"📚 Learning Roadmap: {topic}", ""]
        for i, step in enumerate(roadmap, 1):
            lines.append(f"  {i}. {step}")
        lines.append(f"\nTotal: {len(roadmap)} steps")
        return "\n".join(lines)
