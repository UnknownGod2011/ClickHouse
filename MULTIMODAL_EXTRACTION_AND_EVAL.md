# TakeKeeper — Multimodal Extraction & Evaluation Contract

This document defines how TakeKeeper should expand from the deterministic seeded ClickHouse/MCP vertical slice into genuine Gemini video understanding **without making continuity claims that the underlying media sampling cannot support**.

It is an implementation handoff, not submitted application code.

## 1. Why this contract exists

The core product claim is stronger than generic video summarization: TakeKeeper must turn footage into **structured, evidence-backed production facts** that are safe enough to compare across takes.

That requires separating three questions:

1. Can Gemini observe the property in this clip?
2. Can the observation be normalized into TakeKeeper's strict schema?
3. Is the observation reliable enough to become continuity evidence?

A fluent model answer is not sufficient. A property only becomes judge-facing continuity evidence after it passes the extraction and evaluation gates below.

## 2. Current platform constraints that affect the design

Current official Gemini video-understanding documentation states that uploaded video is processed with timestamped video frames and supports timestamp-specific reasoning. It also documents a default video sampling behavior of roughly **1 frame per second** for File API processing and warns that fast action can lose detail at that sampling rate.

Implication for TakeKeeper:

- persistent states such as jacket open/zipped or lamp on/off are good first targets;
- prop-hand state is acceptable when it persists for several seconds;
- a boom that flashes into frame briefly may be missed;
- a short eyeline shift immediately after dialogue may be missed or temporally blurred;
- the product must not claim frame-accurate continuity from a low-frequency sampled representation.

Therefore the hero demo should deliberately use **slow, sustained, visually obvious states**, while transient properties remain either human-confirmed or excluded until measured.

## 3. Extraction unit

Do not analyze an entire shooting day as one opaque prompt.

The MVP extraction unit is **one registered take** with:

- stable `production_id`, `scene_id`, and `take_id`;
- media URI/reference;
- known take duration;
- optional slate metadata;
- optional transcript/dialogue cue;
- configured property set for that scene;
- extractor/model version.

For the hero scene, keep clips short enough that the relevant state persists clearly and timestamps are easy for judges to inspect.

## 4. Strict observation output contract

Every extracted candidate observation must map to the existing durable observation schema.

Minimum fields:

- `production_id`
- `scene_id`
- `take_id`
- `entity_key`
- `property_key`
- `normalized_value`
- `evidence_start_ms`
- `evidence_end_ms`
- `confidence`
- `source_type = vision | transcript | metadata`
- `extractor_model`
- `extractor_version`
- `verification_state`
- `created_at`

Additional recommended extraction metadata:

- `raw_model_value` — pre-normalization phrase/value;
- `evidence_rationale_short` — one short safe explanation, not chain-of-thought;
- `visibility_state = clear | partial | occluded | absent | unknown`;
- `temporal_support = sustained | transient | single_sample | unknown`;
- `schema_valid` boolean;
- `normalization_warning` when the model answer cannot be mapped cleanly.

The ingestion service must reject malformed or out-of-enum values instead of silently coercing them into production truth.

## 5. Hero property registry

Only configured properties can participate in continuity checks. This prevents the model from inventing arbitrary fields between takes.

### `hero_mug.hand`
Allowed values: `left`, `right`, `both`, `not_held`, `unknown`.

Judge-demo eligibility:
- subject and mug clearly visible;
- state persists for multiple seconds around the evidence timestamp;
- no mirrored footage ambiguity;
- confidence above calibrated threshold.

### `maya.jacket_state`
Allowed values: `open`, `zipped`, `closed_unzipped`, `unknown`.

Judge-demo eligibility:
- torso visible;
- closure state visually obvious;
- no heavy occlusion.

### `practical_lamp.power_state`
Allowed values: `on`, `off`, `unknown`.

Judge-demo eligibility:
- practical itself visible;
- apparent state not inferred only from room brightness;
- ambiguous exposure/reflection remains `unknown` or `needs_confirmation`.

### `boom.visibility`
Allowed values: `visible`, `not_visible`, `unknown`.

Policy:
- treat `visible` as actionable only when direct positive evidence exists;
- do **not** equate failure to observe the boom with proof that it was absent unless evaluation demonstrates adequate coverage;
- for the hackathon demo, make any seeded/real boom appearance sustained enough to survive video sampling.

