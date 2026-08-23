#!/usr/bin/env python3
"""
End-to-end test: Researcher -> ContentStrategist for Power.win Editorial Methodology.
"""

import sys
import os
import json

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from power_win_content.agents.content_writer import ContentWriterAgent
from power_win_content.config import Settings
from power_win_content.llm.client import LLMClient
from power_win_content.research.researcher import Researcher
from power_win_content.research.tools import WebSearchTool, HybridFetcher, SitemapFetcher
from power_win_content.strategy.strategist import ContentStrategist


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


def main():
    print("=" * 60)
    print("END-TO-END TEST: Power.win Editorial Methodology")
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
    print("RESEARCH")
    print("=" * 60)
    print()

    # Research Status
    print(f"research status: {get_enum_value(result.status)}")
    print()

    # Power.win facts
    print(f"number of Power.win facts: {len(result.power_win_facts)}")
    if result.power_win_facts:
        for i, claim in enumerate(result.power_win_facts, 1):
            print(format_claim(claim, i))
            print()
    else:
        print("  (none)")
    print()

    # External facts
    print(f"number of external facts: {len(result.external_facts)}")
    if result.external_facts:
        for i, claim in enumerate(result.external_facts, 1):
            print(format_claim(claim, i))
            print()
    else:
        print("  (none)")
    print()

    # Unsupported claims
    print(f"unsupported claims: {len(result.unsupported_claims)}")
    if result.unsupported_claims:
        for i, claim in enumerate(result.unsupported_claims, 1):
            lines = [f"  {i}. {claim.text}"]
            lines.append(f"     Status: {get_enum_value(claim.status)}")
            lines.append(f"     Reason: {claim.notes or 'No supporting evidence found'}")
            print("\n".join(lines))
            print()
    else:
        print("  (none)")
    print()

    # Research gaps
    print(f"research gaps: {len(result.research_gaps)}")
    if result.research_gaps:
        for i, gap in enumerate(result.research_gaps, 1):
            lines = [f"  {i}. {gap.question}"]
            lines.append(f"     Reason: {gap.reason}")
            if gap.attempted_sources:
                lines.append(f"     Attempted: {', '.join(gap.attempted_sources[:3])}")
            lines.append(f"     Importance: {gap.importance}")
            print("\n".join(lines))
            print()
    else:
        print("  (none)")
    print()

    # Conflicting information
    print(f"conflicting claims: {len(result.conflicting_information)}")
    if result.conflicting_information:
        for i, conflict in enumerate(result.conflicting_information, 1):
            lines = [f"  {i}. Topic: {conflict.topic}"]
            lines.append(f"     Claim A: {conflict.claim_a.text[:150]}...")
            lines.append(f"     Claim B: {conflict.claim_b.text[:150]}...")
            lines.append(f"     Resolution: {conflict.resolution}")
            lines.append(f"     Status: {get_enum_value(conflict.status)}")
            print("\n".join(lines))
            print()
    else:
        print("  (none)")
    print()

    # 6. Generate Content Strategy via ContentStrategist
    print("=" * 60)
    print("STRATEGY")
    print("=" * 60)
    print()

    strategist = ContentStrategist(llm_client=llm_client)
    brief = strategist.create_brief(topic, result)

    # SEO
    print(f"recommended title: {brief.seo.recommended_title}")
    print(f"primary keyword: {brief.seo.primary_keyword}")
    print(f"secondary keywords: {', '.join(brief.seo.secondary_keywords) if brief.seo.secondary_keywords else '(none)'}")
    print(f"search intent: {brief.seo.search_intent}")
    print()
    print("SEO recommendations:")
    if brief.seo.recommended_headings:
        print("  recommended headings:")
        for h in brief.seo.recommended_headings:
            print(f"    - {h}")
    if brief.seo.questions_to_answer:
        print("  questions to answer:")
        for q in brief.seo.questions_to_answer:
            print(f"    - {q}")
    if brief.seo.internal_linking_opportunities:
        print("  internal linking opportunities:")
        for link in brief.seo.internal_linking_opportunities:
            print(f"    - {link}")
    if brief.seo.semantic_coverage_requirements:
        print("  semantic coverage requirements:")
        for req in brief.seo.semantic_coverage_requirements:
            print(f"    - {req}")
    print()

    # AIO
    print("AIO recommendations:")
    if brief.aio.direct_answer_questions:
        print("  direct answer questions:")
        for q in brief.aio.direct_answer_questions:
            print(f"    - {q}")
    if brief.aio.concise_answers:
        print("  concise answers:")
        for q, a in brief.aio.concise_answers.items():
            print(f"    Q: {q}")
            print(f"    A: {a}")
    if brief.aio.definitions:
        print("  definitions:")
        for term, defn in brief.aio.definitions.items():
            print(f"    {term}: {defn}")
    if brief.aio.important_factual_statements:
        print("  important factual statements:")
        for fact in brief.aio.important_factual_statements:
            print(f"    - {fact}")
    if brief.aio.entities:
        print("  entities:")
        for e in brief.aio.entities:
            print(f"    - {e}")
    if brief.aio.evidence_requirements:
        print("  evidence requirements:")
        for req in brief.aio.evidence_requirements:
            print(f"    - {req}")
    if brief.aio.structured_information_requirements:
        print("  structured information requirements:")
        for req in brief.aio.structured_information_requirements:
            print(f"    - {req}")
    print()

    # GEO
    print("GEO recommendations:")
    if brief.geo.important_entities:
        print("  important entities:")
        for e in brief.geo.important_entities:
            print(f"    - {e}")
    if brief.geo.entity_relationships:
        print("  entity relationships:")
        for rel in brief.geo.entity_relationships:
            print(f"    - {rel}")
    if brief.geo.authoritative_external_sources:
        print("  authoritative external sources:")
        for src in brief.geo.authoritative_external_sources:
            print(f"    - {src}")
    if brief.geo.power_win_first_party_facts:
        print("  Power.win first-party facts:")
        for fact in brief.geo.power_win_first_party_facts:
            print(f"    - {fact}")
    if brief.geo.unique_information:
        print("  unique information:")
        for fact in brief.geo.unique_information:
            print(f"    - {fact}")
    if brief.geo.citation_evidence_opportunities:
        print("  citation evidence opportunities:")
        for opp in brief.geo.citation_evidence_opportunities:
            print(f"    - {opp}")
    if brief.geo.factual_consistency_requirements:
        print("  factual consistency requirements:")
        for req in brief.geo.factual_consistency_requirements:
            print(f"    - {req}")
    if brief.geo.questions_to_answer_clearly:
        print("  questions to answer clearly:")
        for q in brief.geo.questions_to_answer_clearly:
            print(f"    - {q}")
    print()

    # Facts recommended for the writer
    print("facts recommended for the writer:")
    recommended_facts = brief.get_all_recommended_facts()
    if recommended_facts:
        for i, fact in enumerate(recommended_facts, 1):
            print(f"  {i}. {fact}")
    else:
        print("  (none)")
    print()

    # All entities
    print("important entities (combined):")
    all_entities = brief.get_all_required_entities()
    if all_entities:
        for e in all_entities:
            print(f"  - {e}")
    else:
        print("  (none)")
    print()

    # Strategy metadata
    print("strategy metadata:")
    print(f"  total verified facts: {brief.total_verified_facts}")
    print(f"  total Power.win facts: {brief.total_power_win_facts}")
    print(f"  total external facts: {brief.total_external_facts}")
    print(f"  research gaps count: {brief.research_gaps_count}")
    print(f"  unsupported claims count: {brief.unsupported_claims_count}")
    print(f"  conflicts count: {brief.conflicts_count}")
    print()

    # 7. Generate Article via ContentWriterAgent
    print("=" * 60)
    print("WRITING ARTICLE")
    print("=" * 60)
    print()
    writer = ContentWriterAgent(llm_client=llm_client)
    article = writer.generate(brief)
    print(article)

    print()
    print("=" * 60)
    print("END-TO-END TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()