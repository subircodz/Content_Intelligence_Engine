import os
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from intelligence_content_engine.research.models import Source, SourceType
from intelligence_content_engine.research.tools.web_search import (
    BingSearchProvider,
    DuckDuckGoProvider,
    GoogleSearchProvider,
    MAX_COMBINED_RESULTS,
    WebSearchTool,
    _PlaywrightBrowserManager,
    _classify_source_type,
    _is_search_challenge_page,
    _normalize_url_for_dedup,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://example.com/page#section", "https://example.com/page"),
        ("https://example.com/page/", "https://example.com/page"),
        ("HTTP://EXAMPLE.COM/Page", "http://example.com/Page"),
    ],
)
def test_url_normalization(url, expected):
    assert _normalize_url_for_dedup(url) == expected


def test_search_challenge_detection():
    assert _is_search_challenge_page("<div>captcha</div>", "verify you are human")
    assert not _is_search_challenge_page("<div>results</div>", "normal search results")


def test_source_classification_is_domain_independent():
    assert _classify_source_type("https://power.win/about") != SourceType.FIRST_PARTY


@pytest.mark.asyncio
async def test_duckduckgo_returns_sources():
    client = AsyncMock()
    response = Mock()
    response.text = (
        '<div class="result"><a class="result__snippet" '
        'href="https://example.com/article">Example Article</a></div>'
    )
    response.raise_for_status = Mock()
    client.get.return_value = response

    provider = DuckDuckGoProvider(client)
    results = await provider.search("test")

    assert len(results) == 1
    assert results[0].provider == "duckduckgo"


@pytest.mark.asyncio
async def test_duckduckgo_timeout_degrades():
    client = AsyncMock()
    client.get.side_effect = httpx.TimeoutException("timeout")
    assert await DuckDuckGoProvider(client).search("test") == []


@pytest.mark.asyncio
async def test_google_api_success_skips_browser():
    client = AsyncMock()
    response = Mock()
    response.json.return_value = {
        "items": [{"link": "https://example.com/article", "title": "Example", "snippet": "Snippet"}]
    }
    response.raise_for_status = Mock()
    client.get.return_value = response
    browser = AsyncMock()

    with patch.dict(os.environ, {"GOOGLE_API_KEY": "key", "GOOGLE_CSE_ID": "cx"}):
        provider = GoogleSearchProvider(client, browser)
        results = await provider.search("test")

    assert len(results) == 1
    assert results[0].provider == "google_api"
    browser.fetch_search_page.assert_not_awaited()


@pytest.mark.asyncio
async def test_google_without_credentials_uses_browser():
    client = AsyncMock()
    browser = AsyncMock()
    browser.fetch_search_page.return_value = None

    with patch.dict(os.environ, {"GOOGLE_API_KEY": "", "GOOGLE_CSE_ID": ""}):
        provider = GoogleSearchProvider(client, browser)
        results = await provider.search("test")

    assert results == []
    browser.fetch_search_page.assert_awaited_once()


@pytest.mark.asyncio
async def test_google_api_failure_uses_browser():
    client = AsyncMock()
    client.get.side_effect = httpx.TimeoutException("timeout")
    browser = AsyncMock()
    browser.fetch_search_page.return_value = None

    with patch.dict(os.environ, {"GOOGLE_API_KEY": "key", "GOOGLE_CSE_ID": "cx"}):
        provider = GoogleSearchProvider(client, browser)
        results = await provider.search("test")

    assert results == []
    browser.fetch_search_page.assert_awaited_once()


@pytest.mark.asyncio
async def test_google_playwright_parser():
    provider = GoogleSearchProvider(AsyncMock(), AsyncMock())
    html = (
        '<div class="g"><a href="https://example.com/page"><h3>Example Page</h3></a>'
        '<div class="VwiC3b">A snippet.</div></div>'
    )
    results = provider._parse_playwright_results(html, "test", 5)
    assert len(results) == 1
    assert results[0].provider == "google_playwright"


