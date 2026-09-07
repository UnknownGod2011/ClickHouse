# TakeKeeper Progress

## Current status

TakeKeeper is a personal open-source production-memory system with deterministic continuity comparison, ClickHouse-backed state, bounded read-only ClickHouse MCP access, append-only extraction/review provenance, governed Gemini/Vertex multimodal extraction, strict continuity projection, deterministic synthetic media, trusted media provenance, bounded schema readiness, schema-gated ingestion, an authenticated WSGI ingest API, secret-safe production composition, Google OIDC/IAP ingress identity, and now an explicit defense-in-depth subject authorization boundary for Google-signed identities.

This run closed the highest-priority authorization gap: a correctly signed Google/IAP token no longer automatically grants production ingest authority. Production Google identity modes now require a deployment-owned verified-subject-to-TakeKeeper-actor mapping.

## Inspected this run

- Read this `progress.md` completely before deciding what to change.
- Inspected `src/takekeeper/google_identity.py`, `src/takekeeper/production_ingest.py`, `tests/test_google_identity.py`, `tests/test_production_ingest.py`, and `PRODUCTION_INGEST.md`.
- Confirmed existing Google identity verification already pins issuer/audience/time and maps identity only from verified `sub`.
- Confirmed the remaining gap was authorization: any otherwise-valid signed Google/IAP subject was accepted even if Cloud Run IAM/IAP policy were accidentally broadened.
- Confirmed authentication still occurs before ingest request-body reads and did not alter that boundary.

## Exact changes made this run

### 1. Subject authorization in Google identity adapters

Updated `src/takekeeper/google_identity.py`:

- added optional bounded `authorized_subjects: Mapping[str, str]` to `GoogleOidcIdentityProvider` and `IapIdentityProvider`;
- mapping keys are verified JWT `sub` values; mapping values are bounded TakeKeeper actor IDs;
- signature/issuer/audience/time validation happens before authorization lookup;
- signed-but-unauthorized subjects fail with the same fixed `PermissionError("invalid credentials")` used for invalid credentials;
- unauthorized subject values are never echoed in errors;
- map size is bounded to 256 entries and subject/actor values to 512 characters;
- empty/invalid mappings fail configuration validation;
- direct embedders may still omit the map when using these classes as pure authentication primitives, but production composition below requires it.

### 2. Production Google identity policy is mandatory

Updated `src/takekeeper/production_ingest.py`:

- added `TAKEKEEPER_INGEST_SUBJECT_MAP` for `google_oidc` and `iap` modes;
- format is a deployment-owned JSON object mapping verified subjects to trusted TakeKeeper actor IDs;
- production Google identity modes fail configuration parsing if the map is absent, empty, malformed, oversized, or contains invalid keys/values;
- static bearer mode rejects `TAKEKEEPER_INGEST_SUBJECT_MAP` so authority modes cannot be mixed;
- map payload is `repr=False` in `ProductionIngestConfig` to avoid routine configuration logging enumerating authorized identities;
- JSON policy is bounded to 16 KiB and 256 entries;
- default production identity factory passes the map into the OIDC/IAP verifier adapters;
- existing Google audience requirements, static-secret rejection, signed IAP assertion header, schema preflight, and startup fail-closed behavior remain intact.

### 3. Regression coverage

Updated `tests/test_google_identity.py` with coverage for:

- explicitly authorized Google subject mapping to a deployment actor;
- correctly signed but unauthorized Google subject denial;
- correctly signed but unauthorized IAP subject denial;
- unauthorized subject redaction;
- empty authorization map rejection;
- invalid mapped actor rejection without value echo.

Added `tests/test_subject_authorization.py` covering:

- production Google mode requiring an explicit subject map;
- JSON subject-to-actor parsing;
- subject policy redaction from config `repr()`;
- static mode rejecting Google subject policy;
- malformed policy errors not echoing contents;
- IAP using the same explicit authorization contract.

Updated `tests/test_production_ingest.py` so existing OIDC/IAP composition cases supply the newly required subject policy and continue asserting the correct credential header behavior.

### 4. Documentation

Added `GOOGLE_SUBJECT_AUTHORIZATION.md` documenting:

- authenticated identity vs application authorization;
- environment configuration examples for Cloud Run OIDC and IAP;
- bounded/fail-closed behavior;
- subject-map rotation guidance;
- why upstream Cloud Run IAM/IAP authorization is still required;
- credential-free test coverage and live-environment limitations.

`PRODUCTION_INGEST.md` remains structurally accurate for the identity modes but its examples do not yet include the newly mandatory subject-map variable; refresh that document and the README in the next documentation pass.

### 5. Repository safety

- No GitHub Actions workflow was added, modified, triggered, or rerun.
- No unrelated repository was touched.
- No ClickHouse, Gemini/Vertex, Google identity, IAP, MCP, or production-media credential was used.
- No cloud resource or production media was accessed or modified.
- No destructive ClickHouse operation was introduced.
- Official ClickHouse MCP remains read-only and separately permissioned from application writes.

## Validation / results

Implementation commits before this handoff update:

