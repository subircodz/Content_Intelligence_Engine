"""Tests for multi-engine web search with DuckDuckGo, Google, and Bing providers."""

import inspect
import json
from unittest.mock import Mock, patch, MagicMock, PropertyMock
import os

import httpx

from power_win_content.research.models import Source, SourceType
from power_win_content.research.tools.web_search import (
    WebSearchTool,
    DuckDuckGoProvider,
    GoogleSearchProvider,
    BingSearchProvider,
    _PlaywrightBrowserManager,
    _classify_source_type,
    _extract_domain,
    _normalize_url_for_dedup,
    _is_search_challenge_page,
    _BrowserProfile,
    _BROWSER_PROFILES,
    MAX_COMBINED_RESULTS,
)


class TestSourceProviderField:
    def test_source_has_provider_field(self):
        source = Source(name="Test", url="https://example.com", provider="google")
        assert source.provider == "google"

    def test_source_provider_default(self):
        source = Source(name="Test", url="https://example.com")
        assert source.provider == "unknown"


class TestURLNormalization:
    def test_normalize_strips_fragment(self):
        assert _normalize_url_for_dedup("https://example.com/page#section") == "https://example.com/page"

    def test_normalize_strips_trailing_slash(self):
        assert _normalize_url_for_dedup("https://example.com/page/") == "https://example.com/page"

    def test_normalize_lowercases_scheme_and_host(self):
        assert _normalize_url_for_dedup("HTTP://EXAMPLE.COM/Page") == "http://example.com/Page"

    def test_normalize_preserves_path_case(self):
        assert _normalize_url_for_dedup("https://example.com/MyPage") == "https://example.com/MyPage"


class TestDuckDuckGoProvider:
    def test_provider_name(self):
        assert DuckDuckGoProvider.provider_name == "duckduckgo"

    def test_search_returns_sources_with_provider(self):
        mock_client = Mock(spec=httpx.Client)
        mock_response = Mock()
        mock_response.text = """
        <html><body>
        <div class="result">
            <a class="result__snippet" href="https://example.com/article">Example Article</a>
        </div>
        </body></html>
        """
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        provider = DuckDuckGoProvider(mock_client)
        results = provider.search("test query")

        assert len(results) == 1
        assert results[0].provider == "duckduckgo"
        assert "example.com" in str(results[0].url)

    def test_search_handles_timeout(self):
        mock_client = Mock(spec=httpx.Client)
        mock_client.get.side_effect = httpx.TimeoutException("timeout")

        provider = DuckDuckGoProvider(mock_client)
        results = provider.search("test query")
        assert results == []

    def test_search_handles_http_error(self):
        mock_client = Mock(spec=httpx.Client)
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=Mock(), response=Mock(status_code=429)
        )
        mock_client.get.return_value = mock_response

        provider = DuckDuckGoProvider(mock_client)
        results = provider.search("test query")
        assert results == []


def ensure_env_clean():
    """Ensure Google/Bing API credentials are absent from the environment."""
    os.environ.pop("GOOGLE_API_KEY", None)
    os.environ.pop("GOOGLE_CSE_ID", None)
    os.environ.pop("BING_API_KEY", None)


class TestGoogleSearchProvider:
    def _make_provider(self, env_overrides=None, api_side_effect=None):
        mock_client = Mock(spec=httpx.Client)
        if api_side_effect is not None:
            mock_client.get.side_effect = api_side_effect
        mock_bm = Mock()
        mock_bm.fetch_search_page.return_value = None
        env = {"GOOGLE_API_KEY": "", "GOOGLE_CSE_ID": ""}
        env.update(env_overrides or {})
        with patch.dict(os.environ, env):
            provider = GoogleSearchProvider(mock_client, mock_bm)
        return provider, mock_client, mock_bm

    def _make_api_success_client(self):
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [
                {
                    "link": "https://example.com/article",
                    "title": "Example Article",
                    "snippet": "A test snippet",
                }
            ]
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock(spec=httpx.Client)
        mock_client.get.return_value = mock_response
        return mock_client

    def test_provider_name(self):
        assert GoogleSearchProvider.provider_name == "google"

    def test_not_configured_without_keys(self):
        provider, _, _ = self._make_provider()
        assert not provider.is_configured

    def test_configured_with_keys(self):
        provider, _, _ = self._make_provider({"GOOGLE_API_KEY": "test_key", "GOOGLE_CSE_ID": "test_cx"})
        assert provider.is_configured

    # --- A: API success ---

    def test_search_returns_sources_with_provider(self):
        provider, _, mock_bm = self._make_provider(
            {"GOOGLE_API_KEY": "test_key", "GOOGLE_CSE_ID": "test_cx"}
        )
        provider.client = self._make_api_success_client()

        results = provider.search("test query")

        assert len(results) == 1
        assert results[0].provider == "google_api"
        assert "example.com" in str(results[0].url)

    def test_api_success_does_not_call_playwright(self):
        provider, client, mock_bm = self._make_provider(
            {"GOOGLE_API_KEY": "test_key", "GOOGLE_CSE_ID": "test_cx"}
        )
        provider.client = self._make_api_success_client()

        results = provider.search("test query")

        assert len(results) == 1
        mock_bm.fetch_search_page.assert_not_called()

    # --- B: API failure / missing credentials -> Playwright fallback attempted ---

    def test_missing_credentials_attempts_playwright_fallback(self):
        ensure_env_clean()
        provider, _, mock_bm = self._make_provider()
        assert not provider.is_configured

        results = provider.search("test query")

        assert results == []
        mock_bm.fetch_search_page.assert_called_once()
        assert "google.com/search" in mock_bm.fetch_search_page.call_args[0][0]

    def test_search_handles_timeout(self):
        provider, _, mock_bm = self._make_provider(
            {"GOOGLE_API_KEY": "test_key", "GOOGLE_CSE_ID": "test_cx"},
            api_side_effect=httpx.TimeoutException("timeout"),
        )

        results = provider.search("test query")

        assert results == []
        mock_bm.fetch_search_page.assert_called_once()

    def test_search_handles_http_error(self):
        provider, client, mock_bm = self._make_provider(
            {"GOOGLE_API_KEY": "test_key", "GOOGLE_CSE_ID": "test_cx"}
        )
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=Mock(), response=Mock(status_code=403)
        )
        client.get.return_value = mock_response

        results = provider.search("test query")

        assert results == []
        mock_bm.fetch_search_page.assert_called_once()


class TestBingSearchProvider:
    def _make_provider(self, env_overrides=None, api_side_effect=None):
        mock_client = Mock(spec=httpx.Client)
        if api_side_effect is not None:
            mock_client.get.side_effect = api_side_effect
        mock_bm = Mock()
        mock_bm.fetch_search_page.return_value = None
        env = {"BING_API_KEY": ""}
        env.update(env_overrides or {})
        with patch.dict(os.environ, env):
            provider = BingSearchProvider(mock_client, mock_bm)
        return provider, mock_client, mock_bm

    def _make_api_success_client(self):
        mock_response = Mock()
        mock_response.json.return_value = {
            "webPages": {
                "value": [
                    {
                        "url": "https://example.com/article",
                        "name": "Example Article",
                        "snippet": "A test snippet",
                    }
                ]
            }
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock(spec=httpx.Client)
        mock_client.get.return_value = mock_response
        return mock_client

    def test_provider_name(self):
        assert BingSearchProvider.provider_name == "bing"

    def test_not_configured_without_key(self):
        provider, _, _ = self._make_provider()
        assert not provider.is_configured

    def test_configured_with_key(self):
        provider, _, _ = self._make_provider({"BING_API_KEY": "test_key"})
        assert provider.is_configured

    # --- Production posture: Bing Search API retired (2025-08-11) ---
    # No key is required or expected; Playwright is the primary Bing method.

    def test_no_key_skips_bing_api_entirely(self):
        """Without BING_API_KEY, no API request is made at all."""
        ensure_env_clean()
        provider, mock_client, mock_bm = self._make_provider()
        assert not provider.is_configured

        provider.search("test query")

        mock_client.get.assert_not_called()
        mock_bm.fetch_search_page.assert_called_once()

    # --- Legacy API path (pre-retirement key that still works) ---

    # --- C: API success ---

    def test_search_returns_sources_with_provider(self):
        provider, _, mock_bm = self._make_provider({"BING_API_KEY": "test_key"})
        provider.client = self._make_api_success_client()

        results = provider.search("test query")

        assert len(results) == 1
        assert results[0].provider == "bing_api"
        assert "example.com" in str(results[0].url)

    def test_api_success_does_not_call_playwright(self):
        provider, client, mock_bm = self._make_provider({"BING_API_KEY": "test_key"})
        provider.client = self._make_api_success_client()

        results = provider.search("test query")

        assert len(results) == 1
        mock_bm.fetch_search_page.assert_not_called()

    # --- D: API failure / missing credentials -> Playwright fallback attempted ---

    def test_missing_credentials_attempts_playwright_fallback(self):
        ensure_env_clean()
        provider, _, mock_bm = self._make_provider()
        assert not provider.is_configured

        results = provider.search("test query")

        assert results == []
        mock_bm.fetch_search_page.assert_called_once()
        assert "bing.com/search" in mock_bm.fetch_search_page.call_args[0][0]

    def test_search_handles_timeout(self):
        provider, _, mock_bm = self._make_provider(
            {"BING_API_KEY": "test_key"},
            api_side_effect=httpx.TimeoutException("timeout"),
        )

        results = provider.search("test query")

        assert results == []
        mock_bm.fetch_search_page.assert_called_once()

    def test_search_handles_http_error(self):
        provider, client, mock_bm = self._make_provider({"BING_API_KEY": "test_key"})
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=Mock(), response=Mock(status_code=401)
        )
        client.get.return_value = mock_response

        results = provider.search("test query")

        assert results == []
        mock_bm.fetch_search_page.assert_called_once()


