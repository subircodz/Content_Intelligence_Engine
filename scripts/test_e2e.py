#!/usr/bin/env python3
"""End-to-end smoke test for the configured content intelligence pipeline."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from intelligence_content_engine.agents.domain_content_writer import DomainContentWriterAgent
from intelligence_content_engine.competitors.analyzer import CompetitorAnalyzer
from intelligence_content_engine.config import Settings
from intelligence_content_engine.llm.client import LLMClient
from intelligence_content_engine.output.docx_writer import save_article_docx
from intelligence_content_engine.research.domain_researcher import DomainResearcher
from intelligence_content_engine.research.tools import HybridFetcher, SitemapFetcher, WebSearchTool
from intelligence_content_engine.strategy.domain_strategist import DomainContentStrategist


async def run(topic: str) -> int:
    settings = Settings()
    target = settings.client
    if target is None:
        raise ValueError("TARGET_DOMAIN is required for the E2E smoke test")

    llm = LLMClient(settings.llm_base_url, settings.llm_model, api_key=settings.llm_api_key)

    print("=" * 60)
    print("CONTENT INTELLIGENCE ENGINE E2E SMOKE TEST")
    print("=" * 60)
    print(f"Target: {target.name} ({target.domain})")
    print(f"Topic: {topic}")

    search = WebSearchTool(timeout=20.0)
    fetcher = HybridFetcher()
    sitemap = SitemapFetcher(client_config=target, fetcher=fetcher)

    async with DomainResearcher(
        llm_client=llm,
        client_config=target,
        search_tool=search,
        fetcher=fetcher,
        sitemap_fetcher=sitemap,
    ) as researcher:
        research, research_status = await researcher.research(topic)

    print(f"Research: {research_status.value}")
    print(f"First-party facts: {len(research.first_party_facts)}")
    print(f"External facts: {len(research.external_facts)}")

    async with CompetitorAnalyzer(llm, target, search_tool=search, fetcher=fetcher, max_competitors=5) as analyzer:
        competitors, competitor_status = await analyzer.analyze(topic)

    print(f"Competitor analysis: {competitor_status.value}")
    print(f"Competitors analyzed: {competitors.successfully_fetched}/{competitors.domains_analyzed}")

    brief, strategy_status = DomainContentStrategist(llm, target).create_brief(topic, research, competitors)
    print(f"Strategy: {strategy_status.value}")
    if brief is None:
        return 1

    article = DomainContentWriterAgent(llm, target).generate(brief)
    if not article.strip():
        print("Writing: failed")
        return 1

    output = save_article_docx(article, topic, competitor_analysis=competitors)
    print(f"Writing: success ({len(article.split())} words)")
    print(f"DOCX: {output}")
    return 0 if output else 1


def main() -> int:
    topic = " ".join(sys.argv[1:]).strip() or "Example content research topic"
    return asyncio.run(run(topic))


if __name__ == "__main__":
    raise SystemExit(main())
