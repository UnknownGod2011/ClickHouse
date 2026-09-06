# TakeKeeper

**Production memory and continuity intelligence for film, television, and creator teams.**

TakeKeeper turns each recorded take into structured, evidence-backed production memory. Gemini-compatible multimodal extractors can produce observations; ClickHouse stores the durable history; and the official `ClickHouse/mcp-clickhouse` server is the read-side bridge for agentic production and editorial queries.

This repository is a **personal open-source project** and the implementation is actively being built here.

## What works today

- ClickHouse DDL for takes, observations, approved continuity baselines, findings, human decisions, and safe agent-run summaries.
- A deterministic `Glass House` Scene 28 seed dataset.
- Continuity comparison logic with explicit `mismatch`, `needs_confirmation`, `insufficient_evidence`, and `missing_baseline` behavior.
- A transport-independent `ProductionMemory` protocol plus deterministic in-memory reference backend.
- `TakeAnalysisService` orchestration that validates production/scene/take scope, ingests observations, loads baselines, computes findings, and replaces stale findings on re-analysis.
- Hard-constraint ClickHouse query builders for continuity evidence and editorial retrieval.
- Tenant/scene/take scoping in both query and application-service layers.
- Deterministic tests for Scene 28 behavior, failure honesty, idempotent re-analysis, and cross-production isolation.

A live Gemini/ADK → official ClickHouse MCP → real ClickHouse round-trip is still unproven and must be measured rather than fabricated.

## Hero workflow

For fictional production `glass-house`, Scene 28, baseline `S28-T31` has Maya holding the mug in her right hand, jacket zipped, lamp on. `S28-T47` changes mug to left, jacket to open, and lamp to off at low confidence. The expected result is two mismatches plus one `needs_confirmation` finding.

The editorial query asks for takes where Maya says “I'm leaving”, looks toward the door afterward, the boom is not visible, and rating ≥4. Expected includes are `S28-T31` and `S28-T47`; `S28-T40` is excluded for eyeline and `S28-T44` for a visible boom.

## Repository map

- `src/takekeeper/continuity.py` — deterministic continuity comparison.
- `src/takekeeper/memory.py` — production-memory protocol and reference backend.
- `src/takekeeper/service.py` — scoped ingest/analyze/persist orchestration.
- `src/takekeeper/queries.py` — ClickHouse analytical query contracts.
- `tests/` — deterministic acceptance and pipeline tests.
- `sql/schema.sql` — ClickHouse production-memory schema.
- `sql/seed_demo.sql` — deterministic Scene 28 fixture.
- `ARCHITECTURE.md`, `VERTICAL_SLICE_SPEC.md`, `DATA_AND_QUERY_CONTRACT.md`, `MULTIMODAL_EXTRACTION_AND_EVAL.md` — design contracts.
- `progress.md` — exact current handoff.

## Run tests

Python 3.11+ is sufficient; runtime code currently has no third-party dependencies.

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## ClickHouse + MCP

Apply `sql/schema.sql`, then `sql/seed_demo.sql` to a real ClickHouse instance. The official MCP server should stay read-only for the agent path. Current upstream `ClickHouse/mcp-clickhouse` documents `run_query`, `list_databases`, and `list_tables`, and read-only is the default (`CLICKHOUSE_ALLOW_WRITE_ACCESS=false`). Network transports require authentication by default; stdio is appropriate for the first local proof.

Server-side environment shape:

```text
CLICKHOUSE_HOST=<host>
CLICKHOUSE_PORT=<port>
CLICKHOUSE_USER=<read-only-user>
CLICKHOUSE_PASSWORD=<secret>
CLICKHOUSE_SECURE=true
CLICKHOUSE_VERIFY=true
CLICKHOUSE_ALLOW_WRITE_ACCESS=false
```

Never expose these values to browser code or commit them.

## Source-of-truth boundaries

ClickHouse owns durable production facts; object storage owns raw media; agent session state is temporary; official MCP is the analytical read path; ingestion and human decisions use a separately permissioned application write path.

Machine perception is candidate evidence, not automatic truth. Low-confidence differences request confirmation, and absent evidence never becomes fabricated absence.

## Next milestone

Implement a real ClickHouse-backed `ProductionMemory` adapter that preserves the tested scope/idempotency contract, then pass **Gemini/ADK → official `ClickHouse/mcp-clickhouse` → real ClickHouse → one seeded fact** as soon as a reachable ClickHouse/Gemini environment exists. Record actual ClickHouse/MCP versions, transport, auth, tool name, rows, latency, and read-only verification before coupling the agent to MCP response details.

## References

- https://github.com/ClickHouse/mcp-clickhouse
- https://clickhouse.com/blog/the-agentic-data-stack
- https://clickhouse.com/blog/10-best-practice-tips
- https://ai.google.dev/gemini-api/docs/video-understanding

## License

Apache-2.0. See `LICENSE`.
