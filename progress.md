# TakeKeeper Progress

## Current status

TakeKeeper now has the deterministic continuity core, in-memory and ClickHouse-backed production memory, an environment-gated real ClickHouse acceptance harness, bounded read-only ClickHouse MCP evidence access, stable continuity finding identities, append-only human review, an authenticated review API and operator console, a governed multimodal extraction/evaluation contract, and append-only extraction provenance stores for both memory and ClickHouse. Live ClickHouse + official MCP + Gemini execution remains unproven in this environment because no authorized runtime endpoints or Google credentials are reachable here.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected the repository root and `src/takekeeper/` tree.
- Read `src/takekeeper/extraction.py`, `src/takekeeper/clickhouse_memory.py`, `sql/schema.sql`, `tests/test_extraction.py`, and `src/takekeeper/__init__.py`.
- Confirmed the previous highest-value unblocked task was append-only extraction-run and extracted-observation persistence.
- Confirmed existing application ClickHouse writes use a separately permissioned client and the official MCP boundary remains read-only.

## Exact changes made this run

### Append-only extraction provenance

- Added `src/takekeeper/extraction_store.py`.
- Added immutable `ExtractionRunRecord` and `ExtractedObservationRecord` contracts.
- Added `ExtractionProvenanceStore` protocol plus `InMemoryExtractionProvenanceStore` and `ClickHouseExtractionProvenanceStore` implementations.
- Persistence accepts both the trusted `TakeExtractionRequest` and validated `ExtractionRunResult`; it fails closed if production/scene/take scope, extractor model/version, prompt-schema version, or observation scope disagree.
- Added a stable SHA-256 `media_fingerprint` over the trusted media reference + duration. This is explicitly provenance identity, not a content hash; immutable/versioned media URIs are still preferred.
- Added deterministic UUIDv5 observation-record IDs derived from extraction run + entity/property identity.
- Reprocessing is append-only: a new run preserves prior evidence; duplicate `run_id` is rejected rather than overwriting history.
- Tenant isolation is enforced on observation history reads by requiring `production_id` together with `run_id`.
- ClickHouse persistence performs inserts only; no DELETE/UPDATE mutation path was added for extraction history.

### ClickHouse schema

- Added `takekeeper.extraction_runs` with production/scene/take scope, run ID, media URI/fingerprint, duration, extractor model/version, prompt-schema version, and creation time.
- Added `takekeeper.extracted_observations` with run linkage, deterministic observation ID, normalized/raw value, confidence, bounded evidence window, source/visibility/temporal metadata, disposition, verification state, rationale, and creation time.
- Both tables use `MergeTree` and production-first ordering for scoped retrieval.

### Tests/package surface

- Added `tests/test_extraction_store.py` covering:
  - reprocessing appends two independently queryable historical runs instead of overwriting;
  - duplicate run IDs are rejected;
  - trusted scope mismatch fails closed;
  - media provenance fingerprint changes when media reference or duration changes;
  - observation-history reads are tenant scoped.
- Exported the new provenance contracts/stores/helpers from `takekeeper.__init__`.
- No GitHub Actions, destructive repository operations, secrets, paid services, or unrelated repository changes were introduced.

## Validation / results

- Repository reads and writes were performed through the authenticated GitHub connector against `UnknownGod2011/ClickHouse` `main`.
- The new code and tests were reviewed structurally against the existing extraction and ClickHouse client contracts.
- This automation environment still does not provide a runnable local checkout, so `tests/test_extraction_store.py` and the complete suite were **not executed and are not claimed as passing** in this run.
- The real ClickHouse integration suite remains unexecuted because no authorized ClickHouse endpoint is reachable here.
- No Google/Gemini credential was available, so no live multimodal API claim is made.

## Decisions locked

