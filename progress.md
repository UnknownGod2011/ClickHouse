# TakeKeeper Progress

## Current status

TakeKeeper is a personal open-source production-memory system with deterministic continuity comparison, ClickHouse-backed state, bounded read-only ClickHouse MCP access, append-only extraction/review provenance, governed Gemini/Vertex multimodal extraction, strict continuity projection, objective multimodal benchmarks, deterministic synthetic media, trusted MIME/hash/byte provenance, immutable same-run retry identity, bounded schema readiness, schema-gated ingestion, an authenticated WSGI ingest API, secret-safe production composition, and now Google-signed production ingress identity for Cloud Run/IAP deployments.

This run closed the highest-priority static-auth production gap. The existing narrow `ReviewerIdentityProvider.authenticate(...) -> actor_id` protocol is preserved while production ingestion can select static bearer, Google OIDC, or IAP signed-assertion identity. Google token verification is audience/issuer/time/subject bounded and verifier errors/token contents are redacted.

## Inspected this run

- Read this `progress.md` completely before deciding what to change.
- Confirmed `UnknownGod2011/ClickHouse` on `main` is the intended repository and the connected GitHub account has push/admin permission.
- Inspected `src/takekeeper/ingest_api.py`, `review_api.py`, `production_ingest.py`, `__init__.py`, `pyproject.toml`, `tests/test_production_ingest.py`, `PRODUCTION_INGEST.md`, and `README.md`.
- Confirmed ingest authentication already occurs before reading attacker-controlled request bytes.
- Confirmed the current production factory was still static-bearer-only and therefore did not yet satisfy the recorded Cloud Run identity gate.
- Checked current official Google Cloud IAP guidance: applications should validate `X-Goog-IAP-JWT-Assertion`; compatibility email/user headers must not be treated as the security mechanism.
- Checked Google's current IAP Python sample: `google.oauth2.id_token.verify_token(...)` with the IAP public-key URL and explicit expected audience remains the documented Python verification path.
- Checked current Google ID-token guidance for issuer/audience/expiry-bearing JWT authentication.

## Exact changes made this run

### Google signed-token identity adapters

Added `src/takekeeper/google_identity.py` with:

- `GoogleOidcIdentityProvider` for Google-issued bearer ID tokens used by Cloud Run/service identity;
- `IapIdentityProvider` for raw `X-Goog-IAP-JWT-Assertion` values;
- injectable `TokenVerifier` seam so claim-policy tests are credential/network-free;
- fixed Google OIDC issuer allow-list: `accounts.google.com` and `https://accounts.google.com`;
- fixed IAP issuer: `https://cloud.google.com/iap`;
- fixed IAP public-key URL matching the official Google sample;
- explicit expected-audience pinning;
- local `aud`, `iss`, `exp`, `iat`, and bounded `sub` revalidation after signature verification;
- bounded clock skew (0-300 seconds, default 60);
- bounded token/actor components;
- actor mapping only from verified `sub` (`google:<sub>` / `iap:<sub>`).

Email claims and IAP compatibility identity headers are intentionally ignored. Caller-controlled actor IDs are not accepted in Google identity modes.

Verifier/provider exceptions are collapsed to fixed `PermissionError` messages with exception context suppressed, so malformed tokens, signature errors, certificate details, claim payloads, or raw token strings cannot escape through the HTTP error boundary.

### IAP credential-source support without widening the identity protocol

Updated `IngestHttpApp` with a server-owned `credential_environ_key` (default `HTTP_AUTHORIZATION`). The key is strictly validated as a bounded uppercase WSGI HTTP environ key.

Authentication still happens before body reads. Production IAP mode selects only `HTTP_X_GOOG_IAP_JWT_ASSERTION`; static and Google OIDC modes continue using `HTTP_AUTHORIZATION`.

This preserves the existing `ReviewerIdentityProvider.authenticate(value)` protocol instead of giving identity providers arbitrary access to the WSGI request/environment.

### Production identity mode composition

Updated `ProductionIngestConfig` / `build_ingest_deployment_from_env(...)`:

- added `TAKEKEEPER_INGEST_IDENTITY_MODE=static|google_oidc|iap`;
- `static` remains default and requires `TAKEKEEPER_INGEST_BEARER_TOKEN` (>=32 chars), with optional `TAKEKEEPER_INGEST_ACTOR_ID`;
- `google_oidc` requires `TAKEKEEPER_INGEST_EXPECTED_AUDIENCE` and rejects static bearer/actor configuration;
- `iap` requires `TAKEKEEPER_INGEST_EXPECTED_AUDIENCE`, rejects static bearer/actor configuration, and selects the signed IAP assertion header;
- static mode rejects a Google expected-audience variable to avoid ambiguous authority configuration;
- added injectable `identity_provider_factory` for composition tests/embedders;
- startup exceptions remain coarse and suppress auth-provider context as well as ClickHouse/Gemini provider context.

