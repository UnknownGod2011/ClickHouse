# TakeKeeper Progress

## Current status

TakeKeeper now has the deterministic continuity core, in-memory and ClickHouse-backed `ProductionMemory` adapters, an environment-gated real ClickHouse acceptance harness, a bounded fail-closed `McpEvidenceReader`, stable deterministic continuity finding identities, and an append-only human review boundary with in-memory and ClickHouse-backed decision stores. The trusted write path remains structurally separate from the read-only agent/MCP path. Live ClickHouse + MCP + Gemini execution is still unproven in this environment because no real ClickHouse service or Google runtime credential is reachable here.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected the repository root and `src/takekeeper/` tree.
- Inspected `models.py`, `memory.py`, `clickhouse_memory.py`, package exports, `sql/schema.sql`, `tests/test_clickhouse_memory.py`, and `README.md`.
- Confirmed the schema already had an append-only `human_decisions` table, but the implementation had no usable review service/store.
- Found a concrete identity defect: `ClickHouseProductionMemory.replace_findings()` generated a new random UUID for every finding on every re-analysis, while that ID is the foreign reference used by `human_decisions`. Because the domain did not expose the generated random ID, later human review could not reliably target or preserve the identity of the same logical finding.

## Changes made this run

- Added `src/takekeeper/review.py`.
- Added `stable_finding_id(finding)`, a deterministic UUIDv5 identity derived from production + scene + take + entity + property. Mutable evidence/value/status are intentionally excluded so the same logical concern keeps one identity across re-analysis.
- Changed ClickHouse continuity persistence to store `stable_finding_id(row)` instead of a fresh random UUID when writing `continuity_findings.finding_id`.
- Added typed `ReviewDecision` and `ReviewOutcome` contracts.
- Added `ReviewDecisionStore` protocol plus `InMemoryReviewDecisionStore` and `ClickHouseReviewDecisionStore`.
- ClickHouse human decisions are append-only and use the existing `human_decisions` table; prior decisions are never mutated or overwritten.
- Added `FindingReviewService`, which never accepts an arbitrary raw finding ID from callers. It first resolves the requested entity/property from the current production/scene/take findings, derives the stable ID internally, and only then records a decision.
- Review outcomes are bounded to `confirmed`, `rejected`, or `needs_followup`; blank actor identities are rejected.
- ClickHouse review-history reads bind `production_id` and `finding_id` as parameters; dynamic database identifiers remain validated.
- Exported review contracts from `takekeeper.__init__`.
- Added `tests/test_review.py` with credential-free coverage for stable identity across re-analysis, scoped review success/history, cross-production rejection, mandatory actor identity, ClickHouse append/read parameter binding, and database identifier validation.
- Extended `tests/test_clickhouse_memory.py` with an assertion that persisted finding IDs equal the deterministic domain identity.
- Updated `README.md` with the human-review boundary, stable identity rationale, repository map, safety properties, and the minimal review-UI milestone.
- No GitHub Actions or CI workflows were added.

## Validation

- Attempted to clone the actual updated repository and run `python -m unittest discover -s tests -v`.
- The execution container still cannot resolve `github.com`, so the clone failed before the full repository suite could run. No full-suite pass is claimed.
- Reconstructed the new review module with compatible `Finding` and `InMemoryProductionMemory` contracts in an isolated local package and ran six credential-free tests covering the new behavior.
- Result: **6 tests passed** (`Ran 6 tests ... OK`).
- `review.py` was syntax-compiled before upload.
- Real ClickHouse review persistence, the environment-gated DB harness, official MCP transport/auth, and Gemini orchestration remain pending and are not claimed as live-proven.

## Decisions locked