- `11097ed739c0259bcdec11a452c763d03f1915f4` — require explicit Google subject authorization policy in identity adapters;
- `b49cce51b67561ed3a344689ed691631da3aa817` — enforce production Google ingest subject mapping;
- `5567d9b88acaf698b68540f54cf4c742d2e07035` — signed-subject authorization regression tests;
- `3faacb6e371a6867ce67e3d25b5e74c41a8f3bab` — production subject policy tests;
- `94d77b1796c73df236fd4b3d8bf6724956f85845` — update production composition tests for mandatory subject policy;
- `cbaf5159a5ad413dfea8fd23c5a3c7ecf000bffa` — subject authorization operations/security documentation.

Executable validation attempted:

```text
git clone --depth 1 https://github.com/UnknownGod2011/ClickHouse.git /tmp/takekeeper-check
cd /tmp/takekeeper-check
PYTHONPATH=src python -m unittest \
  tests.test_google_identity \
  tests.test_subject_authorization \
  tests.test_production_ingest -v
```

The container again failed at clone with `Could not resolve host: github.com`, so Python never started. This is an environment/network blocker, not a test result. I therefore do **not** claim these tests pass. GitHub Actions were deliberately not used as a workaround.

Structural review completed through the GitHub connector:

- production Google modes now require `TAKEKEEPER_INGEST_SUBJECT_MAP`;
- verified `sub` is the only lookup key;
- signed but unmapped subjects fail closed;
- static bearer and Google subject-map authority configuration are mutually exclusive;
- the subject map is absent from `ProductionIngestConfig.__repr__`;
- IAP continues to use only `X-Goog-IAP-JWT-Assertion` as its credential source.

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

## Gates

- **Gate A — live ClickHouse:** schema readiness is implemented/enforced through production composition; real-endpoint execution remains pending.
- **Gate B — continuity correctness:** deterministic comparison, persistence, governed projection, and stale-state convergence are implemented.
- **Gate C — evidence/review:** durable evidence, stable finding identity, append-only review, authenticated API, and operator console are implemented.
- **Gate D — editorial retrieval:** typed/bounded retrieval and SQL coverage exist; live official MCP execution remains pending.
- **Gate E — failure honesty:** extraction/persistence/MCP/review/schema-readiness/ingest-bootstrap/HTTP/composition/auth paths fail closed structurally.
- **Gate F — security:** tenant scope, parameter binding, read/write separation, authenticated review/ingest, immutable retry identity, metadata-only preflight, server-owned extraction policy, secret-safe composition, Google signed-token verification, IAP assertion verification, and defense-in-depth Google subject authorization are implemented structurally; live RBAC/write-denial/IAP-network proof remains pending.
- **Gate G — multimodal evidence:** governed extraction, Gemini transport, objective benchmark metrics, synthetic media, live candidate runner, trusted MIME/byte identity, schema support, persistence, rollout-skew detection, HTTP ingress, and production composition exist; live execution remains pending.

## Blockers / unknowns

1. The execution container cannot resolve `github.com`, so normal checkout and Python test execution remain unavailable from this run.
2. No reachable authorized disposable ClickHouse endpoint is available.
3. No Gemini/Vertex credentials or trusted uploaded benchmark media are available.
4. No authorized Cloud Run/IAP environment is available to empirically verify real signed-token headers, certificate retrieval/cache behavior, audience values, ingress policy, bypass resistance, or subject-map behavior end-to-end.
5. Official MCP runtime/auth/version behavior and explicit write denial remain unmeasured against a live server.
6. Existing deployments must apply `sql/migrations/002_extraction_media_provenance.sql`; startup preflight detects skew and refuses ingestion.
7. Local SHA-256 hashing cannot prove object immutability if another writer replaces same-length bytes during the read; production ingest should hash immutable/versioned objects.
8. Rate limiting, TLS termination/network policy, WSGI server process behavior, and Cloud Run/IAP upstream authorization policy remain deployment responsibilities and are not yet empirically exercised.

## Highest-priority backlog

- Run the targeted identity/subject-policy/composition suites and then the full credential-free suite in a runnable checkout; fix concrete failures.
- Refresh `PRODUCTION_INGEST.md` and `README.md` so production examples explicitly include `TAKEKEEPER_INGEST_SUBJECT_MAP` and explain authenticated-vs-authorized identity.
- Add bounded request-rate / concurrency protection at the ingest boundary or a deployment adapter so an authenticated principal cannot accidentally fan out unlimited Gemini work.
- Run production composition plus migration 002/schema preflight against a disposable authorized ClickHouse instance and verify readiness transitions empirically.
- Exercise real Cloud Run OIDC and IAP ingress, including wrong audience, unauthorized-but-signed subject, direct-service bypass attempts, expired tokens, and compatibility-header spoofing.
- Start official `ClickHouse/mcp-clickhouse` read-only, exercise continuity/editorial operations, and record explicit write denial.

## Single best next step

**Add a bounded per-actor ingestion concurrency/rate guard around the authenticated HTTP boundary before Gemini extraction. It should key only on the trusted authenticated actor, reject excess work with a coarse response, never use tenant/media IDs as untrusted rate keys, expose low-cardinality metrics, and include credential-free tests proving an authorized caller cannot create unbounded concurrent Gemini/ClickHouse work.**

## Relevant implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://googleapis.github.io/python-genai/
- https://cloud.google.com/iap/docs/samples/iap-validate-jwt
- https://cloud.google.com/iap/docs/identity-howto
- https://cloud.google.com/api-gateway/docs/authenticating-users-googleid
