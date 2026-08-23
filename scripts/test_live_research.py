#!/usr/bin/env python3
"""
Live end-to-end research demo using OmniRoute LLM + real WebSearchTool + HybridFetcher + SitemapFetcher.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from power_win_content.config import Settings
from power_win_content.llm.client import LLMClient
from power_win_content.research.researcher import Researcher
from power_win_content.research.tools import WebSearchTool, WebFetcher, HybridFetcher, SitemapFetcher


def get_enum_value(val) -> str:
    """Extract string value from enum or return string as-is."""
    return val.value if hasattr(val, 'value') else val


def format_claim(claim, index: int) -> str:
    """Format a claim for output."""
    lines = [f"  {index}. {claim.text}"]
    lines.append(f"     Status: {get_enum_value(claim.status)}")
    lines.append(f"     Confidence: {claim.confidence:.2f}")
    lines.append(f"     Nature: {get_enum_value(claim.nature)}")
    for ev in claim.evidence:
        lines.append(f"     Source: {ev.source.name}")
        lines.append(f"     URL: {ev.source.url}")
        lines.append(f"     Source Type: {get_enum_value(ev.source.source_type)}")
        lines.append(f"     Retrieval Method: {ev.retrieval_method}")
        lines.append(f"     Excerpt: {ev.excerpt[:200]}...")
    return "\n".join(lines)


def format_unsupported(claim, index: int) -> str:
    """Format an unsupported claim for output."""
    lines = [f"  {index}. {claim.text}"]
    lines.append(f"     Status: {get_enum_value(claim.status)}")
    lines.append(f"     Reason: {claim.notes or 'No supporting evidence found'}")
    return "\n".join(lines)


def format_gap(gap, index: int) -> str:
    """Format a research gap for output."""
    lines = [f"  {index}. {gap.question}"]
    lines.append(f"     Reason: {gap.reason}")
    if gap.attempted_sources:
        lines.append(f"     Attempted: {', '.join(gap.attempted_sources[:3])}")
    lines.append(f"     Importance: {gap.importance}")
    return "\n".join(lines)


def format_conflict(conflict, index: int) -> str:
    """Format conflicting information for output."""
    lines = [f"  {index}. Topic: {conflict.topic}"]
    lines.append(f"     Claim A: {conflict.claim_a.text[:150]}...")
    lines.append(f"     Claim B: {conflict.claim_b.text[:150]}...")
    lines.append(f"     Resolution: {conflict.resolution}")
    lines.append(f"     Status: {get_enum_value(conflict.status)}")
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("LIVE RESEARCH DEMO: Power.win Editorial Methodology")
    print("=" * 60)
    print()

    # 1. Load Settings
    print("Loading Settings...")
    settings = Settings()
    print(f"  OmniRoute Base URL: {settings.omniroute_base_url}")
    print(f"  OmniRoute Model: {settings.omniroute_model}")
    print()

    # 2. Create LLMClient
    print("Creating LLMClient...")
    try:
        llm_client = LLMClient(
            base_url=settings.omniroute_base_url,
            model=settings.omniroute_model,
        )
        print("  LLMClient created successfully")
    except Exception as e:
        print(f"  ERROR creating LLMClient: {e}")
        sys.exit(1)
    print()

    # 3. Create Researcher
    print("Creating Researcher with WebSearchTool + HybridFetcher + SitemapFetcher...")
    search_tool = WebSearchTool(timeout=20.0)
    fetcher = HybridFetcher()  # Uses HTTP + browser fallback
    sitemap_fetcher = SitemapFetcher()
    researcher = Researcher(
        llm_client=llm_client,
        search_tool=search_tool,
        fetcher=fetcher,
        sitemap_fetcher=sitemap_fetcher,
    )
    print("  Researcher created successfully")
    print()

    # 4. Research the topic
    topic = "How we Evaluate Online Casinos: Power.win Editorial & Review Methodology"
    print(f"Researching: {topic}")
    print("-" * 60)
    print()

    try:
        result = researcher.research(topic)
    except Exception as e:
        print(f"ERROR during research: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        researcher.close()
        sys.exit(1)

    researcher.close()

    # 5. Print concise research report
    print("=" * 60)
    print("RESEARCH REPORT")
    print("=" * 60)
    print()

    # Research Status
    print(f"RESEARCH STATUS: {get_enum_value(result.status)}")
    print(f"Summary: {result.summary}")
    print()

    # Power.win facts
    print(f"Power.win facts ({len(result.power_win_facts)}):")
    if result.power_win_facts:
        for i, claim in enumerate(result.power_win_facts, 1):
            print(format_claim(claim, i))
            print()
    else:
        print("  (none)")
    print()

    # External facts
    print(f"External facts ({len(result.external_facts)}):")
    if result.external_facts:
        for i, claim in enumerate(result.external_facts, 1):
            print(format_claim(claim, i))
            print()
    else:
        print("  (none)")
    print()

    # Unsupported claims
    print(f"Unsupported claims ({len(result.unsupported_claims)}):")
    if result.unsupported_claims:
        for i, claim in enumerate(result.unsupported_claims, 1):
            print(format_unsupported(claim, i))
            print()
    else:
        print("  (none)")
    print()

    # Research gaps
    print(f"Research gaps ({len(result.research_gaps)}):")
    if result.research_gaps:
        for i, gap in enumerate(result.research_gaps, 1):
            print(format_gap(gap, i))
            print()
    else:
        print("  (none)")
    print()

    # Conflicting information
    print(f"Conflicting information ({len(result.conflicting_information)}):")
    if result.conflicting_information:
        for i, conflict in enumerate(result.conflicting_information, 1):
            print(format_conflict(conflict, i))
            print()
    else:
        print("  (none)")
    print()

    # Summary statistics as required
    print("=" * 60)
    print("RESEARCH SUMMARY STATISTICS")
    print("=" * 60)
    print(f"1. Power.win first-party facts: {len(result.power_win_facts)}")
    print(f"2. External facts: {len(result.external_facts)}")
    print(f"3. Unsupported claims: {len(result.unsupported_claims)}")
    print(f"4. Research gaps: {len(result.research_gaps)}")
    print(f"5. Conflicts: {len(result.conflicting_information)}")

    # Which first-party domains supplied evidence
    first_party_domains = set()
    for claim in result.power_win_facts:
        for ev in claim.evidence:
            url = str(ev.source.url).lower()
            if "docs.power.win" in url:
                first_party_domains.add("docs.power.win")
            elif "blog.power.win" in url:
                first_party_domains.add("blog.power.win")
            elif "power.win" in url:
                first_party_domains.add("power.win")

    print(f"6. First-party domains supplying evidence: {', '.join(sorted(first_party_domains)) if first_party_domains else 'none'}")

    # Whether power.win itself was accessible
    power_win_accessible = "power.win" in first_party_domains and "docs.power.win" not in first_party_domains and "blog.power.win" not in first_party_domains
    # More precise: check if power.win (main domain) specifically was accessible
    power_win_main_accessible = False
    for claim in result.power_win_facts:
        for ev in claim.evidence:
            url = str(ev.source.url).lower()
            if url.startswith("https://power.win/") and "docs.power.win" not in url and "blog.power.win" not in url:
                power_win_main_accessible = True
    print(f"7. power.win main site accessible: {'Yes' if power_win_main_accessible else 'No (Cloudflare blocked)'}")

    # Whether docs.power.win/blog.power.win supplied usable evidence
    docs_evidence = "docs.power.win" in first_party_domains
    blog_evidence = "blog.power.win" in first_party_domains
    print(f"8. docs.power.win supplied usable evidence: {'Yes' if docs_evidence else 'No'}")
    print(f"9. blog.power.win supplied usable evidence: {'Yes' if blog_evidence else 'No'}")

    print("=" * 60)
    print("Research complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()