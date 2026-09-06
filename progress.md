# TakeKeeper Progress

## Current status

TakeKeeper now has both an in-memory reference backend and a concrete ClickHouse-backed `ProductionMemory` adapter. The trusted application write path is structurally separate from the future read-only MCP agent path. The live ClickHouse/Gemini integration gate remains unproven because this environment has no reachable ClickHouse service or Google runtime credential.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected repository root, `src/takekeeper/memory.py`, `models.py`, `service.py`, `sql/schema.sql`, `pyproject.toml`, and `README.md`.
- Re-checked current official ClickHouse Python guidance: `clickhouse-connect` is the official Python client and supports `query`, `command`, and bulk `insert`.
- Re-checked upstream client API showing bound `parameters` support for query/command calls.

## Changes made this run

- Added `src/takekeeper/clickhouse_memory.py` implementing the existing `ProductionMemory` contract over an injected ClickHouse client.
- Added parameter-bound, scope-constrained reads and synchronous lightweight deletes before idempotent observation/baseline upserts.
- Added scoped finding replacement with validation before any destructive operation.
- Kept MCP out of the write path: this adapter is explicitly for a separately permissioned trusted application credential.
- Updated `sql/schema.sql` so continuity finding fields that can be unknown are `Nullable`; this preserves `insufficient_evidence` / `missing_baseline` without fake values.
- Added `tests/test_clickhouse_memory.py` with a fake client to verify parameter binding, tenant scope, destructive-operation ordering, nullable evidence persistence, and database identifier validation.
- Exposed `ClickHouseProductionMemory` from the package and added an optional `clickhouse-connect>=1,<2` dependency extra.
- Updated README with installation/use and read-vs-write credential boundaries.

## Validation

- New adapter and test modules were syntax-compiled locally before repository write.
- The fake-client tests are designed to run without credentials or a database.
- A real ClickHouse roundtrip could not be executed here because no ClickHouse service is reachable from this automation environment.

## Decisions locked

1. The official MCP connection stays read-only and is never reused for ingestion/persistence.
2. Trusted application writes target the `ProductionMemory` port through a separately permissioned ClickHouse client.
3. Tenant/scene/take values are bound parameters, never interpolated into SQL.
4. Scope validation happens before findings deletion.
5. Lightweight deletes use `mutations_sync=1` to avoid asynchronous stale-row races during idempotent replacement.
6. Nullable finding columns are required for truthful missing-evidence states.
7. Domain logic remains transport-independent.
8. Runtime MCP/auth/version/latency claims must be measured on a real environment.

## Gates

- **Gate A live integration:** NOT YET PROVEN.
- **Gate B continuity correctness:** CORE + APP SERVICE + CLICKHOUSE ADAPTER IMPLEMENTED; live DB assertion pending.
- **Gate C evidence:** nullable durable evidence contract implemented; UI pending.
- **Gate D editorial retrieval:** SQL implemented; live DB assertion pending.
- **Gate E failure honesty:** domain + persistence representation implemented; MCP outage/empty-result integration pending.
- **Gate F security:** app-layer scoping + parameter binding + read/write credential separation implemented; ClickHouse RBAC runtime proof pending.
- **Gate G multimodal evidence:** not started; governed by `MULTIMODAL_EXTRACTION_AND_EVAL.md`.

## Blockers / unknowns

1. No reachable real ClickHouse service, so schema/seed/adapter roundtrip remains unmeasured.
2. No Gemini/Google runtime credentials, so Gate A cannot be truthfully claimed.
3. Actual ClickHouse version, MCP version, transport/auth, response shape, and latency remain unmeasured.
4. No self-owned demo footage exists yet.

## Highest-priority backlog

- Execute schema + seed against real ClickHouse and run the complete suite against `ClickHouseProductionMemory`.
- Add a real integration-test mode gated by environment variables, with no secrets committed.
- Verify re-analysis removes stale findings and zero-finding replacement works in real ClickHouse.
- Verify editorial SQL returns exactly `S28-T31` and `S28-T47`.
- Start official `mcp-clickhouse` read-only; retrieve one seeded fact via `run_query`.
- Record versions, auth, payload shape, row count, latency, and write-denial proof.
- Build a thin MCP evidence reader around the measured response shape.
- Add outage/empty-result/wrong-production integration tests.
- Then add persisted human decisions, minimal API/UI, and Gemini multimodal extraction.

## Single best next step

**Add an environment-gated real ClickHouse integration harness that applies `sql/schema.sql` + `sql/seed_demo.sql`, runs `TakeAnalysisService` through `ClickHouseProductionMemory`, and asserts the exact Scene 28 re-analysis/idempotency contract when `CLICKHOUSE_*` credentials are available.**

## Sources checked

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
