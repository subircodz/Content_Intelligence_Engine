"""Cloudflare challenge fetcher using SeleniumBase."""

import logging
from typing import Optional, Dict
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from seleniumbase import Driver

from intelligence_content_engine.research.tools.url_safety import UnsafeURLError, validate_outbound_url

logger = logging.getLogger(__name__)


class CloudflareBypassFetcher:
    """Fetch Cloudflare-protected pages through a browser session."""

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
        self._session_cache: Dict[str, Dict] = {}

    def _get_driver(self) -> Driver:
        return Driver(uc=True, headless=self.headless, agent=self.user_agent, window_size="1280,720")

    def _extract_session(self, driver: Driver, url: str) -> Dict:
        domain = urlparse(url).netloc
        cookies = driver.get_cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies}
        return {"cookies": cookie_dict, "headers": self._get_real_headers(driver), "domain": domain}

    def _get_real_headers(self, driver: Driver) -> Dict[str, str]:
        try:
            driver.execute_cdp_cmd("Network.enable", {})
        except Exception as e:
            logger.debug("Failed to enable CDP network capture: %s", e)
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _wait_for_cloudflare(self, driver: Driver, max_wait: float = 20.0) -> bool:
        import time
        start = time.time()
        while time.time() - start < max_wait:
            try:
                title = driver.get_title().lower()
                if "just a moment" not in title and "checking your browser" not in title:
                    page_source = driver.get_page_source().lower()
                    if not any(i in page_source for i in [
                        "cf-challenge", "challenge-form", "ray id", "cloudflare",
                        "__cf_chl_", "challenge-platform", "turnstile"
                    ]):
                        return True
            except Exception:
                pass
            time.sleep(1)
        try:
            return len(driver.get_page_source()) > 5000
        except Exception:
            return False

    def fetch(self, url: str) -> Optional[str]:
        try:
            safe_url = validate_outbound_url(url)
        except UnsafeURLError as exc:
            logger.warning("Blocked unsafe Cloudflare URL %s: %s", url, exc)
            return None

        domain = urlparse(safe_url).netloc
        if domain in self._session_cache:
            return self._fetch_with_session(safe_url, self._session_cache[domain])

        driver = None
        try:
            driver = self._get_driver()
            driver.get(safe_url)
            if not self._wait_for_cloudflare(driver, max_wait=self.timeout):
                return None
            try:
                validate_outbound_url(driver.current_url)
            except UnsafeURLError:
                logger.warning("Browser redirected to unsafe URL: %s", driver.current_url)
                return None
            session = self._extract_session(driver, safe_url)
            self._session_cache[domain] = session
            return self._extract_text(driver.get_page_source())
        except Exception as e:
            logger.warning("Cloudflare fetch failed for %s: %s", safe_url, e)
            return None
        finally:
            if driver:
                try: driver.quit()
                except Exception: pass

    def _fetch_with_session(self, url: str, session: Dict) -> Optional[str]:
        try:
            safe_url = validate_outbound_url(url)
            client = httpx.Client(
                timeout=httpx.Timeout(self.timeout, connect=min(self.timeout, 10.0)),
                headers={**session["headers"], "Cookie": self._format_cookies(session["cookies"])},
                follow_redirects=False,
            )
            response = client.get(safe_url)
            if response.is_redirect:
                location = response.headers.get("location")
                if location:
                    from urllib.parse import urljoin
                    redirected = validate_outbound_url(urljoin(safe_url, location))
                    response = client.get(redirected)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return None
            return self._extract_text(response.text[: self.max_content_length])
        except UnsafeURLError as exc:
            logger.warning("Blocked unsafe session URL %s: %s", url, exc)
            return None
        except httpx.TimeoutException:
            logger.warning("Timeout fetching %s with hijacked session", url)
            return None
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP error fetching %s: %s", url, e.response.status_code)
            self._session_cache.pop(urlparse(url).netloc, None)
            return None
        except httpx.RequestError as e:
            logger.warning("Request error fetching %s: %s", url, e)
            return None
        except Exception as e:
            logger.warning("Unexpected error fetching %s: %s", url, e)
            return None

    def _format_cookies(self, cookies: Dict[str, str]) -> str:
        return "; ".join(f"{k}={v}" for k, v in cookies.items())

    def _extract_text(self, html: str) -> str:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for element in soup(["script", "style", "noscript", "iframe", "svg", "nav", "footer", "header"]):
                element.decompose()
            text = soup.get_text(separator="\n", strip=True)
            return "\n".join(line.strip() for line in text.split("\n") if line.strip())
        except Exception as e:
            logger.warning("Error extracting text: %s", e)
            return html[:10000]

    def close(self) -> None:
        self._session_cache.clear()

    def __enter__(self) -> "CloudflareBypassFetcher":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
