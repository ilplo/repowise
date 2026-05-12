"""Auto-generated MCP config for Codex and other MCP clients."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from repowise.app_runtime import ensure_repo_runtime_dir


def _standalone_source_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _toml_value(value: str | int | bool | list[str]) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(json.dumps(item) for item in value) + "]"
    return json.dumps(value)


def _remove_toml_tables(text: str, table_names: set[str]) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    skipping = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            table_name = stripped.lstrip("[").rstrip("]")
            skipping = table_name in table_names
            if skipping:
                continue
        if not skipping:
            kept.append(line)

    return "\n".join(kept).rstrip()


def generate_mcp_config(repo_path: Path) -> dict:
    """Generate MCP config JSON for a repository.

    Returns a dict in the standard mcpServers format.
    """
    abs_path = str(repo_path.resolve()).replace("\\", "/")
    source_root = str(_standalone_source_root()).replace("\\", "/")
    pythonpath = source_root
    existing_pythonpath = os.environ.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath = f"{source_root}{os.pathsep}{existing_pythonpath}"
    return {
        "mcpServers": {
            "repowise": {
                "command": sys.executable,
                "args": ["-m", "repowise", "mcp", abs_path, "--transport", "stdio"],
                "env": {"PYTHONPATH": pythonpath},
                "description": "repowise: codebase intelligence — docs, graph, git signals, dead code, decisions",
            }
        }
    }


def generate_codex_mcp_config_toml(repo_path: Path) -> str:
    """Generate a Codex project-scoped MCP config block for a repository."""
    server = generate_mcp_config(repo_path)["mcpServers"]["repowise"]
    lines = [
        "[mcp_servers.repowise]",
        f"command = {_toml_value(server['command'])}",
        f"args = {_toml_value(server['args'])}",
        'startup_timeout_sec = 30',
        "",
    ]
    env = server.get("env", {})
    if env:
        lines.append("[mcp_servers.repowise.env]")
        for key, value in env.items():
            lines.append(f"{key} = {_toml_value(value)}")
        lines.append("")
    return "\n".join(lines)


def save_mcp_config(repo_path: Path) -> Path:
    """Save MCP config to the central repo runtime directory and return the path."""
    repowise_dir = ensure_repo_runtime_dir(repo_path)
    repowise_dir.mkdir(parents=True, exist_ok=True)
    config_path = repowise_dir / "mcp.json"
    config = generate_mcp_config(repo_path)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return config_path


def save_codex_mcp_config(repo_path: Path) -> Path:
    """Write project-scoped Codex MCP config at <repo>/.codex/config.toml."""
    config_dir = repo_path / ".codex"
    config_path = config_dir / "config.toml"
    new_block = generate_codex_mcp_config_toml(repo_path).rstrip()
    table_names = {"mcp_servers.repowise", "mcp_servers.repowise.env"}

    if config_path.exists():
        try:
            existing = config_path.read_text(encoding="utf-8")
        except OSError:
            existing = ""
        base = _remove_toml_tables(existing, table_names)
        merged = f"{base}\n\n{new_block}\n" if base else f"{new_block}\n"
    else:
        merged = f"{new_block}\n"

    config_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(merged, encoding="utf-8")
    return config_path


def save_root_mcp_config(repo_path: Path) -> Path:
    """Write .mcp.json at repo root for MCP clients that auto-discover it.

    Merges the repowise server entry into any existing mcpServers block
    so other MCP servers configured by the user are preserved.
    """
    config_path = repo_path / ".mcp.json"
    new_entry = generate_mcp_config(repo_path)["mcpServers"]

    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
        servers = dict(existing.get("mcpServers", {}))
        servers.update(new_entry)
        existing["mcpServers"] = servers
        merged = existing
    else:
        merged = {"mcpServers": new_entry}

    config_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return config_path


def format_setup_instructions(repo_path: Path) -> str:
    """Return human-readable setup instructions for MCP clients."""
    config = generate_mcp_config(repo_path)
    server_block = json.dumps(config["mcpServers"]["repowise"], indent=4)
    abs_path = str(repo_path.resolve()).replace("\\", "/")
    codex_config_path = repo_path / ".codex" / "config.toml"

    return f"""
MCP Server Configuration
========================

Codex: automatically configured via {codex_config_path}

Cursor (.cursor/mcp.json):
  {server_block}

Cline (cline_mcp_settings.json):
  "mcpServers": {{
    "repowise": {server_block}
  }}

Or run directly:
  repowise mcp {abs_path}
  repowise mcp {abs_path} --transport sse --port 7338

Config saved to: {ensure_repo_runtime_dir(repo_path) / "mcp.json"}
""".strip()
