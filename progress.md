# TakeKeeper Progress

## Current status

TakeKeeper is a personal open-source production-memory system with a deterministic continuity core, in-memory and ClickHouse-backed state, bounded read-only ClickHouse MCP evidence access, append-only review and extraction provenance, authenticated review surfaces, governed multimodal extraction, fail-closed extraction-to-continuity projection, retry-safe persistence, and an optional Google Gen AI / Vertex AI transport.

Machine continuity state is replacement-based: only clear, sustained, non-abstaining `machine_high_confidence` evidence is eligible to become current continuity state. Later abstaining re-analysis clears stale current projection for the exact trusted production/scene/take while historical extraction provenance remains append-only.

The credential-free multimodal benchmark now has an executable release-gate CLI. It evaluates the complete governed fixture path, emits stable machine-readable JSON with per-case and aggregate metrics, records the exact thresholds and manifest SHA-256, and returns non-zero when quality regresses.

Live ClickHouse, official MCP, and Gemini/Vertex execution remain intentionally unclaimed until exercised against authorized real services.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected repository metadata and confirmed `UnknownGod2011/ClickHouse` (`main`) is the intended repository.
- Inspected `src/takekeeper/multimodal_benchmark.py`, `tests/test_multimodal_benchmark.py`, `tests/fixtures/multimodal_eval/manifest.json`, `src/takekeeper/extraction.py`, `pyproject.toml`, the package inventory, and `README.md`.
- Confirmed the previous single best next step was a deterministic benchmark runner/CLI rather than additional planning.
- Confirmed the existing benchmark scorer already separated value, evidence localization, disposition, projection, finding status, and unsupported assertions, but there was no reusable command, aggregate report contract, threshold policy, or exit-code gate.

## Exact changes made this run

### Deterministic benchmark runner and report contract

Added `src/takekeeper/benchmark_cli.py` with:

- report schema `takekeeper-multimodal-benchmark-report-v1`;
- strict support for the checked-in `takekeeper-multimodal-eval-v1` manifest contract;
- manifest validation for required metadata, non-empty/unique case names, registered property identities, and valid fixture inputs;
- execution of every case through `FixtureExtractionTransport -> GovernedMultimodalExtractor -> evaluate_benchmark_run()` rather than a parallel scorer;
- weighted aggregate metrics across all labeled properties;
- per-case metrics and bounded failure diagnostics;
- SHA-256 of the exact manifest bytes so an archived result can be tied to the evaluated truth fixture;
- candidate extractor model/version metadata in the report;
- deterministic JSON rendering with sorted keys and six-decimal metric rounding;
- explicit acceptance thresholds for exact value, mean evidence IoU, IoU@0.50 rate, disposition, projection, final finding status, and unsupported assertions;
- exit code `0` for pass, `1` for an executed quality regression, and `2` for invalid input/configuration;
- optional `--output` archival while still emitting the identical report to stdout.

Default acceptance remains deliberately strict for the deterministic fixture set:

- exact value accuracy = 1.00;
- mean evidence IoU >= 0.80;
- evidence IoU@0.50 rate = 1.00;
- disposition accuracy = 1.00;
- projection accuracy = 1.00;
- finding-status accuracy = 1.00;
- unsupported assertions = 0.

### CLI regression coverage

Added `tests/test_benchmark_cli.py` covering:

- expected pass for the current three-case/six-property fixture manifest;
- aggregate metric and manifest-digest presence;
- a deliberate valid-but-wrong normalized value causing a case and overall gate failure;
- stable repeatable JSON rendering;
- fail-closed invalid threshold ranges;
- identical stdout/file report output;
- exit code `0` on pass, `1` on quality regression, and `2` on malformed manifest input.

### Packaging

Updated `pyproject.toml` with:

```toml
[project.scripts]
takekeeper-benchmark = "takekeeper.benchmark_cli:main"
```

This keeps the core dependency-free while allowing `pip install -e .` users to invoke the benchmark directly.

### Benchmark documentation

Added `BENCHMARK.md` documenting:

- installed and `PYTHONPATH` invocation paths;
- stable JSON/exit-code contract;
- default acceptance policy;
- report provenance fields;
- the rule that real-model truth labels must not be silently relaxed after observing candidate output;
- the distinction between deterministic safety-boundary validation and actual Gemini video-quality validation.

### README coherence pass

Refreshed `README.md` so it now accurately describes:

- the governed Gemini transport already present in the repository;
- replacement-based current continuity state;
- the benchmark scorer and new CLI release gate;
- current ClickHouse/MCP/Gemini trust boundaries;
- current local and real-service validation commands;
- the remaining production gates rather than the now-stale pre-Gemini next milestone.

### Repository safety

