# TakeKeeper Progress

## Current status

TakeKeeper is a personal open-source production-memory system with a deterministic continuity core, in-memory and ClickHouse-backed state, bounded read-only ClickHouse MCP evidence access, append-only review and extraction provenance, authenticated review surfaces, governed multimodal extraction, fail-closed extraction-to-continuity projection, retry-safe persistence, and an optional Google Gen AI / Vertex AI transport.

Machine continuity state is replacement-based: only clear, sustained, non-abstaining `machine_high_confidence` evidence is eligible to become current continuity state. Later abstaining re-analysis clears stale current projection for the exact trusted production/scene/take while historical extraction provenance remains append-only.

The multimodal evaluation path now includes a deterministic release-gate CLI, a local synthetic-video generator, and a live-candidate runner. The live runner keeps benchmark truth immutable, maps cases to separately supplied trusted external media URIs, executes the same governed extractor/scoring path with Gemini/Vertex, fingerprints the media map, and deliberately omits signed/private URI values from reports.

Live ClickHouse, official MCP, Gemini/Vertex quality, and generated-video rendering remain intentionally unclaimed until exercised against authorized real services and a runnable local checkout.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Confirmed `UnknownGod2011/ClickHouse` on `main` is the intended repository and write permission is available.
- Inspected `src/takekeeper/benchmark_cli.py`, `src/takekeeper/extraction.py`, `src/takekeeper/google_genai_transport.py`, `tests/fixtures/multimodal_eval/manifest.json`, `pyproject.toml`, and `README.md`.
- Confirmed the previous single best next step was the live-candidate benchmark path rather than more deterministic fixture-only evaluation work.
- Preserved the existing benchmark truth labels, fixture responses, evidence windows, thresholds, and generated-media design.

## Exact changes made this run

### Live candidate benchmark runner

Added `src/takekeeper/live_candidate_benchmark.py`.

The runner:

- evaluates the existing immutable `takekeeper-multimodal-eval-v1` truth manifest without rewriting its fixture `media_uri` or `response` fields;
- accepts a separate `takekeeper-live-media-map-v1` JSON document that maps every benchmark case name to a trusted external media URI;
- requires the media map to carry the SHA-256 of the exact truth-manifest bytes and rejects mismatches before model invocation;
- requires an exact case-set match, rejecting missing and unexpected mappings before model invocation;
- bounds candidate identity fields and media URI length;
- routes every mapped take through `GovernedMultimodalExtractor`, so trusted production/scene/take scope, configured property/value registries, evidence bounds, allowed source types, visibility/temporal support, and confidence policy remain locally enforced;
- reuses the exact same `evaluate_benchmark_run` metrics and `BenchmarkThresholds` release-gate policy as the deterministic benchmark;
- records the candidate model/version, truth-manifest SHA-256, media-map SHA-256, and `external_media_candidate` run mode;
- never emits live media URI values in the report, avoiding leakage of signed HTTPS query parameters/private object names;
- contains no upload, deletion, ClickHouse write, or MCP write path.

### Gemini / Vertex CLI

Exposed a new console command:

```text
takekeeper-live-benchmark
```

The CLI composes `create_google_genai_client` + `GoogleGenAIExtractionTransport` and supports both Gemini Developer API SDK credential discovery and Vertex AI via `--vertex-ai` with project/location from flags or `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION`.

API keys are intentionally not accepted as command-line options. Provider/credential exceptions that are not bounded local validation errors are reduced to exception-class names at the CLI boundary instead of blindly copying provider exception strings that may contain request metadata.

### Regression coverage

Added `tests/test_live_candidate_benchmark.py` covering:

- execution through the same governed extraction/scoring path with externally mapped media;
- exact manifest/media-map SHA-256 provenance;
- candidate identity replacing fixture-only model metadata;
- signed media URI/query-secret non-disclosure in reports;
- manifest-digest mismatch rejection before transport invocation;
- missing/unexpected case rejection before transport invocation;
- explicit threshold regression behavior;
- bounded media URI length.

Tests inject `FixtureExtractionTransport`, so they require no Google credentials or network access once a checkout exists.

### Packaging and documentation

Updated `pyproject.toml` with:

```toml
takekeeper-live-benchmark = "takekeeper.live_candidate_benchmark:main"
```

Added `LIVE_BENCHMARK.md` covering:

- the separate media-map contract;
- Developer API and Vertex AI usage;
- immutable-truth discipline;
- report and provenance handling;
- URI secrecy behavior;
- absence of upload authority;
- live-quality claims and security boundaries.

Updated `README.md` so current capabilities, repository map, local commands, safety boundaries, and production gates include the live-candidate path rather than listing it as future work.

### Repository safety

- No GitHub Actions workflow was added, modified, triggered, or rerun.
- No provider credential, signed media map, private media, secret, paid service, destructive operation, or unrelated repository was touched.
- No automatic media upload was added.
- Trusted production/scene/take scope and benchmark truth remain application-owned rather than model-owned.

## Validation / results

