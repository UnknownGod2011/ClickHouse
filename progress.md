# TakeKeeper Progress

## Current status

TakeKeeper now has an in-memory reference backend, a concrete ClickHouse-backed `ProductionMemory` adapter, and an environment-gated real ClickHouse acceptance harness. The trusted application write path remains structurally separate from the future read-only MCP agent path. The live ClickHouse/Gemini integration gate is still unproven in this automation environment because there is no reachable ClickHouse service or Google runtime credential.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected the repository root and current implementation under `src/takekeeper/`.
- Inspected `clickhouse_memory.py`, `service.py`, `fixtures.py`, `queries.py`, `sql/schema.sql`, `sql/seed_demo.sql`, `tests/test_clickhouse_memory.py`, `tests/test_pipeline.py`, `tests/test_queries.py`, `pyproject.toml`, and `README.md`.
- Confirmed the deterministic Scene 28 seed contract: `S28-T47` has 6 seeded observations; three are continuity-relevant; expected continuity outcome is mug mismatch + jacket mismatch + low-confidence lamp `needs_confirmation`; expected editorial retrieval is exactly `S28-T31` and `S28-T47`.

## Changes made this run

- Added `tests/test_clickhouse_integration.py`, an opt-in real-database acceptance harness guarded by `TAKEKEEPER_CLICKHOUSE_INTEGRATION=1`.
- The harness uses the official `clickhouse-connect` client, creates a uniquely named disposable `takekeeper_it_<suffix>` database, rewrites the checked-in schema + seed to that isolated database, runs acceptance assertions, and drops the database in teardown.
- Added real-DB assertions for:
  - three active Scene 28 baselines;
  - six seeded `S28-T47` observations;
  - exact editorial retrieval (`S28-T31`, `S28-T47`);
  - exact continuity statuses for the hero take;
  - persistence of those findings through `ClickHouseProductionMemory`;
  - stale-finding removal after a corrected re-analysis produces zero findings.
- Extended `continuity_evidence_sql` and `editorial_retrieval_sql` with a validated optional `database=` parameter so acceptance tests and real deployments do not have to hard-code the `takekeeper` database.
- Added unit coverage for alternate safe database names and rejection of unsafe database identifiers.
- Updated `README.md` with exact integration-test environment variables, local/Cloud connection notes, disposable-database safety warning, and the revised next milestone.
- No GitHub Actions or CI workflows were added.

## Validation

- Attempted to clone the updated public repository into the execution container to run the full suite, but the container cannot resolve `github.com`; the clone failed before tests could execute.
- Therefore no new test run is claimed as passing from this environment.
- The integration suite is intentionally skipped unless explicitly enabled, so normal unit-test discovery remains credential-free by design.
- Real ClickHouse execution remains pending and must be measured on a host with network access to a ClickHouse instance.

## Decisions locked

1. The official MCP connection stays read-only and is never reused for ingestion/persistence.
2. Trusted application writes target the `ProductionMemory` port through a separately permissioned ClickHouse client.
3. Tenant/scene/take values are bound parameters, never interpolated into trusted persistence SQL.
4. Dynamic database identifiers are validated to letters, digits, and underscores before interpolation.
5. Scope validation happens before findings deletion.
6. Lightweight deletes use `mutations_sync=1` to avoid asynchronous stale-row races during idempotent replacement.
7. Nullable finding columns preserve truthful `insufficient_evidence` / `missing_baseline` states.
8. The real integration harness never touches the configured production database: it creates and removes a unique disposable database instead.
9. Integration tests remain opt-in to prevent accidental database creation/deletion with ordinary test commands.
10. Runtime MCP/auth/version/latency claims must be measured on a real environment.

## Gates

- **Gate A live integration:** NOT YET PROVEN.
- **Gate B continuity correctness:** CORE + APP SERVICE + CLICKHOUSE ADAPTER + REAL-DB HARNESS IMPLEMENTED; live execution pending.
- **Gate C evidence:** nullable durable evidence contract implemented; UI pending.
- **Gate D editorial retrieval:** SQL + exact real-DB acceptance assertion implemented; live execution pending.
- **Gate E failure honesty:** domain + persistence representation implemented; MCP outage/empty-result integration pending.
- **Gate F security:** app-layer scoping + parameter binding + database identifier validation + read/write credential separation implemented; ClickHouse RBAC runtime proof pending.
- **Gate G multimodal evidence:** not started; governed by `MULTIMODAL_EXTRACTION_AND_EVAL.md`.

## Blockers / unknowns

1. No reachable real ClickHouse service from this automation environment, so the new acceptance harness cannot be executed here.
2. No Gemini/Google runtime credentials, so Gemini/ADK orchestration cannot be truthfully demonstrated.
3. Actual ClickHouse server version, `clickhouse-connect` version, official MCP version, transport/auth, response shape, and latency remain unmeasured.
4. No self-owned demo footage exists yet.
5. The current execution container cannot resolve `github.com`, so repository tests cannot be pulled and run locally from this automation environment.

## Highest-priority backlog

- Execute `tests/test_clickhouse_integration.py` against an authorized local or ClickHouse Cloud instance and fix any version-specific DDL/client behavior.
- Record server/client versions plus setup, schema/seed, analysis, editorial-query, and teardown timings.
- Verify the temporary-database teardown succeeds after both passing and failing assertions.
- Start official `mcp-clickhouse` read-only against the seeded database; retrieve one seeded fact via `run_query`.
- Record MCP version, transport, auth, payload shape, row count, latency, and explicit write-denial proof.
- Build a thin MCP evidence reader around the measured `run_query` response shape.
- Add MCP outage, empty-result, malformed-result, and wrong-production tests.
- Add persisted human decisions and evidence-review API/UI.
- Implement the governed Gemini multimodal extraction adapter with fixture-first evaluation before real footage.

## Single best next step

**Run the new opt-in `tests/test_clickhouse_integration.py` on a real authorized ClickHouse instance, fix any concrete incompatibility, and capture server/client versions plus the exact Scene 28 and editorial-query results; then the next run can wire official read-only `mcp-clickhouse` to a response shape that has actually been measured.**

## Sources / implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