@pytest.mark.asyncio
async def test_bing_without_credentials_uses_browser():
    client = AsyncMock()
    browser = AsyncMock()
    browser.fetch_search_page.return_value = None

    with patch.dict(os.environ, {"BING_API_KEY": ""}):
        provider = BingSearchProvider(client, browser)
        results = await provider.search("test")

    assert results == []
    client.get.assert_not_awaited()
    browser.fetch_search_page.assert_awaited_once()


@pytest.mark.asyncio
async def test_bing_api_success_skips_browser():
    client = AsyncMock()
    response = Mock()
    response.json.return_value = {
        "webPages": {"value": [{"url": "https://example.com/article", "name": "Example", "snippet": "Snippet"}]}
    }
    response.raise_for_status = Mock()
    client.get.return_value = response
    browser = AsyncMock()

    with patch.dict(os.environ, {"BING_API_KEY": "key"}):
        provider = BingSearchProvider(client, browser)
        results = await provider.search("test")

    assert len(results) == 1
    assert results[0].provider == "bing_api"
    browser.fetch_search_page.assert_not_awaited()


@pytest.mark.asyncio
async def test_web_search_merges_deduplicates_and_caps_results():
    tool = WebSearchTool(max_results=20)
    providers = []
    for name, url in [
        ("duckduckgo", "https://shared.example/page"),
        ("google", "https://shared.example/page"),
        ("bing", "https://unique.example/page"),
    ]:
        provider = MagicMock()
        provider.provider_name = name
        provider.search = AsyncMock(return_value=[Source(name=name, url=url, provider=name)])
        providers.append(provider)
    tool._providers = providers

    results = await tool.search("test")
    assert len(results) == 2
    assert {source.provider for source in results} == {"duckduckgo", "bing"}


@pytest.mark.asyncio
async def test_web_search_isolates_provider_failure():
    tool = WebSearchTool()
    good = MagicMock()
    good.provider_name = "good"
    good.search = AsyncMock(return_value=[Source(name="Good", url="https://good.example", provider="good")])
    bad = MagicMock()
    bad.provider_name = "bad"
    bad.search = AsyncMock(side_effect=RuntimeError("boom"))
    tool._providers = [good, bad]

    results = await tool.search("test")
    assert len(results) == 1
    assert results[0].provider == "good"


@pytest.mark.asyncio
async def test_web_search_respects_combined_limit():
    tool = WebSearchTool(max_results=10)
    provider = MagicMock()
    provider.provider_name = "test"
    provider.search = AsyncMock(
        return_value=[
            Source(name=str(i), url=f"https://example{i}.com", provider="test")
            for i in range(MAX_COMBINED_RESULTS + 5)
        ]
    )
    tool._providers = [provider]

    results = await tool.search("test")
    assert len(results) == MAX_COMBINED_RESULTS


@pytest.mark.asyncio
async def test_browser_manager_closes_context_and_page():
    manager = _PlaywrightBrowserManager()
    fake_page = AsyncMock()
    fake_response = Mock(status=200)
    fake_page.goto.return_value = fake_response
    fake_page.content.return_value = "<html>" + ("x" * 600) + "</html>"
    fake_context = AsyncMock()
    fake_context.new_page.return_value = fake_page
    fake_browser = AsyncMock()
    fake_browser.new_context.return_value = fake_context
    manager._browser = fake_browser

    result = await manager.fetch_search_page("https://example.com/search")

    assert result is not None
    fake_context.close.assert_awaited_once()
    fake_page.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_browser_manager_reuses_browser_and_rotates_profiles():
    manager = _PlaywrightBrowserManager()
    fake_page = AsyncMock()
    fake_page.goto.return_value = Mock(status=200)
    fake_page.content.return_value = "<html>" + ("x" * 600) + "</html>"
    fake_context = AsyncMock()
    fake_context.new_page.return_value = fake_page
    fake_browser = AsyncMock()
    fake_browser.new_context.return_value = fake_context
    manager._browser = fake_browser

    await manager.fetch_search_page("https://example.com/one")
    await manager.fetch_search_page("https://example.com/two")

    assert fake_browser.new_context.await_count == 2
    assert fake_browser.new_context.call_args_list[0].kwargs["user_agent"] != fake_browser.new_context.call_args_list[1].kwargs["user_agent"]
