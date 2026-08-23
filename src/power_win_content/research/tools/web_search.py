"""Multi-engine web search with DuckDuckGo, Google, and Bing providers.

Google uses Custom Search API as primary method with Playwright browser-search
as fallback. DuckDuckGo uses HTML scraping (no key required).

Bing: the Bing Web Search API was retired on August 11, 2025. Bing search is
Playwright-based; a legacy API code path remains for any pre-retirement key
that still works, but no key is required or expected.
"""

import logging
import os
import re
import time
from typing import Optional
from urllib.parse import unquote, urlparse, parse_qs, quote_plus

import httpx
from bs4 import BeautifulSoup

from power_win_content.research.models import Source, SourceType

logger = logging.getLogger(__name__)

MAX_RESULTS_PER_PROVIDER = 10
MAX_COMBINED_RESULTS = 15

# Playwright search timeout (short — just enough to load a search results page)
PLAYWRIGHT_NAV_TIMEOUT = 15.0
PLAYWRIGHT_CONTENT_TIMEOUT = 10.0
PLAYWRIGHT_MIN_SEARCH_LENGTH = 200


def _classify_source_type(url: str) -> SourceType:
    """Classify source type based on URL domain."""
    url_lower = url.lower()

    if "power.win" in url_lower:
        return SourceType.FIRST_PARTY

    regulatory_domains = [
        "ukgc.gov.uk", "gamblingcommission.gov.uk",
        "mga.org.mt", "malta gaming authority",
        "spillemyndigheden.dk", "danish gambling authority",
        "spillemyndigheten.se", "swedish gambling authority",
        "autoriteitkansspelen.nl", "dutch gambling authority",
        "gambling.gov.ie", "irish gambling regulator",
        "adm.gov.it", "italian gambling regulator",
        "cmvm.pt", "portuguese regulator",
        "nj.gov", "njev", "new jersey gaming",
        "pennsylvania.gov", "pennsylvania gaming",
        "michigan.gov", "michigan gaming",
    ]
    for domain in regulatory_domains:
        if domain in url_lower:
            return SourceType.REGULATORY

    if any(gov in url_lower for gov in [".gov.", ".gov.uk", ".gc.ca", ".gov.au", "legislation.gov"]):
        return SourceType.GOVERNMENT

    primary_domains = [
        "who.int", "wto.org", "imf.org", "worldbank.org",
        "ecb.europa.eu", "federalreserve.gov", "sec.gov",
        "europa.eu", "parliament.uk", "congress.gov",
    ]
    for domain in primary_domains:
        if domain in url_lower:
            return SourceType.PRIMARY

    authoritative_domains = [
        "reuters.com", "apnews.com", "bloomberg.com",
        "ft.com", "wsj.com", "nytimes.com", "theguardian.com",
        "bbc.com", "bbc.co.uk", "economist.com",
        "nature.com", "science.org", "nejm.org", "bmj.com",
        "cochrane.org", "nih.gov", "cdc.gov", "who.int",
    ]
    for domain in authoritative_domains:
        if domain in url_lower:
            return SourceType.AUTHORITATIVE

    secondary_domains = [
        "casino.org", "askgamblers.com", "casinomeister.com",
        "lcbonline.com", "igamingbusiness.com", "cdcgaming.com",
        "gamblingcompliance.com", "egamingreview.com",
    ]
    for domain in secondary_domains:
        if domain in url_lower:
            return SourceType.SECONDARY

    general_domains = [
        "wikipedia.org", "wikiwand.com",
        "investopedia.com", "nerdwallet.com", "bankrate.com",
        "forbes.com", "businessinsider.com", "techcrunch.com",
    ]
    for domain in general_domains:
        if domain in url_lower:
            return SourceType.GENERAL

    return SourceType.UNKNOWN


def _extract_domain(url: str) -> str:
    """Extract a readable domain name from URL."""
    try:
        domain = re.sub(r"^https?://", "", url)
        domain = re.sub(r"^www\.", "", domain)
        domain = domain.split("/")[0]
        return domain
    except Exception:
        return url


def _normalize_url_for_dedup(url: str) -> str:
    """Normalize URL for deduplication: strip fragments, trailing slashes, lowercase scheme/host."""
    try:
        parsed = urlparse(url)
        normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"
        return normalized
    except Exception:
        return url.lower()


