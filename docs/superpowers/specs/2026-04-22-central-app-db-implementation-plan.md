# Repowise Central App DB Implementation Plan

Date: 2026-04-22
Input design: [2026-04-22-central-app-db-design.md](/Users/ilya/Documents/GitHub/repowise/docs/superpowers/specs/2026-04-22-central-app-db-design.md)
Status: Draft

## Summary

Implement a central-data-only Repowise runtime where:

- every `repowise` CLI command starts under the Repowise repo `.venv`
- the Repowise repo-local built-in DB is the only source of truth
- followed repositories are persisted centrally and restored on startup
- analysis, generation, sync state, and history are keyed by central `repository_id`
- target-repo-local `.repowise` state is no longer used for steady-state operation

Recommended release shape:

- MVP:
  - runtime bootstrap and DB path unification
  - central repository CRUD and startup restore
  - command-path migration away from repo-local config/state/db ownership
  - end-to-end persistence proof via UI add repo, sync repo, restart server
- Hardening:
  - import of legacy target-local DBs and config/state
  - stronger repository health metadata
  - operator tooling and cleanup/deprecation warnings

Critical path:

1. unify runtime bootstrap and central DB path
2. make command and server persistence paths central-only
3. prove UI repository restore and sync persistence against the central DB
4. add legacy import without reintroducing dual-write behavior

## Assumptions

- Repowise is launched from its own source repository checkout.
- The intended central DB location is `<repowise-repo>/.repowise/wiki.db`.
- Existing central tables remain the durable schema foundation; no separate “workspace DB” is introduced.
- The current `repositories` table remains the primary aggregate for followed repositories.
- Per-repo local `.repowise` directories may still exist temporarily during migration, but steady-state code must not depend on them.
- There is no requirement to preserve background job execution across process restarts beyond persisted job status/history.

## Workstreams

### 1. Runtime Bootstrap

Scope:
- enforce `.venv` runtime for all CLI commands
- centralize runtime DB path resolution
- remove repo-path-derived DB location from normal runtime

Deliverables:
- shared CLI runtime guard
- shared central DB path resolver
- tests covering stale interpreter re-exec and central DB path selection

Dependencies:
- none

Risks:
- accidental recursion or broken re-exec
- mixed behavior between CLI and server imports

Definition of done:
- `init`, `start`, `mcp`, `status`, `update`, and `watch` all execute under `.venv` when started from the checkout
- default DB path no longer changes based on target repo path in steady-state mode

### 2. Data and Schema

Scope:
- make the existing schema authoritative for repository registration and derived repo state
- add missing normalized repository sync metadata where needed
- prepare one-way import from legacy target-local DB/state

Deliverables:
- repository metadata schema changes if needed
- migration/import metadata tracking
- indexes and uniqueness verification

Dependencies:
- runtime bootstrap workstream for central DB ownership

Risks:
- duplicate repository rows by path normalization differences
- incomplete mapping of repo-local config/state into central fields

Definition of done:
- central schema can represent followed repos, sync metadata, and legacy import state without target-local files

### 3. Backend Command and Service Refactor

Scope:
- refactor CLI helpers and server services away from target-local `.repowise`
- move config/state ownership into central DB-backed records
- ensure sync jobs read target repo source but persist only centrally

Deliverables:
- updated DB resolution helpers
- updated CLI init/update/status/start flows
- updated background execution and repo CRUD behavior

Dependencies:
- runtime bootstrap
- schema decisions for central settings/sync metadata

Risks:
- hidden path-first assumptions in pipeline, helpers, and server job execution
- commands that still expect target-local state side effects

Definition of done:
- command and server behavior are repo-record-first, not target-path-state-first

### 4. Frontend and UX

Scope:
- make repo add/list/restart behavior visibly central and persistent
- ensure UI reflects repository history after restart
- remove UX assumptions about per-repo local bootstrap

Deliverables:
- UI add/list/reload flows validated against central DB
- restart persistence proof
- error states for missing/deleted target repo paths

Dependencies:
- backend repo registry and central persistence

Risks:
- stale optimistic UI assumptions
- missing surfaced metadata for health and sync state

Definition of done:
- UI can add a repo, show it after restart, and continue to show historical data

### 5. Migration and Compatibility

Scope:
- import legacy target-local DBs/config/state into the central DB
- avoid dual-write or fallback read behavior after cutover
- provide operator-safe deprecation messages

Deliverables:
- importer for legacy `.repowise/wiki.db`
- importer for repo-local state/config metadata if still needed
- migration marker and idempotency logic

