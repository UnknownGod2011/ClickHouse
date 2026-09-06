# TakeKeeper Progress

## Current status

TakeKeeper now has the deterministic continuity core, in-memory and ClickHouse-backed `ProductionMemory` adapters, an environment-gated real ClickHouse acceptance harness, a bounded fail-closed `McpEvidenceReader`, stable deterministic continuity finding identities, and an append-only human review boundary with in-memory and ClickHouse-backed decision stores. The real-database harness now also isolates every acceptance case from mutable prior test state and asserts the stable finding ID + append-only review contract end to end. The trusted write path remains structurally separate from the read-only agent/MCP path. Live ClickHouse + MCP + Gemini execution is still unproven in this environment because no real ClickHouse service or Google runtime credential is reachable here.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected `tests/test_clickhouse_integration.py`, `src/takekeeper/review.py`, `sql/schema.sql`, `sql/seed_demo.sql`, and `README.md`.
- Confirmed the previous highest-priority backlog item was extending the real ClickHouse harness to prove stable finding identity and append-only review history.
- Found a concrete acceptance-harness reliability defect: all real-ClickHouse tests shared one mutable seeded database. `test_reanalysis_removes_stale_findings()` replaces the seeded `S28-T47` observations with only three corrected observations, so a later seed-contract test could observe mutated state depending on test order. The harness therefore was not truly test-isolated.

## Changes made this run

- Updated `tests/test_clickhouse_integration.py`.
- The integration database is still created once per test class, but mutable TakeKeeper tables are now truncated and the deterministic Scene 28 seed is reapplied in `setUp()` before every acceptance case.
- This makes editorial, continuity, re-analysis, and review assertions independent of unittest method ordering and prior test mutations.
- Added real-database acceptance coverage for the stable human-review contract:
  - run `TakeAnalysisService` for `S28-T47`;
  - derive the expected deterministic UUIDv5 with `stable_finding_id()`;
  - query `continuity_findings` with bound scope parameters and require the persisted `finding_id` to equal that deterministic ID;
  - append `needs_followup` and then `confirmed` decisions through `FindingReviewService` backed by `ClickHouseReviewDecisionStore`;
  - require both decisions to retain the same finding ID but distinct decision IDs;
  - read history through the service and require both decisions in append order;
  - directly verify the ClickHouse `human_decisions` table still contains two rows for that scoped finding.
- Updated `README.md` so the integration-harness description now documents per-test fixture reset, temporary-table truncate permissions, stable persisted finding-ID verification, and append-only real-table review assertions.
- No GitHub Actions or CI workflows were added.

## Validation

- Attempted to clone the actual updated repository and execute `python -m unittest discover -s tests -v` in the execution container.
- The environment still fails DNS resolution for `github.com` (`Could not resolve host: github.com`), so the clone failed before tests could execute. No full-suite pass is claimed.
- A real ClickHouse service is not reachable from this environment, so the newly extended environment-gated acceptance test cannot be truthfully claimed as live-passing here.
- The changes use only existing repository interfaces (`ClickHouseProductionMemory`, `FindingReviewService`, `ClickHouseReviewDecisionStore`, `stable_finding_id`) and parameter-bound ClickHouse queries; no new dependency or credential was introduced.

## Decisions locked

1. Official MCP is read-only and is never reused for ingestion, persistence, or human-review credentials.
2. Trusted application writes use separately permissioned ClickHouse clients.
3. Model-facing MCP remains bounded to TakeKeeper-owned analytical operations; arbitrary agent SQL is not exposed.
4. Continuity finding identity is deterministic over logical scope (`production_id`, `scene_id`, `take_id`, `entity_id`, `property_key`) and is independent of mutable evidence/status.
5. Human decisions are append-only audit records; later judgments do not erase earlier judgments.
6. The review service derives finding IDs internally from a finding that currently exists in the requested scope; callers cannot submit arbitrary finding IDs.
7. Real-database acceptance tests must reset mutable fixture state before each test so re-analysis and review writes cannot create order-dependent false passes/failures.
8. Generated analytical SQL scopes production/scene/take, and MCP result rows are scope-validated again before becoming evidence.
9. MCP failures/malformed evidence fail closed; empty results remain truthful empty evidence.
10. Trusted persistence uses bound parameters; dynamic database identifiers remain validated to letters, digits, and underscores.
11. Runtime MCP/auth/version/latency/write-denial claims must be measured on a real environment.

