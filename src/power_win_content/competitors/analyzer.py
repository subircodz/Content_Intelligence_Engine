"""Discover competitors and determine whether a topic is covered by the market."""

import json
import logging
import re
from typing import Optional
from urllib.parse import urlparse

from power_win_content.client import ClientConfig
from power_win_content.competitors.models import (
    CompetitorAnalysis,
    CompetitorSource,
    ContentGap,
    CoverageAssessment,
    CoverageConfidence,
    CoverageElement,
    OpportunityType,
    TopicCoverageStatus,
)
from power_win_content.llm.client import LLMClient
from power_win_content.research.models import PhaseStatus
from power_win_content.research.tools.web_fetcher import WebFetcher
from power_win_content.research.tools.web_search import WebSearchTool

logger = logging.getLogger(__name__)

_SEARCH_ENGINE_DOMAINS = {
    "duckduckgo.com", "google.com", "bing.com", "yahoo.com", "baidu.com",
    "tiktok.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "reddit.com", "youtube.com", "linkedin.com", "pinterest.com",
}

_DOMAIN_BLACKLIST_SUFFIXES = (
    ".google.com", ".bing.com", ".duckduckgo.com", ".youtube.com",
    ".facebook.com", ".instagram.com", ".twitter.com", ".x.com",
)


def _normalize_domain(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url)
        return (parsed.hostname or "").lower().removeprefix("www.")
    except Exception:
        return None


def _is_excluded_domain(domain: Optional[str], client_config: ClientConfig) -> bool:
    if not domain:
        return True
    if domain == client_config.domain or domain.endswith(f".{client_config.domain}"):
        return True
    if domain in _SEARCH_ENGINE_DOMAINS:
        return True
    return any(domain.endswith(suffix) for suffix in _DOMAIN_BLACKLIST_SUFFIXES)


def _topic_to_queries(topic: str) -> list[str]:
    clean = re.sub(r"\s+", " ", topic.strip())
    return [clean, f"{clean} explained"]


