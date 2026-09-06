# TakeKeeper — Judge-Ready Vertical Slice Specification

This document is the implementation handoff for the smallest end-to-end TakeKeeper flow that can credibly satisfy the ClickHouse track and demonstrate the product thesis. It is intentionally implementation-language agnostic so the submitted code can be created with hackathon-permitted Google/partner tooling.

## 1. Goal

Prove this loop before any broad UI or video-processing work:

**user asks for continuity check → Gemini agent queries production memory through the official ClickHouse MCP server → agent compares the current take with the approved baseline → returns evidence-backed differences → human resolves an uncertain finding → user asks an editorial retrieval question → agent queries ClickHouse again and returns the correct takes with evidence.**

A successful slice makes both Gemini and ClickHouse visibly indispensable.

## 2. Non-goals for the first slice

Do not block the slice on:
- automatic video upload;
- automatic Gemini vision extraction;
- arbitrary productions or schemas;
- NLE integrations;
- generative editing;
- sophisticated ranking models;
- multi-camera synchronization;
- write access through MCP.

Start with deterministic seeded observations. Add multimodal extraction only after the agent/MCP/database path is proven.

## 3. Deterministic demo production

Use one fictional production called **Glass House**.

### Scene 28 continuity baseline

Character: Maya

Approved baseline take: `S28-T31`

Required baseline facts:
- hero mug: red;
- mug hand: right;
- jacket state: zipped;
- practical lamp: on;
- eyeline after the line “I’m leaving”: toward door;
- boom visible: false;
- director rating: 5.

### Current take

Current take: `S28-T47`

Seed facts:
- hero mug: red;
- mug hand: left;
- jacket state: open;
- practical lamp: off, but low model confidence;
- eyeline after “I’m leaving”: toward door;
- boom visible: false;
- director rating: 4.

Expected continuity result:
1. **High:** mug hand changed `right → left`.
2. **High/Medium:** jacket changed `zipped → open`.
3. **Needs confirmation:** lamp changed `on → off`, because current observation confidence is deliberately below the automatic-assertion threshold.

### Retrieval candidates

Seed at least four takes in Scene 28 so the editorial question has meaningful filtering:

- `S28-T31`: says target line, correct eyeline, no boom, rating 5.
- `S28-T40`: says target line, wrong eyeline, no boom, rating 5.
- `S28-T44`: says target line, correct eyeline, boom visible, rating 5.
- `S28-T47`: says target line, correct eyeline, no boom, rating 4.

Editorial query:

> Find Scene 28 takes where Maya says “I’m leaving”, looks toward the door afterward, the boom is not visible, and director rating is at least 4.

Expected result: `S28-T31` and `S28-T47`, with evidence and reasons. `S28-T40` and `S28-T44` must be excluded for explicit reasons.

## 4. Minimum data contract

The vertical slice only requires these durable concepts.

### Take record

Required fields:
- production ID;
- scene ID;
- take ID and take number;
- media reference or demo clip identifier;
- director rating;
- processing state;
- recorded timestamp.

### Observation record

Required fields:
- production ID;
- scene ID;
- take ID;
- observation ID;
- entity ID/name;
- property key;
- normalized value;
- evidence start/end timestamp;
- confidence;
- source type (`seeded`, later `vision`, `transcript`, `metadata`, `human`);
- verification state;
- model/extractor version;
- created timestamp.

### Baseline record

Required fields:
- production ID;
- scene ID;
- entity/property pair;
- approved value;
- source take ID;
- approval actor/time.

### Human decision record

Required fields:
- finding or observation reference;
- decision (`confirm`, `reject`, `override`);
- actor;
- optional note;
- timestamp.

The first slice does not need a large number of normalized entity tables if that slows implementation. Preserve stable IDs and a migration path, but optimize for proving the workflow.

## 5. ClickHouse physical-design guidance

Validate final engines and ordering with current ClickHouse best-practice tooling during implementation.

For the demo-scale append-heavy history, the likely direction is:
- MergeTree-family tables for large fact/event tables;
- sorting centered on production + scene + take/time access patterns;
- compact categorical types for repeated values where appropriate;
- no speculative materialized views until query traces demonstrate a need;
- raw video remains outside ClickHouse.

