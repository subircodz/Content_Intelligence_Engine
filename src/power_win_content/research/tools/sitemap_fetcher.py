import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from power_win_content.research.models import Source, SourceType

logger = logging.getLogger(__name__)


@dataclass
class SitemapEntry:
    """A single URL entry from a sitemap."""
    url: str
    lastmod: Optional[str] = None
    changefreq: Optional[str] = None
    priority: Optional[str] = None


class SitemapFetcher:
    """
    Fetches and parses sitemap.xml files for first-party source discovery.
    Supports power.win, docs.power.win, and blog.power.win ecosystems.
    """

    # Known first-party sitemap URLs
    KNOWN_SITEMAPS = {
        "power.win": "https://power.win/sitemap.xml",
        "docs.power.win": "https://docs.power.win/sitemap.xml",
        "blog.power.win": "https://blog.power.win/sitemap.xml",
    }

    def __init__(
        self,
        timeout: float = 15.0,
        user_agent: str = "PowerWinContentResearcher/1.0 (+https://power.win)",
    ) -> None:
        self.timeout = timeout
        self.user_agent = user_agent
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
                follow_redirects=True,
            )
        return self._client

    def fetch_sitemap(self, sitemap_url: str) -> list[SitemapEntry]:
        """Fetch and parse a sitemap.xml, returning list of SitemapEntry objects."""
        try:
            client = self._get_client()
            response = client.get(sitemap_url)
            response.raise_for_status()

            return self._parse_sitemap(response.text, sitemap_url)

        except httpx.TimeoutException:
            logger.warning("Timeout fetching sitemap: %s", sitemap_url)
            return []
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP error fetching sitemap %s: %s", sitemap_url, e.response.status_code)
            return []
        except httpx.RequestError as e:
            logger.warning("Request error fetching sitemap %s: %s", sitemap_url, e)
            return []
        except Exception as e:
            logger.warning("Unexpected error fetching sitemap %s: %s", sitemap_url, e)
            return []

    def _parse_sitemap(self, xml_content: str, base_url: str) -> list[SitemapEntry]:
        """Parse sitemap XML content into SitemapEntry objects."""
        entries = []
        try:
            soup = BeautifulSoup(xml_content, "xml")

            # Handle both regular sitemaps and sitemap indexes
            # Regular sitemap has <url> elements
            urls = soup.find_all("url")

            for url_elem in urls:
                loc = url_elem.find("loc")
                if not loc or not loc.text:
                    continue

                url = loc.text.strip()
                lastmod_elem = url_elem.find("lastmod")
                changefreq_elem = url_elem.find("changefreq")
                priority_elem = url_elem.find("priority")

                entry = SitemapEntry(
                    url=url,
                    lastmod=lastmod_elem.text.strip() if lastmod_elem and lastmod_elem.text else None,
                    changefreq=changefreq_elem.text.strip() if changefreq_elem and changefreq_elem.text else None,
                    priority=priority_elem.text.strip() if priority_elem and priority_elem.text else None,
                )
                entries.append(entry)

            # Check for sitemap index (sitemap contains other sitemaps)
            sitemap_index = soup.find_all("sitemap")
            for sitemap_elem in sitemap_index:
                loc = sitemap_elem.find("loc")
                if loc and loc.text:
                    # Recursively fetch sub-sitemaps
                    sub_entries = self.fetch_sitemap(loc.text.strip())
                    entries.extend(sub_entries)

        except Exception as e:
            logger.warning("Error parsing sitemap: %s", e)

        return entries

    def discover_first_party_sources(self, topic: str = "") -> list[Source]:
        """
        Discover first-party Power.win sources from sitemaps.
        Returns Source objects for all discovered URLs.
        """
        all_sources = []

        # Fetch all known sitemaps
        for domain, sitemap_url in self.KNOWN_SITEMAPS.items():
            logger.info("Fetching sitemap for %s: %s", domain, sitemap_url)
            entries = self.fetch_sitemap(sitemap_url)

            for entry in entries:
                source = self._entry_to_source(entry, domain)
                if source:
                    all_sources.append(source)

        # Filter by topic if provided
        if topic:
            all_sources = self._filter_by_topic(all_sources, topic)

        logger.info("Discovered %d first-party sources", len(all_sources))
        return all_sources

    def _entry_to_source(self, entry: SitemapEntry, domain: str) -> Optional[Source]:
        """Convert a SitemapEntry to a Source object."""
        try:
            parsed = urlparse(entry.url)
            if not parsed.netloc:
                return None

            # Classify source type - all power.win ecosystem = FIRST_PARTY
            source_type = self._classify_first_party_domain(parsed.netloc)

            # Create descriptive name
            path = parsed.path.strip("/")
            if path:
                name = f"{domain} - {path.replace('/', ' > ')}"
            else:
                name = f"{domain} - Home"

            source = Source(
                name=name,
                url=entry.url,
                source_type=source_type,
                title=f"{domain} - {path}" if path else f"{domain} Homepage",
                notes=f"Discovered via sitemap: {entry.lastmod}" if entry.lastmod else "Discovered via sitemap",
            )
            return source

        except Exception as e:
            logger.debug("Error converting sitemap entry to source: %s", e)
            return None

    def _classify_first_party_domain(self, netloc: str) -> SourceType:
        """Classify power.win ecosystem domains as FIRST_PARTY."""
        netloc_lower = netloc.lower()

        if "power.win" in netloc_lower:
            return SourceType.FIRST_PARTY

        return SourceType.UNKNOWN

    def _filter_by_topic(self, sources: list[Source], topic: str) -> list[Source]:
        """Filter sources by relevance to topic keywords.

        Uses a lenient approach - returns all sources if no strong match,
        to avoid filtering out potentially relevant pages.
        """
        topic_lower = topic.lower()
        topic_keywords = set(re.findall(r'\w+', topic_lower))

        # Remove very common words
        stop_words = {"the", "and", "or", "how", "we", "to", "a", "of", "in", "on", "for", "with", "by", "is", "are", "our", "your", "their"}
        topic_keywords = topic_keywords - stop_words

        if not topic_keywords:
            return sources  # No meaningful keywords, return all

        filtered = []
        for source in sources:
            source_text = f"{source.name} {source.title or ''} {source.url}".lower()
            if any(keyword in source_text for keyword in topic_keywords):
                filtered.append(source)

        # If filter removes too many, return all (lenient fallback)
        if len(filtered) < max(3, len(sources) * 0.1):
            return sources

        return filtered

    def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "SitemapFetcher":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()