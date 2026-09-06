# TakeKeeper Progress

## Current status

TakeKeeper now has an executable continuity core plus an application-service/persistence boundary that can run entirely in memory for deterministic development and later be backed by ClickHouse. The core no longer stops at pure comparison functions: observations can now be ingested through a scoped service, compared against approved baselines, and persisted as replaceable findings.

The highest-value unresolved milestone remains the live integration proof: **real Gemini/ADK → official `ClickHouse/mcp-clickhouse` → real ClickHouse**. This run made concrete progress on the unblocked application layer without fabricating that live claim.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected the repository root and the executable `src/takekeeper` package.
- Re-read `models.py`, `continuity.py`, `queries.py`, `fixtures.py`, `README.md`, and the current tests.
- Confirmed the existing design intentionally keeps domain logic transport-independent and reserves MCP for the analytical read path.

## Changes made this run

- Added `src/takekeeper/memory.py` with a `ProductionMemory` protocol and deterministic `InMemoryProductionMemory` reference implementation.
- Added idempotent observation/baseline upserts and scoped finding replacement semantics keyed by production, scene, take, entity, and property.
- Added `src/takekeeper/service.py` with `TakeAnalysisService`, which validates requested tenant/take scope before ingesting observations, loads approved baselines, executes continuity comparison, and persists current findings.
- Added `tests/test_pipeline.py` covering end-to-end persistence, stale-finding replacement on re-analysis, and rejection of cross-production ingestion.
- Updated package exports so the service and memory abstractions are public implementation primitives.

## Validation

A local reconstruction of the new stdlib-only modules was executed before committing the repository update:

```text
test_end_to_end ... ok
test_idempotent_reanalysis_replaces_findings ... ok
test_scope_isolation ... ok

Ran 3 tests
OK
```

The repository's previous deterministic suite had 6 passing tests; this run adds 3 pipeline tests. A full cloned-repository run was not possible from the automation container because outbound GitHub DNS/network access is unavailable there, so the new modules were validated in isolation against the same domain model/continuity logic.

## Decisions locked

1. Domain logic stays transport-independent and testable without credentials.
2. Application orchestration targets a `ProductionMemory` port rather than ClickHouse client calls directly.
3. The in-memory implementation is a deterministic reference backend, not a production substitute.
4. Every ingest/analyze request is explicitly scoped by `production_id`, `scene_id`, and `take_id`; cross-production observations are rejected before persistence.
5. Findings are replaced per take on re-analysis so stale continuity warnings cannot survive a corrected extraction.
6. ClickHouse remains durable production memory; media stays in object storage.
7. Official ClickHouse MCP remains the read-only agent path; ingestion/human decisions use a separately permissioned write path.
8. Missing evidence never becomes inferred absence.
9. Runtime MCP/auth/version details must be measured, not guessed.

## Gates

- **Gate A live integration:** NOT YET PROVEN.
- **Gate B continuity correctness:** CORE + APPLICATION SERVICE IMPLEMENTED; live DB path pending.
- **Gate C evidence:** CORE MODEL + persisted service contract implemented; UI path pending.
- **Gate D editorial retrieval:** SQL IMPLEMENTED; live DB assertion pending.
- **Gate E failure honesty:** missing-evidence and tenant-scope behavior tested; MCP outage/empty-result integration pending.
- **Gate F security:** scope boundary now enforced in application service; runtime ClickHouse/RBAC verification pending.
- **Gate G multimodal evidence:** not started; governed by `MULTIMODAL_EXTRACTION_AND_EVAL.md`.

## Blockers / unknowns

1. No real ClickHouse service is reachable from this automation environment, so schema/seed SQL still cannot be executed against ClickHouse here.
2. No Gemini/Google runtime credentials are available here, so Gate A cannot be truthfully claimed.
3. Actual ClickHouse version, MCP version/commit, transport/auth, payload shape, and latency remain unmeasured.
4. No self-owned demo footage exists yet; structured fixture work intentionally comes first.

## Highest-priority backlog

- Implement a ClickHouse-backed `ProductionMemory` adapter over a separately permissioned application write connection, preserving the exact protocol semantics now tested in memory.
- Add parameterized persistence/query tests around that adapter without weakening tenant scope.
- Run `sql/schema.sql` and `sql/seed_demo.sql` against a real ClickHouse instance.
- Verify editorial SQL returns exactly `S28-T31` and `S28-T47`.
- Start official `mcp-clickhouse` read-only and connect a real Gemini/ADK client.
- Retrieve one seeded fact through `run_query` and record versions/transport/auth/tool/rows/latency/read-only proof.
- Add a thin MCP evidence-reader adapter around the measured client API.
- Add outage, empty-result, wrong-production-scope, and exact Scene 28 integration tests.
- Then add persisted human decisions, minimal API/UI, and eventually Gemini multimodal extraction.

## Single best next step

**Implement the real ClickHouse-backed `ProductionMemory` adapter with parameterized writes/reads and the same tenant/idempotency semantics as the tested in-memory reference, while keeping the official MCP path read-only and separate.**

That is the most useful unblocked implementation work before a real ClickHouse/Gemini environment is available; once a service is reachable, run the schema/seed and Gate A proof immediately.

## Sources checked

- https://github.com/ClickHouse/mcp-clickhouse
- https://clickhouse.com/blog/the-agentic-data-stack
- https://clickhouse.com/blog/10-best-practice-tips
- https://ai.google.dev/gemini-api/docs/video-understanding
