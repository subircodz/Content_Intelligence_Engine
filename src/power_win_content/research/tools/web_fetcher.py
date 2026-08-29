import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class WebFetcher:
    """Fetches and extracts readable text content from web pages."""

    def __init__(
        self,
        timeout: float = 15.0,
        max_content_length: int = 500_000,
        user_agent: str = "PowerWinContentResearcher/1.0 (+https://power.win)",
    ) -> None:
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.user_agent = user_agent
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                follow_redirects=True,
            )
        return self._client

    def fetch(self, url: str) -> Optional[str]:
        """
        Fetch a URL and return extracted text content.
        Returns content even on HTTP errors (for Cloudflare detection).
        Returns None only on network/timeout errors.
        """
        content = self.fetch_raw(url)
        if content is None:
            return None
        return self._extract_text(content)

    def fetch_raw(self, url: str) -> Optional[str]:
        """
        Fetch a URL and return raw content (no extraction).
        Used for sitemaps and other XML content.
        """
        try:
            client = self._get_client()
            response = client.get(url)

            # Check content type
            content_type = response.headers.get("content-type", "")
            # Accept HTML, plain text, XML (sitemaps), and error pages
            if not any(ct in content_type for ct in ["text/html", "text/plain", "application/xml", "application/xhtml+xml"]):
                logger.warning("Non-text content type for %s: %s", url, content_type)
                # Still return content for error pages (e.g., Cloudflare challenge)
                if response.status_code >= 400:
                    content = response.text
                    if len(content) > self.max_content_length:
                        content = content[: self.max_content_length]
                    return content
                return None

            # Limit content length
            content = response.text
            if len(content) > self.max_content_length:
                content = content[: self.max_content_length]

            return content

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

            # Remove script, style, and other non-content elements
            for element in soup(["script", "style", "noscript", "iframe", "svg", "nav", "footer", "header"]):
                element.decompose()

            # Get text with some structure preserved
            text = soup.get_text(separator="\n", strip=True)

            # Clean up excessive whitespace
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            return "\n".join(lines)

        except Exception as e:
            logger.warning("Error extracting text: %s", e)
            return html[:10000]  # Fallback: return raw HTML snippet

    def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "WebFetcher":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()