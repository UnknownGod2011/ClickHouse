from __future__ import annotations

import copy
import os
import unittest
from pathlib import Path
from uuid import uuid4

from takekeeper.clickhouse_memory import ClickHouseProductionMemory
from takekeeper.extraction import (
    FixtureExtractionTransport,
    GovernedMultimodalExtractor,
    HERO_PROPERTY_REGISTRY,
    TakeExtractionRequest,
)
from takekeeper.models import Baseline, Observation
from takekeeper.service import TakeAnalysisService


REPO_ROOT = Path(__file__).resolve().parents[1]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _execute_sql_script(client, sql: str) -> None:
    for statement in sql.split(";"):
        statement = statement.strip()
        if statement:
            client.command(statement)


class _FakeClient:
    def __init__(self) -> None:
        self.commands = []
        self.inserts = []

    def command(self, cmd, parameters=None, **kwargs):
        self.commands.append((cmd, parameters, kwargs))

    def insert(self, table, data, column_names=None, **kwargs):
        self.inserts.append((table, data, column_names, kwargs))

    def query(self, query, parameters=None, **kwargs):  # pragma: no cover - not used here
        raise AssertionError("unexpected query")


class ClickHouseProjectionReplacementAdapterTests(unittest.TestCase):
    def test_empty_replacement_deletes_only_exact_bound_take_scope(self) -> None:
        client = _FakeClient()
        memory = ClickHouseProductionMemory(client)
        hostile = "prod' OR 1=1 --"

        memory.replace_observations(
            production_id=hostile,
            scene_id="28",
            take_id="T47",
            observations=[],
        )

        self.assertEqual(1, len(client.commands))
        sql, parameters, kwargs = client.commands[0]
        self.assertNotIn(hostile, sql)
        self.assertIn("production_id = {production_id:String}", sql)
        self.assertIn("scene_id = {scene_id:String}", sql)
        self.assertIn("take_id = {take_id:String}", sql)
        self.assertEqual(
            {"production_id": hostile, "scene_id": "28", "take_id": "T47"},
            parameters,
        )
        self.assertEqual({"mutations_sync": 1}, kwargs["settings"])
        self.assertEqual([], client.inserts)

    def test_cross_scope_replacement_fails_before_mutation(self) -> None:
        client = _FakeClient()
        memory = ClickHouseProductionMemory(client)
        row = Observation(
            production_id="other-production",
            scene_id="28",
            take_id="T47",
            entity_id="hero_mug",
            property_key="hand",
            normalized_value="left",
            confidence=0.96,
            evidence_start_ms=1000,
            evidence_end_ms=5000,
        )

        with self.assertRaisesRegex(ValueError, "replacement scope"):
            memory.replace_observations(
                production_id="glass-house",
                scene_id="28",
                take_id="T47",
                observations=[row],
            )

        self.assertEqual([], client.commands)
        self.assertEqual([], client.inserts)


