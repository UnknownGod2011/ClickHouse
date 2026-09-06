# TakeKeeper Progress

## Current status

The repository now has a concrete judge-ready vertical-slice contract in addition to the product/architecture specification. The project is ready for a hackathon-permitted Gemini implementation session to prove sponsor integration before broader UI/video work.

## Inspected this run

- Read the existing `progress.md` completely before making changes.
- Re-read `README.md` and `ARCHITECTURE.md` to avoid duplicating prior work.
- Re-checked the current official `ClickHouse/mcp-clickhouse` repository.
- Verified current official MCP behavior relevant to deployment: `run_query`, `list_databases`, `list_tables`, read-only-by-default query mode, authenticated HTTP/SSE transports by default, and a network health endpoint.
- Checked current Google Gemini Enterprise documentation for connecting MCP-compatible endpoints and exposing MCP tools to Gemini agent/workflow steps.
- Reviewed current ClickHouse agent/MCP ecosystem references to keep the design aligned with ClickHouse's agentic data positioning.

## Changes made this run

### Created `VERTICAL_SLICE_SPEC.md`
Locked the smallest end-to-end workflow that should be implemented first:

**Gemini request → official ClickHouse MCP → real ClickHouse production memory → evidence-backed continuity comparison → human uncertainty resolution → second MCP-backed editorial retrieval query.**

The new spec defines:
- deterministic fictional production (`Glass House`);
- exact Scene 28 baseline/current-take facts;
- expected continuity findings;
- four retrieval candidates and the exact expected editorial-query result;
- minimum data contract;
- ClickHouse physical-design guidance without prematurely generating submitted SQL/code;
- official MCP security/runtime contract;
- four initial agent intents;
- rule that production facts must be re-read through ClickHouse MCP rather than trusted from conversational memory;
- continuity confidence/uncertainty behavior;
- human-in-the-loop contract;
- judge-visible agent activity requirements;
- six pass/fail acceptance gates;
- multimodal extraction expansion order;
- target deployment topology;
- exact 3-minute demo choreography;
- post-hackathon real-user onboarding path;
- one exact next implementation action.

### Updated `README.md`
- Linked `VERTICAL_SLICE_SPEC.md` as the concrete implementation contract.
- Added the current Gemini Enterprise MCP workflow documentation to source references.
- Clarified that implementation should use the vertical-slice gate sequence before expanding scope.

## Key decisions now locked

1. **Do not start with video upload or extraction.** First prove the real Gemini/ADK → official ClickHouse MCP → ClickHouse loop against deterministic seeded data.
2. **Hero demo production is fixed:** `Glass House`, Scene 28, baseline `S28-T31`, current take `S28-T47`.
3. **Hero continuity differences are fixed:** mug hand `right → left`, jacket `zipped → open`, and intentionally uncertain lamp state.
4. **Hero retrieval query is fixed:** Maya says “I’m leaving”, looks toward the door afterward, boom not visible, rating ≥4. Expected results are `S28-T31` and `S28-T47` only.
5. **MCP remains read-only.** Human-resolution/ingestion writes use a separate backend credential/path.
6. **Production-state answers require a fresh ClickHouse MCP read.** Conversation/session memory is not authoritative production truth.
7. **No opaque continuity score.** Findings expose baseline, observed value, evidence, confidence, verification state and status.
8. **Missing observations are `insufficient_evidence`, not continuity mismatches.**
9. **Judge-visible tool activity is required.** The UI should expose safe tool name/query-purpose/row-count/latency stages without secrets or hidden chain-of-thought.
10. **Multimodal extraction is an expansion after sponsor compliance passes.** Replace seeded observations incrementally with real Gemini extraction and keep only reliably detectable continuity properties.

## Acceptance gates for implementation

### Gate A — Sponsor integration
A real Gemini/ADK agent makes a real runtime call through official `ClickHouse/mcp-clickhouse` to a real ClickHouse service and uses the returned fact in its answer.

### Gate B — Continuity correctness
`S28-T47` produces mug-hand + jacket mismatches while lamp remains uncertain rather than asserted as fact.

### Gate C — Evidence
Every continuity finding references its baseline and evidence timestamp/frame window.