The deployment still cannot be returned ready until the existing ClickHouse extraction-schema preflight succeeds.

### Dependencies and public API

- Added optional `google-auth = ["google-auth>=2,<3"]` dependency.
- Added `production` extra containing ClickHouse Connect + Google Gen AI + google-auth.
- Exported `GoogleOidcIdentityProvider`, `IapIdentityProvider`, `GoogleIdentityClaims`, and `GoogleIdentityConfigurationError` from `takekeeper`.

### Regression coverage

Added `tests/test_google_identity.py` covering:

- valid Google OIDC subject-to-actor mapping;
- verifier receives the exact configured audience;
- email claims do not influence actor identity;
- invalid audience rejection;
- invalid issuer rejection;
- expired token rejection;
- future-issued token rejection beyond clock skew;
- verifier exception/token redaction;
- missing bearer scheme rejected before verifier invocation;
- valid raw IAP assertion handling;
- strict IAP issuer pinning;
- multi-audience ambiguity rejection;
- empty-audience and excessive-clock-skew configuration rejection.

Expanded `tests/test_production_ingest.py` with:

- static mode retaining `Authorization`;
- Google OIDC mode retaining `Authorization`;
- IAP mode selecting only `X-Goog-IAP-JWT-Assertion`;
- Google modes requiring expected audience;
- Google modes rejecting static secrets/actor configuration;
- static mode rejecting Google audience configuration.

### Documentation

Updated `PRODUCTION_INGEST.md` with:

- `.[production]` install path;
- complete static / Google OIDC / IAP configuration contracts;
- Cloud Run OIDC and IAP audience examples;
- explanation that IAP compatibility identity headers are not trusted;
- actor mapping and token/error redaction behavior;
- updated privilege-separation and validation sections;
- current official Google Cloud IAP/ID-token references.

`README.md` was inspected and is structurally still accurate about the product, but its short production-ingest section still describes bearer auth as the only production identity option. The authoritative production guide is current; the README wording should be refreshed in the next documentation pass rather than risk an unnecessary large replacement during this implementation run.

### Repository safety

- No GitHub Actions workflow was added, modified, triggered, or rerun.
- No unrelated repository was touched.
- No ClickHouse, Gemini/Vertex, Google identity, IAP, MCP, or production-media credential was used.
- No cloud resource or production media was accessed or modified.
- No destructive ClickHouse operation was introduced.
- Official ClickHouse MCP remains read-only and separately permissioned from application writes.

## Validation / results

Files were written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.

Implementation commits before this handoff update:

- `601731c9d77dca1420d53ad8d7cc2f35bb1928e0` — Google signed identity providers;
- `095e052fe5bb9c8fc50d3d81e4cd1b4674328c84` — configurable signed-credential HTTP header;
- `9c4fd9662ff0a2441034d72c8f26c9d44199157e` — production Google identity modes;
- `e82c8cc9139d6075dff177ea254428d00aa0d85b` — credential-free identity verifier tests;
- `90e1e823d9ae890c0a02eaf68c8be6c14b7acc2d` — production identity composition tests;
- `7d6472c4004aeabb2e222ab4c483d206d307fa79` — explicit google-auth/production dependency extras;
- `b2a9f28ee4faf542eec8672aa43643fad5d88620` — public Google identity exports;
- `68d4d63a67ffd1a6fe69c2d1ae6a9266e175c0a5` — Google OIDC/IAP production documentation.

Structural review after writing:

- re-fetched `src/takekeeper/google_identity.py` from `main` and verified issuer constants, audience pinning, bounded claim checks, subject-only actor mapping, and exception redaction are committed;
- verified IAP mode uses the signed assertion header rather than compatibility email/user headers;
- verified production composition still performs schema preflight last before returning a deployment;
- verified Google identity modes reject the long-lived static bearer secret and arbitrary configured actor label.

Executable validation attempt:

```text
git clone --depth 1 https://github.com/UnknownGod2011/ClickHouse.git /tmp/takekeeper-check
PYTHONPATH=src python -m unittest \
  tests.test_google_identity \
  tests.test_production_ingest \
  tests.test_ingest_api -v
```

The execution container failed during clone with `Could not resolve host: github.com`, so Python never started. This is an environment/network blocker, not a test result. I therefore do **not** claim the new or existing suites pass here. GitHub Actions were deliberately not used as a workaround.

