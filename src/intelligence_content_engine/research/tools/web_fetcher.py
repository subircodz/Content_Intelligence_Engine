import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from intelligence_content_engine.research.tools.url_safety import UnsafeURLError, validate_outbound_url

logger = logging.getLogger(__name__)


class WebFetcher:
    """Fetches and extracts readable text content from web pages safely."""

    def __init__(
        self,
        timeout: float = 15.0,
        max_content_length: int = 500_000,
        user_agent: str = "IntelligenceContentResearcher/1.0",
    ) -> None:
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.user_agent = user_agent
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(self.timeout, connect=min(self.timeout, 10.0)),
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                follow_redirects=False,
            )
        return self._client

    def fetch(self, url: str) -> Optional[str]:
        """Fetch a URL and return extracted text content."""
        content = self.fetch_raw(url)
        if content is None:
            return None
        return self._extract_text(content)

    def fetch_raw(self, url: str) -> Optional[str]:
        """Fetch raw text content while enforcing outbound URL safety."""
        try:
            current_url = validate_outbound_url(url)
            client = self._get_client()

            for _ in range(5):
                response = client.get(current_url)

                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        logger.warning("Redirect without Location header for %s", current_url)
                        return None
                    from urllib.parse import urljoin
                    current_url = validate_outbound_url(urljoin(current_url, location))
                    continue

                content_type = response.headers.get("content-type", "")
                if not any(ct in content_type for ct in ["text/html", "text/plain", "application/xml", "application/xhtml+xml", "text/xml"]):
                    logger.warning("Non-text content type for %s: %s", current_url, content_type)
                    if response.status_code >= 400:
                        content = response.text[: self.max_content_length]
                        return content
                    return None

                content = response.text[: self.max_content_length]
                return content

            logger.warning("Too many redirects fetching %s", url)
            return None

        except UnsafeURLError as exc:
            logger.warning("Blocked unsafe outbound URL %s: %s", url, exc)
            return None
        except httpx.TimeoutException:
            logger.warning("Timeout fetching %s", url)
            return None
        except httpx.RequestError as e:
            logger.warning("Request error fetching %s: %s", url, e)
            return None
        except Exception as e:
            logger.warning("Unexpected error fetching %s: %s", url, e)
            return None

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
        """Close the underlying HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "WebFetcher":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
