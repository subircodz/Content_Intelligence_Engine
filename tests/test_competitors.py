import json
from unittest.mock import Mock

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
from intelligence_content_engine.research.tools.web_fetcher import WebFetcher
from intelligence_content_engine.research.tools.web_search import WebSearchTool


def _make_source(name: str, url: str) -> Source:
    return Source(name=name, url=url, source_type=SourceType.SECONDARY)


def _client_config() -> ClientConfig:
    return ClientConfig(name="Example", domain="example.com")


def _page_response(scope: str = "FULL", score: float = 0.95) -> str:
    return json.dumps({
        "title": "Competitor Guide",
        "search_intent": "informational",
        "coverage_scope": scope,
        "relevance_score": score,
        "headings": ["Heading"],
        "questions_answered": ["What is it?"],
        "entities": ["EntityX"],
        "statistics": ["A statistic"],
        "sections": ["Introduction"],
        "unique_angles": ["Checklist"],
        "approximate_word_count": 1000,
    })


def _gap_response() -> str:
    return json.dumps({
        "missing_topics": ["Licensing verification"],
        "missing_questions": ["How are competitors evaluated?"],
        "missing_entities": ["EntityY"],
        "missing_comparisons": [],
        "missing_statistics": [],
        "missing_user_concerns": ["Safety"],
        "missing_angles": ["Practical checklist"],
        "competitor_topics_absent_from_target": [],
    })


class TestCompetitorModels:
    def test_competitor_source_defaults(self) -> None:
        source = CompetitorSource(domain="example.org", url="https://example.org/guide")
        assert source.fetched_successfully is False
        assert source.coverage_scope == "UNKNOWN"
        assert source.relevance_score == 0.0

    def test_competitor_analysis_default_coverage(self) -> None:
        analysis = CompetitorAnalysis(topic="Test Topic")
        assert analysis.coverage.status == TopicCoverageStatus.INSUFFICIENT_DATA
        assert analysis.coverage.opportunity_type is None
        assert analysis.gaps == ContentGap()


