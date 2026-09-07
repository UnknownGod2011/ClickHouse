-- TakeKeeper extraction media provenance migration.
-- Safe for existing deployments: all new columns are nullable/defaulted so older rows remain valid.
-- Apply once after sql/schema.sql when upgrading an existing database.

ALTER TABLE takekeeper.extraction_runs
    ADD COLUMN IF NOT EXISTS media_mime_type LowCardinality(Nullable(String)) AFTER media_fingerprint;

ALTER TABLE takekeeper.extraction_runs
    ADD COLUMN IF NOT EXISTS media_content_sha256 Nullable(FixedString(64)) AFTER media_mime_type;

ALTER TABLE takekeeper.extraction_runs
    ADD COLUMN IF NOT EXISTS media_byte_size Nullable(UInt64) AFTER media_content_sha256;

-- These fields are trusted ingest provenance. They must never be populated from model output.
-- `media_content_sha256` identifies bytes when available; `media_fingerprint` remains locator+duration identity.
