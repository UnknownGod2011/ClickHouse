# TakeKeeper Progress

## Current status

TakeKeeper is a personal open-source production-memory system with deterministic continuity comparison, ClickHouse-backed production state, bounded read-only ClickHouse MCP access, append-only extraction/review provenance, governed multimodal extraction, fail-closed continuity projection, a Gemini/Vertex transport, objective multimodal benchmarks, deterministic synthetic-video generation, and a live external-media candidate benchmark path.

Machine continuity state remains replacement-based: only clear, sustained, non-abstaining `machine_high_confidence` evidence may become current continuity state. Later governed re-analysis can clear stale projected machine state for the exact trusted production/scene/take while preserving historical extraction provenance.

This run adds a production-media provenance boundary that distinguishes locator identity from actual byte identity and supports trusted explicit MIME metadata for extensionless private media.

## Inspected this run

- Read the previous `progress.md` completely before deciding what to change.
- Confirmed `UnknownGod2011/ClickHouse` on `main` is the intended repository and that the connected account has write permission.
- Inspected the repository tree and the current extraction/Gemini path, especially:
  - `src/takekeeper/extraction.py`;
  - `src/takekeeper/google_genai_transport.py`;
  - `src/takekeeper/extraction_store.py`;
  - `tests/test_google_genai_transport.py`.
- Confirmed the existing production provenance fingerprint in `extraction_store.py` is explicitly locator+duration identity, not a media content hash.
- Confirmed the Google transport currently infers MIME only from the URI path suffix, which blocks otherwise-valid extensionless signed/object URLs.
- Preserved all existing benchmark truth, continuity policy, tenant scope, ClickHouse/MCP boundaries, and Gemini structured-output validation rules.

## Exact changes made this run

### Trusted media provenance module

Added `src/takekeeper/media_provenance.py` with a dependency-free ingest contract.

It provides:

- `TrustedMediaProvenance` — redaction-safe media provenance containing locator SHA-256, duration, MIME type, optional content SHA-256, and optional byte size;
- `LocalMediaDigest` — content digest metadata for a local operator-owned media file;
- `resolve_video_mime_type()` — validates trusted `https://` / `gs://` locators and resolves an allow-listed video MIME type;
- `build_media_provenance()` — creates bounded provenance without copying a signed/private locator into the record;
- `hash_local_media()` — streams and hashes local media without uploading, mutating, deleting, or transcoding it.

Security and correctness behavior:

- rejects plaintext HTTP, local/FTP media locators, malformed GCS locators, embedded URL credentials, and oversized locators;
- supports extensionless private/signed media when the trusted ingest layer supplies explicit video MIME metadata;
- fails closed when explicit MIME metadata conflicts with an inferable URI/file suffix;
- allow-lists only the same video families currently supported by the Google transport;
- validates content SHA-256 as lowercase 64-character hex;
- prevents byte size from being presented without a content digest;
- local hashing rejects symlinks, non-regular files, empty files, files above a configurable size ceiling, and pathological chunk sizes;
- verifies the observed byte count still equals the pre-read file size to detect a simple class of in-place file changes while hashing;
- hashes the complete trusted locator, including signed query parameters, but stores only the digest so query secrets do not appear in downstream provenance objects.

The locator fingerprint remains explicitly **not** a content hash. Content SHA-256 is the stronger identity when ingest can access the original bytes.

### Regression coverage

Added `tests/test_media_provenance.py` covering:

- extensionless signed HTTPS + explicit `video/mp4`;
- normal suffix MIME inference;
- ambiguous locator rejection without trusted MIME metadata;
- MIME/suffix conflict rejection;
- unsafe URI rejection;
- signed-query non-disclosure in provenance object representation;
- content digest + byte-size recording;
- byte-size-without-digest rejection;
- malformed/uppercase/non-hex digest rejection;
- streamed local hashing and deterministic SHA-256;
- extensionless local media with trusted explicit MIME;
- symlink rejection;
- size ceilings;
- chunk-size bounds.

### Documentation

Added `MEDIA_PROVENANCE.md` documenting:

- locator identity versus byte identity;
- trusted MIME metadata for extensionless production media;
- safe local pre-upload hashing;
- a concrete ingest example;
- signed-URL logging restrictions;
- the remaining wiring step into `TakeExtractionRequest` / `ExtractionPrompt` / the Google transport.

### Repository safety

- No GitHub Actions workflow was added, modified, triggered, or rerun.
- No unrelated repository was touched.
- No credential, private media object, signed media map, paid service, ClickHouse endpoint, Gemini endpoint, object-storage endpoint, or destructive operation was used.
- The new local hashing helper has no upload/delete/transcode authority.

## Validation / results

Files were written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.

Implementation commits this run:

- `3037f436f56c340135376bcbfb8809c9574859b3` — trusted media provenance utilities;
- `c5773795fd9a5202f7f9aab34be82b326917d3f7` — media provenance regression tests;
- `97f8abe0631e1e80c346af150fcb177b5c11009a` — media provenance documentation.

A normal local checkout is still unavailable in this automation environment, so the new Python test module could not be executed here. The tests are therefore structurally reviewed but **not claimed as passing**. No GitHub Actions run was used as a workaround.

No live Gemini/Vertex request, real ClickHouse request, official MCP session, or actual production-media hash was performed in this run.

## Decisions locked

