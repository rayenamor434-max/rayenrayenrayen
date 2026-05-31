"""
JARVIS OMEGA — Automation Engine
Browser control, screenshots, and system-level automation.

NOTE: browser_open() uses webbrowser.open() which opens on the SERVER machine.
      It is preserved here for local/desktop use ONLY.
      Web paths in orchestrator._direct_execute() must NEVER call browser_open().
      Instead they return frontend_action: {type: "open_url", url: ...} so the
      frontend calls window.open() in the user's actual browser.
"""
import os
import webbrowser
import urllib.parse
from datetime import datetime
from typing import Optional

from config import SCREENSHOTS_DIR


class AutomationEngine:
    def __init__(self):
        self._screenshot_available = self._check_screenshot()

    @staticmethod
    def _check_screenshot() -> bool:
        try:
            import pyautogui  # noqa
            return True
        except ImportError:
            return False

    # ── Status ────────────────────────────────────────────────────────────────

    def is_ready(self) -> dict:
        return {
            "screenshot": self._screenshot_available,
            "browser"   : True,
        }

    # ── Screenshots ───────────────────────────────────────────────────────────

    def take_screenshot(self) -> str:
        """Capture a screenshot and save to screenshots dir."""
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

        if not self._screenshot_available:
            return (
                "Screenshot not available — pyautogui not installed. "
                "Run: pip install pyautogui Pillow"
            )
        try:
            import pyautogui
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename  = f"screenshot_{timestamp}.png"
            filepath  = os.path.join(SCREENSHOTS_DIR, filename)
            img = pyautogui.screenshot()
            img.save(filepath)
            size_kb = round(os.path.getsize(filepath) / 1024, 1)
            return f"Screenshot saved: {filepath} ({size_kb} KB)"
        except Exception as e:
            return f"Screenshot failed: {e}"

    def get_screenshots(self, limit: int = 10) -> list:
        """List recent screenshots."""
        if not os.path.exists(SCREENSHOTS_DIR):
            return []
        files = sorted(
            [f for f in os.listdir(SCREENSHOTS_DIR) if f.endswith(".png")],
            reverse=True,
        )
        return [
            {
                "filename": f,
                "path"    : os.path.join(SCREENSHOTS_DIR, f),
                "size_kb" : round(
                    os.path.getsize(os.path.join(SCREENSHOTS_DIR, f)) / 1024, 1
                ),
            }
            for f in files[:limit]
        ]

    # ── Browser Control (LOCAL DESKTOP USE ONLY) ─────────────────────────────

    def browser_open(self, url: str) -> str:
        """
        Open a URL in the default browser ON THE SERVER MACHINE.

        WARNING: This is only useful when JARVIS runs locally on the same
        machine as the user's browser. For web deployments, return a
        frontend_action instead of calling this method.
        """
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            webbrowser.open(url)
            return f"Opened in browser: {url}"
        except Exception as e:
            return f"Could not open browser: {e}"

    def browser_search(self, query: str, engine: str = "google") -> str:
        """Search using default browser (LOCAL DESKTOP USE ONLY)."""
        engines = {
            "google"    : "https://www.google.com/search?q=",
            "duckduckgo": "https://duckduckgo.com/?q=",
            "bing"      : "https://www.bing.com/search?q=",
            "youtube"   : "https://www.youtube.com/results?search_query=",
            "github"    : "https://github.com/search?q=",
        }
        base = engines.get(engine.lower(), engines["google"])
        url  = base + urllib.parse.quote_plus(query)
        try:
            webbrowser.open(url)
            return f"Searching '{query}' on {engine.capitalize()}: {url}"
        except Exception as e:
            return f"Browser search failed: {e}"

    # ── System Automation ─────────────────────────────────────────────────────

    def open_application(self, app_name: str) -> str:
        """Attempt to open a named application (Windows/Linux/Mac)."""
        import subprocess
        import platform

        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(app_name)
                return f"Launched: {app_name}"
            elif system == "Darwin":
                subprocess.Popen(["open", "-a", app_name])
                return f"Opened: {app_name}"
            else:
                subprocess.Popen([app_name])
                return f"Launched: {app_name}"
        except FileNotFoundError:
            return f"Application not found: {app_name}"
        except Exception as e:
            return f"Could not launch {app_name}: {e}"

    def notify(self, title: str, message: str) -> str:
        """Send a desktop notification if possible."""
        try:
            import plyer
            plyer.notification.notify(title=title, message=message, timeout=5)
            return f"Notification sent: {title}"
        except ImportError:
            return f"[Notification — install plyer] {title}: {message}"
        except Exception as e:
            return f"Notification failed: {e}"