@unittest.skipUnless(
    _env_bool("TAKEKEEPER_CLICKHOUSE_INTEGRATION"),
    "set TAKEKEEPER_CLICKHOUSE_INTEGRATION=1 to run against a disposable real ClickHouse database",
)
class RealClickHouseProjectionReplacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            import clickhouse_connect
        except ImportError as exc:  # pragma: no cover - integration mode only
            raise unittest.SkipTest("install TakeKeeper with the [clickhouse] extra") from exc

        cls.client = clickhouse_connect.get_client(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
            username=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""),
            secure=_env_bool("CLICKHOUSE_SECURE", False),
            database=os.getenv("CLICKHOUSE_BOOTSTRAP_DATABASE", "default"),
        )
        cls.database = f"takekeeper_projection_it_{uuid4().hex[:12]}"
        cls.client.command(f"CREATE DATABASE {cls.database}")
        schema = (REPO_ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
        schema = schema.replace("CREATE DATABASE IF NOT EXISTS takekeeper;", "")
        schema = schema.replace("takekeeper.", f"{cls.database}.")
        _execute_sql_script(cls.client, schema)

    @classmethod
    def tearDownClass(cls) -> None:
        client = getattr(cls, "client", None)
        database = getattr(cls, "database", None)
        if client is not None and database is not None:
            client.command(f"DROP DATABASE IF EXISTS {database}")
        if client is not None:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    def setUp(self) -> None:
        for table in ("continuity_findings", "continuity_baselines", "observations"):
            self.client.command(f"TRUNCATE TABLE {self.database}.{table}")
        self.memory = ClickHouseProductionMemory(self.client, database=self.database)
        self.service = TakeAnalysisService(self.memory)
        self.memory.upsert_baselines([
            Baseline(
                production_id="glass-house",
                scene_id="28",
                entity_id="hero_mug",
                property_key="hand",
                baseline_value="right",
                source_take_id="T31",
            )
        ])

    @staticmethod
    def _request() -> TakeExtractionRequest:
        return TakeExtractionRequest(
            production_id="glass-house",
            scene_id="28",
            take_id="T47",
            media_uri="fixture://projection-clickhouse",
            duration_ms=10_000,
            properties=HERO_PROPERTY_REGISTRY[:1],
            extractor_model="gemini-fixture",
            extractor_version="fixture-v1",
        )

    @staticmethod
    def _eligible_payload() -> dict:
        return {
            "observations": [{
                "entity_id": "hero_mug",
                "property_key": "hand",
                "normalized_value": "left",
                "raw_model_value": "left",
                "evidence_start_ms": 1000,
                "evidence_end_ms": 5000,
                "confidence": 0.96,
                "source_type": "vision",
                "evidence_rationale_short": "Mug remains clearly in the left hand.",
                "visibility_state": "clear",
                "temporal_support": "sustained",
            }]
        }

    def _extract(self, payload: dict, *, run_id: str):
        request = self._request()
        return GovernedMultimodalExtractor(
            FixtureExtractionTransport({request.media_uri: payload}),
            run_id_factory=lambda: run_id,
        ).extract(request)

    def test_abstaining_reanalysis_clears_only_target_take_and_converges_to_insufficient_evidence(self) -> None:
        other_take = Observation(
            production_id="glass-house",
            scene_id="28",
            take_id="T99",
            entity_id="hero_mug",
            property_key="hand",
            normalized_value="right",
            confidence=0.99,
            evidence_start_ms=0,
            evidence_end_ms=100,
        )
        other_tenant = Observation(
            production_id="other-production",
            scene_id="28",
            take_id="T47",
            entity_id="hero_mug",
            property_key="hand",
            normalized_value="right",
            confidence=0.99,
            evidence_start_ms=0,
            evidence_end_ms=100,
        )
        self.memory.upsert_observations([other_take, other_tenant])

        first_findings, first_projection = self.service.analyze_extraction(
            self._extract(self._eligible_payload(), run_id="projection-it-1")
        )
        self.assertEqual(1, len(first_projection.observations))
        self.assertEqual("mismatch", first_findings[0].status)
        self.assertEqual("left", first_findings[0].observed_value)
        self.assertEqual(
            ["left"],
            [row.normalized_value for row in self.memory.list_observations(
                production_id="glass-house", scene_id="28", take_id="T47"
            )],
        )

        abstaining = copy.deepcopy(self._eligible_payload())
        abstaining["observations"][0].update(
            normalized_value="unknown",
            raw_model_value="unknown",
            confidence=0.35,
            visibility_state="occluded",
            temporal_support="unknown",
            evidence_rationale_short="Mug hand is not visible enough to classify.",
        )
        second_findings, second_projection = self.service.analyze_extraction(
            self._extract(abstaining, run_id="projection-it-2")
        )

        self.assertEqual((), second_projection.observations)
        self.assertEqual([], self.memory.list_observations(
            production_id="glass-house", scene_id="28", take_id="T47"
        ))
        self.assertEqual(1, len(second_findings))
        self.assertEqual("insufficient_evidence", second_findings[0].status)
        self.assertIsNone(second_findings[0].observed_value)

        self.assertEqual(
            ["right"],
            [row.normalized_value for row in self.memory.list_observations(
                production_id="glass-house", scene_id="28", take_id="T99"
            )],
        )
        self.assertEqual(
            ["right"],
            [row.normalized_value for row in self.memory.list_observations(
                production_id="other-production", scene_id="28", take_id="T47"
            )],
        )

        persisted_findings = self.memory.list_findings(
            production_id="glass-house", scene_id="28", take_id="T47"
        )
        self.assertEqual(1, len(persisted_findings))
        self.assertEqual("insufficient_evidence", persisted_findings[0].status)
        self.assertIsNone(persisted_findings[0].observed_value)


if __name__ == "__main__":
    unittest.main()
