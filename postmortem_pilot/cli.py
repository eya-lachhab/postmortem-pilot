"""CLI entrypoint for postmortem-pilot."""

import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from postmortem_pilot.git_diff import get_git_diff
from postmortem_pilot.log_scanner import scan_logs
from postmortem_pilot.report import render_report
from postmortem_pilot.summarizer import summarize

console = Console()

BANNER = """
██████╗  ██████╗ ███████╗████████╗███╗   ███╗ ██████╗ ██████╗ ████████╗███████╗███╗   ███╗
██╔══██╗██╔═══██╗██╔════╝╚══██╔══╝████╗ ████║██╔═══██╗██╔══██╗╚══██╔══╝██╔════╝████╗ ████║
██████╔╝██║   ██║███████╗   ██║   ██╔████╔██║██║   ██║██████╔╝   ██║   █████╗  ██╔████╔██║
██╔═══╝ ██║   ██║╚════██║   ██║   ██║╚██╔╝██║██║   ██║██╔══██╗   ██║   ██╔══╝  ██║╚██╔╝██║
██║     ╚██████╔╝███████║   ██║   ██║ ╚═╝ ██║╚██████╔╝██║  ██║   ██║   ███████╗██║ ╚═╝ ██║
╚═╝      ╚═════╝ ╚══════╝   ╚═╝   ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝     ╚═╝
                                      ✈  PILOT
"""


@click.group()
@click.version_option()
def main() -> None:
    """postmortem-pilot — Auto-generate deploy postmortems powered by AI."""
    pass


@main.command()
@click.option(
    "--log-file",
    "-l",
    default=None,
    help="Path to log file to scan. Uses example_logs/sample.log if not provided.",
    type=click.Path(exists=False),
)
@click.option(
    "--before",
    "-b",
    default="HEAD~1",
    show_default=True,
    help="Git ref before the deploy (e.g. HEAD~1 or a commit SHA).",
)
@click.option(
    "--after",
    "-a",
    default="HEAD",
    show_default=True,
    help="Git ref after the deploy (e.g. HEAD or a commit SHA).",
)
@click.option(
    "--output",
    "-o",
    default="postmortem.md",
    show_default=True,
    help="Output path for the generated postmortem markdown file.",
)
@click.option(
    "--repo",
    "-r",
    default=".",
    show_default=True,
    help="Path to the git repository.",
    type=click.Path(exists=True),
)
@click.option(
    "--no-llm",
    is_flag=True,
    default=False,
    help="Skip LLM summarization and use template mode only.",
)
def run(
    log_file: str | None,
    before: str,
    after: str,
    output: str,
    repo: str,
    no_llm: bool,
) -> None:
    """Run postmortem generation for a deploy."""
    console.print(Text(BANNER, style="bold cyan"))
    console.print(
        Panel(
            f"[bold]Repo:[/bold] {repo}\n"
            f"[bold]Diff:[/bold] {before} → {after}\n"
            f"[bold]Logs:[/bold] {log_file or 'example_logs/sample.log'}\n"
            f"[bold]Output:[/bold] {output}",
            title="[bold green]🚀 Starting Postmortem Analysis[/bold green]",
            border_style="green",
        )
    )

    # --- Step 1: Git diff ---
    console.print("\n[bold yellow]📂 Step 1/3 — Analysing git diff...[/bold yellow]")
    diff_data = get_git_diff(repo_path=repo, before=before, after=after)
    if diff_data["error"]:
        console.print(f"[yellow]⚠ Git diff warning: {diff_data['error']}[/yellow]")
    else:
        console.print(
            f"  [green]✓[/green] Found [bold]{diff_data['files_changed']}[/bold] changed files, "
            f"[bold]+{diff_data['insertions']}[/bold] insertions, "
            f"[bold]-{diff_data['deletions']}[/bold] deletions"
        )

    # --- Step 2: Log scanning ---
    console.print("\n[bold yellow]🔍 Step 2/3 — Scanning logs...[/bold yellow]")
    resolved_log = log_file or str(Path(repo) / "example_logs" / "sample.log")
    log_data = scan_logs(resolved_log)
    if log_data["error"]:
        console.print(f"[yellow]⚠ Log scan warning: {log_data['error']}[/yellow]")
    else:
        console.print(
            f"  [green]✓[/green] Scanned [bold]{log_data['total_lines']}[/bold] lines — "
            f"[red]{log_data['error_count']} ERRORs[/red], "
            f"[yellow]{log_data['warning_count']} WARNs[/yellow], "
            f"[cyan]{log_data['info_count']} INFOs[/cyan]"
        )

    # --- Step 3: LLM summarization ---
    console.print("\n[bold yellow]🤖 Step 3/3 — Generating AI summary...[/bold yellow]")
    groq_key = os.environ.get("GROQ_API_KEY")

    if no_llm or not groq_key:
        if not groq_key:
            console.print(
                "  [yellow]ℹ No GROQ_API_KEY found — using template mode.[/yellow]"
            )
        else:
            console.print("  [yellow]ℹ --no-llm flag set — using template mode.[/yellow]")
        ai_summary = None
    else:
        console.print("  [cyan]↗ Calling Groq (Llama 3)...[/cyan]")
        ai_summary = summarize(diff_data=diff_data, log_data=log_data, api_key=groq_key)
        if ai_summary:
            console.print("  [green]✓ AI summary generated.[/green]")
        else:
            console.print("  [yellow]⚠ AI summary failed — falling back to template.[/yellow]")

    # --- Render report ---
    report_path = render_report(
        output_path=output,
        diff_data=diff_data,
        log_data=log_data,
        ai_summary=ai_summary,
        before=before,
        after=after,
    )

    console.print(
        Panel(
            f"[bold green]✅ Postmortem written to:[/bold green] [bold]{report_path}[/bold]\n\n"
            "Review it, commit it, and never lose track of a bad deploy again.",
            title="[bold green]🎉 Done![/bold green]",
            border_style="green",
        )
    )


@main.command()
def doctor() -> None:
    """Check your environment and configuration."""
    console.print("\n[bold cyan]🩺 postmortem-pilot doctor[/bold cyan]\n")

    checks = [
        ("GROQ_API_KEY", bool(os.environ.get("GROQ_API_KEY")), "Required for AI summaries (free at console.groq.com)"),
        ("git", _check_git(), "Git must be installed"),
        ("Python >= 3.9", sys.version_info >= (3, 9), f"Current: {sys.version}"),
    ]

    all_ok = True
    for name, ok, note in checks:
        icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
        console.print(f"  {icon} [bold]{name}[/bold] — {note}")
        if not ok:
            all_ok = False

    if all_ok:
        console.print("\n[bold green]All checks passed! You're ready to fly. ✈[/bold green]")
    else:
        console.print("\n[yellow]Some checks failed — see notes above.[/yellow]")


def _check_git() -> bool:
    import shutil
    return shutil.which("git") is not None


if __name__ == "__main__":
    main()
