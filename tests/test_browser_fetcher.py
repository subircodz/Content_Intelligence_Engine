import logging
from unittest.mock import MagicMock, patch

import pytest

from power_win_content.research.tools.browser_fetcher import BrowserFetcher
from power_win_content.research.tools.hybrid_fetcher import HybridFetcher
from power_win_content.research.tools.web_fetcher import WebFetcher

logger = logging.getLogger(__name__)


# Sample HTML content for testing
SPA_SHELL_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <title>Power.win Docs</title>
    <script type="module" src="/assets/index.js"></script>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
"""

CLOUDFLARE_CHALLENGE_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <title>Just a moment...</title>
  </head>
  <body>
    <div id="cf-challenge">
      <form class="challenge-form" id="challenge-form">
        <div class="checking-your-browser">Checking your browser...</div>
      </form>
    </div>
    <script>var ray_id = "abc123";</script>
  </body>
</html>
"""

GOOD_CONTENT_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <title>Test Page</title>
  </head>
  <body>
    <h1>Welcome to Power.win</h1>
    <p>This is the editorial methodology for evaluating online casinos. We check licensing, security, game fairness, and responsible gambling practices.</p>
    <section>
      <h2>Licensing Requirements</h2>
      <p>All casinos must hold valid licenses from recognized regulatory bodies such as the UK Gambling Commission or Malta Gaming Authority.</p>
    </section>
  </body>
