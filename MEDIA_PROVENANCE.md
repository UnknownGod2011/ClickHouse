# TakeKeeper media provenance

TakeKeeper treats a media locator and the bytes it points to as different identities. A signed URL or `gs://` locator can change while referencing the same object, and a mutable locator can reference different bytes over time. Production ingest should therefore record both when possible.

## Trusted media contract

`takekeeper.media_provenance` provides a dependency-free ingest boundary for production media:

- only `https://` and `gs://` locators are accepted;
- embedded URL credentials are rejected;
- supported video MIME types are allow-listed;
- extensionless signed/object URLs require trusted explicit MIME metadata;
- when an inferable suffix and explicit MIME metadata disagree, ingest fails closed;
- the complete locator is SHA-256 fingerprinted so downstream reports can refer to its identity without copying a signed/private URI;
- optional content SHA-256 and byte size provide actual byte identity when available.

The locator fingerprint is **not** a content hash. It proves which exact trusted locator string was supplied, including query parameters, but it does not prove the bytes served by that locator.

## Local ingest hashing

`hash_local_media()` streams an operator-owned local file and returns its SHA-256, byte size, and validated video MIME type. It deliberately:

- does not upload or mutate media;
- does not follow symlinks;
- rejects non-regular or empty files;
- enforces a configurable maximum byte size;
- bounds read chunk size;
- fails if file size changes during hashing.

Example:

```python
from takekeeper.media_provenance import build_media_provenance, hash_local_media

local = hash_local_media("/secure-ingest/scene12-take47.mp4")

provenance = build_media_provenance(
    media_uri="gs://production-private/scene12/take47",
    duration_ms=18_420,
    mime_type=local.mime_type,
    content_sha256=local.content_sha256,
    byte_size=local.byte_size,
)
```

This enables a production ingest adapter to hash bytes before upload, then persist the digest alongside the immutable/versioned object locator. Hashing should happen before model analysis where the production workflow can safely access the original bytes.

## Extensionless production media

Many private delivery systems expose signed URLs whose path has no file extension. URI suffix inference is therefore insufficient for production. In those cases the ingest layer must supply MIME type from trusted upload/object metadata, for example `video/mp4`. Model output must never choose MIME type.

The current Google transport still performs its own URI-suffix check. The next wiring step is to carry this trusted MIME metadata through `TakeExtractionRequest` / `ExtractionPrompt` so the Google adapter can consume extensionless media without weakening its scheme, host, credential, or video allow-list validation.

## Security notes

Do not log signed URLs. Prefer the locator SHA-256 in benchmark/audit records. A content SHA-256 can be logged or persisted as an identifier, but whether it is sensitive depends on the production's threat model and data-retention policy.

Content hashes do not replace authorization, tenant isolation, object-store ACLs, encryption, or retention controls. They are provenance evidence only.