The important judge story is not “we stored rows in ClickHouse.” It is that the **agent repeatedly performs analytical retrieval over production history through ClickHouse MCP**.

## 6. MCP contract

Use the official `ClickHouse/mcp-clickhouse` repository.

Current official behavior to preserve:
- `run_query` executes ClickHouse queries;
- `list_databases` and `list_tables` provide schema discovery;
- query access is read-only by default unless write access is explicitly enabled;
- HTTP/SSE network transports require authentication by default;
- the server exposes a health endpoint for network deployment.

### TakeKeeper policy

- Keep MCP read-only.
- Use a separate backend/service credential for ingestion and human-decision writes.
- Never expose database or MCP credentials to the browser.
- The agent may discover schema when necessary, but normal demo runs should use known, stable table contracts to reduce latency and nondeterminism.

## 7. Gemini agent intents

The first slice needs only four externally visible intents.

### `continuity_check`
Input: production, scene, current take.

Required behavior:
1. establish exact take identity;
2. query current observations through ClickHouse MCP;
3. query approved baseline observations through ClickHouse MCP;
4. compare only configured continuity properties;
5. produce findings with baseline, observed value, confidence, severity, and evidence timestamps;
6. never invent missing production state;
7. mark uncertain perception as `needs_confirmation`.

### `compare_takes`
Input: two take IDs.

Return structured differences and matches with evidence.

### `find_takes`
Input: natural-language editorial constraints.

Required behavior:
1. decompose hard constraints;
2. query ClickHouse through MCP;
3. return only matching take IDs;
4. attach evidence/reason for every included result;
5. state exclusion reason when useful for the demo.

### `explain_finding`
Input: finding reference.

Return what changed, what baseline was used, evidence location, confidence, and whether a human has verified it.

## 8. Agent query discipline

For production-state questions, the agent must not answer from conversation memory alone.

Required rule:

> If the answer depends on a take, observation, baseline, decision, or production-history fact, retrieve the current state through ClickHouse MCP before presenting it as fact.

This is both a reliability constraint and the most important sponsor-integration proof.

## 9. Continuity decision policy

Avoid one opaque “continuity score.”

Each finding should expose:
- property importance;
- baseline value;
- observed value;
- extraction confidence;
- verification state;
- evidence timestamp;
- final status.

Suggested product-level policy to calibrate during implementation:
- obvious/high-confidence deterministic mismatch → surface directly;
- medium confidence → surface with caution;
- low-confidence or subjective state → `needs_confirmation`;
- missing value → `insufficient_evidence`, not a mismatch.

Do not turn a missing observation into an asserted continuity error.

## 10. Human-in-the-loop contract

For the lamp finding in the hero demo:
1. agent marks it `needs_confirmation`;
2. user opens evidence;
3. user rejects or confirms the finding;
4. application write path persists the decision;
5. subsequent explanation reflects the human decision.

MCP remains read-only; this write must use the application backend.

## 11. Judge-visible agent activity

The product should expose a small safe activity view containing:
- user intent;
- MCP tool name;
- safe query purpose/summary;
- returned row count;
- elapsed time;
- reasoning stage (`load current take`, `load baseline`, `retrieve candidates`, etc.);
- final status.

Do not expose:
- passwords/tokens;
- full secret-bearing URLs;
- raw chain-of-thought;
- sensitive production data beyond what the product already displays.

The judge should be able to see that the result came from the official ClickHouse MCP path without opening developer tools.

## 12. Acceptance gates

### Gate A — sponsor integration
PASS only if a Gemini/ADK agent makes a real runtime call through official ClickHouse MCP to a real ClickHouse service and uses returned data in the answer.

### Gate B — continuity correctness
For `S28-T47`, expected findings must contain the mug-hand and jacket mismatches; the lamp must not be asserted as high-confidence truth.

### Gate C — evidence
Every surfaced mismatch has a baseline reference and evidence timestamp/frame window.

### Gate D — editorial retrieval
The fixed retrieval question returns `S28-T31` and `S28-T47` and excludes the deliberately invalid takes.