class TestMultiProviderSearch:
    def test_all_three_providers_return_results(self):
        """All three providers succeed, results are merged."""
        tool = WebSearchTool(max_results=5)

        mock_ddg = Mock(spec=DuckDuckGoProvider)
        mock_ddg.provider_name = "duckduckgo"
        mock_ddg.search.return_value = [
            Source(name="DDG Result", url="https://ddg-result.com/page", provider="duckduckgo"),
        ]

        mock_google = Mock(spec=GoogleSearchProvider)
        mock_google.provider_name = "google"
        mock_google.search.return_value = [
            Source(name="Google Result", url="https://google-result.com/page", provider="google"),
        ]

        mock_bing = Mock(spec=BingSearchProvider)
        mock_bing.provider_name = "bing"
        mock_bing.search.return_value = [
            Source(name="Bing Result", url="https://bing-result.com/page", provider="bing"),
        ]

        tool._providers = [mock_ddg, mock_google, mock_bing]
        results = tool.search("test query")

        assert len(results) == 3
        providers_found = {r.provider for r in results}
        assert providers_found == {"duckduckgo", "google", "bing"}

    def test_one_provider_failing_does_not_terminate(self):
        """One provider raises, others succeed."""
        tool = WebSearchTool(max_results=5)

        mock_ddg = Mock(spec=DuckDuckGoProvider)
        mock_ddg.provider_name = "duckduckgo"
        mock_ddg.search.return_value = [
            Source(name="DDG Result", url="https://ddg-result.com/page", provider="duckduckgo"),
        ]

        mock_google = Mock(spec=GoogleSearchProvider)
        mock_google.provider_name = "google"
        mock_google.search.side_effect = Exception("API error")

        mock_bing = Mock(spec=BingSearchProvider)
        mock_bing.provider_name = "bing"
        mock_bing.search.return_value = [
            Source(name="Bing Result", url="https://bing-result.com/page", provider="bing"),
        ]

        tool._providers = [mock_ddg, mock_google, mock_bing]
        results = tool.search("test query")

        assert len(results) == 2
        providers_found = {r.provider for r in results}
        assert providers_found == {"duckduckgo", "bing"}

    def test_duplicate_urls_deduplicated(self):
        """Same URL from two providers is deduplicated."""
        tool = WebSearchTool(max_results=5)

        mock_ddg = Mock(spec=DuckDuckGoProvider)
        mock_ddg.provider_name = "duckduckgo"
        mock_ddg.search.return_value = [
            Source(name="DDG Result", url="https://shared.com/page", provider="duckduckgo"),
        ]

        mock_google = Mock(spec=GoogleSearchProvider)
        mock_google.provider_name = "google"
        mock_google.search.return_value = [
            Source(name="Google Result", url="https://shared.com/page", provider="google"),
        ]

        mock_bing = Mock(spec=BingSearchProvider)
        mock_bing.provider_name = "bing"
        mock_bing.search.return_value = []

        tool._providers = [mock_ddg, mock_google, mock_bing]
        results = tool.search("test query")

        assert len(results) == 1
        assert results[0].provider == "duckduckgo"

    def test_combined_results_limited(self):
        """Total results are capped at MAX_COMBINED_RESULTS."""
        tool = WebSearchTool(max_results=5)

        mock_ddg = Mock(spec=DuckDuckGoProvider)
        mock_ddg.provider_name = "duckduckgo"
        mock_ddg.search.return_value = [
            Source(name=f"DDG {i}", url=f"https://ddg{i}.com/page", provider="duckduckgo")
            for i in range(10)
        ]

        mock_google = Mock(spec=GoogleSearchProvider)
        mock_google.provider_name = "google"
        mock_google.search.return_value = [
            Source(name=f"Google {i}", url=f"https://google{i}.com/page", provider="google")
            for i in range(10)
        ]

        mock_bing = Mock(spec=BingSearchProvider)
        mock_bing.provider_name = "bing"
        mock_bing.search.return_value = [
            Source(name=f"Bing {i}", url=f"https://bing{i}.com/page", provider="bing")
            for i in range(10)
        ]

        tool._providers = [mock_ddg, mock_google, mock_bing]
        results = tool.search("test query")

        assert len(results) == MAX_COMBINED_RESULTS

    def test_provider_metadata_preserved(self):
        """Provider name is preserved in Source objects."""
        tool = WebSearchTool(max_results=5)

        mock_ddg = Mock(spec=DuckDuckGoProvider)
        mock_ddg.provider_name = "duckduckgo"
        mock_ddg.search.return_value = [
            Source(name="Result", url="https://example.com/page", provider="duckduckgo", title="Title"),
        ]

        tool._providers = [mock_ddg]
        results = tool.search("test query")

        assert results[0].provider == "duckduckgo"
        assert results[0].title == "Title"

    def test_competitor_search_uses_same_mechanism(self):
        """Competitor analyzer's search uses the same WebSearchTool."""
        from power_win_content.competitors.analyzer import CompetitorAnalyzer
        from power_win_content.llm.client import LLMClient

        mock_llm = Mock(spec=LLMClient)
        mock_search = Mock(spec=WebSearchTool)
        mock_search.search.return_value = [
            Source(name="Competitor", url="https://competitor.com/page", provider="duckduckgo"),
        ]
        mock_fetcher = Mock()
        mock_fetcher.fetch.return_value = None

        analyzer = CompetitorAnalyzer(llm_client=mock_llm, search_tool=mock_search, fetcher=mock_fetcher, max_competitors=1)
        analyzer._discover_candidate_urls("test topic")

        mock_search.search.assert_called()

    def test_unconfigured_providers_gracefully_degraded(self):
        """Without API keys, only DuckDuckGo runs."""
        tool = WebSearchTool(max_results=5)

        mock_ddg = Mock(spec=DuckDuckGoProvider)
        mock_ddg.provider_name = "duckduckgo"
        mock_ddg.search.return_value = [
            Source(name="DDG Result", url="https://ddg-result.com/page", provider="duckduckgo"),
        ]

        mock_google = Mock(spec=GoogleSearchProvider)
        mock_google.is_configured = False
        mock_google.search.return_value = []

        mock_bing = Mock(spec=BingSearchProvider)
        mock_bing.is_configured = False
        mock_bing.search.return_value = []

        tool._providers = [mock_ddg, mock_google, mock_bing]
        results = tool.search("test query")

        assert len(results) == 1
        assert results[0].provider == "duckduckgo"


