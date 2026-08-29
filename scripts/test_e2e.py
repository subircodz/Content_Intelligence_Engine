#!/usr/bin/env python3
"""End-to-end smoke test for the configured content intelligence pipeline."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from intelligence_content_engine.agents.domain_content_writer import DomainContentWriterAgent
from intelligence_content_engine.competitors.analyzer import CompetitorAnalyzer
from intelligence_content_engine.config import Settings
from intelligence_content_engine.llm.client import LLMClient
from intelligence_content_engine.research.domain_researcher import DomainResearcher
from intelligence_content_engine.research.tools import HybridFetcher, SitemapFetcher, WebSearchTool
from intelligence_content_engine.strategy.domain_strategist import DomainContentStrategist


def main() -> int:
    settings = Settings()
    topic = " ".join(sys.argv[1:]).strip() or "Example content research topic"
    target = settings.client
    llm = LLMClient(settings.llm_base_url, settings.llm_model)

    print("=" * 60)
    print("CONTENT INTELLIGENCE ENGINE E2E SMOKE TEST")
    print("=" * 60)
    print(f"Target: {target.name} ({target.domain})")
    print(f"Topic: {topic}")

    researcher = DomainResearcher(
        llm_client=llm,
        client_config=target,
        search_tool=WebSearchTool(timeout=20.0),
        fetcher=HybridFetcher(),
        sitemap_fetcher=SitemapFetcher(client_config=target),
    )
    try:
        research, research_status = researcher.research(topic)
    finally:
        researcher.__exit__(None, None, None)

    print(f"Research: {research_status.value}")
    print(f"First-party facts: {len(research.first_party_facts)}")
    print(f"External facts: {len(research.external_facts)}")

    competitors, competitor_status = CompetitorAnalyzer(llm, target, max_competitors=5).analyze(topic)
    print(f"Competitor analysis: {competitor_status.value}")
    print(f"Competitors analyzed: {competitors.successfully_fetched}/{competitors.domains_analyzed}")

    brief, strategy_status = DomainContentStrategist(llm, target).create_brief(topic, research, competitors)
    print(f"Strategy: {strategy_status.value}")

    article = DomainContentWriterAgent(llm, target).generate(brief)
    print(f"Writing: {'success' if article.strip() else 'failed'}")
    return 0 if article.strip() else 1


if __name__ == "__main__":
    raise SystemExit(main())
