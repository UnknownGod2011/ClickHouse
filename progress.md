# TakeKeeper Progress

## Current status

TakeKeeper now has the deterministic continuity core, in-memory and ClickHouse-backed `ProductionMemory` adapters, an environment-gated real ClickHouse acceptance harness, a bounded fail-closed `McpEvidenceReader`, stable deterministic continuity finding identities, append-only human review storage, a narrow authenticated WSGI review API, a same-origin operator review console, and a credential-free governed multimodal extraction/evaluation contract. Live ClickHouse + official MCP + Gemini execution remains unproven in this environment because no real ClickHouse service or Google runtime credential is reachable here.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected the repository root and `src/takekeeper/` tree.
- Read `MULTIMODAL_EXTRACTION_AND_EVAL.md`, `src/takekeeper/models.py`, `src/takekeeper/memory.py`, `src/takekeeper/__init__.py`, and `README.md`.
- Confirmed the previous live ClickHouse/MCP acceptance gate remains externally blocked.
- Re-verified current official Gemini documentation before implementation. As of 2026-09-07, official docs show native video inputs through the Gemini API and JSON-schema structured output. The May 2026 Interactions API migration also moved JSON output configuration into the unified `response_format` contract, so the TakeKeeper adapter intentionally stays SDK/transport-injected rather than freezing one volatile client call shape into the domain layer.

## Changes made this run

### Governed extraction core

- Added `src/takekeeper/extraction.py`.
- Added a strict `PropertySpec` registry and a default hero registry for sustained/inspectable properties including mug hand, jacket state, lamp power state, boom visibility, and transcript-backed target dialogue.
- Added `TakeExtractionRequest` with trusted production/scene/take scope, media URI, clip duration, configured properties, model/version, and prompt-schema version.
- Added `build_extraction_prompt()` which instructs the model to return only configured properties, cite bounded millisecond evidence windows, prefer unknown/uncertain when evidence is weak, and avoid inventing identifiers.
- Added a JSON-schema response contract with `additionalProperties=false`, explicit required fields, bounded confidence, evidence timestamps, source type, visibility state, temporal support, rationale, and raw model value.
- Added `GovernedMultimodalExtractor`, whose model transport is injected. This keeps Google/Gemini client code outside the TakeKeeper domain contract and makes the exact same validation path usable by deterministic fixtures.
- Tenant/take scope is derived only from the trusted `TakeExtractionRequest`; model output is not allowed to provide production/scene/take identifiers.
- Model output fails closed on malformed JSON, unexpected fields, unconfigured properties, duplicate properties, out-of-registry values, impossible evidence windows, invalid confidence, overlong diagnostic text, and disallowed evidence sources.
- Machine perception remains `Observation.verification_state="unverified"`; high model confidence is represented separately as an extraction disposition and is never promoted to human confirmation.
- `machine_high_confidence` requires all of: a non-abstention value, configured confidence threshold, `visibility_state=clear`, and `temporal_support=sustained`. Otherwise the candidate is `needs_confirmation`.
- Dialogue extraction is explicitly constrained to transcript evidence in the default registry; visual lip-movement inference is not accepted as dialogue evidence.
- Added `FixtureExtractionTransport` for credential-free deterministic development/evaluation.

### Deterministic evaluation

- Added `src/takekeeper/extraction_eval.py`.
- Added immutable `TruthObservation` fixtures that record entity/property, expected normalized value, human evidence window, and whether the property is actually observable.
- Added `evaluate_extraction()` with per-run metrics for exact value correctness, evidence-window overlap, unsupported assertions, and correct abstention on unobservable truth.
- Kept evaluation property-level instead of inventing a blended "AI accuracy" claim.

### Tests and package surface

- Added `tests/test_extraction.py` with credential-free coverage for:
  - fixture transport using the same production validation path;
  - trusted scope propagation;
  - unconfigured-property rejection;
  - out-of-registry-value rejection;
  - impossible evidence-window rejection;
  - low-confidence / weak-temporal-support downgrade to confirmation;
  - property-specific evidence-source enforcement;
  - exact-value + evidence-overlap evaluation;
  - correct abstention for intentionally unobservable truth.
- Exported the extraction/evaluation contracts from `takekeeper.__init__`.
- No GitHub Actions, destructive repository operations, secrets, paid services, or unrelated repository changes were introduced.

## Validation

- Repository reads/writes were performed through the authenticated GitHub connector against `UnknownGod2011/ClickHouse` `main`.
- Attempted a fresh local clone and `PYTHONPATH=src python -m unittest tests.test_extraction -v`.
- The execution environment failed before checkout with: `Could not resolve host: github.com`.
- Therefore the new extraction tests are committed but are **not claimed as passing** in this run.
- The real ClickHouse integration suite remains unexecuted because no authorized ClickHouse endpoint is reachable from this environment.
- No Google/Gemini credential was available, so no live multimodal latency/accuracy/API-envelope claim is made.

## Decisions locked

