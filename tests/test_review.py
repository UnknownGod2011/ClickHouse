from __future__ import annotations

import unittest
from datetime import datetime, timezone

from takekeeper.memory import InMemoryProductionMemory
from takekeeper.models import Finding
from takekeeper.review import (
    ClickHouseReviewDecisionStore,
    FindingReviewService,
    InMemoryReviewDecisionStore,
    ReviewDecision,
    stable_finding_id,
)


class Result:
    def __init__(self, rows):
        self.result_set = rows


class FakeClient:
    def __init__(self):
        self.inserts = []
        self.queries = []
        self.query_results = []

    def insert(self, table, data, column_names=None, **kwargs):
        self.inserts.append((table, data, column_names, kwargs))

    def query(self, query, parameters=None, **kwargs):
        self.queries.append((query, parameters, kwargs))
        return Result(self.query_results.pop(0) if self.query_results else [])


def finding(*, production_id="glass-house", observed_value="right"):
    return Finding(
        production_id=production_id,
        scene_id="S28",
        take_id="S28-T47",
        entity_id="maya",
        property_key="prop.mug_hand",
        baseline_value="left",
        observed_value=observed_value,
        confidence=0.98,
        status="mismatch",
        evidence_start_ms=100,
        evidence_end_ms=900,
        baseline_source_take_id="S28-T31",
    )


class ReviewTests(unittest.TestCase):
    def test_finding_id_is_stable_across_reanalysis_values(self):
        first = finding(observed_value="right")
        second = finding(observed_value="center")
        self.assertEqual(stable_finding_id(first), stable_finding_id(second))

    def test_review_service_records_only_existing_scoped_finding(self):
        memory = InMemoryProductionMemory()
        memory.replace_findings(
            production_id="glass-house",
            scene_id="S28",
            take_id="S28-T47",
            findings=[finding()],
        )
        store = InMemoryReviewDecisionStore()
        service = FindingReviewService(memory, store)

        decision = service.review(
            production_id="glass-house",
            scene_id="S28",
            take_id="S28-T47",
            entity_id="maya",
            property_key="prop.mug_hand",
            actor_id="script-supervisor@example.test",
            decision="confirmed",
            note="Matches the marked continuity reference.",
        )

        self.assertEqual(stable_finding_id(finding()), decision.finding_id)
        self.assertTrue(decision.decision_id)
        self.assertIsNotNone(decision.created_at)
        self.assertEqual([decision], service.history(
            production_id="glass-house",
            scene_id="S28",
            take_id="S28-T47",
            entity_id="maya",
            property_key="prop.mug_hand",
        ))

    def test_review_service_rejects_unknown_or_cross_tenant_finding(self):
        memory = InMemoryProductionMemory()
        memory.replace_findings(
            production_id="glass-house",
            scene_id="S28",
            take_id="S28-T47",
            findings=[finding()],
        )
        service = FindingReviewService(memory, InMemoryReviewDecisionStore())
        with self.assertRaises(LookupError):
            service.review(
                production_id="other-production",
                scene_id="S28",
                take_id="S28-T47",
                entity_id="maya",
                property_key="prop.mug_hand",
                actor_id="reviewer",
                decision="rejected",
            )

    def test_review_requires_actor(self):
        with self.assertRaises(ValueError):
            ReviewDecision(
                production_id="glass-house",
                scene_id="S28",
                take_id="S28-T47",
                entity_id="maya",
                property_key="prop.mug_hand",
                finding_id=stable_finding_id(finding()),
                actor_id="   ",
                decision="confirmed",
            )

    def test_clickhouse_store_appends_without_mutation_and_binds_scope_on_read(self):
        client = FakeClient()
        store = ClickHouseReviewDecisionStore(client)
        persisted = store.append(
            ReviewDecision(
                production_id="glass-house' OR 1=1 --",
                scene_id="S28",
                take_id="S28-T47",
                entity_id="maya",
                property_key="prop.mug_hand",
                finding_id="stable-id",
                actor_id="reviewer",
                decision="needs_followup",
                note="Check second camera.",
            )
        )
        self.assertEqual("takekeeper.human_decisions", client.inserts[0][0])
        self.assertEqual("stable-id", client.inserts[0][1][0][2])
        self.assertTrue(persisted.decision_id)

        created = datetime(2026, 9, 6, tzinfo=timezone.utc)
        client.query_results = [[("decision-1", "reviewer", "confirmed", "ok", created)]]
        rows = store.list_for_finding(
            production_id="glass-house' OR 1=1 --",
            scene_id="S28",
            take_id="S28-T47",
            entity_id="maya",
            property_key="prop.mug_hand",
            finding_id="stable-id",
        )
        sql, parameters, _ = client.queries[0]
        self.assertNotIn("glass-house' OR 1=1 --", sql)
        self.assertEqual("glass-house' OR 1=1 --", parameters["production_id"])
        self.assertEqual("confirmed", rows[0].decision)

    def test_database_identifier_is_validated(self):
        with self.assertRaises(ValueError):
            ClickHouseReviewDecisionStore(FakeClient(), database="takekeeper; DROP DATABASE default")


if __name__ == "__main__":
    unittest.main()