- Files were written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.
- Implementation commits this run:
  - `76ab85ed66cb08c8daf1e8070a90dc4e155ec4a7` — live candidate benchmark runner;
  - `9f717bf16c024d7358d1df8ec3d767f777ee8a4f` — live benchmark regression coverage;
  - `823b696be0e83da52463e04d88dfe0958e303475` — live benchmark console entrypoint;
  - `fe1768a649360610b87df36ccbf53a95d95c0a59` — live benchmark documentation;
  - `a5a9b3bdc53cb5affea384500a0872edf01f24b8` — README coherence update.
- Attempted a clean checkout and targeted execution:
  - `PYTHONPATH=src python -m unittest tests.test_live_candidate_benchmark tests.test_multimodal_benchmark tests.test_benchmark_cli -v`
- The execution container failed before Python started because `github.com` DNS resolution remains unavailable: `Could not resolve host: github.com`.
- Therefore the new tests are structurally reviewed but **not claimed as passing** in this environment.
- No live Gemini/Vertex request, real ClickHouse request, official MCP session, or actual ffmpeg rendering was made.

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
13. The Google transport cannot choose tools, production scope, persistence operations, or media identity.
14. Evaluation reports independent metrics for value, evidence localization, disposition, projection, and continuity outcome rather than one blended AI-accuracy score.
15. Benchmark pass/fail policy is explicit and recorded in every report; thresholds must not be silently changed after observing a candidate.
16. Benchmark provenance includes the exact truth-manifest SHA-256 and candidate model/version.
17. Synthetic benchmark video must not contain semantic text that leaks the truth label to OCR-capable models.
18. Generated media is local-only by default; publication/upload is an explicit operator action.
19. Generated-media content digests identify exact bytes, while ffmpeg version is separately recorded because cross-version binary reproducibility is not assumed.
20. Live media mapping is separate from immutable benchmark truth and must cryptographically bind to the exact truth-manifest bytes.
21. Signed/private live URI values are not copied into benchmark reports; only the media-map digest is recorded.
22. Live service claims require execution against the real service and are not inferred from mocks.

## Gates

- **Gate A — live ClickHouse:** implementation/harness coverage exists for memory, review, extraction retry, and scoped projection replacement; real-endpoint execution remains pending.
- **Gate B — continuity correctness:** deterministic comparison, application service, persistence adapter, MCP evidence reader, governed projection, and stale-state convergence are implemented.
- **Gate C — evidence/review:** durable evidence, stable finding identity, append-only review, authenticated bounded API, and operator console are implemented.
- **Gate D — editorial retrieval:** typed/bounded retrieval and SQL coverage exist; live official MCP execution remains pending.
- **Gate E — failure honesty:** extraction/persistence/MCP/review paths fail closed structurally; abstentions cannot become false mismatches.
- **Gate F — security:** tenant scope, parameter binding, read/write separation, authenticated review, trusted extraction scope, and replacement isolation are implemented structurally; live RBAC/write-denial proof remains pending.
- **Gate G — multimodal evidence:** governed extraction, provenance, retry safety, projection/replacement, Google transport, objective benchmark metrics, deterministic release gate, synthetic-media generation, generated-byte provenance, and a live external-media candidate runner are implemented; full local execution and live Gemini evaluation remain pending.

## Blockers / unknowns

1. The execution container cannot currently resolve `github.com` for a local checkout.
2. Actual ffmpeg/x264 rendering has not been executed in this runtime because a runnable checkout could not be obtained.
3. No reachable authorized ClickHouse endpoint is available in this run.
4. No Gemini/Vertex credentials or uploaded trusted benchmark media are available in this run.
5. Official MCP runtime/auth/version behavior and explicit write denial remain unmeasured against a live server.
6. Live `google-genai` model/schema/video behavior, latency, token usage, and provider failure modes remain unmeasured.
7. The synthetic renderer is intentionally simple; whether Gemini can reliably infer mug-hand and jacket-state geometry from the generated clips is an empirical live-candidate question, not yet proven.
8. Production-media provenance still fingerprints trusted URI + duration; true content hashing is currently implemented only for locally generated evaluation media.
9. Extensionless signed-media endpoints still require explicit trusted MIME/ingest metadata before the Google transport can support them safely.

## Highest-priority backlog

- Run the complete credential-free suite and `takekeeper-generate-fixture-media` in a normal checkout with ffmpeg, then inspect the generated clips and digests.
- Upload only generated self-owned benchmark clips to a trusted private media location, create the external media map, run `takekeeper-live-benchmark` with Gemini/Vertex, and archive both provenance reports.
- Execute projection-replacement and extraction-retry integration suites against disposable real ClickHouse.
- Start official `ClickHouse/mcp-clickhouse` read-only, inject the actual transport, prove continuity/editorial queries, and record explicit write denial.
- Add optional ingest-time media content hashing and trusted explicit MIME metadata for real production media.
- Add repeat-run candidate comparison tooling once at least two real live benchmark reports exist, including latency/token/cost metadata gathered without weakening report secrecy.

## Single best next step

**Run the full credential-free suite plus actual `ffmpeg` fixture generation in a normal checkout, then use the generated self-owned clips with `takekeeper-live-benchmark` against one authorized Gemini/Vertex model and archive the benchmark report together with `media-manifest.json`. This is now the shortest path to replacing structural confidence with measured multimodal quality.**

## Relevant implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
