from unittest.mock import Mock, patch

from power_win_content.llm.client import LLMClient
from power_win_content.research.models import ResearchPlan, ResearchResult
from power_win_content.strategy.models import AIOStrategy, ContentBrief, GEOStrategy, SEOStrategy
from power_win_content.ui import display_banner, display_pipeline_completion, display_welcome, prompt_user_topic


def test_ui_display_functions() -> None:
    display_banner()
    display_welcome()
    from power_win_content.research.models import PhaseStatus
    display_pipeline_completion(docx_created=True, has_warnings=False)


def test_prompt_user_topic_valid() -> None:
    with patch("power_win_content.ui.Prompt.ask", return_value="  My Custom Article Topic  "):
        topic = prompt_user_topic()
        assert topic == "My Custom Article Topic"


def test_prompt_user_topic_retry_on_empty() -> None:
    with patch("power_win_content.ui.Prompt.ask", side_effect=["", "   ", "Valid Topic"]):
        topic = prompt_user_topic()
        assert topic == "Valid Topic"


def test_pipeline_handles_empty_article() -> None:
    from power_win_content.main import run_pipeline
    from power_win_content.research.models import PhaseStatus

    mock_research = ResearchResult(
        topic="Test",
        plan=ResearchPlan(topic="Test", questions=[]),
        questions=[],
    )
    mock_brief = ContentBrief(
        topic="Test",
        seo=SEOStrategy(primary_topic="Test", search_intent="informational", primary_keyword="test", recommended_title="Test"),
        aio=AIOStrategy(),
        geo=GEOStrategy(),
    )

    with (
        patch("power_win_content.main.Settings"),
        patch("power_win_content.main.LLMClient"),
        patch("power_win_content.main.Researcher") as mock_researcher_cls,
        patch("power_win_content.main.ContentStrategist") as mock_strategist_cls,
        patch("power_win_content.main.ContentWriterAgent") as mock_writer_cls,
    ):
        mock_researcher_ctx = Mock()
        mock_researcher_ctx.research.return_value = (mock_research, PhaseStatus.DEGRADED)
        mock_researcher_cls.return_value.__enter__ = Mock(return_value=mock_researcher_ctx)
        mock_researcher_cls.return_value.__exit__ = Mock(return_value=False)

        mock_strategist_cls.return_value.create_brief.return_value = (mock_brief, PhaseStatus.DEGRADED)
        mock_writer_cls.return_value.generate.return_value = ""

        result = run_pipeline("Test Topic")
        assert result is None
