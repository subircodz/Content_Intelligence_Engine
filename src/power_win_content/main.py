import logging
import sys
from typing import Optional

from rich.console import Console

from power_win_content.agents.domain_content_writer import DomainContentWriterAgent
from power_win_content.client import ClientConfig
from power_win_content.competitors.analyzer import CompetitorAnalyzer
from power_win_content.competitors.models import CompetitorAnalysis
from power_win_content.config import Settings
from power_win_content.llm.client import LLMClient
from power_win_content.output.docx_writer import save_article_docx
from power_win_content.research.domain_researcher import DomainResearcher
from power_win_content.research.models import PhaseStatus
from power_win_content.research.tools.sitemap_fetcher import SitemapFetcher
from power_win_content.strategy.domain_strategist import DomainContentStrategist
from power_win_content.ui import (
    display_banner, display_competitor_domains, display_competitor_summary,
    display_error, display_info, display_pipeline_completion, display_phase_result,
    display_summary_table, display_welcome, prompt_user_topic,
)

console = Console()


def run_pipeline(topic: str, client_config: ClientConfig) -> Optional[str]:
    display_info(f"Target: [bold]{client_config.name}[/bold] ({client_config.domain})")
    display_info(f"Target Topic: [bold]{topic}[/bold]")

    settings = Settings()
    llm_client = LLMClient(base_url=settings.llm_base_url, model=settings.llm_model)
    pipeline_statuses: list[PhaseStatus] = []

    display_info("Executing Research Phase (first-party and external sources)...")
    research_status = PhaseStatus.FAILED
    research_result = None
    try:
        with console.status("[bold cyan]Researching target and external sources..."):
            with DomainResearcher(
                llm_client=llm_client,
                client_config=client_config,
                sitemap_fetcher=SitemapFetcher(client_config=client_config),
            ) as researcher:
                research_result, research_status = researcher.research(topic)
    except Exception as exc:
        display_error(f"Research phase failed: {exc}")
    pipeline_statuses.append(research_status)

    if research_result is None or research_status == PhaseStatus.FAILED:
        display_phase_result("Research Phase", PhaseStatus.FAILED, "Could not produce research results.")
        display_pipeline_completion(False, False)
        return None

    first_party_facts = len(research_result.first_party_facts)
    external_facts = len(research_result.external_facts)
    display_phase_result("Research Phase", research_status, f"{first_party_facts} first-party facts, {external_facts} external facts found.")

    display_info("Discovering content competitors...")
    competitor_status = PhaseStatus.FAILED
    competitor_analysis: Optional[CompetitorAnalysis] = None
    try:
        analyzer = CompetitorAnalyzer(llm_client=llm_client, client_config=client_config, max_competitors=5)
        with console.status("[bold cyan]Analyzing competitor content..."):
            competitor_analysis, competitor_status = analyzer.analyze(topic)
        if competitor_analysis and competitor_analysis.domains_analyzed:
            display_competitor_domains(competitor_analysis.analyzed_sources)
            display_competitor_summary(
                competitors_selected=competitor_analysis.domains_analyzed,
                successfully_analyzed=competitor_analysis.successfully_fetched,
                processing_failures=competitor_analysis.failures,
                missing_topics=len(competitor_analysis.gaps.missing_topics),
                missing_questions=len(competitor_analysis.gaps.missing_questions),
                missing_entities=len(competitor_analysis.gaps.missing_entities),
                recommended_angles=len(competitor_analysis.gaps.missing_angles),
            )
        display_phase_result("Competitor Analysis", competitor_status)
    except Exception as exc:
        competitor_status = PhaseStatus.DEGRADED
        display_phase_result("Competitor Analysis", competitor_status, f"Could not complete: {exc}")
    pipeline_statuses.append(competitor_status)

    strategy_status = PhaseStatus.FAILED
    brief = None
    try:
        with console.status("[bold cyan]Executing Strategy Phase (SEO, AIO, GEO brief)..."):
            strategist = DomainContentStrategist(llm_client=llm_client, client_config=client_config)
            brief, strategy_status = strategist.create_brief(topic, research_result, competitor_analysis=competitor_analysis)
        display_phase_result("Strategy Phase", strategy_status)
    except Exception as exc:
        display_error(f"Strategy phase failed: {exc}")
        display_phase_result("Strategy Phase", PhaseStatus.FAILED, "Strategy brief was not produced.")
    pipeline_statuses.append(strategy_status)
    if brief is None:
        display_pipeline_completion(False, any(s == PhaseStatus.DEGRADED for s in pipeline_statuses))
        return None

    writing_status = PhaseStatus.FAILED
    article = None
    try:
        with console.status("[bold cyan]Executing Writing Phase..."):
            article = DomainContentWriterAgent(llm_client=llm_client, client_config=client_config).generate(brief)
        if article and article.strip():
            writing_status = PhaseStatus.SUCCESS
            display_phase_result("Writing Phase", writing_status, f"~{len(article.split())} words generated.")
        else:
            display_phase_result("Writing Phase", PhaseStatus.FAILED, "No article was generated.")
    except Exception as exc:
        display_phase_result("Writing Phase", PhaseStatus.FAILED, f"Unexpected error: {exc}")
    pipeline_statuses.append(writing_status)
    if writing_status == PhaseStatus.FAILED:
        display_pipeline_completion(False, any(s == PhaseStatus.DEGRADED for s in pipeline_statuses))
        return None

    docx_status = PhaseStatus.FAILED
    docx_path = None
    try:
        docx_path = save_article_docx(article, topic, competitor_analysis=competitor_analysis)
        if docx_path:
            docx_status = PhaseStatus.SUCCESS
            display_phase_result("DOCX Generation", docx_status, str(docx_path))
        else:
            display_phase_result("DOCX Generation", PhaseStatus.FAILED, "Could not write document.")
    except Exception as exc:
        display_phase_result("DOCX Generation", PhaseStatus.FAILED, f"Unexpected error: {exc}")
    pipeline_statuses.append(docx_status)

    has_warnings = any(s == PhaseStatus.DEGRADED for s in pipeline_statuses)
    display_summary_table(
        topic=topic,
        research_status=str(research_result.status),
        pipeline_status_label="COMPLETED WITH WARNINGS" if has_warnings else "COMPLETED",
        first_party_facts_count=len(research_result.first_party_facts),
        external_facts_count=len(research_result.external_facts),
        gaps_count=len(research_result.research_gaps),
        unsupported_count=len(research_result.unsupported_claims),
        recommended_title=brief.seo.recommended_title,
        primary_keyword=brief.seo.primary_keyword,
        article_length=len(article.split()),
        competitors_selected=competitor_analysis.domains_analyzed if competitor_analysis else 0,
        competitors_analyzed=competitor_analysis.successfully_fetched if competitor_analysis else 0,
        competitors_failed=competitor_analysis.failures if competitor_analysis else 0,
    )
    display_pipeline_completion(docx_status == PhaseStatus.SUCCESS, has_warnings)
    return article


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Content Intelligence Engine")
    parser.add_argument("topic", nargs="*", help="Article title or topic")
    parser.add_argument("--target-domain", help="Target website domain; overrides TARGET_DOMAIN")
    parser.add_argument("--target-brand", help="Target brand name; overrides TARGET_BRAND")
    parser.add_argument("--first-party-sitemap", action="append", dest="sitemaps", help="First-party sitemap URL; repeatable")
    parser.add_argument("--debug", action="store_true", help="Enable detailed debug output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING)
    display_banner()
    display_welcome()

    settings = Settings()
    domain = args.target_domain or settings.client.domain
    brand = args.target_brand or settings.client.name
    sitemaps = tuple(args.sitemaps) if args.sitemaps else settings.client.first_party_sitemaps
    client_config = ClientConfig(name=brand, domain=domain, first_party_sitemaps=sitemaps)

    topic = " ".join(args.topic) if args.topic else prompt_user_topic()
    try:
        run_pipeline(topic, client_config)
    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline execution cancelled by user.[/yellow]")
        sys.exit(0)
    except Exception as exc:
        display_error(f"Pipeline execution failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
