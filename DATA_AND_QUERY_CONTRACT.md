# TakeKeeper — ClickHouse Data & Query Contract

This document turns the logical architecture into an implementation handoff for the ClickHouse-backed production-memory layer. It is intentionally language- and framework-agnostic so the submitted implementation can be created with hackathon-permitted Google/partner tooling.

## 1. Design objective

The data layer must make these two judge-visible workflows fast, explainable, and deterministic:

1. **Continuity check:** compare a current take against an approved scene/entity/property baseline and return evidence-backed differences.
2. **Editorial retrieval:** answer multi-constraint natural-language questions over takes, dialogue/eyeline/quality observations, and ratings.

The design must also preserve a clean sponsor story:

> Gemini decides what production evidence it needs. The official ClickHouse MCP server retrieves that evidence from ClickHouse. The agent reasons only after that read.

## 2. Source-of-truth boundaries

### ClickHouse owns durable production memory
Store structured facts/events that must be queryable across scenes/takes:
- take metadata;
- atomic observations;
- approved baselines;
- continuity findings;
- human decisions;
- safe agent-run summaries.

### Object storage owns media
Raw video/audio/keyframes remain in private Cloud Storage or equivalent. ClickHouse stores only stable references plus evidence timestamps/frame windows.

### Agent session state is not production truth
Session memory may hold current intent or candidate IDs, but any answer about current/historical production state must be re-read through ClickHouse MCP.

## 3. Table contract

The MVP should favor explicit typed columns for fields used frequently in filters, joins, sorting, or comparisons. Flexible JSON is acceptable for sparse/non-critical metadata, but do not hide hero continuity facts inside opaque blobs.

### `takes`
Purpose: one row per recorded take.

Required fields:
- `production_id`
- `scene_id`
- `take_id`
- `take_number`
- `camera_id`
- `media_ref`
- `duration_ms`
- `director_rating`
- `processing_status`
- `recorded_at`
- `created_at`

Primary access patterns:
- all takes for one production + scene;
- exact take lookup;
- scene-level filtering by rating/status/time.

### `observations`
Purpose: append-oriented atomic perception/transcript/metadata facts.

Required fields:
- `production_id`
- `scene_id`
- `take_id`
- `observation_id`
- `entity_id`
- `entity_type`
- `property_key`
- `normalized_value`
- `raw_value`
- `evidence_start_ms`
- `evidence_end_ms`
- `confidence`
- `source_type`
- `verification_state`
- `model_version`
- `created_at`

Hero property keys for the demo:
- `prop.mug.color`
- `prop.mug.hand`
- `wardrobe.jacket.state`
- `set.practical_lamp.state`
- `performance.eyeline.after_target_line`
- `quality.boom_visible`
- `dialogue.target_line_present`

Primary access patterns:
- exact take observations;
- property history across scene/takes;
- entity/property comparison against baseline;
- filter candidates by specific observation values.

### `continuity_baselines`
Purpose: approved reference state for scene/entity/property combinations.

Required fields:
- `production_id`
- `scene_id`
- `entity_id`
- `property_key`
- `baseline_value`
- `source_take_id`
- `approved_by`
- `approved_at`
- `active`

Policy:
- only one active baseline per production + scene + entity + property in the MVP;
- baseline changes require explicit human action via the application write path;
- MCP remains read-only.

### `continuity_findings`
Purpose: auditable derived findings shown to production users.

Required fields:
- `production_id`
- `scene_id`
- `current_take_id`
- `finding_id`
- `entity_id`
- `property_key`
- `baseline_value`
- `observed_value`
- `severity`
- `confidence`
- `status`
- `evidence_start_ms`
- `evidence_end_ms`
- `baseline_source_take_id`
- `created_at`

### `human_decisions`
Purpose: append-only confirmation/rejection/override trail.

Required fields:
- `production_id`
- `decision_id`
- `finding_id`
- `actor_id`
- `decision`
- `note`
- `created_at`

Do not silently overwrite the original machine finding. Preserve the human decision as a separate event.

### `agent_runs`
Purpose: safe operational/audit summary for the product and judge-visible activity drawer.

Required fields:
- `production_id`
- `run_id`
- `intent`
- `request_summary`
- `tool_name`
- `query_purpose`
- `row_count`
- `elapsed_ms`
- `result_summary`
- `status`
- `started_at`
- `completed_at`

Never store credentials, secret-bearing URLs, or hidden chain-of-thought.

## 4. Physical design guidance

The final implementation should validate this against the exact ClickHouse service/version used, but the preferred MVP direction is:

- use MergeTree-family tables for append-heavy fact/event data;
- design sorting around the dominant access path: production → scene → take/entity/property → time;
- keep repeated categorical fields compact where appropriate;
- use explicit typed columns for high-value continuity predicates;
- reserve JSON/flexible metadata for secondary/sparse fields rather than the hero query path;
- avoid materialized views and projections until the actual demo/evaluation queries show a measured need.

Current ClickHouse guidance emphasizes that projections/materialized views trade additional write/storage cost for faster reads, so TakeKeeper should add them only after profiling real query patterns rather than prematurely optimizing the tiny demo dataset.

## 5. Query contract — continuity check

Input:
- production ID;
- scene ID;
- current take ID.

The agent must obtain at least these evidence classes through ClickHouse MCP:

1. **Current observations** for configured hero continuity properties.
2. **Active approved baselines** for the same entity/property pairs.
3. **Baseline source take identity** so the product can show what the comparison is against.
4. Optional human verification state/history when explaining an already-reviewed finding.