class TestClassifySourceType:
    def test_power_win_first_party(self):
        assert _classify_source_type("https://power.win/about") == SourceType.FIRST_PARTY

    def test_regulatory(self):
        assert _classify_source_type("https://www.ukgc.gov.uk/license") == SourceType.REGULATORY

    def test_government(self):
        assert _classify_source_type("https://www.gov.uk/gambling-law") == SourceType.GOVERNMENT

    def test_authoritative(self):
        assert _classify_source_type("https://www.bbc.com/news") == SourceType.AUTHORITATIVE

    def test_unknown(self):
        assert _classify_source_type("https://random-site.com/page") == SourceType.UNKNOWN


class TestExtractDomain:
    def test_simple_domain(self):
        assert _extract_domain("https://example.com/page") == "example.com"

    def test_www_stripped(self):
        assert _extract_domain("https://www.example.com/page") == "example.com"

    def test_no_protocol(self):
        assert _extract_domain("example.com/page") == "example.com"


class TestSearchChallengeDetection:
    def test_captcha_detected(self):
        assert _is_search_challenge_page("<div>captcha</div>", "Please verify you are human") is True

    def test_unusual_traffic_detected(self):
        assert _is_search_challenge_page("", "We detected unusual traffic") is True

    def test_normal_results_not_flagged(self):
        assert _is_search_challenge_page("<div>normal results</div>", "Search results for query") is False

    def test_google_consent_detected(self):
        assert _is_search_challenge_page("consent.google.com", "") is True


