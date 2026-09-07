# Gemini / Vertex AI extraction integration

TakeKeeper keeps multimodal model access behind the `ExtractionTransport` protocol. The concrete `GoogleGenAIExtractionTransport` uses Google's current `google-genai` SDK while leaving all production/scene/take scope, property-registry validation, confidence policy, provenance persistence, and continuity projection inside TakeKeeper's deterministic application core.

## Install

The core project has no Google dependency. Install the optional integration only when needed:

```bash
pip install -e '.[gemini]'
```

## Gemini Developer API

```python
from takekeeper import (
    GoogleGenAIExtractionTransport,
    GoogleGenAITransportConfig,
    GovernedMultimodalExtractor,
    create_google_genai_client,
)

client = create_google_genai_client()  # normal google-genai environment discovery
transport = GoogleGenAIExtractionTransport(
    client,
    GoogleGenAITransportConfig(model="gemini-2.5-flash"),
)
extractor = GovernedMultimodalExtractor(transport)
```

An explicit API key can be supplied to `create_google_genai_client(api_key=...)`, but do not hard-code it in source or checked-in config.

## Vertex AI

```python
client = create_google_genai_client(
    vertex_ai=True,
    project="my-gcp-project",
    location="global",
)
transport = GoogleGenAIExtractionTransport(
    client,
    GoogleGenAITransportConfig(model="gemini-2.5-flash"),
)
```

Vertex authentication is delegated to Google's normal Application Default Credentials. Use a narrowly permissioned service identity in deployed environments.

## Media contract

The current transport accepts only trusted `https://` and `gs://` video URIs with a recognizable supported video extension. `file://`, plaintext `http://`, FTP, embedded URL credentials, missing GCS objects, image files, and ambiguous extensionless URIs fail before an SDK request is sent.

This boundary intentionally does **not** upload local files or mint signed URLs. Production code should upload media through a separately governed ingest/object-storage path and pass a trusted URI into `TakeExtractionRequest`. Signed HTTPS query parameters are allowed because private object stores commonly use them; TakeKeeper never writes the URI into model output or continuity state.

## Structured output

Every request uses:

- `response_mime_type = application/json`;
- TakeKeeper's generated response JSON Schema;
- deterministic temperature `0.0` by default;
- a bounded output-token limit;
- no Google tools, function calling, code execution, or model-selected external resources.

TakeKeeper-only `x-*` schema annotations are removed before the provider request. The original schema remains unchanged locally.

Provider-side structured output is not trusted as validation. `GovernedMultimodalExtractor` parses and validates the returned JSON again, rejects unexpected top-level or observation fields, rejects unconfigured entity/property pairs and values, checks evidence windows against trusted take duration, enforces allowed source types, and derives machine-confidence disposition locally.

## Trust boundary

The model never supplies `production_id`, `scene_id`, or `take_id`. Those identifiers come from trusted application metadata. Model output also cannot directly write ClickHouse, approve findings, mutate baselines, or bypass the extraction-to-continuity projection rule.

A model/provider exception is wrapped in a redacted transport error rather than returning provider exception text to operators or persistence layers. Empty/non-text responses fail closed.

## Testing

`tests/test_google_genai_transport.py` uses a fake SDK client and fake media-part factory, so it requires neither Google credentials nor `google-genai`. It verifies the request envelope, schema sanitization, media URI policy, redacted failures, empty-response behavior, and the end-to-end handoff back through `GovernedMultimodalExtractor`.

Live Gemini/Vertex compatibility is a separate integration gate and must be measured with private/self-owned media before being claimed.

## Current official references

- Google Gen AI Python SDK: https://googleapis.github.io/python-genai/
- Gemini video understanding: https://ai.google.dev/gemini-api/docs/video-understanding
- Gemini file input methods: https://ai.google.dev/gemini-api/docs/generate-content/file-input-methods
- Gemini structured output examples are documented under the Python SDK's JSON Response Schema section.
