# TakeKeeper ingest admission control

Production extraction is expensive work: one accepted request may invoke Gemini/Vertex and then persist extraction provenance in ClickHouse. Authentication and schema readiness alone therefore are not sufficient admission controls.

`IngestHttpApp` now owns a process-local `ActorIngestAdmissionGuard`. The guard is evaluated **after authentication but before request-body parsing, extraction, or ClickHouse persistence**.

## Authority boundary

The only admission key is the actor ID returned by the configured trusted identity provider:

- static mode: the deployment-owned bearer-token-to-actor mapping;
- Google OIDC: the verified JWT `sub` after deployment-owned subject authorization;
- IAP: the verified IAP assertion `sub` after deployment-owned subject authorization.

Production IDs, scene IDs, take IDs, media URIs, hashes, property profiles, and other request data are never used as limiter keys. That prevents a caller from escaping its quota simply by varying media metadata.

## Defaults

Each `IngestHttpApp` receives a guard by default with:

- at most 2 concurrent admitted requests per authenticated actor;
- at most 30 admitted requests per actor in a sliding 60-second window;
- at most 512 process-local tracked actors;
- bounded validation for actor IDs and limiter configuration.

The implementation is thread-safe and leases are released on success and on exceptions. A rejected request returns only:

```json
{"error":"ingestion overloaded"}
```

with HTTP `429 Too Many Requests`. Provider details, actor IDs, tenant/media metadata, and limiter internals are not returned.

## Aggregate telemetry

`GET /metrics` exposes only aggregate JSON counters:

```json
{
  "ingest_admission": {
    "active_requests": 0,
    "admitted_total": 0,
    "rejected_concurrency_total": 0,
    "rejected_rate_total": 0,
    "rejected_capacity_total": 0
  }
}
```

No actor, subject, production, scene, take, media, or credential labels are emitted, so telemetry cardinality remains fixed.

## Multi-instance deployments

This guard is intentionally process-local. It protects each WSGI/Cloud Run process from unbounded local fan-out, but it is not a distributed global quota. A production with multiple replicas should also configure an upstream control appropriate to the deployment, such as Cloud Run/IAP/API-gateway quotas or another distributed admission layer. The application guard remains useful as defense in depth even when an upstream quota exists.

Do not replace the actor key with untrusted request metadata. If a future distributed limiter is added, it should preserve the same trusted-identity keying contract.

## Credential-free regression coverage

`tests/test_ingest_admission.py` covers:

- per-actor concurrent isolation;
- sliding-window rate rejection and expiry;
- bounded actor-state tracking;
- overload rejection before request-body reads;
- lease release after invalid requests;
- fixed, aggregate-only metrics without actor disclosure.

Live multi-replica quota behavior remains a deployment acceptance test rather than a unit-test claim.
