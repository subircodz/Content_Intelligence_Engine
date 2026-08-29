import logging
from typing import Optional

from power_win_content.research.tools.web_fetcher import WebFetcher
from power_win_content.research.tools.browser_fetcher import BrowserFetcher
from power_win_content.research.tools.cloudflare_fetcher import CloudflareBypassFetcher

logger = logging.getLogger(__name__)


class HybridFetcher:
    """
    Hybrid fetcher that tries HTTP first, falls back to Cloudflare bypass for protected sites,
    then falls back to browser for JavaScript-heavy pages.
    """

    def __init__(
        self,
        http_fetcher: Optional[WebFetcher] = None,
        browser_fetcher: Optional[BrowserFetcher] = None,
        cloudflare_fetcher: Optional[CloudflareBypassFetcher] = None,
        min_content_length: int = 500,
    ) -> None:
        self.http_fetcher = http_fetcher or WebFetcher()
        self.browser_fetcher = browser_fetcher or BrowserFetcher()
        self.cloudflare_fetcher = cloudflare_fetcher or CloudflareBypassFetcher()
        self.min_content_length = min_content_length
        self._failed_urls: set[str] = set()

    def fetch(self, url: str) -> Optional[str]:
        """
        Fetch a URL, trying HTTP first, then Cloudflare bypass, then browser.
        Caches failed URLs within session to avoid redundant failing requests.
        """
        if url in self._failed_urls:
            logger.debug("Skipping previously failed URL: %s", url)
            return None

        # Try HTTP first
        logger.debug("Trying HTTP fetch for: %s", url)
        content = self.http_fetcher.fetch(url)

        if self._is_usable_content(content):
            logger.debug("HTTP fetch successful for: %s", url)
            return content

        # Check if it's a Cloudflare challenge
        if self._is_cloudflare_challenge(content):
            logger.info("Cloudflare challenge detected for %s, using bypass fetcher", url)
            try:
                content = self.cloudflare_fetcher.fetch(url)
                if self._is_usable_content(content):
                    logger.debug("Cloudflare bypass successful for: %s", url)
                    return content
                logger.warning("Cloudflare bypass also insufficient for: %s", url)
            except Exception as e:
                logger.warning("Cloudflare bypass failed for %s: %s", url, e)

        logger.info("Falling back to browser for: %s", url)

        # Fallback to browser
        try:
            content = self.browser_fetcher.fetch(url)
            if self._is_usable_content(content):
                logger.debug("Browser fetch successful for: %s", url)
                return content
            logger.warning("Browser fetch also insufficient for: %s", url)
            self._failed_urls.add(url)
            return content
        except Exception as e:
            logger.warning("Browser fetch failed for %s: %s", url, e)
            self._failed_urls.add(url)
            return content  # Return HTTP content even if insufficient

    def fetch_raw(self, url: str) -> Optional[str]:
        """Fetch raw content without extraction (for sitemaps, etc.)."""
        return self.http_fetcher.fetch_raw(url)

    def _is_usable_content(self, content: Optional[str]) -> bool:
        """
        Determine if fetched content is usable (not just SPA shell or challenge page).
        """
        if not content:
            return False

        if len(content) < self.min_content_length:
            return False

        content_lower = content.lower()

        # Check for Cloudflare challenge page
        cf_indicators = [
            "cf-challenge",
            "challenge-form",
            "checking your browser",
            "please wait",
            "ray id",
            "__cf_chl_",
            "challenge-platform",
            "turnstile",
        ]
        for indicator in cf_indicators:
            if indicator in content_lower:
                return False

        # Check for SPA shell (empty root/app/__next with minimal text)
        spa_indicators = ['id="root"', 'id="app"', 'id="__next"']
        for indicator in spa_indicators:
            if indicator in content_lower:
                # If we have SPA mount point but very little meaningful content
                # (the extracted text would be minimal for a shell)
                if len(content) < self.min_content_length * 2:
                    return False

        return True

    def _is_cloudflare_challenge(self, content: Optional[str]) -> bool:
        """Detect if content is a Cloudflare challenge page."""
        if not content:
            return False
        content_lower = content.lower()
        cf_indicators = [
            "cf-challenge",
            "challenge-form",
            "checking your browser",
            "please wait",
            "ray id",
            "__cf_chl_",
            "challenge-platform",
            "turnstile",
            "just a moment",
        ]
        return any(indicator in content_lower for indicator in cf_indicators)

    def close(self) -> None:
        """Close all fetchers."""
        self.http_fetcher.close()
        self.browser_fetcher.close()
        self.cloudflare_fetcher.close()

    def clear_failed_cache(self) -> None:
        """Clear the failed URL cache to allow retries."""
        self._failed_urls.clear()

    def __enter__(self) -> "HybridFetcher":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()