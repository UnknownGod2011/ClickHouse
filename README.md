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
- Hard-constraint editorial/continuity SQL builders.
- Tests for Scene 28 behavior, tenant isolation, idempotency, failure honesty, and ClickHouse adapter safety.

A live Gemini/ADK → official ClickHouse MCP → real ClickHouse round-trip is still unproven and must be measured rather than fabricated.

## Repository map

- `src/takekeeper/continuity.py` — deterministic continuity comparison.
- `src/takekeeper/memory.py` — production-memory protocol and in-memory reference backend.
- `src/takekeeper/clickhouse_memory.py` — separately permissioned ClickHouse application persistence adapter.
- `src/takekeeper/service.py` — scoped ingest/analyze/persist orchestration.
- `src/takekeeper/queries.py` — ClickHouse analytical query contracts.
- `tests/` — deterministic acceptance, pipeline, and adapter tests.
- `sql/schema.sql` / `sql/seed_demo.sql` — durable schema and Scene 28 fixture.
- `progress.md` — exact current handoff.

## Run tests

Python 3.11+ is sufficient for the core:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Install the production ClickHouse client only when using the database adapter:

```bash
pip install -e '.[clickhouse]'
```

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

Apply `sql/schema.sql`, then `sql/seed_demo.sql` to a real ClickHouse instance. The findings schema uses nullable evidence fields so `insufficient_evidence` and `missing_baseline` remain representable without fabricated values.

## Hero workflow

For fictional production `glass-house`, Scene 28, baseline `S28-T31` has Maya holding the mug in her right hand, jacket zipped, lamp on. `S28-T47` changes mug to left, jacket to open, and lamp to off at low confidence. The expected result is two mismatches plus one `needs_confirmation` finding.

The editorial query asks for takes where Maya says “I'm leaving”, looks toward the door afterward, the boom is not visible, and rating ≥4. Expected includes are `S28-T31` and `S28-T47`; `S28-T40` is excluded for eyeline and `S28-T44` for a visible boom.

## Safety and data boundaries

ClickHouse owns durable production facts; object storage owns raw media; agent session state is temporary; official MCP is the analytical read path; ingestion and human decisions use a separately permissioned application write path.

Machine perception is candidate evidence, not automatic truth. Low-confidence differences request confirmation, and absent evidence never becomes fabricated absence. Tenant identifiers are always bound query parameters rather than interpolated SQL.

## Next milestone

Run the real ClickHouse adapter against a local/Cloud instance, execute schema + seed, assert exact Scene 28 persistence/re-analysis behavior, then pass **Gemini/ADK → official `ClickHouse/mcp-clickhouse` → one seeded fact** and record actual versions, transport, auth, tool payload, rows, latency, and read-only verification.

## References

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://ai.google.dev/gemini-api/docs/video-understanding

## License

Apache-2.0. See `LICENSE`.
