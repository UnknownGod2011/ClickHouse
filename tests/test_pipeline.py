import unittest

from takekeeper.memory import InMemoryProductionMemory
from takekeeper.models import Baseline, Observation
from takekeeper.service import TakeAnalysisService


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.memory = InMemoryProductionMemory()
        self.service = TakeAnalysisService(self.memory)
        self.memory.upsert_baselines([
            Baseline("glass-house", "28", "maya", "prop.mug.hand", "right", "S28-T31")
        ])

    def test_end_to_end_analysis_persists_findings(self) -> None:
        findings = self.service.analyze(
            production_id="glass-house",
            scene_id="28",
            take_id="S28-T47",
            observations=[
                Observation("glass-house", "28", "S28-T47", "maya", "prop.mug.hand", "left", 0.96, 1000, 2000)
            ],
        )
        self.assertEqual(findings[0].status, "mismatch")
        self.assertEqual(
            self.memory.list_findings(production_id="glass-house", scene_id="28", take_id="S28-T47"),
            findings,
        )

    def test_reanalysis_replaces_stale_findings(self) -> None:
        bad = Observation("glass-house", "28", "S28-T47", "maya", "prop.mug.hand", "left", 0.96, 1000, 2000)
        good = Observation("glass-house", "28", "S28-T47", "maya", "prop.mug.hand", "right", 0.96, 1000, 2000)
        self.service.analyze(production_id="glass-house", scene_id="28", take_id="S28-T47", observations=[bad])
        self.assertEqual(len(self.memory.list_findings(production_id="glass-house", scene_id="28", take_id="S28-T47")), 1)
        self.service.analyze(production_id="glass-house", scene_id="28", take_id="S28-T47", observations=[good])
        self.assertEqual(self.memory.list_findings(production_id="glass-house", scene_id="28", take_id="S28-T47"), [])

    def test_rejects_cross_production_ingestion(self) -> None:
        with self.assertRaises(ValueError):
            self.service.analyze(
                production_id="glass-house",
                scene_id="28",
                take_id="S28-T47",
                observations=[
                    Observation("other-production", "28", "S28-T47", "maya", "prop.mug.hand", "left", 0.90, 1000, 2000)
                ],
            )
        self.assertEqual(self.memory.list_observations(production_id="glass-house", scene_id="28", take_id="S28-T47"), [])


if __name__ == "__main__":
    unittest.main()
