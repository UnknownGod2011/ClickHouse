# TakeKeeper

**Production memory and continuity intelligence for film, television, and creator teams.**

TakeKeeper turns each recorded take into structured, evidence-backed production memory. Gemini-compatible multimodal extractors can produce observations; ClickHouse stores durable history; and the official `ClickHouse/mcp-clickhouse` server is the read-side bridge for agentic production and editorial queries.

This repository is a **personal open-source project** and the implementation is actively being built here.

## What works today

- Deterministic continuity comparison with explicit `mismatch`, `needs_confirmation`, `insufficient_evidence`, and `missing_baseline`.
- `ProductionMemory` port with both in-memory and real ClickHouse-backed implementations.
- `TakeAnalysisService` with production/scene/take scope enforcement and stale-finding replacement on re-analysis.
- ClickHouse DDL and deterministic `Glass House` Scene 28 seed data.
- Parameter-bound ClickHouse reads/deletes and bulk inserts through the official `clickhouse-connect` client surface.
- Hard-constraint editorial/continuity SQL builders with validated configurable database identifiers.
- A bounded `McpEvidenceReader` for the official MCP `run_query` tool. It only emits TakeKeeper-owned scoped SQL, validates production/scene/take scope on returned rows, records query latency/row-count provenance, and fails closed on malformed/tool-error/wrong-tenant responses.
- Environment-gated real ClickHouse integration tests that create an isolated ephemeral database, apply schema + seed, verify the Scene 28 contract, verify editorial retrieval, prove stale-finding deletion, and then drop the database.
- Tests for Scene 28 behavior, tenant isolation, idempotency, failure honesty, ClickHouse adapter safety, and MCP response parsing.

A live Gemini/ADK → official ClickHouse MCP → real ClickHouse round-trip is still unproven and must be measured rather than fabricated.

## Repository map

- `src/takekeeper/continuity.py` — deterministic continuity comparison.
- `src/takekeeper/memory.py` — production-memory protocol and in-memory reference backend.
- `src/takekeeper/clickhouse_memory.py` — separately permissioned ClickHouse application persistence adapter.
- `src/takekeeper/mcp_reader.py` — bounded, fail-closed read-only MCP evidence adapter.
- `src/takekeeper/service.py` — scoped ingest/analyze/persist orchestration.
- `src/takekeeper/queries.py` — ClickHouse analytical query contracts.
- `tests/test_clickhouse_integration.py` — opt-in real-database acceptance harness.
- `tests/test_mcp_reader.py` — MCP payload/scope/failure tests without credentials.
- `tests/` — deterministic acceptance, pipeline, adapter, and query tests.
- `sql/schema.sql` / `sql/seed_demo.sql` — durable schema and Scene 28 fixture.
- `progress.md` — exact current handoff.

## Run tests

Python 3.11+ is sufficient for the core:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

The real ClickHouse integration suite is skipped by default. Install the official client extra and explicitly opt in when a disposable/local or otherwise authorized ClickHouse instance is available:

```bash
pip install -e '.[clickhouse]'
TAKEKEEPER_CLICKHOUSE_INTEGRATION=1 \
CLICKHOUSE_HOST=localhost \
CLICKHOUSE_PORT=8123 \
CLICKHOUSE_USER=default \
CLICKHOUSE_PASSWORD='' \
PYTHONPATH=src python -m unittest tests.test_clickhouse_integration -v
```

For ClickHouse Cloud, set `CLICKHOUSE_SECURE=true`, use the service port/credentials supplied by ClickHouse, and optionally set `CLICKHOUSE_BOOTSTRAP_DATABASE` if the credential does not default to `default`.

The integration harness creates a uniquely named `takekeeper_it_<suffix>` database, rewrites the checked-in schema/seed to that isolated database, runs assertions, and drops the database in teardown. **Only enable it with a credential that is allowed to create/drop a temporary database.** No secrets are read from files or committed.

Construct the official client outside the domain layer and pass it to `ClickHouseProductionMemory`:

```python
import clickhouse_connect
from takekeeper import ClickHouseProductionMemory

client = clickhouse_connect.get_client(
    host="localhost",
    port=8123,
    username="takekeeper_app",
    password="...",
)
memory = ClickHouseProductionMemory(client)
```

Use a separately permissioned application credential for this write adapter. Do **not** reuse the agent/MCP credential.

## ClickHouse + MCP boundary

The application persistence path may insert/update production memory. The agent-facing official `ClickHouse/mcp-clickhouse` connection remains read-only (`CLICKHOUSE_ALLOW_WRITE_ACCESS=false`) and is only used for analytical retrieval. This prevents model-directed writes from bypassing application validation and human-control boundaries.

`McpEvidenceReader` accepts a host-supplied `call_tool(name, arguments)` function and only invokes `run_query` using TakeKeeper's own typed query builders. It does not expose an arbitrary SQL method to the model-facing layer. Continuity/editorial queries now project their scope identifiers so every returned row can be rejected if it crosses production, scene, or take boundaries.

The parser supports the official server's current JSON-string query result plus MCP text-content envelopes and a small future-compatible structured wrapper. Transport failure, tool error, malformed JSON, malformed rows, wrong scope, impossible confidence, or invalid evidence windows all raise `McpReadError` instead of fabricating evidence.

Apply `sql/schema.sql`, then `sql/seed_demo.sql` to a real ClickHouse instance. The findings schema uses nullable evidence fields so `insufficient_evidence` and `missing_baseline` remain representable without fabricated values.

## Hero workflow

For fictional production `glass-house`, Scene 28, baseline `S28-T31` has Maya holding the mug in her right hand, jacket zipped, lamp on. `S28-T47` changes mug to left, jacket to open, and lamp to off at low confidence. The expected result is two mismatches plus one `needs_confirmation` finding.

The editorial query asks for takes where Maya says “I'm leaving”, looks toward the door afterward, the boom is not visible, and rating ≥4. Expected includes are `S28-T31` and `S28-T47`; `S28-T40` is excluded for eyeline and `S28-T44` for a visible boom.

## Safety and data boundaries

ClickHouse owns durable production facts; object storage owns raw media; agent session state is temporary; official MCP is the analytical read path; ingestion and human decisions use a separately permissioned application write path.

Machine perception is candidate evidence, not automatic truth. Low-confidence differences request confirmation, and absent evidence never becomes fabricated absence. Tenant identifiers are scoped in generated analytical SQL and validated again on MCP response rows. Trusted persistence uses parameter binding; dynamic database identifiers are separately validated and restricted to letters, digits, and underscores.

## Next milestone

Run the opt-in real ClickHouse integration harness on a local/Cloud instance and record concrete ClickHouse/client versions and timings. Then start official `ClickHouse/mcp-clickhouse` in read-only mode against the seeded database, inject its `run_query` transport into `McpEvidenceReader`, prove the exact Scene 28 continuity/editorial results, and capture actual MCP version, transport, auth, payload, row count, latency, and explicit write-denial behavior.

## References

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://ai.google.dev/gemini-api/docs/video-understanding

## License

Apache-2.0. See `LICENSE`.
