# TakeKeeper Progress

## Current status

TakeKeeper now has four complementary implementation handoffs:

1. `ARCHITECTURE.md` — system boundaries and production topology.
2. `VERTICAL_SLICE_SPEC.md` — deterministic judge-ready workflow and Gates A–F.
3. `DATA_AND_QUERY_CONTRACT.md` — ClickHouse table/query/evidence semantics and runtime evidence template.
4. `MULTIMODAL_EXTRACTION_AND_EVAL.md` — conservative Gemini video-extraction, evidence, ground-truth, and evaluation contract.

The product concept and seeded ClickHouse/MCP vertical slice are sufficiently specified for implementation with hackathon-permitted Google/partner tooling. The next engineering milestone remains deliberately narrow: **prove Gate A with a real Gemini/ADK → official ClickHouse MCP → real ClickHouse read before investing in UI or automatic video extraction.**

## Inspected this run

- Read the existing `progress.md` completely before making changes.
- Re-read `README.md` and `VERTICAL_SLICE_SPEC.md` so the new work extends rather than duplicates the existing handoff.
- Verified current official Gemini video-understanding guidance and Vertex AI video input patterns.
- Re-checked current MCP ecosystem references while keeping the official `ClickHouse/mcp-clickhouse` path as the required sponsor integration.

## Changes made this run

### Created `MULTIMODAL_EXTRACTION_AND_EVAL.md`

Added a concrete post-Gate-A multimodal contract covering:

- one-take-at-a-time extraction units;
- strict schema-compatible observation output;
- property registries and allowed normalized values;
- evidence-window/timestamp validation;
- a conservative two-pass extraction/validation strategy;
- explicit human-verification states;
- self-owned labeled demo-footage design;
- per-property evaluation metrics instead of one misleading blended accuracy number;
- go/no-go rules for allowing a property into the live judge flow;
- reprocessing/model-version audit rules;
- failure behavior for missing visibility, invalid timestamps, schema errors and disagreeing extraction passes;
- implementation sequence that starts with sustained mug-hand + jacket state and evaluates lamp/boom/dialogue/eyeline later.

### Critical multimodal risk resolved in the product design

Current official Gemini video-understanding documentation states that File API video processing samples at roughly **1 frame per second** and warns that fast action can lose detail. That materially affects TakeKeeper's proposed continuity properties.

The design is now explicitly adjusted:

- persistent jacket/lamp states are strong early extraction targets;
- mug-hand state is suitable when held for several seconds;
- a brief boom intrusion cannot safely be treated as absent merely because Gemini did not observe it;
- a quick eyeline shift should not be a hero multimodal claim until measured;
- demo footage must deliberately hold hero visual states long enough to be observable;
- transient/ambiguous properties should stay seeded, human-confirmed, or out of the 3-minute live extraction path until evaluation proves them.

This prevents the final demo from overclaiming frame-level continuity accuracy from a temporally sampled video representation.

## Key decisions now locked

1. **Gate A remains first.** Do not start Gemini vision work until the real Gemini/ADK → official ClickHouse MCP → ClickHouse path works.
2. **ClickHouse is durable production memory; raw media remains in object storage.**
3. **MCP remains read-only for the agent path.** Ingestion/human decisions use a separately permissioned backend write path.
4. **Agent session memory is not production truth.** Production-history answers require a fresh ClickHouse MCP read.
5. **Hero continuity predicates remain explicit typed fields/normalized properties, not arbitrary JSON blobs.**
6. **Hard editorial constraints are enforced by structured data/query semantics rather than LLM intuition.**
7. **Every production query is scoped by `production_id` plus application authorization.**
8. **No speculative ClickHouse optimization.** Measure first; projections/materialized views come only after demonstrated need.
9. **Multimodal output is candidate evidence, not automatic truth.** Schema validity, visibility, evidence windows, confidence and human verification remain separate concepts.
10. **No frame-perfect claim.** Standard Gemini video sampling means the MVP must favor sustained visible states and measure transient-property behavior explicitly.
11. **Boom absence requires caution.** Failure to observe a short-lived boom is not proof of absence unless the tested pipeline demonstrates adequate coverage.
12. **Model upgrades never silently rewrite production history.** Reprocessing creates new extraction versions; human-confirmed baselines/decisions persist.
13. **Self-owned labeled clips are the benchmark.** Do not tune ground-truth labels after seeing model output.
14. **Report per-property evaluation.** Mug hand, jacket, lamp, boom and eyeline have different failure modes and should not be hidden behind one synthetic accuracy score.

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

