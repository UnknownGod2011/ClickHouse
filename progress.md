# TakeKeeper Progress

## Current status

TakeKeeper is a personal open-source production-memory system with a deterministic continuity core, in-memory and ClickHouse-backed state, bounded read-only ClickHouse MCP evidence access, append-only review and extraction provenance, authenticated review surfaces, governed multimodal extraction, fail-closed extraction-to-continuity projection, retry-safe persistence, and an optional Google Gen AI / Vertex AI transport.

Machine continuity state is replacement-based: only clear, sustained, non-abstaining `machine_high_confidence` evidence is eligible to become current continuity state. Later abstaining re-analysis clears stale current projection for the exact trusted production/scene/take while historical extraction provenance remains append-only.

A credential-free multimodal benchmark now exercises the complete governed path from fixture model response through local extraction validation, confidence/disposition classification, continuity projection, and final continuity finding status.

Live ClickHouse, official MCP, and Gemini/Vertex execution remain intentionally unclaimed until they are exercised against authorized real services.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected `src/takekeeper/extraction.py`, `extraction_eval.py`, `extraction_projection.py`, `continuity.py`, `models.py`, the source/test inventory, and the existing multimodal evaluation contract.
- Confirmed the previous single best next step was an objective credential-free multimodal evaluation fixture around mug-hand and jacket-state.
- Confirmed the existing evaluator measured exact value and simple evidence overlap but did not separately measure confidence/disposition, projection eligibility, or final continuity status.

## Exact changes made this run

### End-to-end multimodal benchmark

Added `src/takekeeper/multimodal_benchmark.py` with:

- `BenchmarkTruth`, which labels normalized value, human evidence window, expected extraction disposition, expected projection eligibility, and expected final continuity finding status;
- `BenchmarkEvaluation`, exposing separate exact-value, temporal-evidence, disposition, projection, and finding-status metrics;
- inclusive millisecond temporal Intersection-over-Union (`evidence_window_iou`) so a huge weakly localized window does not receive the same credit as a tightly localized one merely because both overlap;
- an IoU >= 0.50 evidence-localization metric plus mean IoU;
- duplicate prediction/truth identity rejection;
- unsupported non-abstaining assertion counting;
- evaluation through the actual `compare_extraction_to_baselines()` projection boundary rather than a parallel approximation.

### Labeled deterministic fixture manifest

Added `tests/fixtures/multimodal_eval/manifest.json` with three synthetic/self-owned contract fixtures over the two first production properties:

1. `matching_clear_take` — mug in left hand and jacket zipped; both clear/sustained/high confidence; no continuity finding expected.
2. `clear_continuity_mismatch` — mug in right hand and jacket open against left/zipped baselines; both should project and become deterministic `mismatch` findings.
3. `occluded_abstention` — mug-hand and jacket state are genuinely unobservable; both return `unknown`, require confirmation, must not project, and must become `insufficient_evidence` rather than mismatches.

The fixture set contains no third-party media and no credentials. It is a response/evidence contract benchmark, not a claim that live Gemini video quality has been measured yet.

### Deterministic regression suite

Added `tests/test_multimodal_benchmark.py` covering:

- the three labeled fixtures through `FixtureExtractionTransport` + `GovernedMultimodalExtractor` + continuity projection;
- 100% expected normalized-value, disposition, projection, and finding-status accuracy on the fixed deterministic fixture responses;
- temporal IoU quality with an >= 0.80 mean requirement and 100% IoU@0.50 rate for the fixed fixtures;
- explicit proof that occluded abstentions never become continuity facts;
- temporal-IoU behavior that penalizes broad weak localization even if it overlaps truth;
- fail-closed duplicate truth identities.

### Repository safety

- No GitHub Actions workflow was added, modified, triggered, or rerun.
- No credential, paid service, destructive production operation, arbitrary SQL surface, or cross-tenant authority was introduced.
- Trusted production/scene/take scope still comes from application input, not model output.
- The benchmark measures the deterministic safety boundary independently of provider credentials.

## Validation / results

- Files were written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.
- Implementation commits this run:
  - `c206fa1d81f5def1d0ed5c8d7d91da353b8f327f` — multimodal benchmark scorer;
  - `23c530d8118d02aae9da2300287878da6f6a40af` — labeled benchmark manifest;
  - `c1b457e4dbede3df311700a4183074ab166b6911` — benchmark regression suite.
- Attempted a clean checkout followed by `PYTHONPATH=src python -m unittest tests.test_multimodal_benchmark -v`.
- The execution container still cannot resolve `github.com`, so clone failed before Python started. The checked-in suite is therefore structurally reviewed but **not claimed as passing**.
- No live Gemini/Vertex request was made and no real ClickHouse/MCP endpoint was contacted.