def _is_search_challenge_page(html: str, text: str) -> bool:
    """Detect if a search page shows CAPTCHA/challenge instead of results."""
    combined = (html + " " + text).lower()
    indicators = [
        "unusual traffic",
        "are you a robot",
        "captcha",
        "verify you are human",
        "challenge-platform",
        "not a robot",
        "automated queries",
        "detected unusual traffic",
        "blocked",
        "sorry/unusual-traffic",
        "sorry/how-does-this-work",
        "consent.google",
        "sorry/index.html",
    ]
    return any(ind in combined for ind in indicators)


def _make_source(url: str, query: str, provider: str, title: str = "", snippet: str = "") -> Optional[Source]:
    """Create a Source from search result data."""
    if not url or not url.startswith("http"):
        return None

    source_type = _classify_source_type(url)
    name = _extract_domain(url)
    if title and len(title) > len(name):
        name = title[:100]

    return Source(
        name=name,
        url=url,
        source_type=source_type,
        provider=provider,
        title=title or snippet or None,
        notes=f"Search query: {query}" if snippet else None,
    )


class DuckDuckGoProvider:
    """Search provider using DuckDuckGo HTML scraping (no API key required)."""

    provider_name = "duckduckgo"

    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def search(self, query: str, max_results: int = MAX_RESULTS_PER_PROVIDER) -> list[Source]:
        try:
            params = {"q": query, "kl": "us-en"}
            response = self.client.get("https://html.duckduckgo.com/html/", params=params)
            response.raise_for_status()
            return self._parse_results(response.text, query, max_results)
        except httpx.TimeoutException:
            logger.warning("DuckDuckGo timeout for: %s", query)
            return []
        except httpx.HTTPStatusError as e:
            logger.warning("DuckDuckGo HTTP error for %s: %s", query, e.response.status_code)
            return []
        except httpx.RequestError as e:
            logger.warning("DuckDuckGo request error for %s: %s", query, e)
            return []
        except Exception as e:
            logger.warning("DuckDuckGo unexpected error for %s: %s", query, e)
            return []

    def _parse_results(self, html: str, query: str, max_results: int) -> list[Source]:
        sources = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            result_elements = soup.select(".result__body, .result__snippet, .web-result, .result")

            for elem in result_elements[:max_results]:
                link_elem = elem.select_one("a.result__snippet, a.result__url, a[href^='http'], a.result__snippet")
                if not link_elem:
                    continue

                url = link_elem.get("href")
                if not url:
                    continue

                url = self._decode_ddg_redirect(url)
                if not url or not url.startswith("http"):
                    continue

                title_elem = elem.select_one(".result__title, h2, h3, .result__snippet")
                title = title_elem.get_text(strip=True) if title_elem else None

                snippet_elem = elem.select_one(".result__snippet, .snippet, .description")
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else None

                source = _make_source(url, query, self.provider_name, title=title or "", snippet=snippet or "")
                if source:
                    sources.append(source)

        except Exception as e:
            logger.warning("DuckDuckGo parse error: %s", e)

        return sources

    def _decode_ddg_redirect(self, url: str) -> Optional[str]:
        try:
            if url.startswith("//"):
                url = "https:" + url

            parsed = urlparse(url)
            if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
                query_params = parse_qs(parsed.query)
                if "uddg" in query_params and query_params["uddg"]:
                    encoded_url = query_params["uddg"][0]
                    decoded_url = unquote(encoded_url)
                    return decoded_url
            return url
        except Exception as e:
            logger.debug("Error decoding DDG redirect: %s", e)
            return url


class _BrowserProfile:
    """A realistic browser profile for Playwright search fallback.

    Each profile is internally consistent: user-agent, viewport, locale, and
    headers all match a real browser/OS combination.
    """

    __slots__ = ("user_agent", "viewport", "locale", "accept", "accept_language")

    def __init__(
        self,
        user_agent: str,
        viewport: dict,
        locale: str,
        accept: str,
        accept_language: str,
    ) -> None:
        self.user_agent = user_agent
        self.viewport = viewport
        self.locale = locale
        self.accept = accept
        self.accept_language = accept_language


