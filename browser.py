"""
OMEGA — Browser Agent
Real browser control via Playwright.
Supports: open URLs, search, content extraction, screenshot, tab management.
"""
import asyncio
import re
import os
from typing import Optional, Dict, List
from datetime import datetime

_playwright_instance = None
_browser_instance    = None
_page_instance       = None
_started             = False
_lock                = asyncio.Lock()


async def _get_page():
    global _playwright_instance, _browser_instance, _page_instance, _started
    async with _lock:
        if _started and _page_instance and not _page_instance.is_closed():
            return _page_instance
        try:
            from playwright.async_api import async_playwright
            if _playwright_instance is None:
                _playwright_instance = await async_playwright().start()
            if _browser_instance is None or not _browser_instance.is_connected():
                _browser_instance = await _playwright_instance.chromium.launch(
                    headless=False,  # show browser so user sees actions
                    args=["--no-sandbox", "--disable-dev-shm-usage",
                          "--disable-blink-features=AutomationControlled"],
                )
            ctx  = await _browser_instance.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            _page_instance = await ctx.new_page()
            _started       = True
            return _page_instance
        except Exception as e:
            raise RuntimeError(f"Playwright not available: {e}")


def is_available() -> bool:
    try:
        from playwright.async_api import async_playwright  # noqa
        return True
    except ImportError:
        return False


class BrowserAgent:
    """Async Playwright-based browser agent."""

    async def open(self, url: str) -> Dict:
        """Navigate to a URL and return page info."""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            page = await _get_page()
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            title = await page.title()
            return {
                "success" : True,
                "url"     : page.url,
                "title"   : title,
                "status"  : resp.status if resp else 200,
                "message" : f"Opened: {title} ({page.url})",
            }
        except Exception as e:
            return {"success": False, "url": url, "message": str(e)}

    async def search(self, query: str, engine: str = "google") -> Dict:
        """Search and return top results."""
        engines = {
            "google"    : f"https://www.google.com/search?q={_q(query)}",
            "duckduckgo": f"https://duckduckgo.com/?q={_q(query)}",
            "youtube"   : f"https://www.youtube.com/results?search_query={_q(query)}",
            "github"    : f"https://github.com/search?q={_q(query)}",
            "wikipedia" : f"https://en.wikipedia.org/wiki/Special:Search?search={_q(query)}",
        }
        url = engines.get(engine.lower(), engines["google"])
        result = await self.open(url)
        if not result["success"]:
            return result

        try:
            page = await _get_page()
            await page.wait_for_load_state("networkidle", timeout=10000)
            links = await self._extract_links(page)
            return {**result, "results": links[:8]}
        except Exception:
            return {**result, "results": []}

    async def get_page_content(self, max_chars: int = 4000) -> str:
        """Get text content of current page."""
        try:
            page = await _get_page()
            # Remove script/style tags
            text = await page.evaluate("""() => {
                const remove = document.querySelectorAll('script,style,nav,footer,header');
                remove.forEach(el => el.remove());
                return document.body?.innerText || '';
            }""")
            text = re.sub(r"\s+", " ", text).strip()
            return text[:max_chars]
        except Exception as e:
            return f"Could not extract content: {e}"

    async def current_url(self) -> str:
        try:
            page = await _get_page()
            return page.url
        except Exception:
            return ""

    async def current_title(self) -> str:
        try:
            page = await _get_page()
            return await page.title()
        except Exception:
            return ""

    async def screenshot(self, path: str = None) -> str:
        """Take screenshot of current browser page."""
        try:
            page = await _get_page()
            if not path:
                from config import SCREENSHOTS_DIR
                os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
                path = os.path.join(
                    SCREENSHOTS_DIR,
                    f"browser_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                )
            await page.screenshot(path=path, full_page=False)
            return path
        except Exception as e:
            return f"Screenshot failed: {e}"

    async def click(self, selector_or_text: str) -> Dict:
        """Click an element by CSS selector or visible text."""
        try:
            page = await _get_page()
            # Try text first, then selector
            try:
                await page.get_by_text(selector_or_text, exact=False).first.click(timeout=5000)
            except Exception:
                await page.click(selector_or_text, timeout=5000)
            return {"success": True, "message": f"Clicked: {selector_or_text}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def fill(self, selector: str, value: str) -> Dict:
        """Fill an input field."""
        try:
            page = await _get_page()
            await page.fill(selector, value)
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def scroll(self, direction: str = "down", amount: int = 500) -> Dict:
        """Scroll the current page."""
        try:
            page = await _get_page()
            delta = amount if direction == "down" else -amount
            await page.evaluate(f"window.scrollBy(0, {delta})")
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def close(self):
        global _browser_instance, _page_instance, _started
        try:
            if _page_instance:
                await _page_instance.close()
            _page_instance = None
            _started       = False
        except Exception:
            pass

    async def status(self) -> Dict:
        try:
            page = await _get_page()
            return {
                "active": True,
                "url"   : page.url,
                "title" : await page.title(),
            }
        except Exception:
            return {"active": False, "url": "", "title": ""}

    # ── Private ───────────────────────────────────────────────────────────────

    @staticmethod
    async def _extract_links(page) -> List[Dict]:
        try:
            items = await page.evaluate("""() => {
                const results = [];
                // Google results
                document.querySelectorAll('h3').forEach(h => {
                    const a = h.closest('a') || h.querySelector('a');
                    if(a && a.href && a.href.startsWith('http') && !a.href.includes('google.com/search')) {
                        results.push({title: h.innerText.trim(), url: a.href});
                    }
                });
                // Generic links
                if(results.length < 3) {
                    document.querySelectorAll('a[href^="http"]').forEach(a => {
                        if(a.innerText.trim().length > 10) {
                            results.push({title: a.innerText.trim().slice(0,100), url: a.href});
                        }
                    });
                }
                return results.slice(0,10);
            }""")
            return items
        except Exception:
            return []


def _q(query: str) -> str:
    import urllib.parse
    return urllib.parse.quote_plus(query)