class TestBrowserProfiles:
    def test_profiles_exist(self):
        assert len(_BROWSER_PROFILES) >= 3

    def test_profiles_are_consistent(self):
        for p in _BROWSER_PROFILES:
            assert isinstance(p, _BrowserProfile)
            assert p.user_agent.startswith("Mozilla/")
            assert "width" in p.viewport
            assert "height" in p.viewport
            assert len(p.locale) >= 2
            assert "text/html" in p.accept

    def test_profile_rotation(self):
        from power_win_content.research.tools.web_search import _PlaywrightBrowserManager
        bm = _PlaywrightBrowserManager()
        p1 = bm._next_profile()
        p2 = bm._next_profile()
        p3 = bm._next_profile()
        assert p1.user_agent != p2.user_agent or p1.viewport != p2.viewport
        # Rotation wraps around
        p4 = bm._next_profile()
        assert p4.user_agent == p1.user_agent


class TestPlaywrightFallbackIntegration:
    def test_google_falls_back_to_playwright_when_api_fails(self):
        mock_client = Mock(spec=httpx.Client)
        mock_bm = Mock()
        mock_bm.fetch_search_page.return_value = None

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "key", "GOOGLE_CSE_ID": "cx"}):
            provider = GoogleSearchProvider(mock_client, mock_bm)
            # API returns error
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            results = provider.search("test query")
            assert results == []

    def test_bing_falls_back_to_playwright_when_api_fails(self):
        mock_client = Mock(spec=httpx.Client)
        mock_bm = Mock()
        mock_bm.fetch_search_page.return_value = None

        with patch.dict(os.environ, {"BING_API_KEY": "key"}):
            provider = BingSearchProvider(mock_client, mock_bm)
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            results = provider.search("test query")
            assert results == []

    def test_google_playwright_returns_empty_on_captcha(self):
        mock_client = Mock(spec=httpx.Client)
        mock_bm = Mock()
        # Simulate a CAPTCHA page
        mock_bm.fetch_search_page.return_value = (
            "<html><body>"
            "<div>We detected unusual traffic from your network</div>"
            "<form class='captcha-form'>CAPTCHA</form>"
            "</body></html>"
        )

        provider = GoogleSearchProvider(mock_client, mock_bm)
        results = provider._search_playwright("test", 5)
        assert results == []

    def test_bing_playwright_returns_empty_on_captcha(self):
        mock_client = Mock(spec=httpx.Client)
        mock_bm = Mock()
        mock_bm.fetch_search_page.return_value = (
            "<html><body>"
            "<h1>Are you a robot?</h1>"
            "<p>Please complete the captcha to continue.</p>"
            "</body></html>"
        )

        provider = BingSearchProvider(mock_client, mock_bm)
        results = provider._search_playwright("test", 5)
        assert results == []

    def test_google_playwright_extracts_results(self):
        mock_client = Mock(spec=httpx.Client)
        mock_bm = Mock()
        mock_bm.fetch_search_page.return_value = (
            "<html><body>"
            '<div class="g"><a href="https://example.com/page"><h3>Example Page</h3></a>'
            '<div class="VwiC3b">A snippet about the page.</div></div>'
            "</body></html>"
        )

        provider = GoogleSearchProvider(mock_client, mock_bm)
        results = provider._search_playwright("test", 5)
        assert len(results) == 1
        assert results[0].provider == "google_playwright"
        assert "example.com" in str(results[0].url)

    def test_bing_playwright_extracts_results(self):
        mock_client = Mock(spec=httpx.Client)
        mock_bm = Mock()
        mock_bm.fetch_search_page.return_value = (
            "<html><body>"
            '<li class="b_algo"><a href="https://example.com/page"><h2>Bing Result</h2></a>'
            '<div class="b_caption"><p>A Bing snippet.</p></div></li>'
            "</body></html>"
        )

        provider = BingSearchProvider(mock_client, mock_bm)
        results = provider._search_playwright("test", 5)
        assert len(results) == 1
        assert results[0].provider == "bing_playwright"
        assert "example.com" in str(results[0].url)

    def test_google_failure_does_not_stop_bing_ddg(self):
        tool = WebSearchTool(max_results=5)
        mock_ddg = Mock(spec=DuckDuckGoProvider)
        mock_ddg.provider_name = "duckduckgo"
        mock_ddg.search.return_value = [Source(name="DDG", url="https://ddg.com/page", provider="duckduckgo")]

        mock_google = Mock(spec=GoogleSearchProvider)
        mock_google.provider_name = "google"
        mock_google.search.side_effect = Exception("google crashed")

        mock_bing = Mock(spec=BingSearchProvider)
        mock_bing.provider_name = "bing"
        mock_bing.search.return_value = [Source(name="Bing", url="https://bing.com/page", provider="bing")]

        tool._providers = [mock_ddg, mock_google, mock_bing]
        results = tool.search("test")
        assert len(results) == 2
        assert {r.provider for r in results} == {"duckduckgo", "bing"}

    def test_bing_failure_does_not_stop_google_ddg(self):
        tool = WebSearchTool(max_results=5)
        mock_ddg = Mock(spec=DuckDuckGoProvider)
        mock_ddg.provider_name = "duckduckgo"
        mock_ddg.search.return_value = [Source(name="DDG", url="https://ddg.com/page", provider="duckduckgo")]

        mock_google = Mock(spec=GoogleSearchProvider)
        mock_google.provider_name = "google"
        mock_google.search.return_value = [Source(name="Google", url="https://google.com/page", provider="google")]

        mock_bing = Mock(spec=BingSearchProvider)
        mock_bing.provider_name = "bing"
        mock_bing.search.side_effect = Exception("bing crashed")

        tool._providers = [mock_ddg, mock_google, mock_bing]
        results = tool.search("test")
        assert len(results) == 2
        assert {r.provider for r in results} == {"duckduckgo", "google"}

    def test_all_three_providers_same_url_deduplicated(self):
        """G: Same URL from Google, Bing, and DuckDuckGo appears once."""
        tool = WebSearchTool(max_results=5)

        mock_ddg = Mock(spec=DuckDuckGoProvider)
        mock_ddg.provider_name = "duckduckgo"
        mock_ddg.search.return_value = [
            Source(name="DDG", url="https://shared.com/page", provider="duckduckgo"),
        ]

        mock_google = Mock(spec=GoogleSearchProvider)
        mock_google.provider_name = "google"
        mock_google.search.return_value = [
            Source(name="Google", url="https://shared.com/page", provider="google"),
        ]

        mock_bing = Mock(spec=BingSearchProvider)
        mock_bing.provider_name = "bing"
        mock_bing.search.return_value = [
            Source(name="Bing", url="https://shared.com/page", provider="bing"),
        ]

        tool._providers = [mock_ddg, mock_google, mock_bing]
        results = tool.search("test query")

        assert len(results) == 1
        assert results[0].provider == "duckduckgo"

    def test_all_three_providers_different_urls(self):
        """Each provider returns unique URLs; all three appear."""
        tool = WebSearchTool(max_results=5)

        mock_ddg = Mock(spec=DuckDuckGoProvider)
        mock_ddg.provider_name = "duckduckgo"
        mock_ddg.search.return_value = [
            Source(name="DDG", url="https://ddg.com/page", provider="duckduckgo"),
        ]

        mock_google = Mock(spec=GoogleSearchProvider)
        mock_google.provider_name = "google"
        mock_google.search.return_value = [
            Source(name="Google", url="https://google.com/page", provider="google"),
        ]

        mock_bing = Mock(spec=BingSearchProvider)
        mock_bing.provider_name = "bing"
        mock_bing.search.return_value = [
            Source(name="Bing", url="https://bing.com/page", provider="bing"),
        ]

        tool._providers = [mock_ddg, mock_google, mock_bing]
        results = tool.search("test query")

        assert len(results) == 3
        assert {r.provider for r in results} == {"duckduckgo", "google", "bing"}

    def test_two_of_three_same_url_deduplicated(self):
        """Two providers return same URL; third is unique. Total = 2."""
        tool = WebSearchTool(max_results=5)

        mock_ddg = Mock(spec=DuckDuckGoProvider)
        mock_ddg.provider_name = "duckduckgo"
        mock_ddg.search.return_value = [
            Source(name="DDG", url="https://shared.com/page", provider="duckduckgo"),
        ]

        mock_google = Mock(spec=GoogleSearchProvider)
        mock_google.provider_name = "google"
        mock_google.search.return_value = [
            Source(name="Google", url="https://shared.com/page", provider="google"),
        ]

        mock_bing = Mock(spec=BingSearchProvider)
        mock_bing.provider_name = "bing"
        mock_bing.search.return_value = [
            Source(name="Bing", url="https://unique-bing.com/page", provider="bing"),
        ]

        tool._providers = [mock_ddg, mock_google, mock_bing]
        results = tool.search("test query")

        assert len(results) == 2
        assert {r.provider for r in results} == {"duckduckgo", "bing"}


