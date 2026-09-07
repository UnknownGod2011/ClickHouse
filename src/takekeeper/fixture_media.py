from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

MEDIA_REPORT_SCHEMA = "takekeeper-generated-media-v1"
SUPPORTED_BENCHMARK_SCHEMA = "takekeeper-multimodal-eval-v1"
DEFAULT_SIZE = "640x360"
DEFAULT_FPS = 30
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


@dataclass(frozen=True, slots=True)
class GeneratedArtifact:
    case_name: str
    take_id: str
    path: str
    mime_type: str
    duration_ms: int
    sha256: str
    bytes: int


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_manifest(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != SUPPORTED_BENCHMARK_SCHEMA:
        raise ValueError(f"unsupported benchmark manifest schema: {payload.get('schema_version')!r}")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("benchmark manifest must contain at least one case")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("benchmark cases must be objects")
        name = case.get("name")
        take_id = case.get("take_id")
        duration_ms = case.get("duration_ms")
        truth = case.get("truth")
        if not isinstance(name, str) or not _SAFE_NAME.fullmatch(name):
            raise ValueError(f"unsafe benchmark case name: {name!r}")
        if name in seen:
            raise ValueError(f"duplicate benchmark case name: {name}")
        seen.add(name)
        if not isinstance(take_id, str) or not _SAFE_NAME.fullmatch(take_id):
            raise ValueError(f"unsafe benchmark take_id for {name!r}")
        if not isinstance(duration_ms, int) or not 1000 <= duration_ms <= 60_000:
            raise ValueError(f"duration_ms for {name!r} must be between 1000 and 60000")
        if not isinstance(truth, list) or not truth:
            raise ValueError(f"benchmark case {name!r} must contain truth labels")
        for row in truth:
            if not isinstance(row, Mapping):
                raise ValueError(f"truth rows for {name!r} must be objects")
            start = row.get("evidence_start_ms")
            end = row.get("evidence_end_ms")
            if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= duration_ms:
                raise ValueError(f"invalid evidence interval for {name!r}")


def _enable(start_ms: int, end_ms: int) -> str:
    return f"between(t,{start_ms / 1000:.3f},{end_ms / 1000:.3f})"


def _drawbox(x: int, y: int, w: int, h: int, *, color: str, start_ms: int | None = None, end_ms: int | None = None) -> str:
    value = f"drawbox=x={x}:y={y}:w={w}:h={h}:color={color}:t=fill"
    if start_ms is not None and end_ms is not None:
        value += f":enable='{_enable(start_ms, end_ms)}'"
    return value


def build_filtergraph(case: Mapping[str, Any]) -> str:
    """Build a simple, text-free visual scene from immutable benchmark truth labels.

    The graphics are intentionally synthetic: a neutral performer silhouette, jacket geometry,
    mug/hand geometry, and explicit occlusion masks. No labels such as "left", "right", or
    "open" are rendered into the video, so a future model cannot solve the benchmark by OCR.
    """

    duration_ms = int(case["duration_ms"])
    filters = [
        _drawbox(270, 70, 100, 230, color="0x45505f"),  # torso
        _drawbox(220, 105, 50, 28, color="0x6b7280"),  # left arm
        _drawbox(370, 105, 50, 28, color="0x6b7280"),  # right arm
        _drawbox(292, 32, 56, 56, color="0xc7a27c"),   # head
    ]

    supported = {("hero_mug", "hand"), ("maya", "jacket_state")}
    identities: set[tuple[str, str]] = set()
    for truth in case["truth"]:
        entity = str(truth.get("entity_id"))
        key = str(truth.get("property_key"))
        identity = (entity, key)
        if identity not in supported:
            raise ValueError(f"fixture media renderer does not support property {entity}.{key}")
        if identity in identities:
            raise ValueError(f"duplicate truth property {entity}.{key}")
        identities.add(identity)

        value = str(truth.get("normalized_value"))
        start = int(truth["evidence_start_ms"])
        end = int(truth["evidence_end_ms"])

        if identity == ("hero_mug", "hand"):
            if value == "left":
                filters.extend([
                    _drawbox(180, 112, 40, 20, color="0xc7a27c", start_ms=start, end_ms=end),
                    _drawbox(154, 126, 34, 44, color="0xb87333", start_ms=start, end_ms=end),
                ])
            elif value == "right":
                filters.extend([
                    _drawbox(420, 112, 40, 20, color="0xc7a27c", start_ms=start, end_ms=end),
                    _drawbox(452, 126, 34, 44, color="0xb87333", start_ms=start, end_ms=end),
                ])
            elif value == "unknown":
                filters.extend([
                    _drawbox(160, 92, 94, 105, color="0x20242b", start_ms=start, end_ms=end),
                    _drawbox(386, 92, 94, 105, color="0x20242b", start_ms=start, end_ms=end),
                ])
            else:
                raise ValueError(f"unsupported hero_mug.hand value: {value!r}")

        if identity == ("maya", "jacket_state"):
            if value == "zipped":
                filters.extend([
                    _drawbox(300, 92, 40, 190, color="0x253449", start_ms=start, end_ms=end),
                    _drawbox(318, 102, 4, 166, color="0xd1d5db", start_ms=start, end_ms=end),
                ])
            elif value == "open":
                filters.extend([
                    _drawbox(286, 92, 27, 190, color="0x253449", start_ms=start, end_ms=end),
                    _drawbox(327, 92, 27, 190, color="0x253449", start_ms=start, end_ms=end),
                    _drawbox(313, 112, 14, 150, color="0x8b6b52", start_ms=start, end_ms=end),
                ])
            elif value == "unknown":
                filters.append(_drawbox(276, 82, 88, 210, color="0x20242b", start_ms=start, end_ms=end))
            else:
                raise ValueError(f"unsupported maya.jacket_state value: {value!r}")

    if not identities:
        raise ValueError("benchmark case has no renderable truth properties")
    # A subtle floor keeps the generated scene spatially stable without adding semantic text.
    filters.append(_drawbox(0, 315, 640, 45, color="0x111827", start_ms=0, end_ms=duration_ms))
    return ",".join(filters)


def _ffmpeg_version(ffmpeg: str) -> str:
    result = subprocess.run(
        [ffmpeg, "-version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    first = result.stdout.splitlines()[0].strip() if result.stdout else ""
    if not first:
        raise RuntimeError("ffmpeg returned no version information")
    return first[:300]


def render_case(case: Mapping[str, Any], *, output_dir: Path, ffmpeg: str) -> GeneratedArtifact:
    name = str(case["name"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name}.mp4"
    duration_seconds = int(case["duration_ms"]) / 1000
    command = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=0xf1f5f9:s={DEFAULT_SIZE}:r={DEFAULT_FPS}:d={duration_seconds:.3f}",
        "-vf",
        build_filtergraph(case),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-map_metadata",
        "-1",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=90)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip().splitlines()
        suffix = f": {detail[-1][:300]}" if detail else ""
        raise RuntimeError(f"ffmpeg failed for benchmark case {name!r}{suffix}") from exc

    size = output_path.stat().st_size
    if size <= 0:
        raise RuntimeError(f"ffmpeg produced an empty artifact for benchmark case {name!r}")
    return GeneratedArtifact(
        case_name=name,
        take_id=str(case["take_id"]),
        path=output_path.name,
        mime_type="video/mp4",
        duration_ms=int(case["duration_ms"]),
        sha256=_sha256_file(output_path),
        bytes=size,
    )


def generate_media(manifest_path: Path, output_dir: Path, *, ffmpeg: str | None = None) -> dict[str, Any]:
    manifest_bytes = manifest_path.read_bytes()
    payload = json.loads(manifest_bytes)
    if not isinstance(payload, Mapping):
        raise ValueError("benchmark manifest root must be an object")
    _validate_manifest(payload)

    executable = ffmpeg or shutil.which("ffmpeg")
    if not executable:
        raise RuntimeError("ffmpeg is required to generate benchmark media but was not found on PATH")

    version = _ffmpeg_version(executable)
    artifacts = [render_case(case, output_dir=output_dir, ffmpeg=executable) for case in payload["cases"]]
    report = {
        "schema_version": MEDIA_REPORT_SCHEMA,
        "benchmark_manifest_sha256": _sha256_bytes(manifest_bytes),
        "generator": {
            "renderer": "takekeeper.fixture_media",
            "ffmpeg": version,
            "frame_size": DEFAULT_SIZE,
            "fps": DEFAULT_FPS,
        },
        "artifacts": [
            {
                "case_name": item.case_name,
                "take_id": item.take_id,
                "path": item.path,
                "mime_type": item.mime_type,
                "duration_ms": item.duration_ms,
                "sha256": item.sha256,
                "bytes": item.bytes,
            }
            for item in artifacts
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "media-manifest.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate self-owned synthetic video fixtures for TakeKeeper's multimodal benchmark.")
    parser.add_argument("manifest", type=Path, help="Path to takekeeper-multimodal-eval-v1 manifest")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".takekeeper/generated-eval-media"),
        help="Generated media directory (default: .takekeeper/generated-eval-media)",
    )
    parser.add_argument("--ffmpeg", help="Explicit ffmpeg executable path; otherwise PATH is searched")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = generate_media(args.manifest, args.output_dir, ffmpeg=args.ffmpeg)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"takekeeper-fixture-media: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