- No GitHub Actions workflow was added, modified, triggered, or rerun.
- No credential, secret, paid service, destructive production operation, arbitrary SQL surface, or cross-tenant authority was introduced.
- Benchmark reports do not duplicate raw video, provider credentials, prompts, model rationales, or secrets.
- Trusted production/scene/take scope still comes from application input, never model output.

## Validation / results

- Files were written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.
- Implementation commits this run:
  - `8c09791cb5c2f4fcf4e3b26e3f23efe40e884f3d` — deterministic benchmark CLI/release gate;
  - `4e7491b48421ff159101d69ddd76dbcd5a81663f` — CLI regression suite;
  - `25f368262d5c8fcf8b11c6c485f904af5e4aeb75` — package console entrypoint;
  - `b66c8ee3fbf2594cb1e03c7a19963d42892d5877` — benchmark usage/report documentation;
  - `c4e3430f87aefbe6e1b6a18056d117af66a2a70e` — README coherence refresh.
- Attempted a clean checkout followed by the targeted benchmark tests:
  - `PYTHONPATH=src python -m unittest tests.test_multimodal_benchmark tests.test_benchmark_cli -v`
- The execution container still cannot resolve `github.com`; clone failed with `Could not resolve host: github.com` before Python started.
- Therefore the new suite is structurally reviewed but **not claimed as passing** in this environment.
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
15. Benchmark pass/fail policy is explicit and recorded in every report; thresholds must not be silently changed after observing a candidate.
16. Benchmark provenance includes the exact manifest SHA-256 and candidate model/version.
17. Live service claims require execution against the real service and are not inferred from mocks.

## Gates

- **Gate A — live ClickHouse:** implementation/harness coverage exists for memory, review, extraction retry, and scoped projection replacement; real-endpoint execution remains pending.
- **Gate B — continuity correctness:** deterministic comparison, application service, persistence adapter, MCP evidence reader, governed projection, and stale-state convergence are implemented.
- **Gate C — evidence/review:** durable evidence, stable finding identity, append-only review, authenticated bounded API, and operator console are implemented.
- **Gate D — editorial retrieval:** typed/bounded retrieval and SQL coverage exist; live official MCP execution remains pending.
- **Gate E — failure honesty:** extraction/persistence/MCP/review paths fail closed structurally; abstentions cannot become false mismatches.
- **Gate F — security:** tenant scope, parameter binding, read/write separation, authenticated review, trusted extraction scope, and replacement isolation are implemented structurally; live RBAC/write-denial proof remains pending.
- **Gate G — multimodal evidence:** governed extraction, provenance, retry safety, projection/replacement, Google transport, objective benchmark metrics, and a reusable JSON release gate are implemented; full local test execution, real labeled video assets, and live Gemini evaluation remain pending.

## Blockers / unknowns

1. The execution container cannot currently resolve `github.com` for a local checkout.
2. No reachable authorized ClickHouse endpoint is available in this run.
3. No Gemini/Vertex credentials or private/self-owned live video are available in this run.
4. Official MCP runtime/auth/version behavior and explicit write denial remain unmeasured against a live server.
5. Live `google-genai` model/schema/video behavior, latency, token usage, and provider failure modes remain unmeasured.
6. The current manifest is a deterministic response/evidence contract benchmark; actual fixed self-owned/generated video clips matching the labels still need to exist before measuring provider quality.
7. Media provenance currently fingerprints trusted URI + duration; a true content digest should be added when bytes are available at ingest.
8. Extensionless signed-media endpoints still require explicit trusted MIME/ingest metadata before the Google transport can support them safely.

## Highest-priority backlog

- Run the complete credential-free suite in a normal checkout and fix any concrete failures, starting with `tests.test_multimodal_benchmark`, `tests.test_benchmark_cli`, and `tests.test_google_genai_transport`.
- Add a deterministic local fixture-media generator that creates tiny self-owned synthetic clips corresponding to the fixed mug-hand/jacket-state truth labels without committing large binaries.
- Add a live-candidate benchmark path that swaps fixture responses for `GoogleGenAIExtractionTransport` while preserving the exact immutable truth manifest and the same JSON report schema.
- Execute one live private/self-owned video extraction with Google Gen AI / Vertex AI and archive the unchanged benchmark report.
- Execute projection-replacement and extraction-retry integration suites against disposable real ClickHouse.
- Start official `ClickHouse/mcp-clickhouse` read-only, inject the actual transport, prove continuity/editorial queries, and record explicit write denial.
- Add optional ingest-time media content hashing and trusted explicit MIME metadata.

## Single best next step

**Add a deterministic local fixture-media generator for the existing benchmark cases, producing tiny self-owned synthetic videos plus a content-digest manifest without committing bulky binary media. Then the same fixed truth labels can drive a future live Gemini candidate benchmark instead of evaluating response JSON alone.**

## Relevant implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
