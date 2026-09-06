# TakeKeeper

**The production memory and continuity agent for film, television, and creator studios.**

TakeKeeper is a proposed production-ready Gemini Enterprise / Google Cloud agent that turns every recorded take into structured, queryable production memory in ClickHouse. It helps script supervisors, directors, editors, and small creator teams catch continuity mistakes while reshoots are still possible and later retrieve the exact take they need using natural language.

> **Core promise:** Every take remembered. Every continuity risk surfaced with evidence.

## Why this exists

Film and video productions accumulate thousands of small facts that must remain consistent across takes and shooting days: wardrobe state, prop positions, actor blocking, eyelines, dialogue variants, lighting state, camera/lens settings, scene geography, director selects, and notes. Much of this knowledge is fragmented across handwritten notes, slates, camera reports, NLE metadata, and human memory.

A missed continuity error can survive until edit or post-production, when correction may require expensive VFX or a reshoot. At the same time, editors waste time manually searching for takes that satisfy several conditions at once.

TakeKeeper treats each take as a set of timestamped, evidence-backed observations. Gemini extracts the observations; ClickHouse stores the history; the official ClickHouse MCP server lets the agent reason over that history at runtime.

## Target users

1. **Script supervisors** — detect visual/dialogue continuity mismatches across takes and setups.
2. **Directors / DPs** — understand what changed between takes and confirm coverage.
3. **Editors / assistant editors** — retrieve takes by semantic + production criteria instead of scrubbing manually.
4. **Indie and creator teams** — get a lightweight “virtual script supervisor” when one person is wearing several production roles.

## Primary workflows

### 1. Analyze a new take
A user uploads or registers a take with scene/slate metadata. Gemini analyzes the media and emits structured observations with confidence and evidence timestamps. The ingestion layer writes those observations to ClickHouse.

### 2. Continuity check
The agent compares the current take with the designated continuity baseline and relevant historical takes, using the official ClickHouse MCP server for runtime queries. It returns a small set of high-confidence differences grouped by severity, with exact evidence timestamps rather than generic warnings.

Example:

- **High:** hero prop moved from right hand to left hand.
- **Medium:** jacket changed from zipped to open.
- **Low / uncertain:** practical lamp state differs; confidence 0.68 — request human confirmation.

### 3. Find the best take
An editor can ask:

> Find takes from Scene 28 where Maya delivers “I’m leaving” cleanly, looks toward the door afterward, the boom is not visible, and director rating is at least 4.

Gemini decomposes the request into production constraints, queries ClickHouse through MCP, and returns ranked candidates with evidence and reasons.

### 4. Ask production-history questions
Examples:

- “When did the coffee cup first move to the left side of the table?”
- “Show every take where wardrobe differs from the approved Scene 14 baseline.”
- “Which continuity warnings remain unresolved?”
- “What changed between Take 12 and Take 17?”
- “Which shots are missing a clean dialogue take?”

## What makes TakeKeeper agentic

TakeKeeper is not a chatbot over metadata. A useful request can trigger a deterministic multi-step workflow:

**understand goal → inspect production state → discover/query ClickHouse through MCP → retrieve evidence → compare observations → reason about severity/confidence → ask for human confirmation when needed → record/return an auditable result.**

The agent must never silently convert uncertain model perception into production truth. Low-confidence or subjective observations are explicitly surfaced for human confirmation.

## Why ClickHouse is indispensable

TakeKeeper is designed around ClickHouse rather than treating it as generic storage.

- A production creates a high-volume event history: takes, observations, entities, continuity states, warnings, decisions, and later editorial queries.
- The agent repeatedly needs analytical questions across many scenes, takes, entities, and timestamps.
- ClickHouse provides fast analytical retrieval across this append-heavy history.
- The hackathon requires runtime use of the official `ClickHouse/mcp-clickhouse` server; TakeKeeper makes that MCP path visible in the core reasoning workflow.
- The agent can use MCP to discover schemas and run read-side analytical queries while ingestion remains a separately permissioned write path.

This follows ClickHouse’s own “agentic data stack” pattern: the LLM decides it needs data, calls the MCP tool, ClickHouse executes the analytical query, and the result returns to the agent for reasoning.

## Proposed architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the detailed design.

For the exact smallest judge-ready workflow, seeded demo contract, MCP behavior and pass/fail gates, see [VERTICAL_SLICE_SPEC.md](VERTICAL_SLICE_SPEC.md).

For the implementation-facing ClickHouse table semantics, query contracts, evidence rules, scale-test plan, and Gate A runtime-evidence template, see [DATA_AND_QUERY_CONTRACT.md](DATA_AND_QUERY_CONTRACT.md).

At a high level:

1. **Web app / production console** — ingest takes, review continuity, ask questions, approve/resolve warnings.
2. **Ingestion + media pipeline** — registers media and metadata; stores raw media in object storage rather than ClickHouse.
3. **Gemini multimodal extraction** — generates structured observations with timestamps, confidence, source type, and extraction version.
4. **ClickHouse production memory** — stores normalized production facts/events and supports analytical queries.
5. **Official ClickHouse MCP server** — runtime analytical bridge from Gemini agent to ClickHouse.
6. **Gemini Enterprise Agent Platform / ADK agent** — orchestrates continuity checks, production-history questions, and human-in-the-loop decisions.

## Data model: MVP logical entities

| Entity | Purpose |
|---|---|
| `productions` | tenant / production identity and settings |
| `scenes` | scene identifiers and continuity groupings |
| `takes` | slate metadata, media references, timestamps, ratings, processing state |
| `observations` | atomic extracted facts tied to take + time range + confidence |
| `entities` | canonical people/characters/props/wardrobe/items/locations |
| `continuity_baselines` | approved reference state for an entity/property in a scene/setup |
| `continuity_findings` | detected mismatches, severity, evidence, lifecycle status |
| `human_decisions` | confirmation/override trail for uncertain findings |
| `agent_runs` | auditable request/tool/decision summaries for demo and operations |

