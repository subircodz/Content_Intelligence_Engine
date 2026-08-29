"""Discover competitors and determine whether a topic is covered by the market."""

import difflib
import json
import logging
import re
from typing import Optional
from urllib.parse import urlparse

from intelligence_content_engine.client import ClientConfig
from intelligence_content_engine.competitors.models import (
    CompetitorAnalysis,
    CompetitorSource,
    ContentGap,
    CoverageAssessment,
    CoverageConfidence,
    CoverageElement,
    OpportunityType,
    TopicCoverageStatus,
)
from intelligence_content_engine.llm.client import LLMClient
from intelligence_content_engine.research.models import PhaseStatus
from intelligence_content_engine.research.tools.web_fetcher import WebFetcher
from intelligence_content_engine.research.tools.web_search import WebSearchTool

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

_RELEVANCE_THRESHOLD = 0.50
_MIN_ANALYZED_SOURCES = 5
_MIN_ANALYZED_DOMAINS = 3
_ELEMENT_SIMILARITY_THRESHOLD = 0.78


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


def _normalize_element(value: str) -> str:
    value = re.sub(r"[^\w\s]", " ", value.lower())
    return re.sub(r"\s+", " ", value).strip()


def _element_similarity(left: str, right: str) -> float:
    """Return a conservative semantic-text similarity without an embedding dependency."""
    if left == right:
        return 1.0
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    sequence = difflib.SequenceMatcher(None, left, right).ratio()
    return max(overlap, sequence)


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
        self.minimum_analysis_required = min(_MIN_ANALYZED_SOURCES, max_competitors)
        self.minimum_domains_required = min(_MIN_ANALYZED_DOMAINS, max_competitors)

    async def close(self) -> None:
        """Close the search tool and fetcher."""
        if self.search_tool is not None:
            await self.search_tool.close()
        if self.fetcher is not None:
            self.fetcher.close()

    async def __aenter__(self) -> "CompetitorAnalyzer":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def analyze(self, topic: str) -> tuple[CompetitorAnalysis, PhaseStatus]:
        queries = _topic_to_queries(topic)
        candidate_urls, successful_queries = await self._discover_candidate_urls(queries)
        unique_sources = self._select_unique_sources(candidate_urls)
        selected = unique_sources[: self.max_competitors]

        analysis = CompetitorAnalysis(topic=topic)
        analysis.coverage.search_queries_attempted = len(queries)
        analysis.coverage.search_queries_succeeded = successful_queries
        analysis.coverage.candidate_pages_discovered = len(unique_sources)
        analysis.coverage.minimum_analysis_required = self.minimum_analysis_required
        analysis.coverage.minimum_domains_required = self.minimum_domains_required

        domains_seen: set[str] = set()
        for source in selected:
            domain = _normalize_domain(source.url) or "unknown"
            if domain in domains_seen:
                continue
            domains_seen.add(domain)
            fetched_content = self._fetch_page(source.url)
            enriched = self._enrich_source_from_fetch(source, fetched_content, topic)
            analysis.analyzed_sources.append(enriched)

        analysis.domains_analyzed = len(analysis.analyzed_sources)
        analysis.successfully_fetched = sum(1 for s in analysis.analyzed_sources if s.fetched_successfully)
        analysis.failures = len(analysis.analyzed_sources) - analysis.successfully_fetched
        analysis.coverage.successfully_analyzed = analysis.successfully_fetched
        analysis.coverage.failed_analysis = analysis.failures

        relevant_sources = [
            s for s in analysis.analyzed_sources
            if s.fetched_successfully
            and s.coverage_scope in {"FULL", "PARTIAL"}
            and s.relevance_score >= _RELEVANCE_THRESHOLD
        ]
        analysis.coverage.relevant_pages_found = len(relevant_sources)
        analysis.coverage.relevant_domains_found = len({s.domain for s in relevant_sources})

        self._assess_coverage(analysis, relevant_sources, successful_queries)
        analysis.gaps = self._extract_gaps(topic, relevant_sources, analysis.coverage)
        analysis.coverage_elements = self._build_coverage_elements(relevant_sources)

        if successful_queries == 0:
            return analysis, PhaseStatus.FAILED
        if analysis.coverage.status in {
            TopicCoverageStatus.SEARCH_FAILED,
            TopicCoverageStatus.INSUFFICIENT_DATA,
        } or analysis.failures > 0:
            return analysis, PhaseStatus.DEGRADED
        return analysis, PhaseStatus.SUCCESS

    async def _discover_candidate_urls(self, queries: list[str]) -> tuple[list[CompetitorSource], int]:
        candidates: list[CompetitorSource] = []
        successful_queries = 0
        for query in queries:
            try:
                sources = await self.search_tool.search(query)
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

        sufficient_sample = (
            analysis.coverage.successfully_analyzed >= self.minimum_analysis_required
            and analysis.domains_analyzed >= self.minimum_domains_required
            and analysis.failures == 0
        )

        if not relevant_sources:
            if sufficient_sample:
                analysis.coverage.status = TopicCoverageStatus.NOT_FOUND
                analysis.coverage.confidence = CoverageConfidence.HIGH
                analysis.coverage.opportunity_type = OpportunityType.MARKET_WHITESPACE
                analysis.coverage.rationale = (
                    "A sufficient, successfully analyzed and domain-diverse market sample contained no "
                    "meaningful coverage of the requested topic. This is market whitespace, not a search failure."
                )
            else:
                analysis.coverage.status = TopicCoverageStatus.INSUFFICIENT_DATA
                analysis.coverage.confidence = CoverageConfidence.LOW
                analysis.coverage.opportunity_type = None
                analysis.coverage.rationale = (
                    "Search completed, but the successfully analyzed market sample was insufficient to establish "
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
        relevant_count = len(relevant_sources)
        analysis.coverage.confidence = (
            CoverageConfidence.HIGH if relevant_count >= 3
            else CoverageConfidence.MEDIUM if relevant_count >= 2
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
        """Build a deterministic semantic coverage matrix from extracted competitor elements.

        The LLM extracts page-level elements, but clustering and coverage counts are performed
        by the application. Similar labels such as "payment options" and "payment methods"
        are grouped when their normalized text is sufficiently similar; exact string equality
        is not required.
        """
        if not sources:
            return []

        clusters: list[dict[str, object]] = []
        for source in sources:
            typed_elements = (
                [("section", value) for value in source.sections]
                + [("question", value) for value in source.questions_answered]
                + [("entity", value) for value in source.entities]
            )
            seen_for_source: set[tuple[str, str]] = set()
            for element_type, value in typed_elements:
                normalized = _normalize_element(value)
                if not normalized or (element_type, normalized) in seen_for_source:
                    continue
                seen_for_source.add((element_type, normalized))

                best_cluster = None
                best_score = 0.0
                for cluster in clusters:
                    if cluster["element_type"] != element_type:
                        continue
                    score = _element_similarity(normalized, str(cluster["canonical"]))
                    if score >= _ELEMENT_SIMILARITY_THRESHOLD and score > best_score:
                        best_cluster = cluster
                        best_score = score

                if best_cluster is None:
                    clusters.append({
                        "canonical": normalized,
                        "element_type": element_type,
                        "variants": [value.strip()],
                        "domains": {source.domain},
                    })
                else:
                    best_cluster["variants"].append(value.strip())
                    best_cluster["domains"].add(source.domain)

        total_domains = len({source.domain for source in sources})
        elements: list[CoverageElement] = []
        for cluster in clusters:
            domains = sorted(cluster["domains"])
            elements.append(
                CoverageElement(
                    element=str(cluster["canonical"]),
                    element_type=str(cluster["element_type"]),
                    variants=sorted(set(cluster["variants"])),
                    covered_by_domains=domains,
                    coverage_count=len(domains),
                    coverage_percentage=round((len(domains) / total_domains) * 100, 2) if total_domains else 0.0,
                )
            )

        return sorted(elements, key=lambda item: (-item.coverage_count, item.element_type, item.element))

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
