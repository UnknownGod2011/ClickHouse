# TakeKeeper Progress

## Current status

TakeKeeper is a personal open-source production-memory system with deterministic continuity comparison, ClickHouse-backed state, bounded read-only ClickHouse MCP access, append-only extraction/review provenance, governed Gemini/Vertex multimodal extraction, strict continuity projection, deterministic synthetic media, trusted media provenance, bounded schema readiness, schema-gated ingestion, an authenticated WSGI ingest API, secret-safe production composition, Google OIDC/IAP ingress identity, defense-in-depth subject authorization, and now a bounded per-actor ingestion admission boundary before expensive Gemini/ClickHouse work.

This run closed the highest-priority resource-amplification gap: an authenticated/authorized caller can no longer create unbounded concurrent extraction work inside a TakeKeeper process. Admission is keyed only by the trusted actor returned by the identity provider and happens before request-body parsing.

## Inspected this run

- Read this `progress.md` completely before deciding what to change.
- Inspected repository metadata and confirmed `UnknownGod2011/ClickHouse` on `main`.
- Inspected `src/takekeeper/ingest_api.py`, `src/takekeeper/review_api.py`, `src/takekeeper/production_ingest.py`, `src/takekeeper/__init__.py`, `tests/test_ingest_api.py`, and the relevant production-composition tests.
- Confirmed authentication already happened before request-body reads and returned a stable trusted actor ID.
- Confirmed production composition already instantiates `IngestHttpApp`, so a safe default guard inside that boundary protects static, Google OIDC, and IAP production composition without requiring a separate deployment code path.
- Confirmed the remaining gap was admission control: any authorized actor could previously fan out unlimited simultaneous Gemini extraction and ClickHouse persistence work.

## Exact changes made this run

### 1. Thread-safe per-actor admission guard

Added `src/takekeeper/ingest_admission.py` with `ActorIngestAdmissionGuard`:

- key is only the authenticated actor ID returned by the trusted identity provider;
- no production/scene/take/media/property/request metadata can be supplied as a limiter key;
- default per-actor concurrent cap is 2 active requests;
- default sliding-window cap is 30 admitted requests per 60 seconds;
- tracked actor state is bounded to 512 identities by default;
- limiter configuration itself is bounded to prevent pathological values;
- actor IDs are bounded and control characters are rejected;
- implementation is thread-safe using a process-local lock;
- admission uses an idempotent lease/context-manager so concurrency is released on both success and exceptions;
- stale idle actor state is pruned after its rate window expires;
- overload reasons remain internal and callers receive a fixed coarse response;
- explicit documentation states this is per-process defense in depth, not a distributed global quota.

Added `IngestAdmissionSnapshot` with aggregate-only counters:

- `active_requests`;
- `admitted_total`;
- `rejected_concurrency_total`;
- `rejected_rate_total`;
- `rejected_capacity_total`.

No actor/tenant/media labels are exposed.

### 2. Admission integrated into the HTTP boundary before body parsing

Updated `src/takekeeper/ingest_api.py`:

- every `IngestHttpApp` now receives a safe `ActorIngestAdmissionGuard` by default;
- authentication still occurs first;
- the actor returned by authentication is the only admission key;
- the admission lease is acquired before `_read_json_body(...)`, request construction, Gemini extraction, or ClickHouse persistence;
- overloaded work returns HTTP 429 with exactly `{\"error\":\"ingestion overloaded\"}`;
- request bodies are not read for requests rejected at the concurrency/rate boundary;
- lease cleanup is automatic if body validation, extraction, persistence, or any downstream step raises;
- existing liveness/readiness behavior remains unchanged;
- added `GET /metrics` with aggregate JSON admission counters only.

Because production composition already constructs `IngestHttpApp`, these safe defaults are now active for static bearer, Google OIDC, and IAP deployments without additional production bootstrap changes.

### 3. Regression coverage

Added `tests/test_ingest_admission.py` covering:

- per-actor concurrent isolation: one saturated actor does not consume another actor's per-actor slot;
- same-actor concurrent rejection;
- sliding-window request rejection and expiry;
- bounded tracked-actor capacity and recovery after idle expiry;
- HTTP overload rejection after authentication but before body reads using a body object that fails if read;
- no service/Gemini-equivalent work on overload;
- concurrency lease release after an invalid request;
- aggregate metrics that contain no authenticated actor ID.