Raw video should remain in Google Cloud Storage (or equivalent object storage). ClickHouse stores references and structured observations, not the full media blob.

## Evidence and confidence contract

Every machine-extracted observation should carry:

- production / scene / take identity;
- entity + property + normalized value;
- evidence start/end timestamp or frame range;
- model confidence;
- extraction model/version;
- source type (vision, transcript, metadata, human);
- verification state (unverified, human-confirmed, human-rejected);
- created timestamp.

Continuity severity should combine **importance × confidence × deviation type**. Subjective or low-confidence differences must not be presented as facts.

## Security model

- Production isolation by `production_id` plus application-layer authorization.
- Raw media stored in private object storage with short-lived access.
- Separate credentials for ingestion writes vs agent analytical reads.
- Keep the ClickHouse MCP integration read-only for the core agent path unless a later workflow proves writes are essential.
- Never expose ClickHouse credentials, MCP bearer tokens, signed media URLs, or Google credentials to the browser.
- Human approval is required for any action that changes an approved continuity baseline or production record.

## Judge demo: 3-minute story

The demo should be a controlled, preloaded fictional production so success is deterministic.

**0:00–0:20 — Problem**
Show Scene 28 baseline take: Maya holds a red mug in her right hand, jacket zipped, lamp on.

**0:20–0:50 — New take arrives**
Register Take 47. Gemini analyzes it and creates evidence-backed observations.

**0:50–1:30 — Agent investigates through ClickHouse MCP**
Continuity Check visibly triggers MCP queries for the approved baseline and historical observations. Surface the tool path in the UI or trace panel so ClickHouse use is undeniable.

**1:30–1:55 — Finding**
Show three differences, each with clickable timestamps. One uncertain difference is explicitly marked “Needs confirmation.”

**1:55–2:25 — Human loop**
Script supervisor confirms the mug-hand mismatch and rejects the uncertain lamp warning. The product shows an audit trail rather than pretending the model is infallible.

**2:25–2:50 — Editorial payoff**
Ask: “Find clean takes where Maya says ‘I’m leaving’, looks toward the door, boom not visible, rating ≥4.” Agent queries ClickHouse and returns ranked candidates.

**2:50–3:00 — Close**
“Gemini understands each take. ClickHouse remembers the production. TakeKeeper catches what humans should not have to memorize.”

## Real-world onboarding vision

MVP onboarding should not require a studio to redesign its workflow:

1. Create production.
2. Choose naming/slate convention and continuity categories to track.
3. Connect or upload media from a watch folder / cloud bucket.
4. Optionally import CSV/JSON camera reports or NLE metadata.
5. Connect a ClickHouse Cloud service (or use a managed TakeKeeper workspace in a future hosted product).
6. Test one scene and review extraction accuracy before scaling ingestion.

A future production deployment can support camera-report integrations, NLE exports, DAM/MAM systems, and webhook/event ingestion.

## MVP boundaries

Build the smallest product that proves the core loop:

- one fictional production;
- a few scenes and 6–12 short demo takes;
- 4–6 continuity properties with obvious visual differences;
- evidence timestamps;
- approved baseline + human confirmation;
- one editorial natural-language retrieval workflow;
- visible ClickHouse MCP runtime usage;
- hosted Google Cloud agent path.

Do **not** spend the hackathon building a full NLE, automatic editing suite, generative storyboarder, or arbitrary computer-vision platform.

## Success metrics

For the demo/evaluation set:

- continuity precision on deliberately seeded high-importance mismatches;
- evidence timestamp accuracy;
- false-positive rate requiring human review;
- percentage of natural-language retrieval questions answered with correct take IDs;
- ClickHouse query latency for demo-scale and synthetic larger-scale datasets;
- end-to-end time from take registration to continuity result.

## Hackathon alignment

TakeKeeper is designed for the **ClickHouse track** of Google Cloud’s Agentic Cinema hackathon. The official rules require active runtime use of ClickHouse through the official MCP server connected to ClickHouse Cloud or a self-hosted cluster. The project should also use Gemini and Google Cloud Agent Builder / Gemini Enterprise Agent Platform and demonstrate a real media-and-entertainment workflow.

The public repository and final demo must make both runtime dependencies observable and testable. Do not merely mention ClickHouse in documentation.

## Build policy for this repository

Planning/specification work may be prepared here, but submitted implementation must be created using hackathon-permitted Google/partner tooling. Before implementation begins, re-check the latest official rules and resource pages.

## Source references

- Hackathon overview: https://agentic-cinema.devpost.com/
- Official rules: https://agentic-cinema.devpost.com/rules
- ClickHouse MCP: https://github.com/ClickHouse/mcp-clickhouse
- ClickHouse Agentic Data Stack: https://clickhouse.com/blog/the-agentic-data-stack
- ClickHouse current best-practice guidance: https://clickhouse.com/blog/10-best-practice-tips
- Gemini Enterprise MCP workflow docs: https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder/connect-mcp-servers
- Gemini Enterprise Agent Platform ADK runtime quickstart: https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk

## Status

Specification / architecture phase. See [VERTICAL_SLICE_SPEC.md](VERTICAL_SLICE_SPEC.md) for the concrete implementation contract, [DATA_AND_QUERY_CONTRACT.md](DATA_AND_QUERY_CONTRACT.md) for the ClickHouse data/query handoff, and [progress.md](progress.md) for the current handoff/next action.
