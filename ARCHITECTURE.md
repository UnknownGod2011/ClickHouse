# TakeKeeper Architecture

## 1. Architectural goal

TakeKeeper must prove one narrow, credible production loop end to end:

**new take → multimodal extraction → structured production memory → ClickHouse MCP retrieval → continuity reasoning → evidence-backed finding → human resolution → editorial retrieval**.

The architecture should make ClickHouse essential, keep agent permissions safe, and be simple enough to implement and demo reliably before the hackathon deadline.

## 2. System context

### Actors

- Script supervisor / continuity lead
- Director / DP
- Editor / assistant editor
- Production administrator

### External services

- Google Cloud Storage: raw media and optional thumbnails/keyframes
- Gemini on Google Cloud: multimodal extraction + agent reasoning
- Gemini Enterprise Agent Platform / ADK runtime: hosted agent orchestration
- ClickHouse Cloud or self-hosted ClickHouse: production memory
- Official `ClickHouse/mcp-clickhouse`: runtime read-side bridge between agent and ClickHouse

## 3. Component boundaries

### A. Production Console
Responsibilities:
- create/select production;
- register/upload takes and slate metadata;
- show processing state;
- trigger continuity checks;
- show evidence cards and compare takes;
- resolve findings;
- ask editorial/production-history questions;
- expose a concise “agent trace” that shows MCP/tool usage for judges.

Do not embed database or Google credentials in the browser.

### B. Take Ingestion Service
Responsibilities:
- accept take metadata and object-storage reference;
- create immutable `take_id`;
- invoke extraction workflow;
- validate structured extraction output;
- persist normalized facts to ClickHouse via a dedicated write credential;
- update processing state.

This service is the write path. It is intentionally separate from the agent's ClickHouse MCP read path.

### C. Multimodal Extraction Worker
Input:
- media URI;
- production/scene/take metadata;
- extraction schema;
- optional continuity categories to prioritize.

Output:
- transcript/dialogue segments;
- entity observations;
- production-quality signals (e.g. boom visible, focus issue if in scope);
- evidence timestamps/frame windows;
- confidence + model version.

The extraction worker should emit atomic observations rather than prose summaries.

### D. ClickHouse Production Memory
Stores append-heavy structured history and supports cross-take analytical queries.

Recommended MVP logical tables:

#### `productions`
- `production_id`
- `name`
- `created_at`
- `settings_json`

#### `scenes`
- `production_id`
- `scene_id`
- `scene_label`
- `continuity_group`
- `shoot_date`

#### `takes`
- `production_id`
- `scene_id`
- `take_id`
- `take_number`
- `camera_id`
- `media_uri`
- `duration_ms`
- `director_rating`
- `processing_status`
- `recorded_at`
- `created_at`

#### `entities`
- `production_id`
- `entity_id`
- `entity_type` (`character`, `prop`, `wardrobe`, `set_object`, etc.)
- `canonical_name`
- `aliases`

#### `observations`
Primary analytical fact table.

- `production_id`
- `scene_id`
- `take_id`
- `observation_id`
- `entity_id`
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

#### `continuity_baselines`
- `production_id`
- `scene_id`
- `entity_id`
- `property_key`
- `baseline_value`
- `source_take_id`
- `approved_by`
- `approved_at`

#### `continuity_findings`
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
- `created_at`

#### `human_decisions`
- `production_id`
- `decision_id`
- `finding_id`
- `actor_id`
- `decision`
- `note`
- `created_at`

#### `agent_runs`
- `production_id`
- `run_id`
- `intent`
- `request_summary`
- `tool_summary`
- `result_summary`
- `started_at`
- `completed_at`
- `status`

### Physical ClickHouse guidance for implementation

During implementation, use ClickHouse Agent Skills / official best-practice docs to choose engines, sorting keys, partitioning, projections/materialized views, and indexes. Do not prematurely optimize the empty repo spec.