class CompetitorAnalyzer:
    """Build a market coverage assessment before asking for content gaps."""

    def __init__(
        self,
        llm_client: LLMClient,
        client_config: ClientConfig,
        search_tool: Optional[WebSearchTool] = None,
        fetcher: Optional[WebFetcher] = None,
        max_competitors: int = 5,
    ) -> None:
        self.llm_client = llm_client
        self.client_config = client_config
        self.search_tool = search_tool or WebSearchTool(timeout=20.0)
        self.fetcher = fetcher or WebFetcher(timeout=15.0)
        self.max_competitors = max_competitors

    def analyze(self, topic: str) -> tuple[CompetitorAnalysis, PhaseStatus]:
        queries = _topic_to_queries(topic)
        candidate_urls, successful_queries = self._discover_candidate_urls(queries)
        unique_sources = self._select_unique_sources(candidate_urls)
        selected = unique_sources[: self.max_competitors]

        analysis = CompetitorAnalysis(topic=topic)
        analysis.coverage.search_queries_attempted = len(queries)
        analysis.coverage.search_queries_succeeded = successful_queries
        analysis.coverage.candidate_pages_discovered = len(unique_sources)

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
                enriched = self._enrich_source_from_fetch(source, fetched_content, topic)
                llm_calls_used += 1
            else:
                enriched = CompetitorSource(
                    domain=domain,
                    url=source.url,
                    title=source.title,
                    fetched_successfully=False,
                    fetch_failure_reason="analysis budget exceeded",
                )
            analysis.analyzed_sources.append(enriched)

        analysis.domains_analyzed = len(analysis.analyzed_sources)
        analysis.successfully_fetched = sum(1 for s in analysis.analyzed_sources if s.fetched_successfully)
        analysis.failures = len(analysis.analyzed_sources) - analysis.successfully_fetched
        analysis.coverage.successfully_analyzed = analysis.successfully_fetched
        analysis.coverage.failed_analysis = analysis.failures

        relevant_sources = [
            s for s in analysis.analyzed_sources
            if s.fetched_successfully and s.coverage_scope in {"FULL", "PARTIAL"} and s.relevance_score >= 0.5
        ]
        analysis.coverage.relevant_pages_found = len(relevant_sources)
        analysis.coverage.relevant_domains_found = len({s.domain for s in relevant_sources})

        self._assess_coverage(analysis, relevant_sources, successful_queries)
        analysis.gaps = self._extract_gaps(topic, relevant_sources, analysis.coverage)
        analysis.coverage_elements = self._build_coverage_elements(relevant_sources)

        if successful_queries == 0:
            return analysis, PhaseStatus.FAILED
        if analysis.failures > 0 or analysis.coverage.status == TopicCoverageStatus.INSUFFICIENT_DATA:
            return analysis, PhaseStatus.DEGRADED
        return analysis, PhaseStatus.SUCCESS

    def _discover_candidate_urls(self, queries: list[str]) -> tuple[list[CompetitorSource], int]:
        candidates: list[CompetitorSource] = []
        successful_queries = 0
        for query in queries:
            try:
                sources = self.search_tool.search(query)
                successful_queries += 1
            except Exception as exc:
                logger.debug("Competitor search failed for query %r: %s", query, exc)
                continue
            for source in sources:
                domain = _normalize_domain(str(source.url))
                if _is_excluded_domain(domain, self.client_config):
                    continue
                candidates.append(CompetitorSource(
                    domain=domain or "unknown", url=str(source.url), title=source.title
                ))
        return candidates, successful_queries

    def _select_unique_sources(self, candidates: list[CompetitorSource]) -> list[CompetitorSource]:
        seen_urls: set[str] = set()
        seen_domains: set[str] = set()
        selected: list[CompetitorSource] = []
        for source in candidates:
            if source.url in seen_urls or source.domain in seen_domains:
                continue
            seen_urls.add(source.url)
            seen_domains.add(source.domain)
            selected.append(source)
        return selected

    def _fetch_page(self, url: str) -> Optional[str]:
        try:
            content = self.fetcher.fetch(url)
            return content if content and content.strip() else None
        except Exception as exc:
            logger.debug("Competitor page fetch failed for %s: %s", url, exc)
            return None

    def _enrich_source_from_fetch(
        self,
        source: CompetitorSource,
        content: Optional[str],
        topic: str,
    ) -> CompetitorSource:
        if not content or not content.strip():
            source.fetched_successfully = False
            source.fetch_failure_reason = source.fetch_failure_reason or "no usable content"
            return source
        try:
            response = self.llm_client.generate(self._build_analysis_prompt(content, source.title or source.domain, topic))
            parsed = self._parse_json(response)
        except Exception as exc:
            logger.debug("Competitor LLM analysis failed for %s: %s", source.url, exc)
            source.fetched_successfully = False
            source.fetch_failure_reason = "LLM analysis failed"
            return source
        return CompetitorSource(
            domain=source.domain,
            url=source.url,
            title=parsed.get("title") or source.title,
            search_intent=parsed.get("search_intent"),
            coverage_scope=str(parsed.get("coverage_scope") or "NOT_RELEVANT").upper(),
            relevance_score=self._bounded_score(parsed.get("relevance_score")),
            headings=self._clean_list(parsed.get("headings")),
            questions_answered=self._clean_list(parsed.get("questions_answered")),
            entities=self._clean_list(parsed.get("entities")),
            statistics=self._clean_list(parsed.get("statistics")),
            sections=self._clean_list(parsed.get("sections")),
            unique_angles=self._clean_list(parsed.get("unique_angles")),
            approximate_word_count=parsed.get("approximate_word_count") or len(content.split()),
            fetched_successfully=True,
        )

    def _build_analysis_prompt(self, content: str, title: str, topic: str) -> str:
        return (
            "Analyze this candidate competitor page for market coverage of the requested topic.\n\n"
            f"Requested topic: {topic}\n"
            f"Page title: {title}\n\n"
            f"Content (truncated):\n{content[:12000]}\n\n"
            "First determine whether the page meaningfully covers the requested topic. "
            "coverage_scope must be FULL, PARTIAL, or NOT_RELEVANT. "
            "FULL means the page substantially addresses the topic; PARTIAL means it covers a meaningful subset; "
            "NOT_RELEVANT means the page is not a genuine competitor result for this topic. "
            "relevance_score must be between 0 and 1. Extract only information actually present in the page. "
            "Return ONLY valid JSON with title, search_intent, coverage_scope, relevance_score, headings, "
            "questions_answered, entities, statistics, sections, unique_angles, and approximate_word_count."
        )

    def _assess_coverage(
        self,
        analysis: CompetitorAnalysis,
        relevant_sources: list[CompetitorSource],
        successful_queries: int,
    ) -> None:
        if successful_queries == 0:
            analysis.coverage.status = TopicCoverageStatus.SEARCH_FAILED
            analysis.coverage.confidence = CoverageConfidence.LOW
            analysis.coverage.opportunity_type = None
            analysis.coverage.rationale = "All market-search queries failed. No market conclusion is safe."
            return

        if not relevant_sources:
            if analysis.coverage.candidate_pages_discovered >= 5 and analysis.failures == 0:
                analysis.coverage.status = TopicCoverageStatus.NOT_FOUND
                analysis.coverage.confidence = CoverageConfidence.MEDIUM
                analysis.coverage.opportunity_type = OpportunityType.MARKET_WHITESPACE
                analysis.coverage.rationale = (
                    "Multiple candidate competitor pages were discovered and analyzed, but none meaningfully "
                    "covered the requested topic. This is classified as market whitespace rather than a competitive gap."
                )
            else:
                analysis.coverage.status = TopicCoverageStatus.INSUFFICIENT_DATA
                analysis.coverage.confidence = CoverageConfidence.LOW
                analysis.coverage.opportunity_type = None
                analysis.coverage.rationale = (
                    "Search completed, but the evidence set was too small or incomplete to establish either "
                    "market coverage or market whitespace with confidence."
                )
            return

        has_full = any(s.coverage_scope == "FULL" for s in relevant_sources)
        has_partial = any(s.coverage_scope == "PARTIAL" for s in relevant_sources)
        if has_full:
            status = TopicCoverageStatus.FOUND
            rationale = "At least one relevant competitor page substantially covers the requested topic."
        elif has_partial:
            status = TopicCoverageStatus.PARTIALLY_FOUND
            rationale = "Relevant competitor pages cover meaningful parts of the requested topic, but not comprehensively."
        else:
            status = TopicCoverageStatus.INSUFFICIENT_DATA
            rationale = "No sufficiently classified competitor coverage was established."

        analysis.coverage.status = status
        analysis.coverage.opportunity_type = OpportunityType.COMPETITIVE_GAP
        analysis.coverage.confidence = (
            CoverageConfidence.HIGH if len(relevant_sources) >= 3
            else CoverageConfidence.MEDIUM if len(relevant_sources) >= 2
            else CoverageConfidence.LOW
        )
        analysis.coverage.rationale = rationale

    def _extract_gaps(
        self,
        topic: str,
        sources: list[CompetitorSource],
        coverage: CoverageAssessment,
    ) -> ContentGap:
        if not sources or coverage.opportunity_type != OpportunityType.COMPETITIVE_GAP:
            return ContentGap()
        try:
            response = self.llm_client.generate(self._build_gap_prompt(topic, sources))
            parsed = self._parse_json(response)
        except Exception as exc:
            logger.debug("Competitor gap extraction LLM failed: %s", exc)
            return ContentGap()
        return ContentGap(
            missing_topics=self._clean_list(parsed.get("missing_topics")),
            missing_questions=self._clean_list(parsed.get("missing_questions")),
            missing_entities=self._clean_list(parsed.get("missing_entities")),
            missing_comparisons=self._clean_list(parsed.get("missing_comparisons")),
            missing_statistics=self._clean_list(parsed.get("missing_statistics")),
            missing_user_concerns=self._clean_list(parsed.get("missing_user_concerns")),
            missing_angles=self._clean_list(parsed.get("missing_angles")),
            competitor_topics_absent_from_target=self._clean_list(parsed.get("competitor_topics_absent_from_target")),
        )

    def _build_gap_prompt(self, topic: str, sources: list[CompetitorSource]) -> str:
        summaries = []
        for idx, source in enumerate(sources, start=1):
            summaries.append(
                f"{idx}. {source.title or source.domain}\n"
                f"   URL: {source.url}\n"
                f"   Coverage: {source.coverage_scope} ({source.relevance_score:.2f})\n"
                f"   Intent: {source.search_intent or 'unknown'}\n"
                f"   Headings: {', '.join(source.headings[:12]) or 'unknown'}\n"
                f"   Questions: {', '.join(source.questions_answered[:8]) or 'unknown'}\n"
                f"   Entities: {', '.join(source.entities[:10]) or 'unknown'}\n"
                f"   Statistics: {', '.join(source.statistics[:6]) or 'unknown'}\n"
                f"   Unique angles: {', '.join(source.unique_angles[:6]) or 'unknown'}\n"
            )
        return (
            "Identify genuine competitive content opportunities across these relevant competitor pages.\n\n"
            f"Target topic: {topic}\n\n" + "\n".join(summaries) + "\n\n"
            "Do not assume anything about an unpublished target article. Identify market-level omissions, "
            "under-covered questions, entities, comparisons, statistics, user concerns, and angles. "
            "Return ONLY valid JSON with missing_topics, missing_questions, missing_entities, "
            "missing_comparisons, missing_statistics, missing_user_concerns, missing_angles, "
            "and competitor_topics_absent_from_target."
        )

    def _build_coverage_elements(self, sources: list[CompetitorSource]) -> list[CoverageElement]:
        if not sources:
            return []
        counts: dict[str, set[str]] = {}
        for source in sources:
            elements = set(source.sections + source.questions_answered + source.entities)
            for element in elements:
                normalized = re.sub(r"\s+", " ", element.strip()).lower()
                if normalized:
                    counts.setdefault(normalized, set()).add(source.domain)
        total = len({s.domain for s in sources})
        return [
            CoverageElement(
                element=element,
                covered_by_domains=sorted(domains),
                coverage_count=len(domains),
                coverage_percentage=round((len(domains) / total) * 100, 2) if total else 0.0,
            )
            for element, domains in sorted(counts.items(), key=lambda item: (-len(item[1]), item[0]))
        ]

    @staticmethod
    def _parse_json(response: Optional[str]) -> dict:
        if not response or not response.strip():
            return {}
        try:
            data = json.loads(response.strip())
            return data if isinstance(data, dict) else {}
        except Exception:
            logger.debug("Failed to parse LLM JSON response")
            return {}

    @staticmethod
    def _bounded_score(value: object) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _clean_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