## Decisions locked

1. Official ClickHouse MCP remains read-only and is not reused for application writes or credentials.
2. Trusted application writes use separately permissioned ClickHouse clients.
3. Agent-facing MCP access stays bounded to TakeKeeper-owned analytical operations; arbitrary agent SQL is not exposed.
4. Production/scene/take scope is trusted application metadata and is never accepted from model output.
5. Only configured entity/property pairs and registry values can enter governed extraction.
6. Machine confidence is not human confirmation.
7. Extraction provenance is append-only; reprocessing creates a new run.
8. Multi-table extraction persistence is not represented as transactional; deterministic identity + reconciliation provide retry safety.
9. Continuity projection is stricter than extraction persistence: uncertain evidence can be retained historically but cannot become current continuity state.
10. Missing/abstaining projected evidence becomes `insufficient_evidence`, never a mismatch.
11. Governed re-analysis replaces current projected state only for the exact trusted take scope so stale evidence cannot survive a later abstention.
12. Google structured output is a formatting aid, not a trust boundary; responses are locally validated before persistence/projection.
13. The Google transport cannot choose tools, production scope, or persistence operations.
14. Evaluation reports independent metrics for value, evidence localization, disposition, projection, and continuity outcome rather than one blended "AI accuracy" score.
15. Live service claims require execution against the real service and are not inferred from mocks.

## Gates

- **Gate A — live ClickHouse:** implementation/harness coverage exists for memory, review, extraction retry, and scoped projection replacement; real-endpoint execution remains pending.
- **Gate B — continuity correctness:** deterministic comparison, application service, persistence adapter, MCP evidence reader, governed projection, and stale-state convergence are implemented.
- **Gate C — evidence/review:** durable evidence, stable finding identity, append-only review, authenticated bounded API, and operator console are implemented.
- **Gate D — editorial retrieval:** typed/bounded retrieval and SQL coverage exist; live official MCP execution remains pending.
- **Gate E — failure honesty:** extraction/persistence/MCP/review paths fail closed structurally; abstentions cannot become false mismatches.
- **Gate F — security:** tenant scope, parameter binding, read/write separation, authenticated review, trusted extraction scope, and replacement isolation are implemented structurally; live RBAC/write-denial proof remains pending.
- **Gate G — multimodal evidence:** governed extraction, provenance, retry safety, projection/replacement, Google transport, and now an objective response-to-continuity benchmark are implemented; full local test execution, real labeled video assets, and live Gemini evaluation remain pending.

## Blockers / unknowns

1. The execution container cannot currently resolve `github.com` for a local checkout.
2. No reachable authorized ClickHouse endpoint is available in this run.
3. No Gemini/Vertex credentials or private/self-owned live video are available in this run.
4. Official MCP runtime/auth/version behavior and explicit write denial remain unmeasured against a live server.
5. Live `google-genai` model/schema/video behavior, latency, token usage, and provider failure modes remain unmeasured.
6. The new manifest is a deterministic contract benchmark; actual self-recorded/generated video clips matching the labels still need to be created before measuring model quality.
7. Media provenance currently fingerprints trusted URI + duration; a true content digest should be added when bytes are available at ingest.
8. Extensionless signed-media endpoints still require an explicit trusted MIME/ingest manifest before the Google transport can support them safely.

## Highest-priority backlog

- Run the complete credential-free suite in a normal checkout and fix any concrete failures, starting with `tests.test_multimodal_benchmark` and `tests.test_google_genai_transport`.
- Add a benchmark runner that emits a stable machine-readable JSON report across all manifest cases, suitable for comparing model/version candidates without weakening per-property metrics.
- Replace/augment the response-only benchmark cases with tiny self-owned or generated video clips carrying the same labels; never tune truth labels after seeing model output.
- Execute one live private/self-owned video extraction with Google Gen AI / Vertex AI and feed the returned response unchanged through the benchmark and governed validator.
- Execute the projection replacement and extraction retry integration suites against disposable real ClickHouse.
- Start official `ClickHouse/mcp-clickhouse` read-only, inject the actual transport, prove continuity/editorial queries, and record explicit write denial.
- Add optional ingest-time media content hashing and trusted explicit MIME metadata.

## Single best next step

**Add a deterministic benchmark runner/CLI that loads `tests/fixtures/multimodal_eval/manifest.json`, evaluates every case through the governed extraction/projection pipeline, emits stable JSON with per-case and aggregate value/IoU/disposition/projection/finding metrics, and exits non-zero when explicit acceptance thresholds fail. That turns the new fixture set into a reusable release gate for future Gemini model/version comparisons without requiring CI or credentials.**

## Relevant implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