Expected comparison policy:
- current value present + high confidence + differs from approved baseline → mismatch candidate;
- current value present + low confidence + differs → `needs_confirmation`;
- value absent → `insufficient_evidence`;
- equal values → no finding;
- baseline absent → report missing baseline; do not invent one.

### Hero acceptance result
For `Glass House`, Scene 28, `S28-T47`:
- mug hand: `right → left` → mismatch;
- jacket: `zipped → open` → mismatch;
- lamp: `on → off` with low confidence → `needs_confirmation`.

## 6. Query contract — editorial retrieval

Natural-language request:

> Find Scene 28 takes where Maya says “I’m leaving”, looks toward the door afterward, the boom is not visible, and director rating is at least 4.

The agent should decompose this into hard constraints before querying:
- production/scene identity;
- target dialogue present;
- eyeline equals `toward_door`;
- boom visible equals false;
- rating >= 4.

The database result must carry enough evidence to explain inclusion/exclusion.

Expected included IDs:
- `S28-T31`
- `S28-T47`

Expected excluded IDs:
- `S28-T40` — wrong eyeline;
- `S28-T44` — boom visible.

Do not rely on post-hoc LLM intuition to filter known hard constraints when the structured data can enforce them.

## 7. MCP read discipline

For any production-state answer:

1. determine intent;
2. determine exact production/scene/take scope;
3. call official ClickHouse MCP (`run_query`, with schema discovery only when needed);
4. validate that returned rows match the requested scope;
5. reason over returned evidence;
6. present answer with take IDs/evidence/confidence;
7. fail visibly if the tool call fails or returns no supporting data.

The agent must never claim a production fact solely because it appeared earlier in conversation context.

## 8. Tenant isolation contract

Every production-memory query must be scoped by `production_id`.

Minimum design rules:
- application authorizes the user for the requested production before agent invocation;
- MCP/database credentials are server-side only;
- the MCP ClickHouse user is read-only;
- demo queries should have a fixed allowed production context;
- never permit arbitrary cross-production retrieval because the user mentioned another ID in natural language.

## 9. Evidence contract

Any finding or retrieval result shown to users must be able to answer:
- what take did this come from?
- what exact property/constraint matched or differed?
- where in the media can a human verify it?
- how confident was machine extraction?
- was it human-confirmed/rejected?

For video-derived observations, use stable evidence timestamps/frame windows rather than prose like “around the middle of the clip.”

## 10. Scale test contract

The judge demo can use a tiny deterministic dataset, but the repository should demonstrate that the architecture was designed for real production volumes.

Create two evaluation tiers during permitted implementation:

### Tier 1 — deterministic demo
- 1 production;
- Scene 28 fixture from `VERTICAL_SLICE_SPEC.md`;
- enough rows to prove all Gates A–F.

### Tier 2 — synthetic scale
Generate metadata/observations only (no copyrighted media needed):
- hundreds to thousands of takes;
- many scenes;
- multiple observation properties per take;
- controlled distribution of ratings/errors/continuity states.

Measure:
- continuity retrieval latency;
- editorial multi-filter latency;
- rows scanned / result rows where observable;
- MCP round-trip latency;
- end-to-end agent latency.

Do not make unverified “millions of takes in milliseconds” claims. Record actual measurements from the deployed environment.

## 11. Optimization trigger policy

Only add an optimization when one of these conditions is observed:
- repeated query is materially slower than the demo latency budget;
- query scans substantially more data than expected;
- one alternate sort/filter path dominates editorial retrieval;
- storage/write overhead is justified by a measured read benefit.

Candidate tools, only if justified:
- revised ordering/sort key;
- projection for a second dominant access path;
- materialized view for frequently precomputed aggregates;
- text/full-text capabilities for future transcript search if structured target-line fields are no longer sufficient.

The hero demo should stay structured and deterministic rather than depending on fuzzy full-text search.

## 12. Gate A runtime evidence template

When the permitted Gemini implementation session first passes sponsor integration, append the following evidence to `progress.md`:

- ClickHouse service/version:
- MCP server commit/version:
- MCP transport:
- Authentication mode:
- Agent/runtime used:
- Tool invoked:
- Query purpose:
- Rows returned:
- MCP/tool latency:
- End-to-end latency:
- Exact seeded fact returned:
- Browser exposed credentials? yes/no:
- Read-only verified? yes/no:
- Failure encountered / workaround:

This becomes the factual architecture record. Do not replace it with assumptions.

## 13. Build order unlocked by this contract

After Gate A passes:

1. create/seed the full Scene 28 fixture using this table contract;
2. pass continuity Gate B;
3. attach evidence Gate C;
4. pass fixed editorial query Gate D;
5. test outage/empty-data behavior Gate E;
6. inspect client/server boundaries for Gate F;
7. only then add the UI shell and multimodal extraction.

## 14. Current reference notes

Current ClickHouse product guidance (checked September 6, 2026) supports the design choice to keep frequently queried data typed/columnar and to introduce projections/materialized views based on measured access patterns rather than automatically. ClickHouse's recent releases also provide mature JSON, full-text, and vector-search capabilities that could support future versions, but none is required to prove the TakeKeeper MVP.

References:
- https://clickhouse.com/blog/10-best-practice-tips
- https://clickhouse.com/blog/what-a-difference-10-years-of-open-source-makes
- https://github.com/ClickHouse/mcp-clickhouse
- https://clickhouse.com/blog/the-agentic-data-stack
