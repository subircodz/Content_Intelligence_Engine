#!/usr/bin/env python3
"""End-to-end smoke test for the configured content intelligence pipeline."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from power_win_content.agents.domain_content_writer import DomainContentWriterAgent
from power_win_content.competitors.analyzer import CompetitorAnalyzer
from power_win_content.config import Settings
from power_win_content.llm.client import LLMClient
from power_win_content.research.domain_researcher import DomainResearcher
from power_win_content.research.tools import HybridFetcher, SitemapFetcher, WebSearchTool
from power_win_content.strategy.domain_strategist import DomainContentStrategist


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
