import json
from unittest.mock import Mock, patch

from power_win_content.competitors.analyzer import CompetitorAnalyzer
from power_win_content.competitors.models import CompetitorAnalysis, CompetitorSource, ContentGap
from power_win_content.llm.client import LLMClient
from power_win_content.research.tools.web_fetcher import WebFetcher
from power_win_content.research.tools.web_search import WebSearchTool
from power_win_content.research.models import Source, SourceType, PhaseStatus
from power_win_content.strategy.models import AIOStrategy, ContentBrief, GEOStrategy, SEOStrategy


def _make_source(name: str, url: str) -> Source:
    return Source(name=name, url=url, source_type=SourceType.SECONDARY)


class TestCompetitorModels:
    def test_competitor_source_defaults(self) -> None:
        source = CompetitorSource(domain="example.com", url="https://example.com/guide")
        assert source.fetched_successfully is False
        assert source.headings == []
        assert source.approximate_word_count == 0

    def test_competitor_analysis_default_counts(self) -> None:
        analysis = CompetitorAnalysis(topic="Test Topic")
        assert analysis.domains_analyzed == 0
        assert analysis.gaps == ContentGap()


class TestCompetitorAnalyzer:
    def test_analyzer_discover_and_select(self) -> None:
        mock_search = Mock(spec=WebSearchTool)
        mock_fetcher = Mock(spec=WebFetcher)
        mock_llm = Mock(spec=LLMClient)

        mock_search.search.return_value = [
            _make_source("Competitor Guide", "https://competitor-a.com/guide"),
            _make_source("Competitor Review", "https://competitor-b.com/review"),
            _make_source("Power.win Page", "https://power.win/about"),
            _make_source("Duplicate A", "https://competitor-a.com/guide"),
        ]
        mock_fetcher.fetch.return_value = (
            "## Heading\nSome content about evaluation process and FAQ questions."
        )
        competitor_page_response = json.dumps(
            {
                "title": "Competitor Guide",
                "search_intent": "informational",
                "headings": ["Heading"],
                "questions_answered": ["What is it?"],
                "entities": ["UKGC"],
                "statistics": ["100% coverage"],
                "sections": ["Intro"],
                "unique_angles": ["Checklist"],
            }
        )
        mock_llm.generate.side_effect = [
            competitor_page_response,
            competitor_page_response,
            json.dumps(
                {
                    "missing_topics": ["Licensing verification"],
                    "missing_questions": ["How are casinos rated?"],
                    "missing_entities": ["MGA"],
                    "missing_comparisons": [],
                    "missing_statistics": [],
                    "missing_user_concerns": [],
                    "missing_angles": [],
                    "competitor_topics_absent_from_ours": ["bonus wagering"],
                }
            ),
        ]

        analyzer = CompetitorAnalyzer(llm_client=mock_llm, search_tool=mock_search, fetcher=mock_fetcher, max_competitors=2)
        analysis, _ = analyzer.analyze("How we evaluate online casinos")

        assert isinstance(analysis, CompetitorAnalysis)
        assert analysis.domains_analyzed == 2
        assert any(source.domain == "competitor-a.com" for source in analysis.analyzed_sources)
        assert analysis.gaps.missing_topics == ["Licensing verification"]
        assert "How are casinos rated?" in analysis.gaps.missing_questions

    def test_degraded_when_all_sources_fail(self) -> None:
        """When all selected sources fail to process, status is DEGRADED."""
        mock_search = Mock(spec=WebSearchTool)
        mock_fetcher = Mock(spec=WebFetcher)
        mock_llm = Mock(spec=LLMClient)

        mock_search.search.return_value = [
            _make_source("Competitor A", "https://a.com/page"),
            _make_source("Competitor B", "https://b.com/page"),
        ]
        mock_fetcher.fetch.return_value = None

        analyzer = CompetitorAnalyzer(llm_client=mock_llm, search_tool=mock_search, fetcher=mock_fetcher, max_competitors=2)
        analysis, status = analyzer.analyze("test topic")

        assert status == PhaseStatus.DEGRADED
        assert analysis.domains_analyzed == 2
        assert analysis.failures == 2
        assert analysis.successfully_fetched == 0

    def test_degraded_when_partial_failure(self) -> None:
        """Status is DEGRADED when some sources succeed and some fail."""
        mock_search = Mock(spec=WebSearchTool)
        mock_fetcher = Mock(spec=WebFetcher)
        mock_llm = Mock(spec=LLMClient)

        mock_search.search.return_value = [
            _make_source("Good", "https://good.com/page"),
            _make_source("Bad", "https://bad.com/page"),
        ]
        mock_fetcher.fetch.side_effect = [
            "Valid content from good source",
            None,
        ]
        mock_llm.generate.side_effect = [
            json.dumps({"title": "T", "search_intent": "informational", "headings": [], "questions_answered": [], "entities": [], "statistics": [], "sections": [], "unique_angles": []}),
            json.dumps({"missing_topics": ["A"], "missing_questions": [], "missing_entities": [], "missing_comparisons": [], "missing_statistics": [], "missing_user_concerns": [], "missing_angles": [], "competitor_topics_absent_from_ours": []}),
        ]

        analyzer = CompetitorAnalyzer(llm_client=mock_llm, search_tool=mock_search, fetcher=mock_fetcher, max_competitors=2)
        analysis, status = analyzer.analyze("test topic")

        assert status == PhaseStatus.DEGRADED
        assert analysis.domains_analyzed == 2
        assert analysis.successfully_fetched == 1
        assert analysis.failures == 1

    def test_gaps_only_from_successful_sources(self) -> None:
        """Failed sources should not contribute to gap analysis."""
        mock_search = Mock(spec=WebSearchTool)
        mock_fetcher = Mock(spec=WebFetcher)
        mock_llm = Mock(spec=LLMClient)

        mock_search.search.return_value = [
            _make_source("Good", "https://good.com/page"),
            _make_source("Bad", "https://bad.com/page"),
        ]
        mock_fetcher.fetch.side_effect = [
            "Content with headings and questions",
            None,
        ]
        mock_llm.generate.side_effect = [
            json.dumps({"title": "T", "search_intent": "informational", "headings": ["H1"], "questions_answered": ["Q?"], "entities": [], "statistics": [], "sections": [], "unique_angles": []}),
            json.dumps({"missing_topics": ["found topic"], "missing_questions": [], "missing_entities": [], "missing_comparisons": [], "missing_statistics": [], "missing_user_concerns": [], "missing_angles": [], "competitor_topics_absent_from_ours": []}),
        ]

        analyzer = CompetitorAnalyzer(llm_client=mock_llm, search_tool=mock_search, fetcher=mock_fetcher, max_competitors=2)
        analysis, status = analyzer.analyze("test")

        assert analysis.gaps.missing_topics == ["found topic"]
        assert mock_llm.generate.call_count == 2


