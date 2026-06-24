from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repowise.core.ingestion.git_indexer import GitIndexer
from repowise.core.persistence import create_engine, create_session_factory, get_session, init_db
from repowise.core.persistence.crud import (
    get_all_git_metadata,
    prune_git_metadata_to_paths,
    recompute_git_percentiles,
    upsert_git_metadata_bulk,
    upsert_repository,
)


class GitHotspotClassificationTests(unittest.TestCase):
    def test_low_absolute_churn_is_not_a_hotspot(self) -> None:
        metadata = [
            {
                "file_path": "a.ts",
                "commit_count_90d": 1,
                "temporal_hotspot_score": 1.0,
            },
            {
                "file_path": "b.ts",
                "commit_count_90d": 2,
                "temporal_hotspot_score": 2.0,
            },
            {
                "file_path": "app/page.tsx",
                "commit_count_90d": 4,
                "temporal_hotspot_score": 5.6,
            },
            {
                "file_path": "blast-radius/page.tsx",
                "commit_count_90d": 1,
                "temporal_hotspot_score": 6.0,
            },
        ]

        GitIndexer._compute_percentiles(metadata)

        self.assertFalse(any(meta.get("is_hotspot") for meta in metadata))

    def test_sustained_churn_can_be_a_hotspot(self) -> None:
        metadata = [
            {
                "file_path": "a.ts",
                "commit_count_90d": 1,
                "temporal_hotspot_score": 1.0,
            },
            {
                "file_path": "b.ts",
                "commit_count_90d": 2,
                "temporal_hotspot_score": 2.0,
            },
            {
                "file_path": "c.ts",
                "commit_count_90d": 3,
                "temporal_hotspot_score": 3.0,
            },
            {
                "file_path": "active/page.tsx",
                "commit_count_90d": 5,
                "temporal_hotspot_score": 6.0,
            },
        ]

        GitIndexer._compute_percentiles(metadata)

        active = next(meta for meta in metadata if meta["file_path"] == "active/page.tsx")
        self.assertTrue(active.get("is_hotspot"))

    def test_incremental_index_skips_non_code_files(self) -> None:
        class FakeRepo:
            def close(self) -> None:
                pass

        indexer = GitIndexer(Path("."))
        indexed: list[str] = []
        indexer._get_repo = lambda: FakeRepo()  # type: ignore[method-assign]

        def index_file(file_path: str, repo: object) -> dict:
            indexed.append(file_path)
            return {"file_path": file_path}

        indexer._index_file = index_file  # type: ignore[method-assign]

        result = asyncio.run(
            indexer.index_changed_files(
                [
                    "packages/web/package-lock.json",
                    "packages/web/src/app/page.tsx",
                ]
            )
        )

        self.assertEqual(indexed, ["packages/web/src/app/page.tsx"])
        self.assertEqual(result, [{"file_path": "packages/web/src/app/page.tsx"}])


class GitHotspotPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine("sqlite+aiosqlite:///:memory:", use_static_pool=True)
        await init_db(self.engine)
        self.session_factory = create_session_factory(self.engine)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()

    async def test_recompute_uses_absolute_churn_floor(self) -> None:
        async with get_session(self.session_factory) as session:
            repo = await upsert_repository(
                session,
                name="repo",
                local_path="/tmp/repo",
            )
            await upsert_git_metadata_bulk(
                session,
                repo.id,
                [
                    {
                        "file_path": "a.ts",
                        "commit_count_90d": 1,
                        "temporal_hotspot_score": 1.0,
                    },
                    {
                        "file_path": "b.ts",
                        "commit_count_90d": 2,
                        "temporal_hotspot_score": 2.0,
                    },
                    {
                        "file_path": "app/page.tsx",
                        "commit_count_90d": 4,
                        "temporal_hotspot_score": 5.6,
                    },
                    {
                        "file_path": "blast-radius/page.tsx",
                        "commit_count_90d": 1,
                        "temporal_hotspot_score": 6.0,
                    },
                ],
            )
            await recompute_git_percentiles(session, repo.id)
            rows = await get_all_git_metadata(session, repo.id)

        self.assertFalse(any(row.is_hotspot for row in rows.values()))

    async def test_prune_removes_stale_non_indexed_rows(self) -> None:
        async with get_session(self.session_factory) as session:
            repo = await upsert_repository(
                session,
                name="repo",
                local_path="/tmp/repo",
            )
            await upsert_git_metadata_bulk(
                session,
                repo.id,
                [
                    {
                        "file_path": "packages/web/package-lock.json",
                        "commit_count_90d": 10,
                        "temporal_hotspot_score": 100.0,
                        "is_hotspot": True,
                    },
                    {
                        "file_path": "packages/web/src/app/page.tsx",
                        "commit_count_90d": 5,
                        "temporal_hotspot_score": 10.0,
                    },
                ],
            )

            deleted = await prune_git_metadata_to_paths(
                session,
                repo.id,
                ["packages/web/src/app/page.tsx"],
            )
            rows = await get_all_git_metadata(session, repo.id)

        self.assertEqual(deleted, 1)
        self.assertEqual(set(rows), {"packages/web/src/app/page.tsx"})


if __name__ == "__main__":
    unittest.main()
