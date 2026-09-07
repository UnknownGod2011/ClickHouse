# TakeKeeper Progress

## Current status

TakeKeeper now has a deterministic continuity core, in-memory and ClickHouse-backed production memory, bounded read-only ClickHouse MCP evidence access, stable continuity finding identities, append-only human review, an authenticated review API and operator console, governed multimodal extraction/evaluation, append-only extraction provenance, retry-safe two-table ClickHouse provenance reconciliation, disposable real-ClickHouse interrupted-write acceptance cases, and an explicit extraction-to-continuity projection boundary. Machine-derived continuity state is now fail-closed: only clear, sustained, non-abstaining observations already classified `machine_high_confidence` can enter continuity comparison. Governed extraction re-analysis replaces the take's previous projected machine state so a newer abstention cannot inherit stale evidence from an older run.

Live ClickHouse + official MCP + Gemini execution remains unproven in this environment because no authorized runtime endpoints or Google credentials are reachable here.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected the actual `UnknownGod2011/ClickHouse` repository through the authenticated GitHub connector.
- Read `src/takekeeper/extraction.py`, `continuity.py`, `models.py`, `memory.py`, `clickhouse_memory.py`, `service.py`, package exports, `tests/test_extraction.py`, `tests/test_continuity.py`, `tests/test_pipeline.py`, and the current README where relevant.
- Confirmed the previous single best next step was the extraction-to-continuity projection/evaluation boundary.
- Identified an additional stale-evidence hazard while wiring that boundary: an earlier high-confidence machine observation could survive a later abstaining re-analysis if governed extraction reused ordinary per-key upsert semantics.

## Exact changes made this run

### Governed extraction-to-continuity projection

- Added `src/takekeeper/extraction_projection.py`.
- Added `ProjectionDecision` and `ContinuityProjection` so every extracted property has an audit-friendly projection outcome.
- `project_extraction_for_continuity()` only promotes an observation when all of these remain true:
  - trusted production/scene/take scope matches the extraction run,
  - value is not `unknown`/`uncertain`,
  - visibility is `clear`,
  - temporal support is `sustained`,
  - extractor disposition is `machine_high_confidence`.
- Excluded observations retain explicit reasons: `abstention_value`, `visibility_not_clear`, `temporal_support_not_sustained`, or `needs_confirmation`.
- Trusted-scope drift fails closed with `ExtractionProjectionError` rather than being treated as ordinary insufficient evidence.
- Added `compare_extraction_to_baselines()` as a deterministic helper that guarantees continuity comparison only sees projected observations.

### Deterministic projection tests

- Added `tests/test_extraction_projection.py`.
- Proves sustained high-confidence evidence can become a real `mismatch`.
- Proves an abstention becomes `insufficient_evidence`, never a mismatch.
- Proves occluded evidence cannot become a mismatch.
- Proves weak-confidence evidence cannot become a mismatch.
- Proves single-sample/uncertain temporal support cannot become a mismatch.

### Stale machine-state prevention

- Extended the `ProductionMemory` contract with scoped `replace_observations(...)`.
- Added scoped replacement behavior to `InMemoryProductionMemory`.
- Added scoped replacement behavior to `ClickHouseProductionMemory`; it deletes only the exact trusted production + scene + take observation scope using bound parameters and synchronous mutation, then inserts the new projected set.
- Refactored ClickHouse observation insertion into `_insert_observations()` so ordinary per-key upsert and full governed replacement share one serialization path.
- Kept existing `TakeAnalysisService.analyze()` semantics unchanged for callers that intentionally use generic observations.
- Added `TakeAnalysisService.analyze_extraction()` for governed multimodal re-analysis. It:
  1. projects the extraction result through the strict policy boundary,
  2. replaces the take's current projected machine observation set,
  3. recomputes continuity from persisted current state,
  4. replaces current findings,
  5. returns findings plus the projection audit decisions.
- Historical raw/model evidence remains append-only in the extraction provenance store; only the current continuity projection is replaced.
- Added a regression proving a first run can produce a left-vs-right mismatch, while a later occluded/unknown run clears the stale projected observation and yields `insufficient_evidence` with no observed value.

### Package surface

- Exported `ContinuityProjection`, `ProjectionDecision`, `ExtractionProjectionError`, `project_extraction_for_continuity`, and `compare_extraction_to_baselines` from `takekeeper`.

### Repository safety

- No GitHub Actions workflow was added or triggered.
- No credentials or paid services were introduced.
- No model-facing write capability was added.
- ClickHouse replacement is tenant/take scoped and parameter-bound; it does not broaden the official MCP read-only boundary.

## Validation / results

- New code was written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.
- The new projection module was syntax-compiled from its source shape successfully in the execution runtime.
- A clean repository clone + targeted unittest run was attempted with:
  `PYTHONPATH=src python -m unittest tests.test_extraction_projection tests.test_pipeline -v`.
- The checkout could not start because this runtime still cannot resolve `github.com`; therefore the checked-in tests were **not executed and are not claimed as passing**.
- No authorized ClickHouse endpoint was available, so the new `replace_observations()` ClickHouse path is not yet proven against a live server.
- No Gemini/Google credential was available, so no live multimodal claim is made.

## Decisions locked

