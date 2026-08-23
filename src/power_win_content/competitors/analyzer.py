"""Discover and analyze competitor pages for content gap analysis."""

import logging
import re
from typing import Optional
from urllib.parse import urlparse

import httpx

from power_win_content.competitors.models import CompetitorAnalysis, CompetitorSource, ContentGap
from power_win_content.llm.client import LLMClient
from power_win_content.research.models import PhaseStatus
from power_win_content.research.tools.web_fetcher import WebFetcher
from power_win_content.research.tools.web_search import WebSearchTool

logger = logging.getLogger(__name__)

_EXCLUDED_DOMAINS = {
    "power.win",
    "www.power.win",
    "docs.power.win",
    "blog.power.win",
    "duckduckgo.com",
    "google.com",
    "bing.com",
    "yahoo.com",
    "baidu.com",
    "tiktok.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "reddit.com",
    "youtube.com",
    "linkedin.com",
    "pinterest.com",
}

_DOMAIN_BLACKLIST_SUFFIXES = (
    ".google.com",
    ".bing.com",
    ".duckduckgo.com",
    ".youtube.com",
    ".facebook.com",
    ".instagram.com",
    ".twitter.com",
    ".x.com",
)


def _normalize_domain(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url)
        return (parsed.hostname or "").lower().lstrip("www.")
    except Exception:
        return None


def _is_excluded_domain(domain: Optional[str]) -> bool:
    if not domain:
        return True
    if domain in _EXCLUDED_DOMAINS:
        return True
    for suffix in _DOMAIN_BLACKLIST_SUFFIXES:
        if domain.endswith(suffix):
            return True
    return False


def _topic_to_queries(topic: str) -> list[str]:
    clean = re.sub(r"\s+", " ", topic.strip())
    return [
        f"{clean}",
        f"{clean} explained",
    ]