1. Official ClickHouse MCP remains read-only and is never reused for ingestion, persistence, or human-review credentials.
2. Trusted application writes use separately permissioned ClickHouse clients.
3. Model-facing ClickHouse MCP remains bounded to TakeKeeper-owned analytical operations; arbitrary agent SQL is not exposed.
4. Continuity finding identity is deterministic over logical scope and independent of mutable evidence/status.
5. Human decisions are append-only audit records.
6. Reviewer identity comes from authenticated context, not caller-controlled JSON.
7. Multimodal model output is candidate evidence, never automatic human truth.
8. Production/scene/take scope is trusted application metadata and is never accepted from model output.
9. Only configured entity/property pairs and enum values can enter the structured observation path.
10. Invalid timestamps, invalid confidence, malformed payloads, unconfigured properties, duplicate properties, and disallowed evidence sources fail closed.
11. `machine_high_confidence` is separate from `human_confirmed` and requires clear + sustained evidence in addition to a calibrated confidence threshold.
12. Unobservable or weakly supported states must abstain/request confirmation rather than becoming negative evidence.
13. Model/transport code remains injectable so fixture tests, Gemini API, and future Vertex AI transports can share one domain validation path.
14. Extraction/evaluation records retain model version and prompt-schema version so reprocessing can be versioned rather than silently mutating historical truth.
15. Runtime MCP/auth/version/latency/write-denial claims must be measured on a real environment.

## Gates

- **Gate A live ClickHouse integration:** NOT YET PROVEN; adapters and isolated harness implemented, live execution pending.
- **Gate B continuity correctness:** CORE + APP SERVICE + CLICKHOUSE ADAPTER + ISOLATED REAL-DB HARNESS + MCP EVIDENCE READER IMPLEMENTED; live execution pending.
- **Gate C evidence/review:** durable evidence + stable finding identity + append-only review + authenticated bounded API + operator console IMPLEMENTED; live execution pending.
- **Gate D editorial retrieval:** SQL + isolated real-DB assertion + typed MCP reader IMPLEMENTED; live MCP execution pending.
- **Gate E failure honesty:** domain/persistence/MCP/review/extraction fail-closed behavior IMPLEMENTED; newest extraction tests pending execution in a runnable checkout.
- **Gate F security:** scoping + parameter binding + read/write credential separation + MCP result scope validation + authenticated review boundary + browser hardening + trusted extraction scope IMPLEMENTED; live ClickHouse RBAC/write-denial proof pending.
- **Gate G multimodal evidence:** GOVERNED EXTRACTION CONTRACT + FIXTURE TRANSPORT + DETERMINISTIC EVALUATOR IMPLEMENTED; live Gemini transport, persistence/versioning, and real labeled footage evaluation pending.

## Blockers / unknowns

1. No reachable authorized ClickHouse service from this automation environment.
2. No Gemini/Google runtime credentials.
3. The execution container cannot currently resolve `github.com`, so it cannot clone the repository and run the checked-in suite.
4. Actual ClickHouse server/client and official MCP runtime versions, transport/auth, payload envelope, row count, latency, and explicit write denial remain unmeasured.
5. No self-owned labeled demo footage exists yet.
6. The new extraction contract is not yet wired to append-only extraction-run/observation persistence; current `ProductionMemory.upsert_observations()` intentionally represents only the existing deterministic vertical slice.
7. A concrete Gemini/Vertex transport implementation should be added only behind the injected transport boundary and tested against the current Interactions API shape before claiming production compatibility.

## Highest-priority backlog

- Run the complete credential-free Python suite in a normal checkout, especially `tests/test_extraction.py`, and fix any concrete failures.
- Execute `tests/test_clickhouse_integration.py` against an authorized disposable/local or ClickHouse Cloud instance and record server/client versions and timings.
- Start official `ClickHouse/mcp-clickhouse` with write access disabled, inject its real `run_query` transport into `McpEvidenceReader`, prove the Scene 28 continuity/editorial results, and record explicit write denial.
- Add append-only extraction-run + extracted-observation persistence so model version, prompt-schema version, source metadata, raw normalized evidence metadata, and reprocessing history survive independently of the current observation projection.
- Add a concrete Gemini Interactions API transport behind `ExtractionTransport`, using JSON-schema structured output and private/self-owned media only.
- Create a tiny self-owned labeled fixture set for mug-hand + jacket-state first; add lamp/boom/dialogue only after property-level evidence metrics are acceptable.
- Add continuity evaluation on pairs of extracted truth observations so uncertain/missing evidence is explicitly proven not to become a mismatch.
- Replace static-bearer deployment auth with a production OIDC/IAP identity adapter when selecting a concrete Google Cloud topology.

## Single best next step

**Implement append-only extraction-run and extracted-observation persistence in ClickHouse, including model/prompt/media provenance and reprocessing version identity, with an in-memory reference store and credential-free tests. This is fully unblocked and prevents later Gemini integration from silently overwriting production history.**

## Sources / implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/interactions-breaking-changes-may-2026
