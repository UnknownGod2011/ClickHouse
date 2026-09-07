# TakeKeeper Progress

## Current status

TakeKeeper now has the deterministic continuity core, in-memory and ClickHouse-backed production memory, bounded read-only ClickHouse MCP evidence access, stable continuity finding identities, append-only human review, an authenticated review API and operator console, a governed multimodal extraction/evaluation contract, append-only extraction provenance stores, retry-safe two-table provenance reconciliation, and a disposable real-ClickHouse acceptance harness that now covers both reprocessing history and the two critical interrupted-write retry scenarios. Live ClickHouse + official MCP + Gemini execution remains unproven in this environment because no authorized runtime endpoints or Google credentials are reachable here.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected the actual `UnknownGod2011/ClickHouse` repository through the authenticated GitHub connector.
- Read `tests/test_clickhouse_integration.py` and `src/takekeeper/extraction_store.py` before implementation.
- Confirmed the previous single best next step was to exercise retry reconciliation through the disposable real-ClickHouse harness rather than adding more mock-only behavior.
- Confirmed `ClickHouseExtractionProvenanceStore.append()` already performs deterministic row reconciliation and table-scoped ClickHouse insert deduplication; the missing piece was acceptance coverage through the actual ClickHouse client path.

## Exact changes made this run

### Real-ClickHouse interrupted-write acceptance coverage

- Extended `tests/test_clickhouse_integration.py` with `_OneShotInsertFailureClient`, a thin delegating wrapper around the real ClickHouse client.
- The wrapper supports exactly two deterministic failure modes against a selected table:
  - `before`: raise before the first matching insert reaches ClickHouse.
  - `after`: delegate the insert to ClickHouse and then raise, simulating acknowledgement loss after the server has accepted the mutation.
- Reads and commands are delegated unchanged, so reconciliation queries still exercise the real ClickHouse server/client behavior when integration mode is enabled.
- Added `_extraction_counts()` to query authoritative row counts directly from `extraction_runs` and `extracted_observations` by tenant + run ID.

### Partial-write repair case

- Added `test_extraction_retry_repairs_failure_before_observation_persistence`.
- The first append persists the extraction-run row, then injects a timeout before the observation insert reaches ClickHouse.
- The test asserts the intermediate real-database state is exactly one run row and zero observation rows.
- An identical retry then uses the same store/wrapper, reconciles the existing immutable run, persists the missing observation, and must converge to exactly one run row and one observation row.
- The final observation is read through the production provenance store and checked for the expected normalized value.

### Acknowledgement-loss convergence case

- Added `test_extraction_retry_converges_after_acknowledgement_loss`.
- The first append sends the observation insert to the real ClickHouse client and only then injects a timeout, reproducing the ambiguous outcome where the caller did not receive success but the server may have committed the insert.
- The test asserts the post-failure state is already exactly one run row and one observation row.
- An identical retry must discover the existing immutable observation and complete without issuing a duplicate logical provenance record.
- The final direct ClickHouse count remains exactly one run and one observation, and the tenant-scoped provenance read returns one expected historical observation.

### Repository safety

- No GitHub Actions workflow was added or triggered.
- No destructive production path was introduced. The disposable integration database still uses its existing per-test `TRUNCATE` and class-level ephemeral database create/drop lifecycle only when the explicitly gated integration suite is run.
- The failure injector is test-only and does not affect runtime persistence code.

## Validation / results

- Changes were written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.
- Integration test code was structurally checked against the current `ClickHouseExtractionProvenanceStore` client usage: `query`, `insert`, and `command` are delegated with arbitrary positional/keyword arguments so `clickhouse-connect` settings such as `insert_deduplication_token` remain intact.
- The integration tests remain guarded by `TAKEKEEPER_CLICKHOUSE_INTEGRATION=1`; they cannot accidentally contact or mutate a ClickHouse service during normal credential-free test runs.
- This automation environment still does not provide a runnable local repository checkout, so the Python suite was **not executed and is not claimed as passing** in this run.
- The new real-ClickHouse cases were **not executed** because no authorized ClickHouse endpoint is reachable here. Their value is that the exact failure scenarios are now ready to execute unchanged against a disposable MergeTree database as soon as an endpoint is supplied.
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
15. Extraction-run + extracted-observation persistence is explicitly non-transactional across tables. Safety comes from deterministic identities, per-table insert deduplication tokens, immutable-payload verification, and retry reconciliation.
16. A retry may repair an identical partial provenance write, but it must never reinterpret conflicting same-ID data as equivalent.
17. Retry repair must remain append-only; cleanup mutations are not part of the normal provenance persistence path.
18. Acceptance tests for interrupted writes must assert intermediate server state as well as eventual convergence; final-state-only checks can hide materially different failure behavior.
19. Acknowledgement-loss acceptance must inject failure *after* delegating the insert to the real client so the ambiguity being tested is genuine rather than another pre-write timeout.

