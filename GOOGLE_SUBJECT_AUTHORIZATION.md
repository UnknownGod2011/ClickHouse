# Google subject authorization

TakeKeeper treats a correctly signed Google or IAP token as **authenticated identity, not ingest authorization**.

Production `google_oidc` and `iap` modes require an explicit deployment-owned JSON mapping in `TAKEKEEPER_INGEST_SUBJECT_MAP`. Keys are verified JWT `sub` claims and values are the bounded TakeKeeper actor IDs written into provenance/review records.

```text
TAKEKEEPER_INGEST_IDENTITY_MODE=google_oidc
TAKEKEEPER_INGEST_EXPECTED_AUDIENCE=https://takekeeper-...run.app
TAKEKEEPER_INGEST_SUBJECT_MAP={"123456789012345678901":"production-ingest-worker"}
```

For IAP the same mapping contract applies, with the IAP audience and signed assertion header:

```text
TAKEKEEPER_INGEST_IDENTITY_MODE=iap
TAKEKEEPER_INGEST_EXPECTED_AUDIENCE=/projects/<PROJECT_NUMBER>/global/backendServices/<BACKEND_ID>
TAKEKEEPER_INGEST_SUBJECT_MAP={"verified-iap-subject":"script-supervisor"}
```

## Security properties

1. Signature, issuer, audience, expiry, issued-at, and subject validation happens before authorization.
2. Only the verified `sub` claim is used to look up authorization. Email claims and compatibility identity headers never choose the actor.
3. A valid token whose `sub` is absent from the map receives the same bounded `invalid credentials` failure as other invalid credentials. The response does not disclose the subject or whether it exists in policy.
4. Production Google identity modes refuse to start without a non-empty subject map.
5. Static bearer mode rejects `TAKEKEEPER_INGEST_SUBJECT_MAP`; Google and static authority configuration cannot be mixed.
6. The map is bounded to 16 KiB / 256 entries and subject/actor strings are bounded to 512 characters with control characters rejected.
7. `ProductionIngestConfig.__repr__` does not include the map, preventing routine configuration logging from enumerating authorized identities.

This is defense in depth. Cloud Run IAM or IAP upstream authorization should still be configured narrowly. The local map protects the application if upstream policy is accidentally broadened.

## Rotation

Treat subject-map changes as deployment configuration changes. Add the replacement subject before removing the old one when zero-downtime identity rotation is required. Do not use email addresses as stable authorization keys; use the verified Google/IAP subject identifier.

## Tests

Credential-free coverage is split between:

- `tests/test_google_identity.py` — signed-but-unauthorized subject denial, actor mapping, and error redaction;
- `tests/test_subject_authorization.py` — production configuration requirement, bounded JSON parsing, static/Google mode separation, and config repr redaction;
- `tests/test_production_ingest.py` — production composition with explicit subject policy.

Live Cloud Run/IAP policy still requires authorized deployment testing; these unit tests do not claim upstream IAM/IAP correctness.