## Gates

- **Gate A live integration:** NOT YET PROVEN; adapters implemented, live official MCP transport pending.
- **Gate B continuity correctness:** CORE + APP SERVICE + CLICKHOUSE ADAPTER + ISOLATED REAL-DB HARNESS + MCP EVIDENCE READER IMPLEMENTED; live execution pending.
- **Gate C evidence/review:** durable nullable evidence + stable finding identity + append-only scoped human-review service/store + real-DB acceptance assertions IMPLEMENTED; live execution and review API/UI pending.
- **Gate D editorial retrieval:** SQL + isolated real-DB acceptance assertion + MCP typed reader implemented; live MCP execution pending.
- **Gate E failure honesty:** domain + persistence + MCP outage/empty/malformed/wrong-scope behavior implemented and unit-tested.
- **Gate F security:** app-layer scoping + parameter binding + database identifier validation + read/write credential separation + MCP result scope validation + review-scope resolution implemented; ClickHouse RBAC/write-denial runtime proof pending.
- **Gate G multimodal evidence:** not started; governed by `MULTIMODAL_EXTRACTION_AND_EVAL.md`.

## Blockers / unknowns

1. No reachable real ClickHouse service from this automation environment, so the real acceptance harness and official MCP server cannot be exercised here.
2. No Gemini/Google runtime credentials, so Gemini/ADK orchestration cannot be truthfully demonstrated.
3. Actual ClickHouse server version, `clickhouse-connect` version, official MCP runtime version, transport/auth, concrete live response envelope, row count, and latency remain unmeasured.
4. Explicit runtime write-denial proof with the real MCP credential is still pending.
5. Real ClickHouse execution of the newly extended stable-ID + append-only review acceptance case is still pending.
6. No self-owned demo footage exists yet.
7. The current execution container cannot resolve `github.com`, so the complete repository test suite cannot be cloned and run here.

## Highest-priority backlog

- Execute `tests/test_clickhouse_integration.py` against an authorized local or ClickHouse Cloud instance and fix any version-specific DDL/client/review-store behavior.
- Record ClickHouse server/client versions and acceptance timings once the real harness executes.
- Start official `mcp-clickhouse` with `CLICKHOUSE_ALLOW_WRITE_ACCESS=false` against the seeded database.
- Inject the real MCP client's `call_tool` transport into `McpEvidenceReader` and retrieve the Scene 28 continuity rows plus exact editorial hits (`S28-T31`, `S28-T47`).
- Capture official MCP version, transport, auth mode, actual payload envelope, row counts, per-query latency, and server/client versions.
- Attempt a harmless write through the MCP credential and record the expected denial without changing data.
- Add a minimal evidence-review HTTP API/UI over `FindingReviewService` that shows evidence window/confidence/status/history and appends decisions without arbitrary write primitives.
- Implement the governed Gemini multimodal extraction adapter with fixture-first evaluation before real footage.

## Single best next step

**Execute the now test-isolated `tests/test_clickhouse_integration.py` against an authorized ClickHouse instance and fix any real server/client behavior found; once that passes, move immediately to the official read-only `mcp-clickhouse` runtime gate.**

## Sources / implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://github.com/ClickHouse/mcp-clickhouse/blob/08319aacffeced14598fc605dfa690b8e2081975/mcp_clickhouse/mcp_server.py
- https://github.com/ClickHouse/mcp-clickhouse/releases
