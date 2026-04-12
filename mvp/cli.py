"""ClawBox CLI - Command line interface for ClawBox API."""

import json
import sys
from pathlib import Path
from typing import List, Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="clawbox",
    help="CLI for ClawBox - a cloud file system for agents",
    no_args_is_help=True,
)
console = Console()

# Config file location
CONFIG_DIR = Path.home() / ".clawbox"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_API_URL = "https://clawbox.ink"


def get_config() -> dict:
    """Load configuration from file."""
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(config: dict) -> None:
    """Save configuration to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get_api_url() -> str:
    """Get API URL from config or default."""
    config = get_config()
    return config.get("api_url", DEFAULT_API_URL)


def get_token() -> Optional[str]:
    """Get token from config."""
    config = get_config()
    return config.get("token")


def require_token() -> str:
    """Get token or exit with error."""
    token = get_token()
    if not token:
        console.print("[red]No token configured. Run 'clawbox init' first.[/red]")
        raise typer.Exit(1)
    return token


def api_request(
    method: str,
    endpoint: str,
    token: Optional[str] = None,
    **kwargs,
) -> httpx.Response:
    """Make an API request."""
    url = f"{get_api_url()}{endpoint}"
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = httpx.request(method, url, headers=headers, timeout=30, **kwargs)
        return response
    except httpx.ConnectError:
        console.print(f"[red]Cannot connect to API at {get_api_url()}[/red]")
        console.print("For local dev: python -m mvp.main")
        raise typer.Exit(1)


@app.command()
def init(
    api_url: Optional[str] = typer.Option(None, "--api-url", "-u", help="API URL"),
    login: bool = typer.Option(False, "--login", "-l", help="Sign in with Google (opens browser)"),
):
    """Initialize ClawBox and get a new token, or sign in with Google."""
    config = get_config()

    if api_url:
        config["api_url"] = api_url
        save_config(config)

    if login:
        import webbrowser
        base_url = get_api_url()
        login_url = f"{base_url}/auth/google"
        console.print(f"Opening browser for Google sign-in...")
        console.print(f"URL: [cyan]{login_url}[/cyan]")
        webbrowser.open(login_url)
        console.print("\nAfter signing in, copy your token from the web UI and run:")
        console.print("  [cyan]clawbox config --token YOUR_TOKEN[/cyan]")
        return

    # Get a new anonymous token
    response = api_request("POST", "/get_token")

    if response.status_code == 200:
        data = response.json()
        config["token"] = data["token"]
        save_config(config)

        storage_limit = data['storage_limit_bytes']
        if storage_limit >= 1024 * 1024 * 1024:
            limit_str = f"{storage_limit / (1024**3):.0f} GB"
        else:
            limit_str = f"{storage_limit / (1024**2):.0f} MB"

        console.print("[green]ClawBox initialized successfully![/green]")
        console.print(f"Token: [cyan]{data['token']}[/cyan]")
        console.print(f"Storage limit: {limit_str}")
        console.print(f"Config saved to: {CONFIG_FILE}")
    else:
        console.print(f"[red]Failed to get token: {response.text}[/red]")
        raise typer.Exit(1)


@app.command()
def config(
    show: bool = typer.Option(False, "--show", "-s", help="Show current config"),
    api_url: Optional[str] = typer.Option(None, "--api-url", "-u", help="Set API URL"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Set token"),
):
    """View or update configuration."""
    cfg = get_config()

    if api_url:
        cfg["api_url"] = api_url
        save_config(cfg)
        console.print(f"API URL set to: {api_url}")

    if token:
        cfg["token"] = token
        save_config(cfg)
        console.print("Token updated")

    if show or (not api_url and not token):
        console.print(f"Config file: {CONFIG_FILE}")
        console.print(f"API URL: {cfg.get('api_url', DEFAULT_API_URL)}")
        console.print(f"Token: {cfg.get('token', '[not set]')}")


@app.command()
def upload(
    file_path: Path = typer.Argument(..., help="File to upload", exists=True),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Virtual path (e.g., /docs/readme.md)"),
):
    """Upload a file. Use --path to organize into folders."""
    token = require_token()

    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f)}
        data = {"path": path} if path else {}
        response = api_request("POST", "/files/upload", token=token, files=files, data=data)

    if response.status_code == 201:
        data = response.json()
        console.print("[green]File uploaded successfully![/green]")
        console.print(f"ID: [cyan]{data['id']}[/cyan]")
        console.print(f"Path: {data.get('folder', '/')}{data['filename']}")
        console.print(f"Size: {data['size_bytes']} bytes")
        embedding_status = data.get("embedding_status", "not_applicable")
        if embedding_status == "completed":
            console.print("[green]Indexed for search[/green]")
        elif embedding_status == "pending":
            console.print("[yellow]Indexing pending[/yellow]")
        elif embedding_status == "failed":
            console.print(
                "[yellow]Embedding failed — file stored but not searchable. "
                "Use 'clawbox embed --failed' to retry.[/yellow]"
            )
    else:
        console.print(f"[red]Upload failed: {response.text}[/red]")
        raise typer.Exit(1)


@app.command()
def download(
    file_id: str = typer.Argument(..., help="File ID to download"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path"),
):
    """Download a file."""
    token = require_token()

    response = api_request("GET", f"/files/{file_id}", token=token)

    if response.status_code == 200:
        # Get filename from Content-Disposition header
        content_disp = response.headers.get("content-disposition", "")
        filename = file_id
        if "filename=" in content_disp:
            filename = content_disp.split("filename=")[1].strip('"')

        output_path = output or Path(filename)
        output_path.write_bytes(response.content)
        console.print(f"[green]Downloaded to: {output_path}[/green]")
    elif response.status_code == 404:
        console.print("[red]File not found[/red]")
        raise typer.Exit(1)
    else:
        console.print(f"[red]Download failed: {response.text}[/red]")
        raise typer.Exit(1)


@app.command(name="list")
def list_files(
    folder: Optional[str] = typer.Option(None, "--folder", "-f", help="Filter by folder (e.g., /docs/)"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subfolders"),
):
    """List all files, optionally filtered by folder."""
    token = require_token()

    params = {}
    if folder:
        params["folder"] = folder
    if recursive:
        params["recursive"] = "true"

    response = api_request("GET", "/files", token=token, params=params)

    if response.status_code == 200:
        data = response.json()

        if not data["files"]:
            console.print("No files uploaded yet.")
            return

        table = Table(title=f"Files ({data['total']} total)")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Path", overflow="fold", max_width=50)
        table.add_column("Type", no_wrap=True)
        table.add_column("Size", justify="right")
        table.add_column("Indexed")
        table.add_column("Created", overflow="fold")

        for f in data["files"]:
            size = f"{f['size_bytes']:,} B"
            if f["size_bytes"] > 1024:
                size = f"{f['size_bytes'] / 1024:.1f} KB"
            if f["size_bytes"] > 1024 * 1024:
                size = f"{f['size_bytes'] / 1024 / 1024:.1f} MB"

            created = f["created_at"][:19].replace("T", " ")
            file_path = f.get("folder", "/") + f["filename"]

            embedding_status = f.get("embedding_status", "not_applicable")
            if embedding_status == "completed":
                indexed = "[green]Yes[/green]"
            elif embedding_status == "pending":
                indexed = "[yellow]Pending[/yellow]"
            elif embedding_status == "failed":
                indexed = "[red]Failed[/red]"
            else:
                indexed = "[dim]N/A[/dim]"

            table.add_row(
                f["id"],
                file_path,
                f["content_type"],
                size,
                indexed,
                created,
            )

        console.print(table)
    else:
        console.print(f"[red]Failed to list files: {response.text}[/red]")
        raise typer.Exit(1)


@app.command()
def delete(
    file_id: str = typer.Argument(..., help="File ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a file."""
    token = require_token()

    if not force:
        confirm = typer.confirm(f"Delete file {file_id}?")
        if not confirm:
            raise typer.Abort()

    response = api_request("DELETE", f"/files/{file_id}", token=token)

    if response.status_code == 204:
        console.print("[green]File deleted[/green]")
    elif response.status_code == 404:
        console.print("[red]File not found[/red]")
        raise typer.Exit(1)
    else:
        console.print(f"[red]Delete failed: {response.text}[/red]")
        raise typer.Exit(1)


