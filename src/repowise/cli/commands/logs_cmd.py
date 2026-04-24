"""``repowise logs`` — show or follow the running server log."""

from __future__ import annotations

import time
from collections import deque
from pathlib import Path

import click

from repowise.app_runtime import get_server_log_path
from repowise.cli.helpers import console


def read_last_lines(path: Path, line_count: int) -> list[str]:
    """Return the last *line_count* lines from *path*."""
    if line_count <= 0:
        return []

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return list(deque(handle, maxlen=line_count))


def print_log_tail(path: Path, line_count: int) -> None:
    for line in read_last_lines(path, line_count):
        console.print(line.rstrip("\n"))


def follow_log(path: Path, line_count: int, interval: float) -> None:
    print_log_tail(path, line_count)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(0, 2)
        try:
            while True:
                line = handle.readline()
                if line:
                    console.print(line.rstrip("\n"))
                    continue
                time.sleep(interval)
        except KeyboardInterrupt:
            pass


@click.command("logs")
@click.option("--follow", "-f", is_flag=True, help="Keep streaming new log lines.")
@click.option(
    "--lines",
    "-n",
    default=100,
    show_default=True,
    type=click.IntRange(min=0),
    help="Number of recent log lines to show before exiting or following.",
)
@click.option(
    "--interval",
    default=0.5,
    show_default=True,
    type=click.FloatRange(min=0.1),
    help="Polling interval in seconds when following.",
)
def logs_command(follow: bool, lines: int, interval: float) -> None:
    """Show or follow logs from a running repowise server."""
    log_path = get_server_log_path()
    if not log_path.exists():
        raise click.ClickException(
            f"No repowise server log found at {log_path}. Run 'repowise start' or 'repowise restart' first."
        )

    if follow:
        follow_log(log_path, lines, interval)
        return

    print_log_tail(log_path, lines)