### `maya.eyeline_after_line`
Allowed values: `toward_door`, `toward_camera`, `toward_character`, `other`, `unknown`.

Policy:
- requires a known dialogue cue/time window;
- evaluate separately from static visual properties;
- do not include in the live multimodal hero path unless measured accuracy is acceptable;
- deterministic seeded data may continue to support the editorial-query proof while the extraction model is being validated.

### `dialogue.im_leaving`
Allowed values: `present`, `absent`, `uncertain`.

Preferred source:
- transcript/audio evidence, with timing linked to the take;
- do not infer dialogue presence from lip movement alone.

## 6. Evidence-window policy

A TakeKeeper observation is useful only if a human can inspect the source.

For every extracted property:

1. request or derive a timestamp/time window;
2. clamp the returned evidence window to the actual clip duration;
3. reject impossible timestamps;
4. store evidence window separately from the normalized value;
5. display the evidence clip/frame range in the product;
6. if timestamp support is weak, mark the observation as unverified rather than fabricating precision.

For a sustained visual state, prefer a short window (for example, several seconds) over pretending a single exact frame is authoritative.

## 7. Two-pass extraction strategy

Use a conservative two-pass workflow after Gate A–F are proven.

### Pass 1 — candidate extraction
Gemini receives the take plus the scene's configured property registry and returns only schema-compatible candidate observations with evidence timestamps and confidence.

### Pass 2 — evidence validation
For each high-value candidate:
- ask whether the cited window actually contains enough visible evidence for the claimed normalized value;
- allow `unknown` / `insufficient_evidence` as first-class outcomes;
- reject contradictions between the value and its evidence window.

The second pass exists to reduce polished-but-unsupported assertions. It should be measured for value before being used on every property in production.

## 8. Human verification states

Use explicit states:

- `machine_unverified`
- `machine_high_confidence`
- `needs_confirmation`
- `human_confirmed`
- `human_rejected`
- `human_overridden`

A machine confidence score is not equivalent to human confirmation.

Approved continuity baselines should normally come from human-confirmed state or trusted imported production metadata, not from an arbitrary first model output.

## 9. Ground-truth dataset for the hackathon

Create a tiny self-owned dataset rather than relying on random web footage.

Recommended set:

- 8–12 clips total;
- 6–15 seconds per clip;
- same room, performer, red mug, jacket, practical lamp;
- stable camera and lighting where possible;
- deliberately controlled continuity variations;
- at least two clips containing negative/uncertain cases.

For every clip create a manual truth sheet with:

- take ID;
- property value;
- exact human-labeled evidence window;
- whether the property is genuinely observable;
- whether the state is sustained or transient;
- notes on occlusion/ambiguity.

Do not tune the truth labels after seeing model output.

## 10. Evaluation matrix

Evaluate each property independently.

Minimum metrics:

### Classification correctness
For each configured property:
- exact normalized-value accuracy;
- unknown/abstention correctness;
- false-positive rate;
- false-negative rate where meaningful.

### Evidence correctness
- timestamp/window overlaps human-labeled evidence;
- cited window actually shows the property;
- impossible/out-of-range timestamp rate.

### Continuity correctness
Given two labeled takes:
- true mismatches detected;
- true matches not flagged;
- uncertain/missing evidence does not become a mismatch.

### Product reliability
- schema-validation failure rate;
- extraction latency per take;
- reprocessing determinism for the fixed demo clips;
- percentage of judge-demo observations requiring manual fallback.

Do not publish a single blended "AI accuracy" number; report per-property behavior because failure modes differ materially.

## 11. Go/no-go thresholds for the judge flow

A property can enter the **live multimodal judge path** only when the fixed evaluation set shows that it is reliable enough not to derail the demo.

Recommended initial rule:

- zero unsupported high-severity continuity assertions on the fixed demo set;
- every surfaced high-severity mismatch has valid evidence;
- ambiguous cases correctly abstain or request confirmation;
- repeat runs on hero clips do not change the primary normalized value unexpectedly.

If a property fails this standard:
- keep it seeded for the ClickHouse/MCP continuity proof, or
- move it to the human-confirmation portion of the demo, or
- remove it from the 3-minute story.

This is better than hiding model uncertainty.

## 12. Demo-footage design to match Gemini's sampling behavior

The hero footage should be deliberately engineered for observability:

