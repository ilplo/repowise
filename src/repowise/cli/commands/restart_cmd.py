"""``repowise restart`` — rebuild the web UI and restart the server."""

from __future__ import annotations

import click

from repowise.cli.commands.start_cmd import (
    _build_local_web,
    _find_local_web,
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
@click.option("--skip-build", is_flag=True, default=False, help="Skip web UI rebuild.")
def restart_command(
    path: str | None,
    port: int | None,
    host: str | None,
    workers: int | None,
    ui_port: int | None,
    no_ui: bool,
    skip_build: bool,
) -> None:
    """Rebuild the web UI and restart (or start) the repowise server."""
    if not no_ui and not skip_build:
        local_web = _find_local_web()
        npm = _npm_available()
        if local_web and npm:
            if _build_local_web(local_web, npm):
                console.print("[green]✓[/green] Web UI built.")
            else:
                console.print("[yellow]Web UI build failed — using existing build.[/yellow]")

    repo_path = resolve_repo_path(path) if path is not None else None
    restart_server(
        repo_path=repo_path,
        port=port,
        host=host,
        workers=workers,
        ui_port=ui_port,
        no_ui=no_ui if no_ui else None,
    )
    console.print(f"[green]✓ Server restarted[/green] [dim](http://127.0.0.1:{port or 7337})[/dim]")