1. Official MCP is read-only and is never reused for ingestion, persistence, or human-review credentials.
2. Trusted application writes use separately permissioned ClickHouse clients.
3. Model-facing MCP remains bounded to TakeKeeper-owned analytical operations; arbitrary agent SQL is not exposed.
4. Continuity finding identity is deterministic over logical scope (`production_id`, `scene_id`, `take_id`, `entity_id`, `property_key`) and is independent of mutable evidence/status.
5. Human decisions are append-only audit records; later judgments do not erase earlier judgments.
6. The review service derives finding IDs internally from a finding that currently exists in the requested scope; callers cannot submit arbitrary finding IDs.
7. Generated analytical SQL scopes production/scene/take, and MCP result rows are scope-validated again before becoming evidence.
8. MCP failures/malformed evidence fail closed; empty results remain truthful empty evidence.
9. Trusted persistence uses bound parameters; dynamic database identifiers remain validated to letters, digits, and underscores.
10. Runtime MCP/auth/version/latency/write-denial claims must be measured on a real environment.

## Gates

- **Gate A live integration:** NOT YET PROVEN; adapters implemented, live official MCP transport pending.
- **Gate B continuity correctness:** CORE + APP SERVICE + CLICKHOUSE ADAPTER + REAL-DB HARNESS + MCP EVIDENCE READER IMPLEMENTED; live execution pending.
- **Gate C evidence/review:** durable nullable evidence + stable finding identity + append-only scoped human-review service/store IMPLEMENTED; review API/UI pending.
- **Gate D editorial retrieval:** SQL + real-DB acceptance assertion + MCP typed reader implemented; live MCP execution pending.
- **Gate E failure honesty:** domain + persistence + MCP outage/empty/malformed/wrong-scope behavior implemented and unit-tested.
- **Gate F security:** app-layer scoping + parameter binding + database identifier validation + read/write credential separation + MCP result scope validation + review-scope resolution implemented; ClickHouse RBAC/write-denial runtime proof pending.
- **Gate G multimodal evidence:** not started; governed by `MULTIMODAL_EXTRACTION_AND_EVAL.md`.

## Blockers / unknowns

1. No reachable real ClickHouse service from this automation environment, so the real acceptance harness and official MCP server cannot be exercised here.
2. No Gemini/Google runtime credentials, so Gemini/ADK orchestration cannot be truthfully demonstrated.
3. Actual ClickHouse server version, `clickhouse-connect` version, official MCP runtime version, transport/auth, concrete live response envelope, row count, and latency remain unmeasured.
4. Explicit runtime write-denial proof with the real MCP credential is still pending.
5. Real ClickHouse persistence of the new human-review path is not yet acceptance-tested against a live server.
6. No self-owned demo footage exists yet.
7. The current execution container cannot resolve `github.com`, so the complete repository test suite cannot be cloned and run here.

## Highest-priority backlog

- Extend the real ClickHouse integration harness to assert stable persisted finding IDs and append/read one `human_decisions` row without mutating prior history.
- Execute `tests/test_clickhouse_integration.py` against an authorized local or ClickHouse Cloud instance and fix any version-specific DDL/client behavior.
- Start official `mcp-clickhouse` with `CLICKHOUSE_ALLOW_WRITE_ACCESS=false` against the seeded database.
- Inject the real MCP client's `call_tool` transport into `McpEvidenceReader` and retrieve the Scene 28 continuity rows plus exact editorial hits (`S28-T31`, `S28-T47`).
- Capture official MCP version, transport, auth mode, actual payload envelope, row counts, per-query latency, and server/client versions.
- Attempt a harmless write through the MCP credential and record the expected denial without changing data.
- Add a minimal evidence-review HTTP API/UI over `FindingReviewService` that shows evidence window/confidence/status/history and appends decisions without arbitrary write primitives.
- Implement the governed Gemini multimodal extraction adapter with fixture-first evaluation before real footage.

## Single best next step

**Extend the environment-gated real ClickHouse acceptance harness to prove the new stable finding identity + append-only human-decision contract end to end, then run that harness on an authorized ClickHouse instance when one is reachable.**

## Sources / implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://github.com/ClickHouse/mcp-clickhouse/blob/08319aacffeced14598fc605dfa690b8e2081975/mcp_clickhouse/mcp_server.py
- https://github.com/ClickHouse/mcp-clickhouse/releases
