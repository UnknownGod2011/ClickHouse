# TakeKeeper Progress

## Current status

Repository started from empty. The first specification pass is complete enough to hand to a hackathon-permitted Gemini implementation session.

## Inspected this run

- Repository state: completely empty at start.
- Official Agentic Cinema overview/rules and current schedule.
- Official ClickHouse track requirement: runtime use of ClickHouse through the official `mcp-clickhouse` server connected to ClickHouse Cloud or self-hosted ClickHouse.
- Official `ClickHouse/mcp-clickhouse` README and security defaults.
- ClickHouse “Agentic Data Stack” architecture/pattern.
- Current Gemini Enterprise Agent Platform / ADK Agent Runtime quickstart.

## Files created

### `README.md`
Established:
- product thesis and target users;
- primary workflows;
- why ClickHouse is indispensable;
- MVP logical entities;
- evidence/confidence contract;
- security model;
- 3-minute judge demo;
- real-world onboarding vision;
- MVP boundaries and success metrics;
- current authoritative source links.

### `ARCHITECTURE.md`
Established:
- system/component boundaries;
- separation of ingestion write path from MCP read path;
- proposed ClickHouse logical schema;
- continuity and editorial-retrieval workflows;
- state ownership boundaries;
- minimum viable security;
- Google Cloud deployment topology;
- deterministic demo dataset;
- failure behavior;
- judge-visible technical proof;
- implementation order designed to de-risk the ClickHouse track requirement first.

## Key decisions

1. **Product direction remains TakeKeeper:** a production-memory + continuity agent, not a generic video chatbot or AI editor.
2. **ClickHouse is the durable production memory.** Raw video stays in object storage; ClickHouse stores structured facts/events/references.
3. **Official ClickHouse MCP is the Gemini agent's analytical read path.** This directly satisfies the track's core runtime requirement.
4. **Ingestion writes are separated from MCP.** The official MCP is read-only by default; TakeKeeper should preserve that safer default and use a dedicated backend credential/service for inserts.
5. **Evidence-first UX.** Every continuity warning should point to exact evidence timestamps and confidence, not just produce a score.
6. **Human-in-the-loop is mandatory for uncertainty.** Low-confidence/subjective perception must be confirmable/rejectable and audited.
7. **MVP hero workflow is deliberately narrow:** analyze/register a new take → query historical baseline through MCP → identify a few obvious continuity mismatches → human resolve → run one natural-language editorial retrieval query.
8. **Implementation order de-risks sponsor integration before multimodal polish.** First prove Gemini → official MCP → ClickHouse → useful answer over seeded observations; only then add automated video extraction.
9. **No OpenAI-generated submitted implementation artifacts.** This repo currently contains only research/specification material for later implementation with hackathon-permitted Google/partner tooling.

## Important current facts

- The hackathon submission deadline is **September 9, 2026 at 2:00 PM PDT** according to the current Devpost schedule.
- ClickHouse track rules require active runtime use of the official MCP server; README-only references do not satisfy the goal.
- Current official `mcp-clickhouse` supports query/schema tools and defaults to read-only queries; network transports require authentication by default.
- Current Google Agent Runtime documentation supports deploying ADK-built agents to managed Agent Runtime / Agent Platform resources.
- Devpost guidance says the demo video is a backstop if cloud credits later expire, so the final recording must capture the complete working end-to-end flow.

## Risks / unresolved blockers

1. **No implementation exists yet.** The repository is specification-only by design.
2. **No demo footage/dataset exists.** A small fictional/self-created continuity dataset must be produced quickly.
3. **Exact physical ClickHouse schema is not frozen.** Logical tables are defined, but engine/ORDER BY/partition decisions should be validated using current ClickHouse Agent Skills and measured query patterns during implementation.
4. **Gemini multimodal extraction schema needs empirical validation.** It is unknown which visual continuity properties can be extracted reliably enough for the demo; choose visually obvious ones first.
5. **Exact MCP-to-Gemini Agent Platform connection mechanism needs an implementation spike.** The core requirement is clear, but current SDK/runtime wiring should be verified with official docs in the permitted coding environment.
6. **License file is still missing.** Hackathon submission requires a public open-source repository/license; choose and add the desired license before submission.
7. **Hosted UI/deployment details are still open.** Keep them minimal until MCP + ClickHouse + Gemini read loop is proven.

## Highest-priority implementation backlog

### P0 — prove track compliance
- Create ClickHouse Cloud/self-hosted service.
- Create minimal `takes`, `observations`, `continuity_baselines` demo schema.
- Seed one scene with 3–4 takes and known ground truth.
- Run official `ClickHouse/mcp-clickhouse` securely.
- Connect Gemini/ADK agent to MCP.
- Demonstrate one agent request that queries ClickHouse and returns the correct continuity difference.

### P0 — freeze deterministic demo
- Record/create 6–12 very short fictional takes.
- Seed obvious differences: mug hand, jacket state, lamp state, dialogue/eyeline variant.
- Define expected outputs for each take.

### P1 — product shell
- Production console with take list, processing state, continuity compare view, finding/evidence cards, ask-production input, and minimal agent-activity drawer.

### P1 — ingestion/extraction
- Upload/register media to private object storage.
- Gemini multimodal extraction to strict structured observations.
- Validate output and write observations via backend ingestion credential.

### P1 — human resolution
- Confirm/reject uncertain findings.
- Persist decision/audit trail.

### P2 — evaluation + polish
- Fixed retrieval query suite.
- Continuity precision/false-positive check.
- Failure states for MCP/database/media issues.
- Final 3-minute demo recording.
- Deployment/run instructions and license.

## Single best next step

**Use Gemini CLI / Gemini Code Assist to implement the smallest possible vertical slice that proves `Gemini agent → official ClickHouse MCP → ClickHouse query → evidence-backed continuity answer` against a tiny manually seeded dataset. Do not start with video upload or UI polish.**

Once that vertical slice works, update this file with the exact MCP connection method, working schema, query/tool traces, latency, and any changes needed to the architecture.

## Sources

- https://agentic-cinema.devpost.com/
- https://agentic-cinema.devpost.com/rules
- https://agentic-cinema.devpost.com/details/dates
- https://agentic-cinema.devpost.com/forum_topics/44701-how-will-judges-test-projects-after-cloud-credits-expire
- https://github.com/ClickHouse/mcp-clickhouse
- https://clickhouse.com/blog/the-agentic-data-stack
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk
