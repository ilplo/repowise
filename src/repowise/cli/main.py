"""repowise CLI — codebase intelligence for developers and AI."""

from __future__ import annotations

import click

from repowise.cli import __version__
from repowise.cli.commands.claude_md_cmd import claude_md_command
from repowise.cli.commands.costs_cmd import costs_command
from repowise.cli.commands.dead_code_cmd import dead_code_command
from repowise.cli.commands.decision_cmd import decision_group
from repowise.cli.commands.doctor_cmd import doctor_command
from repowise.cli.commands.export_cmd import export_command
from repowise.cli.commands.init_cmd import init_command
from repowise.cli.commands.logs_cmd import logs_command
from repowise.cli.commands.mcp_cmd import mcp_command
from repowise.cli.commands.reindex_cmd import reindex_command
from repowise.cli.commands.restart_cmd import restart_command
from repowise.cli.commands.search_cmd import search_command
from repowise.cli.commands.start_cmd import start_command
from repowise.cli.commands.status_cmd import status_command
from repowise.cli.commands.stop_cmd import stop_command
from repowise.cli.commands.update_cmd import update_command
from repowise.cli.commands.watch_cmd import watch_command
from repowise.cli.runtime import ensure_local_cli_runtime


@click.group()
@click.version_option(version=__version__, prog_name="repowise")
def cli() -> None:
    """repowise -- codebase intelligence for developers and AI."""
    ensure_local_cli_runtime()


cli.add_command(init_command)
cli.add_command(claude_md_command)
cli.add_command(costs_command)
cli.add_command(update_command)
cli.add_command(dead_code_command)
cli.add_command(decision_group)
cli.add_command(search_command)
cli.add_command(export_command)
cli.add_command(status_command)
cli.add_command(doctor_command)
cli.add_command(watch_command)
cli.add_command(start_command)
cli.add_command(stop_command)
cli.add_command(logs_command)
cli.add_command(mcp_command)
cli.add_command(reindex_command)
cli.add_command(restart_command)
