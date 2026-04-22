"""Async database engine and session factory for repowise.

Supports two backends:
- SQLite (default): sqlite+aiosqlite:///path/to/file.db
- PostgreSQL:       postgresql+asyncpg://user:pass@host/dbname

Call get_db_url() to normalise raw URLs (adds the async driver prefix).
Call create_engine() to create an AsyncEngine.
Call init_db() once at startup to create all tables and the FTS index.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool
from sqlalchemy.sql import text

from repowise.app_runtime import ensure_app_data_dir, get_app_db_path
from repowise.target_repo import resolve_target_repo_paths

from .models import Base

__all__ = [
    "AsyncEngine",
    "AsyncSession",
    "async_sessionmaker",
    "create_engine",
    "create_session_factory",
    "get_configured_db_url",
    "get_db_url",
    "get_repo_db_path",
    "get_session",
    "init_db",
    "resolve_db_url",
]

DB_FILENAME = "wiki.db"
REPOWISE_DIRNAME = ".repowise"
DB_ENV_VARS = ("REPOWISE_DB_URL", "REPOWISE_DATABASE_URL")


async def _ensure_sqlite_graph_nodes_schema(conn) -> None:
    """Backfill columns added after the initial SQLite graph schema shipped.

    Repowise currently relies on create_all() without a migration layer, so
    repo-local SQLite databases can drift across package versions.
    """
    result = await conn.execute(text("PRAGMA table_info(graph_nodes)"))
    existing_columns = {row[1] for row in result.fetchall()}
    if not existing_columns:
        return

    add_column_statements = {
        "community_meta_json": (
            "ALTER TABLE graph_nodes "
            "ADD COLUMN community_meta_json TEXT NOT NULL DEFAULT '{}'"
        ),
        "kind": "ALTER TABLE graph_nodes ADD COLUMN kind VARCHAR(32)",
        "name": "ALTER TABLE graph_nodes ADD COLUMN name VARCHAR(255)",
        "qualified_name": "ALTER TABLE graph_nodes ADD COLUMN qualified_name TEXT",
        "file_path": "ALTER TABLE graph_nodes ADD COLUMN file_path TEXT",
        "start_line": "ALTER TABLE graph_nodes ADD COLUMN start_line INTEGER",
        "end_line": "ALTER TABLE graph_nodes ADD COLUMN end_line INTEGER",
        "visibility": "ALTER TABLE graph_nodes ADD COLUMN visibility VARCHAR(16)",
        "signature": "ALTER TABLE graph_nodes ADD COLUMN signature TEXT",
        "parent_symbol_id": "ALTER TABLE graph_nodes ADD COLUMN parent_symbol_id TEXT",
    }
    for column_name, statement in add_column_statements.items():
        if column_name not in existing_columns:
            await conn.execute(text(statement))


async def _ensure_sqlite_graph_edges_schema(conn) -> None:
    """Backfill columns added after the initial SQLite edge schema shipped."""
    result = await conn.execute(text("PRAGMA table_info(graph_edges)"))
    existing_columns = {row[1] for row in result.fetchall()}
    if not existing_columns:
        return

    add_column_statements = {
        "confidence": (
            "ALTER TABLE graph_edges "
            "ADD COLUMN confidence FLOAT NOT NULL DEFAULT 1.0"
        ),
    }
    for column_name, statement in add_column_statements.items():
        if column_name not in existing_columns:
            await conn.execute(text(statement))


async def _ensure_sqlite_wiki_pages_schema(conn) -> None:
    """Backfill columns added to wiki_pages after initial schema shipped."""
    result = await conn.execute(text("PRAGMA table_info(wiki_pages)"))
    existing_columns = {row[1] for row in result.fetchall()}
    if not existing_columns:
        return

    add_column_statements = {
        "summary": "ALTER TABLE wiki_pages ADD COLUMN summary TEXT",
        "human_notes": "ALTER TABLE wiki_pages ADD COLUMN human_notes TEXT",
    }
    for column_name, statement in add_column_statements.items():
        if column_name not in existing_columns:
            await conn.execute(text(statement))


async def _ensure_sqlite_indexes(conn) -> None:
    """Create runtime-managed indexes that ``create_all()`` cannot backfill."""
    statements = (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_repositories_local_path "
        "ON repositories(local_path)",
        "CREATE INDEX IF NOT EXISTS ix_wiki_pages_repository_id ON wiki_pages(repository_id)",
        "CREATE INDEX IF NOT EXISTS ix_generation_jobs_repository_id ON generation_jobs(repository_id)",
    )
    for statement in statements:
        await conn.execute(text(statement))


def get_repo_db_path(repo_path: str | Path) -> Path:
    """Return the repo-local database path ``<repo>/.repowise/wiki.db``."""
    return resolve_target_repo_paths(repo_path).db_path


def _default_db_url(repo_path: str | Path | None = None) -> str:
    """Return the default SQLite URL for the central application database."""
    ensure_app_data_dir()
    db_path = get_app_db_path()
    return f"sqlite+aiosqlite:///{db_path.as_posix()}"


def get_db_url(raw_url: str | None = None) -> str:
    """Normalise a database URL to include the async driver prefix.

    - ``sqlite:///...``      → ``sqlite+aiosqlite:///...``
    - ``postgresql://...``   → ``postgresql+asyncpg://...``
    - ``postgresql+psycopg://...`` → unchanged (explicit driver wins)
    - Already async-prefixed URLs are returned as-is.
    - ``None`` → central application DB: ``<repowise-root>/.repowise/wiki.db``
    """
    if raw_url is None:
        return _default_db_url()

    url = raw_url.strip()

    if url.startswith("sqlite://") and "aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)

    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return url.replace("://", "+asyncpg://", 1)

    return url


def get_configured_db_url() -> str | None:
    """Return the configured DB URL from supported env vars, if present."""
    for env_name in DB_ENV_VARS:
        env_url = os.environ.get(env_name)
        if env_url:
            return get_db_url(env_url)
    return None


def resolve_db_url(repo_path: str | Path | None = None) -> str:
    """Resolve the active DB URL from env vars or the default filesystem path.

    Resolution order:
    1. ``REPOWISE_DB_URL``
    2. ``REPOWISE_DATABASE_URL`` (legacy compatibility)
    3. central application DB otherwise
    """
    configured = get_configured_db_url()
    if configured is not None:
        return configured
    return _default_db_url(repo_path)


def create_engine(
    url: str | None = None,
    *,
    echo: bool = False,
    # StaticPool is required for :memory: SQLite so all connections share the same DB.
    # Pass use_static_pool=True explicitly when creating in-memory test engines.
    use_static_pool: bool = False,
) -> AsyncEngine:
    """Create an AsyncEngine for the given database URL.

    Args:
        url:             Raw or async-prefixed database URL.  Defaults to SQLite.
        echo:            Log all SQL statements (useful for debugging).
        use_static_pool: Force StaticPool (required for in-memory SQLite tests).
    """
    db_url = get_db_url(url)
    is_sqlite = db_url.startswith("sqlite")

    kwargs: dict = {"echo": echo}

    if is_sqlite:
        # SQLite requires check_same_thread=False for multi-threaded async use
        kwargs["connect_args"] = {"check_same_thread": False}
        if use_static_pool or ":memory:" in db_url:
            # StaticPool: all connect() calls return the same connection.
            # Mandatory for in-memory SQLite — without it each call gets a fresh DB.
            kwargs["poolclass"] = StaticPool
        else:
            kwargs["poolclass"] = NullPool
    else:
        # PostgreSQL — asyncpg handles its own connection pool
        kwargs["pool_pre_ping"] = True

    engine = create_async_engine(db_url, **kwargs)

    if is_sqlite and not (use_static_pool or ":memory:" in db_url):
        # WAL mode allows multiple concurrent writers across processes.
        # busy_timeout makes SQLite retry for up to 10 s instead of
        # immediately raising "database is locked".
        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_wal(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return an async_sessionmaker bound to *engine*.

    expire_on_commit=False: prevents SQLAlchemy from expiring attributes after
    commit, which would require a sync lazy-load (impossible in async context).
    """
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that yields a session and handles commit/rollback."""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db(engine: AsyncEngine) -> None:
    """Create all SQLAlchemy tables and the FTS index for the given engine.

    Safe to call on an already-initialised database (idempotent).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # SQLite-only: create FTS5 virtual table for full-text search.
        # PostgreSQL uses a GIN index added by the Alembic migration.
        if engine.dialect.name == "sqlite":
            await _ensure_sqlite_graph_nodes_schema(conn)
            await _ensure_sqlite_graph_edges_schema(conn)
            await _ensure_sqlite_indexes(conn)
            await _ensure_sqlite_wiki_pages_schema(conn)
            await conn.execute(
                text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS page_fts "
                    "USING fts5(page_id UNINDEXED, title, content)"
                )
            )
