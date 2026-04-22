"""``repowise mcp`` — Start the MCP server for editor integration."""

from __future__ import annotations

import click

from repowise.cli.helpers import console, require_repowise_dir, resolve_repo_path


@click.command("mcp")
@click.argument("path", required=True)
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="Transport protocol: stdio (Claude Code/Cursor) or sse (web clients).",
)
@click.option(
    "--port",
    type=int,
    default=7338,
    help="Port for SSE transport (default: 7338).",
)
def mcp_command(path: str, transport: str, port: int) -> None:
    """Start the MCP server for editor integration.

    Exposes 16 tools for querying the repowise wiki via the MCP protocol.
    Supports both stdio (for Claude Code, Cursor, Cline) and SSE transports.

    Examples:

        repowise mcp /path/to/repo       # stdio, specific repo
        repowise mcp --transport sse     # SSE on port 7338
    """
    repo_path = resolve_repo_path(path, require_explicit=True)
    require_repowise_dir(repo_path)

    if transport == "sse":
        console.print(
            f"[bold green]Starting repowise MCP server (SSE) on port {port}...[/bold green]"
        )
    else:
        # stdio mode — no console output (it would corrupt the protocol)
        pass

    from repowise.server.mcp_server import run_mcp

    run_mcp(
        transport=transport,
        repo_path=str(repo_path),
        port=port,
    )