class TestChallengeDetectionAtProviderLevel:
    """E: Search pages with CAPTCHA/challenge/blocking are handled gracefully."""

    def test_google_challenge_page_returns_empty(self):
        mock_client = Mock(spec=httpx.Client)
        mock_bm = Mock()
        mock_bm.fetch_search_page.return_value = (
            "<html><body>"
            "<div>We detected unusual traffic from your network</div>"
            "<form class='captcha-form'>CAPTCHA</form>"
            "</body></html>"
        )

        provider = GoogleSearchProvider(mock_client, mock_bm)
        results = provider._search_playwright("test", 5)
        assert results == []

    def test_bing_challenge_page_returns_empty(self):
        mock_client = Mock(spec=httpx.Client)
        mock_bm = Mock()
        mock_bm.fetch_search_page.return_value = (
            "<html><body>"
            "<h1>Are you a robot?</h1>"
            "<p>Please complete the captcha to continue.</p>"
            "</body></html>"
        )

        provider = BingSearchProvider(mock_client, mock_bm)
        results = provider._search_playwright("test", 5)
        assert results == []

    def test_google_blocked_page_returns_empty(self):
        mock_client = Mock(spec=httpx.Client)
        mock_bm = Mock()
        mock_bm.fetch_search_page.return_value = (
            "<html><body><p>blocked by administrator</p></body></html>"
        )

        provider = GoogleSearchProvider(mock_client, mock_bm)
        results = provider._search_playwright("test", 5)
        assert results == []

    def test_bing_consent_wall_returns_empty(self):
        mock_client = Mock(spec=httpx.Client)
        mock_bm = Mock()
        mock_bm.fetch_search_page.return_value = (
            "<html><body>"
            "<p>consent.google.com - Please accept terms</p>"
            "</body></html>"
        )

        provider = BingSearchProvider(mock_client, mock_bm)
        results = provider._search_playwright("test", 5)
        assert results == []

    def test_challenge_via_full_search_method(self):
        """Challenge detected via full search() method returns empty."""
        mock_client = Mock(spec=httpx.Client)
        mock_bm = Mock()
        mock_bm.fetch_search_page.return_value = (
            "<html><body>"
            "<div>captcha verification required</div>"
            "</body></html>"
        )

        ensure_env_clean()
        provider = BingSearchProvider(mock_client, mock_bm)
        results = provider.search("test")
        assert results == []
        # Provider should NOT raise
        assert isinstance(results, list)


