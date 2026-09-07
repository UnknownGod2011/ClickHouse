# TakeKeeper

**Production memory and continuity intelligence for film, television, and creator teams.**

TakeKeeper turns recorded takes into structured, evidence-backed production memory. A governed Gemini/Google Gen AI extraction adapter can analyze trusted media, ClickHouse stores durable observations and review history, deterministic continuity logic detects mismatches, and the official `ClickHouse/mcp-clickhouse` server is the bounded read-side bridge for production/editorial agents.

This repository is a personal open-source project.

## What works today

- Deterministic continuity comparison with explicit `mismatch`, `needs_confirmation`, `insufficient_evidence`, and `missing_baseline` outcomes.
- In-memory and ClickHouse-backed production-memory adapters with trusted tenant/scene/take scoping.
- Replacement-based current machine state: later abstaining re-analysis clears stale projected observations for the exact take while append-only extraction provenance is retained.
- Governed multimodal extraction with configured entity/property registries, bounded evidence windows, confidence/disposition policy, local response validation, and fail-closed extraction-to-continuity projection.
- Optional Google Gen AI / Vertex AI video transport behind the same extraction boundary; missing provider credentials do not break the deterministic core.
- Retry-safe extraction persistence and disposable real-ClickHouse acceptance harnesses for persistence/reconciliation and scoped replacement semantics.
- Hard-constrained ClickHouse analytical query builders plus a bounded `McpEvidenceReader` for the official MCP `run_query` tool. Arbitrary model-authored SQL is not exposed.
- Stable deterministic finding IDs, append-only human review history, authenticated review API, and a dependency-free same-origin operator console.
- A credential-free multimodal benchmark that measures normalized-value accuracy, temporal evidence IoU, extraction disposition, projection eligibility, final continuity status, and unsupported assertions independently.
- A deterministic benchmark CLI/release gate that emits stable JSON and exits non-zero on quality regression.
- A local synthetic-media generator that renders text-free self-owned MP4 fixtures from the immutable benchmark truth and records manifest/artifact SHA-256 provenance without committing video binaries.
- A live-candidate benchmark runner that maps those immutable benchmark cases to trusted external `https://`/`gs://` media, executes the Google transport through the same governed extractor, and preserves the same scoring/release-gate contract without leaking signed media URIs into reports.

Live ClickHouse, official MCP, and Gemini/Vertex behavior is only considered proven after execution against authorized real services; fixture tests are not presented as live-service validation.

## Repository map

- `src/takekeeper/extraction.py` — governed extraction contract and local validation.
- `src/takekeeper/google_genai_transport.py` — optional Google Gen AI / Vertex AI multimodal transport.
- `src/takekeeper/extraction_projection.py` — strict evidence-to-current-continuity projection boundary.
- `src/takekeeper/multimodal_benchmark.py` — independent benchmark metrics.
- `src/takekeeper/benchmark_cli.py` — stable JSON deterministic benchmark runner and release gate.
- `src/takekeeper/live_candidate_benchmark.py` — external-media Gemini/Vertex candidate runner using the same benchmark truth and scoring contract.
- `src/takekeeper/fixture_media.py` — local deterministic synthetic-video renderer and content-provenance manifest.
- `src/takekeeper/continuity.py` — deterministic continuity comparison.
- `src/takekeeper/memory.py` / `clickhouse_memory.py` — memory protocol and ClickHouse persistence.
- `src/takekeeper/extraction_store.py` — extraction provenance/reconciliation persistence.
- `src/takekeeper/mcp_reader.py` — bounded read-only official-MCP adapter.
- `src/takekeeper/review.py`, `review_api.py`, `review_console.py` — human review boundary and UI.
- `src/takekeeper/service.py` — scoped ingest/analyze/persist orchestration.
- `src/takekeeper/queries.py` — bounded analytical query contracts.
- `sql/schema.sql` / `sql/seed_demo.sql` — durable schema and deterministic Scene 28 demo fixture.
- `tests/fixtures/multimodal_eval/manifest.json` — labeled credential-free multimodal benchmark manifest.
- `BENCHMARK.md` — benchmark semantics, thresholds, and usage.
- `FIXTURE_MEDIA.md` — generated-video workflow and content-digest provenance contract.
- `LIVE_BENCHMARK.md` — external media map, Gemini/Vertex live evaluation, and provenance/security contract.
- `GEMINI_INTEGRATION.md` — provider setup and transport trust boundary.
- `progress.md` — exact implementation handoff and next step.

