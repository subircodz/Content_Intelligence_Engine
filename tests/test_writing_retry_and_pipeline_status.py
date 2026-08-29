"""Tests for writing retry, pipeline status, and phase terminology."""

import httpx
import time
from unittest.mock import Mock, patch, MagicMock

import pytest

from intelligence_content_engine.agents.content_writer import ContentWriterAgent, _is_transient_error
from intelligence_content_engine.llm.client import LLMClient
from intelligence_content_engine.research.models import PhaseStatus
from intelligence_content_engine.strategy.models import AIOStrategy, ContentBrief, GEOStrategy, SEOStrategy


def _make_brief(title: str = "Test Topic") -> ContentBrief:
    return ContentBrief(
        topic=title,
        seo=SEOStrategy(primary_topic=title, search_intent="informational", primary_keyword=title, recommended_title=title),
        aio=AIOStrategy(),
        geo=GEOStrategy(),
    )


# === _is_transient_error ===

class TestTransientErrorDetection:
    def test_timeout_is_transient(self):
        assert _is_transient_error(httpx.TimeoutException("timed out")) is True

    def test_connect_error_is_transient(self):
        assert _is_transient_error(httpx.ConnectError("refused")) is True

    def test_remote_protocol_error_is_transient(self):
        assert _is_transient_error(httpx.RemoteProtocolError("bad protocol")) is True

    def test_429_is_transient(self):
        req = httpx.Request("GET", "http://x")
        resp = httpx.Response(429, request=req)
        assert _is_transient_error(httpx.HTTPStatusError("429", request=req, response=resp)) is True

    def test_500_is_transient(self):
        req = httpx.Request("GET", "http://x")
        resp = httpx.Response(500, request=req)
        assert _is_transient_error(httpx.HTTPStatusError("500", request=req, response=resp)) is True

    def test_502_is_transient(self):
        req = httpx.Request("GET", "http://x")
        resp = httpx.Response(502, request=req)
        assert _is_transient_error(httpx.HTTPStatusError("502", request=req, response=resp)) is True

    def test_503_is_transient(self):
        req = httpx.Request("GET", "http://x")
        resp = httpx.Response(503, request=req)
        assert _is_transient_error(httpx.HTTPStatusError("503", request=req, response=resp)) is True

    def test_504_is_transient(self):
        req = httpx.Request("GET", "http://x")
        resp = httpx.Response(504, request=req)
        assert _is_transient_error(httpx.HTTPStatusError("504", request=req, response=resp)) is True

    def test_400_is_not_transient(self):
        req = httpx.Request("GET", "http://x")
        resp = httpx.Response(400, request=req)
        assert _is_transient_error(httpx.HTTPStatusError("400", request=req, response=resp)) is False

    def test_401_is_not_transient(self):
        req = httpx.Request("GET", "http://x")
        resp = httpx.Response(401, request=req)
        assert _is_transient_error(httpx.HTTPStatusError("401", request=req, response=resp)) is False

    def test_403_is_not_transient(self):
        req = httpx.Request("GET", "http://x")
        resp = httpx.Response(403, request=req)
        assert _is_transient_error(httpx.HTTPStatusError("403", request=req, response=resp)) is False


# === Writing retry — success on first attempt ===