1. Official ClickHouse MCP remains read-only and is never reused for application writes or credential handling.
2. Trusted application writes use separately permissioned ClickHouse clients.
3. Agent-facing MCP access stays bounded to TakeKeeper-owned analytical operations; arbitrary agent SQL is not exposed.
4. Production/scene/take scope remains trusted application metadata and is never accepted from model output.
5. Only configured entity/property pairs and registry values can enter governed extraction.
6. Machine confidence is not human confirmation.
7. Extraction provenance is append-only; reprocessing creates a new run.
8. Multi-table extraction persistence is not represented as transactional; deterministic identity + reconciliation provide retry safety.
9. Continuity projection is stricter than extraction persistence: uncertain evidence may be retained historically but cannot become current continuity state.
10. Missing/abstaining projected evidence becomes `insufficient_evidence`, never a mismatch.
11. Governed re-analysis replaces current projected state only for the exact trusted take scope so stale evidence cannot survive a later abstention.
12. Google structured output is a formatting aid, not a trust boundary; responses are locally validated before persistence/projection.
13. The Google transport cannot choose tools, production scope, persistence operations, model identity, or media identity.
14. Evaluation reports value accuracy, evidence localization, disposition, projection, and continuity outcome independently.
15. Benchmark thresholds are explicit and must not be relaxed after observing a model candidate.
16. Benchmark provenance includes the exact truth-manifest SHA-256 and candidate model/version.
17. Synthetic benchmark video must not contain semantic text that leaks truth labels to OCR-capable models.
18. Generated media remains local-only by default; publication/upload is an explicit operator action.
19. Live media mapping remains separate from immutable benchmark truth and cryptographically binds to exact truth bytes.
20. Signed/private live URI values are not copied into benchmark reports.
21. Live-service quality claims require execution against the real service and are not inferred from mocks.
22. Locator fingerprints and content hashes are distinct provenance concepts; locator hashing must never be presented as proof of media bytes.
23. Explicit MIME metadata is trusted ingest metadata, not model output. MIME/suffix disagreement fails closed.
24. Local media hashing must not imply upload authority or weaken tenant/object-store authorization boundaries.

## Gates

- **Gate A — live ClickHouse:** implementation/harness coverage exists for memory, review, extraction retry, and scoped projection replacement; real-endpoint execution remains pending.
- **Gate B — continuity correctness:** deterministic comparison, application service, persistence adapter, MCP evidence reader, governed projection, and stale-state convergence are implemented.
- **Gate C — evidence/review:** durable evidence, stable finding identity, append-only review, authenticated bounded API, and operator console are implemented.
- **Gate D — editorial retrieval:** typed/bounded retrieval and SQL coverage exist; live official MCP execution remains pending.
- **Gate E — failure honesty:** extraction/persistence/MCP/review paths fail closed structurally; abstentions cannot become false mismatches.
- **Gate F — security:** tenant scope, parameter binding, read/write separation, authenticated review, trusted extraction scope, and replacement isolation are implemented structurally; live RBAC/write-denial proof remains pending.
- **Gate G — multimodal evidence:** governed extraction, provenance, retry safety, projection/replacement, Google transport, objective benchmark metrics, synthetic media, generated-byte provenance, live candidate runner, and trusted media provenance utilities are implemented; full local execution and live Gemini evaluation remain pending.

## Blockers / unknowns

1. A runnable local repository checkout is unavailable in this execution environment, so Python tests and ffmpeg rendering remain unexecuted here.
2. No reachable authorized disposable ClickHouse endpoint is available in this run.
3. No Gemini/Vertex credentials or uploaded trusted benchmark media are available in this run.
4. Official MCP runtime/auth/version behavior and explicit write denial remain unmeasured against a live server.
5. Live `google-genai` video/schema behavior, latency, token usage, and provider failure modes remain unmeasured.
6. The synthetic renderer's real Gemini quality remains an empirical question.
7. The new trusted MIME/content-hash metadata is not yet wired into `TakeExtractionRequest`, extraction persistence columns, or `GoogleGenAIExtractionTransport`; the current Google transport still requires a supported URI suffix.
8. Local hashing detects byte-count changes but cannot guarantee a writer did not replace bytes with identical length during hashing; production ingest should hash immutable/staged files or use object-generation/version guarantees.

## Highest-priority backlog

- Carry trusted MIME type and optional content SHA-256/byte size through `TakeExtractionRequest` and extraction provenance persistence, migrating the ClickHouse schema safely.
- Teach `GoogleGenAIExtractionTransport` to consume trusted explicit MIME metadata while retaining scheme/host/credential/video allow-list validation and MIME/suffix conflict checks.
- Run the complete credential-free suite plus actual `ffmpeg` fixture generation in a normal checkout.
- Run `takekeeper-live-benchmark` against one authorized Gemini/Vertex candidate using only generated self-owned media.
- Execute projection-replacement and extraction-retry integration suites against disposable real ClickHouse.
- Start official `ClickHouse/mcp-clickhouse` read-only, exercise TakeKeeper continuity/editorial operations, and record explicit write denial.
- Add candidate comparison tooling once at least two real live benchmark reports exist.

## Single best next step

**Wire the new trusted `mime_type`, optional `content_sha256`, and `byte_size` fields through `TakeExtractionRequest` → `ExtractionPrompt` → extraction provenance persistence → `GoogleGenAIExtractionTransport`. This removes the extensionless-private-media blocker and upgrades persisted extraction provenance from locator-only identity to real byte identity when ingest provides it, without requiring any external credential.**

## Relevant implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
