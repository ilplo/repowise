# Repowise Central App DB Design

Date: 2026-04-22
Status: Proposed
Scope: Replace per-repo local `.repowise` state with a central built-in application database and make the Repowise repo runtime self-bootstrap into `.venv`.

## Executive Summary

Repowise should be run from its own source repository and should always execute under that repository's `.venv`, even if the caller did not activate it first. The application should manage external target repositories as persisted application state in one central built-in database. Followed repositories, sync history, generated pages, graph data, jobs, and UI-visible repo metadata must survive restarts without depending on target-repo-local `.repowise` directories.

Recommended architecture:

- Keep the Repowise repo as the single application runtime root.
- Make the built-in app DB the only source of truth for followed repositories and all derived repo state.
- Remove writes to target-repo-local `.repowise/wiki.db`, `.repowise/state.json`, and `.repowise/config.yaml`.
- Persist per-repo operational settings, sync state, and history under central DB ownership.
- Load registered repositories from the central DB on server startup and surface them immediately in the UI.

This is a behavioral and storage-ownership refactor, not a new feature bolted on top of the existing per-repo layout.

## Facts

- Repowise already has a central SQLAlchemy schema with `repositories`, `wiki_pages`, `wiki_page_versions`, `graph_nodes`, `graph_edges`, `generation_jobs`, and other derived-data tables.
- The current runtime still resolves database location from a target repo path and defaults to `<target>/.repowise/wiki.db`.
- `init`, `update`, `status`, `serve`, and server routes still assume a target repo path is the primary anchor for both runtime and persistence.
- The UI already has repository CRUD and background sync flows under `/api/repos`.

## Assumptions

- Repowise will always be launched from the Repowise source repository checkout, not from a random external directory.
- The central built-in DB can be stored under the Repowise runtime home and is durable across application restarts.
- Target repositories remain accessible on disk by `local_path`, but the app database owns their registration and historical analysis state.
- Existing target-repo-local state does not need to remain a supported steady-state storage model after migration.

## Requirements

### Functional

- All CLI commands must ensure the Repowise repo `.venv` runtime is used before command logic executes.
- The application must persist the set of followed repositories centrally.
- A repository added through the UI must remain visible after restarting Repowise.
- Generated docs, graph data, page versions, git-derived history, decisions, and dead-code findings must remain available after restart.
- Sync and full-resync operations must continue to target a repository record stored in the central DB.
- Repository-specific settings currently written to repo-local config must move into central persistence.

### Non-Functional

- Startup must not depend on scanning target repos to rediscover followed repos.
- The migration must be idempotent and safe to re-run.
- Repository identity must remain stable even if the app restarts mid-job.
- There must be one clear write owner for every persisted record.

## Constraints and Breakpoints

- Current code mixes two persistence models: central tables and target-repo-local DB resolution.
- The current repository primary key model is already central; the main inconsistency is storage location and config/state ownership.
- Existing CLI and server code paths are path-first, not repo-record-first.
- Migration risk is highest where a code path still derives DB URL or state file path from a target repo rather than the central runtime.

Top breakpoints:

- Commands that call `resolve_db_url(repo_path)` and silently switch to target-local DB files.
- `load_state()` and `save_config()` style helpers that read or write target-local files.
- Any background job or sync path that assumes a repo-local `.repowise` directory exists.

## Proposed Architecture

### System Context

- Actor: Developer launching Repowise from the Repowise repo.
- Actor: User interacting with the Repowise web UI.
- External system: Target repositories on local disk.
- External system: LLM providers and embedding providers.
- Data store: Central Repowise app DB.

### Trust Zones

- Client: Browser UI.
- Application: FastAPI server and CLI runtime.
- Worker: Background sync / generation execution.
- Data: Central app DB only.
- External: Target repository filesystem, LLM APIs.

### Ownership Model

- Repowise runtime owns process bootstrapping and environment selection.
- Central app DB owns:
  - followed repository registration
  - repository settings
  - sync/job history
  - generated pages and versions
  - graph nodes/edges
  - git-derived metadata
  - dead-code and decision analysis results
- Target repos own only source code and git history, not Repowise state.

## Module Boundaries

### 1. Runtime Bootstrap

Responsibility:
- ensure `.venv` runtime is active
- resolve the central app DB path
- never derive the primary DB from a target repo path

Must not:
- inspect or create target-repo-local `.repowise` state as part of normal startup

### 2. Repository Registry

Responsibility:
- create, update, list, and delete followed repository records
- persist operational settings per repository
- expose startup-visible repository state to the UI

Primary aggregate:
- `Repository`