Dependencies:
- central schema and refactored persistence paths

Risks:
- partial import creates confusing duplicates
- operators depend on old repo-local files for manual inspection

Definition of done:
- repeated import is idempotent
- steady-state runtime does not read target-local state except through the importer

### 6. Observability, QA, and Documentation

Scope:
- verification for restart persistence and sync continuity
- migration diagnostics
- updated operator and developer docs

Deliverables:
- integration tests
- logging for import, sync, and missing-path conditions
- documentation updates

Dependencies:
- backend and frontend slices complete enough for end-to-end verification

Risks:
- false confidence from unit-only validation

Definition of done:
- restart persistence is covered by automated tests and documented for operators

## Phase Plan

### Phase 1: Clarification and Finalization

Objective:
- finalize central DB path, central settings ownership, and migration contract before broad refactoring

Entry criteria:
- approved architecture package exists

Major tasks:
- confirm `<repowise-repo>/.repowise/wiki.db` as default built-in DB path
- choose where sync metadata lives: normalized repository columns vs `settings_json`
- define exact legacy import surface: DB only vs DB + config/state
- inventory code paths that currently resolve DB/state/config from a target repo

Exit criteria:
- DB path and schema ownership decisions are explicit
- implementation task list can be assigned without re-deriving architecture

Evidence of completion:
- implementation plan approved
- code-path inventory captured in task tracker or implementation notes

### Phase 2: Runtime and Persistence Foundation

Objective:
- make runtime and DB ownership central before changing user-facing flows

Entry criteria:
- Phase 1 decisions locked

Major tasks:
- land `.venv` runtime guard for all CLI commands
- create central DB path resolver for source-checkout mode
- refactor helpers so default DB resolution is central-only
- add tests for runtime selection and DB path resolution

Exit criteria:
- stale interpreter and target-derived DB path issues are removed from steady-state startup

Evidence of completion:
- command tests pass under `.venv`
- central DB path tests pass

### Phase 3: Central Repository Ownership Slice

Objective:
- prove that repository registration, listing, and restart restore work entirely from the central DB

Entry criteria:
- Phase 2 foundation complete

Major tasks:
- refactor repository CRUD flows to rely only on central persistence
- move repo settings ownership from repo-local config to DB-backed repository state
- ensure `/api/repos` returns persisted repo records after restart
- add restart persistence integration test

Exit criteria:
- repo add/list/restart flow works with no target-local state dependency

Evidence of completion:
- add repo via API/UI, restart server, repo still visible

### Phase 4: Command and Job Migration

Objective:
- remove target-local `.repowise` state writes from init/update/status/start and background sync paths

Entry criteria:
- repository ownership slice proven

Major tasks:
- refactor `init` persistence and post-run state/config writes into central DB
- refactor `status` to read central DB-backed sync metadata
- refactor server job execution and sync flow to persist central-only
- remove assumptions that target repo must contain `.repowise`

Exit criteria:
- steady-state CLI and server flows no longer create or require target-local `.repowise`

Evidence of completion:
- end-to-end sync and status flows pass without target-local DB/state/config

### Phase 5: Legacy Import and Cutover

Objective:
- support migration from existing target-local state without keeping dual-write behavior

Entry criteria:
- central-only steady-state path is complete

Major tasks:
- implement legacy importer for repo-local DBs
- import or map legacy config/state into central repository settings and sync metadata
- add import idempotency markers and tests
- add deprecation warnings for legacy local-state usage

Exit criteria:
- existing local-state users can migrate into the central DB safely

Evidence of completion:
- importer can run twice without duplication
- migrated repos show prior history through the central UI/API

### Phase 6: Rollout and Hardening

Objective:
- ship safely, validate in real use, and remove residual compatibility risk

Entry criteria:
- phases 2-5 complete

Major tasks:
- perform manual restart persistence and missing-path handling checks
- validate logging and operator diagnostics
- update README/operator docs
- decide on final removal timing for legacy read paths if any temporary compatibility remains

Exit criteria:
- release is safe for daily use

Evidence of completion:
- release checklist signed off
- manual smoke results recorded

## Ordered Task Breakdown

### Task 1. Add central runtime bootstrap guard

Owner:
- backend / CLI

Scope:
- ensure all commands re-exec into `.venv` when launched from the Repowise repo checkout

Dependencies:
- none

Proof:
- unit tests for stale runtime vs already-correct runtime

Parallelization:
- can run in parallel with Task 2 discovery work

### Task 2. Inventory target-local state dependencies

Owner:
- backend