### Gate E — failure honesty
If MCP/ClickHouse is unavailable or returns no supporting data, the agent must fail visibly and must not fabricate production facts.

### Gate F — security
MCP stays read-only; browser receives no database/MCP credentials.

Only after A–F pass should implementation time go into automatic video extraction and visual polish.

## 13. Multimodal extraction expansion

After the seeded vertical slice passes:
1. replace one seeded take with a short self-created clip;
2. have Gemini produce the same strict observation contract;
3. compare extracted facts against manually labeled ground truth;
4. add only properties that behave reliably in the demo;
5. retain manual/seeded fallback for deterministic judge recording if needed, but the final submission should visibly demonstrate genuine Gemini runtime use for the workflow claimed.

Prioritize visually obvious properties:
- left/right hand for a distinctive prop;
- jacket open/zipped;
- practical lamp on/off;
- boom visible/not visible;
- simple eyeline direction.

Avoid ambiguous fine-grained continuity properties until the basic demo is stable.

## 14. Deployment handoff

Target implementation topology:
- production console/frontend on a Google-hosted surface;
- API/ingestion service on Cloud Run or equivalent;
- media in private Cloud Storage;
- Gemini multimodal/agent reasoning on permitted Google Cloud Gemini services;
- ADK agent deployed to Gemini Enterprise Agent Platform Agent Runtime where feasible;
- official ClickHouse MCP server on an authenticated network-reachable endpoint;
- ClickHouse Cloud or permitted self-hosted ClickHouse;
- secrets in Secret Manager/server-side environment only.

Current Google documentation supports connecting MCP-compatible endpoints to Gemini Enterprise workflows and adding MCP tools to Gemini agent steps. Re-check the exact SDK/runtime API during the permitted implementation session because these APIs are actively evolving.

## 15. Three-minute demo choreography

### 0:00–0:20 — why continuity fails
Show baseline and current take side-by-side briefly.

### 0:20–0:40 — continuity check
User clicks/runs **Check continuity** for `S28-T47`.

### 0:40–1:10 — sponsor proof
Agent activity shows real ClickHouse MCP calls retrieving current observations and approved baseline.

### 1:10–1:35 — findings
Mug and jacket differences appear with evidence; lamp is marked uncertain.

### 1:35–1:55 — responsible human loop
Open lamp evidence and reject/confirm it; show audit update.

### 1:55–2:30 — editorial query
Ask the fixed “I’m leaving” retrieval question. Agent calls ClickHouse MCP and returns the two correct takes with reasons.

### 2:30–2:50 — architecture proof
Briefly show hosted Gemini agent path + ClickHouse production-memory/MCP path.

### 2:50–3:00 — close
**Gemini understands each take. ClickHouse remembers the production. TakeKeeper catches what the crew should not have to memorize.**

## 16. Real-user path after the hackathon

The MVP should evolve toward:
1. create production;
2. choose continuity categories;
3. connect/upload a watch folder or Cloud Storage bucket;
4. import optional slate/camera/NLE metadata;
5. map characters/props once;
6. validate extraction on one scene;
7. enable continuous ingestion;
8. review continuity findings and use production-history search.

The long-term defensible asset is not generic video analysis. It is the growing, auditable **production memory** that links every take, observation, baseline, decision, and editorial query.

## 17. Sources to verify during implementation

- Agentic Cinema overview/rules: https://agentic-cinema.devpost.com/
- Official ClickHouse MCP: https://github.com/ClickHouse/mcp-clickhouse
- ClickHouse Agentic Data Stack: https://clickhouse.com/blog/the-agentic-data-stack
- Gemini Enterprise MCP workflow docs: https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder/connect-mcp-servers
- Gemini Enterprise Agent Platform: https://docs.cloud.google.com/gemini-enterprise-agent-platform/

## 18. Exact next implementation action

Using Gemini CLI / Gemini Code Assist or another hackathon-permitted Google/partner implementation tool, build only enough infrastructure to pass **Gate A** first: a real Gemini/ADK agent calling the official ClickHouse MCP server against a tiny real ClickHouse service and returning one known seeded production fact correctly.

Record the exact connection method, authentication mode, observed tool payload shape, row counts, and latency in `progress.md` before moving to Gate B.
