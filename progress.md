# TakeKeeper Progress

## Current status

TakeKeeper has a deterministic continuity core, in-memory and ClickHouse-backed production memory, bounded read-only ClickHouse MCP evidence access, stable finding identities, append-only review, authenticated review API/operator console, governed multimodal extraction, append-only extraction provenance with retry reconciliation, and an explicit fail-closed extraction-to-continuity projection boundary.

Machine-derived continuity state is replacement-based: only clear, sustained, non-abstaining `machine_high_confidence` observations become current continuity facts. A later abstaining re-analysis clears the stale current projection for that exact production/scene/take while historical extraction provenance remains append-only.

Live ClickHouse + official MCP + Gemini execution remains unproven in this environment because no authorized runtime endpoints or Google credentials are available.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected the authenticated `UnknownGod2011/ClickHouse` repository.
- Read the current ClickHouse production-memory adapter, continuity service, governed extraction validator, extraction projection boundary, in-memory memory contract, existing projection tests, and disposable real-ClickHouse integration harness.
- Confirmed the highest-priority gap was direct adapter + real-server acceptance coverage for `replace_observations()` and stale-projection removal.
- Verified the current replacement SQL uses parameter-bound `production_id`, `scene_id`, and `take_id` with synchronous mutation semantics; it does not interpolate tenant/take values into SQL.

## Exact changes made this run

### Scoped projection replacement acceptance suite

Added `tests/test_projection_replacement_clickhouse.py`.

Credential-free adapter tests now prove:

- an empty replacement still performs the required deletion, so an abstaining re-analysis can clear stale current state;
- replacement uses only bound production/scene/take parameters, including hostile tenant input;
- ClickHouse mutation execution is synchronous (`mutations_sync=1`), so analysis does not race a still-running delete;
- empty replacement performs no insert;
- cross-scope observations fail before any ClickHouse mutation or insert occurs.

A separately gated disposable real-ClickHouse acceptance test now proves the full governed flow:

1. Create a baseline (`hero_mug.hand = right`) for the target production/scene.
2. Insert unrelated observations in another take of the same production and in the same take ID of another production.
3. Run a high-confidence, clear, sustained extraction for target take `T47` with `hero_mug.hand = left`.
4. Verify it becomes one current projected observation and a persisted `mismatch`.
5. Re-run extraction with `unknown`, low confidence, occluded visibility, and unknown temporal support.
6. Verify projection becomes empty.
7. Verify target take current observations become exactly zero.
8. Verify continuity converges to one persisted `insufficient_evidence` finding with no observed value.
9. Verify the other take and other tenant observations remain untouched.

The real-server test creates a unique disposable database, applies the repository schema, and drops the database in teardown. It remains opt-in behind `TAKEKEEPER_CLICKHOUSE_INTEGRATION=1` and therefore adds no noisy CI workload.

### Repository safety

- No GitHub Actions workflow was added or triggered.
- No credentials, paid services, or destructive production operations were introduced.
- No arbitrary SQL surface was exposed to the model.
- All new real-ClickHouse writes are confined to a disposable test database.

## Validation / results

- New tests were written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.
- Commit adding the acceptance suite: `2da676d161007d12edf7a5ef3fca8882110c324e`.
- The credential-free adapter tests are structurally deterministic, but this runtime still does not provide a runnable checkout, so the checked-in Python suite was not executed and is not claimed as passing.
- The real-ClickHouse case is intentionally skipped unless `TAKEKEEPER_CLICKHOUSE_INTEGRATION=1`; no authorized ClickHouse endpoint was available in this run, so live mutation behavior is not claimed as measured.
- No Gemini/Google credential was available, so no live multimodal compatibility claim is made.

## Decisions locked

1. Official ClickHouse MCP remains read-only and is never reused for ingestion, persistence, or review credentials.
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
13. Live ClickHouse/MCP/Gemini claims require execution against real services rather than inference from mocks.

## Gates

- **Gate A live ClickHouse integration:** harness covers core memory, review, extraction reprocessing, interrupted-write retry, and now scoped current-projection replacement; execution against a real endpoint still pending.
- **Gate B continuity correctness:** deterministic core, app service, ClickHouse adapter, MCP evidence reader, governed extraction projection, and stale-state convergence path implemented.
- **Gate C evidence/review:** durable evidence, stable finding identity, append-only review, authenticated bounded API, and operator console implemented.
- **Gate D editorial retrieval:** SQL, isolated real-DB assertion, and typed MCP reader implemented; live MCP execution pending.
- **Gate E failure honesty:** domain/persistence/MCP/review/extraction fail-closed behavior, retry reconciliation, and abstention-to-insufficient-evidence replacement covered.
- **Gate F security:** tenant scoping, parameter binding, read/write credential separation, MCP scope validation, authenticated review, trusted extraction scope, and replacement isolation covered; live RBAC/write-denial proof pending.
- **Gate G multimodal evidence:** governed extraction, fixture evaluator, append-only provenance, retry-safe ClickHouse store, real-DB failure harness, projection boundary, and current-projection replacement acceptance path implemented; live Gemini transport and labeled-footage evaluation pending.

## Blockers / unknowns

1. No reachable authorized ClickHouse service from this environment.
2. No Gemini/Google runtime credentials.
3. A runnable local checkout is unavailable here, so the full credential-free test suite still needs execution in a normal development environment.
4. Actual ClickHouse server/client and official MCP runtime versions, auth envelopes, latency, explicit write denial, and disposable replacement behavior remain unmeasured.
5. No self-owned labeled demo footage exists yet.
6. ClickHouse insert deduplication is bounded by server/table configuration, so explicit reconciliation remains the correctness mechanism.
7. Media provenance currently fingerprints trusted URI + duration; ingest should optionally add a true content digest when local bytes are available.

## Highest-priority backlog

- Run the full credential-free Python suite in a normal checkout and fix concrete failures.
- Execute `tests/test_projection_replacement_clickhouse.py` with `TAKEKEEPER_CLICKHOUSE_INTEGRATION=1` against a disposable ClickHouse endpoint and verify exact row counts.
- Start official `ClickHouse/mcp-clickhouse` read-only, inject its real `run_query` transport, prove continuity/editorial results, and record explicit write denial.
- Add a concrete current Gemini or Vertex AI transport behind `ExtractionTransport` using schema-constrained output and private/self-owned media.
- Create a tiny self-owned labeled fixture set for mug-hand + jacket-state and add value/evidence/projection evaluation metrics.
- Add optional ingest-time media content hashing without requiring media upload to ClickHouse.

## Single best next step

**Implement and test the concrete Gemini/Google transport behind the existing `ExtractionTransport` boundary using current official structured-output + video-understanding APIs, while keeping credentials optional and adding deterministic fake-SDK tests so TakeKeeper gains a real multimodal integration path without weakening the existing extraction validator.**

## Sources / implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