Existing `tests/test_ingest_api.py` remains compatible because each app now receives its own default guard and the existing tests do not exceed the safe defaults within a single app instance.

### 4. Public API and documentation

Updated `src/takekeeper/__init__.py` to export:

- `ActorIngestAdmissionGuard`;
- `IngestAdmissionSnapshot`;
- `IngestOverloaded`.

Added `INGEST_ADMISSION.md` documenting authority boundaries, defaults, fixed overload semantics, aggregate telemetry, multi-instance limitations, and credential-free regression coverage.

### 5. Repository safety

- No GitHub Actions workflow was added, modified, triggered, or rerun.
- No unrelated repository was touched.
- No ClickHouse, Gemini/Vertex, Google identity, IAP, MCP, or production-media credential was used.
- No cloud resource or production media was accessed or modified.
- No destructive ClickHouse operation was introduced.
- Official ClickHouse MCP remains read-only and separately permissioned from application writes.

## Validation / results

Implementation commits this run:

- `c4ce44b6bee08bde641c0d7e365c17b9d08d9c90` — add per-actor ingest admission guard, HTTP integration, and regression tests;
- `6abc77bf27c64272692f4cdab9f434d322e51a41` — export admission primitives;
- `0d95db9319fe5c17074ccb5fdd68e47eb6f1dc0a` — document the admission boundary.

Executable validation attempted:

```text
git clone --depth 1 https://github.com/UnknownGod2011/ClickHouse.git /tmp/takekeeper
```

The execution container again failed with `Could not resolve host: github.com`, so a runnable checkout could not be created and Python did not execute. This is an environment/network blocker, not a test result. I therefore do **not** claim the new tests pass. GitHub Actions were deliberately not used as a workaround.

Structural validation completed through the GitHub connector:

- the implementation commit applies cleanly to `main`;
- authentication remains before admission and body parsing;
- admission receives only the trusted actor returned by `ReviewerIdentityProvider.authenticate(...)`;
- HTTP 429 is mapped explicitly;
- aggregate metrics contain no actor/subject/production/scene/take/media labels;
- the guard is default-constructed by `IngestHttpApp`, which means current production composition is protected without a separate bootstrap path;
- public exports reference the new module/classes now present on `main`.

## Decisions locked

1. Official ClickHouse MCP remains read-only and is never reused for application writes, migrations, or credential handling.
2. Trusted application writes use separately permissioned ClickHouse clients.
3. Agent-facing MCP access remains bounded; arbitrary agent SQL is not exposed.
4. Production/scene/take scope is trusted application metadata and never model output.
5. Machine confidence is not human confirmation.
6. Extraction provenance is append-only and same-run retry identity remains immutable.
7. Continuity projection remains stricter than extraction persistence; abstention cannot become a mismatch.
8. Production extraction ingress starts closed and schema readiness remains a prerequisite.
9. Network callers cannot define model identity, prompt schema, property registries, SQL, or migrations.
10. Production composition obtains secrets from environment/secret injection rather than argv and suppresses provider exception context.
11. Static bearer identity remains supported for local/self-hosted trusted deployments.
12. Cloud Run service/workload identity uses Google-signed OIDC bearer tokens with explicit audience/issuer/time checks.
13. IAP mode authenticates only from the verified signed assertion, never compatibility email/user headers.
14. Google/IAP production authorization requires explicit deployment-owned verified-subject mapping; token authenticity alone is insufficient.
15. Google identity and static shared-secret authority configuration are mutually exclusive.
16. Authentication must continue to happen before ingest request-body reads.
17. Ingest admission is keyed only by trusted authenticated actor identity, never caller-controlled production/media metadata.
18. Process-local admission remains mandatory defense in depth even when a deployment adds a distributed/upstream quota.
19. Admission telemetry must remain aggregate/low-cardinality and must not enumerate actors or media scope.

## Gates