# A small, controlled set of realistic browser profiles.
# All values are consistent with actual browser releases.
_BROWSER_PROFILES = [
    _BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        accept="text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        accept_language="en-US,en;q=0.9",
    ),
    _BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/18.1 Safari/605.1.15"
        ),
        viewport={"width": 1440, "height": 900},
        locale="en-US",
        accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        accept_language="en-US,en;q=0.9",
    ),
    _BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1366, "height": 768},
        locale="en-US",
        accept="text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        accept_language="en-US,en;q=0.9",
    ),
]

_CAPTCHA_INDICATORS = [
    "unusual traffic",
    "are you a robot",
    "captcha",
    "verify you are human",
    "not a robot",
    "automated queries",
    "detected unusual traffic",
    "blocked",
    "sorry/unusual-traffic",
    "sorry/how-does-this-work",
    "consent.google",
    "sorry/index.html",
    "challenge-platform",
]


def _is_search_challenge_page(html: str, text: str) -> bool:
    """Detect if a search page shows CAPTCHA/challenge instead of results."""
    combined = (html + " " + text).lower()
    return any(ind in combined for ind in _CAPTCHA_INDICATORS)


class _PlaywrightBrowserManager:
    """Playwright browser manager for search fallback.

    Manages a shared Chromium process. Each search attempt creates an
    independent browser context with a rotated realistic profile.
    """

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self._profile_index = 0
        self._playwright = None
        self._browser = None

    def _get_browser(self):
        if self._browser is None:
            if self._playwright is None:
                from playwright.sync_api import sync_playwright
                self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
        return self._browser

    def _next_profile(self) -> _BrowserProfile:
        """Return the next profile in rotation."""
        profile = _BROWSER_PROFILES[self._profile_index % len(_BROWSER_PROFILES)]
        self._profile_index += 1
        return profile

    def fetch_search_page(self, url: str) -> Optional[str]:
        """Navigate to a URL and return the rendered page HTML.

        Creates a fresh browser context with a rotated profile for each
        call so that every search attempt is isolated.
        """
        browser = self._get_browser()
        profile = self._next_profile()
        context = None
        page = None
        try:
            context = browser.new_context(
                user_agent=profile.user_agent,
                viewport=profile.viewport,
                locale=profile.locale,
                extra_http_headers={
                    "Accept": profile.accept,
                    "Accept-Language": profile.accept_language,
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                },
            )
            page = context.new_page()
            page.set_default_timeout(PLAYWRIGHT_NAV_TIMEOUT * 1000)
            page.set_default_navigation_timeout(PLAYWRIGHT_NAV_TIMEOUT * 1000)

            response = page.goto(url, wait_until="domcontentloaded")
            if response is None:
                return None
            if response.status >= 400:
                logger.warning("Playwright search page HTTP %d for %s", response.status, url)
                return None

            # Brief wait for dynamic content to settle
            try:
                page.wait_for_load_state("networkidle", timeout=min(PLAYWRIGHT_CONTENT_TIMEOUT * 1000, 8000))
            except Exception:
                pass

            html = page.content()
            if not html or len(html) < 500:
                return None
            return html

        except Exception as e:
            logger.debug("Playwright search fetch error for %s: %s", url, e)
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

    def close(self) -> None:
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


