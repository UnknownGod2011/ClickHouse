# TakeKeeper Progress

## Current status

TakeKeeper has a deterministic continuity core, in-memory and ClickHouse-backed production memory, bounded read-only ClickHouse MCP evidence access, stable finding identities, append-only review, authenticated review API/operator console, governed multimodal extraction, append-only extraction provenance with retry reconciliation, an explicit fail-closed extraction-to-continuity projection boundary, and now a concrete optional Google Gen AI / Vertex AI extraction transport.

Machine-derived continuity state is replacement-based: only clear, sustained, non-abstaining `machine_high_confidence` observations become current continuity facts. A later abstaining re-analysis clears the stale current projection for that exact production/scene/take while historical extraction provenance remains append-only.

The Google transport is deliberately subordinate to this deterministic core: it can submit one trusted video URI plus a TakeKeeper-generated prompt to one configured model with JSON Schema-constrained output, but provider output is revalidated locally and cannot supply tenant/take scope, tools, persistence commands, review decisions, or continuity authority.

Live ClickHouse + official MCP + Gemini execution remains unproven in this environment because no authorized runtime endpoints or Google credentials are available.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected the authenticated `UnknownGod2011/ClickHouse` repository and current root/source/test layout.
- Read `src/takekeeper/extraction.py`, `src/takekeeper/__init__.py`, `pyproject.toml`, the current README, existing extraction/projection test inventory, and the prior replacement acceptance status.
- Confirmed the highest-priority backlog item was the concrete Google multimodal transport behind the existing `ExtractionTransport` protocol.
- Checked current official Google documentation for the `google-genai` Python SDK, JSON response schemas, URI media parts, Gemini video input, HTTPS/signed URL inputs, and Vertex AI client mode.

## Exact changes made this run

### Concrete Google Gen AI / Vertex AI transport

Added `src/takekeeper/google_genai_transport.py` with:

- `GoogleGenAIExtractionTransport`, implementing the existing callable `ExtractionTransport` shape;
- `GoogleGenAITransportConfig` with explicit model, temperature, and output-token bounds;
- `create_google_genai_client()` for optional Gemini Developer API or Vertex AI construction using the official `google-genai` package;
- lazy SDK import so TakeKeeper core import/test paths do not require Google dependencies or credentials;
- a narrow provider request containing exactly one trusted media part plus TakeKeeper's prompt;
- `response_mime_type=application/json` and `response_json_schema` from TakeKeeper's generated schema;
- no tools, function calling, code execution, arbitrary provider configuration, or model-selected external resources;
- removal of TakeKeeper-private `x-*` schema annotations before the provider request without mutating the local validation schema;
- fail-closed response handling when Google returns no usable text;
- redacted provider exceptions so transport internals/secrets are not copied into the exposed error message.

### Media URI boundary

The concrete transport now refuses ambiguous or unsafe media references before any model call:

- only `https://` and `gs://` are accepted;
- plaintext HTTP, FTP, local `file://`, and embedded URL credentials are rejected;
- GCS URIs require both bucket and object;
- the URI path must identify a supported video MIME type;
- signed HTTPS query parameters remain compatible with private object-storage delivery.

This transport intentionally does not upload local files or mint signed URLs; media ingest/object-storage permissions remain a separate application responsibility.

### Deterministic fake-SDK tests

Added `tests/test_google_genai_transport.py` without requiring `google-genai` or credentials. Coverage includes:

- exact bounded `generate_content` envelope;
- JSON response MIME type and schema use;
- absence of provider tools;
- provider-schema sanitization without local-schema mutation;
- full handoff through `GovernedMultimodalExtractor` for a high-confidence mug-hand observation;
- rejection of provider attempts to inject trusted scope fields;
- HTTPS/GCS video URI acceptance and unsafe/ambiguous URI rejection;
- provider exception redaction;
- missing/empty response failure;
- configuration bounds.

### Packaging and onboarding

- Added optional `gemini = ["google-genai>=1,<2"]` packaging extra.
- Exported the Google transport/config/client factory from `takekeeper.__init__`.
- Added `GEMINI_INTEGRATION.md` with Gemini Developer API and Vertex AI setup, media contract, structured-output boundary, trust model, testing instructions, and current official references.

### Repository safety

- No GitHub Actions workflow was added or triggered.
- No credentials, paid services, or destructive production operations were introduced.
- The model still has no arbitrary SQL/write surface and cannot select production scope.
- No live media was uploaded and no external production data was accessed.

## Validation / results

- Files were written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.
- Implementation commits this run include:
  - `9dde249fd68293a3ec44f9bcf0d05a3d7bcc34cf` — concrete Google Gen AI extraction transport;
  - `9a936cb7464ee6bc0bd90085298102f1751b776b` — deterministic fake-SDK regression suite;
  - `72a758228a285443eb6270c3cc3308fed4149552` — optional `google-genai` packaging extra;
  - `09227918ddf472c2dd0f6787792e3850a9369ad6` — public transport exports;
  - `c89b63dd70eb06af2d1724b259e93856e2d795e0` — Gemini/Vertex onboarding document.
- Attempted a clean public checkout followed by `PYTHONPATH=src python -m unittest tests.test_google_genai_transport -v`.
- The runtime could not resolve `github.com`, so cloning failed before Python started. The new suite is therefore structurally reviewed but **not claimed as passing**.
- No authorized Google credential/private test video was available, so no live Gemini or Vertex AI compatibility/latency/cost claim is made.

## Decisions locked

