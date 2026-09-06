import unittest
from takekeeper.continuity import compare_observations
from takekeeper.fixtures import PRODUCTION_ID, SCENE_ID, scene_28_baselines, take_47_observations
from takekeeper.models import Observation

class ContinuityTests(unittest.TestCase):
    def test_scene_28_take_47_acceptance_contract(self):
        findings = compare_observations(production_id=PRODUCTION_ID, scene_id=SCENE_ID, take_id="S28-T47", observations=take_47_observations(), baselines=scene_28_baselines())
        by_property = {f.property_key: f for f in findings}
        self.assertEqual(by_property["prop.mug.hand"].status, "mismatch")
        self.assertEqual(by_property["prop.mug.hand"].baseline_value, "right")
        self.assertEqual(by_property["prop.mug.hand"].observed_value, "left")
        self.assertEqual(by_property["wardrobe.jacket.state"].status, "mismatch")
        self.assertEqual(by_property["set.practical_lamp.state"].status, "needs_confirmation")
        self.assertEqual(by_property["set.practical_lamp.state"].baseline_source_take_id, "S28-T31")
    def test_missing_observation_is_not_invented(self):
        findings = compare_observations(production_id=PRODUCTION_ID, scene_id=SCENE_ID, take_id="S28-T47", observations=take_47_observations()[:-1], baselines=scene_28_baselines())
        lamp = next(f for f in findings if f.property_key == "set.practical_lamp.state")
        self.assertEqual(lamp.status, "insufficient_evidence")
        self.assertIsNone(lamp.observed_value)
    def test_invalid_confidence_rejected(self):
        with self.assertRaises(ValueError): Observation(PRODUCTION_ID, SCENE_ID, "T", "maya", "x", "y", 1.2, 0, 1)

if __name__ == "__main__": unittest.main()