### Gate D — Editorial retrieval
The fixed query returns `S28-T31` and `S28-T47`, excluding the two deliberately invalid candidates for explicit reasons.

### Gate E — Failure honesty
If ClickHouse/MCP is unavailable or has no supporting data, the agent fails visibly and does not fabricate production history.

### Gate F — Security
MCP is read-only and no ClickHouse/MCP credentials reach the browser.

Do not spend significant time on automatic video extraction or visual polish until A–F pass.

## Important current technical facts

- The official `ClickHouse/mcp-clickhouse` server currently implements MCP `2026-07-28` while retaining compatibility with older initialization handshakes.
- Its core ClickHouse tools include `run_query`, `list_databases`, and `list_tables`.
- Query execution is read-only by default unless write access is explicitly enabled.
- HTTP/SSE network modes require authentication by default; static bearer token and OAuth/OIDC modes are supported.
- The official server exposes `/health` for network deployment readiness checks.
- Current Gemini Enterprise Workflow Builder documentation supports connecting MCP-compatible endpoints and adding MCP tools to Gemini agent steps.
- The hackathon submission deadline remains **September 9, 2026 at 2:00 PM PDT / September 10, 2026 at 2:30 AM IST** based on the current Devpost schedule previously inspected.

## Risks / unresolved blockers

1. **No submitted implementation exists yet** by design; code must be produced with hackathon-permitted Google/partner tooling.
2. **Gate A is still unproven:** exact deployed Gemini/ADK ↔ official ClickHouse MCP connection/auth method must be tested in the implementation environment.
3. **No real ClickHouse service/demo database is provisioned yet.**
4. **No demo footage exists.** The seeded data contract is fixed, but self-created/authorized clips are still needed for the multimodal expansion.
5. **Physical ClickHouse engines/ORDER BY/partition choices are not frozen.** Validate against real query patterns and current ClickHouse best practices during implementation.
6. **Gemini extraction reliability is unknown** for some visual properties; start with obvious mug-hand/jacket/lamp/boom/eyeline states and measure against labels.
7. **License file is still missing.** The public submission requires an open-source license; choose/add it before final submission.
8. **Hosted UI, API service and MCP endpoint do not exist yet.** Keep these minimal until Gate A works.

## Highest-priority implementation backlog

### P0 — Gate A only
- Provision a minimal ClickHouse service/database.
- Create the smallest schema required for one production fact.
- Seed one known production fact.
- Run official `ClickHouse/mcp-clickhouse` with authentication and read-only access.
- Connect a Gemini/ADK agent using hackathon-permitted Google tooling.
- Ask for the known production fact and verify that the response demonstrably came through the MCP tool path.
- Record exact connection method, authentication mode, observed MCP tool payload shape, returned row count and latency here.

### P0 — Gates B–D
- Seed the full `Glass House` Scene 28 fixture defined in `VERTICAL_SLICE_SPEC.md`.
- Implement continuity comparison behavior.
- Implement evidence-backed findings.
- Implement the fixed editorial retrieval query and verify exact expected take IDs.

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
- Failure-state UX.
- Evaluation matrix and latency measurements.
- Hosted deployment/runbook.
- Public license.
- README setup/test instructions.
- Deterministic 3-minute recording showing genuine Google Cloud + ClickHouse runtime use.

## Single best next step

**Using Gemini CLI / Gemini Code Assist or another hackathon-permitted Google/partner implementation tool, pass Gate A only: prove one real Gemini/ADK runtime call through the official authenticated, read-only ClickHouse MCP server to a real ClickHouse service and return one seeded production fact correctly.**

Before doing anything else, update this file with the exact MCP connection/auth method, tool request/response shape, latency, and any runtime limitation discovered. That evidence determines the rest of the implementation architecture.

## Sources

- https://agentic-cinema.devpost.com/
- https://agentic-cinema.devpost.com/rules
- https://agentic-cinema.devpost.com/details/dates
- https://github.com/ClickHouse/mcp-clickhouse
- https://clickhouse.com/blog/the-agentic-data-stack
- https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder/connect-mcp-servers
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/
