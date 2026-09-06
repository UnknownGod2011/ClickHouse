# TakeKeeper Progress

## Current status

TakeKeeper now has the deterministic continuity core, in-memory and ClickHouse-backed production memory, an environment-gated real ClickHouse acceptance harness, bounded read-only ClickHouse MCP evidence access, stable continuity finding identities, append-only human review, an authenticated review API and operator console, a governed multimodal extraction/evaluation contract, append-only extraction provenance stores for both memory and ClickHouse, and a real-ClickHouse acceptance case for extraction reprocessing history. Live ClickHouse + official MCP + Gemini execution remains unproven in this environment because no authorized runtime endpoints or Google credentials are reachable here.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected the actual `UnknownGod2011/ClickHouse` repository through the authenticated GitHub connector.
- Read `tests/test_clickhouse_integration.py`, `src/takekeeper/extraction_store.py`, `src/takekeeper/extraction.py`, `tests/test_extraction_store.py`, and `sql/schema.sql`.
- Confirmed the previous single best next step was to bridge the new append-only extraction provenance contract into the disposable real-ClickHouse acceptance harness.
- Re-checked current ClickHouse guidance around insert deduplication/idempotency. ClickHouse 26.1 documents per-table insert deduplication and explicit deduplication tokens, which is relevant to a future retry-safe persistence hardening pass; TakeKeeper does not yet claim multi-table atomicity for extraction-run + observation inserts.

## Exact changes made this run

### Real ClickHouse extraction-provenance acceptance coverage

- Extended `tests/test_clickhouse_integration.py` to import and instantiate `ClickHouseExtractionProvenanceStore` against the disposable per-test-suite database.
- Added deterministic fixture helpers that run the same governed extraction validation path used by the credential-free extractor tests before persistence.
- Added `extraction_runs` and `extracted_observations` to per-test truncation so extraction history cannot leak between acceptance cases.
- Added `test_extraction_reprocessing_preserves_independent_history`.
- The new acceptance case appends two extraction runs for the same production/scene/take with different normalized mug-hand evidence (`left` then `right`).
- It proves both run IDs remain independently listable rather than one replacing the other.
- It proves each run's historical extracted observation remains independently queryable with its original normalized value.
- It asserts observation IDs differ across reprocessing runs, preserving run-scoped evidence identity.
- It performs a direct ClickHouse aggregate over `extracted_observations` and requires one persisted evidence row for each run ID.
- It reasserts tenant isolation by requiring a wrong-production read for a known run ID to return no observations.
- No destructive operation was added outside the disposable integration database; the harness still drops only its own randomly named temporary database.
- No GitHub Actions, paid services, secret material, or unrelated repository changes were introduced.

## Validation / results

- The modified integration harness was written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.
- The new test is guarded by the existing `TAKEKEEPER_CLICKHOUSE_INTEGRATION=1` flag and therefore cannot accidentally contact a real database during ordinary credential-free unit-test runs.
- The harness was structurally reviewed against the current `TakeExtractionRequest`, `GovernedMultimodalExtractor`, `ClickHouseExtractionProvenanceStore`, and schema contracts.
- This automation environment still does not provide a runnable local repository checkout, so the Python suite was **not executed and is not claimed as passing** in this run.
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
15. The real-DB integration harness must isolate extraction provenance state just as it isolates continuity/review state.
16. Extraction-run + extracted-observation persistence spans two ClickHouse tables and is not currently represented as transactionally atomic; retry/idempotency hardening must be explicit rather than implied.

## Gates

- **Gate A live ClickHouse integration:** HARNESS NOW COVERS CORE MEMORY + REVIEW + EXTRACTION PROVENANCE; live execution still NOT YET PROVEN.
- **Gate B continuity correctness:** CORE + APP SERVICE + CLICKHOUSE ADAPTER + ISOLATED REAL-DB HARNESS + MCP EVIDENCE READER IMPLEMENTED; live execution pending.
- **Gate C evidence/review:** durable evidence + stable finding identity + append-only review + authenticated bounded API + operator console IMPLEMENTED; live execution pending.
- **Gate D editorial retrieval:** SQL + isolated real-DB assertion + typed MCP reader IMPLEMENTED; live MCP execution pending.
- **Gate E failure honesty:** domain/persistence/MCP/review/extraction fail-closed behavior IMPLEMENTED; newest real-DB provenance case pending execution in a reachable environment.
- **Gate F security:** scoping + parameter binding + read/write credential separation + MCP result scope validation + authenticated review boundary + browser hardening + trusted extraction scope + tenant-scoped provenance reads IMPLEMENTED; live ClickHouse RBAC/write-denial proof pending.
- **Gate G multimodal evidence:** GOVERNED EXTRACTION CONTRACT + FIXTURE TRANSPORT + DETERMINISTIC EVALUATOR + APPEND-ONLY PROVENANCE PERSISTENCE + REAL-DB ACCEPTANCE CASE IMPLEMENTED; live Gemini transport and labeled-footage evaluation pending.

## Blockers / unknowns

1. No reachable authorized ClickHouse service from this automation environment.
2. No Gemini/Google runtime credentials.
3. No runnable local repository checkout is available here, so checked-in Python tests cannot currently be executed.
4. Actual ClickHouse server/client and official MCP runtime versions, auth, payload envelope, latency, row counts, and explicit write denial remain unmeasured.
5. No self-owned labeled demo footage exists yet.
6. `ClickHouseExtractionProvenanceStore` still has not been exercised against a real ClickHouse server; the acceptance case is now ready for that execution.
7. The media provenance fingerprint is based on trusted URI + duration; a future ingest layer should optionally add a true content digest when media bytes are locally available.
8. A concrete Gemini/Vertex transport should be added only behind `ExtractionTransport` and verified against current official API behavior before compatibility is claimed.
9. `ClickHouseExtractionProvenanceStore.append()` writes the run row and observation rows in separate inserts. A mid-write failure can therefore leave partial provenance unless retry/idempotency semantics are hardened; no multi-table atomicity claim should be made.

## Highest-priority backlog

- Run the complete credential-free Python suite in a normal checkout, especially `tests/test_extraction.py`, `tests/test_extraction_store.py`, and the integration module's import path, and fix concrete failures.
- Execute the real ClickHouse integration harness and record server/client versions and timings, including the new two-run provenance assertion.
- Harden extraction persistence retry semantics across the two ClickHouse tables, using deterministic identities and current ClickHouse insert-deduplication capabilities where appropriate, while preserving append-only history.
- Start official `ClickHouse/mcp-clickhouse` read-only, inject its real `run_query` transport, prove continuity/editorial results, and record explicit write denial.
- Add a concrete Gemini transport behind `ExtractionTransport`, using schema-constrained output and private/self-owned media only.
- Create a tiny self-owned labeled fixture set for mug-hand + jacket-state and add property-level evidence metrics.
- Add continuity evaluation over extracted observations so uncertain/missing evidence is explicitly proven not to become a mismatch.
- Add optional ingest-time media content hashing without requiring media upload to ClickHouse.

## Single best next step

**Harden `ClickHouseExtractionProvenanceStore.append()` for retry-safe partial-failure behavior across `extraction_runs` and `extracted_observations`. The newly added real-DB test proves normal append-only reprocessing; the next production risk is an interrupted two-table write leaving an orphaned run or duplicated evidence. Implement deterministic retry semantics and failure-injection tests without pretending ClickHouse provides cross-table transactional atomicity.**

## Sources / implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://clickhouse.com/blog/clickhouse-release-26-01
- https://clickhouse.com/blog/common-getting-started-issues-with-clickhouse
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/interactions-breaking-changes-may-2026
