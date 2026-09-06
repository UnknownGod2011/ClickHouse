# TakeKeeper Progress

## Current status

TakeKeeper now has the deterministic continuity core, in-memory and ClickHouse-backed `ProductionMemory` adapters, an environment-gated real ClickHouse acceptance harness, and a bounded fail-closed `McpEvidenceReader` for the official `ClickHouse/mcp-clickhouse` `run_query` tool. The trusted write path remains structurally separate from the read-only agent/MCP path. Live ClickHouse + MCP + Gemini execution is still unproven in this environment because no real ClickHouse service or Google runtime credential is reachable here.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected the repository tree and current `src/takekeeper/` implementation, especially `queries.py`, `models.py`, package exports, `tests/test_queries.py`, `tests/test_clickhouse_integration.py`, `pyproject.toml`, and `README.md`.
- Re-checked the current official `ClickHouse/mcp-clickhouse` repository. Its exposed ClickHouse tools remain `run_query`, `list_databases`, and `list_tables`.
- Confirmed upstream `run_query` is read-only by default when `CLICKHOUSE_ALLOW_WRITE_ACCESS=false`.
- Confirmed the upstream release/changelog path fixed successful tool responses to return valid JSON strings, so the TakeKeeper adapter treats JSON text as the primary observed compatibility shape while also accepting standard MCP text-content envelopes.

## Changes made this run

- Added `src/takekeeper/mcp_reader.py` with a bounded `McpEvidenceReader` that never accepts arbitrary agent SQL. It only calls `run_query` using TakeKeeper-owned typed continuity/editorial query builders.
- Added typed `ContinuityEvidenceRow`, `EditorialHit`, `McpQueryTrace`, and `McpReadError` contracts.
- Added strict MCP response normalization for:
  - official JSON-string row results;
  - standard MCP text-content envelopes;
  - `structuredContent` / `structured_content` wrappers;
  - small future-compatible `data` / `rows` / `result` row-list wrappers.
- Added fail-closed behavior for MCP tool errors, transport failures, non-JSON text, malformed row lists, wrong production/scene/take scope, invalid confidence, and invalid evidence windows.
- Added per-query latency + row-count provenance in `McpQueryTrace`.
- Hardened `continuity_evidence_sql` and `editorial_retrieval_sql` so analytical result rows explicitly project production/scene/take scope identifiers. This lets the adapter independently reject cross-tenant/cross-scene/cross-take results after MCP execution.
- Preserved editorial result ordering/leading columns so the existing real-DB acceptance assertion on `row[0] == take_id` remains compatible.
- Exported the new MCP types from `takekeeper.__init__`.
- Added `tests/test_mcp_reader.py` with 8 credential-free tests covering official JSON text, MCP text envelope, structured wrapper, empty result, transport outage, wrong-production rejection, malformed/tool-error responses, invalid confidence, and invalid evidence windows.
- Updated `README.md` with the implemented MCP boundary, scope-validation model, failure behavior, repository map, and revised live milestone.
- No GitHub Actions or CI workflows were added.

## Validation

- Reconstructed the new `mcp_reader.py`, revised `queries.py`, and `tests/test_mcp_reader.py` in an isolated local package and executed the new test module.
- Result: **8 tests passed** (`Ran 8 tests ... OK`).
- The full repository suite was not re-run from GitHub because this execution container still cannot resolve/clone `github.com`; no full-suite pass is claimed.
- The query changes preserve existing public function signatures and keep `take_id` as column 0 for editorial integration assertions.
- Real ClickHouse execution, real MCP transport/auth, and real Gemini orchestration remain pending and are not claimed as proven.

## Decisions locked

1. Official MCP is read-only and is never reused for ingestion/persistence credentials.
2. Trusted application writes use `ClickHouseProductionMemory` through a separately permissioned client.
3. The model-facing MCP adapter does not expose arbitrary SQL; it exposes bounded TakeKeeper analytical operations.
4. Generated analytical SQL scopes production/scene/take, and every MCP result row is scope-validated again before becoming evidence.
5. MCP failure or malformed evidence fails closed via `McpReadError`; it is never translated into a positive continuity/editorial claim.
6. Empty MCP results remain truthful empty evidence rather than fabricated absence.
7. Query latency and row count are recorded for later agent/evaluation provenance.
8. Trusted persistence still uses bound parameters; dynamic database identifiers remain validated to letters, digits, and underscores.
9. Runtime MCP/auth/version/latency/write-denial claims must be measured on a real environment.
10. The real integration harness stays opt-in and disposable-database-only.

## Gates

- **Gate A live integration:** NOT YET PROVEN; adapter implemented, live official MCP transport pending.
- **Gate B continuity correctness:** CORE + APP SERVICE + CLICKHOUSE ADAPTER + REAL-DB HARNESS + MCP EVIDENCE READER IMPLEMENTED; live execution pending.
- **Gate C evidence:** durable nullable evidence + typed MCP evidence/provenance implemented; review UI pending.
- **Gate D editorial retrieval:** SQL + real-DB acceptance assertion + MCP typed reader implemented; live MCP execution pending.
- **Gate E failure honesty:** domain + persistence + MCP outage/empty/malformed/wrong-scope behavior implemented and unit-tested.
- **Gate F security:** app-layer scoping + parameter binding + database identifier validation + read/write credential separation + MCP result scope validation implemented; ClickHouse RBAC/write-denial runtime proof pending.
- **Gate G multimodal evidence:** not started; governed by `MULTIMODAL_EXTRACTION_AND_EVAL.md`.

## Blockers / unknowns

1. No reachable real ClickHouse service from this automation environment, so the real acceptance harness and official MCP server cannot be exercised here.
2. No Gemini/Google runtime credentials, so Gemini/ADK orchestration cannot be truthfully demonstrated.
3. Actual ClickHouse server version, `clickhouse-connect` version, official MCP runtime version, transport/auth, concrete live response envelope, row count, and latency remain unmeasured.
4. Explicit runtime write-denial proof with the real MCP credential is still pending.
5. No self-owned demo footage exists yet.
6. The current execution container cannot resolve `github.com`, so the complete repository test suite cannot be cloned and run here.

## Highest-priority backlog

- Execute `tests/test_clickhouse_integration.py` against an authorized local or ClickHouse Cloud instance and fix any version-specific DDL/client behavior.
- Start official `mcp-clickhouse` with `CLICKHOUSE_ALLOW_WRITE_ACCESS=false` against the seeded database.
- Inject the real MCP client's `call_tool` transport into `McpEvidenceReader` and retrieve the Scene 28 continuity rows plus exact editorial hits (`S28-T31`, `S28-T47`).
- Capture official MCP version, transport, auth mode, actual payload envelope, row counts, per-query latency, and server/client versions.
- Attempt a harmless write through the MCP credential and record the expected denial without changing data.
- Add an environment-gated live MCP acceptance test using the measured transport API and preserve the existing fake-transport tests.
- Add persisted human decisions and a minimal evidence-review API/UI.
- Implement the governed Gemini multimodal extraction adapter with fixture-first evaluation before real footage.

## Single best next step

**Run official `ClickHouse/mcp-clickhouse` in read-only mode against the disposable seeded ClickHouse integration database and drive one real Scene 28 continuity query plus the editorial query through `McpEvidenceReader`; record the actual MCP payload/auth/version/latency and prove write denial.**

## Sources / implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://github.com/ClickHouse/mcp-clickhouse/blob/08319aacffeced14598fc605dfa690b8e2081975/mcp_clickhouse/mcp_server.py
- https://github.com/ClickHouse/mcp-clickhouse/releases
