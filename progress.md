# TakeKeeper Progress

## Current status

The repository now has a concrete judge-ready vertical slice **and** a ClickHouse-specific data/query contract. The product concept, sponsor story, logical architecture, evidence rules, exact demo fixture, query semantics, scale-test strategy, and implementation acceptance gates are now sufficiently specified for a hackathon-permitted Gemini implementation session.

The next engineering milestone remains deliberately narrow: prove one real Gemini/ADK → official ClickHouse MCP → real ClickHouse read before spending time on UI or video extraction.

## Inspected this run

- Read the existing `progress.md` completely before making changes.
- Re-read `README.md`, `ARCHITECTURE.md`, and `VERTICAL_SLICE_SPEC.md` to avoid duplicating earlier work.
- Checked current ClickHouse guidance on schema/query optimization, projections/materialized views, JSON, and recent search capabilities.
- Confirmed that the MVP should keep hero continuity predicates in explicit typed columns and avoid speculative optimization until real query traces exist.

## Changes made this run

### Created `DATA_AND_QUERY_CONTRACT.md`
Added the implementation-facing contract for the ClickHouse production-memory layer:

- source-of-truth boundaries for ClickHouse, object storage, and agent session state;
- MVP table semantics for `takes`, `observations`, `continuity_baselines`, `continuity_findings`, `human_decisions`, and `agent_runs`;
- hero continuity property keys for the deterministic `Glass House` demo;
- guidance to keep frequently queried continuity facts typed/columnar rather than buried in flexible JSON;
- continuity-check query contract and exact expected result for `S28-T47`;
- editorial-retrieval hard-constraint contract and exact include/exclude expectations;
- MCP read discipline requiring a fresh production-state read before factual answers;
- tenant-isolation contract requiring `production_id` scoping plus application authorization;
- evidence contract for every finding/result;
- two-tier evaluation plan: deterministic demo + synthetic metadata/observation scale test;
- explicit optimization-trigger policy so projections/materialized views are introduced only after measured need;
- Gate A runtime-evidence template to record actual ClickHouse/MCP/runtime details instead of assumptions;
- post-Gate-A implementation sequence.

### Updated `README.md`
- Linked `DATA_AND_QUERY_CONTRACT.md` directly from the architecture section.
- Added current ClickHouse best-practice guidance to the references.
- Clarified that the repository now contains three implementation handoff layers: architecture, vertical slice, and data/query contract.

## Key decisions now locked

1. **Typed columns for hero predicates.** Mug hand, jacket state, lamp state, eyeline, boom visibility, dialogue presence, confidence, take identity, and ratings should not be hidden inside opaque metadata for the MVP.
2. **ClickHouse remains durable production memory; raw media stays in object storage.**
3. **Agent session memory is not authoritative.** Any answer about production state must re-read ClickHouse through MCP.
4. **Hard editorial constraints should be enforced from structured data rather than post-hoc LLM intuition.**
5. **Every query is production-scoped.** `production_id` isolation and application authorization are part of the product contract, not optional polish.
6. **No speculative ClickHouse optimization.** Start with a simple MergeTree-family direction and measure actual query latency/scans before considering projections/materialized views.
7. **Scale claims must be measured.** The final README/demo should report real observed latency rather than marketing claims.
8. **Gate A evidence must be recorded factually.** Exact transport/auth/version/tool/row-count/latency details stay unknown until the permitted implementation session proves them.

## Current acceptance gates

### Gate A — Sponsor integration
A real Gemini/ADK agent makes a real runtime call through official `ClickHouse/mcp-clickhouse` to a real ClickHouse service and uses the returned fact in its answer.

### Gate B — Continuity correctness
`S28-T47` produces mug-hand + jacket mismatches while lamp remains uncertain rather than asserted as fact.

### Gate C — Evidence
Every continuity finding references its baseline and evidence timestamp/frame window.

### Gate D — Editorial retrieval
The fixed query returns `S28-T31` and `S28-T47`, excluding `S28-T40` for wrong eyeline and `S28-T44` for visible boom.

### Gate E — Failure honesty
If ClickHouse/MCP is unavailable or has no supporting data, the agent fails visibly and does not fabricate production history.

### Gate F — Security
MCP is read-only and no ClickHouse/MCP credentials reach the browser.

Do not spend significant time on automatic video extraction or visual polish until A–F pass.

## Important current technical facts

