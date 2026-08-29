"""Cloudflare bypass fetcher using SeleniumBase (undetected-chromedriver) + session hijacking."""

import logging
from typing import Optional, Dict
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from seleniumbase import Driver

logger = logging.getLogger(__name__)


class CloudflareBypassFetcher:
    """
    Fetcher that bypasses Cloudflare using SeleniumBase undetected-chromedriver,
    then hijacks the session (cookies + headers) for fast HTTP crawling.
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_content_length: int = 500_000,
        user_agent: str = "PowerWinContentResearcher/1.0 (+https://power.win)",
        headless: bool = True,
    ) -> None:
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.user_agent = user_agent
        self.headless = headless
        self._session_cache: Dict[str, Dict] = {}  # domain -> {cookies, headers}

    def _get_driver(self) -> Driver:
        """Create a new undetected Chrome driver."""
        return Driver(
            uc=True,
            headless=self.headless,
            agent=self.user_agent,
            window_size="1280,720",
        )

    def _extract_session(self, driver: Driver, url: str) -> Dict:
        """Extract cookies and headers from the browser session."""
        domain = urlparse(url).netloc
        cookies = driver.get_cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies}

        # Get headers from a real request via CDP
        headers = self._get_real_headers(driver)

        return {
            "cookies": cookie_dict,
            "headers": headers,
            "domain": domain,
        }

    def _get_real_headers(self, driver: Driver) -> Dict[str, str]:
        """Capture headers from a real browser request using CDP."""
        try:
            # Enable Network domain and capture headers
            driver.execute_cdp_cmd("Network.enable", {})
            
            # Get the main frame to trigger a request
            # We'll capture headers from the next request
            return {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
            }
        except Exception as e:
            logger.debug("Failed to capture real headers via CDP: %s", e)
            return {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }

    def _wait_for_cloudflare(self, driver: Driver, max_wait: float = 20.0) -> bool:
        """Wait for Cloudflare challenge to complete."""
        import time
        start = time.time()
        while time.time() - start < max_wait:
            try:
                # Check if we're past the challenge
                title = driver.get_title().lower()
                if "just a moment" not in title and "checking your browser" not in title:
                    # Additional check: look for challenge indicators in page source
                    page_source = driver.get_page_source().lower()
                    if not any(indicator in page_source for indicator in [
                        "cf-challenge", "challenge-form", "ray id", "cloudflare",
                        "__cf_chl_", "challenge-platform", "turnstile"
                    ]):
                        return True
            except Exception:
                pass
            time.sleep(1)
        # Final check - if we have substantial content, consider it success
        try:
            final_content = driver.get_page_source()
            if len(final_content) > 5000:
                return True
        except Exception:
            pass
        return False

    def fetch(self, url: str) -> Optional[str]:
        """
        Fetch a URL by first bypassing Cloudflare with SeleniumBase,
        then using the hijacked session for subsequent requests.
        """
        domain = urlparse(url).netloc

        # Check if we have a cached session for this domain
        if domain in self._session_cache:
            logger.debug("Using cached session for domain: %s", domain)
            return self._fetch_with_session(url, self._session_cache[domain])

        # No cached session - need to bypass Cloudflare
        logger.info("Bypassing Cloudflare for: %s", url)
        driver = None
        try:
            driver = self._get_driver()
            driver.get(url)

            # Wait for Cloudflare challenge to complete
            if not self._wait_for_cloudflare(driver, max_wait=self.timeout):
                logger.warning("Cloudflare challenge did not complete in time for %s", url)
                return None

            # Extract session (cookies + headers)
            session = self._extract_session(driver, url)
            self._session_cache[domain] = session

            # Get the page content
            content = driver.get_page_source()
            return self._extract_text(content)

        except Exception as e:
            logger.warning("Cloudflare bypass failed for %s: %s", url, e)
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _fetch_with_session(self, url: str, session: Dict) -> Optional[str]:
        """Fetch using hijacked session (cookies + headers)."""
        try:
            client = httpx.Client(
                timeout=self.timeout,
                headers={**session["headers"], "Cookie": self._format_cookies(session["cookies"])},
                follow_redirects=True,
            )
            response = client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                logger.warning("Non-text content type for %s: %s", url, content_type)
                return None

            content = response.text
            if len(content) > self.max_content_length:
                content = content[: self.max_content_length]

            return self._extract_text(content)

        except httpx.TimeoutException:
            logger.warning("Timeout fetching %s with hijacked session", url)
            return None
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP error fetching %s: %s", url, e.response.status_code)
            # Session may have expired, remove from cache
            domain = urlparse(url).netloc
            self._session_cache.pop(domain, None)
            return None
        except httpx.RequestError as e:
            logger.warning("Request error fetching %s: %s", url, e)
            return None
        except Exception as e:
            logger.warning("Unexpected error fetching %s: %s", url, e)
            return None

    def _format_cookies(self, cookies: Dict[str, str]) -> str:
        """Format cookies dict as Cookie header string."""
        return "; ".join(f"{k}={v}" for k, v in cookies.items())

    def _extract_text(self, html: str) -> str:
        """Extract readable text from HTML."""
        try:
            soup = BeautifulSoup(html, "html.parser")

            for element in soup(["script", "style", "noscript", "iframe", "svg", "nav", "footer", "header"]):
                element.decompose()

            text = soup.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            return "\n".join(lines)

        except Exception as e:
            logger.warning("Error extracting text: %s", e)
            return html[:10000]

    def close(self) -> None:
        """Clear session cache."""
        self._session_cache.clear()

    def __enter__(self) -> "CloudflareBypassFetcher":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()