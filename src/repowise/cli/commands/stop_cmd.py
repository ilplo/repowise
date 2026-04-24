"""``repowise stop`` — stop the API server and companion services."""

from __future__ import annotations

import click

from repowise.cli.commands.start_cmd import load_server_state, stop_server
from repowise.cli.helpers import console


@click.command("stop")
@click.option("--port", type=int, default=None, help="API server port override.")
@click.option("--ui-port", type=int, default=None, help="Web UI port override.")
@click.option("--mcp-port", type=int, default=None, help="MCP SSE port override.")
@click.option("--no-ui", is_flag=True, default=False, help="Skip looking for the web UI process.")
@click.option("--no-mcp", is_flag=True, default=False, help="Skip looking for the MCP process.")
def stop_command(
    port: int | None,
    ui_port: int | None,
    mcp_port: int | None,
    no_ui: bool,
    no_mcp: bool,
) -> None:
    """Stop the running repowise services."""
    state = load_server_state()
    terminated = stop_server(
        port=port,
        ui_port=ui_port,
        mcp_port=mcp_port,
        no_ui=no_ui if no_ui else None,
        no_mcp=no_mcp if no_mcp else None,
    )

    if not terminated:
        console.print("[dim]No running repowise processes found.[/dim]")
        return

    if state and state.get("port"):
        console.print(
            f"[green]Stopped repowise processes[/green] [dim](pid(s): {', '.join(str(pid) for pid in terminated)}, "
            f"http://127.0.0.1:{state['port']})[/dim]"
        )
        return

    console.print(
        f"[green]Stopped repowise processes[/green] [dim](pid(s): {', '.join(str(pid) for pid in terminated)})[/dim]"
    )