Scope:
- enumerate all code paths reading/writing target-local DB, config, or state

Dependencies:
- none

Proof:
- checklist of affected helpers, commands, and services

Parallelization:
- can run in parallel with Task 1

### Task 3. Replace default DB path resolution with central built-in DB

Owner:
- backend / persistence

Scope:
- change steady-state path resolution to `<repowise-repo>/.repowise/wiki.db`

Dependencies:
- Task 1

Proof:
- DB path contract tests

Critical path:
- yes; every later persistence refactor depends on one authoritative DB path

### Task 4. Define central repository settings and sync metadata storage

Owner:
- backend / data

Scope:
- choose exact shape of repository settings and last-sync metadata

Dependencies:
- Task 2, Task 3

Proof:
- schema/task note and migration stub or implementation

Critical path:
- yes; command and server refactors need a target location for data previously stored in files

### Task 5. Refactor repository CRUD to central-only ownership

Owner:
- backend / API

Scope:
- make repo add/update/list semantics central-only and restart-safe

Dependencies:
- Task 3, Task 4

Proof:
- API tests and manual UI verification

Critical path:
- yes; startup restore and UI persistence depend on it

### Task 6. Add startup restore integration coverage

Owner:
- backend / QA

Scope:
- prove repos remain visible after server restart

Dependencies:
- Task 5

Proof:
- integration test or deterministic service-level test

Parallelization:
- can run alongside Task 7 once Task 5 lands

### Task 7. Refactor `init` away from repo-local state/config writes

Owner:
- backend / CLI

Scope:
- move provider/model/embedder/state persistence into central DB-backed repository state

Dependencies:
- Task 4, Task 5

Proof:
- command tests and end-to-end `init` behavior validation

Critical path:
- yes; `init` is a primary writer and currently owns much of the repo-local state behavior

### Task 8. Refactor `status`, `update`, and `start` to central-only reads/writes

Owner:
- backend / CLI

Scope:
- remove reliance on repo-local config/state and centralize status reads

Dependencies:
- Task 4, Task 5

Proof:
- command tests and manual smoke

Parallelization:
- can run in parallel with Task 7 after Task 5

### Task 9. Refactor background sync/job execution paths

Owner:
- backend / worker

Scope:
- ensure sync/full-resync read target repos but persist only centrally

Dependencies:
- Task 3, Task 4, Task 5

Proof:
- sync job integration tests

Critical path:
- yes; historical continuity after restart depends on worker writes being centralized

### Task 10. Update UI flows for central repository persistence semantics

Owner:
- frontend

Scope:
- ensure add/list/reload/restart behavior reflects central persisted state and missing-path errors

Dependencies:
- Task 5, Task 9

Proof:
- UI smoke and component/integration coverage

Parallelization:
- can run alongside late backend hardening once repository APIs stabilize

### Task 11. Implement legacy importer for target-local DB/state

Owner:
- backend / data migration

Scope:
- one-way import from target-local `.repowise` artifacts into central DB

Dependencies:
- Task 7, Task 8, Task 9

Proof:
- idempotent import tests on fixture data

Critical path:
- yes for release if legacy users must be supported immediately

### Task 12. Add deprecation warnings and operator docs

Owner:
- backend / docs

Scope:
- communicate removal of repo-local state ownership and how import works

Dependencies:
- Task 11

Proof:
- docs merged and warnings visible in expected flows

Parallelization:
- can run in parallel with Task 13

### Task 13. Final verification and release readiness

Owner:
- QA / release

Scope:
- perform end-to-end checks, restart persistence proof, and rollback rehearsal

Dependencies:
- Tasks 6-12

Proof:
- release checklist complete

Critical path:
- yes; this is the final gate

## Dependencies

### Critical Path

The critical path is:

1. Task 1: runtime guard
2. Task 3: central DB path unification
3. Task 4: central settings/sync metadata decision
4. Task 5: central repository CRUD ownership
5. Task 7: `init` migration
6. Task 9: sync/job migration
7. Task 11: legacy import
8. Task 13: final verification

Why this is critical:
- if DB path ownership is not unified early, later refactors can silently persist to the wrong store
- if repository settings/state ownership is not decided, command migration stalls
- if `init` and sync jobs still write repo-local state, restart persistence remains unreliable
- if migration/import is left until the end without dedicated validation, release becomes unsafe for existing users

### Parallel Work

Can run in parallel after foundation tasks:

- Task 2 with Task 1
- Task 6 with Task 7/8 after Task 5
- Task 8 with Task 7 after Task 5
- Task 10 with late backend tasks after APIs stabilize
- Task 12 with Task 13 preparation

