import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from intelligence_content_engine.research.models import PhaseStatus

console = Console()


def display_banner() -> None:
    banner = """
┌──────────────────────────────────────────────────────────────────────────┐
│  CONTENT INTELLIGENCE ENGINE                                             │
│  Research + Market Intelligence + SEO/AIO/GEO + Content Writer           │
└──────────────────────────────────────────────────────────────────────────┘
"""
    console.print(Panel(Text(banner.strip(), style="bold cyan"), expand=False))


def display_welcome() -> None:
    console.print("[bold cyan]Welcome to the Content Intelligence Engine![/bold cyan]")
    console.print("Generate research-backed, SEO/AIO/GEO-optimized article drafts with human review.\n")


def prompt_user_topic() -> str:
    while True:
        try:
            topic = Prompt.ask("[bold green]Enter the article title/topic you want to write[/bold green]").strip()
            if topic:
                return topic
            console.print("[yellow]Topic cannot be empty.[/yellow]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Operation cancelled by user.[/yellow]")
            sys.exit(0)


def display_info(message: str) -> None:
    console.print(f"[cyan][INFO][/cyan] {message}")


def display_success(message: str) -> None:
    console.print(f"[green][SUCCESS][/green] {message}")


def display_warning(message: str) -> None:
    console.print(f"[yellow][WARNING][/yellow] {message}")


def display_error(message: str) -> None:
    console.print(f"[red][ERROR][/red] {message}")


def display_phase_result(phase_name: str, status: PhaseStatus, detail: str = "") -> None:
    suffix = f" {detail}" if detail else ""
    if status == PhaseStatus.SUCCESS:
        console.print(f"[green][SUCCESS][/green] {phase_name} completed.{suffix}")
    elif status == PhaseStatus.DEGRADED:
        console.print(f"[yellow][WARNING][/yellow] {phase_name} completed with warnings.{suffix}")
    else:
        console.print(f"[red][ERROR][/red] {phase_name} failed.{suffix}")


def display_pipeline_completion(docx_created: bool, has_warnings: bool) -> None:
    if docx_created and not has_warnings:
        console.print("[bold green][SUCCESS] Pipeline completed successfully.[/bold green]")
    elif docx_created:
        console.print("[bold yellow][WARNING] Pipeline completed with warnings. Article and DOCX are ready.[/bold yellow]")
    else:
        console.print("[bold red][ERROR] Pipeline failed. No document was produced.[/bold red]")


def display_competitor_summary(competitors_selected: int, successfully_analyzed: int, processing_failures: int, missing_topics: int, missing_questions: int, missing_entities: int, recommended_angles: int) -> None:
    table = Table(show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="bold white", justify="right")
    for label, value in (("Competitors Selected", competitors_selected), ("Successfully Analyzed", successfully_analyzed), ("Processing Failures", processing_failures), ("Missing Topics", missing_topics), ("Missing Questions", missing_questions), ("Missing Entities", missing_entities), ("Recommended Angles", recommended_angles)):
        if label != "Processing Failures" or value:
            table.add_row(label, str(value))
    console.print(table)


def display_competitor_domains(sources: list) -> None:
    if not sources:
        return
    console.print("[cyan]Competitors:[/cyan]")
    for idx, source in enumerate(sources, start=1):
        indicator = "[green]+[/green]" if source.fetched_successfully else "[red]x[/red]"
        reason = f" ({source.fetch_failure_reason})" if source.fetch_failure_reason else ""
        console.print(f"  {idx}. {indicator} {source.domain}{reason}")


def _format_research_status(raw: str) -> str:
    if "." in raw:
        raw = raw.rsplit(".", 1)[-1]
    return {"verified": "Verified", "partially_supported": "Partially Supported", "unsupported": "Unsupported", "conflicting": "Conflicting", "uncertain": "Uncertain"}.get(raw.lower(), raw)


def display_summary_table(topic: str, research_status: str, pipeline_status_label: str, first_party_facts_count: int, external_facts_count: int, gaps_count: int, unsupported_count: int, recommended_title: str, primary_keyword: str, article_length: int, competitors_selected: int = 0, competitors_analyzed: int = 0, competitors_failed: int = 0) -> None:
    table = Table(title="Pipeline Summary", show_header=True, header_style="bold blue")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="bold white")
    table.add_row("Topic / Requested Title", topic)
    status_style = "[green]" if pipeline_status_label == "COMPLETED" else "[yellow]" if "WARNINGS" in pipeline_status_label else "[red]"
    table.add_row("Pipeline Status", f"{status_style}{pipeline_status_label}[/]")
    friendly = _format_research_status(research_status)
    table.add_row("Research", f"[green]{friendly}[/green]" if research_status.lower() in ("verified", "partially_supported") else f"[yellow]{friendly}[/yellow]")
    table.add_row("First-Party Facts", str(first_party_facts_count))
    table.add_row("External Facts", str(external_facts_count))
    table.add_row("Research Gaps", str(gaps_count))
    table.add_row("Unsupported Claims", str(unsupported_count))
    if competitors_selected:
        table.add_row("Competitors Selected", str(competitors_selected))
        table.add_row("Successfully Analyzed", str(competitors_analyzed))
        if competitors_failed:
            table.add_row("Competitor Failures", str(competitors_failed))
    table.add_row("SEO Recommended Title", recommended_title)
    table.add_row("Primary Keyword", primary_keyword)
    table.add_row("Article Word Count", f"~{article_length} words")
    console.print(table)
