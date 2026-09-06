# TakeKeeper Progress

## Current status

TakeKeeper now has the deterministic continuity core, in-memory and ClickHouse-backed production memory, bounded read-only ClickHouse MCP evidence access, stable continuity finding identities, append-only human review, an authenticated review API and operator console, a governed multimodal extraction/evaluation contract, append-only extraction provenance stores, a real-ClickHouse reprocessing acceptance case, and retry-safe reconciliation for the two-table extraction provenance write path. Live ClickHouse + official MCP + Gemini execution remains unproven in this environment because no authorized runtime endpoints or Google credentials are reachable here.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected the actual `UnknownGod2011/ClickHouse` repository through the authenticated GitHub connector.
- Read `src/takekeeper/extraction_store.py`, `src/takekeeper/clickhouse_memory.py`, and `tests/test_extraction_store.py` before implementation.
- Confirmed the previous single best next step was to harden `ClickHouseExtractionProvenanceStore.append()` against interrupted writes between `extraction_runs` and `extracted_observations`.
- Re-checked current official ClickHouse guidance. ClickHouse documents insert-time deduplication for MergeTree-family tables and explicit insert deduplication tokens; deduplication is table-scoped, so TakeKeeper still does not claim cross-table transactional atomicity.

## Exact changes made this run

### Retry-safe extraction provenance persistence

- Reworked `ClickHouseExtractionProvenanceStore.append()` from a duplicate-precheck followed by two blind inserts into an explicit reconciliation workflow.
- The store now computes the desired immutable run/observation records before writing and looks up any existing row by tenant-scoped deterministic identity.
- If no run row exists, it inserts the run with a deterministic `insert_deduplication_token` and `insert_deduplicate=1`.
- If an identical run row already exists, the retry resumes instead of being rejected as a duplicate.
- If a same-ID run already exists with different immutable provenance (scope, media reference/fingerprint, duration, model, extractor version, or schema version), persistence fails closed.
- Each extracted observation is reconciled independently by deterministic observation ID. Missing observations are inserted; identical observations are accepted as completed retry work; same-ID payload drift fails closed.
- Each observation insert uses its own deterministic ClickHouse deduplication token. This means acknowledgement-loss retries reuse the same logical insert identity rather than producing a new mutation attempt.
- After reconciliation, the store queries all observation IDs for the run and requires the persisted ID set to exactly equal the expected ID set. Duplicate IDs, missing IDs, or unexpected extra IDs fail closed.
- Existing stored `created_at` is preserved when a retry resumes a previously written run/observation rather than being silently replaced.
- No DELETE, mutation, cleanup, or destructive repair path was introduced. Partial state is repaired only by appending the missing deterministic rows.
- The in-memory store retains its stricter duplicate-run behavior as the simple reference implementation; the ClickHouse adapter adds retry semantics specifically because its write path spans independent server operations.

### Failure-injection regression tests

- Added `tests/test_extraction_store_retry.py` with a stateful ClickHouse-client fake.
- Added a case where the run row is persisted but the first observation insert fails before persistence; a second identical call repairs the missing observation without duplicating the run.
- Added an acknowledgement-loss case where the observation row is persisted and the client receives a timeout; a second identical call detects the completed row and does not duplicate it.
- Added fail-closed coverage for reusing a run/observation identity with changed immutable evidence.
- Added fail-closed coverage for unexpected persisted observations attached to a known run.
- Added an assertion that both run and observation writes carry deterministic 64-character SHA-256 deduplication tokens with insert deduplication enabled.
- The fake rejects destructive `command()` calls, proving this retry strategy does not rely on cleanup mutations.

## Validation / results

- The implementation and tests were written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.
- The new logic was structurally reviewed against the `ClickHouseClientLike` protocol and existing extraction record layout.
- Current official ClickHouse guidance supports the use of per-table insert deduplication tokens for safe retries; TakeKeeper deliberately layers explicit row reconciliation on top because its provenance operation spans two separate tables.
- This automation environment still does not provide a runnable local repository checkout, so the Python suite was **not executed and is not claimed as passing** in this run.
- The real ClickHouse integration suite remains unexecuted because no authorized ClickHouse endpoint is reachable here.
- No Google/Gemini credential was available, so no live multimodal API claim is made.
- No GitHub Actions workflow was added or triggered.

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
15. Extraction-run + extracted-observation persistence is explicitly non-transactional across tables. Safety comes from deterministic identities, per-table insert deduplication tokens, immutable-payload verification, and retry reconciliation.
16. A retry may repair an identical partial provenance write, but it must never reinterpret conflicting same-ID data as equivalent.
17. Retry repair must remain append-only; cleanup mutations are not part of the normal provenance persistence path.