Blocked work:

- frontend persistence UX must wait for stable central repo APIs
- importer design must wait until steady-state central-only write paths exist

## Quality Gates

### Gate A: Foundation Review

Applies before Phase 3.

Checks:
- runtime re-exec behavior reviewed
- central DB path tests pass
- no unresolved ambiguity on sync metadata ownership

Evidence:
- code review sign-off
- passing runtime/path tests

### Gate B: Repository Persistence Slice

Applies before command migration broadens.

Checks:
- add/list/restart flow proven against central DB
- API contract reviewed
- no target-local state dependency in repo CRUD path

Evidence:
- integration or service-level restart persistence test
- manual smoke: add repo, restart, list repo

### Gate C: Command and Worker Migration

Applies before importer work begins.

Checks:
- `init`, `status`, `start`, and sync jobs operate central-only in steady-state
- missing target path errors are surfaced cleanly
- no new writes to target-local `.repowise` in tested flows

Evidence:
- command tests
- sync integration test
- grep/code review of target-local write paths

### Gate D: Migration Readiness

Applies before release candidate.

Checks:
- importer is idempotent
- migrated repos preserve historical pages/graph/job visibility
- deprecation warnings are in place

Evidence:
- import fixture tests
- manual migration dry run on sample legacy repo

### Gate E: Release Readiness

Applies before production/daily-use release.

Checks:
- docs updated
- restart persistence smoke passes
- rollback plan rehearsed
- no P0/P1 known data-loss issues

Evidence:
- release checklist complete

## Rollout / Rollback Plan

### Rollout

1. Land runtime guard and central DB path changes behind internal verification.
2. Land central repository CRUD and restart restore slice.
3. Land command and worker migration to central-only steady-state behavior.
4. Enable/import legacy local-state migration path.
5. Release with deprecation notice for repo-local state.

Rollout strategy:
- internal-only first on developer workstations
- verify restart persistence and repo history restoration before broad use

### Rollback

Rollback constraints:
- once import copies local-state data into the central DB, rollback must avoid duplicating or corrupting data

Rollback actions:
- if runtime/bootstrap changes fail, revert to prior CLI bootstrap
- if central-only steady-state behavior breaks before importer rollout, revert command-path changes and retain existing local-state behavior temporarily
- if importer has issues after import begins, disable importer entrypoint and keep already imported data intact; use forward-fix rather than attempting destructive reverse migration

Forward-fix rule:
- imported central data should not be deleted automatically during rollback

## Risks and Mitigations

### Risk 1: Hidden target-local assumptions remain

Early warning:
- commands still create `.repowise` directories under target repos

Mitigation:
- explicit inventory and grep-based verification
- targeted tests for commands most likely to regress

### Risk 2: Repository identity drift from path normalization

Early warning:
- duplicate rows for the same repo path under symlink or case variation

Mitigation:
- normalize and resolve `local_path` before persistence
- add or verify unique constraint behavior on normalized path

### Risk 3: Import duplicates historical records

Early warning:
- rerunning import changes counts unexpectedly

Mitigation:
- import keyed by natural keys and repository path
- dedicated idempotency fixtures

### Risk 4: Status UX degrades when target repo path disappears

Early warning:
- sync/status calls fail with opaque errors

Mitigation:
- explicit missing-path repository health state
- UI-visible error messaging

### Risk 5: Schedule slips in migration phase

Early warning:
- command migration tasks uncover more path-first assumptions than expected

Mitigation:
- prove thin vertical slices early
- keep importer after steady-state refactor, not before

## Definition of Done Per Milestone

### Milestone 1: Runtime Foundation Done

- all CLI commands run under the checkout `.venv`
- central DB path is authoritative in steady-state
- runtime/path tests pass

### Milestone 2: Central Repository Persistence Done

- repo add/list/update/restart restore work from the central DB
- UI shows persisted repos after restart
- no repo CRUD dependence on target-local `.repowise`

### Milestone 3: Central-Only Command and Worker Flow Done

- `init`, `status`, `start`, `update`, and sync jobs do not require or write target-local state
- historical pages/graph/jobs persist across restart
- end-to-end sync smoke passes

### Milestone 4: Legacy Migration Done

- importer moves legacy target-local data into the central DB
- rerunning import is idempotent
- deprecation messaging is visible

### Milestone 5: Release Done

- documentation updated
- rollout and rollback checklist completed
- no known blocker on restart persistence, sync continuity, or data integrity