@app.command()
def embed(
    file_ids: Optional[List[str]] = typer.Argument(None, help="File IDs to embed"),
    failed: bool = typer.Option(False, "--failed", help="Retry all files that failed embedding"),
):
    """Embed specific files or retry all failed embeddings."""
    token = require_token()

    requested_file_ids = file_ids or []
    if not requested_file_ids and not failed:
        console.print("[red]Specify file IDs or use --failed[/red]")
        raise typer.Exit(1)
    if requested_file_ids and failed:
        console.print("[red]Use file IDs or --failed, not both[/red]")
        raise typer.Exit(1)

    payload = {"failed_only": True} if failed else {"file_ids": requested_file_ids}
    response = api_request("POST", "/files/embed", token=token, json=payload)

    if response.status_code == 200:
        data = response.json()
        if data["processed"] == 0:
            console.print("No files need embedding.")
            return

        console.print(
            f"Processed {data['processed']} file(s): "
            f"{data['succeeded']} succeeded, {data['failed']} failed"
        )
        for result in data["results"]:
            label = result.get("filename") or result.get("requested_id") or result.get("id", "[unknown]")
            if result["embedding_status"] == "completed":
                console.print(f"  [green]✓[/green] {label}")
            else:
                error_detail = result.get("error")
                detail = f" ({error_detail})" if error_detail else ""
                console.print(f"  [red]✗[/red] {label}{detail}")

        if data["failed"] > 0:
            raise typer.Exit(1)
    elif response.status_code == 404:
        console.print("[red]File not found[/red]")
        raise typer.Exit(1)
    elif response.status_code == 503:
        console.print("[yellow]Embeddings require OpenAI API key on the server[/yellow]")
        raise typer.Exit(1)
    else:
        console.print(f"[red]Embed failed: {response.text}[/red]")
        raise typer.Exit(1)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
):
    """Search files using semantic search."""
    token = require_token()

    response = api_request(
        "POST",
        "/search",
        token=token,
        json={"query": query, "limit": limit},
    )

    if response.status_code == 200:
        data = response.json()

        if not data["results"]:
            console.print("No matching files found.")
            return

        table = Table(title=f"Search Results ({data['total']} matches)")
        table.add_column("Score", justify="right")
        table.add_column("ID", style="cyan")
        table.add_column("Filename")
        table.add_column("Matched Text")

        for r in data["results"]:
            table.add_row(
                f"{r['relevance_score']:.3f}",
                r["file_id"],
                r["filename"],
                r["matched_chunk"][:50] + "..." if len(r["matched_chunk"]) > 50 else r["matched_chunk"],
            )

        console.print(table)
    elif response.status_code == 503:
        console.print("[yellow]Search requires OpenAI API key on the server[/yellow]")
        raise typer.Exit(1)
    else:
        console.print(f"[red]Search failed: {response.text}[/red]")
        raise typer.Exit(1)


@app.command()
def status():
    """Check API server status and token info."""
    # Check server health
    try:
        response = api_request("GET", "/health")
        if response.status_code == 200:
            data = response.json()
            console.print(f"[green]Server: {get_api_url()} (v{data['version']})[/green]")
        else:
            console.print(f"[red]Server unhealthy: {response.status_code}[/red]")
    except typer.Exit:
        return

    # Check token
    token = get_token()
    if token:
        response = api_request("GET", "/files", token=token)
        if response.status_code == 200:
            console.print(f"[green]Token: valid[/green]")
        else:
            console.print(f"[yellow]Token: invalid or expired[/yellow]")
    else:
        console.print("[yellow]Token: not configured[/yellow]")


if __name__ == "__main__":
    app()