1. Official ClickHouse MCP remains read-only and is never reused for ingestion, persistence, review, or Google credentials.
2. Trusted application writes use separately permissioned ClickHouse clients.
3. Agent-facing MCP access stays bounded to TakeKeeper-owned analytical operations; arbitrary agent SQL is not exposed.
4. Production/scene/take scope is trusted application metadata and is never accepted from model output.
5. Only configured entity/property pairs and registry values can enter governed extraction.
6. `machine_high_confidence` is not human confirmation.
7. Extraction provenance is append-only; reprocessing creates a new run.
8. Extraction-run + extracted-observation writes are explicitly non-transactional across tables; deterministic identity + reconciliation provide retry safety.
9. Continuity projection is stricter than extraction persistence: uncertain evidence can be retained historically but cannot become current continuity fact state.
10. Missing/abstaining projected evidence becomes `insufficient_evidence`, never a mismatch.
11. Governed machine re-analysis replaces the current observation projection for the exact trusted take scope so stale evidence cannot survive a later abstention.
12. Cross-scope replacement is an error before mutation.
13. Google structured output is a provider formatting aid, not a trust boundary; every response is parsed and revalidated by `GovernedMultimodalExtractor`.
14. The Google transport cannot invoke tools/functions or choose media/scope; production object-storage ingest remains outside the model boundary.
15. Google credentials remain optional and are discovered/constructed only when the concrete integration is explicitly used.
16. Live ClickHouse/MCP/Gemini claims require execution against real services rather than inference from mocks.

## Gates

- **Gate A live ClickHouse integration:** harness covers core memory, review, extraction reprocessing, interrupted-write retry, and scoped current-projection replacement; execution against a real endpoint still pending.
- **Gate B continuity correctness:** deterministic core, app service, ClickHouse adapter, MCP evidence reader, governed extraction projection, and stale-state convergence path implemented.
- **Gate C evidence/review:** durable evidence, stable finding identity, append-only review, authenticated bounded API, and operator console implemented.
- **Gate D editorial retrieval:** SQL, isolated real-DB assertion, and typed MCP reader implemented; live MCP execution pending.
- **Gate E failure honesty:** domain/persistence/MCP/review/extraction fail-closed behavior, retry reconciliation, abstention-to-insufficient-evidence replacement, and Google transport failure redaction covered structurally.
- **Gate F security:** tenant scoping, parameter binding, read/write credential separation, MCP scope validation, authenticated review, trusted extraction scope, replacement isolation, and bounded Google media/request authority covered; live RBAC/write-denial proof pending.
- **Gate G multimodal evidence:** governed extraction, fixture evaluator, append-only provenance, retry-safe ClickHouse store, real-DB failure harness, projection boundary, current-projection replacement acceptance path, and concrete Google Gen AI/Vertex transport implemented; deterministic suite execution plus live private-media compatibility and labeled-footage evaluation remain pending.

## Blockers / unknowns

1. No reachable authorized ClickHouse service from this environment.
2. No Gemini/Google runtime credentials or private/self-owned live test video.
3. The runtime cannot resolve `github.com` for a local checkout, so the checked-in Python suite still needs execution in a normal development environment.
4. Actual ClickHouse server/client and official MCP runtime versions, auth envelopes, latency, explicit write denial, and disposable replacement behavior remain unmeasured.
5. Current live `google-genai` version/model compatibility, Vertex/Gemini auth envelope, video retrieval behavior, structured-schema acceptance, latency, token usage, and provider failure modes remain unmeasured.
6. No self-owned labeled demo footage exists yet.
7. ClickHouse insert deduplication is bounded by server/table configuration, so explicit reconciliation remains the correctness mechanism.
8. Media provenance currently fingerprints trusted URI + duration; ingest should optionally add a true content digest when local bytes are available.
9. MIME inference currently depends on the trusted URI path extension; extensionless signed-media endpoints need an explicit trusted MIME-type field or an ingest manifest before they can be supported safely.

## Highest-priority backlog

- Run the full credential-free Python suite in a normal checkout and fix concrete failures.
- Run `tests/test_google_genai_transport.py` specifically and correct any SDK-neutral contract issues.
- Execute one live private/self-owned video extraction with the optional `google-genai` integration, record exact SDK/model/backend, request compatibility, latency and token usage, and verify the returned payload passes the existing validator unchanged.
- Create a tiny self-owned labeled fixture set for mug-hand + jacket-state and add value/evidence/projection evaluation metrics.
- Execute `tests/test_projection_replacement_clickhouse.py` with `TAKEKEEPER_CLICKHOUSE_INTEGRATION=1` against a disposable ClickHouse endpoint and verify exact row counts.
- Start official `ClickHouse/mcp-clickhouse` read-only, inject its real `run_query` transport, prove continuity/editorial results, and record explicit write denial.
- Add optional ingest-time media content hashing without requiring media upload to ClickHouse.
- Add a trusted explicit media MIME field/manifest if production deployments need extensionless signed URLs.

## Single best next step

**Build a credential-free end-to-end multimodal evaluation fixture around the new Google transport contract: add a tiny self-owned/synthetic labeled take manifest (mug hand + jacket state), reusable extraction-response fixtures, and evaluation assertions that separately score normalized value, evidence-window overlap, disposition, and continuity projection. This gives live Gemini runs an objective acceptance target instead of merely checking that the SDK returns JSON.**

## Sources / implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/generate-content/file-input-methods
- https://ai.google.dev/gemini-api/docs/structured-output
