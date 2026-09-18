import logging
from typing import Optional

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Playwright, sync_playwright

from intelligence_content_engine.research.tools.url_safety import UnsafeURLError, validate_outbound_url

logger = logging.getLogger(__name__)


class BrowserFetcher:
    """Fetches and extracts rendered text content from web pages using Playwright."""

    CF_CHALLENGE_INDICATORS = [
        "cf-challenge", "challenge-form", "checking your browser", "please wait",
        "ray id", "cloudflare", "__cf_chl_", "challenge-platform", "turnstile",
    ]
    SPA_SHELL_INDICATORS = ['id="root"', 'id="app"', 'id="__next"']

    def __init__(
        self,
        timeout: float = 15.0,
        user_agent: str = "PowerWinContentResearcher/1.0 (+https://power.win)",
        min_content_length: int = 500,
        headless: bool = True,
    ) -> None:
        self.timeout = timeout
        self.user_agent = user_agent
        self.min_content_length = min_content_length
        self.headless = headless
        self._playwright: Optional[Playwright] = None
        self._browser = None

    def _get_browser(self):
        if self._browser is None:
            if self._playwright is None:
                self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
        return self._browser

    def fetch(self, url: str) -> Optional[str]:
        """Fetch a URL using a browser after validating the destination."""
        try:
            safe_url = validate_outbound_url(url)
        except UnsafeURLError as exc:
            logger.warning("Blocked unsafe browser URL %s: %s", url, exc)
            return None

        browser = self._get_browser()
        context = None
        page = None
        try:
            context = browser.new_context(
                user_agent=self.user_agent,
                viewport={"width": 1280, "height": 720},
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            page = context.new_page()
            page.set_default_timeout(self.timeout * 1000)
            page.set_default_navigation_timeout(self.timeout * 1000)
            logger.info("Browser fetching: %s", safe_url)
            response = page.goto(safe_url, wait_until="domcontentloaded")
            if response is None:
                logger.warning("No response for %s", safe_url)
                return None
            if response.status >= 400:
                logger.warning("HTTP %d for %s", response.status, safe_url)
            try:
                page.wait_for_load_state("networkidle", timeout=min(self.timeout * 1000, 10000))
            except PlaywrightError:
                pass
            content = self._wait_for_content(page)
            if content:
                # Validate the final browser URL as well. This does not eliminate
                # redirect-time exposure, but prevents accepting unsafe destinations.
                try:
                    validate_outbound_url(page.url)
                except UnsafeURLError:
                    logger.warning("Browser redirected to an unsafe URL: %s", page.url)
                    return None
                return content
            return None
        except PlaywrightError as e:
            logger.warning("Playwright error fetching %s: %s", safe_url, e)
            return None
        except Exception as e:
            logger.warning("Unexpected error fetching %s: %s", safe_url, e)
            return None
        finally:
            if page:
                try: page.close()
                except Exception: pass
            if context:
                try: context.close()
                except Exception: pass

    def _wait_for_content(self, page) -> Optional[str]:
        import time
        start_time = time.time()
        max_wait = self.timeout
        last_len = -1
        stable_count = 0
        while time.time() - start_time < max_wait:
            content = page.content()
            text_content = page.evaluate("() => document.body?.innerText?.trim() || ''")
            if len(text_content) >= self.min_content_length:
                return self._extract_text(content)
            current_len = len(text_content)
            if current_len == last_len:
                stable_count += 1
                if stable_count >= 3:
                    break
            else:
                last_len = current_len
                stable_count = 0
            time.sleep(1)
        final_content = page.content()
        final_text = page.evaluate("() => document.body?.innerText?.trim() || ''")
        if len(final_text) >= self.min_content_length:
            return self._extract_text(final_content)
        return None

    def _is_cloudflare_challenge(self, html: str, text: str) -> bool:
        combined = f"{html.lower()} {text.lower()}"
        return any(indicator in combined for indicator in self.CF_CHALLENGE_INDICATORS)

    def _is_spa_shell(self, html: str, text: str) -> bool:
        html_lower = html.lower()
        return any(indicator in html_lower and len(text.strip()) < 200 for indicator in self.SPA_SHELL_INDICATORS)

    def _extract_text(self, html: str) -> str:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for element in soup(["script", "style", "noscript", "iframe", "svg", "nav", "footer", "header"]):
                element.decompose()
            text = soup.get_text(separator="\n", strip=True)
            return "\n".join(line.strip() for line in text.split("\n") if line.strip())
        except Exception as e:
            logger.warning("Error extracting text: %s", e)
            return html[:10000]

    def close(self) -> None:
        if self._browser is not None:
            try: self._browser.close()
            except Exception: pass
            self._browser = None
        if self._playwright is not None:
            try: self._playwright.stop()
            except Exception: pass
            self._playwright = None

    def __enter__(self) -> "BrowserFetcher":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