- The official `ClickHouse/mcp-clickhouse` path remains the required runtime bridge for the sponsor story.
- Its core analytical tools include `run_query`, `list_databases`, and `list_tables`; the MVP should keep the agent read-only.
- Current ClickHouse guidance favors designing ordering/sort keys around actual access patterns and using projections/materialized views only when their read benefits justify additional write/storage cost.
- Recent ClickHouse releases provide mature JSON, full-text, and vector-search capabilities that may be useful later, but **none is necessary to prove the TakeKeeper MVP**.
- The current deterministic query contract is intentionally structured so the demo does not depend on fuzzy search or ambiguous perception.

## Risks / unresolved blockers

1. **No submitted implementation exists yet** by design; code must be produced with hackathon-permitted Google/partner tooling.
2. **Gate A is still unproven:** exact deployed Gemini/ADK ↔ official ClickHouse MCP connection/auth method must be tested in the implementation environment.
3. **No real ClickHouse service/demo database is provisioned yet.**
4. **No physical ClickHouse schema has been measured.** Sorting/engine decisions must be finalized against the real service/version and query traces.
5. **No demo footage exists.** The seeded contract is fixed, but self-created/authorized clips are still needed for multimodal expansion.
6. **Gemini extraction reliability is unknown** for some visual properties; start with obvious mug-hand/jacket/lamp/boom/eyeline states and measure against labels.
7. **License file is still missing.** The public submission requires an open-source license before final submission.
8. **Hosted UI, API service and MCP endpoint do not exist yet.** Keep these minimal until Gate A works.

## Highest-priority implementation backlog

### P0 — Gate A only
- Provision a minimal ClickHouse service/database.
- Create the smallest schema required for one known production fact using the contract in `DATA_AND_QUERY_CONTRACT.md`.
- Seed one known production fact.
- Run official `ClickHouse/mcp-clickhouse` with authentication and read-only access.
- Connect a Gemini/ADK agent using hackathon-permitted Google tooling.
- Ask for the known production fact and verify that the response demonstrably came through the MCP tool path.
- Record the Gate A runtime-evidence template from `DATA_AND_QUERY_CONTRACT.md` here.

### P0 — Gates B–D
- Seed the full `Glass House` Scene 28 fixture.
- Implement continuity comparison behavior.
- Implement evidence-backed findings.
- Implement the fixed editorial retrieval query and verify exact expected take IDs/exclusion reasons.

### P0 — Gates E–F
- Verify MCP/database outage behavior.
- Verify zero fabrication on empty result.
- Verify browser contains no database/MCP credentials.
- Keep MCP write access disabled.

### P1 — Product shell
- Take list + processing state.
- Continuity compare/findings view.
- Evidence viewer.
- Human confirm/reject action.
- Ask-production input.
- Safe agent-activity drawer.

### P1 — Multimodal expansion
- Create short self-owned demo clips matching the fixed fixture.
- Gemini multimodal extraction into the strict observation contract.
- Compare extraction against ground truth before enabling a property in the judge flow.

### P2 — production readiness / submission
- Synthetic scale dataset + measured ClickHouse/MCP latency.
- Failure-state UX.
- Evaluation matrix.
- Hosted deployment/runbook.
- Public license.
- README setup/test instructions.
- Deterministic 3-minute recording showing genuine Google Cloud + ClickHouse runtime use.

## Single best next step

**Using Gemini CLI / Gemini Code Assist or another hackathon-permitted Google/partner implementation tool, pass Gate A only: provision the smallest real ClickHouse dataset, connect the official authenticated read-only ClickHouse MCP server, and make a real Gemini/ADK runtime retrieve one seeded production fact.**

Immediately record the actual ClickHouse version, MCP version/commit, transport, auth mode, tool invoked, row count, tool latency, end-to-end latency, read-only verification, and any runtime limitation using the evidence template in `DATA_AND_QUERY_CONTRACT.md`. Those measured facts should determine the final physical schema and deployment choices.

## Sources

- https://agentic-cinema.devpost.com/
- https://agentic-cinema.devpost.com/rules
- https://agentic-cinema.devpost.com/details/dates
- https://github.com/ClickHouse/mcp-clickhouse
- https://clickhouse.com/blog/the-agentic-data-stack
- https://clickhouse.com/blog/10-best-practice-tips
- https://clickhouse.com/blog/what-a-difference-10-years-of-open-source-makes
- https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder/connect-mcp-servers
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/