## Gates

- **Gate A live ClickHouse integration:** HARNESS COVERS CORE MEMORY + REVIEW + EXTRACTION REPROCESSING + INTERRUPTED-WRITE RETRY; live execution still NOT YET PROVEN.
- **Gate B continuity correctness:** CORE + APP SERVICE + CLICKHOUSE ADAPTER + ISOLATED REAL-DB HARNESS + MCP EVIDENCE READER IMPLEMENTED; live execution pending.
- **Gate C evidence/review:** durable evidence + stable finding identity + append-only review + authenticated bounded API + operator console IMPLEMENTED; live execution pending.
- **Gate D editorial retrieval:** SQL + isolated real-DB assertion + typed MCP reader IMPLEMENTED; live MCP execution pending.
- **Gate E failure honesty:** domain/persistence/MCP/review/extraction fail-closed behavior + retry reconciliation + real-DB failure-injection cases IMPLEMENTED; execution against a real server pending.
- **Gate F security:** scoping + parameter binding + read/write credential separation + MCP result scope validation + authenticated review boundary + browser hardening + trusted extraction scope + tenant-scoped provenance reads IMPLEMENTED; live ClickHouse RBAC/write-denial proof pending.
- **Gate G multimodal evidence:** GOVERNED EXTRACTION CONTRACT + FIXTURE TRANSPORT + DETERMINISTIC EVALUATOR + APPEND-ONLY PROVENANCE + RETRY-SAFE CLICKHOUSE RECONCILIATION + REAL-DB REPROCESSING/RETRY ACCEPTANCE CASES IMPLEMENTED; live Gemini transport and labeled-footage evaluation pending.

## Blockers / unknowns

1. No reachable authorized ClickHouse service from this automation environment.
2. No Gemini/Google runtime credentials.
3. No runnable local repository checkout is available here, so checked-in Python tests cannot currently be executed.
4. Actual ClickHouse server/client and official MCP runtime versions, auth, payload envelope, latency, row counts, and explicit write denial remain unmeasured.
5. No self-owned labeled demo footage exists yet.
6. The new failure-injection acceptance cases still need one execution against a real ClickHouse server to confirm the current `clickhouse-connect` version and server settings preserve the expected dedup/reconciliation behavior.
7. ClickHouse insert deduplication depends on server/table configuration and a bounded deduplication window. TakeKeeper therefore does not rely on server deduplication alone; explicit reconciliation remains required.
8. The media provenance fingerprint is based on trusted URI + duration; a future ingest layer should optionally add a true content digest when media bytes are locally available.
9. A concrete Gemini/Vertex transport should be added only behind `ExtractionTransport` and verified against current official API behavior before compatibility is claimed.

## Highest-priority backlog

- Run the complete credential-free Python suite in a normal checkout, especially `tests/test_extraction.py`, `tests/test_extraction_store.py`, and `tests/test_extraction_store_retry.py`, and fix concrete failures.
- Execute `tests/test_clickhouse_integration.py` against a disposable real ClickHouse service and record server/client versions and timings, including the new failure-before-write and acknowledgement-loss cases.
- Start official `ClickHouse/mcp-clickhouse` read-only, inject its real `run_query` transport, prove continuity/editorial results, and record explicit write denial.
- Add a concrete Gemini transport behind `ExtractionTransport`, using schema-constrained output and private/self-owned media only.
- Create a tiny self-owned labeled fixture set for mug-hand + jacket-state and add property-level evidence metrics.
- Add continuity evaluation over extracted observations so uncertain/missing evidence is explicitly proven not to become a mismatch.
- Add optional ingest-time media content hashing without requiring media upload to ClickHouse.

## Single best next step

**Add an explicit extraction-to-continuity projection/evaluation boundary that only promotes policy-eligible extracted observations into continuity analysis, then add deterministic tests proving abstentions, occluded evidence, weak confidence, and uncertain temporal support can never become continuity mismatches while high-confidence sustained evidence can.**

## Sources / implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://clickhouse.com/blog/clickhouse-release-26-01
- https://clickhouse.com/blog/common-getting-started-issues-with-clickhouse
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/interactions-breaking-changes-may-2026
