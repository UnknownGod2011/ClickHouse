# TakeKeeper Multimodal Benchmark

TakeKeeper's multimodal benchmark is a credential-free release gate for the governed extraction-to-continuity path. It is designed to catch regressions in production-memory safety independently of provider availability.

The checked-in manifest lives at `tests/fixtures/multimodal_eval/manifest.json`. Each case supplies trusted production/take metadata, a deterministic fixture model response, labeled per-property truth, and continuity baselines. Evaluation flows through the same `GovernedMultimodalExtractor` and continuity projection boundary used by the application.

## Run

From an editable install:

```bash
pip install -e .
takekeeper-benchmark tests/fixtures/multimodal_eval/manifest.json
```

Without installation:

```bash
PYTHONPATH=src python -m takekeeper.benchmark_cli tests/fixtures/multimodal_eval/manifest.json
```

Write the exact same stable JSON report to a file:

```bash
PYTHONPATH=src python -m takekeeper.benchmark_cli \
  tests/fixtures/multimodal_eval/manifest.json \
  --output .takekeeper/benchmark-report.json
```

The command always emits the report to stdout. Exit code `0` means all acceptance thresholds passed, `1` means the benchmark executed but quality regressed, and `2` means the benchmark could not be evaluated because the manifest/arguments/input were invalid.

## Default acceptance policy

The default gate requires:

- exact normalized-value accuracy: `1.00`;
- mean temporal evidence IoU: `>= 0.80`;
- evidence IoU@0.50 rate: `1.00`;
- extraction-disposition accuracy: `1.00`;
- continuity-projection eligibility accuracy: `1.00`;
- final finding-status accuracy: `1.00`;
- unsupported non-abstaining assertions: `0`.

Thresholds can be changed explicitly with CLI flags when evaluating a real model candidate, but benchmark reports record the thresholds used so results remain auditable. Do not silently lower thresholds after inspecting a candidate result.

## Report contract

Reports use schema `takekeeper-multimodal-benchmark-report-v1` and contain:

- SHA-256 of the exact manifest bytes;
- extractor model/version candidate metadata;
- the exact acceptance thresholds;
- weighted aggregate metrics across all labeled properties;
- per-case metrics and failure reasons;
- final `passed` and bounded failure diagnostics.

JSON keys are sorted and floating metrics are rounded to six decimal places, making output stable enough for local diffing and archival without requiring GitHub Actions.

The report intentionally does **not** duplicate raw video, credentials, prompts, model rationales, or provider secrets.

## What this benchmark proves

The deterministic fixture suite proves that TakeKeeper's local safety machinery correctly scores and handles model responses, including abstention and continuity projection. It does **not** prove Gemini video-understanding quality. A live model candidate should use fixed, self-owned/generated labeled clips and preserve truth labels independently of model output before claiming real multimodal accuracy.