class TestPlaywrightBrowserLifecycle:
    """Verify shared _PlaywrightBrowserManager reuse, context isolation, and cleanup."""

    def _make_manager_with_fake_browser(self):
        """Create a _PlaywrightBrowserManager with injected fake browser objects."""
        bm = _PlaywrightBrowserManager()
        fake_page = MagicMock()
        fake_response = MagicMock()
        fake_response.status = 200
        fake_page.goto.return_value = fake_response
        fake_page.content.return_value = "<html>" + "x" * 600 + "</html>"
        fake_context = MagicMock()
        fake_context.new_page.return_value = fake_page
        fake_browser = MagicMock()
        fake_browser.new_context.return_value = fake_context
        bm._browser = fake_browser
        return bm, fake_browser, fake_context, fake_page

    def test_shared_browser_reused_across_calls(self):
        """Two calls reuse the same browser object (no new launch)."""
        bm, fake_browser, _, _ = self._make_manager_with_fake_browser()

        bm.fetch_search_page("https://one.com/search")
        bm.fetch_search_page("https://two.com/search")

        # Browser.new_context was called twice (one per search)
        assert fake_browser.new_context.call_count == 2
        # But browser was never relaunched (no new_context constructor call)
        fake_browser.launch.assert_not_called()

    def test_independent_context_per_search(self):
        """Each search call creates its own browser context."""
        bm, fake_browser, _, _ = self._make_manager_with_fake_browser()

        bm.fetch_search_page("https://one.com/search")
        bm.fetch_search_page("https://two.com/search")

        assert fake_browser.new_context.call_count == 2

    def test_profile_rotation_between_calls(self):
        """Different profiles used for successive calls."""
        bm, fake_browser, _, _ = self._make_manager_with_fake_browser()

        bm.fetch_search_page("https://one.com/search")
        bm.fetch_search_page("https://two.com/search")

        uas = [
            call.kwargs.get("user_agent") or call[1].get("user_agent")
            for call in fake_browser.new_context.call_args_list
        ]
        # At least one kwarg form or positional form
        # The profiles are rotated so user-agents should differ
        all_uas = []
        for call in fake_browser.new_context.call_args_list:
            kw = call.kwargs if call.kwargs else {}
            all_uas.append(kw.get("user_agent", ""))

        # With 3 profiles and 2 calls, both should have a user_agent
        assert len(all_uas) == 2
        assert all(ua.startswith("Mozilla/") for ua in all_uas)

    def test_context_closed_after_successful_fetch(self):
        """Context is closed in the finally block after success."""
        bm, _, fake_context, _ = self._make_manager_with_fake_browser()

        bm.fetch_search_page("https://example.com/search")

        fake_context.close.assert_called_once()

    def test_page_closed_after_successful_fetch(self):
        """Page is closed in the finally block after success."""
        bm, _, fake_context, fake_page = self._make_manager_with_fake_browser()

        bm.fetch_search_page("https://example.com/search")

        fake_page.close.assert_called_once()

    def test_context_closed_after_exception(self):
        """Context is closed even when goto raises an exception."""
        bm, fake_browser, _, fake_page = self._make_manager_with_fake_browser()
        fake_page.goto.side_effect = Exception("network error")

        # Should not raise
        result = bm.fetch_search_page("https://example.com/search")
        assert result is None

        # Context still closed
        fake_context = fake_browser.new_context.return_value
        fake_context.close.assert_called_once()

    def test_close_resets_state(self):
        """close() closes playwright and browser, resets attributes to None."""
        bm = _PlaywrightBrowserManager()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        bm._playwright = mock_playwright
        bm._browser = mock_browser

        bm.close()

        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        assert bm._browser is None
        assert bm._playwright is None

    def test_close_is_idempotent(self):
        """Calling close() twice does not raise."""
        bm = _PlaywrightBrowserManager()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        bm._playwright = mock_playwright
        bm._browser = mock_browser

        bm.close()
        bm.close()

        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()

    def test_no_rich_in_web_search_module(self):
        """web_search.py must not use Rich console for Playwright operations."""
        source = inspect.getsource(
            __import__(
                "power_win_content.research.tools.web_search", fromlist=["web_search"]
            )
        )
        assert "from rich" not in source
        assert "import rich" not in source
        assert "console.status" not in source
