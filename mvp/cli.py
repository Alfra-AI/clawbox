"""AgentBox CLI - Command line interface for AgentBox API."""

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="agentbox",
    help="CLI for AgentBox - a cloud file system for agents",
    no_args_is_help=True,
)
console = Console()

# Config file location
CONFIG_DIR = Path.home() / ".agentbox"
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
        console.print("[red]No token configured. Run 'agentbox init' first.[/red]")
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
    """Initialize AgentBox and get a new token, or sign in with Google."""
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
        console.print("  [cyan]agentbox config --token YOUR_TOKEN[/cyan]")
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

        console.print("[green]AgentBox initialized successfully![/green]")
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


MULTIPART_THRESHOLD = 5 * 1024 * 1024  # 5 MB
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB per part


@app.command()
def upload(
    file_path: Path = typer.Argument(..., help="File to upload", exists=True),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Virtual path (e.g., /docs/readme.md)"),
    sync: bool = typer.Option(False, "--sync", "-s", help="Force synchronous upload"),
):
    """Upload a file. Large files (>5 MB) upload in background automatically."""
    token = require_token()
    size = file_path.stat().st_size

    # Small files or --sync: use existing synchronous upload
    if size < MULTIPART_THRESHOLD or sync:
        _upload_sync(file_path, path, token)
        return

    # Large files: try multipart background upload
    num_parts = math.ceil(size / CHUNK_SIZE)
    response = api_request(
        "POST", "/files/upload-multipart", token=token,
        json={
            "filename": file_path.name,
            "size_bytes": size,
            "num_parts": num_parts,
            "path": path,
        },
    )

    if response.status_code == 400:
        # Server doesn't support multipart (local storage) — fall back to sync
        _upload_sync(file_path, path, token)
        return

    if response.status_code != 200:
        console.print(f"[red]Upload failed: {response.text}[/red]")
        raise typer.Exit(1)

    data = response.json()
    file_id = data["file_id"]

    # Save transfer state
    from mvp.transfers import create_transfer, _log_path
    create_transfer(
        file_id=file_id,
        direction="upload",
        file_path=str(file_path.resolve()),
        filename=file_path.name,
        size_bytes=size,
        upload_id=data["upload_id"],
        part_urls=data["part_urls"],
        virtual_path=path,
        total_parts=num_parts,
    )

    # Fork background worker
    log_file = _log_path(file_id)
    log_fd = open(log_file, "w")
    subprocess.Popen(
        [sys.executable, "-m", "mvp.cli", "_worker", "upload", file_id],
        start_new_session=True,
        stdout=log_fd,
        stderr=log_fd,
        stdin=subprocess.DEVNULL,
    )

    console.print(f"[green]Uploading in background...[/green]")
    console.print(f"File ID: [cyan]{file_id}[/cyan]")
    console.print(f"Check progress: [dim]agentbox status {file_id}[/dim]")


def _upload_sync(file_path: Path, path: Optional[str], token: str):
    """Synchronous upload for small files or local storage."""
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
            console.print("[yellow]Indexing in background[/yellow]")
    else:
        console.print(f"[red]Upload failed: {response.text}[/red]")
        raise typer.Exit(1)


