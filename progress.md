# TakeKeeper Progress

## Current status

TakeKeeper now has the deterministic continuity core, in-memory and ClickHouse-backed `ProductionMemory` adapters, an environment-gated real ClickHouse acceptance harness, a bounded fail-closed `McpEvidenceReader`, stable deterministic continuity finding identities, append-only human review storage, and a narrow authenticated WSGI review API. The review API exposes only current finding/evidence/history reads plus append-only bounded decisions; reviewer identity comes from a configured identity provider rather than request JSON. The trusted application write path remains structurally separate from the read-only agent/MCP path. Live ClickHouse + official MCP + Gemini execution is still unproven in this environment because no real ClickHouse service or Google runtime credential is reachable here.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected `src/takekeeper/review.py`, `src/takekeeper/models.py`, `src/takekeeper/memory.py`, `src/takekeeper/__init__.py`, `tests/test_review.py`, the package tree, and `README.md`.
- Confirmed the previous top live gate is still blocked by the absence of a reachable ClickHouse service.
- Chose the highest-value unblocked backlog item instead: expose the existing evidence/review boundary through a safe application API without arbitrary SQL, arbitrary finding IDs, or caller-controlled reviewer identity.

## Changes made this run

- Added `src/takekeeper/review_api.py`.
- Added `ReviewerIdentityProvider` as a small authentication port so deployments can supply a stronger provider later without coupling the review service to a web framework or identity vendor.
- Added `StaticBearerIdentityProvider` for local/self-hosted use:
  - requires an operator-configured token → stable actor-ID mapping;
  - compares bearer tokens with `hmac.compare_digest`;
  - never returns or persists the secret token itself;
  - rejects missing and invalid authentication.
- Added `ReviewHttpApp`, a zero-extra-dependency WSGI boundary with only two POST operations:
  - `/v1/review/context` resolves the current scoped finding and returns evidence plus append-only decision history;
  - `/v1/review/decision` appends only `confirmed`, `rejected`, or `needs_followup` with an optional bounded note.
- Hardened the API boundary:
  - 16 KiB request-body limit;
  - 2,000-character review-note limit;
  - all scope fields required, non-empty, and individually bounded;
  - unexpected fields rejected, including caller-supplied `actor_id` and `finding_id`;
  - no SQL/table/query/action primitive exposed;
  - cross-production/scene/take misses return not-found instead of leaking another scope;
  - internal exceptions are not reflected to clients;
  - responses set `Cache-Control: no-store`.
- Refactored `FindingReviewService._find()` into the public, still strictly scoped `get_finding()` method so the HTTP boundary can retrieve a finding without duplicating service lookup logic. Existing `review()` and `history()` now call the same method.
- Added `tests/test_review_api.py` with credential-free coverage for:
  - finding/evidence/history retrieval;
  - authenticated actor provenance;
  - append-only decision visibility;
  - rejection of caller-supplied `actor_id` and `finding_id`;
  - missing/invalid bearer authentication;
  - cross-production non-disclosure;
  - decision and note bounds;
  - method restriction.
- Exported the new review API primitives from `takekeeper.__init__`.
- Updated `README.md` with the review API trust model, routes, limits, local bearer adapter, TLS/secret-management requirement for non-loopback use, and updated roadmap.
- No GitHub Actions, destructive repository operations, secrets, or unrelated repository changes were introduced.

## Validation

- Attempted to clone the updated repository and run `PYTHONPATH=src python -m unittest discover -s tests -v` in the execution container.
- The environment again failed DNS resolution for `github.com` (`Could not resolve host: github.com`), so the clone failed before test execution. No full-suite pass is claimed.
- The new API tests are committed but are not represented as passing in this environment.
- A real ClickHouse service is still not reachable here, so the environment-gated acceptance test and official MCP runtime gate remain unexecuted.
- The new API adds no runtime dependency beyond the Python standard library and existing TakeKeeper domain interfaces.

## Decisions locked