### 3. Analysis and Generation Pipeline

Responsibility:
- read target repo source and git history
- write all derived outputs into central tables under `repository_id`

Must not:
- write parallel copies of analysis output into repo-local DB files

### 4. UI and API

Responsibility:
- operate against central repository records
- restore repo list from the central DB on app load
- trigger sync jobs by repository ID

## Domain Model

### Aggregate: Repository

Fields:
- `id`
- `name`
- `url`
- `local_path`
- `default_branch`
- `head_commit`
- `settings_json`
- `created_at`
- `updated_at`

New or formalized settings in `settings_json`:
- provider/model defaults
- embedder selection
- exclude patterns
- commit limit
- follow-renames flag
- UI follow/enabled status if needed

Invariants:
- `local_path` is unique for active repositories.
- All derived records must reference a valid `repository_id`.
- Deleting a repository cascades all derived central records.

### Aggregate: Repository Sync State

Recommendation:
- keep job execution history in `generation_jobs`
- add explicit last-sync metadata either:
  - as normalized columns on `repositories`, or
  - in `settings_json` only as a transitional step

Preferred normalized fields on `repositories` in a follow-up migration:
- `status`
- `last_indexed_at`
- `last_synced_commit`
- `last_sync_error`

## Persistence Design

### Source of Truth

Single source of truth:
- central built-in DB only

Removed ownership:
- `<target>/.repowise/wiki.db`
- `<target>/.repowise/state.json`
- `<target>/.repowise/config.yaml`

### Central DB Path

Recommended default:
- `<repowise-repo>/.repowise/wiki.db` for local-dev source checkout mode

Rationale:
- keeps application runtime and data colocated with the application repo
- matches the user's mental model that Repowise is started from its own repo
- avoids hidden writes into arbitrary target repos

Alternative acceptable runtime root:
- `~/.repowise/wiki.db`

But for this requested mode, the Repowise repo-local DB is the better fit because the app is always launched from its own repo.

### Migration Rules

At startup or via explicit migration command:

1. Open the central DB.
2. Detect any existing target-repo-local DBs only for import, not normal runtime.
3. For each imported repo-local DB:
   - upsert `repositories` record by `local_path`
   - copy pages, page versions, graph, job history, and related derived records
   - merge by natural keys where possible
4. Mark migration completion in central metadata.
5. Stop reading target-local state for normal operation.

Idempotency:
- keyed by repository `local_path`
- page natural IDs and graph uniqueness constraints prevent duplication

### Indexing and Constraints

Keep and rely on:
- unique repository `local_path`
- page natural primary key
- graph node and graph edge uniqueness constraints

Add or verify:
- unique index on `repositories.local_path`
- fast lookup indexes on `generation_jobs.repository_id` and `wiki_pages.repository_id`

## Contracts

### Create Repository

Request:

```json
{
  "name": "my-repo",
  "local_path": "/abs/path/to/my-repo",
  "url": "git@github.com:org/my-repo.git",
  "default_branch": "main",
  "settings": {
    "provider": "xai",
    "model": "grok-4-1-fast-reasoning"
  }
}
```

Response:

```json
{
  "id": "repo_123",
  "name": "my-repo",
  "local_path": "/abs/path/to/my-repo",
  "url": "git@github.com:org/my-repo.git",
  "default_branch": "main",
  "head_commit": null,
  "settings": {
    "provider": "xai",
    "model": "grok-4-1-fast-reasoning"
  }
}
```

Rules:
- idempotent by `local_path`
- path must exist and be a git repo before follow is accepted

### Startup Restore

Flow:
- server starts
- central DB initializes
- UI requests `/api/repos`
- server returns persisted repositories ordered by recent activity

### Sync Job

Request:
- `POST /api/repos/{repo_id}/sync`

Rules:
- only one active job per repository
- all outputs written under that `repository_id`
- failure does not drop historical records unless explicit full reset is requested

## DFD

```text
Trust Zone: Client
  E1 Browser UI

Trust Zone: Application
  P1 CLI Bootstrap
  P2 FastAPI Server
  P3 Repository Registry

Trust Zone: Worker
  P4 Sync / Generation Worker

Trust Zone: Data
  D1 Central App DB

Trust Zone: External
  E2 Target Repository Filesystem
  E3 Git Metadata / Local Git CLI
  E4 LLM / Embedding Providers

Flows:
  E1 -> P2 : API requests (list repos, add repo, sync repo)
  P1 -> D1 : init DB, load runtime metadata
  P2 -> P3 : repository CRUD commands
  P3 -> D1 : persist repository records and settings
  P2 -> P4 : enqueue or launch sync job by repository_id
  P4 -> E2 : read source tree
  P4 -> E3 : read commit history
  P4 -> E4 : generate docs / embeddings
  P4 -> D1 : persist all derived repo state
  P2 -> D1 : serve repos, pages, jobs, graph, history
```