1. Official ClickHouse MCP remains read-only and is never reused for ingestion, persistence, or review credentials.
2. Trusted application writes use separately permissioned ClickHouse clients.
3. Model-facing MCP access remains bounded to TakeKeeper-owned analytical operations; arbitrary agent SQL is not exposed.
4. Continuity finding identity is deterministic over logical scope and independent of mutable evidence/status.
5. Human decisions are append-only audit records and reviewer identity comes from authenticated context.
6. Multimodal output is candidate evidence, never automatic human truth.
7. Production/scene/take scope is trusted application metadata and is never accepted from model output.
8. Only configured entity/property pairs and registry values can enter the governed extraction path.
9. `machine_high_confidence` remains distinct from human confirmation.
10. Extraction transport remains injectable so fixtures, Gemini API, and future Vertex AI transports share one validation path.
11. Extraction provenance is append-only: reprocessing creates a new run and never replaces historical model evidence.
12. Extraction-run + extracted-observation persistence remains explicitly non-transactional across tables; deterministic identities, table-scoped deduplication, immutable-payload validation, and reconciliation provide retry safety.
13. Continuity projection is stricter than extraction persistence. Uncertain evidence may be retained historically for review but cannot become current continuity fact state.
14. A missing/abstaining projected property must become `insufficient_evidence`, not mismatch.
15. Governed machine re-analysis is replacement semantics for the current take projection, preventing stale evidence from surviving a later abstention.
16. Current projected state and historical extraction provenance are separate concepts and must not be conflated.
17. Scope drift at the extraction-to-continuity boundary is an error, not an uncertainty signal.
18. Live runtime claims must be measured against real ClickHouse/MCP/Gemini environments rather than inferred from mocks.

## Gates

- **Gate A live ClickHouse integration:** HARNESS COVERS CORE MEMORY + REVIEW + EXTRACTION REPROCESSING + INTERRUPTED-WRITE RETRY; current-projection replacement live execution still pending.
- **Gate B continuity correctness:** CORE + APP SERVICE + CLICKHOUSE ADAPTER + MCP EVIDENCE READER + GOVERNED EXTRACTION PROJECTION IMPLEMENTED; live execution pending.
- **Gate C evidence/review:** durable evidence + stable finding identity + append-only review + authenticated bounded API + operator console IMPLEMENTED; live execution pending.
- **Gate D editorial retrieval:** SQL + isolated real-DB assertion + typed MCP reader IMPLEMENTED; live MCP execution pending.
- **Gate E failure honesty:** domain/persistence/MCP/review/extraction fail-closed behavior + retry reconciliation + uncertainty-to-insufficient-evidence projection IMPLEMENTED; real runtime execution pending.
- **Gate F security:** tenant scoping + parameter binding + read/write credential separation + MCP scope validation + authenticated review + trusted extraction scope + projection scope validation IMPLEMENTED; live RBAC/write-denial proof pending.
- **Gate G multimodal evidence:** GOVERNED EXTRACTION + FIXTURE EVALUATOR + APPEND-ONLY PROVENANCE + RETRY-SAFE CLICKHOUSE STORE + REAL-DB FAILURE HARNESS + EXTRACTION-TO-CONTINUITY POLICY BOUNDARY IMPLEMENTED; live Gemini transport and labeled-footage evaluation pending.

## Blockers / unknowns

1. No reachable authorized ClickHouse service from this environment.
2. No Gemini/Google runtime credentials.
3. Container DNS currently cannot resolve `github.com`, so a local checkout/test execution cannot be performed despite authenticated connector access.
4. Actual ClickHouse server/client and official MCP runtime versions, auth, payload envelope, latency, row counts, explicit write denial, and current-projection replacement behavior remain unmeasured.
5. No self-owned labeled demo footage exists yet.
6. ClickHouse insert deduplication depends on server/table configuration and a bounded deduplication window, so TakeKeeper continues to rely on explicit reconciliation rather than server deduplication alone.
7. The media provenance fingerprint is based on trusted URI + duration; a future ingest layer should optionally add a true content digest when media bytes are locally available.
8. A concrete Gemini/Vertex transport must remain behind `ExtractionTransport` and should be verified against current official API behavior before compatibility is claimed.

## Highest-priority backlog

- Run the full credential-free Python suite in a normal checkout and fix concrete failures, especially the new projection/service tests.
- Add adapter-level tests for `ClickHouseProductionMemory.replace_observations()` proving exact tenant/take scoping and empty replacement behavior without touching unrelated takes.
- Execute the disposable real-ClickHouse suite and add a case proving a high-confidence projection followed by an abstaining projection leaves zero current observation rows for that property and an `insufficient_evidence` finding.
- Start official `ClickHouse/mcp-clickhouse` read-only, inject its real `run_query` transport, prove continuity/editorial results, and record explicit write denial.
- Add a concrete Gemini transport behind `ExtractionTransport`, using schema-constrained output and private/self-owned media only.
- Create a tiny self-owned labeled fixture set for mug-hand + jacket-state and add property-level value/evidence/projection metrics.
- Add optional ingest-time media content hashing without requiring media upload to ClickHouse.

## Single best next step

**Add adapter-level and disposable-real-ClickHouse acceptance coverage for scoped `replace_observations()`, specifically proving that an eligible machine projection followed by an abstaining re-analysis removes the stale current observation for only that production/scene/take while preserving other tenants/takes, and that continuity converges to `insufficient_evidence`.**

## Sources / implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/interactions-breaking-changes-may-2026
