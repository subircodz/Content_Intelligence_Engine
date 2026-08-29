#!/usr/bin/env python3
"""Live research smoke test using configured target and LLM settings."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from power_win_content.client import ClientConfig
from power_win_content.config import Settings
from power_win_content.llm.client import LLMClient
from power_win_content.research.domain_researcher import DomainResearcher
from power_win_content.research.models import PhaseStatus
from power_win_content.research.tools import HybridFetcher, SitemapFetcher, WebSearchTool


def main() -> int:
    settings = Settings()
    topic = " ".join(sys.argv[1:]).strip() or "Example content research topic"
    client = settings.client
    llm = LLMClient(base_url=settings.llm_base_url, model=settings.llm_model)

    print("=" * 60)
    print("LIVE RESEARCH SMOKE TEST")
    print("=" * 60)
    print(f"Target: {client.name} ({client.domain})")
    print(f"Topic: {topic}")
    print(f"LLM endpoint: {settings.llm_base_url}")
    print(f"LLM model: {settings.llm_model}")
    print()

    researcher = DomainResearcher(
        llm_client=llm,
        client_config=client,
        search_tool=WebSearchTool(timeout=20.0),
        fetcher=HybridFetcher(),
        sitemap_fetcher=SitemapFetcher(client_config=client),
    )

    try:
        result, status = researcher.research(topic)
    except Exception as exc:
        print(f"Research failed: {type(exc).__name__}: {exc}")
        return 1
    finally:
        researcher.__exit__(None, None, None)

    print(f"Phase status: {status.value}")
    print(f"Research status: {result.status}")
    print(f"First-party facts: {len(result.first_party_facts)}")
    print(f"External facts: {len(result.external_facts)}")
    print(f"Unsupported claims: {len(result.unsupported_claims)}")
    print(f"Research gaps: {len(result.research_gaps)}")
    print()

    if status == PhaseStatus.FAILED:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
