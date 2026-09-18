import json
from unittest.mock import AsyncMock, Mock

import pytest

from intelligence_content_engine.client import ClientConfig
from intelligence_content_engine.competitors.analyzer import CompetitorAnalyzer
from intelligence_content_engine.competitors.models import (
    CompetitorAnalysis,
    CompetitorSource,
    ContentGap,
    OpportunityType,
    TopicCoverageStatus,
)
from intelligence_content_engine.llm.client import LLMClient
from intelligence_content_engine.research.models import PhaseStatus, Source, SourceType


def _source(name: str, url: str) -> Source:
    return Source(name=name, url=url, source_type=SourceType.SECONDARY)


def _config() -> ClientConfig:
    return ClientConfig(name="Example", domain="example.com")


def _page(scope="FULL", score=0.95) -> str:
    return json.dumps({
        "title": "Guide",
        "search_intent": "informational",
        "coverage_scope": scope,
        "relevance_score": score,
        "headings": ["Heading"],
        "questions_answered": ["What is it?"],
        "entities": ["Entity"],
        "statistics": [],
        "sections": ["Introduction"],
        "unique_angles": ["Checklist"],
        "approximate_word_count": 1000,
    })


def _gaps() -> str:
    return json.dumps({
        "missing_topics": ["Gap"],
        "missing_questions": [],
        "missing_entities": [],
        "missing_comparisons": [],
        "missing_statistics": [],
        "missing_user_concerns": [],
        "missing_angles": [],
        "competitor_topics_absent_from_target": [],
    })


def _analyzer(search, fetcher, llm, max_competitors=5):
    return CompetitorAnalyzer(
        llm_client=llm,
        client_config=_config(),
        search_tool=search,
        fetcher=fetcher,
        max_competitors=max_competitors,
    )


@pytest.mark.asyncio
async def test_competitor_analysis_finds_gaps_and_excludes_target():
    search = Mock()
    search.search = AsyncMock(return_value=[
        _source("A", "https://a.com/guide"),
        _source("B", "https://b.com/guide"),
        _source("Target", "https://example.com/about"),
    ])
    fetcher = Mock()
    fetcher.fetch.return_value = "Useful competitor content"
    llm = Mock(spec=LLMClient)
    llm.generate.side_effect = [_page(), _page(), _gaps()]

    analysis, status = await _analyzer(search, fetcher, llm, 2).analyze("How to evaluate a product")

    assert status == PhaseStatus.SUCCESS
    assert analysis.coverage.status == TopicCoverageStatus.FOUND
    assert analysis.coverage.opportunity_type == OpportunityType.COMPETITIVE_GAP
    assert analysis.gaps.missing_topics == ["Gap"]
    assert all(source.domain != "example.com" for source in analysis.analyzed_sources)


@pytest.mark.asyncio
async def test_competitor_search_failure_is_distinct():
    search = Mock()
    search.search = AsyncMock(side_effect=RuntimeError("search unavailable"))
    fetcher = Mock()
    llm = Mock(spec=LLMClient)

    analysis, status = await _analyzer(search, fetcher, llm).analyze("test")

    assert status == PhaseStatus.FAILED
    assert analysis.coverage.status == TopicCoverageStatus.SEARCH_FAILED


@pytest.mark.asyncio
async def test_competitor_insufficient_data_is_not_whitespace():
    search = Mock()
    search.search = AsyncMock(return_value=[_source("One", "https://one.com/page")])
    fetcher = Mock()
    fetcher.fetch.return_value = "Irrelevant"
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = _page("NOT_RELEVANT", 0.1)

    analysis, status = await _analyzer(search, fetcher, llm).analyze("test")

    assert status == PhaseStatus.DEGRADED
    assert analysis.coverage.status == TopicCoverageStatus.INSUFFICIENT_DATA
    assert analysis.coverage.opportunity_type is None


@pytest.mark.asyncio
async def test_competitor_partial_fetch_failure_degrades():
    search = Mock()
    search.search = AsyncMock(return_value=[
        _source("Good", "https://good.com/page"),
        _source("Bad", "https://bad.com/page"),
    ])
    fetcher = Mock()
    fetcher.fetch.side_effect = ["valid content", None]
    llm = Mock(spec=LLMClient)
    llm.generate.side_effect = [_page(), _gaps()]

    analysis, status = await _analyzer(search, fetcher, llm, 2).analyze("test")

    assert status == PhaseStatus.DEGRADED
    assert analysis.successfully_fetched == 1
    assert analysis.failures == 1


def test_competitor_models_have_safe_defaults():
    analysis = CompetitorAnalysis(topic="Test")
    assert analysis.coverage.status == TopicCoverageStatus.INSUFFICIENT_DATA
    assert analysis.gaps == ContentGap()


def test_coverage_elements_are_aggregated():
    analyzer = _analyzer(Mock(), Mock(), Mock())
    sources = [
        CompetitorSource(
            domain="a.com", url="https://a.com", fetched_successfully=True,
            coverage_scope="FULL", relevance_score=1.0, sections=["Licensing"],
            questions_answered=["How?"], entities=["EntityA"],
        ),
        CompetitorSource(
            domain="b.com", url="https://b.com", fetched_successfully=True,
            coverage_scope="FULL", relevance_score=1.0, sections=["Licensing"],
            questions_answered=["How?"], entities=["EntityB"],
        ),
    ]
    elements = analyzer._build_coverage_elements(sources)
    licensing = next(item for item in elements if item.element == "licensing")
    assert licensing.coverage_count == 2