</html>
"""

SHORT_CONTENT_HTML = "<html><body><p>Short</p></body></html>"


class TestBrowserFetcher:
    """Tests for BrowserFetcher class."""

    def test_browser_fetcher_initialization(self):
        """Test BrowserFetcher can be initialized with default params."""
        fetcher = BrowserFetcher()
        assert fetcher.timeout == 15.0
        assert fetcher.min_content_length == 500
        assert fetcher.headless is True
        fetcher.close()

    def test_browser_fetcher_custom_params(self):
        """Test BrowserFetcher with custom parameters."""
        fetcher = BrowserFetcher(timeout=30.0, min_content_length=200, headless=False)
        assert fetcher.timeout == 30.0
        assert fetcher.min_content_length == 200
        assert fetcher.headless is False
        fetcher.close()

    @patch("power_win_content.research.tools.browser_fetcher.sync_playwright")
    @patch("time.sleep", return_value=None)  # Speed up test
    def test_fetch_spa_shell_triggers_wait(self, mock_sleep, mock_sync_playwright):
        """Test that SPA shell content triggers waiting logic."""
        # Setup mock
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_sync_playwright.return_value.start.return_value = mock_playwright
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        # Mock response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_page.goto.return_value = mock_response

        # First call returns SPA shell, subsequent calls return good content
        call_count = [0]

        def content_side_effect():
            call_count[0] += 1
            return SPA_SHELL_HTML if call_count[0] == 1 else GOOD_CONTENT_HTML

        eval_count = [0]
        def eval_side_effect(*args, **kwargs):
            eval_count[0] += 1
            # Return realistic content that passes min_content_length=100
            return "" if eval_count[0] == 1 else (
                "Welcome to Power.win editorial methodology. "
                "We check licensing, security, game fairness, and responsible gambling practices. "
                "All casinos must hold valid licenses from recognized regulatory bodies "
                "such as the UK Gambling Commission or Malta Gaming Authority."
            )

        mock_page.content.side_effect = content_side_effect
        mock_page.evaluate.side_effect = eval_side_effect

        fetcher = BrowserFetcher(timeout=10.0, min_content_length=100)
        fetcher._playwright = mock_playwright
        fetcher._browser = mock_browser

        result = fetcher.fetch("https://example.com")

        assert result is not None
        assert "editorial methodology" in result.lower()
        fetcher.close()

    @patch("power_win_content.research.tools.browser_fetcher.sync_playwright")
    @patch("time.sleep", return_value=None)  # Speed up test
    def test_fetch_cloudflare_challenge_waits(self, mock_sleep, mock_sync_playwright):
        """Test that Cloudflare challenge page triggers waiting."""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_sync_playwright.return_value.start.return_value = mock_playwright
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_response = MagicMock()
        mock_response.status = 200
        mock_page.goto.return_value = mock_response

        # First call returns challenge, subsequent calls return good content
        call_count = [0]

        def content_side_effect():
            call_count[0] += 1
            return CLOUDFLARE_CHALLENGE_HTML if call_count[0] == 1 else GOOD_CONTENT_HTML

        eval_count = [0]
        def eval_side_effect(*args, **kwargs):
            eval_count[0] += 1
            # Return realistic content that passes min_content_length=100
            return "" if eval_count[0] == 1 else (
                "Welcome to Power.win editorial methodology. "
                "We check licensing, security, game fairness, and responsible gambling practices. "
                "All casinos must hold valid licenses from recognized regulatory bodies "
                "such as the UK Gambling Commission or Malta Gaming Authority."
            )

        mock_page.content.side_effect = content_side_effect
        mock_page.evaluate.side_effect = eval_side_effect

        fetcher = BrowserFetcher(timeout=10.0, min_content_length=100)
        fetcher._playwright = mock_playwright
        fetcher._browser = mock_browser

        result = fetcher.fetch("https://example.com")

        assert result is not None
        assert "editorial methodology" in result.lower()
        fetcher.close()

    @patch("power_win_content.research.tools.browser_fetcher.sync_playwright")
    def test_fetch_timeout_handled(self, mock_sync_playwright):
        """Test that browser timeout is handled gracefully."""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_sync_playwright.return_value.start.return_value = mock_playwright
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_response = MagicMock()
        mock_response.status = 200
        mock_page.goto.return_value = mock_response

        # Always return SPA shell (never resolves)
        mock_page.content.return_value = SPA_SHELL_HTML
        mock_page.evaluate.return_value = ""

        fetcher = BrowserFetcher(timeout=1.0, min_content_length=500)
        fetcher._playwright = mock_playwright
        fetcher._browser = mock_browser

        result = fetcher.fetch("https://example.com")

        # Should return None after timeout
        assert result is None
        fetcher.close()

    @patch("power_win_content.research.tools.browser_fetcher.sync_playwright")
    def test_fetch_navigation_error_handled(self, mock_sync_playwright):
        """Test that navigation errors are handled."""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_sync_playwright.return_value.start.return_value = mock_playwright
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        # Simulate navigation error
        from playwright.sync_api import Error as PlaywrightError
        mock_page.goto.side_effect = PlaywrightError("Navigation failed")

        fetcher = BrowserFetcher(timeout=10.0)
        fetcher._playwright = mock_playwright
        fetcher._browser = mock_browser

        result = fetcher.fetch("https://example.com")

        assert result is None
        fetcher.close()

    def test_close_cleans_up_resources(self):
        """Test that close() properly cleans up browser and playwright."""
        fetcher = BrowserFetcher()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        fetcher._playwright = mock_playwright
        fetcher._browser = mock_browser

        fetcher.close()

        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        assert fetcher._browser is None
        assert fetcher._playwright is None

    def test_context_manager(self):
        """Test context manager usage."""
        with patch("power_win_content.research.tools.browser_fetcher.sync_playwright") as mock_sync:
            mock_playwright = MagicMock()
            mock_browser = MagicMock()
            mock_sync.return_value.start.return_value = mock_playwright
            mock_playwright.chromium.launch.return_value = mock_browser

            with BrowserFetcher() as fetcher:
                fetcher.fetch("https://example.com")

            mock_browser.close.assert_called_once()
            mock_playwright.stop.assert_called_once()


class TestHybridFetcher:
    """Tests for HybridFetcher class."""

    def test_hybrid_fetcher_initialization(self):
        """Test HybridFetcher can be initialized."""
        http_fetcher = WebFetcher()
        browser_fetcher = BrowserFetcher()
        hybrid = HybridFetcher(http_fetcher=http_fetcher, browser_fetcher=browser_fetcher)
        assert hybrid.http_fetcher is http_fetcher
        assert hybrid.browser_fetcher is browser_fetcher
        assert hybrid.min_content_length == 500
        hybrid.close()

    def test_hybrid_fetcher_defaults(self):
        """Test HybridFetcher with default fetchers."""
        hybrid = HybridFetcher()
        assert hybrid.http_fetcher is not None
        assert hybrid.browser_fetcher is not None
        hybrid.close()

    def test_usable_content_good_html(self):
        """Test that good content passes usability check."""
        hybrid = HybridFetcher(min_content_length=100)
        assert hybrid._is_usable_content(GOOD_CONTENT_HTML) is True
        hybrid.close()

    def test_usable_content_too_short(self):
        """Test that too-short content fails usability check."""
        hybrid = HybridFetcher(min_content_length=100)
        assert hybrid._is_usable_content(SHORT_CONTENT_HTML) is False
        hybrid.close()

    def test_usable_content_none(self):
        """Test that None content fails usability check."""
        hybrid = HybridFetcher()
        assert hybrid._is_usable_content(None) is False
        hybrid.close()

    def test_usable_content_spa_shell(self):
        """Test that SPA shell fails usability check."""
        hybrid = HybridFetcher(min_content_length=100)
        assert hybrid._is_usable_content(SPA_SHELL_HTML) is False
        hybrid.close()

    def test_usable_content_cloudflare_challenge(self):
        """Test that Cloudflare challenge fails usability check."""
        hybrid = HybridFetcher(min_content_length=100)
        assert hybrid._is_usable_content(CLOUDFLARE_CHALLENGE_HTML) is False
        hybrid.close()

    def test_fetch_returns_http_content_when_good(self):
        """Test that HTTP content is returned when good (no browser fallback)."""
        mock_http = MagicMock(spec=WebFetcher)
        mock_browser = MagicMock(spec=BrowserFetcher)

        mock_http.fetch.return_value = GOOD_CONTENT_HTML

        hybrid = HybridFetcher(http_fetcher=mock_http, browser_fetcher=mock_browser)
        result = hybrid.fetch("https://example.com")

        assert result == GOOD_CONTENT_HTML
        mock_http.fetch.assert_called_once_with("https://example.com")
        mock_browser.fetch.assert_not_called()
        hybrid.close()

    def test_fetch_falls_back_to_browser_when_http_insufficient(self):
        """Test that browser is used when HTTP content is insufficient."""
        mock_http = MagicMock(spec=WebFetcher)
        mock_browser = MagicMock(spec=BrowserFetcher)

        mock_http.fetch.return_value = SPA_SHELL_HTML
        mock_browser.fetch.return_value = GOOD_CONTENT_HTML

        hybrid = HybridFetcher(http_fetcher=mock_http, browser_fetcher=mock_browser)
        result = hybrid.fetch("https://example.com")

        assert result == GOOD_CONTENT_HTML
        mock_http.fetch.assert_called_once_with("https://example.com")
        mock_browser.fetch.assert_called_once_with("https://example.com")
        hybrid.close()

    def test_fetch_returns_http_content_when_browser_fails(self):
        """Test that HTTP content is returned even if browser fails."""
        mock_http = MagicMock(spec=WebFetcher)
        mock_browser = MagicMock(spec=BrowserFetcher)

        mock_http.fetch.return_value = SPA_SHELL_HTML
        mock_browser.fetch.side_effect = Exception("Browser failed")

        hybrid = HybridFetcher(http_fetcher=mock_http, browser_fetcher=mock_browser)
        result = hybrid.fetch("https://example.com")

        # Should return the HTTP content (even if insufficient) when browser fails
        assert result == SPA_SHELL_HTML
        hybrid.close()

    def test_fetch_cloudflare_triggers_browser(self):
        """Test that Cloudflare challenge triggers browser fallback."""
        mock_http = MagicMock(spec=WebFetcher)
        mock_browser = MagicMock(spec=BrowserFetcher)

        mock_http.fetch.return_value = CLOUDFLARE_CHALLENGE_HTML
        mock_browser.fetch.return_value = GOOD_CONTENT_HTML

        hybrid = HybridFetcher(http_fetcher=mock_http, browser_fetcher=mock_browser)
        result = hybrid.fetch("https://example.com")

        assert result == GOOD_CONTENT_HTML
        mock_browser.fetch.assert_called_once()
        hybrid.close()

    def test_close_calls_both_fetchers(self):
        """Test that close() closes both fetchers."""
        mock_http = MagicMock(spec=WebFetcher)
        mock_browser = MagicMock(spec=BrowserFetcher)

        hybrid = HybridFetcher(http_fetcher=mock_http, browser_fetcher=mock_browser)
        hybrid.close()

        mock_http.close.assert_called_once()
        mock_browser.close.assert_called_once()

    def test_context_manager(self):
        """Test context manager usage."""
        mock_http = MagicMock(spec=WebFetcher)
        mock_browser = MagicMock(spec=BrowserFetcher)

        with HybridFetcher(http_fetcher=mock_http, browser_fetcher=mock_browser) as hybrid:
            hybrid.fetch("https://example.com")

        mock_http.close.assert_called_once()
        mock_browser.close.assert_called_once()