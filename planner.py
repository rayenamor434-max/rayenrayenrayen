"""
JARVIS OMEGA — Planner
Task management + AI-powered planning.
Bridges MemorySystem and AICore for intelligent task orchestration.
"""
import json
import re
from typing import Optional, Dict, List
from datetime import datetime


class Planner:
    def __init__(self, memory, ai):
        self.memory = memory
        self.ai = ai

    # ── Task CRUD ─────────────────────────────────────────────────────────[...]

    def add(
        self,
        title: str,
        description: str = "",
        priority: str = "normal",
        project: str = "inbox",
        due_date: Optional[str] = None,
    ) -> Dict:
        """Add a task and return its info dict."""
        task_id = self.memory.add_task(
            title,
            description=description,
            priority=priority,
            project=project,
            due_date=due_date,
        )
        self.memory.log_event(
            "task_created",
            f"Task #{task_id}: {title}",
            {"priority": priority, "project": project},
        )
        return {
            "id": task_id,
            "title": title,
            "priority": priority,
            "project": project,
            "due_date": due_date,
            "status": "pending",
        }

    def complete(self, task_id: int) -> str:
        """Mark task as done and return confirmation message."""
        ok = self.memory.update_task(task_id, status="done")
        if not ok:
            return f"Task #{task_id} not found."
        self.memory.log_event("task_completed", f"Task #{task_id} marked done")
        return f"✓ Task #{task_id} marked as complete."

    def summary(self) -> str:
        """Plain-text summary of pending/done tasks."""
        tasks = self.memory.get_tasks()
        if not tasks:
            return "No tasks yet. Use /task to add one."
        pending = [t for t in tasks if t.get("status") != "done"]
        done = [t for t in tasks if t.get("status") == "done"]
        lines = [f"Tasks: {len(pending)} pending, {len(done)} done"]
        for t in pending[:10]:
            flag = {"high": "🔴", "normal": "🟡", "low": "🟢"}.get(t.get("priority", "normal"), "🟡")
            lines.append(f"  {flag} [{t['id']}] {t['title']} ({t.get('project', 'inbox')})")
        return "\n".join(lines)

    # ── AI Planning ─────────────────────────────────────────────────────────[...]

    def ai_breakdown(self, goal: str) -> Dict:
        """
        Use AI to break a high-level goal into concrete sub-tasks.
        Returns {goal, tasks: [{title, priority, description}], raw_ai}
        """
        prompt = f"""Break down this goal into 4-8 actionable sub-tasks:

Goal: {goal}

Return ONLY a JSON array of objects. Each object must have:
- "title": short task name (string)
- "priority": "high" | "normal" | "low"
- "description": one sentence detail (string)

Example: [{{{"title": "Research X", "priority": "high", "description": "Gather info on X."}}}"""

        raw = self.ai.quick(prompt, system="You are a project planning assistant. Output only valid JSON.")
        tasks = []
        try:
            clean = re.sub(r"```(?:json)?", "", raw).strip().strip("`")
            m = re.search(r"\[.*\]", clean, re.S)
            if m:
                parsed = json.loads(m.group(0))
                for item in parsed:
                    if isinstance(item, dict) and "title" in item:
                        task_id = self.memory.add_task(
                            item["title"],
                            description=item.get("description", ""),
                            priority=item.get("priority", "normal"),
                            project=goal[:40],
                        )
                        tasks.append({**item, "id": task_id})
        except Exception:
            pass

        if not tasks:
            # Fallback: single task with the goal itself
            task_id = self.memory.add_task(goal, project="ai-plan")
            tasks = [{"title": goal, "id": task_id, "priority": "normal", "description": ""}]

        self.memory.log_event("ai_plan", f"Breakdown for: {goal}", {"tasks": len(tasks)})
        return {"goal": goal, "tasks": tasks, "raw_ai": raw}

    def smart_schedule(self, available_hours: float = 4.0) -> str:
        """
        Ask AI to propose a schedule for pending tasks within available hours.
        """
        tasks = self.memory.get_tasks(status="pending")
        if not tasks:
            return "No pending tasks to schedule."

        task_list = "\n".join(
            f"- [{t.get('priority','normal')}] {t['title']} (project: {t.get('project','inbox')})"
            for t in tasks[:15]
        )
        prompt = (
            f"I have {available_hours} hours available today. "
            f"Create a realistic time-blocked schedule for these tasks:\n\n{task_list}\n\n"
            f"Format as a numbered list with time blocks (e.g., 09:00-10:00 Task X). "
            f"Be concise."
        )
        return self.ai.quick(prompt, system="You are a productivity coach. Output a simple schedule.")

    def task_summary(self) -> Dict:
        """Return task count stats dict."""
        tasks = self.memory.get_tasks()
        pending = sum(1 for t in tasks if t.get("status") == "pending")
        done = sum(1 for t in tasks if t.get("status") == "done")
        high = sum(1 for t in tasks if t.get("priority") == "high" and t.get("status") != "done")
        return {"total": len(tasks), "pending": pending, "done": done, "high_priority": high}
