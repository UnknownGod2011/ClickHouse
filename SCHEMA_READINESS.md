# ClickHouse schema readiness

TakeKeeper's trusted extraction writer must not use the first production take as a schema-migration detector. Production ingestion now has a canonical fail-closed boundary: `SchemaGatedIngestService` starts closed and will not invoke Gemini/extraction or persistence until the trusted application ClickHouse connection passes `require_extraction_schema_ready(...)`.

```python
import clickhouse_connect
from takekeeper import (
    ClickHouseExtractionProvenanceStore,
    GoogleGenAIExtractionTransport,
    GovernedMultimodalExtractor,
    SchemaGatedIngestService,
)

# Build the server-side trusted application client with a separately permissioned credential.
client = clickhouse_connect.get_client(...)
store = ClickHouseExtractionProvenanceStore(client, database="takekeeper")
extractor = GovernedMultimodalExtractor(GoogleGenAIExtractionTransport(...))

ingest = SchemaGatedIngestService(
    clickhouse_client=client,
    extractor=extractor,
    provenance_store=store,
    database="takekeeper",
)

ingest.start()  # fail closed here if schema metadata is missing/incompatible
assert ingest.readiness().ready

# Only after start() succeeds may a trusted TakeExtractionRequest be accepted.
result = ingest.ingest(request)
```

The preflight is read-only. It performs two bounded parameterized reads from `system.columns`: one for `extraction_runs` and one for `extracted_observations`. It reads no take rows, media locators, content hashes, production identifiers, model output, or credentials.

The gate verifies the exact columns/types required by the current extraction persistence adapter, including migration `002_extraction_media_provenance.sql` fields:

- `media_mime_type`
- `media_content_sha256`
- `media_byte_size`

If required columns are missing or incompatible, `ClickHouseSchemaNotReady` is raised with an intentionally coarse remediation message. A provider/transport failure is wrapped as `IngestBootstrapError`; its public message does not copy provider exception text. In both cases the ingestion boundary stays closed.

`start()` is also a revalidation operation. It revokes readiness *before* rechecking, so a failed post-deploy schema verification cannot leave a previously-ready process accepting new takes. `close()` explicitly revokes readiness without touching ClickHouse or historical extraction records.

`readiness()` intentionally exposes only two coarse fields: `state` (`ready` or `not_ready`) and whether the schema check completed. It does not expose hosts, database names, schema diffs, provider details, media/tenant identifiers, hashes, or credentials.

For a fresh deployment apply `sql/schema.sql`. For an existing deployment apply pending files under `sql/migrations/` in order, then restart/recheck before enabling ingestion.

This check belongs on the trusted application connection, not the agent-facing ClickHouse MCP connection. MCP remains read-only and independently permissioned.

## Deployment pattern

A production process should treat schema readiness as a startup/deployment gate rather than a high-frequency liveness probe:

1. Create the trusted ClickHouse application client from server-side configuration.
2. Construct the extraction transport/extractor and `ClickHouseExtractionProvenanceStore`.
3. Construct `SchemaGatedIngestService`; it is closed by default.
4. Call `start()` before marking the worker/API ready or accepting ingestion traffic.
5. If startup fails, keep the deployment unready and apply migrations out of band with appropriately privileged credentials.
6. Restart/recheck with the normal lower-privilege application connection.
7. Route trusted take ingestion only through `SchemaGatedIngestService.ingest(...)`.

Do not grant migration privileges to Gemini, the operator browser, or the ClickHouse MCP server merely to make this check pass.