## Run the credential-free suite

Python 3.11+ is sufficient for the core:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Run the multimodal benchmark gate

Without installation:

```bash
PYTHONPATH=src python -m takekeeper.benchmark_cli \
  tests/fixtures/multimodal_eval/manifest.json
```

Or install the local package and use the console entry point:

```bash
pip install -e .
takekeeper-benchmark tests/fixtures/multimodal_eval/manifest.json
```

The benchmark emits `takekeeper-multimodal-benchmark-report-v1` JSON to stdout. Exit code `0` means all thresholds passed, `1` means the benchmark executed but quality regressed, and `2` means the benchmark input/configuration was invalid. Use `--output <path>` to archive the exact same stable report locally. See `BENCHMARK.md` for the full metric contract.

The checked-in deterministic gate currently requires exact value/disposition/projection/finding correctness, evidence IoU@0.50 of 100%, mean evidence IoU of at least 0.80, and zero unsupported assertions. Real-model thresholds may be changed explicitly for experiments, but the report records the thresholds used; do not relabel truth after observing a model candidate.

## Generate self-owned benchmark video

`ffmpeg` with `libx264` is required; no cloud credentials are needed:

```bash
PYTHONPATH=src python -m takekeeper.fixture_media \
  tests/fixtures/multimodal_eval/manifest.json
```

After installation, the equivalent command is:

```bash
takekeeper-generate-fixture-media \
  tests/fixtures/multimodal_eval/manifest.json
```

Generated clips and `media-manifest.json` land under `.takekeeper/generated-eval-media/` by default. That directory is ignored by Git. The renderer does not place semantic labels in the video; it represents mug-hand state, jacket state, and deliberate occlusion using geometry only. The generated manifest records the exact truth-manifest digest, ffmpeg provenance, artifact sizes, and SHA-256 of every MP4. See `FIXTURE_MEDIA.md`.

## Evaluate a live Gemini / Vertex candidate

Keep the truth manifest unchanged. Upload only self-owned generated clips to a trusted private location outside TakeKeeper, then create a separate `takekeeper-live-media-map-v1` JSON that maps every benchmark case name to its trusted `gs://` or supported `https://` video URI and contains the SHA-256 of the exact truth manifest.

Install the optional provider dependency and run:

```bash
pip install -e '.[gemini]'

takekeeper-live-benchmark \
  tests/fixtures/multimodal_eval/manifest.json \
  /secure/path/live-media-map.json \
  --model <gemini-model-id> \
  --extractor-version <candidate-label> \
  --output .takekeeper/live-benchmark-report.json
```

Add `--vertex-ai` for Vertex AI; project/location may come from `--project` / `--location` or `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION`. Provider API keys are intentionally not accepted as command-line flags.

The runner fingerprints the media-map bytes but never emits its URI values into the report, because signed HTTPS entries may contain secrets. It has no upload primitive and continues to use `GovernedMultimodalExtractor` for local scope/property/value/evidence validation before scoring. See `LIVE_BENCHMARK.md`.

## ClickHouse application path

Install the official client extra:

```bash
pip install -e '.[clickhouse]'
```

Construct the official client outside the domain layer and inject it into TakeKeeper:

```python
import clickhouse_connect
from takekeeper import ClickHouseProductionMemory

client = clickhouse_connect.get_client(
    host="localhost",
    port=8123,
    username="takekeeper_app",
    password="...",
)
memory = ClickHouseProductionMemory(client)
```

Use a separately permissioned application credential for trusted writes. Do **not** reuse the agent/MCP credential.

