"""/api/logs — read-only server log access for the local UI."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from repowise.app_runtime import get_server_log_path
from repowise.server.deps import verify_api_key
from repowise.server.schemas import ServerLogResponse

router = APIRouter(
    prefix="/api/logs",
    tags=["logs"],
    dependencies=[Depends(verify_api_key)],
)


def _tail_log_lines(path: Path, line_count: int) -> list[str]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return [line.rstrip("\n") for line in deque(handle, maxlen=line_count)]


@router.get("/server", response_model=ServerLogResponse)
def get_server_logs(
    lines: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> ServerLogResponse:
    """Return the latest lines from the local repowise server log."""
    log_path = get_server_log_path()
    return ServerLogResponse(
        path=str(log_path),
        lines=_tail_log_lines(log_path, lines),
    )
