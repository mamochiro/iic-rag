import typer
import psycopg
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.config import settings
from src.gitlab_source import list_projects
from src.ingest import ingest_space, ingest_jira_project, ingest_gitlab
from src.query import answer_question
from src.store import set_curated

app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def ingest(
    space: str = typer.Option(..., help="Confluence space key, e.g. IIC"),
    limit: int = typer.Option(None, help="Max pages to fetch (for testing)"),
    incremental: bool = typer.Option(False, "--incremental", help="Only fetch pages changed since last sync"),
):
    """Ingest a Confluence space into the vector store."""
    result = ingest_space(space, limit=limit, incremental=incremental)
    console.print(f"Done: {result}")


@app.command()
def ingest_jira(
    project: str = typer.Option(..., help="Jira project key, e.g. IIC"),
    limit: int = typer.Option(None, help="Max issues to fetch (for testing)"),
    incremental: bool = typer.Option(False, "--incremental", help="Only fetch issues updated since last sync"),
):
    """Ingest Jira issues (In Progress + Done) into the vector store."""
    result = ingest_jira_project(project, limit=limit, incremental=incremental)
    console.print(f"Done: {result}")


@app.command()
def ingest_gl(
    project: str = typer.Option(..., help="GitLab project ID or namespace/name, e.g. 123 or mygroup/myrepo"),
    limit: int = typer.Option(None, help="Max pages to fetch (for testing)"),
    incremental: bool = typer.Option(False, "--incremental", help="Only fetch changes since last sync"),
):
    """Ingest GitLab wiki pages and .md files into the vector store."""
    result = ingest_gitlab(project, limit=limit, incremental=incremental)
    console.print(f"Done: {result}")


@app.command()
def gl_list(
    search: str = typer.Option(None, help="Filter projects by name"),
):
    """List accessible GitLab projects and their IDs."""
    projects = list_projects(search=search)
    if not projects:
        console.print("No projects found.")
        return
    table = Table(title="GitLab Projects")
    table.add_column("ID", justify="right")
    table.add_column("Name")
    table.add_column("Path")
    for p in projects:
        table.add_row(str(p["id"]), p["name"], p["path"])
    console.print(table)


@app.command()
def sync(
    space: str = typer.Option(None, help="Confluence space key to sync"),
    project: str = typer.Option(None, help="Jira project key to sync"),
    gl: str = typer.Option(None, help="GitLab project ID or path to sync"),
):
    """Incremental sync — only re-ingest content changed since last run."""
    if not space and not project and not gl:
        console.print("[red]Provide --space, --project, and/or --gl.[/red]")
        raise typer.Exit(1)
    if space:
        result = ingest_space(space, incremental=True)
        console.print(f"Confluence [{space}]: {result}")
    if project:
        result = ingest_jira_project(project, incremental=True)
        console.print(f"Jira [{project}]: {result}")
    if gl:
        result = ingest_gitlab(gl, incremental=True)
        console.print(f"GitLab [{gl}]: {result}")


@app.command()
def status():
    """Show last sync time for all indexed sources."""
    with psycopg.connect(settings.database_url) as conn:
        cur = conn.cursor()
        cur.execute("SELECT source_type, source_key, last_synced_at, pages_fetched, chunks_upserted FROM sync_log ORDER BY last_synced_at DESC;")
        rows = cur.fetchall()

    if not rows:
        console.print("No syncs recorded yet.")
        return

    table = Table(title="Sync Status")
    table.add_column("Source")
    table.add_column("Key")
    table.add_column("Last Synced")
    table.add_column("Pages", justify="right")
    table.add_column("Chunks", justify="right")
    for r in rows:
        table.add_row(r[0], r[1], r[2].strftime("%Y-%m-%d %H:%M"), str(r[3]), str(r[4]))
    console.print(table)


@app.command()
def curate(
    url: str = typer.Argument(..., help="Source URL of the page/issue to mark as curated"),
):
    """Mark a page as curated — its chunks get a retrieval score boost."""
    n = set_curated(url, True)
    console.print(f"Marked {n} chunk(s) as curated for {url}")


@app.command()
def uncurate(
    url: str = typer.Argument(..., help="Source URL of the page/issue to unmark"),
):
    """Remove curated flag from a page."""
    n = set_curated(url, False)
    console.print(f"Removed curated flag from {n} chunk(s) for {url}")


@app.command()
def logs(
    limit: int = typer.Option(10, help="Number of recent queries to show"),
):
    """Show recent queries with latency and rewritten form."""
    with psycopg.connect(settings.database_url) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT created_at, latency_ms, question, rewritten_question
            FROM query_log ORDER BY created_at DESC LIMIT %s;
        """, (limit,))
        rows = cur.fetchall()

    if not rows:
        console.print("No queries logged yet.")
        return

    table = Table(title=f"Last {limit} Queries")
    table.add_column("Time")
    table.add_column("ms", justify="right")
    table.add_column("Question")
    table.add_column("Rewritten")
    for r in rows:
        table.add_row(
            r[0].strftime("%m-%d %H:%M"),
            str(r[1]),
            r[2][:60] + ("…" if len(r[2]) > 60 else ""),
            (r[3] or "")[:60] + ("…" if r[3] and len(r[3]) > 60 else ""),
        )
    console.print(table)


@app.command()
def query(
    question: str = typer.Argument(..., help="Your question"),
    top_k: int = typer.Option(None, help="Override top_k for retrieval"),
    show_rewritten: bool = typer.Option(False, "--show-rewritten", help="Print the rewritten query"),
):
    """Ask a question against the indexed content."""
    result = answer_question(question, top_k=top_k)
    if show_rewritten and result.get("rewritten") != question:
        console.print(f"[dim]Rewritten: {result['rewritten']}[/dim]\n")
    console.print(Panel(result["answer"], title="Answer", border_style="cyan"))
    console.print("\n[bold]Retrieved chunks:[/bold]")
    for r in result["retrieved"]:
        console.print(f"  • [{r['score']:.3f}] {r['title']} — {r['url']}")


if __name__ == "__main__":
    app()