class TestCompetitorAnalyzer:
    def test_case_1_topic_found_and_gaps_are_extracted(self) -> None:
        search = Mock(spec=WebSearchTool)
        fetcher = Mock(spec=WebFetcher)
        llm = Mock(spec=LLMClient)

        search.search.return_value = [
            _make_source("Competitor A", "https://a.com/guide"),
            _make_source("Competitor B", "https://b.com/guide"),
            _make_source("Target", "https://example.com/about"),
        ]
        fetcher.fetch.return_value = "Useful competitor content"
        llm.generate.side_effect = [_page_response(), _page_response(), _gap_response()]

        analyzer = CompetitorAnalyzer(
            llm_client=llm,
            client_config=_client_config(),
            search_tool=search,
            fetcher=fetcher,
            max_competitors=2,
        )
        analysis, status = analyzer.analyze("How to evaluate a product")

        assert status == PhaseStatus.SUCCESS
        assert analysis.coverage.status == TopicCoverageStatus.FOUND
        assert analysis.coverage.opportunity_type == OpportunityType.COMPETITIVE_GAP
        assert analysis.coverage.relevant_domains_found == 2
        assert analysis.gaps.missing_topics == ["Licensing verification"]
        assert all(source.domain != "example.com" for source in analysis.analyzed_sources)

    def test_case_2_market_whitespace_requires_multiple_analyzed_candidates(self) -> None:
        search = Mock(spec=WebSearchTool)
        fetcher = Mock(spec=WebFetcher)
        llm = Mock(spec=LLMClient)

        search.search.side_effect = [
            [_make_source(f"Candidate {i}", f"https://candidate{i}.com/page") for i in range(1, 4)],
            [_make_source(f"Candidate {i}", f"https://candidate{i}.com/page") for i in range(4, 7)],
        ]
        fetcher.fetch.return_value = "Irrelevant content"
        llm.generate.side_effect = [_page_response("NOT_RELEVANT", 0.1) for _ in range(5)]

        analyzer = CompetitorAnalyzer(
            llm_client=llm,
            client_config=_client_config(),
            search_tool=search,
            fetcher=fetcher,
            max_competitors=5,
        )
        analysis, status = analyzer.analyze("A highly specific underserved topic")

        assert status == PhaseStatus.SUCCESS
        assert analysis.coverage.status == TopicCoverageStatus.NOT_FOUND
        assert analysis.coverage.opportunity_type == OpportunityType.MARKET_WHITESPACE
        assert analysis.coverage.relevant_pages_found == 0
        assert analysis.gaps == ContentGap()

    def test_insufficient_data_is_not_treated_as_whitespace(self) -> None:
        search = Mock(spec=WebSearchTool)
        fetcher = Mock(spec=WebFetcher)
        llm = Mock(spec=LLMClient)
        search.search.return_value = [_make_source("One", "https://one.com/page")]
        fetcher.fetch.return_value = "Irrelevant content"
        llm.generate.return_value = _page_response("NOT_RELEVANT", 0.1)

        analyzer = CompetitorAnalyzer(
            llm_client=llm,
            client_config=_client_config(),
            search_tool=search,
            fetcher=fetcher,
            max_competitors=5,
        )
        analysis, status = analyzer.analyze("test topic")

        assert status == PhaseStatus.DEGRADED
        assert analysis.coverage.status == TopicCoverageStatus.INSUFFICIENT_DATA
        assert analysis.coverage.opportunity_type is None

    def test_search_failure_is_distinct_from_no_coverage(self) -> None:
        search = Mock(spec=WebSearchTool)
        fetcher = Mock(spec=WebFetcher)
        llm = Mock(spec=LLMClient)
        search.search.side_effect = RuntimeError("search unavailable")

        analyzer = CompetitorAnalyzer(
            llm_client=llm,
            client_config=_client_config(),
            search_tool=search,
            fetcher=fetcher,
        )
        analysis, status = analyzer.analyze("test topic")

        assert status == PhaseStatus.FAILED
        assert analysis.coverage.status == TopicCoverageStatus.SEARCH_FAILED
        assert analysis.coverage.opportunity_type is None

    def test_partial_source_failure_degrades_analysis(self) -> None:
        search = Mock(spec=WebSearchTool)
        fetcher = Mock(spec=WebFetcher)
        llm = Mock(spec=LLMClient)
        search.search.return_value = [
            _make_source("Good", "https://good.com/page"),
            _make_source("Bad", "https://bad.com/page"),
        ]
        fetcher.fetch.side_effect = ["valid content", None]
        llm.generate.side_effect = [_page_response(), _gap_response()]

        analyzer = CompetitorAnalyzer(
            llm_client=llm,
            client_config=_client_config(),
            search_tool=search,
            fetcher=fetcher,
            max_competitors=2,
        )
        analysis, status = analyzer.analyze("test topic")

        assert status == PhaseStatus.DEGRADED
        assert analysis.successfully_fetched == 1
        assert analysis.failures == 1
        assert analysis.coverage.status == TopicCoverageStatus.FOUND

    def test_coverage_elements_create_market_matrix_data(self) -> None:
        analyzer = CompetitorAnalyzer(
            llm_client=Mock(spec=LLMClient),
            client_config=_client_config(),
        )
        sources = [
            CompetitorSource(
                domain="a.com", url="https://a.com", fetched_successfully=True,
                coverage_scope="FULL", relevance_score=1.0,
                sections=["Licensing", "Security"], questions_answered=["How?"], entities=["EntityA"],
            ),
            CompetitorSource(
                domain="b.com", url="https://b.com", fetched_successfully=True,
                coverage_scope="FULL", relevance_score=1.0,
                sections=["Licensing"], questions_answered=["How?"], entities=["EntityB"],
            ),
        ]

        elements = analyzer._build_coverage_elements(sources)
        licensing = next(item for item in elements if item.element == "licensing")
        assert licensing.coverage_count == 2
        assert licensing.coverage_percentage == 100.0


class TestStrategyCoverageIntegration:
    def test_brief_receives_market_coverage(self) -> None:
        from unittest.mock import Mock
        from intelligence_content_engine.strategy.strategist import ContentStrategist

        llm = Mock(spec=LLMClient)
        llm.generate.side_effect = [
            json.dumps({"primary_topic": "Test", "search_intent": "informational", "primary_keyword": "test", "recommended_title": "Test"}),
            json.dumps({}),
            json.dumps({}),
        ]

        research = Mock()
        research.first_party_facts = []
        research.external_facts = []
        research.unsupported_claims = []
        research.research_gaps = []
        research.conflicting_information = []

        competitor = CompetitorAnalysis(topic="Test")
        competitor.coverage.status = TopicCoverageStatus.FOUND
        competitor.coverage.opportunity_type = OpportunityType.COMPETITIVE_GAP
        competitor.gaps = ContentGap(missing_topics=["Gap A"])

        brief, _ = ContentStrategist(llm).create_brief("Test", research, competitor)

        assert brief.market_coverage.status == TopicCoverageStatus.FOUND
        assert brief.competitor_gaps.missing_topics == ["Gap A"]