- **Gate A — live ClickHouse:** schema readiness is implemented/enforced through production composition; real-endpoint execution remains pending.
- **Gate B — continuity correctness:** deterministic comparison, persistence, governed projection, and stale-state convergence are implemented.
- **Gate C — evidence/review:** durable evidence, stable finding identity, append-only review, authenticated API, and operator console are implemented.
- **Gate D — editorial retrieval:** typed/bounded retrieval and SQL coverage exist; live official MCP execution remains pending.
- **Gate E — failure honesty:** extraction/persistence/MCP/review/schema-readiness/ingest-bootstrap/HTTP/composition/auth/admission paths fail closed structurally.
- **Gate F — security:** tenant scope, parameter binding, read/write separation, authenticated review/ingest, immutable retry identity, metadata-only preflight, server-owned extraction policy, secret-safe composition, Google signed-token verification, IAP assertion verification, defense-in-depth Google subject authorization, and bounded per-actor local admission are implemented structurally; live RBAC/write-denial/IAP-network/distributed-quota proof remains pending.
- **Gate G — multimodal evidence:** governed extraction, Gemini transport, objective benchmark metrics, synthetic media, live candidate runner, trusted MIME/byte identity, schema support, persistence, rollout-skew detection, HTTP ingress, production composition, and local admission protection exist; live execution remains pending.

## Blockers / unknowns

1. The execution container cannot resolve `github.com`, so normal checkout and Python test execution remain unavailable from this run.
2. No reachable authorized disposable ClickHouse endpoint is available.
3. No Gemini/Vertex credentials or trusted uploaded benchmark media are available.
4. No authorized Cloud Run/IAP environment is available to empirically verify real signed-token headers, certificate retrieval/cache behavior, audience values, ingress policy, bypass resistance, subject-map behavior, or multi-replica admission behavior end-to-end.
5. Official MCP runtime/auth/version behavior and explicit write denial remain unmeasured against a live server.
6. Existing deployments must apply `sql/migrations/002_extraction_media_provenance.sql`; startup preflight detects skew and refuses ingestion.
7. Local SHA-256 hashing cannot prove object immutability if another writer replaces same-length bytes during the read; production ingest should hash immutable/versioned objects.
8. TLS termination/network policy, WSGI server process behavior, Cloud Run/IAP upstream authorization policy, and distributed/global quotas remain deployment responsibilities and are not yet empirically exercised.
9. Current admission defaults are safe but not yet environment-configurable through `ProductionIngestConfig`; operators needing different throughput must currently construct `IngestHttpApp` with an explicit guard.
10. `GET /metrics` currently exposes aggregate JSON rather than Prometheus exposition format; this is safe/low-cardinality but not yet directly scrape-native.

## Highest-priority backlog

- Run `tests.test_ingest_admission`, `tests.test_ingest_api`, identity/subject-policy/composition suites, and then the full credential-free suite in a runnable checkout; fix concrete failures.
- Add bounded environment configuration for production admission limits and pass an explicit guard from `build_ingest_deployment_from_env`.
- Add a scrape-native Prometheus exposition endpoint or adapter while preserving fixed cardinality and no actor/tenant/media labels.
- Refresh `PRODUCTION_INGEST.md` and `README.md` so examples include `TAKEKEEPER_INGEST_SUBJECT_MAP` plus the new admission boundary.
- Run production composition plus migration 002/schema preflight against a disposable authorized ClickHouse instance and verify readiness transitions empirically.
- Exercise real Cloud Run OIDC and IAP ingress, including wrong audience, unauthorized-but-signed subject, direct-service bypass attempts, expired tokens, compatibility-header spoofing, and multi-replica quota behavior.
- Start official `ClickHouse/mcp-clickhouse` read-only, exercise continuity/editorial operations, and record explicit write denial.

## Single best next step

**Wire the admission policy explicitly into `ProductionIngestConfig`: add bounded environment settings for per-actor concurrency and sliding-window rate, construct the guard in `build_ingest_deployment_from_env`, and add production-composition tests proving invalid/extreme limits fail before provider factories while configured limits actually govern authenticated HTTP ingestion.**

## Relevant implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://googleapis.github.io/python-genai/
- https://cloud.google.com/iap/docs/samples/iap-validate-jwt
- https://cloud.google.com/iap/docs/identity-howto
- https://cloud.google.com/api-gateway/docs/authenticating-users-googleid