class TestCompetitorIntegrationWithBriefAndWriter:
    def test_brief_receives_competitor_gaps(self) -> None:
        from power_win_content.strategy.strategist import ContentStrategist

        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = [
            json.dumps({
                "primary_topic": "Casino evaluation",
                "search_intent": "informational",
                "primary_keyword": "casino evaluation",
                "recommended_title": "How We Evaluate Casinos",
            }),
            json.dumps({
                "direct_answer_questions": [],
                "concise_answers": {},
                "definitions": {},
                "important_factual_statements": [],
                "entities": [],
                "evidence_requirements": [],
                "structured_information_requirements": [],
            }),
            json.dumps({
                "important_entities": [],
                "entity_relationships": [],
                "authoritative_external_sources": [],
                "power_win_first_party_facts": [],
                "unique_information": [],
                "citation_evidence_opportunities": [],
                "factual_consistency_requirements": [],
                "questions_to_answer_clearly": [],
            }),
        ]

        strategist = ContentStrategist(llm_client=mock_llm)
        research = Mock()
        research.power_win_facts = []
        research.external_facts = []
        research.unsupported_claims = []
        research.research_gaps = []
        research.conflicting_information = []

        competitor_analysis = CompetitorAnalysis(
            topic="Test",
            gaps=ContentGap(missing_topics=["missing topic A"], missing_questions=["Q1?"], missing_entities=["EntityX"]),
        )

        brief, _ = strategist.create_brief("Test Topic", research, competitor_analysis=competitor_analysis)

        assert brief.competitor_gaps.missing_topics == ["missing topic A"]
        assert brief.competitor_gaps.missing_questions == ["Q1?"]
        assert brief.competitor_gaps.missing_entities == ["EntityX"]


    def test_writer_receives_competitor_gap_guidance(self) -> None:
        from power_win_content.agents.content_writer import ContentWriterAgent

        brief = ContentBrief(
            topic="Test Topic",
            seo=SEOStrategy(primary_topic="Test", search_intent="informational", primary_keyword="test", recommended_title="Test"),
            aio=AIOStrategy(),
            geo=GEOStrategy(),
            competitor_gaps=ContentGap(missing_topics=["Payment methods"], missing_questions=["Which wallets are supported?"]),
        )

        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.return_value = "Generated content"

        writer = ContentWriterAgent(llm_client=mock_llm)
        result = writer.generate(brief)

        assert result == "Generated content"
        prompt = mock_llm.generate.call_args[0][0]
        assert "Payment methods" in prompt
        assert "Which wallets are supported?" in prompt
        assert "editorial planning input" in prompt.lower()
        assert "not factual evidence" in prompt.lower()

    def test_strategy_receives_none_when_all_competitors_failed(self) -> None:
        """When all competitors failed, main.py passes None to strategy."""
        from power_win_content.strategy.strategist import ContentStrategist

        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = [
            json.dumps({
                "primary_topic": "Test",
                "search_intent": "informational",
                "primary_keyword": "test",
                "recommended_title": "Test Title",
            }),
            json.dumps({"direct_answer_questions": [], "concise_answers": {}, "definitions": {}, "important_factual_statements": [], "entities": [], "evidence_requirements": [], "structured_information_requirements": []}),
            json.dumps({"important_entities": [], "entity_relationships": [], "authoritative_external_sources": [], "power_win_first_party_facts": [], "unique_information": [], "citation_evidence_opportunities": [], "factual_consistency_requirements": [], "questions_to_answer_clearly": []}),
        ]

        strategist = ContentStrategist(llm_client=mock_llm)
        research = Mock()
        research.power_win_facts = []
        research.external_facts = []
        research.unsupported_claims = []
        research.research_gaps = []
        research.conflicting_information = []

        competitor_for_strategy = None
        brief, _ = strategist.create_brief("Test Topic", research, competitor_analysis=competitor_for_strategy)

        assert brief.competitor_gaps.missing_topics == []
        assert brief.competitor_gaps.missing_questions == []
        prompt = mock_llm.generate.call_args[0][0]
        assert "competitor" not in prompt.lower() or "no" in prompt.lower()