The opt-in real ClickHouse tests are skipped by default. Only enable them against a disposable/local or otherwise explicitly authorized instance because the harness creates and drops an isolated temporary database.

```bash
TAKEKEEPER_CLICKHOUSE_INTEGRATION=1 \
CLICKHOUSE_HOST=localhost \
CLICKHOUSE_PORT=8123 \
CLICKHOUSE_USER=default \
CLICKHOUSE_PASSWORD='' \
PYTHONPATH=src python -m unittest tests.test_clickhouse_integration -v
```

For ClickHouse Cloud, use the service endpoint/credentials supplied by ClickHouse and set secure transport as documented by the client.

## ClickHouse MCP boundary

The official `ClickHouse/mcp-clickhouse` connection is a read-only analytical boundary. Keep `CLICKHOUSE_ALLOW_WRITE_ACCESS=false` and use a distinct least-privilege credential.

`McpEvidenceReader` accepts a host-supplied MCP `call_tool` transport and only invokes TakeKeeper-owned, parameterized analytical operations. It validates production/scene/take identifiers again on returned rows and fails closed on malformed results, tool errors, scope drift, impossible confidence, or invalid evidence windows. Agent-facing arbitrary SQL is intentionally not exposed.

## Gemini / Vertex AI boundary

Install provider support only when needed:

```bash
pip install -e '.[gemini]'
```

`GoogleGenAIExtractionTransport` handles provider communication, but provider JSON is never trusted directly. `GovernedMultimodalExtractor` still enforces configured properties/values, trusted production scope, evidence bounds, allowed source types, visibility/temporal support, and confidence policy before persistence or continuity projection.

Only clear, sustained, non-abstaining `machine_high_confidence` observations may become current machine continuity facts. Occluded, weak, transient, or otherwise uncertain evidence remains historical evidence and produces `insufficient_evidence` rather than a fabricated mismatch.

See `GEMINI_INTEGRATION.md` for Developer API / Vertex AI setup and media URI constraints.

## Human review boundary

Continuity findings use deterministic identities derived from trusted production, scene, take, entity, and property scope. Human decisions are append-only.

The authenticated WSGI API exposes only bounded context reads and `confirmed`, `rejected`, or `needs_followup` decisions. Reviewer identity is derived from the configured identity provider rather than caller-supplied actor IDs. `ReviewConsoleApp` provides a same-origin dependency-free UI without adding a broader mutation primitive.

## Demo workflow

The deterministic `glass-house` Scene 28 fixture contains continuity and editorial examples across takes. Apply `sql/schema.sql`, then `sql/seed_demo.sql` to an authorized ClickHouse instance to exercise the real persistence/read path.

## Safety and data boundaries

- ClickHouse owns durable structured production facts; raw media should live in object storage.
- Production/scene/take scope comes from trusted application metadata, never from model output.
- Machine perception is candidate evidence, not automatic human truth.
- Extraction history is append-only; current machine projection is scoped replacement state.
- Missing/abstaining evidence cannot become a false continuity mismatch.
- Trusted writes and agent-facing MCP reads use separate credentials and capabilities.
- Dynamic database identifiers are validated; values are parameter-bound.
- Generated benchmark media is local-only by default and has no automatic upload path.
- Live benchmark URI maps are operator-owned external inputs and signed/private URI values are not copied into reports.
- No credential, API key, raw private media, or secret belongs in the repository or benchmark reports.

## Next production gates

1. Run the full credential-free suite plus actual fixture-media rendering in a normal checkout and fix any concrete failures.
2. Upload only the generated self-owned clips to a trusted private media location, execute one live Gemini/Vertex candidate with `takekeeper-live-benchmark`, and archive both benchmark JSON and generated-media digests.
3. Execute the disposable ClickHouse integration suites against a real authorized instance.
4. Start official `ClickHouse/mcp-clickhouse` read-only and record actual auth/transport/version behavior, query latency, result shape, and explicit write denial.
5. Add optional ingest-time content hashing and trusted MIME metadata for production media so provenance can move beyond URI + duration fingerprints.

## References

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output

## License

Apache-2.0. See `LICENSE`.