@app.command()
def download(
    file_id: str = typer.Argument(..., help="File ID to download"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path"),
    sync: bool = typer.Option(False, "--sync", "-s", help="Force synchronous download"),
):
    """Download a file. Large files download in background via presigned URL."""
    token = require_token()

    # Get file info first to check size and get filename
    info_response = api_request("GET", f"/files/{file_id}/info", token=token)
    if info_response.status_code == 404:
        console.print("[red]File not found[/red]")
        raise typer.Exit(1)
    elif info_response.status_code != 200:
        console.print(f"[red]Failed: {info_response.text}[/red]")
        raise typer.Exit(1)

    file_info = info_response.json()
    filename = file_info["filename"]
    size = file_info["size_bytes"]
    output_path = output or Path(filename)

    # Small files or --sync: download directly
    if size < MULTIPART_THRESHOLD or sync:
        response = api_request("GET", f"/files/{file_id}", token=token)
        if response.status_code == 200:
            output_path.write_bytes(response.content)
            console.print(f"[green]Downloaded to: {output_path}[/green]")
        else:
            console.print(f"[red]Download failed: {response.text}[/red]")
            raise typer.Exit(1)
        return

    # Large files: try presigned URL + background download
    direct_response = api_request("GET", f"/files/{file_id}?direct=true", token=token)
    if direct_response.status_code == 200:
        data = direct_response.json()
        if "download_url" in data:
            from mvp.transfers import create_transfer, _log_path
            create_transfer(
                file_id=file_id,
                direction="download",
                file_path=str(output_path.resolve()),
                filename=filename,
                size_bytes=size,
            )

            log_file = _log_path(file_id)
            log_fd = open(log_file, "w")
            subprocess.Popen(
                [sys.executable, "-m", "mvp.cli", "_worker", "download", file_id],
                start_new_session=True,
                stdout=log_fd,
                stderr=log_fd,
                stdin=subprocess.DEVNULL,
            )

            console.print(f"[green]Downloading in background...[/green]")
            console.print(f"Output: [cyan]{output_path}[/cyan]")
            console.print(f"Check progress: [dim]agentbox status {file_id}[/dim]")
            return

    # Fallback to sync download
    response = api_request("GET", f"/files/{file_id}", token=token)
    if response.status_code == 200:
        output_path.write_bytes(response.content)
        console.print(f"[green]Downloaded to: {output_path}[/green]")
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
        table.add_column("Path")
        table.add_column("Type")
        table.add_column("Size", justify="right")
        table.add_column("Indexed")
        table.add_column("Created")

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
def status(
    file_id: Optional[str] = typer.Argument(None, help="File ID to check transfer status"),
    transfers: bool = typer.Option(False, "--transfers", "-t", help="List all active transfers"),
):
    """Check server status, or check transfer progress for a file."""
    from mvp.transfers import get_transfer, list_transfers, is_worker_alive

    # Show transfer status for a specific file
    if file_id:
        state = get_transfer(file_id)
        if state:
            alive = is_worker_alive(state.get("worker_pid"))
            status_str = state["status"]
            if status_str in ("uploading", "downloading") and not alive:
                status_str = "interrupted (worker died)"

            console.print(f"File ID: [cyan]{state['file_id']}[/cyan]")
            console.print(f"Direction: {state['direction']}")
            console.print(f"Status: [bold]{status_str}[/bold]")
            if state.get("total_parts"):
                pct = (state.get("completed_parts", 0) / state["total_parts"]) * 100
                console.print(f"Progress: {state.get('completed_parts', 0)}/{state['total_parts']} parts ({pct:.0f}%)")
            if state.get("bytes_transferred"):
                console.print(f"Transferred: {formatsize(state['bytes_transferred'])} / {formatsize(state['size_bytes'])}")
            if state.get("error"):
                console.print(f"Error: [red]{state['error']}[/red]")
            if state.get("file_path"):
                console.print(f"Local path: {state['file_path']}")
        else:
            # Check server for file info
            token = get_token()
            if token:
                resp = api_request("GET", f"/files/{file_id}/info", token=token)
                if resp.status_code == 200:
                    data = resp.json()
                    console.print(f"File: [cyan]{data['folder']}{data['filename']}[/cyan]")
                    console.print(f"Status: {data['embedding_status']}")
                    console.print(f"Size: {formatsize(data['size_bytes'])}")
                else:
                    console.print("[red]File not found[/red]")
            else:
                console.print("[red]No transfer found and no token configured[/red]")
        return

    # List all transfers
    if transfers:
        active = list_transfers()
        if not active:
            console.print("No active transfers.")
            return
        table = Table(title="Transfers")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Direction")
        table.add_column("File")
        table.add_column("Status")
        table.add_column("Progress")

        for t in active[:20]:
            alive = is_worker_alive(t.get("worker_pid"))
            s = t["status"]
            if s in ("uploading", "downloading") and not alive:
                s = "interrupted"
            pct = ""
            if t.get("total_parts"):
                pct = f"{t.get('completed_parts', 0)}/{t['total_parts']}"
            elif t.get("bytes_transferred"):
                pct = formatsize(t["bytes_transferred"])
            table.add_row(t["file_id"][:12], t["direction"], t["filename"], s, pct)
        console.print(table)
        return

    # Default: server health + token check
    try:
        response = api_request("GET", "/health")
        if response.status_code == 200:
            data = response.json()
            console.print(f"[green]Server: {get_api_url()} (v{data['version']})[/green]")
        else:
            console.print(f"[red]Server unhealthy: {response.status_code}[/red]")
    except typer.Exit:
        return

    token = get_token()
    if token:
        response = api_request("GET", "/files", token=token)
        if response.status_code == 200:
            console.print(f"[green]Token: valid[/green]")
        else:
            console.print(f"[yellow]Token: invalid or expired[/yellow]")
    else:
        console.print("[yellow]Token: not configured[/yellow]")


def formatsize(b):
    if b < 1024: return f"{b} B"
    if b < 1024**2: return f"{b/1024:.1f} KB"
    if b < 1024**3: return f"{b/1024**2:.1f} MB"
    return f"{b/1024**3:.1f} GB"


# --- Background worker (hidden command, called by subprocess) ---

@app.command(hidden=True)
def _worker(
    action: str = typer.Argument(..., help="upload or download"),
    transfer_id: str = typer.Argument(..., help="File/transfer ID"),
):
    """Background worker for chunked upload/download. Not for direct use."""
    from mvp.transfers import get_transfer, update_transfer

    state = get_transfer(transfer_id)
    if state is None:
        print(f"Transfer {transfer_id} not found")
        raise typer.Exit(1)

    update_transfer(transfer_id, worker_pid=os.getpid())

    if action == "upload":
        _worker_upload(transfer_id, state)
    elif action == "download":
        _worker_download(transfer_id, state)
    else:
        print(f"Unknown action: {action}")
        raise typer.Exit(1)


def _worker_upload(transfer_id: str, state: dict):
    """Background upload worker — reads file in chunks, PUTs to presigned URLs."""
    from mvp.transfers import update_transfer

    token = require_token()
    file_path = state["file_path"]
    part_urls = state.get("part_urls", [])

    completed_etags = []
    try:
        with open(file_path, "rb") as f:
            for part in part_urls:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                resp = httpx.put(
                    part["upload_url"],
                    content=chunk,
                    timeout=600,
                )
                resp.raise_for_status()
                etag = resp.headers.get("etag", "")
                completed_etags.append({
                    "part_number": part["part_number"],
                    "etag": etag,
                })
                update_transfer(
                    transfer_id,
                    bytes_transferred=f.tell(),
                    completed_parts=len(completed_etags),
                    completed_etags=completed_etags,
                )
                print(f"Part {part['part_number']}/{len(part_urls)} uploaded")

        # Complete multipart upload on server
        update_transfer(transfer_id, status="confirming")
        response = api_request(
            "POST", "/files/complete-multipart", token=token,
            json={
                "file_id": transfer_id,
                "upload_id": state["upload_id"],
                "parts": completed_etags,
            },
        )

        if response.status_code == 200:
            data = response.json()
            update_transfer(transfer_id, status="ready", embedding_status=data.get("embedding_status"))
            print(f"Upload complete: {transfer_id}")
        else:
            update_transfer(transfer_id, status="failed", error=f"Complete failed: {response.status_code}")
            print(f"Complete failed: {response.text}")

    except Exception as e:
        update_transfer(transfer_id, status="failed", error=str(e))
        print(f"Upload failed: {e}")


def _worker_download(transfer_id: str, state: dict):
    """Background download worker — streams file from presigned URL."""
    from mvp.transfers import update_transfer

    token = require_token()
    output_path = state["file_path"]

    try:
        # Get presigned download URL
        response = api_request("GET", f"/files/{transfer_id}?direct=true", token=token)
        if response.status_code != 200:
            # Fall back to regular download
            response = api_request("GET", f"/files/{transfer_id}", token=token)
            if response.status_code == 200:
                Path(output_path).write_bytes(response.content)
                update_transfer(transfer_id, status="downloaded", bytes_transferred=len(response.content))
                print(f"Download complete: {output_path}")
            else:
                update_transfer(transfer_id, status="failed", error=f"Download failed: {response.status_code}")
            return

        data = response.json()
        download_url = data.get("download_url")
        if not download_url:
            update_transfer(transfer_id, status="failed", error="No download URL returned")
            return

        # Stream download in chunks
        with httpx.stream("GET", download_url, timeout=600) as stream:
            stream.raise_for_status()
            bytes_downloaded = 0
            with open(output_path, "wb") as f:
                for chunk in stream.iter_bytes(chunk_size=CHUNK_SIZE):
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
                    update_transfer(transfer_id, bytes_transferred=bytes_downloaded)

        update_transfer(transfer_id, status="downloaded")
        print(f"Download complete: {output_path}")

    except Exception as e:
        update_transfer(transfer_id, status="failed", error=str(e))
        print(f"Download failed: {e}")


if __name__ == "__main__":
    app()
