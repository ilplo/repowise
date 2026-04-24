from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repowise.cli.helpers import _load_repo_settings_async, _load_repo_state_async
from repowise.cli.main import cli
from repowise.core.persistence import create_engine, create_session_factory, get_session, init_db
from repowise.core.persistence.crud import get_generation_job, upsert_generation_job, upsert_repository
from repowise.core.persistence.models import Page
from repowise.core.persistence.page_ids import make_storage_page_id
from repowise.server.routers.repos import create_repo, full_resync, list_repos, sync_repo
from repowise.server.schemas import RepoCreate
from repowise.server.job_executor import execute_job


class CentralRepoPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(self._cleanup_tempdir)

        self.root = Path(self._tmpdir.name)
        self.app_root = self.root / "repowise-app"
        self.app_root.mkdir(parents=True)
        self.repo_path = self.root / "target-repo"
        (self.repo_path / ".git").mkdir(parents=True)

        self.env_patch = patch.dict(os.environ, {"REPOWISE_APP_ROOT": str(self.app_root)}, clear=False)
        self.env_patch.start()
        self.addAsyncCleanup(self._stop_env_patch)

        self.engine = create_engine("sqlite+aiosqlite:///:memory:", use_static_pool=True)
        await init_db(self.engine)
        self.session_factory = create_session_factory(self.engine)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()

    async def _cleanup_tempdir(self) -> None:
        self._tmpdir.cleanup()

    async def _stop_env_patch(self) -> None:
        self.env_patch.stop()

    async def test_create_repo_normalizes_path_and_persists_across_sessions(self) -> None:
        raw_path = str(self.repo_path / ".")

        async with get_session(self.session_factory) as session:
            created = await create_repo(RepoCreate(name="target", local_path=raw_path), session=session)

        self.assertEqual(created.local_path, str(self.repo_path.resolve()))

        async with get_session(self.session_factory) as session:
            repos = await list_repos(session=session)

        self.assertEqual(len(repos), 1)
        self.assertEqual(repos[0].id, created.id)
        self.assertEqual(repos[0].local_path, str(self.repo_path.resolve()))

    async def test_create_repo_rejects_missing_target_path(self) -> None:
        missing = self.root / "does-not-exist"

        async with get_session(self.session_factory) as session:
            with self.assertRaises(HTTPException) as ctx:
                await create_repo(RepoCreate(name="missing", local_path=str(missing)), session=session)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("does not exist", str(ctx.exception.detail))

    async def test_sync_repo_rejects_deleted_target_path(self) -> None:
        async with get_session(self.session_factory) as session:
            created = await create_repo(
                RepoCreate(name="target", local_path=str(self.repo_path)),
                session=session,
            )

        shutil.rmtree(self.repo_path)

        async with get_session(self.session_factory) as session:
            with self.assertRaises(HTTPException) as ctx:
                await sync_repo(created.id, request=types.SimpleNamespace(), session=session)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("does not exist", str(ctx.exception.detail))

    async def test_sync_repo_returns_job_contract_with_id(self) -> None:
        async with get_session(self.session_factory) as session:
            created = await create_repo(
                RepoCreate(name="target", local_path=str(self.repo_path)),
                session=session,
            )

        request = types.SimpleNamespace()
        with patch("repowise.server.routers.repos._launch_job_task") as launch:
            async with get_session(self.session_factory) as session:
                job = await sync_repo(created.id, request=request, session=session)

        self.assertEqual(job.repository_id, created.id)
        self.assertEqual(job.status, "pending")
        self.assertTrue(job.id)
        launch.assert_called_once_with(request, job.id)

    async def test_full_resync_rejects_missing_provider_before_creating_job(self) -> None:
        async with get_session(self.session_factory) as session:
            created = await create_repo(
                RepoCreate(name="target", local_path=str(self.repo_path)),
                session=session,
            )

        request = types.SimpleNamespace()
        with patch(
            "repowise.server.provider_config.get_chat_provider_instance",
            side_effect=ValueError("No active provider configured. Set an API key first."),
        ):
            async with get_session(self.session_factory) as session:
                with self.assertRaises(HTTPException) as ctx:
                    await full_resync(created.id, request=request, session=session)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("No active provider configured", str(ctx.exception.detail))

        async with get_session(self.session_factory) as session:
            from sqlalchemy import func, select

            from repowise.core.persistence.models import GenerationJob

            count = await session.scalar(
                select(func.count()).select_from(GenerationJob).where(GenerationJob.repository_id == created.id)
            )

        self.assertEqual(count, 0)

    async def test_full_resync_job_fails_if_provider_disappears_before_execution(self) -> None:
        async with get_session(self.session_factory) as session:
            repo = await upsert_repository(
                session,
                name="target",
                local_path=str(self.repo_path),
            )
            job = await upsert_generation_job(
                session,
                repository_id=repo.id,
                status="pending",
                config={"mode": "full_resync"},
            )

        app_state = types.SimpleNamespace(
            session_factory=self.session_factory,
            fts=None,
            vector_store=None,
        )

        with patch(
            "repowise.server.provider_config.get_chat_provider_instance",
            side_effect=ValueError("No active provider configured. Set an API key first."),
        ):
            with patch("repowise.server.job_executor.run_pipeline") as run_pipeline:
                with patch("repowise.server.job_executor.logger"):
                    await execute_job(job.id, app_state)

        run_pipeline.assert_not_called()
        async with get_session(self.session_factory) as session:
            stored = await get_generation_job(session, job.id)

        self.assertIsNotNone(stored)
        self.assertEqual(stored.status, "failed")
        self.assertIn("Full re-index requires an active provider", stored.error_message or "")

    async def test_load_config_and_state_ignore_repo_local_legacy_files(self) -> None:
        legacy_dir = self.repo_path / ".repowise"
        legacy_dir.mkdir(parents=True)
        (legacy_dir / "config.yaml").write_text("provider: gemini\nmodel: legacy\n", encoding="utf-8")
        (legacy_dir / "state.json").write_text('{"last_sync_commit":"abc123"}', encoding="utf-8")

        self.assertEqual(await _load_repo_settings_async(self.repo_path), {})
        self.assertEqual(await _load_repo_state_async(self.repo_path), {})

class DoctorCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

        self.root = Path(self._tmpdir.name)
        self.app_root = self.root / "repowise-app"
        self.app_root.mkdir(parents=True)
        self.repo_path = self.root / "target-repo"
        (self.repo_path / ".git").mkdir(parents=True)

        self.env_patch = patch.dict(os.environ, {"REPOWISE_APP_ROOT": str(self.app_root)}, clear=False)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_doctor_reads_repository_data_from_central_db(self) -> None:
        async def _seed() -> None:
            (self.app_root / ".repowise").mkdir(parents=True, exist_ok=True)
            url = f"sqlite+aiosqlite:///{(self.app_root / '.repowise' / 'wiki.db').as_posix()}"
            engine = create_engine(url)
            await init_db(engine)
            session_factory = create_session_factory(engine)
            try:
                async with get_session(session_factory) as session:
                    repo = await upsert_repository(
                        session,
                        name="target",
                        local_path=str(self.repo_path.resolve()),
                    )
                    session.add(
                        Page(
                            id=make_storage_page_id(repo.id, "overview:README.md"),
                            repository_id=repo.id,
                            page_type="overview",
                            title="README",
                            content="hello",
                            target_path="README.md",
                            source_hash="hash",
                            model_name="grok-4-1-fast-reasoning",
                            provider_name="xai",
                            created_at=repo.created_at,
                            updated_at=repo.updated_at,
                        )
                    )
            finally:
                await engine.dispose()

        asyncio.run(_seed())

        result = CliRunner().invoke(cli, ["doctor", str(self.repo_path)])

        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("wiki.db not found", result.output)
        self.assertIn("1 pages", result.output)


if __name__ == "__main__":
    unittest.main()