1. Official MCP is read-only and is never reused for ingestion, persistence, or human-review credentials.
2. Trusted application writes use separately permissioned ClickHouse clients.
3. Model-facing MCP remains bounded to TakeKeeper-owned analytical operations; arbitrary agent SQL is not exposed.
4. Continuity finding identity is deterministic over logical scope (`production_id`, `scene_id`, `take_id`, `entity_id`, `property_key`) and is independent of mutable evidence/status.
5. Human decisions are append-only audit records; later judgments do not erase earlier judgments.
6. The review service derives finding IDs internally from a finding that currently exists in the requested scope; callers cannot submit arbitrary finding IDs.
7. Reviewer identity at the HTTP boundary must come from authenticated context, not caller-controlled JSON.
8. The public review HTTP surface remains capability-narrow: inspect one current finding/history or append one bounded disposition; it does not expose generic ClickHouse writes or SQL.
9. Real-database acceptance tests must reset mutable fixture state before each test so re-analysis and review writes cannot create order-dependent false passes/failures.
10. Generated analytical SQL scopes production/scene/take, and MCP result rows are scope-validated again before becoming evidence.
11. MCP failures/malformed evidence fail closed; empty results remain truthful empty evidence.
12. Trusted persistence uses bound parameters; dynamic database identifiers remain validated to letters, digits, and underscores.
13. Runtime MCP/auth/version/latency/write-denial claims must be measured on a real environment.

## Gates

- **Gate A live integration:** NOT YET PROVEN; adapters implemented, live official MCP transport pending.
- **Gate B continuity correctness:** CORE + APP SERVICE + CLICKHOUSE ADAPTER + ISOLATED REAL-DB HARNESS + MCP EVIDENCE READER IMPLEMENTED; live execution pending.
- **Gate C evidence/review:** durable nullable evidence + stable finding identity + append-only scoped human-review service/store + authenticated bounded review HTTP API + real-DB acceptance assertions IMPLEMENTED; live execution and operator UI pending.
- **Gate D editorial retrieval:** SQL + isolated real-DB acceptance assertion + MCP typed reader implemented; live MCP execution pending.
- **Gate E failure honesty:** domain + persistence + MCP outage/empty/malformed/wrong-scope behavior implemented and unit-tested; review HTTP failure mapping implemented, new HTTP tests pending execution in a runnable checkout.
- **Gate F security:** app-layer scoping + parameter binding + database identifier validation + read/write credential separation + MCP result scope validation + review-scope resolution + authenticated actor derivation + bounded review API implemented; ClickHouse RBAC/write-denial runtime proof pending.
- **Gate G multimodal evidence:** not started; governed by `MULTIMODAL_EXTRACTION_AND_EVAL.md`.

## Blockers / unknowns

1. No reachable real ClickHouse service from this automation environment, so the real acceptance harness and official MCP server cannot be exercised here.
2. No Gemini/Google runtime credentials, so Gemini/ADK orchestration cannot be truthfully demonstrated.
3. Actual ClickHouse server version, `clickhouse-connect` version, official MCP runtime version, transport/auth, concrete live response envelope, row count, and latency remain unmeasured.
4. Explicit runtime write-denial proof with the real MCP credential is still pending.
5. Real ClickHouse execution of the stable-ID + append-only review acceptance case is still pending.
6. No self-owned demo footage exists yet.
7. The current execution container cannot resolve `github.com`, so the complete repository test suite cannot be cloned and run here.
8. The included static bearer identity adapter is intentionally small; internet-facing production deployments should replace it with a real trusted identity integration and TLS termination rather than embedding tokens in application source.

## Highest-priority backlog

- Execute `tests/test_clickhouse_integration.py` against an authorized local or ClickHouse Cloud instance and fix any version-specific DDL/client/review-store behavior.
- Record ClickHouse server/client versions and acceptance timings once the real harness executes.
- Start official `mcp-clickhouse` with `CLICKHOUSE_ALLOW_WRITE_ACCESS=false` against the seeded database.
- Inject the real MCP client's `call_tool` transport into `McpEvidenceReader` and retrieve the Scene 28 continuity rows plus exact editorial hits (`S28-T31`, `S28-T47`).
- Capture official MCP version, transport, auth mode, actual payload envelope, row counts, per-query latency, and server/client versions.
- Attempt a harmless write through the MCP credential and record the expected denial without changing data.
- Add a minimal operator review UI over `/v1/review/context` and `/v1/review/decision`, showing evidence window, confidence, baseline/observed values, status, and append-only history without adding generic write primitives.
- Replace/static-bearer deployment option with a production OIDC/IAP identity adapter when choosing a concrete Google Cloud deployment topology.
- Implement the governed Gemini multimodal extraction adapter with fixture-first evaluation before real footage.

## Single best next step

**Execute the isolated real ClickHouse acceptance harness as soon as an authorized ClickHouse endpoint is reachable; if that external gate remains unavailable on the next run, build the minimal operator review UI against the newly bounded authenticated review API, keeping all writes constrained to append-only review decisions.**

## Sources / implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://github.com/ClickHouse/mcp-clickhouse/blob/08319aacffeced14598fc605dfa690b8e2081975/mcp_clickhouse/mcp_server.py
- https://github.com/ClickHouse/mcp-clickhouse/releases