1. Official ClickHouse MCP remains read-only and is never reused for ingestion, persistence, or review credentials.
2. Trusted application writes use separately permissioned ClickHouse clients.
3. Model-facing MCP access remains bounded to TakeKeeper-owned analytical operations; arbitrary agent SQL is not exposed.
4. Continuity finding identity is deterministic over logical scope and independent of mutable evidence/status.
5. Human decisions are append-only audit records and reviewer identity comes from authenticated context.
6. Multimodal output is candidate evidence, never automatic human truth.
7. Production/scene/take scope is trusted application metadata and is never accepted from model output.
8. Only configured entity/property pairs and registry values can enter the governed extraction path.
9. Machine-high-confidence remains distinct from human confirmation.
10. Extraction transport is injectable so fixtures, Gemini API, and future Vertex AI transports share one domain validation path.
11. Extraction history is append-only: reprocessing creates a new run and never silently replaces historical model evidence.
12. Extraction provenance records retain model version, extractor version, prompt-schema version, trusted media reference/fingerprint, evidence metadata, and run identity.
13. The media fingerprint identifies the configured media reference/version and duration; it must not be represented as a cryptographic content hash unless a future ingest path actually hashes media bytes.
14. Runtime MCP/auth/version/latency/write-denial claims must be measured in a real environment.

## Gates

- **Gate A live ClickHouse integration:** NOT YET PROVEN; adapters/schema/harness implemented, live execution pending.
- **Gate B continuity correctness:** CORE + APP SERVICE + CLICKHOUSE ADAPTER + ISOLATED REAL-DB HARNESS + MCP EVIDENCE READER IMPLEMENTED; live execution pending.
- **Gate C evidence/review:** durable evidence + stable finding identity + append-only review + authenticated bounded API + operator console IMPLEMENTED; live execution pending.
- **Gate D editorial retrieval:** SQL + isolated real-DB assertion + typed MCP reader IMPLEMENTED; live MCP execution pending.
- **Gate E failure honesty:** domain/persistence/MCP/review/extraction fail-closed behavior IMPLEMENTED; newest provenance tests pending execution in a runnable checkout.
- **Gate F security:** scoping + parameter binding + read/write credential separation + MCP result scope validation + authenticated review boundary + browser hardening + trusted extraction scope + tenant-scoped provenance reads IMPLEMENTED; live ClickHouse RBAC/write-denial proof pending.
- **Gate G multimodal evidence:** GOVERNED EXTRACTION CONTRACT + FIXTURE TRANSPORT + DETERMINISTIC EVALUATOR + APPEND-ONLY PROVENANCE PERSISTENCE IMPLEMENTED; live Gemini transport and labeled-footage evaluation pending.

## Blockers / unknowns

1. No reachable authorized ClickHouse service from this automation environment.
2. No Gemini/Google runtime credentials.
3. No runnable local repository checkout is available here, so checked-in Python tests cannot currently be executed.
4. Actual ClickHouse server/client and official MCP runtime versions, auth, payload envelope, latency, row counts, and explicit write denial remain unmeasured.
5. No self-owned labeled demo footage exists yet.
6. `ClickHouseExtractionProvenanceStore` has not yet been exercised against a real ClickHouse server.
7. The media provenance fingerprint is based on trusted URI + duration; a future ingest layer should optionally add a true content digest when media bytes are locally available.
8. A concrete Gemini/Vertex transport should be added only behind `ExtractionTransport` and verified against current official API behavior before compatibility is claimed.

## Highest-priority backlog

- Run the complete credential-free Python suite in a normal checkout, especially `tests/test_extraction.py` and `tests/test_extraction_store.py`, and fix concrete failures.
- Extend `tests/test_clickhouse_integration.py` to exercise `extraction_runs` + `extracted_observations` append-only persistence against a disposable ClickHouse database.
- Execute the real ClickHouse integration harness and record server/client versions and timings.
- Start official `ClickHouse/mcp-clickhouse` read-only, inject its real `run_query` transport, prove continuity/editorial results, and record explicit write denial.
- Add a concrete Gemini transport behind `ExtractionTransport`, using schema-constrained output and private/self-owned media only.
- Create a tiny self-owned labeled fixture set for mug-hand + jacket-state and add property-level evidence metrics.
- Add continuity evaluation over extracted observations so uncertain/missing evidence is explicitly proven not to become a mismatch.
- Add optional ingest-time media content hashing without requiring media upload to ClickHouse.

## Single best next step

**Extend the disposable real-ClickHouse acceptance harness to create/clear the two new provenance tables, append two extraction runs for the same take, and prove both historical runs and their evidence remain independently queryable. This is the most valuable bridge between the newly implemented append-only contract and production behavior; if no ClickHouse endpoint is reachable, the harness itself can still be implemented credential-free.**

## Sources / implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/interactions-breaking-changes-may-2026