### Baseline `S28-T31`
- Maya holds the red mug in the **right hand** for at least several seconds;
- jacket visibly **zipped**;
- practical lamp clearly **on**;
- target line spoken clearly;
- doorward eyeline held long enough to be inspectable;
- no boom.

### Current `S28-T47`
- mug held in the **left hand** for several seconds;
- jacket clearly **open**;
- practical lamp clearly **off**, but production UI can deliberately treat this property as requiring confirmation;
- target line spoken clearly;
- same sustained doorward eyeline;
- no boom.

### Negative controls
Create at least:
- one take with the wrong eyeline held clearly;
- one take with a boom intentionally visible for multiple seconds;
- one intentionally occluded/ambiguous property that should return `unknown`.

These choices make the evaluation honest while reducing failures caused purely by temporal sampling.

## 13. Production-scale ingestion policy

For a real studio deployment:

- register source media in private object storage;
- extract asynchronously rather than blocking upload UX;
- persist extraction version so observations can be reprocessed later;
- preserve old model outputs for audit rather than overwriting history silently;
- write new observation versions append-only where practical;
- human decisions remain durable even if a later extractor version disagrees;
- ClickHouse stores structured facts/evidence metadata, not the raw video blob.

## 14. Reprocessing/versioning contract

Model behavior will change. TakeKeeper must not silently mutate history when extraction models are upgraded.

Every extraction run should have a stable `agent_run` / `extraction_run` identity and record:

- model name;
- model/API version if exposed;
- prompt/schema version;
- media reference/version;
- created timestamp;
- success/failure state;
- resulting observation IDs.

A re-run creates a new version. Human-confirmed observations/baselines are never silently replaced.

## 15. Failure behavior

### Video cannot be processed
Return explicit processing failure; do not create empty observations that look like negative evidence.

### Property is not visible
Return `unknown` / `insufficient_evidence`.

### Returned timestamp is invalid
Reject or quarantine the observation and surface extraction-quality failure.

### Model emits an unrecognized value
Fail schema validation and retain raw output only in protected diagnostic data if needed.

### Two extraction passes disagree
Downgrade confidence / require human review instead of choosing whichever answer is more convenient.

### ClickHouse unavailable
Extraction may complete, but continuity/history workflows must not claim persistence until the write path succeeds; agent history queries fail visibly per Gate E.

## 16. Implementation order

Do **not** start here until Gate A–F in `VERTICAL_SLICE_SPEC.md` pass.

Then:

1. create and label 2 clips (`S28-T31`, `S28-T47`);
2. test only mug-hand and jacket extraction;
3. validate schema + evidence windows;
4. persist extracted observations alongside seeded equivalents using a distinct source/version;
5. compare model output to fixed truth labels;
6. add lamp;
7. add one negative-control boom clip;
8. test dialogue timestamping;
9. evaluate eyeline last;
10. promote only properties that meet the judge-flow threshold.

## 17. What the final demo should truthfully claim

Good claim:

> Gemini converts each take into timestamped production observations; ClickHouse preserves that history and lets the agent compare it across the shoot through the official MCP path. Uncertain perception remains reviewable instead of being silently treated as fact.

Avoid claims such as:

- "frame-perfect continuity" unless measured with an appropriate frame-level pipeline;
- "detects every continuity error";
- "real-time" unless measured end-to-end latency supports the wording;
- "zero hallucinations";
- accuracy percentages not produced by the fixed evaluation set.

## 18. Current source references

Re-verify these at implementation time because model/API behavior can evolve.

- Gemini API video understanding: https://ai.google.dev/gemini-api/docs/video-understanding
- Vertex AI video sample: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/samples/googlegenaisdk-textgen-with-video
- Official ClickHouse MCP: https://github.com/ClickHouse/mcp-clickhouse
- TakeKeeper vertical slice: `VERTICAL_SLICE_SPEC.md`
- TakeKeeper ClickHouse contract: `DATA_AND_QUERY_CONTRACT.md`

## 19. Immediate decision this document unlocks

**Do not make transient boom/eyeline behavior the first proof of Gemini extraction.** Start with sustained mug-hand and jacket-state differences, measure them against self-owned labeled clips, and promote other properties only after their evidence quality is demonstrated.

This keeps the hackathon story technically defensible while preserving the seeded data path for deterministic ClickHouse/MCP acceptance gates.