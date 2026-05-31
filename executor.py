"""
JARVIS OMEGA — Safe Python Code Executor
Subprocess sandbox with: timeout, output capture, history, auto-fix hooks.
"""
import subprocess
import sys
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional
from config import CODE_EXEC_TIMEOUT, CODE_DIR, CODE_EXEC_ENABLED

BLOCKED_PATTERNS = [
    r"import\s+os\s*;\s*os\.system",
    r"subprocess\.call\(\[.{0,10}rm\s+-rf",
    r"shutil\.rmtree\(\s*['\"]\/ ",
    r"__import__\(['\"]os['\"]\)\.system",
    r"eval\(compile",
    r"exec\(compile",
    r"open\(['\"]\/ etc",
    r"open\(['\"]\/ proc",
    r"ctypes\.cdll",
    r"ctypes\.windll",
    # Additional dangerous patterns
    r"os\.system\(",
    r"os\.popen\(",
    r"subprocess\.Popen\(",
    r"subprocess\.check_output\(",
    r"socket\.socket\(",
    r"__builtins__\[",
]

_COMPILED_BLOCKS = [re.compile(p, re.I) for p in BLOCKED_PATTERNS]


class CodeExecutor:
    def __init__(self):
        self.enabled = CODE_EXEC_ENABLED
        self.history: List[Dict] = []
        os.makedirs(CODE_DIR, exist_ok=True)

    def execute(self, code: str, language: str = "python", timeout: int = None) -> Dict:
        """Execute code with safety checks."""
        if not self.enabled:
            return self._err("Code execution disabled. Set CODE_EXEC=true in .env", code)

        if language.lower() not in ("python", "py"):
            return self._err(f"Language '{language}' not supported yet.", code)

        for pattern in _COMPILED_BLOCKS:
            if pattern.search(code):
                return self._err(f"Blocked unsafe pattern in code.", code)

        return self._run_subprocess(code, timeout or CODE_EXEC_TIMEOUT)

    def execute_file(self, filepath: str, timeout: int = None) -> Dict:
        """Execute a file."""
        if not os.path.exists(filepath):
            return self._err(f"File not found: {filepath}", "")
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            code = f.read()
        return self.execute(code, timeout=timeout)

    def execute_raw(self, code: str, timeout: int = None) -> Dict:
        """Public method for API calls."""
        return self.execute(code, timeout=timeout)

    def _run_subprocess(self, code: str, timeout: int) -> Dict:
        """Run code in isolated subprocess."""
        fname = os.path.join(CODE_DIR, f"exec_{os.getpid()}_{int(time.time()*1000)}.py")
        try:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(code)

            start = time.perf_counter()
            try:
                proc = subprocess.run(
                    [sys.executable, "-u", fname],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=CODE_DIR,
                    encoding="utf-8",
                    errors="replace",
                )
            except subprocess.TimeoutExpired:
                return self._err(f"Timed out after {timeout}s", code, timeout)
            except Exception as e:
                return self._err(f"Execution error: {str(e)}", code)

            elapsed = round(time.perf_counter() - start, 3)

            entry = {
                "success": proc.returncode == 0,
                "output": proc.stdout[:6000],
                "error": proc.stderr[:3000] if proc.stderr else "",
                "return_code": proc.returncode,
                "execution_time": elapsed,
                "code": code,
                "timestamp": datetime.now().isoformat(),
                "language": "python",
            }
            self.history.append(entry)
            if len(self.history) > 50:
                self.history = self.history[-50:]
            return entry

        except Exception as e:
            return self._err(str(e), code)
        finally:
            try:
                os.remove(fname)
            except OSError:
                pass

    def format_result(self, result: Dict) -> str:
        """Format result for display."""
        if result["success"]:
            out = result["output"].strip() or "(no output)"
            return f"✓ {result['execution_time']}s\n{out}"
        else:
            err = result["error"].strip() or result.get("output", "").strip() or "Unknown error"
            return f"✗ Error ({result['execution_time']}s)\n{err}"

    def get_last_error(self) -> Optional[str]:
        """Get last error from history."""
        for entry in reversed(self.history):
            if not entry["success"]:
                return entry.get("error", "")
        return None

    def get_history(self, limit: int = 20) -> List[Dict]:
        """Get execution history."""
        return self.history[-limit:]

    @staticmethod
    def extract_code_block(text: str) -> Optional[str]:
        """Extract Python code from markdown code block."""
        m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
        if m:
            return m.group(1).strip()
        m = re.search(r"`([^`\n]{15,})`", text)
        if m:
            return m.group(1).strip()
        return None

    @staticmethod
    def _err(msg: str, code: str, t: float = 0) -> Dict:
        """Format error response."""
        return {
            "success": False,
            "output": "",
            "error": msg,
            "return_code": -1,
            "execution_time": t,
            "code": code,
            "timestamp": datetime.now().isoformat(),
            "language": "python",
        }