Likely design direction for the largest event tables:
- append-oriented MergeTree-family tables;
- order data around `production_id`, `scene_id`, and time/take dimensions used by continuity queries;
- keep low-cardinality categorical fields typed appropriately;
- use materialized views only after real query patterns are measured.

The implementation session should validate these choices against official ClickHouse recommendations rather than blindly copying this draft.

### E. Official ClickHouse MCP Server
Required by the ClickHouse track.

Use `ClickHouse/mcp-clickhouse` as the agent's runtime analytical interface. As of the current official README, the server provides tools including `run_query`, `list_databases`, and `list_tables`; queries are read-only by default unless write access is explicitly enabled.

TakeKeeper should keep MCP read-only for MVP.

This gives a clean trust boundary:
- ingestion service: scoped write credential;
- Gemini agent through MCP: scoped analytical read credential;
- browser: neither credential.

### F. Gemini Agent
Primary intents:

1. `continuity_check`
2. `compare_takes`
3. `find_takes`
4. `production_history_question`
5. `explain_finding`

The agent should not guess table contents. For production-state questions it must query ClickHouse through MCP.

## 4. Continuity-check workflow

1. User selects current take and requests continuity check.
2. Agent resolves production/scene/take identity.
3. Agent calls MCP to inspect/query the relevant baseline and current observations.
4. If no approved baseline exists, agent queries nearest suitable historical/selected take and asks user whether it should be used as reference.
5. Agent compares only properties present in the configured continuity policy.
6. For each difference, calculate a finding class based on:
   - property importance;
   - extraction confidence;
   - human verification state;
   - semantic magnitude/type of deviation.
7. Return findings with exact evidence timestamps.
8. High-confidence deterministic mismatches can be flagged directly.
9. Low-confidence or subjective differences are marked `needs_confirmation`.
10. User confirms/rejects; decision is written via the application write path, not MCP.

## 5. Retrieval workflow

Example request:

“Find clean takes from Scene 28 where Maya says ‘I’m leaving’, looks toward the door after the line, boom not visible, rating ≥4.”

Agent plan:
1. identify constraints;
2. inspect relevant schema if needed;
3. query take metadata + transcript/observation facts through MCP;
4. apply hard filters before soft ranking;
5. return take IDs with matched evidence;
6. distinguish exact filters from uncertain semantic matches.

A judge should be able to see the MCP call(s) that produced the answer.

## 6. Evidence model

Every claim presented as a visual continuity issue should answer:

- **What changed?**
- **Compared with what baseline?**
- **Where can the human verify it?**
- **How confident is the model?**
- **Has a human confirmed it?**

This is a stronger product story than a generic AI “continuity score.”

## 7. State boundaries

### ClickHouse is durable production memory
Store facts/events needed for analytical history and auditability.

### Agent session state is conversational/orchestration state
Examples:
- current user request;
- current production context;
- current candidate take IDs;
- pending human approval.

Do not rely on ephemeral agent session state as the source of truth for continuity.

### Object storage is media source of truth
Raw video/audio stays outside ClickHouse.

## 8. Security and permissions

### Minimum viable security
- separate service identities for frontend/backend, extraction, and MCP;
- least-privilege ClickHouse users;
- MCP read-only in production/demo;
- secrets only in server-side secret/config storage;
- signed/short-lived media access;
- production-level authorization checks on every backend operation;
- audit human overrides;
- never make destructive database tools available to the reasoning agent.

### MCP deployment
The official MCP server supports HTTP/SSE authentication, including bearer-token and OAuth/OIDC configurations. For a hackathon-hosted demo, prefer the simplest secure server-side mode compatible with the Google agent runtime; do not disable authentication on a network-exposed endpoint.

## 9. Google Cloud deployment topology

Target topology to validate with current Google docs during implementation:

