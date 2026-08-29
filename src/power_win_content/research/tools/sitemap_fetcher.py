import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from power_win_content.client import ClientConfig
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
    """Discover first-party sources from sitemaps configured for the target site."""

    def __init__(
        self,
        client_config: Optional[ClientConfig] = None,
        sitemap_urls: Optional[list[str]] = None,
        timeout: float = 15.0,
        user_agent: str = "ContentIntelligenceEngine/1.0",
    ) -> None:
        self.client_config = client_config
        self.sitemap_urls = tuple(sitemap_urls or (client_config.first_party_sitemaps if client_config else ()))
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
        try:
            response = self._get_client().get(sitemap_url)
            response.raise_for_status()
            return self._parse_sitemap(response.text, sitemap_url)
        except httpx.TimeoutException:
            logger.warning("Timeout fetching sitemap: %s", sitemap_url)
        except httpx.HTTPStatusError as exc:
            logger.warning("HTTP error fetching sitemap %s: %s", sitemap_url, exc.response.status_code)
        except httpx.RequestError as exc:
            logger.warning("Request error fetching sitemap %s: %s", sitemap_url, exc)
        except Exception as exc:
            logger.warning("Unexpected error fetching sitemap %s: %s", sitemap_url, exc)
        return []

    def _parse_sitemap(self, xml_content: str, base_url: str) -> list[SitemapEntry]:
        entries: list[SitemapEntry] = []
        try:
            soup = BeautifulSoup(xml_content, "xml")
            for url_elem in soup.find_all("url"):
                loc = url_elem.find("loc")
                if not loc or not loc.text:
                    continue
                entries.append(SitemapEntry(
                    url=loc.text.strip(),
                    lastmod=(url_elem.find("lastmod").text.strip() if url_elem.find("lastmod") else None),
                    changefreq=(url_elem.find("changefreq").text.strip() if url_elem.find("changefreq") else None),
                    priority=(url_elem.find("priority").text.strip() if url_elem.find("priority") else None),
                ))

            for sitemap_elem in soup.find_all("sitemap"):
                loc = sitemap_elem.find("loc")
                if loc and loc.text:
                    entries.extend(self.fetch_sitemap(loc.text.strip()))
        except Exception as exc:
            logger.warning("Error parsing sitemap: %s", exc)
        return entries

    def discover_first_party_sources(self, topic: str = "") -> list[Source]:
        if not self.client_config or not self.sitemap_urls:
            return []

        all_sources: list[Source] = []
        for sitemap_url in self.sitemap_urls:
            for entry in self.fetch_sitemap(sitemap_url):
                source = self._entry_to_source(entry)
                if source:
                    all_sources.append(source)

        if topic:
            all_sources = self._filter_by_topic(all_sources, topic)
        return all_sources

    def _entry_to_source(self, entry: SitemapEntry) -> Optional[Source]:
        try:
            parsed = urlparse(entry.url)
            if not parsed.netloc or not self.client_config.is_first_party_url(entry.url):
                return None
            host = parsed.hostname or self.client_config.domain
            path = parsed.path.strip("/")
            name = f"{host} - {path.replace('/', ' > ')}" if path else f"{host} - Home"
            return Source(
                name=name,
                url=entry.url,
                source_type=SourceType.FIRST_PARTY,
                title=f"{host} - {path}" if path else f"{host} Homepage",
                notes=f"Discovered via sitemap: {entry.lastmod}" if entry.lastmod else "Discovered via sitemap",
            )
        except Exception as exc:
            logger.debug("Error converting sitemap entry to source: %s", exc)
            return None

    def _filter_by_topic(self, sources: list[Source], topic: str) -> list[Source]:
        keywords = set(re.findall(r"\w+", topic.lower()))
        keywords -= {"the", "and", "or", "how", "we", "to", "a", "of", "in", "on", "for", "with", "by", "is", "are", "our", "your", "their"}
        if not keywords:
            return sources
        filtered = [s for s in sources if any(k in f"{s.name} {s.title or ''} {s.url}".lower() for k in keywords)]
        return filtered if len(filtered) >= max(3, len(sources) * 0.1) else sources

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "SitemapFetcher":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
