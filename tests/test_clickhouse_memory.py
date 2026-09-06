from __future__ import annotations

import unittest

from takekeeper.clickhouse_memory import ClickHouseProductionMemory
from takekeeper.models import Finding, Observation
from takekeeper.review import stable_finding_id


class Result:
    def __init__(self, rows):
        self.result_set = rows


class FakeClient:
    def __init__(self):
        self.commands = []
        self.inserts = []
        self.queries = []
        self.query_results = []

    def command(self, cmd, parameters=None, **kwargs):
        self.commands.append((cmd, parameters, kwargs))

    def insert(self, table, data, column_names=None, **kwargs):
        self.inserts.append((table, data, column_names, kwargs))

    def query(self, query, parameters=None, **kwargs):
        self.queries.append((query, parameters, kwargs))
        return Result(self.query_results.pop(0) if self.query_results else [])


class ClickHouseProductionMemoryTests(unittest.TestCase):
    def test_observation_upsert_uses_bound_scope_parameters(self):
        client = FakeClient()
        memory = ClickHouseProductionMemory(client)
        hostile = "glass-house' OR 1=1 --"
        observation = Observation(production_id=hostile, scene_id="S28", take_id="S28-T47", entity_id="maya", property_key="prop.mug_hand", normalized_value="right", confidence=0.98, evidence_start_ms=100, evidence_end_ms=900)
        memory.upsert_observations([observation])
        sql, parameters, kwargs = client.commands[0]
        self.assertNotIn(hostile, sql)
        self.assertEqual(hostile, parameters["production_id"])
        self.assertEqual({"mutations_sync": 1}, kwargs["settings"])
        self.assertEqual("takekeeper.observations", client.inserts[0][0])

    def test_list_observations_maps_rows_and_scope(self):
        client = FakeClient()
        client.query_results = [[("maya", "prop.mug_hand", "right", 0.91, 10, 20, "unverified")]]
        memory = ClickHouseProductionMemory(client)
        rows = memory.list_observations(production_id="glass-house", scene_id="S28", take_id="S28-T47")
        self.assertEqual("right", rows[0].normalized_value)
        _, parameters, _ = client.queries[0]
        self.assertEqual({"production_id": "glass-house", "scene_id": "S28", "take_id": "S28-T47"}, parameters)

    def test_replace_findings_rejects_cross_scope_before_delete(self):
        client = FakeClient()
        memory = ClickHouseProductionMemory(client)
        finding = Finding(production_id="other-production", scene_id="S28", take_id="S28-T47", entity_id="maya", property_key="wardrobe.jacket_state", baseline_value="on", observed_value="off", confidence=0.99, status="mismatch", evidence_start_ms=0, evidence_end_ms=100, baseline_source_take_id="S28-T31")
        with self.assertRaises(ValueError):
            memory.replace_findings(production_id="glass-house", scene_id="S28", take_id="S28-T47", findings=[finding])
        self.assertEqual([], client.commands)
        self.assertEqual([], client.inserts)

    def test_replace_findings_uses_stable_finding_identity(self):
        client = FakeClient()
        memory = ClickHouseProductionMemory(client)
        finding = Finding(production_id="glass-house", scene_id="S28", take_id="S28-T47", entity_id="maya", property_key="prop.mug_hand", baseline_value="left", observed_value="right", confidence=0.98, status="mismatch", evidence_start_ms=100, evidence_end_ms=900, baseline_source_take_id="S28-T31")
        memory.replace_findings(production_id="glass-house", scene_id="S28", take_id="S28-T47", findings=[finding])
        inserted = client.inserts[0][1][0]
        self.assertEqual(stable_finding_id(finding), inserted[3])

    def test_replace_findings_allows_nullable_failure_honesty_fields(self):
        client = FakeClient()
        memory = ClickHouseProductionMemory(client)
        finding = Finding(production_id="glass-house", scene_id="S28", take_id="S28-T47", entity_id="maya", property_key="prop.phone_hand", baseline_value="left", observed_value=None, confidence=None, status="insufficient_evidence", evidence_start_ms=None, evidence_end_ms=None, baseline_source_take_id="S28-T31")
        memory.replace_findings(production_id="glass-house", scene_id="S28", take_id="S28-T47", findings=[finding])
        inserted = client.inserts[0][1][0]
        self.assertIsNone(inserted[7])
        self.assertIsNone(inserted[9])
        self.assertIsNone(inserted[11])
        self.assertIsNone(inserted[12])

    def test_database_identifier_is_validated(self):
        with self.assertRaises(ValueError):
            ClickHouseProductionMemory(FakeClient(), database="takekeeper; DROP DATABASE default")


if __name__ == "__main__":
    unittest.main()
