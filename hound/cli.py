import json
import asyncio
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.text import Text
from rich import box
from . import __version__
from .engine import hunt
from .modules import ALL_MODULES, SITE_NAMES

console = Console()

BANNER = """
[bold cyan]  ╔─ HOUND ─────────────────────────────────────────────╗[/bold cyan]
[bold cyan]  │[/bold cyan]  [bold white]email osint[/bold white] [dim]· account discovery · 42+ platforms[/dim]  [bold cyan]│[/bold cyan]
[bold cyan]  ╚─────────────────────────────────────────────────────╝[/bold cyan]
"""


@click.command()
@click.argument("email")
@click.option("--only", "-o", multiple=True, help="Check specific sites only (repeatable)")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON")
@click.option("--found-only", "-f", is_flag=True, help="Show only found accounts")
@click.option("--timeout", "-t", default=12, show_default=True, help="Timeout per site (seconds)")
@click.option("--concurrency", "-c", default=10, show_default=True, help="Concurrent checks")
@click.option("--no-banner", is_flag=True, hidden=True)
def main(email, only, as_json, found_only, timeout, concurrency, no_banner):
    """Hunt for accounts registered to EMAIL across 42 platforms."""

    if not as_json and not no_banner:
        console.print(BANNER)

    # Resolve modules
    if only:
        modules = []
        for name in only:
            key = name.lower().strip()
            if key in SITE_NAMES:
                modules.append(SITE_NAMES[key])
            else:
                console.print(f"[yellow]Unknown site: {name}[/yellow]")
        if not modules:
            console.print("[red]No valid sites selected.[/red]")
            raise SystemExit(1)
    else:
        modules = ALL_MODULES

    if not as_json:
        console.print(f"[dim]Target:[/dim] [bold cyan]{email}[/bold cyan]")
        console.print(f"[dim]Checking {len(modules)} platforms...[/dim]\n")

    results = []

    if as_json:
        results = asyncio.run(hunt(email, modules=modules, concurrency=concurrency, timeout=timeout))
    else:
        with Progress(
            SpinnerColumn(style="green"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30, style="green", complete_style="bold green"),
            TaskProgressColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Scanning...", total=len(modules))
            completed = []

            async def run_with_progress():
                sem = asyncio.Semaphore(concurrency)
                import httpx as _httpx
                limits = _httpx.Limits(max_connections=concurrency, max_keepalive_connections=5)
                async with _httpx.AsyncClient(timeout=timeout, follow_redirects=True, limits=limits) as client:
                    async def run_one(mod):
                        async with sem:
                            r = await mod(client, email)
                            completed.append(r)
                            progress.advance(task)
                            return r
                    return await asyncio.gather(*[run_one(m) for m in modules])

            results = asyncio.run(run_with_progress())

    # Output
    if as_json:
        click.echo(json.dumps(results, indent=2))
        return

    found = [r for r in results if r["found"] is True]
    unknown = [r for r in results if r["found"] is None]
    not_found = [r for r in results if r["found"] is False]

    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim")
    table.add_column("Platform", style="bold", min_width=18)
    table.add_column("Status", min_width=10)
    table.add_column("URL", style="dim")

    display = found if found_only else (found + (not_found if not found_only else []))
    if not found_only:
        display = found + unknown + not_found

    for r in display:
        if r["found"] is True:
            status = Text("● FOUND", style="bold green")
        elif r["found"] is False:
            status = Text("○ not found", style="dim")
        else:
            err = f"? {r.get('error','unknown')}"[:30]
            status = Text(err, style="dim yellow")
        table.add_row(r["name"], status, r["url"])

    if table.row_count:
        console.print(table)

    # Summary
    console.print(
        f"\n[bold green]{len(found)} found[/bold green]  "
        f"[dim]{len(not_found)} not found  {len(unknown)} unknown[/dim]\n"
    )
