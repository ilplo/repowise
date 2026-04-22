"""``repowise restart`` — restart the API/UI server with the current checkout code."""

from __future__ import annotations

import click

from repowise.cli.commands.serve_cmd import restart_server
from repowise.cli.helpers import console, resolve_repo_path


@click.command("restart")
@click.argument("path", required=False, default=None)
@click.option("--port", type=int, default=None, help="API server port override.")
@click.option("--host", default=None, help="Host override.")
@click.option("--workers", type=int, default=None, help="Worker-count override.")
@click.option("--ui-port", type=int, default=None, help="Web UI port override.")
@click.option("--no-ui", is_flag=True, default=False, help="Restart API only.")
def restart_command(
    path: str | None,
    port: int | None,
    host: str | None,
    workers: int | None,
    ui_port: int | None,
    no_ui: bool,
) -> None:
    """Restart the repowise server using the current source checkout."""
    repo_path = resolve_repo_path(path) if path is not None else None
    restart_server(
        repo_path=repo_path,
        port=port,
        host=host,
        workers=workers,
        ui_port=ui_port,
        no_ui=no_ui if no_ui else None,
    )
    console.print("[green]repowise server restart requested.[/green]")