class CompetitorAnalyzer:
    def __init__(
        self,
        llm_client: LLMClient,
        search_tool: Optional[WebSearchTool] = None,
        fetcher: Optional[WebFetcher] = None,
        max_competitors: int = 5,
    ) -> None:
        self.llm_client = llm_client
        self.search_tool = search_tool or WebSearchTool(timeout=20.0)
        self.fetcher = fetcher or WebFetcher(timeout=15.0)
        self.max_competitors = max_competitors

    def analyze(self, topic: str) -> tuple[CompetitorAnalysis, PhaseStatus]:
        candidate_urls = self._discover_candidate_urls(topic)
        unique_sources = self._select_unique_sources(candidate_urls)
        selected = unique_sources[: self.max_competitors]

        analysis = CompetitorAnalysis(topic=topic)
        domains_seen: set[str] = set()
        llm_calls_used = 0
        llm_call_budget = self.max_competitors + 1

        for source in selected:
            domain = _normalize_domain(source.url) or "unknown"
            if domain in domains_seen:
                continue
            domains_seen.add(domain)

            fetched_content = self._fetch_page(source.url)
            if llm_calls_used < llm_call_budget:
                enriched = self._enrich_source_from_fetch(source, fetched_content)
                llm_calls_used += 1
            else:
                enriched = CompetitorSource(
                    domain=domain,
                    url=source.url,
                    title=source.title,
                    fetched_successfully=False,
                    fetch_failure_reason="budget exceeded",
                )
            analysis.analyzed_sources.append(enriched)

        for source in analysis.analyzed_sources:
            if source.fetched_successfully:
                analysis.successfully_fetched += 1
            else:
                analysis.failures += 1

        analysis.domains_analyzed = len(analysis.analyzed_sources)

        # Only extract gaps from successfully analyzed sources — failed sources
        # have empty coverage data that would produce misleading gap results.
        successful_sources = [s for s in analysis.analyzed_sources if s.fetched_successfully]
        analysis.gaps = self._extract_gaps(topic, successful_sources)

        # SUCCESS only when sources were found AND every one succeeded.
        # Any failure (partial or total) means degraded competitor intelligence.
        if analysis.domains_analyzed == 0 or analysis.failures > 0:
            phase_status = PhaseStatus.DEGRADED
        else:
            phase_status = PhaseStatus.SUCCESS

        return analysis, phase_status

    def _discover_candidate_urls(self, topic: str) -> list[CompetitorSource]:
        queries = _topic_to_queries(topic)
        candidates: list[CompetitorSource] = []

        for query in queries:
            try:
                sources = self.search_tool.search(query)
            except Exception as exc:
                logger.debug("Competitor search failed for query %r: %s", query, exc)
                continue

            for source in sources:
                domain = _normalize_domain(str(source.url))
                if _is_excluded_domain(domain):
                    continue
                candidates.append(
                    CompetitorSource(
                        domain=domain or "unknown",
                        url=str(source.url),
                        title=source.title,
                    )
                )

        return candidates

    def _select_unique_sources(self, candidates: list[CompetitorSource]) -> list[CompetitorSource]:
        seen_urls: set[str] = set()
        selected: list[CompetitorSource] = []

        for source in candidates:
            url = source.url
            if url in seen_urls:
                continue
            seen_urls.add(url)
            selected.append(source)

        return selected

    def _fetch_page(self, url: str) -> Optional[str]:
        try:
            content = self.fetcher.fetch(url)
            if not content or not content.strip():
                return None
            return content
        except Exception as exc:
            logger.debug("Competitor page fetch failed for %s: %s", url, exc)
            return None

    def _enrich_source_from_fetch(
        self,
        source: CompetitorSource,
        content: Optional[str],
    ) -> CompetitorSource:
        if not content or not content.strip():
            source.fetched_successfully = False
            source.fetch_failure_reason = source.fetch_failure_reason or "no usable content"
            return source

        prompt = self._build_analysis_prompt(content, source.title or source.domain)
        try:
            response = self.llm_client.generate(prompt)
        except Exception as exc:
            logger.debug("Competitor LLM analysis failed for %s: %s", source.url, exc)
            source.fetched_successfully = False
            source.fetch_failure_reason = "LLM analysis failed"
            return source

        parsed = self._parse_analysis_response(response)

        return CompetitorSource(
            domain=source.domain,
            url=source.url,
            title=parsed.get("title") or source.title,
            search_intent=parsed.get("search_intent"),
            headings=self._clean_list(parsed.get("headings")),
            questions_answered=self._clean_list(parsed.get("questions_answered")),
            entities=self._clean_list(parsed.get("entities")),
            statistics=self._clean_list(parsed.get("statistics")),
            sections=self._clean_list(parsed.get("sections")),
            unique_angles=self._clean_list(parsed.get("unique_angles")),
            approximate_word_count=parsed.get("approximate_word_count") or len(content.split()),
            fetched_successfully=True,
            fetch_failure_reason=None,
        )

    def _build_analysis_prompt(self, content: str, title: str) -> str:
        return (
            "Analyze this competitor page content. Extract structured intelligence.\n\n"
            f"Page title: {title}\n\n"
            f"Content (truncated):\n{content[:12000]}\n\n"
            "Return ONLY valid JSON:\n"
            "{\n"
            '  "title": "...",\n'
            '  "search_intent": "informational|commercial|transactional|navigational|mixed",\n'
            '  "headings": ["...", "..."],\n'
            '  "questions_answered": ["...", "..."],\n'
            '  "entities": ["...", "..."],\n'
            '  "statistics": ["...", "..."],\n'
            '  "sections": ["...", "..."],\n'
            '  "unique_angles": ["...", "..."]\n'
            "}\n\n"
            "Rules:\n"
            "- Extract only information actually present in the page.\n"
            "- Do not invent competitor information.\n"
            "- Keep lists practical and specific."
        )

    def _parse_analysis_response(self, response: Optional[str]) -> dict:
        if not response or not response.strip():
            return {}
        try:
            data = __import__("json").loads(response.strip())
            return data if isinstance(data, dict) else {}
        except Exception:
            logger.debug("Failed to parse competitor analysis response")
            return {}

    def _extract_gaps(self, topic: str, sources: list[CompetitorSource]) -> ContentGap:
        if not sources:
            return ContentGap()

        prompt = self._build_gap_prompt(topic, sources)
        try:
            response = self.llm_client.generate(prompt)
        except Exception as exc:
            logger.debug("Competitor gap extraction LLM failed: %s", exc)
            return ContentGap()

        parsed = self._parse_gap_response(response)

        return ContentGap(
            missing_topics=self._clean_list(parsed.get("missing_topics")),
            missing_questions=self._clean_list(parsed.get("missing_questions")),
            missing_entities=self._clean_list(parsed.get("missing_entities")),
            missing_comparisons=self._clean_list(parsed.get("missing_comparisons")),
            missing_statistics=self._clean_list(parsed.get("missing_statistics")),
            missing_user_concerns=self._clean_list(parsed.get("missing_user_concerns")),
            missing_angles=self._clean_list(parsed.get("missing_angles")),
            competitor_topics_absent_from_ours=self._clean_list(parsed.get("competitor_topics_absent_from_ours")),
        )

    def _build_gap_prompt(self, topic: str, sources: list[CompetitorSource]) -> str:
        competitor_summaries = []
        for idx, source in enumerate(sources, start=1):
            competitor_summaries.append(
                f"{idx}. {source.title or source.domain}\n"
                f"   URL: {source.url}\n"
                f"   Intent: {source.search_intent or 'unknown'}\n"
                f"   Headings: {', '.join(source.headings[:12]) or 'unknown'}\n"
                f"   Questions answered: {', '.join(source.questions_answered[:8]) or 'unknown'}\n"
                f"   Entities: {', '.join(source.entities[:10]) or 'unknown'}\n"
                f"   Stats/data: {', '.join(source.statistics[:6]) or 'unknown'}\n"
                f"   Unique angles: {', '.join(source.unique_angles[:6]) or 'unknown'}\n"
            )

        return (
            "You are a content strategist performing competitor content gap analysis.\n\n"
            f"Requested Power.win article topic: {topic}\n\n"
            "Competitor pages discovered and analyzed:\n\n"
            + "\n".join(competitor_summaries)
            + "\n\n"
            "Identify what competitors cover that the requested Power.win article/topic likely does not yet cover.\n"
            "Return ONLY valid JSON:\n"
            "{\n"
            '  "missing_topics": ["...", "..."],\n'
            '  "missing_questions": ["...", "..."],\n'
            '  "missing_entities": ["...", "..."],\n'
            '  "missing_comparisons": ["...", "..."],\n'
            '  "missing_statistics": ["...", "..."],\n'
            '  "missing_user_concerns": ["...", "..."],\n'
            '  "missing_angles": ["...", "..."],\n'
            '  "competitor_topics_absent_from_ours": ["...", "..."]\n'
            "}\n\n"
            "Rules:\n"
            "- Focus on useful editorial opportunities, not copyable content.\n"
            "- Do not invent research-backed facts; only identify coverage gaps.\n"
            "- Keep recommendations specific and actionable for Power.win."
        )

    def _parse_gap_response(self, response: Optional[str]) -> dict:
        if not response or not response.strip():
            return {}
        try:
            data = __import__("json").loads(response.strip())
            return data if isinstance(data, dict) else {}
        except Exception:
            logger.debug("Failed to parse competitor gap response")
            return {}

    @staticmethod
    def _clean_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                cleaned.append(item.strip())
        return cleaned