- Production Console frontend: suitable Google-hosted web service/static hosting.
- API/Ingestion service: Cloud Run or equivalent managed service.
- Media: Cloud Storage.
- Extraction: Gemini on Vertex AI / approved Gemini service.
- Agent: ADK deployed to Gemini Enterprise Agent Platform Agent Runtime.
- Secrets: Secret Manager.
- ClickHouse MCP: securely reachable service endpoint using the official server.
- ClickHouse: ClickHouse Cloud or self-hosted cluster permitted by rules.

Google's current Agent Runtime quickstart supports ADK agents deployed as managed reasoning/agent-engine resources with managed sessions. Implementation must re-check the exact current deployment APIs before coding.

## 10. Demo dataset design

Use fictional names/assets with explicit permission or self-created footage.

Recommended minimum:
- 1 production;
- 2 scenes;
- 6–12 short takes;
- 2 characters;
- 2 props;
- 1 wardrobe state;
- 1 set/practical state;
- dialogue line with multiple delivery/timing variants;
- one deliberately visible boom/error signal if feasible;
- 5–10 seeded continuity mismatches with ground truth.

### Hero continuity scenario
Baseline:
- Maya: red mug in right hand;
- jacket zipped;
- lamp on.

New take:
- mug in left hand (high confidence);
- jacket open (high confidence);
- lamp perception ambiguous (low confidence).

This produces a demo containing both automation **and** responsible uncertainty handling.

## 11. Evaluation plan

Create a small labeled evaluation matrix before broad feature work.

### Extraction
- entity/property accuracy;
- timestamp error;
- confidence calibration.

### Continuity
- true positive / false positive counts on seeded mismatches;
- high-severity precision;
- human-confirmation rate.

### Retrieval
- correct take IDs for a fixed set of 10–20 editorial questions;
- evidence correctness;
- tool-query latency.

### Reliability
- malformed extraction output handling;
- missing baseline handling;
- MCP unavailable handling;
- ClickHouse query timeout handling;
- duplicate upload/idempotency behavior.

## 12. Failure behavior

| Failure | Expected product behavior |
|---|---|
| Gemini cannot confidently identify prop state | mark uncertain, do not assert mismatch |
| No continuity baseline | request/derive candidate baseline instead of inventing one |
| MCP unavailable | show actionable dependency error, no fabricated production answer |
| ClickHouse query returns no rows | explain no matching evidence found |
| Media inaccessible | preserve take record and processing failure state |
| Duplicate take upload | detect idempotency key/hash and avoid duplicate production facts |
| Human rejects finding | preserve override and exclude/reduce future reliance on that specific result as appropriate |

## 13. Judge-visible technical proof

The final product should make technological implementation undeniable without forcing judges to inspect logs:

- small “Agent activity” drawer;
- shows intent, MCP tool name, safe query summary, result row count, reasoning stage, and latency;
- no credentials or raw sensitive values;
- links a continuity result to its evidence timestamps.

The demo video should also briefly show the ClickHouse tables/query path and the hosted Gemini agent path.

## 14. Implementation sequence

1. Freeze demo dataset + exact hero workflow.
2. Provision/configure permitted Google Cloud + ClickHouse resources using hackathon-allowed tooling.
3. Create ClickHouse schema and seed ground-truth demo data.
4. Connect official MCP server and prove Gemini can execute a read query against ClickHouse.
5. Implement agent continuity/retrieval workflows over pre-seeded observations first.
6. Build production console around those working flows.
7. Add multimodal extraction/ingestion after the read-side agent loop is reliable.
8. Add human resolution + audit trail.
9. Run fixed evaluation set and fix false positives.
10. Record deterministic 3-minute demo and complete deployment/runbook.

This order de-risks the track requirement early: prove **Gemini → official MCP → ClickHouse → useful production answer** before investing in video-processing polish.

## 15. Current source-of-truth references

- Hackathon rules: https://agentic-cinema.devpost.com/rules
- ClickHouse MCP repository: https://github.com/ClickHouse/mcp-clickhouse
- ClickHouse Agentic Data Stack: https://clickhouse.com/blog/the-agentic-data-stack
- Google Agent Runtime + ADK quickstart: https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk
