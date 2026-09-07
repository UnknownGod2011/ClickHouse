from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from takekeeper.fixture_media import (
    MEDIA_REPORT_SCHEMA,
    build_filtergraph,
    generate_media,
    main,
    render_case,
)


class FixtureMediaTests(unittest.TestCase):
    def _manifest(self) -> dict:
        return {
            "schema_version": "takekeeper-multimodal-eval-v1",
            "production_id": "demo-production",
            "scene_id": "scene-12",
            "extractor_model": "fixture-model",
            "extractor_version": "fixture-v1",
            "baselines": [],
            "cases": [
                {
                    "name": "clear_case",
                    "take_id": "take-001",
                    "media_uri": "fixture://take-001.mp4",
                    "duration_ms": 10000,
                    "truth": [
                        {
                            "entity_id": "hero_mug",
                            "property_key": "hand",
                            "normalized_value": "left",
                            "evidence_start_ms": 1400,
                            "evidence_end_ms": 4400,
                        },
                        {
                            "entity_id": "maya",
                            "property_key": "jacket_state",
                            "normalized_value": "zipped",
                            "evidence_start_ms": 1000,
                            "evidence_end_ms": 8600,
                        },
                    ],
                }
            ],
        }

    def test_filtergraph_is_text_free_and_uses_truth_windows(self) -> None:
        graph = build_filtergraph(self._manifest()["cases"][0])
        self.assertIn("between(t,1.400,4.400)", graph)
        self.assertIn("between(t,1.000,8.600)", graph)
        self.assertNotIn("drawtext", graph)
        self.assertNotIn("left hand", graph.lower())
        self.assertNotIn("zipped", graph.lower())

    def test_filtergraph_supports_mismatch_and_occlusion_geometry(self) -> None:
        mismatch = self._manifest()["cases"][0]
        mismatch["truth"][0]["normalized_value"] = "right"
        mismatch["truth"][1]["normalized_value"] = "open"
        mismatch_graph = build_filtergraph(mismatch)
        self.assertIn("x=452", mismatch_graph)
        self.assertIn("x=313", mismatch_graph)

        occluded = self._manifest()["cases"][0]
        occluded["truth"][0]["normalized_value"] = "unknown"
        occluded["truth"][1]["normalized_value"] = "unknown"
        occluded_graph = build_filtergraph(occluded)
        self.assertIn("color=0x20242b", occluded_graph)

    def test_manifest_validation_rejects_path_like_case_names(self) -> None:
        manifest = self._manifest()
        manifest["cases"][0]["name"] = "../escape"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsafe benchmark case name"):
                generate_media(path, Path(tmp) / "out", ffmpeg="ffmpeg")

    @patch("takekeeper.fixture_media.subprocess.run")
    def test_render_case_uses_bounded_local_ffmpeg_command(self, run) -> None:
        def fake_run(command, **kwargs):
            class Result:
                stdout = ""
                stderr = ""
            output = Path(command[-1])
            output.write_bytes(b"synthetic-mp4")
            return Result()

        run.side_effect = fake_run
        with tempfile.TemporaryDirectory() as tmp:
            artifact = render_case(
                self._manifest()["cases"][0],
                output_dir=Path(tmp),
                ffmpeg="/usr/bin/ffmpeg",
            )
        command = run.call_args.args[0]
        self.assertEqual(command[0], "/usr/bin/ffmpeg")
        self.assertIn("-nostdin", command)
        self.assertIn("-an", command)
        self.assertIn("libx264", command)
        self.assertNotIn("drawtext", command[command.index("-vf") + 1])
        self.assertEqual(artifact.sha256, hashlib.sha256(b"synthetic-mp4").hexdigest())
        self.assertEqual(artifact.bytes, len(b"synthetic-mp4"))

    @patch("takekeeper.fixture_media.subprocess.run")
    def test_generate_media_records_manifest_and_tool_provenance(self, run) -> None:
        def fake_run(command, **kwargs):
            class Result:
                stderr = ""
                stdout = "ffmpeg version fixture-7.0\n" if "-version" in command else ""
            if "-version" not in command:
                Path(command[-1]).write_bytes(b"generated-video")
            return Result()

        run.side_effect = fake_run
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            manifest_bytes = (json.dumps(self._manifest(), sort_keys=True) + "\n").encode()
            manifest_path.write_bytes(manifest_bytes)
            output_dir = root / "generated"
            report = generate_media(manifest_path, output_dir, ffmpeg="/usr/bin/ffmpeg")
            written = json.loads((output_dir / "media-manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(report["schema_version"], MEDIA_REPORT_SCHEMA)
        self.assertEqual(report["benchmark_manifest_sha256"], hashlib.sha256(manifest_bytes).hexdigest())
        self.assertEqual(report["generator"]["ffmpeg"], "ffmpeg version fixture-7.0")
        self.assertEqual(report, written)
        self.assertEqual(report["artifacts"][0]["sha256"], hashlib.sha256(b"generated-video").hexdigest())
        self.assertEqual(report["artifacts"][0]["mime_type"], "video/mp4")

    @patch("takekeeper.fixture_media.shutil.which", return_value=None)
    def test_missing_ffmpeg_fails_closed(self, _which) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(self._manifest()), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "ffmpeg is required"):
                generate_media(path, Path(tmp) / "out")

    def test_cli_returns_input_error_for_missing_manifest(self) -> None:
        self.assertEqual(main(["/definitely/missing/manifest.json"]), 2)


if __name__ == "__main__":
    unittest.main()
