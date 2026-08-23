import logging
from typing import Optional

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Playwright, sync_playwright

logger = logging.getLogger(__name__)


class BrowserFetcher:
    """
    Fetches and extracts rendered text content from web pages using Playwright.
    Useful for JavaScript-rendered pages and Cloudflare-protected sites.
    """

    # Indicators of Cloudflare challenge page
    CF_CHALLENGE_INDICATORS = [
        "cf-challenge",
        "challenge-form",
        "checking your browser",
        "please wait",
        "ray id",
        "cloudflare",
        "__cf_chl_",
        "challenge-platform",
        "turnstile",
    ]

    # Indicators of SPA shell (empty app mount point)
    SPA_SHELL_INDICATORS = [
        'id="root"',
        'id="app"',
        'id="__next"',
    ]

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
        """Get or create the browser instance."""
        if self._browser is None:
            if self._playwright is None:
                self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
        return self._browser

    def fetch(self, url: str) -> Optional[str]:
        """
        Fetch a URL using browser and return extracted text content.
        Returns None on failure.
        """
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

            # Set timeouts
            page.set_default_timeout(self.timeout * 1000)
            page.set_default_navigation_timeout(self.timeout * 1000)

            # Navigate to URL
            logger.info("Browser fetching: %s", url)
            response = page.goto(url, wait_until="domcontentloaded")

            if response is None:
                logger.warning("No response for %s", url)
                return None

            status = response.status
            if status >= 400:
                logger.warning("HTTP %d for %s", status, url)

            # Wait for network to settle
            try:
                page.wait_for_load_state("networkidle", timeout=min(self.timeout * 1000, 10000))
            except PlaywrightError:
                pass

            # Wait for meaningful content or challenge resolution
            content = self._wait_for_content(page)

            if content:
                logger.info("Browser fetch successful: %s (%d chars)", url, len(content))
                return content

            logger.warning("Browser fetch returned insufficient content for %s", url)
            return None

        except PlaywrightError as e:
            logger.warning("Playwright error fetching %s: %s", url, e)
            return None
        except Exception as e:
            logger.warning("Unexpected error fetching %s: %s", url, e)
            return None
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass
            if context:
                try:
                    context.close()
                except Exception:
                    pass

    def _wait_for_content(self, page) -> Optional[str]:
        """
        Wait for page to have meaningful content.
        Exits early if content length stabilizes without reaching min_content_length.
        """
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

            # Track content length stability to exit early if SPA rendering stalled
            current_len = len(text_content)
            if current_len == last_len:
                stable_count += 1
                if stable_count >= 3:  # Stale for 3 seconds, break early
                    logger.debug("Content length stabilized at %d chars, exiting wait loop early", current_len)
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
        """Detect if page is a Cloudflare challenge page."""
        html_lower = html.lower()
        text_lower = text.lower()

        for indicator in self.CF_CHALLENGE_INDICATORS:
            if indicator in html_lower or indicator in text_lower:
                return True
        return False

    def _is_spa_shell(self, html: str, text: str) -> bool:
        """Detect if page is an SPA shell with empty content."""
        html_lower = html.lower()

        # Check for SPA mount points
        for indicator in self.SPA_SHELL_INDICATORS:
            if indicator in html_lower:
                # If we have a mount point but very little text, it's likely a shell
                if len(text.strip()) < 200:
                    return True
        return False

    def _extract_text(self, html: str) -> str:
        """Extract readable text from HTML using BeautifulSoup."""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")

            # Remove script, style, and other non-content elements
            for element in soup(
                [
                    "script",
                    "style",
                    "noscript",
                    "iframe",
                    "svg",
                    "nav",
                    "footer",
                    "header",
                ]
            ):
                element.decompose()

            # Get text with some structure preserved
            text = soup.get_text(separator="\n", strip=True)

            # Clean up excessive whitespace
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            return "\n".join(lines)

        except Exception as e:
            logger.warning("Error extracting text: %s", e)
            return html[:10000]  # Fallback

    def close(self) -> None:
        """Close the browser and playwright."""
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    def __enter__(self) -> "BrowserFetcher":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()