class GoogleSearchProvider:
    """Google search: Custom Search API primary, Playwright fallback.

    Requires GOOGLE_API_KEY + GOOGLE_CSE_ID for API.
    Falls back to Google search HTML rendered by Playwright when API unavailable.
    """

    provider_name = "google"

    def __init__(self, client: httpx.Client, browser_manager: _PlaywrightBrowserManager) -> None:
        self.client = client
        self.browser_manager = browser_manager
        self.api_key = os.environ.get("GOOGLE_API_KEY", "")
        self.cse_id = os.environ.get("GOOGLE_CSE_ID", "")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.cse_id)

    def search(self, query: str, max_results: int = MAX_RESULTS_PER_PROVIDER) -> list[Source]:
        # Try API first
        if self.is_configured:
            api_results = self._search_api(query, max_results)
            if api_results:
                return api_results
            logger.info("Google API returned no results, falling back to Playwright search")

        # Fallback to Playwright browser search
        return self._search_playwright(query, max_results)

    def _search_api(self, query: str, max_results: int) -> list[Source]:
        try:
            params = {
                "key": self.api_key,
                "cx": self.cse_id,
                "q": query,
                "num": min(max_results, 10),
            }
            response = self.client.get(
                "https://www.googleapis.com/customsearch/v1",
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_api_results(data, query, max_results)
        except httpx.TimeoutException:
            logger.warning("Google API timeout for: %s", query)
            return []
        except httpx.HTTPStatusError as e:
            logger.warning("Google API HTTP error for %s: %s", query, e.response.status_code)
            return []
        except httpx.RequestError as e:
            logger.warning("Google API request error for %s: %s", query, e)
            return []
        except Exception as e:
            logger.warning("Google API unexpected error for %s: %s", query, e)
            return []

    def _search_playwright(self, query: str, max_results: int) -> list[Source]:
        encoded_query = quote_plus(query)
        url = f"https://www.google.com/search?q={encoded_query}&hl=en"

        try:
            html = self.browser_manager.fetch_search_page(url)
            if not html:
                logger.warning("Google Playwright returned no content for: %s", query)
                return []

            text_content = BeautifulSoup(html, "html.parser").get_text()
            if _is_search_challenge_page(html, text_content):
                logger.warning("Google Playwright detected CAPTCHA/challenge for: %s", query)
                return []

            return self._parse_playwright_results(html, query, max_results)
        except Exception as e:
            logger.warning("Google Playwright search error for %s: %s", query, e)
            return []

    def _parse_api_results(self, data: dict, query: str, max_results: int) -> list[Source]:
        sources = []
        for item in data.get("items", [])[:max_results]:
            source = _make_source(
                url=item.get("link", ""),
                query=query,
                provider=f"{self.provider_name}_api",
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
            )
            if source:
                sources.append(source)
        return sources

    def _parse_playwright_results(self, html: str, query: str, max_results: int) -> list[Source]:
        """Parse Google search results HTML rendered by Playwright."""
        sources = []
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Google search result containers
            for result in soup.select("div.g, div[data-hveid]")[:max_results]:
                link_elem = result.select_one("a[href^='http']")
                if not link_elem:
                    continue

                url = link_elem.get("href", "")
                if not url or not url.startswith("http"):
                    continue
                if "google.com" in url:
                    continue

                title_elem = result.select_one("h3")
                title = title_elem.get_text(strip=True) if title_elem else ""

                snippet_elem = result.select_one("div[data-sncf], span.aCOpRe, div.VwiC3b")
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                source = _make_source(url, query, f"{self.provider_name}_playwright", title=title, snippet=snippet)
                if source:
                    sources.append(source)

        except Exception as e:
            logger.warning("Google Playwright parse error: %s", e)

        return sources


class BingSearchProvider:
    """Bing search via Playwright browser rendering.

    The Bing Web Search API was retired on August 11, 2025, so Playwright
    browser search is the primary method. A legacy API path is kept for any
    pre-retirement BING_API_KEY that still works: if such a key is configured
    AND the legacy endpoint returns results, they are used; in every other
    case (no key, API error, timeout, empty results) Bing search falls back
    to Playwright. No key is required or expected.
    """

    provider_name = "bing"

    def __init__(self, client: httpx.Client, browser_manager: _PlaywrightBrowserManager) -> None:
        self.client = client
        self.browser_manager = browser_manager
        self.api_key = os.environ.get("BING_API_KEY", "")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, max_results: int = MAX_RESULTS_PER_PROVIDER) -> list[Source]:
        # Try API first
        if self.is_configured:
            api_results = self._search_api(query, max_results)
            if api_results:
                return api_results
            logger.info("Bing API returned no results, falling back to Playwright search")

        # Fallback to Playwright browser search
        return self._search_playwright(query, max_results)

    def _search_api(self, query: str, max_results: int) -> list[Source]:
        try:
            headers = {
                "Ocp-Apim-Subscription-Key": self.api_key,
                "Accept": "application/json",
            }
            params = {
                "q": query,
                "count": min(max_results, 50),
                "mkt": "en-US",
            }
            response = self.client.get(
                "https://api.bing.microsoft.com/v7.0/search",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_api_results(data, query, max_results)
        except httpx.TimeoutException:
            logger.warning("Bing API timeout for: %s", query)
            return []
        except httpx.HTTPStatusError as e:
            logger.warning("Bing API HTTP error for %s: %s", query, e.response.status_code)
            return []
        except httpx.RequestError as e:
            logger.warning("Bing API request error for %s: %s", query, e)
            return []
        except Exception as e:
            logger.warning("Bing API unexpected error for %s: %s", query, e)
            return []

    def _search_playwright(self, query: str, max_results: int) -> list[Source]:
        encoded_query = quote_plus(query)
        url = f"https://www.bing.com/search?q={encoded_query}&setlang=en"

        try:
            html = self.browser_manager.fetch_search_page(url)
            if not html:
                logger.warning("Bing Playwright returned no content for: %s", query)
                return []

            text_content = BeautifulSoup(html, "html.parser").get_text()
            if _is_search_challenge_page(html, text_content):
                logger.warning("Bing Playwright detected CAPTCHA/challenge for: %s", query)
                return []

            return self._parse_playwright_results(html, query, max_results)
        except Exception as e:
            logger.warning("Bing Playwright search error for %s: %s", query, e)
            return []

    def _parse_api_results(self, data: dict, query: str, max_results: int) -> list[Source]:
        sources = []
        for item in data.get("webPages", {}).get("value", [])[:max_results]:
            source = _make_source(
                url=item.get("url", ""),
                query=query,
                provider=f"{self.provider_name}_api",
                title=item.get("name", ""),
                snippet=item.get("snippet", ""),
            )
            if source:
                sources.append(source)
        return sources

    def _parse_playwright_results(self, html: str, query: str, max_results: int) -> list[Source]:
        """Parse Bing search results HTML rendered by Playwright."""
        sources = []
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Bing search result containers
            for result in soup.select("li.b_algo")[:max_results]:
                link_elem = result.select_one("a[href^='http']")
                if not link_elem:
                    continue

                url = link_elem.get("href", "")
                if not url or not url.startswith("http"):
                    continue
                if "bing.com" in url:
                    continue

                title_elem = result.select_one("h2")
                title = title_elem.get_text(strip=True) if title_elem else ""

                snippet_elem = result.select_one("div.b_caption p, p")
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                source = _make_source(url, query, f"{self.provider_name}_playwright", title=title, snippet=snippet)
                if source:
                    sources.append(source)

        except Exception as e:
            logger.warning("Bing Playwright parse error: %s", e)

        return sources


class WebSearchTool:
    """Multi-engine web search using DuckDuckGo, Google, and Bing.

    DuckDuckGo is always available (no API key required).
    Google/Bing use API as primary, Playwright browser-search as fallback.

    Results from all available providers are merged and deduplicated.
    One provider failing does not terminate research.
    """

    def __init__(
        self,
        timeout: float = 15.0,
        user_agent: str = "PowerWinContentResearcher/1.0 (+https://power.win)",
        max_results: int = 10,
    ) -> None:
        self.timeout = timeout
        self.user_agent = user_agent
        self.max_results = max_results
        self._client: Optional[httpx.Client] = None
        self._browser_manager: Optional[_PlaywrightBrowserManager] = None
        self._providers: Optional[list] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
                follow_redirects=True,
            )
        return self._client

    def _get_browser_manager(self) -> _PlaywrightBrowserManager:
        if self._browser_manager is None:
            self._browser_manager = _PlaywrightBrowserManager()
        return self._browser_manager

    def _get_providers(self) -> list:
        if self._providers is None:
            client = self._get_client()
            bm = self._get_browser_manager()
            self._providers = [
                DuckDuckGoProvider(client),
                GoogleSearchProvider(client, bm),
                BingSearchProvider(client, bm),
            ]
        return self._providers

    def search(self, query: str) -> list[Source]:
        """Search using all configured providers, merge and deduplicate results."""
        all_sources: list[Source] = []
        seen_urls: set[str] = set()

        for provider in self._get_providers():
            try:
                results = provider.search(query, max_results=self.max_results)
                for source in results:
                    if source.url is None:
                        continue
                    normalized = _normalize_url_for_dedup(str(source.url))
                    if normalized not in seen_urls:
                        seen_urls.add(normalized)
                        all_sources.append(source)
            except Exception as e:
                logger.warning("Provider %s failed for query '%s': %s", provider.provider_name, query, e)

        # Limit combined results
        if len(all_sources) > MAX_COMBINED_RESULTS:
            all_sources = all_sources[:MAX_COMBINED_RESULTS]

        return all_sources

    def close(self) -> None:
        """Close the underlying HTTP client and browser."""
        if self._browser_manager is not None:
            self._browser_manager.close()
            self._browser_manager = None
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "WebSearchTool":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
