from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repowise.core.persistence import create_engine, create_session_factory, get_session, init_db
from repowise.core.persistence.crud import (
    get_decision_health_summary,
    upsert_decision,
    upsert_git_metadata_bulk,
    upsert_repository,
)
from repowise.server.routers.git import get_ownership


class AttentionSignalTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine("sqlite+aiosqlite:///:memory:", use_static_pool=True)
        await init_db(self.engine)
        self.session_factory = create_session_factory(self.engine)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()

    async def _create_repo(self) -> str:
        async with get_session(self.session_factory) as session:
            repo = await upsert_repository(
                session,
                name="repowise",
                local_path="/tmp/repowise",
            )
            return repo.id

    async def test_single_owner_repository_modules_are_not_attention_silos(self) -> None:
        repo_id = await self._create_repo()
        async with get_session(self.session_factory) as session:
            await upsert_git_metadata_bulk(
                session,
                repo_id,
                [
                    {
                        "file_path": "packages/web/src/app/page.tsx",
                        "primary_owner_name": "ilplo",
                        "primary_owner_email": "ilplo@example.com",
                        "primary_owner_commit_pct": 1.0,
                        "commit_count_total": 8,
                    },
                    {
                        "file_path": "packages/web/src/lib/api.ts",
                        "primary_owner_name": "ilplo",
                        "primary_owner_email": "ilplo@example.com",
                        "primary_owner_commit_pct": 1.0,
                        "commit_count_total": 7,
                    },
                    {
                        "file_path": "packages/web/src/components/panel.tsx",
                        "primary_owner_name": "ilplo",
                        "primary_owner_email": "ilplo@example.com",
                        "primary_owner_commit_pct": 1.0,
                        "commit_count_total": 6,
                    },
                ],
            )

            entries = await get_ownership(repo_id, granularity="module", session=session)

        self.assertTrue(entries)
        self.assertFalse(any(entry.is_silo for entry in entries))

    async def test_low_confidence_readme_mined_decisions_are_not_attention_items(self) -> None:
        repo_id = await self._create_repo()
        async with get_session(self.session_factory) as session:
            await upsert_decision(
                session,
                repository_id=repo_id,
                title="Add summary/human_notes to Page model",
                status="proposed",
                source="readme_mining",
                confidence=0.60,
            )
            await upsert_decision(
                session,
                repository_id=repo_id,
                title="Review explicit CLI decision",
                status="proposed",
                source="cli",
                confidence=1.0,
            )

            health = await get_decision_health_summary(session, repo_id)

        self.assertEqual(
            [decision.title for decision in health["proposed_awaiting_review"]],
            ["Review explicit CLI decision"],
        )

    async def test_stale_non_code_and_low_activity_hotspot_rows_are_not_attention_items(self) -> None:
        repo_id = await self._create_repo()
        async with get_session(self.session_factory) as session:
            await upsert_git_metadata_bulk(
                session,
                repo_id,
                [
                    {
                        "file_path": "packages/web/package-lock.json",
                        "is_hotspot": True,
                        "churn_percentile": 0.99,
                        "commit_count_90d": 20,
                    },
                    {
                        "file_path": "packages/web/src/app/page.tsx",
                        "is_hotspot": True,
                        "churn_percentile": 0.90,
                        "commit_count_90d": 4,
                    },
                    {
                        "file_path": "packages/web/src/core/high_churn.ts",
                        "is_hotspot": True,
                        "churn_percentile": 0.95,
                        "commit_count_90d": 7,
                    },
                ],
            )

            health = await get_decision_health_summary(session, repo_id)

        self.assertEqual(
            health["ungoverned_hotspots"],
            ["packages/web/src/core/high_churn.ts"],
        )


if __name__ == "__main__":
    unittest.main()