No live Google certificate retrieval, IAP request, Cloud Run identity token, Gemini/Vertex request, real ClickHouse request, official MCP session, or production-media operation was performed.

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
14. Google identity actor IDs derive only from verified `sub`; request bodies/email claims cannot choose actor identity.
15. Google identity and static shared-secret authority configuration are mutually exclusive.
16. Authentication must continue to happen before ingest request-body reads.

## Gates

- **Gate A — live ClickHouse:** schema readiness is implemented/enforced through production composition; real-endpoint execution remains pending.
- **Gate B — continuity correctness:** deterministic comparison, persistence, governed projection, and stale-state convergence are implemented.
- **Gate C — evidence/review:** durable evidence, stable finding identity, append-only review, authenticated API, and operator console are implemented.
- **Gate D — editorial retrieval:** typed/bounded retrieval and SQL coverage exist; live official MCP execution remains pending.
- **Gate E — failure honesty:** extraction/persistence/MCP/review/schema-readiness/ingest-bootstrap/HTTP/composition/auth paths fail closed structurally.
- **Gate F — security:** tenant scope, parameter binding, read/write separation, authenticated review/ingest, immutable retry identity, metadata-only preflight, server-owned extraction policy, secret-safe composition, startup gating, Google OIDC audience/issuer/time validation, and IAP signed-assertion verification are implemented structurally; live RBAC/write-denial/IAP-network proof remains pending.
- **Gate G — multimodal evidence:** governed extraction, Gemini transport, objective benchmark metrics, synthetic media, live candidate runner, trusted MIME/byte identity, schema support, persistence, rollout-skew detection, HTTP ingress, and production composition exist; live execution remains pending.

## Blockers / unknowns

1. The execution container cannot currently resolve `github.com`, so normal checkout and Python test execution remain unavailable from this run.
2. No reachable authorized disposable ClickHouse endpoint is available.
3. No Gemini/Vertex credentials or trusted uploaded benchmark media are available.
4. No authorized Cloud Run/IAP environment is available to empirically verify real signed-token headers, certificate retrieval/cache behavior, audience values, ingress policy, or bypass resistance.
5. Official MCP runtime/auth/version behavior and explicit write denial remain unmeasured against a live server.
6. Live `google-genai` video/schema behavior, latency, token usage, and provider failure modes remain unmeasured.
7. Existing deployments must apply `sql/migrations/002_extraction_media_provenance.sql`; startup preflight detects skew and refuses ingestion.
8. Local SHA-256 hashing cannot prove object immutability if another writer replaces same-length bytes during the read; production ingest should hash immutable/versioned objects.
9. A real ClickHouse validation is still needed for exact driver type strings and nullable `FixedString(64)` round trips.
10. Rate limiting, TLS termination/network policy, WSGI server process behavior, and Cloud Run/IAP upstream authorization policy remain deployment responsibilities and are not yet empirically exercised.

## Highest-priority backlog

- Run `tests/test_google_identity.py`, `tests/test_production_ingest.py`, `tests/test_ingest_api.py`, `tests/test_ingest_runtime.py`, `tests/test_schema_preflight.py`, extraction persistence tests, and the full credential-free suite in a runnable checkout; fix concrete issues.
- Refresh the README production-ingest section/repository map so it explicitly lists `google_identity.py`, the `production` extra, and static/OIDC/IAP identity modes.
- Add defense-in-depth Google-subject authorization policy (allow-listed service-account/user subjects or trusted mapping) so token authenticity does not alone grant ingest authority when upstream IAM/IAP policy is misconfigured.
- Run production composition plus migration 002/schema preflight against a disposable authorized ClickHouse instance and verify readiness transitions empirically.
- Exercise real Cloud Run OIDC and IAP ingress, including wrong audience, direct-service bypass attempts, expired tokens, and compatibility-header spoofing.
- Run the deterministic ffmpeg fixture generator and `takekeeper-live-benchmark` against one authorized Gemini/Vertex candidate using self-owned generated media.
- Start official `ClickHouse/mcp-clickhouse` read-only, exercise continuity/editorial operations, and record explicit write denial.

## Single best next step

**Add defense-in-depth subject authorization to the Google identity adapters/production config: require an explicit deployment-owned allow-list or subject-to-actor mapping for `google_oidc`/`iap`, validate it without exposing identities in errors, and add credential-free tests proving a correctly signed token from an unauthorized Google/IAP subject still cannot ingest. This protects TakeKeeper if Cloud Run IAM or IAP upstream authorization is accidentally broadened.**

## Relevant implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://googleapis.github.io/python-genai/
- https://cloud.google.com/iap/docs/samples/iap-validate-jwt
- https://cloud.google.com/iap/docs/identity-howto
- https://cloud.google.com/api-gateway/docs/authenticating-users-googleid
