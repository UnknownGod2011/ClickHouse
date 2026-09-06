# TakeKeeper Progress

## Current status

TakeKeeper has moved from specification-only to an executable personal open-source implementation. The repository now contains a deterministic production-memory core, ClickHouse DDL/seed data, and tests for the fixed Scene 28 continuity contract.

The highest-value unresolved milestone is the live integration proof: **real Gemini/ADK → official `ClickHouse/mcp-clickhouse` → real ClickHouse**. This run implemented everything useful that can be validated without external credentials while keeping that live claim unproven.

## Inspected this run

- Read `progress.md` completely before deciding what to change.
- Inspected the repository root and confirmed it previously contained specifications/docs only.
- Re-read `README.md` and `DATA_AND_QUERY_CONTRACT.md` so code matches the existing table/query/evidence contract.
- Re-checked the current upstream `ClickHouse/mcp-clickhouse` README: `run_query`, `list_databases`, `list_tables`; read-only query mode by default; network transports authenticate by default; stdio is suitable for a local first proof.

## Changes made this run

- Added `src/takekeeper/models.py`, `continuity.py`, `queries.py`, `fixtures.py`, and package exports.
- Implemented deterministic outcomes: `mismatch`, `needs_confirmation`, `insufficient_evidence`, `missing_baseline`.
- Added `sql/schema.sql` with MergeTree tables for takes, observations, baselines, findings, human decisions, and agent-run summaries.
- Added `sql/seed_demo.sql` with `S28-T31`, `S28-T40`, `S28-T44`, `S28-T47` and approved Scene 28 baselines.
- Added tests for exact Scene 28 behavior, missing evidence honesty, validation, query scoping, editorial constraints, and SQL escaping.
- Added `pyproject.toml`, `.gitignore`, and Apache-2.0 `LICENSE`.
- Rewrote `README.md` to reflect the personal open-source implementation status and runnable core.

## Validation

Local deterministic validation performed before commit:

```text
Ran 6 tests
OK
```

The fixed contract now executes in code: `S28-T47` produces mug-hand + jacket mismatches and a low-confidence lamp confirmation request. The editorial SQL encodes the exact rating/dialogue/eyeline/boom hard constraints.

## Decisions locked

1. Domain logic stays transport-independent and testable without credentials.
2. ClickHouse remains durable production memory; media stays in object storage.
3. Official ClickHouse MCP remains the read-only agent path.
4. Ingestion/human decisions use a separately permissioned write path.
5. Missing evidence never becomes inferred absence.
6. The fixed Scene 28 fixture is executable ground truth for integration tests.
7. Hard editorial filters are database constraints, not LLM post-filtering.
8. Runtime MCP/auth/version details must be measured, not guessed.

## Gates

- **Gate A live integration:** NOT YET PROVEN.
- **Gate B continuity correctness:** CORE LOGIC IMPLEMENTED; live DB path pending.
- **Gate C evidence:** CORE MODEL IMPLEMENTED; UI path pending.
- **Gate D editorial retrieval:** SQL IMPLEMENTED; live DB assertion pending.
- **Gate E failure honesty:** domain missing-evidence behavior tested; MCP outage/empty-result integration pending.
- **Gate F security:** design preserved; runtime verification pending.
- **Gate G multimodal evidence:** not started; governed by `MULTIMODAL_EXTRACTION_AND_EVAL.md`.

## Blockers / unknowns

1. No real ClickHouse service is reachable from this automation environment, so schema/seed SQL could not be executed against ClickHouse here.
2. No Gemini/Google runtime credentials are available here, so Gate A cannot be truthfully claimed.
3. Actual ClickHouse version, MCP version/commit, transport/auth, payload shape, and latency remain unmeasured.
4. No self-owned demo footage exists yet; structured fixture work intentionally comes first.

## Highest-priority backlog

- Run `sql/schema.sql` and `sql/seed_demo.sql` against a real ClickHouse instance.
- Verify editorial SQL returns exactly `S28-T31` and `S28-T47`.
- Start official `mcp-clickhouse` read-only and connect a real Gemini/ADK client.
- Retrieve one seeded fact through `run_query` and record versions/transport/auth/tool/rows/latency/read-only proof.
- Add a thin MCP evidence-reader adapter around the measured client API.
- Add integration tests for outage, empty result, wrong production scope, and exact Scene 28 results.
- Then add separately permissioned ingestion writes, persisted findings/human decisions, minimal API/UI, and eventually Gemini multimodal extraction.

## Single best next step

**Execute `sql/schema.sql` + `sql/seed_demo.sql` on a real ClickHouse instance, then use official read-only `ClickHouse/mcp-clickhouse` to make one real `run_query` request for the seeded `glass-house` production.**

Immediately record the actual ClickHouse/MCP versions, transport, auth mode, payload shape, row count, MCP latency, end-to-end latency, and read-only verification; then implement the thin measured MCP adapter instead of guessing its client API.

## Sources checked

- https://github.com/ClickHouse/mcp-clickhouse
- https://clickhouse.com/blog/the-agentic-data-stack
- https://clickhouse.com/blog/10-best-practice-tips
- https://ai.google.dev/gemini-api/docs/video-understanding
