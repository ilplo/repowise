"""``repowise serve`` — start the API server and web UI."""

from __future__ import annotations

import os
import json
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path

import click

from repowise.app_runtime import (
    ensure_app_data_dir,
    get_server_log_path,
    get_server_state_path,
)
from repowise.cli.helpers import (
    console,
    get_db_url_for_repo,
    load_app_config,
    save_app_config,
    require_repowise_dir,
    resolve_repo_path,
)


def _setup_embedder() -> None:
    """Ensure REPOWISE_EMBEDDER is set before the server starts.

    Priority:
      1. Already set in environment → nothing to do.
      2. Saved in the central app config → restore it (and its API key).
      3. Prompt the user interactively → save choice for next time.
    """
    if os.environ.get("REPOWISE_EMBEDDER"):
        return

    # Check global config saved by a previous serve/init run.
    cfg = load_app_config()
    saved_embedder = cfg.get("embedder", "")
    if saved_embedder and saved_embedder != "mock":
        os.environ["REPOWISE_EMBEDDER"] = saved_embedder
        # Restore API key if saved alongside the config.
        if cfg.get("embedder_api_key"):
            _set_api_key_env(saved_embedder, cfg["embedder_api_key"])
        return

    # No embedder configured — server defaults to MockEmbedder with full-text search fallback.
    # Chat works via the configured LLM (xAI); semantic search degrades gracefully to FTS.


def _get_or_prompt_api_key(embedder: str) -> str:
    """Return existing API key for *embedder* or prompt the user for one."""
    if embedder == "gemini":
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if key:
            return key
        return click.prompt("  GEMINI_API_KEY", default="", show_default=False).strip()
    if embedder == "openai":
        key = os.environ.get("OPENAI_API_KEY", "")
        if key:
            return key
        return click.prompt("  OPENAI_API_KEY", default="", show_default=False).strip()
    return ""


def _set_api_key_env(embedder: str, key: str) -> None:
    if not key:
        return
    if embedder == "gemini":
        os.environ.setdefault("GEMINI_API_KEY", key)
    elif embedder == "openai":
        os.environ.setdefault("OPENAI_API_KEY", key)


def _save_global_embedder(embedder: str, api_key: str) -> None:
    """Persist embedder choice to the central app config."""
    try:
        payload = {"embedder": embedder}
        if api_key:
            payload["embedder_api_key"] = api_key
        save_app_config(payload)
    except Exception:
        pass  # Non-fatal — user just gets prompted again next time.


def _write_server_state(
    *,
    repo_path: Path,
    port: int,
    host: str,
    workers: int,
    ui_port: int,
    no_ui: bool,
    mcp_port: int,
    no_mcp: bool,
) -> None:
    ensure_app_data_dir()
    state_path = get_server_state_path()
    state_path.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "repo_path": str(repo_path),
                "port": port,
                "host": host,
                "workers": workers,
                "ui_port": ui_port,
                "no_ui": no_ui,
                "mcp_port": mcp_port,
                "no_mcp": no_mcp,
                "started_at": time.time(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def clear_server_state() -> None:
    state_path = get_server_state_path()
    if state_path.exists():
        state_path.unlink()


def load_server_state() -> dict | None:
    state_path = get_server_state_path()
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _terminate_process(pid: int) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except PermissionError:
        raise click.ClickException(f"Cannot terminate process {pid}.")

    deadline = time.time() + 8
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.2)

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    return True


