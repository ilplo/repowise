from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class TargetRepoResolutionError(ValueError):
    """Raised when a target repository path cannot be resolved safely."""


@dataclass(frozen=True)
class TargetRepoPaths:
    repo_path: Path
    repowise_dir: Path
    db_path: Path
    config_path: Path
    state_path: Path


def canonicalize_target_repo_path(target_repo_path: str | Path) -> Path:
    return Path(target_repo_path).expanduser().resolve(strict=False)


def validate_target_repo_path(target_repo_path: str | Path) -> Path:
    candidate = canonicalize_target_repo_path(target_repo_path)

    if not candidate.exists():
        raise TargetRepoResolutionError(f"Target repo path does not exist: {candidate}")

    if not candidate.is_dir():
        raise TargetRepoResolutionError(f"Target repo path is not a directory: {candidate}")

    git_marker = candidate / ".git"
    if not git_marker.exists():
        raise TargetRepoResolutionError(
            f"Target repo path must point to a repository root containing .git: {candidate}"
        )

    return candidate


def resolve_target_repo_paths(target_repo_path: str | Path) -> TargetRepoPaths:
    repo_path = validate_target_repo_path(target_repo_path)
    repowise_dir = repo_path / ".repowise"

    return TargetRepoPaths(
        repo_path=repo_path,
        repowise_dir=repowise_dir,
        db_path=repowise_dir / "wiki.db",
        config_path=repowise_dir / "config.yaml",
        state_path=repowise_dir / "state.json",
    )


def ensure_repowise_dir(paths: TargetRepoPaths) -> Path:
    if paths.repowise_dir.exists() and not paths.repowise_dir.is_dir():
        raise TargetRepoResolutionError(
            f"Repowise state path exists but is not a directory: {paths.repowise_dir}"
        )

    paths.repowise_dir.mkdir(parents=True, exist_ok=True)
    return paths.repowise_dir


def require_repowise_dir(paths: TargetRepoPaths) -> Path:
    if not paths.repowise_dir.exists():
        raise TargetRepoResolutionError(
            f"Repowise state directory does not exist: {paths.repowise_dir}. "
            f"Run 'repowise init {paths.repo_path}' first."
        )

    if not paths.repowise_dir.is_dir():
        raise TargetRepoResolutionError(
            f"Repowise state path exists but is not a directory: {paths.repowise_dir}"
        )

    return paths.repowise_dir