## Gates

- **Gate A live ClickHouse integration:** HARNESS COVERS CORE MEMORY + REVIEW + EXTRACTION PROVENANCE; live execution still NOT YET PROVEN.
- **Gate B continuity correctness:** CORE + APP SERVICE + CLICKHOUSE ADAPTER + ISOLATED REAL-DB HARNESS + MCP EVIDENCE READER IMPLEMENTED; live execution pending.
- **Gate C evidence/review:** durable evidence + stable finding identity + append-only review + authenticated bounded API + operator console IMPLEMENTED; live execution pending.
- **Gate D editorial retrieval:** SQL + isolated real-DB assertion + typed MCP reader IMPLEMENTED; live MCP execution pending.
- **Gate E failure honesty:** domain/persistence/MCP/review/extraction fail-closed behavior + retry reconciliation IMPLEMENTED; real server execution pending.
- **Gate F security:** scoping + parameter binding + read/write credential separation + MCP result scope validation + authenticated review boundary + browser hardening + trusted extraction scope + tenant-scoped provenance reads IMPLEMENTED; live ClickHouse RBAC/write-denial proof pending.
- **Gate G multimodal evidence:** GOVERNED EXTRACTION CONTRACT + FIXTURE TRANSPORT + DETERMINISTIC EVALUATOR + APPEND-ONLY PROVENANCE + RETRY-SAFE CLICKHOUSE RECONCILIATION + REAL-DB ACCEPTANCE CASE IMPLEMENTED; live Gemini transport and labeled-footage evaluation pending.

## Blockers / unknowns

1. No reachable authorized ClickHouse service from this automation environment.
2. No Gemini/Google runtime credentials.
3. No runnable local repository checkout is available here, so checked-in Python tests cannot currently be executed.
4. Actual ClickHouse server/client and official MCP runtime versions, auth, payload envelope, latency, row counts, and explicit write denial remain unmeasured.
5. No self-owned labeled demo footage exists yet.
6. `ClickHouseExtractionProvenanceStore` still has not been exercised against a real ClickHouse server, including the new deduplication-token settings and partial-write retry behavior.
7. ClickHouse insert deduplication depends on server/table configuration and a bounded deduplication window. TakeKeeper therefore does not rely on server deduplication alone; the explicit reconciliation checks remain required.
8. The media provenance fingerprint is based on trusted URI + duration; a future ingest layer should optionally add a true content digest when media bytes are locally available.
9. A concrete Gemini/Vertex transport should be added only behind `ExtractionTransport` and verified against current official API behavior before compatibility is claimed.

## Highest-priority backlog

- Run the complete credential-free Python suite in a normal checkout, especially `tests/test_extraction.py`, `tests/test_extraction_store.py`, and `tests/test_extraction_store_retry.py`, and fix concrete failures.
- Extend the disposable real-ClickHouse harness with partial-write/acknowledgement-loss retry assertions using an injected failing client wrapper around the real ClickHouse client.
- Execute the real ClickHouse integration harness and record server/client versions and timings, including reprocessing and retry reconciliation.
- Start official `ClickHouse/mcp-clickhouse` read-only, inject its real `run_query` transport, prove continuity/editorial results, and record explicit write denial.
- Add a concrete Gemini transport behind `ExtractionTransport`, using schema-constrained output and private/self-owned media only.
- Create a tiny self-owned labeled fixture set for mug-hand + jacket-state and add property-level evidence metrics.
- Add continuity evaluation over extracted observations so uncertain/missing evidence is explicitly proven not to become a mismatch.
- Add optional ingest-time media content hashing without requiring media upload to ClickHouse.

## Single best next step

**Extend the disposable real-ClickHouse acceptance harness with a failure-injection client wrapper that simulates (a) failure after the run row but before observation persistence and (b) acknowledgement loss after an observation reaches ClickHouse, then prove an identical retry converges to exactly one run row and exactly the expected observation rows on a real MergeTree server.**

## Sources / implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://clickhouse.com/blog/clickhouse-release-26-01
- https://clickhouse.com/blog/common-getting-started-issues-with-clickhouse
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/interactions-breaking-changes-may-2026