### Gate G — Multimodal evidence quality (post A–F)
For the fixed self-owned labeled clips, every judge-facing high-severity machine-extracted mismatch has valid visible evidence; ambiguous properties abstain/request confirmation rather than becoming unsupported facts.

Do not spend significant time on automatic video extraction or visual polish until A–F pass. Gate G governs which visual properties may enter the live multimodal demo after that.

## Risks / unresolved blockers

1. **No submitted implementation exists yet** by design; code must be produced with hackathon-permitted Google/partner tooling.
2. **Gate A is still unproven:** exact deployed Gemini/ADK ↔ official ClickHouse MCP connection/auth method must be tested in the implementation environment.
3. **No real ClickHouse service/demo database is provisioned yet.**
4. **No physical ClickHouse schema has been measured.** Sorting/engine decisions must be finalized against real version/query traces.
5. **No self-owned demo footage exists yet.** The new multimodal contract specifies how to shoot/label it once seeded Gates A–F are stable.
6. **Gemini extraction accuracy is unmeasured for TakeKeeper properties.** Default video sampling makes transient boom/eyeline behavior a specific known risk.
7. **License file is still missing.** Add the required open-source license before final submission.
8. **Hosted UI, API service and MCP endpoint do not exist yet.** Keep these minimal until Gate A works.
9. **MCP/runtime version details remain unknown until measured.** Do not encode assumptions as facts in the final README/demo.

## Highest-priority implementation backlog

### P0 — Gate A only
- Provision a minimal ClickHouse service/database.
- Create the smallest schema required for one known production fact using `DATA_AND_QUERY_CONTRACT.md`.
- Seed one known production fact.
- Run official `ClickHouse/mcp-clickhouse` with authentication and read-only access.
- Connect a Gemini/ADK agent using hackathon-permitted Google tooling.
- Ask for the known production fact and verify the response demonstrably came through MCP.
- Record ClickHouse version, MCP version/commit, transport, auth, tool invoked, row count and latency.

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
- Safe agent-activity drawer showing MCP usage without chain-of-thought/secrets.

### P1 — Gate G multimodal expansion
Follow `MULTIMODAL_EXTRACTION_AND_EVAL.md`:
- shoot/label `S28-T31` and `S28-T47` first;
- test sustained mug-hand + jacket state first;
- validate timestamps/schema/evidence against ground truth;
- add lamp next;
- create one sustained visible-boom negative control;
- test dialogue timing;
- evaluate eyeline last;
- promote only properties that meet the live-demo go/no-go criteria.

### P2 — production readiness / submission
- Synthetic scale dataset + measured ClickHouse/MCP latency.
- Failure-state UX and evaluation matrix.
- Hosted deployment/runbook.
- Public license.
- README setup/test instructions.
- Deterministic 3-minute recording showing genuine Google Cloud + ClickHouse runtime use.
- Publish only measured performance/accuracy claims.

## Single best next step

**Using Gemini CLI / Gemini Code Assist or another hackathon-permitted Google/partner implementation tool, pass Gate A only: provision the smallest real ClickHouse dataset, connect the official authenticated read-only ClickHouse MCP server, and make a real Gemini/ADK runtime retrieve one seeded production fact.**

Immediately record the actual ClickHouse version, official MCP version/commit, transport, authentication mode, tool invoked, returned row count, MCP latency, end-to-end latency, read-only verification and any runtime limitation. Those measured facts should determine subsequent deployment/schema decisions.

After Gates A–F pass, use `MULTIMODAL_EXTRACTION_AND_EVAL.md` rather than improvising video prompts or demo footage.

## Sources

- https://agentic-cinema.devpost.com/
- https://agentic-cinema.devpost.com/rules
- https://github.com/ClickHouse/mcp-clickhouse
- https://clickhouse.com/blog/the-agentic-data-stack
- https://clickhouse.com/blog/10-best-practice-tips
- https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder/connect-mcp-servers
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/samples/googlegenaisdk-textgen-with-video