def restart_server(
    *,
    repo_path: Path | None = None,
    port: int | None = None,
    host: str | None = None,
    workers: int | None = None,
    ui_port: int | None = None,
    no_ui: bool | None = None,
    mcp_port: int | None = None,
    no_mcp: bool | None = None,
) -> None:
    state = load_server_state() or {}
    effective_repo_path = repo_path or (Path(state["repo_path"]) if state.get("repo_path") else None)
    if effective_repo_path is None:
        raise click.ClickException("No previous server state found. Pass the repo path explicitly.")

    if state.get("pid"):
        _terminate_process(int(state["pid"]))

    command = [
        sys.executable,
        "-m",
        "repowise",
        "serve",
        str(effective_repo_path),
        "--port",
        str(port if port is not None else state.get("port", 7337)),
        "--host",
        str(host if host is not None else state.get("host", "127.0.0.1")),
        "--workers",
        str(workers if workers is not None else state.get("workers", 1)),
        "--ui-port",
        str(ui_port if ui_port is not None else state.get("ui_port", 3000)),
        "--mcp-port",
        str(mcp_port if mcp_port is not None else state.get("mcp_port", 7338)),
    ]
    effective_no_ui = no_ui if no_ui is not None else bool(state.get("no_ui", False))
    if effective_no_ui:
        command.append("--no-ui")
    effective_no_mcp = no_mcp if no_mcp is not None else bool(state.get("no_mcp", False))
    if effective_no_mcp:
        command.append("--no-mcp")

    ensure_app_data_dir()
    log_path = get_server_log_path()
    with log_path.open("ab") as handle:
        subprocess.Popen(
            command,
            cwd=str(Path(__file__).resolve().parents[4]),
            stdout=handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

def _node_available() -> str | None:
    """Return the path to node binary, or None."""
    return shutil.which("node")


def _npm_available() -> str | None:
    """Return the path to npm binary, or None."""
    return shutil.which("npm")


def _find_local_web() -> Path | None:
    """Return the repo-local Web UI source directory when present."""
    for candidate in Path(__file__).resolve().parents:
        pkg_web = candidate / "packages" / "web"
        if (pkg_web / "package.json").exists():
            return pkg_web
    return None


def _build_local_web(web_dir: Path, npm: str) -> bool:
    """Build the Next.js frontend from source."""
    console.print("[dim]Building web UI (first time only)...[/dim]")
    try:
        # Install deps if needed
        if not (web_dir / "node_modules").exists():
            result = subprocess.run(
                [npm, "install"],
                cwd=str(web_dir),
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                console.print(f"[yellow]npm install failed:[/yellow]\n{result.stderr or result.stdout}")
                return False
        # Build
        result = subprocess.run(
            [npm, "run", "build"],
            cwd=str(web_dir),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(f"[yellow]npm run build failed:[/yellow]\n{result.stderr or result.stdout}")
            return False
        return True
    except Exception as exc:
        console.print(f"[yellow]Web UI build failed: {exc}[/yellow]")
        return False


def _start_mcp(repo_path: Path, mcp_port: int) -> subprocess.Popen | None:
    try:
        return subprocess.Popen(
            [sys.executable, "-m", "repowise", "mcp", str(repo_path), "--transport", "sse", "--port", str(mcp_port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
    except Exception as exc:
        console.print(f"[yellow]Could not start MCP server: {exc}[/yellow]")
        return None


def _start_frontend(node: str, backend_port: int, frontend_port: int) -> subprocess.Popen | None:
    """Start the Next.js frontend server. Returns the process or None."""
    env = {
        **os.environ,
        "REPOWISE_API_URL": f"http://localhost:{backend_port}",
        "HOSTNAME": "127.0.0.1",
        "PORT": str(frontend_port),
    }

    local_web = _find_local_web()
    if local_web:
        standalone_dir = local_web / ".next" / "standalone"
        server_js = standalone_dir / "server.js"
        if server_js.exists():
            # Copy static files into standalone (Next.js requirement)
            static_src = local_web / ".next" / "static"
            static_dst = standalone_dir / ".next" / "static"
            if static_src.exists() and not static_dst.exists():
                shutil.copytree(str(static_src), str(static_dst))
            public_src = local_web / "public"
            public_dst = standalone_dir / "public"
            if public_src.exists() and not public_dst.exists():
                shutil.copytree(str(public_src), str(public_dst))

            return subprocess.Popen(
                [node, str(server_js)],
                cwd=str(standalone_dir),
                env=env,
            )

    return None


@click.command("serve")
@click.argument("path", required=False, default=None)
@click.option("--port", default=7337, type=int, help="API server port.")
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
@click.option("--workers", default=1, type=int, help="Number of uvicorn workers.")
@click.option("--ui-port", default=3000, type=int, help="Web UI port.")
@click.option("--no-ui", is_flag=True, help="Start API server only, skip the web UI.")
@click.option("--mcp-port", default=7338, type=int, help="MCP SSE server port.")
@click.option("--no-mcp", is_flag=True, help="Skip the MCP SSE server.")
def serve_command(path: str | None, port: int, host: str, workers: int, ui_port: int, no_ui: bool, mcp_port: int, no_mcp: bool) -> None:
    """Start the repowise API server, web UI, and MCP SSE server.

    Use --no-ui to skip the web UI, --no-mcp to skip the MCP server.
    """
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn is not installed. Install it with: pip install repowise[/red]")
        raise SystemExit(1) from None

    repo_path = resolve_repo_path(path) if path is not None else None
    if repo_path is not None:
        require_repowise_dir(repo_path)
    _setup_embedder()
    if repo_path is not None:
        os.environ["REPOWISE_TARGET_REPO"] = str(repo_path)
        os.environ["REPOWISE_DB_URL"] = get_db_url_for_repo(repo_path)
        console.print(f"[dim]Using target repository: {repo_path}[/dim]")
    else:
        os.environ.pop("REPOWISE_TARGET_REPO", None)
        os.environ["REPOWISE_DB_URL"] = get_db_url_for_repo(Path.cwd())
        console.print("[dim]Using central repowise application database.[/dim]")
    _write_server_state(
        repo_path=repo_path or Path.cwd(),
        port=port,
        host=host,
        workers=workers,
        ui_port=ui_port,
        no_ui=no_ui,
        mcp_port=mcp_port,
        no_mcp=no_mcp,
    )

    mcp_proc: subprocess.Popen | None = None
    if not no_mcp:
        mcp_proc = _start_mcp(repo_path or Path.cwd(), mcp_port)
        if mcp_proc:
            console.print(f"[green]MCP SSE server starting on http://127.0.0.1:{mcp_port}/sse[/green]")

    frontend_proc: subprocess.Popen | None = None
    local_web = _find_local_web()

    if not no_ui:
        node = _node_available()
        npm = _npm_available()

        if not node:
            console.print(
                "[yellow]Node.js not found — starting API server only.[/yellow]\n"
                "[dim]To get the web UI, install Node.js 20+ or use Docker:\n"
                "  docker run -p 7337:7337 -p 3000:3000 -v .repowise:/data repowise[/dim]"
            )
        elif not local_web:
            console.print(
                "[yellow]Local Web UI source not found in packages/web — starting API server only.[/yellow]"
            )
        else:
            ready = False

            standalone = local_web / ".next" / "standalone" / "server.js"
            if standalone.exists():
                ready = True

            if not ready:
                ready = _build_local_web(local_web, npm) if npm else False

            if ready:
                frontend_proc = _start_frontend(node, port, ui_port)
                if frontend_proc:
                    console.print(f"[green]Web UI starting on http://127.0.0.1:{ui_port}[/green]")
                else:
                    console.print("[yellow]Could not start web UI — running API only.[/yellow]")
            else:
                console.print(
                    "[yellow]Local Web UI build failed — starting API server only.[/yellow]"
                )

    console.print(f"[green]API server starting on http://{host}:{port}[/green]")

    try:
        uvicorn.run(
            "repowise.server.app:create_app",
            factory=True,
            host=host,
            port=port,
            workers=workers,
            log_level="info",
        )
    finally:
        clear_server_state()
        if mcp_proc:
            mcp_proc.terminate()
            mcp_proc.wait(timeout=5)
        if frontend_proc:
            frontend_proc.terminate()
            frontend_proc.wait(timeout=5)
