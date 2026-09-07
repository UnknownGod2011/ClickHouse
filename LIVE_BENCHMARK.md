# Live Gemini / Vertex benchmark

TakeKeeper's live-candidate runner evaluates externally hosted self-owned benchmark clips with the same governed extraction, projection, continuity, metrics, and pass/fail policy used by the deterministic fixture benchmark.

## Trust boundary

The checked-in `takekeeper-multimodal-eval-v1` manifest remains immutable benchmark truth. Do not replace its `media_uri` or `response` fields when preparing a live run.

Instead, create a separate `takekeeper-live-media-map-v1` file:

```json
{
  "schema_version": "takekeeper-live-media-map-v1",
  "manifest_sha256": "<sha256-of-exact-manifest-bytes>",
  "cases": {
    "matching_clear_take": "gs://private-bucket/take-001.mp4",
    "clear_continuity_mismatch": "gs://private-bucket/take-002.mp4",
    "occluded_abstention": "gs://private-bucket/take-003.mp4"
  }
}
```

The case set must exactly match the truth manifest and the digest must match the exact manifest bytes being evaluated. This prevents accidentally scoring one truth revision against media prepared for another.

The media-map contents are never copied into the benchmark report. Only its SHA-256 is recorded, because HTTPS media entries may contain signed query parameters. Do not commit a media map containing signed URLs or private bucket names unless those values are intentionally public.

TakeKeeper does not upload media. Upload/publication remains an explicit operator-controlled step outside the runner.

## Developer API

Install the optional provider dependency:

```bash
pip install -e '.[gemini]'
```

Configure Google Gen AI credentials using the SDK-supported environment mechanism, then run:

```bash
takekeeper-live-benchmark \
  tests/fixtures/multimodal_eval/manifest.json \
  /secure/path/live-media-map.json \
  --model <gemini-model-id> \
  --extractor-version <candidate-label> \
  --output .takekeeper/live-benchmark-report.json
```

API keys are intentionally not accepted as command-line flags so they are not encouraged into shell history or process listings.

## Vertex AI

Use Application Default Credentials and provide the project/location either with flags or environment variables:

```bash
export GOOGLE_CLOUD_PROJECT=<project>
export GOOGLE_CLOUD_LOCATION=<location>

takekeeper-live-benchmark \
  tests/fixtures/multimodal_eval/manifest.json \
  /secure/path/live-media-map.json \
  --model <vertex-gemini-model-id> \
  --extractor-version <candidate-label> \
  --vertex-ai \
  --output .takekeeper/live-benchmark-report.json
```

`--project` and `--location` override the corresponding environment variables when supplied.

## What is scored

Each live response still passes through `GovernedMultimodalExtractor`, so provider-side structured output is not trusted as application state. The runner evaluates:

- normalized value accuracy;
- evidence-window mean IoU;
- evidence IoU >= 0.50 rate;
- extraction disposition accuracy;
- continuity projection eligibility;
- final continuity finding status;
- unsupported assertions.

Default thresholds are identical to the deterministic benchmark gate. Exit code `0` means the candidate passed, `1` means the run completed but quality failed policy, and `2` means input/provider execution failed.

## Provenance and comparison discipline

Archive together:

1. the immutable truth manifest or its exact digest;
2. generated `media-manifest.json` from `takekeeper-generate-fixture-media`;
3. the private live media map in an appropriate secure location;
4. the emitted `takekeeper-multimodal-benchmark-report-v1` report;
5. the exact model identifier and operator-defined extractor version already recorded in that report.

Do not loosen labels or thresholds after observing a candidate merely to make that candidate pass. If thresholds are intentionally changed for an experiment, the report records the applied policy.

## Security properties

- Media URIs remain trusted operator input; Gemini cannot select production media.
- `GoogleGenAIExtractionTransport` still accepts only supported `https://` or `gs://` video URIs and rejects embedded URL credentials.
- The live runner has no upload, deletion, ClickHouse-write, MCP-write, or remediation authority.
- Signed media URIs are not emitted in benchmark JSON.
- Provider failures are reduced at the CLI boundary so exception payloads are not blindly copied to stderr.
- Production/scene/take identity comes from the immutable benchmark manifest, never from provider output.

Live quality remains unproven until the command is executed with authorized Gemini/Vertex credentials and reachable trusted media.