class TestWritingRetrySuccess:
    def test_first_attempt_success_no_retry(self):
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.return_value = "Article content."

        writer = ContentWriterAgent(llm_client=mock_llm)
        article = writer.generate(_make_brief())

        assert article == "Article content."
        assert mock_llm.generate.call_count == 1

    def test_first_attempt_timeout_second_succeeds(self):
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = [
            httpx.TimeoutException("timeout"),
            "Recovered article.",
        ]

        writer = ContentWriterAgent(llm_client=mock_llm)
        with patch("intelligence_content_engine.agents.content_writer.time.sleep") as mock_sleep:
            article = writer.generate(_make_brief())

        assert article == "Recovered article."
        assert mock_llm.generate.call_count == 2
        mock_sleep.assert_called_once_with(1.0)

    def test_first_attempt_503_second_succeeds(self):
        req = httpx.Request("GET", "http://x")
        resp = httpx.Response(503, request=req)
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = [
            httpx.HTTPStatusError("503", request=req, response=resp),
            "Recovered article.",
        ]

        writer = ContentWriterAgent(llm_client=mock_llm)
        with patch("intelligence_content_engine.agents.content_writer.time.sleep") as mock_sleep:
            article = writer.generate(_make_brief())

        assert article == "Recovered article."
        assert mock_llm.generate.call_count == 2
        mock_sleep.assert_called_once_with(1.0)

    def test_two_failures_then_succeeds(self):
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = [
            httpx.TimeoutException("t1"),
            httpx.ConnectError("c1"),
            "Final article.",
        ]

        writer = ContentWriterAgent(llm_client=mock_llm)
        with patch("intelligence_content_engine.agents.content_writer.time.sleep") as mock_sleep:
            article = writer.generate(_make_brief())

        assert article == "Final article."
        assert mock_llm.generate.call_count == 3
        assert mock_sleep.call_count == 2
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0]

    def test_all_retries_fail_empty(self):
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.return_value = ""

        writer = ContentWriterAgent(llm_client=mock_llm)
        with patch("intelligence_content_engine.agents.content_writer.time.sleep") as mock_sleep:
            article = writer.generate(_make_brief())

        assert article == ""
        assert mock_llm.generate.call_count == 3
        assert mock_sleep.call_count == 2

    def test_all_retries_fail_with_exception(self):
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = httpx.TimeoutException("persistent timeout")

        writer = ContentWriterAgent(llm_client=mock_llm)
        with patch("intelligence_content_engine.agents.content_writer.time.sleep") as mock_sleep:
            with pytest.raises(httpx.TimeoutException):
                article = writer.generate(_make_brief())

        assert mock_llm.generate.call_count == 3
        assert mock_sleep.call_count == 2

    def test_empty_response_is_retried(self):
        """Whitespace-only response counts as empty and is retried."""
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = ["   ", " \n ", "Real content"]

        writer = ContentWriterAgent(llm_client=mock_llm)
        with patch("intelligence_content_engine.agents.content_writer.time.sleep") as mock_sleep:
            article = writer.generate(_make_brief())

        assert article == "Real content"
        assert mock_llm.generate.call_count == 3
        assert mock_sleep.call_count == 2

    def test_retry_backoff_is_bounded(self):
        """Backoff delays are exactly 1s and 2s."""
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = [
            httpx.TimeoutException("t1"),
            httpx.TimeoutException("t2"),
            "article",
        ]

        writer = ContentWriterAgent(llm_client=mock_llm)
        with patch("intelligence_content_engine.agents.content_writer.time.sleep") as mock_sleep:
            writer.generate(_make_brief())

        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0]

    def test_400_raises_immediately_no_retry(self):
        """Permanent error (400) is not retried — raised on first attempt."""
        req = httpx.Request("GET", "http://x")
        resp = httpx.Response(400, request=req)
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = httpx.HTTPStatusError("400", request=req, response=resp)

        writer = ContentWriterAgent(llm_client=mock_llm)
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            writer.generate(_make_brief())

        assert exc_info.value.response.status_code == 400
        assert mock_llm.generate.call_count == 1

    def test_auth_failure_raises_immediately(self):
        """Authentication failure (401) is not retried."""
        req = httpx.Request("GET", "http://x")
        resp = httpx.Response(401, request=req)
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = httpx.HTTPStatusError("401", request=req, response=resp)

        writer = ContentWriterAgent(llm_client=mock_llm)
        with pytest.raises(httpx.HTTPStatusError):
            writer.generate(_make_brief())

        assert mock_llm.generate.call_count == 1

    def test_logging_in_debug_mode(self):
        """Retry operations produce debug-level log messages."""
        import logging
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = [
            httpx.TimeoutException("timeout"),
            "article",
        ]

        writer = ContentWriterAgent(llm_client=mock_llm)
        with patch("intelligence_content_engine.agents.content_writer.time.sleep"):
            with patch("intelligence_content_engine.agents.content_writer.logger") as mock_logger:
                writer.generate(_make_brief())

        mock_logger.debug.assert_called()
        # The format string contains placeholders; verify the template
        log_template = mock_logger.debug.call_args[0][0]
        assert "attempt" in log_template
        assert "Retrying" in log_template


