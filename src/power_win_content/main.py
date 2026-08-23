import logging
import sys
from typing import Optional

from rich.console import Console

from power_win_content.agents.content_writer import ContentWriterAgent
from power_win_content.competitors.analyzer import CompetitorAnalyzer
from power_win_content.competitors.models import CompetitorAnalysis
from power_win_content.config import Settings
from power_win_content.llm.client import LLMClient
from power_win_content.output.docx_writer import save_article_docx
from power_win_content.research.models import PhaseStatus
from power_win_content.research.researcher import Researcher
from power_win_content.strategy.strategist import ContentStrategist
from power_win_content.ui import (
    display_banner,
    display_competitor_domains,
    display_competitor_summary,
    display_error,
    display_info,
    display_pipeline_completion,
    display_phase_result,
    display_success,
    display_summary_table,
    display_warning,
    display_welcome,
    prompt_user_topic,
)

console = Console()


def run_pipeline(topic: str) -> Optional[str]:
    display_info(f"Target Topic: [bold]{topic}[/bold]")

    settings = Settings()
    llm_client = LLMClient(
        base_url=settings.omniroute_base_url,
        model=settings.omniroute_model,
    )

    pipeline_statuses: list[PhaseStatus] = []

    # === RESEARCH PHASE ===
    display_info("Executing Research Phase (searching, fetching, analyzing)...")
    research_status = PhaseStatus.FAILED
    research_result = None
    try:
        with console.status("[bold cyan]Researching first-party and external sources..."):
            with Researcher(llm_client=llm_client) as researcher:
                research_result, research_status = researcher.research(topic)
    except Exception:
        research_status = PhaseStatus.FAILED
        display_error("Research phase encountered an unexpected error.")
        pipeline_statuses.append(PhaseStatus.FAILED)

    if research_status == PhaseStatus.DEGRADED:
        pipeline_statuses.append(PhaseStatus.DEGRADED)
        facts = len(research_result.power_win_facts) if research_result else 0
        ext_facts = len(research_result.external_facts) if research_result else 0
        display_phase_result(
            "Research Phase", PhaseStatus.DEGRADED,
            f"{facts} Power.win facts, {ext_facts} external facts found.",
        )
    elif research_status == PhaseStatus.SUCCESS:
        pipeline_statuses.append(PhaseStatus.SUCCESS)
        facts = len(research_result.power_win_facts) if research_result else 0
        ext_facts = len(research_result.external_facts) if research_result else 0
        display_phase_result(
            "Research Phase", PhaseStatus.SUCCESS,
            f"{facts} Power.win facts, {ext_facts} external facts found.",
        )
    else:
        pipeline_statuses.append(PhaseStatus.FAILED)
        display_phase_result("Research Phase", PhaseStatus.FAILED, "Could not produce research results.")

    # === COMPETITOR PHASE ===
    display_info("Discovering content competitors...")
    competitor_status = PhaseStatus.FAILED
    competitor_analysis: Optional[CompetitorAnalysis] = None
    try:
        competitor_analyzer = CompetitorAnalyzer(llm_client=llm_client, max_competitors=2)
        with console.status("[bold cyan]Analyzing competitor content..."):
            competitor_analysis, competitor_status = competitor_analyzer.analyze(topic)

        if competitor_analysis and competitor_analysis.domains_analyzed > 0:
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

        if competitor_status == PhaseStatus.SUCCESS:
            display_phase_result("Competitor Analysis", PhaseStatus.SUCCESS)
        else:
            if competitor_analysis and competitor_analysis.failures == competitor_analysis.domains_analyzed:
                display_phase_result("Competitor Analysis", PhaseStatus.DEGRADED, f"{competitor_analysis.failures} source processing failure(s).")
            elif competitor_analysis and competitor_analysis.failures > 0:
                display_phase_result("Competitor Analysis", PhaseStatus.DEGRADED, f"{competitor_analysis.failures} source processing failure(s).")
            else:
                display_warning("No usable competitor sources were found.")
    except Exception:
        competitor_status = PhaseStatus.DEGRADED
        display_phase_result("Competitor Analysis", PhaseStatus.DEGRADED, "Could not complete. Pipeline continues without competitor data.")

    # When all competitors failed, pass None to strategy so it treats
    # competitor data as genuinely unavailable — not as "no gaps found".
    competitor_for_strategy = competitor_analysis
    if competitor_analysis and competitor_analysis.failures == competitor_analysis.domains_analyzed:
        competitor_for_strategy = None

    pipeline_statuses.append(competitor_status)

    # === STRATEGY PHASE ===
    strategy_status = PhaseStatus.FAILED
    brief = None
    try:
        with console.status("[bold cyan]Executing Strategy Phase (SEO, AIO, GEO brief)..."):
            strategist = ContentStrategist(llm_client=llm_client)
            brief, strategy_status = strategist.create_brief(topic, research_result, competitor_analysis=competitor_for_strategy)
    except Exception:
        strategy_status = PhaseStatus.FAILED
        display_error("Strategy phase encountered an unexpected error.")

    if brief is not None:
        display_phase_result("Strategy Phase", strategy_status)
    else:
        display_phase_result("Strategy Phase", PhaseStatus.FAILED, "Strategy brief was not produced.")
    pipeline_statuses.append(strategy_status)

    # === WRITING PHASE ===
    writing_status = PhaseStatus.FAILED
    article = None
    try:
        with console.status("[bold cyan]Executing Writing Phase (generating article from brief)..."):
            writer = ContentWriterAgent(llm_client=llm_client)
            article = writer.generate(brief)

        if not article or not article.strip():
            writing_status = PhaseStatus.FAILED
            display_phase_result("Writing Phase", PhaseStatus.FAILED, "No article was generated.")
        else:
            writing_status = PhaseStatus.SUCCESS
            display_phase_result("Writing Phase", PhaseStatus.SUCCESS, f"~{len(article.split())} words generated.")
    except Exception:
        writing_status = PhaseStatus.FAILED
        display_phase_result("Writing Phase", PhaseStatus.FAILED, "An unexpected error occurred.")

    pipeline_statuses.append(writing_status)

    if writing_status == PhaseStatus.FAILED:
        docx_created = False
        has_warnings = any(s == PhaseStatus.DEGRADED for s in pipeline_statuses)
        display_pipeline_completion(docx_created, has_warnings)
        return None

    # === DOCX PHASE ===
    docx_status = PhaseStatus.FAILED
    docx_path = None
    try:
        docx_path = save_article_docx(article, topic, competitor_analysis=competitor_analysis)
        if docx_path is None:
            docx_status = PhaseStatus.FAILED
            display_phase_result("DOCX Generation", PhaseStatus.FAILED, "Could not write document.")
        else:
            docx_status = PhaseStatus.SUCCESS
            display_phase_result("DOCX Generation", PhaseStatus.SUCCESS, str(docx_path))
    except Exception:
        docx_status = PhaseStatus.FAILED
        display_phase_result("DOCX Generation", PhaseStatus.FAILED, "An unexpected error occurred.")

    pipeline_statuses.append(docx_status)
    docx_created = docx_status == PhaseStatus.SUCCESS

    # === FINAL SUMMARY ===
    if research_result is not None:
        has_warnings = any(s == PhaseStatus.DEGRADED for s in pipeline_statuses)

        if has_warnings:
            pipeline_label = "COMPLETED WITH WARNINGS"
        else:
            pipeline_label = "COMPLETED"

        display_summary_table(
            topic=topic,
            research_status=str(research_result.status),
            pipeline_status_label=pipeline_label,
            power_win_facts_count=len(research_result.power_win_facts),
            external_facts_count=len(research_result.external_facts),
            gaps_count=len(research_result.research_gaps),
            unsupported_count=len(research_result.unsupported_claims),
            recommended_title=brief.seo.recommended_title if brief else "N/A (strategy unavailable)",
            primary_keyword=brief.seo.primary_keyword if brief else "N/A",
            article_length=len(article.split()) if article else 0,
            competitors_selected=competitor_analysis.domains_analyzed if competitor_analysis else 0,
            competitors_analyzed=competitor_analysis.successfully_fetched if competitor_analysis else 0,
            competitors_failed=competitor_analysis.failures if competitor_analysis else 0,
        )

    has_warnings = any(s == PhaseStatus.DEGRADED for s in pipeline_statuses)
    display_pipeline_completion(docx_created, has_warnings)
    return article


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Power.win Content Intelligence Pipeline")
    parser.add_argument("topic", nargs="*", help="Article title or topic")
    parser.add_argument("--debug", action="store_true", help="Enable detailed debug output for research and fetching")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

        for logger_name in [
            "power_win_content.research",
            "power_win_content.research.tools",
            "power_win_content.llm",
            "power_win_content.strategy.strategist",
            "power_win_content.competitors",
            "httpx",
            "httpcore",
        ]:
            logging.getLogger(logger_name).setLevel(logging.ERROR)

    display_banner()
    display_welcome()

    if args.topic:
        topic = " ".join(args.topic)
    else:
        topic = prompt_user_topic()

    try:
        run_pipeline(topic)
    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline execution cancelled by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        display_error(f"Pipeline execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
