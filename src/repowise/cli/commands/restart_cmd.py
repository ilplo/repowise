"""``repowise restart`` — stop all running services and start them fresh."""

from __future__ import annotations

import click

from repowise.cli.commands.start_cmd import (
    _build_local_web,
    _find_local_web,
    _frontend_needs_build,
    _npm_available,
    restart_server,
)
from repowise.cli.helpers import console, resolve_repo_path


@click.command("restart")
@click.argument("path", required=False, default=None)
@click.option("--port", type=int, default=None, help="API server port override.")
@click.option("--host", default=None, help="Host override.")
@click.option("--workers", type=int, default=None, help="Worker-count override.")
@click.option("--ui-port", type=int, default=None, help="Web UI port override.")
@click.option("--no-ui", is_flag=True, default=False, help="Skip the web UI.")
@click.option("--no-mcp", is_flag=True, default=False, help="Skip the MCP server.")
def restart_command(
    path: str | None,
    port: int | None,
    host: str | None,
    workers: int | None,
    ui_port: int | None,
    no_ui: bool,
    no_mcp: bool,
) -> None:
    """Stop all running repowise services and start them fresh."""
    local_web = _find_local_web()
    npm = _npm_available()
    if local_web and npm:
        if _frontend_needs_build(local_web):
            console.print("[dim]Frontend source changed — rebuilding…[/dim]")
            if _build_local_web(local_web, npm):
                console.print("[green]✓[/green] Frontend built.")
            else:
                console.print("[yellow]Frontend build failed — using existing build.[/yellow]")

    repo_path = resolve_repo_path(path) if path is not None else None
    restart_server(
        repo_path=repo_path,
        port=port,
        host=host,
        workers=workers,
        ui_port=ui_port,
        no_ui=no_ui if no_ui else None,
        no_mcp=no_mcp if no_mcp else None,
    )
    console.print(f"[green]✓ Server restarted[/green] [dim](http://127.0.0.1:{port or 7337})[/dim]")
