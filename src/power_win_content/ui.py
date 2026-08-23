import sys
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from power_win_content.research.models import PhaseStatus


console = Console()


def display_banner() -> None:
    clean_banner = """
┌──────────────────────────────────────────────────────────────────────────┐
│  POWER.WIN CONTENT INTELLIGENCE PLATFORM                                 │
│  Deep Research  +  Strategy Brief (SEO/AIO/GEO)  +  Content Writer       │
└──────────────────────────────────────────────────────────────────────────┘
"""
    console.print(Panel(Text(clean_banner.strip(), style="bold cyan"), expand=False))


def display_welcome() -> None:
    console.print("[bold cyan]Welcome to the Power.win Content Production Pipeline![/bold cyan]")
    console.print("Generate research-backed, SEO & AI optimized articles with verified first-party facts.\n")


def prompt_user_topic() -> str:
    while True:
        try:
            topic = Prompt.ask("[bold green]Enter the article title/topic you want to write[/bold green]").strip()
            if topic:
                return topic
            console.print("[yellow]Topic cannot be empty. Please enter a valid article title or topic.[/yellow]")
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
    """Display a per-phase result using SUCCESS / WARNING / ERROR labels."""
    if status == PhaseStatus.SUCCESS:
        console.print(f"[green][SUCCESS][/green] {phase_name} completed.{f' {detail}' if detail else ''}")
    elif status == PhaseStatus.DEGRADED:
        console.print(f"[yellow][WARNING][/yellow] {phase_name} completed with warnings.{f' {detail}' if detail else ''}")
    else:
        console.print(f"[red][ERROR][/red] {phase_name} failed.{f' {detail}' if detail else ''}")


def display_pipeline_completion(
    docx_created: bool,
    has_warnings: bool,
) -> None:
    """Display final pipeline status based on actual output.

    Rules:
    - docx_created=True  and has_warnings=False  → COMPLETED
    - docx_created=True  and has_warnings=True   → COMPLETED WITH WARNINGS
    - docx_created=False                          → FAILED
    """
    if docx_created and not has_warnings:
        console.print("[bold green][SUCCESS] Pipeline completed successfully.[/bold green]")
    elif docx_created and has_warnings:
        console.print("[bold yellow][WARNING] Pipeline completed with warnings. Article and DOCX are ready.[/bold yellow]")
    else:
        console.print("[bold red][ERROR] Pipeline failed. No document was produced.[/bold red]")


def display_competitor_summary(
    competitors_selected: int,
    successfully_analyzed: int,
    processing_failures: int,
    missing_topics: int,
    missing_questions: int,
    missing_entities: int,
    recommended_angles: int,
) -> None:
    table = Table(show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="bold white", justify="right")
    table.add_row("Competitors Selected", str(competitors_selected))
    table.add_row("Successfully Analyzed", str(successfully_analyzed))
    if processing_failures > 0:
        table.add_row("Processing Failures", str(processing_failures))
    table.add_row("Missing Topics", str(missing_topics))
    table.add_row("Missing Questions", str(missing_questions))
    table.add_row("Missing Entities", str(missing_entities))
    table.add_row("Recommended Angles", str(recommended_angles))
    console.print(table)


def display_competitor_domains(sources: list) -> None:
    """Show competitor domains with per-domain success/failure indicators."""
    if not sources:
        return
    console.print("[cyan]Competitors:[/cyan]")
    for idx, source in enumerate(sources, start=1):
        indicator = "[green]+[/green]" if source.fetched_successfully else "[red]x[/red]"
        reason = f" ({source.fetch_failure_reason})" if source.fetch_failure_reason else ""
        console.print(f"  {idx}. {indicator} {source.domain}{reason}")


def _format_research_status(raw: str) -> str:
    """Convert ClaimStatus enum value to friendly user-facing text.

    Handles both raw enum string like 'Claimstatus.Uncertain' and plain
    values like 'uncertain'.
    """
    # Strip any enum class prefix (e.g. "Claimstatus.Uncertain" → "uncertain")
    if "." in raw:
        raw = raw.rsplit(".", 1)[-1]

    friendly = {
        "verified": "Verified",
        "partially_supported": "Partially Supported",
        "unsupported": "Unsupported",
        "conflicting": "Conflicting",
        "uncertain": "Uncertain",
    }
    return friendly.get(raw.lower(), raw)


def display_summary_table(
    topic: str,
    research_status: str,
    pipeline_status_label: str,
    power_win_facts_count: int,
    external_facts_count: int,
    gaps_count: int,
    unsupported_count: int,
    recommended_title: str,
    primary_keyword: str,
    article_length: int,
    competitors_selected: int = 0,
    competitors_analyzed: int = 0,
    competitors_failed: int = 0,
) -> None:
    table = Table(title="Pipeline Summary", show_header=True, header_style="bold blue")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="bold white")

    table.add_row("Topic / Requested Title", topic)

    status_style = (
        "[green]" if pipeline_status_label == "COMPLETED" else
        "[yellow]" if "WARNINGS" in pipeline_status_label else
        "[red]"
    )
    table.add_row("Pipeline Status", f"{status_style}{pipeline_status_label}[/]")

    # Friendly research status — no technical enum names
    friendly_research = _format_research_status(research_status)
    if research_status.lower() in ("verified", "partially_supported"):
        table.add_row("Research", f"[green]{friendly_research}[/green]")
    else:
        table.add_row("Research", f"[yellow]{friendly_research}[/yellow]")

    table.add_row("Power.win Facts", str(power_win_facts_count))
    table.add_row("External Facts", str(external_facts_count))
    table.add_row("Research Gaps", str(gaps_count))
    table.add_row("Unsupported Claims", str(unsupported_count))
    if competitors_selected > 0:
        table.add_row("Competitors Selected", str(competitors_selected))
        table.add_row("Successfully Analyzed", str(competitors_analyzed))
        if competitors_failed > 0:
            table.add_row("Competitor Failures", str(competitors_failed))
    table.add_row("SEO Recommended Title", recommended_title)
    table.add_row("Primary Keyword", primary_keyword)
    table.add_row("Article Word Count", f"~{article_length} words")

    console.print(table)
