# ClickHouse schema readiness

TakeKeeper's trusted extraction writer must not use the first production take as a schema-migration detector. Before enabling ingestion for a deployment, run the application connection through `require_extraction_schema_ready(...)` from `takekeeper.schema_preflight`.

```python
from takekeeper.schema_preflight import require_extraction_schema_ready

# `client` is the separately permissioned trusted application ClickHouse client.
require_extraction_schema_ready(client, database="takekeeper")
# Only construct/enable the extraction ingest worker after this succeeds.
```

The preflight is read-only. It performs two bounded parameterized reads from `system.columns`: one for `extraction_runs` and one for `extracted_observations`. It reads no take rows, media locators, content hashes, production identifiers, model output, or credentials.

The gate verifies the exact columns/types required by the current extraction persistence adapter, including migration `002_extraction_media_provenance.sql` fields:

- `media_mime_type`
- `media_content_sha256`
- `media_byte_size`

If required columns are missing or incompatible, `ClickHouseSchemaNotReady` is raised with an intentionally coarse remediation message. The exception does not echo the ClickHouse host, database name, production data, media URI, content hash, observed database type, credentials, or provider exception payload.

For a fresh deployment apply `sql/schema.sql`. For an existing deployment apply pending files under `sql/migrations/` in order, then rerun the preflight before enabling ingestion.

This check belongs on the trusted application connection, not the agent-facing ClickHouse MCP connection. MCP remains read-only and independently permissioned.

## Deployment pattern

A production process should treat schema readiness as a startup/deployment gate rather than a high-frequency liveness probe:

1. Create the trusted ClickHouse application client from server-side configuration.
2. Run `require_extraction_schema_ready(...)` once before accepting ingestion traffic or starting extraction workers.
3. Fail the deployment/readiness transition if it raises.
4. Apply migrations out of band with appropriately privileged credentials.
5. Restart/recheck with the normal lower-privilege application connection.

Do not grant migration privileges to Gemini, the operator browser, or the ClickHouse MCP server merely to make this check pass.