## Sequence Diagrams

### 1. CLI Startup With `.venv` Re-exec

```text
User -> CLI entrypoint: repowise serve
CLI entrypoint -> Runtime Bootstrap: inspect cwd and current interpreter
Runtime Bootstrap -> Runtime Bootstrap: locate repo checkout and .venv
alt stale interpreter
  Runtime Bootstrap -> OS: exec .venv/bin/python -m repowise.cli.main serve ...
else already correct
  Runtime Bootstrap -> CLI entrypoint: continue
end
CLI entrypoint -> FastAPI Server: start
```

### 2. Add Followed Repository From UI

```text
Browser UI -> API /api/repos: POST create repository
API -> Repository Registry: validate path and upsert by local_path
Repository Registry -> Central DB: write repository row
Central DB -> Repository Registry: repository_id
Repository Registry -> API: RepoResponse
API -> Browser UI: persisted repository card
```

### 3. Restart and Restore State

```text
User -> CLI entrypoint: repowise serve
CLI entrypoint -> FastAPI Server: start under .venv
FastAPI Server -> Central DB: initialize schema and connect
Browser UI -> API /api/repos: GET
API -> Central DB: list repositories
Central DB -> API: persisted repo rows
API -> Browser UI: repositories with existing stats/history
```

### 4. Sync Repository

```text
Browser UI -> API /api/repos/{id}/sync: POST
API -> Central DB: create generation_job if none active
API -> Worker: launch execute_job(repository_id, job_id)
Worker -> Target Filesystem: read current source
Worker -> Git: read history
Worker -> LLM providers: generate content if needed
Worker -> Central DB: upsert pages, graph, metadata, job status
Worker -> Central DB: mark completion or error
Browser UI -> API jobs/status: poll
API -> Browser UI: current progress
```

## ADRs

### ADR-001: Central App DB Is the Only Source of Truth

Decision:
- store all repository registration and analysis outputs only in the central built-in DB

Why:
- restart-safe state restoration
- no hidden writes into target repos
- consistent UI and server behavior

Rejected:
- keeping target-local DBs as first-class storage

### ADR-002: Runtime Is Anchored to the Repowise Repo Checkout

Decision:
- all CLI commands must ensure execution under the checkout `.venv`

Why:
- avoids stale site-packages behavior
- keeps app/runtime and app/database aligned

### ADR-003: Target Repos Are Inputs, Not State Owners

Decision:
- target repos contribute source and git history only

Why:
- avoids split-brain persistence
- makes repository follow state a durable application concept

## Risks and Trade-Offs

### Risks

- Migrating existing repo-local data may surface duplicate or stale records.
- Operators may move or delete target repos after they are registered centrally.
- Some current commands may still assume target-local config/state files and need systematic cleanup.

### Trade-Offs

- Central ownership simplifies startup and restore but requires a broader migration than a small local fix.
- Removing repo-local state reduces portability of a single target repo’s derived data in isolation.
- The app becomes more intentionally “workspace manager” than “run-in-any-repo scratch tool”.

## Failure Modes and Recovery

- Missing target path at sync time:
  - mark repository unhealthy
  - keep historical records
  - show actionable error in UI

- Migration interrupted:
  - rerun import idempotently by repository `local_path`

- Duplicate repo registration attempts:
  - upsert existing repository by `local_path`

- Background job crash:
  - persist job error state
  - do not delete already-persisted history

## Rollout Plan

### Slice 1
- Runtime bootstrap always re-execs into `.venv`
- Central DB path fixed to the Repowise runtime repo

### Slice 2
- Repository CRUD and startup restore use only central DB
- UI add/list flows fully persistent

### Slice 3
- `init`, `update`, `status`, `serve`, and job execution stop reading/writing target-local state files

### Slice 4
- One-time migration/import from target-local DBs if present
- Deprecation warnings for old repo-local layout

## Proof Points

- Add a repo in the UI, restart `repowise serve`, confirm the repo still appears.
- Run sync, restart the server, confirm pages/graph/history remain available.
- Start `repowise init` or `repowise serve` from the Repowise checkout without activating the shell venv and confirm the process re-execs into `.venv`.

## Recommended Next Step

Write an implementation plan that breaks this into:

1. runtime bootstrap and DB path unification
2. central repository/state ownership
3. command-path migration away from repo-local files
4. import/migration of legacy local state