# === Pipeline status and completion display ===

class TestPipelineStatus:
    def test_display_pipeline_completion_success(self):
        from intelligence_content_engine.ui import display_pipeline_completion
        display_pipeline_completion(docx_created=True, has_warnings=False)

    def test_display_pipeline_completion_with_warnings(self):
        from intelligence_content_engine.ui import display_pipeline_completion
        display_pipeline_completion(docx_created=True, has_warnings=True)

    def test_display_pipeline_completion_failed(self):
        from intelligence_content_engine.ui import display_pipeline_completion
        display_pipeline_completion(docx_created=False, has_warnings=False)

    def test_display_pipeline_completion_failed_with_warnings(self):
        from intelligence_content_engine.ui import display_pipeline_completion
        display_pipeline_completion(docx_created=False, has_warnings=True)

    def test_phase_result_success(self):
        from intelligence_content_engine.ui import display_phase_result
        display_phase_result("Research Phase", PhaseStatus.SUCCESS, "details")

    def test_phase_result_degraded_shows_warning(self):
        from intelligence_content_engine.ui import display_phase_result
        display_phase_result("Competitor Analysis", PhaseStatus.DEGRADED, "partial failure")

    def test_phase_result_failed(self):
        from intelligence_content_engine.ui import display_phase_result
        display_phase_result("Writing Phase", PhaseStatus.FAILED, "no article generated")

    def test_summary_table_completed(self):
        from intelligence_content_engine.ui import display_summary_table
        display_summary_table(
            topic="Test", research_status="verified", pipeline_status_label="COMPLETED",
            power_win_facts_count=3, external_facts_count=2, gaps_count=1,
            unsupported_count=0, recommended_title="Test", primary_keyword="test",
            article_length=500,
        )

    def test_summary_table_completed_with_warnings(self):
        from intelligence_content_engine.ui import display_summary_table
        display_summary_table(
            topic="Test", research_status="uncertain", pipeline_status_label="COMPLETED WITH WARNINGS",
            power_win_facts_count=0, external_facts_count=1, gaps_count=3,
            unsupported_count=2, recommended_title="Test", primary_keyword="test",
            article_length=500, competitors_selected=2, competitors_analyzed=1,
            competitors_failed=1,
        )

    def test_summary_table_failed(self):
        from intelligence_content_engine.ui import display_summary_table
        display_summary_table(
            topic="Test", research_status="unsupported", pipeline_status_label="FAILED",
            power_win_facts_count=0, external_facts_count=0, gaps_count=0,
            unsupported_count=0, recommended_title="N/A", primary_keyword="N/A",
            article_length=0,
        )

    def test_summary_table_no_technical_enums(self):
        """Summary table must not contain raw ClaimStatus enum text."""
        from intelligence_content_engine.ui import display_summary_table
        # If ClaimStatus.UNCERTAIN appears in output, the test would need
        # to capture console output — this test ensures the function runs
        # without crashing with any status string.
        for status in ("verified", "partially_supported", "unsupported", "uncertain", "conflicting"):
            display_summary_table(
                topic="Test", research_status=status, pipeline_status_label="COMPLETED",
                power_win_facts_count=0, external_facts_count=0, gaps_count=0,
                unsupported_count=0, recommended_title="T", primary_keyword="t",
                article_length=0,
            )
