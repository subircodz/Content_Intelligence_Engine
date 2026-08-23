import json
from unittest.mock import Mock, patch

import httpx

from power_win_content.llm.client import LLMClient
from power_win_content.research.models import PhaseStatus, ResearchPlan, ResearchResult
from power_win_content.research.researcher import Researcher
from power_win_content.research.tools import WebSearchTool, WebFetcher, SitemapFetcher
from power_win_content.competitors.analyzer import CompetitorAnalyzer
from power_win_content.strategy.strategist import ContentStrategist
from power_win_content.agents.content_writer import ContentWriterAgent
from power_win_content.strategy.models import AIOStrategy, ContentBrief, GEOStrategy, SEOStrategy
from power_win_content.output.docx_writer import save_article_docx
from pathlib import Path


def test_phase_status_enum_values():
    assert PhaseStatus.SUCCESS.value == "success"
    assert PhaseStatus.DEGRADED.value == "degraded"
    assert PhaseStatus.FAILED.value == "failed"


def test_phase_status_is_string_enum():
    assert isinstance(PhaseStatus.SUCCESS, str)
    assert PhaseStatus.SUCCESS == "success"


def test_competitor_degraded_with_zero_sources():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.side_effect = [
        "invalid json",
        "also invalid",
    ]
    mock_search = Mock(spec=WebSearchTool)
    mock_search.search.return_value = []
    mock_fetcher = Mock(spec=WebFetcher)
    mock_fetcher.fetch.return_value = None

    analyzer = CompetitorAnalyzer(llm_client=mock_llm, search_tool=mock_search, fetcher=mock_fetcher, max_competitors=2)
    analysis, status = analyzer.analyze("Topic with no results")
    assert status == PhaseStatus.DEGRADED
    assert analysis.domains_analyzed == 0


def test_competitor_success_with_sources():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.side_effect = [
        json.dumps({"title": "Guide", "search_intent": "informational", "headings": [], "questions_answered": [], "entities": [], "statistics": [], "sections": [], "unique_angles": []}),
        json.dumps({"missing_topics": ["A"], "missing_questions": [], "missing_entities": [], "missing_comparisons": [], "missing_statistics": [], "missing_user_concerns": [], "missing_angles": [], "competitor_topics_absent_from_ours": []}),
    ]
    mock_search = Mock(spec=WebSearchTool)
    from power_win_content.research.models import Source, SourceType
    mock_search.search.return_value = [Source(name="Guide", url="https://example.com/guide", source_type=SourceType.SECONDARY)]
    mock_fetcher = Mock(spec=WebFetcher)
    mock_fetcher.fetch.return_value = "Some content about guide"

    analyzer = CompetitorAnalyzer(llm_client=mock_llm, search_tool=mock_search, fetcher=mock_fetcher, max_competitors=2)
    analysis, status = analyzer.analyze("Topic")
    assert status == PhaseStatus.SUCCESS
    assert analysis.domains_analyzed == 1


def test_research_degraded_on_fallback():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.side_effect = [httpx.ReadTimeout("timed out"), json.dumps({"claims": []})]
    mock_search = Mock(spec=WebSearchTool)
    mock_search.search.return_value = []
    mock_fetcher = Mock(spec=WebFetcher)
    mock_sitemap = Mock(spec=SitemapFetcher)
    mock_sitemap.discover_first_party_sources.return_value = []

    researcher = Researcher(llm_client=mock_llm, search_tool=mock_search, fetcher=mock_fetcher, sitemap_fetcher=mock_sitemap)
    result, status = researcher.research("Fallback Topic")
    assert status == PhaseStatus.DEGRADED


def test_writing_success():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.return_value = "The article content."
    writer = ContentWriterAgent(llm_client=mock_llm)
    article = writer.generate("Test Title")
    assert article == "The article content."


def test_writing_failure_returns_empty():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.return_value = ""
    writer = ContentWriterAgent(llm_client=mock_llm)
    article = writer.generate("Test Title")
    assert article == ""


def test_docx_success(tmp_path: Path):
    path = save_article_docx("# Title\n\nContent.", "Test", output_dir=str(tmp_path))
    assert path is not None
    assert path.exists()


def test_docx_failure_on_empty():
    path = save_article_docx("", "Test")
    assert path is None


def test_display_phase_result_runs():
    from power_win_content.ui import display_phase_result
    display_phase_result("Test", PhaseStatus.SUCCESS, "detail")
    display_phase_result("Test", PhaseStatus.DEGRADED, "detail")
    display_phase_result("Test", PhaseStatus.FAILED, "detail")


def test_display_pipeline_completion_runs():
    from power_win_content.ui import display_pipeline_completion
    display_pipeline_completion(docx_created=True, has_warnings=False)
    display_pipeline_completion(docx_created=True, has_warnings=True)
    display_pipeline_completion(docx_created=False, has_warnings=False)
