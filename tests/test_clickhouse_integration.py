from __future__ import annotations

import os
import unittest
from pathlib import Path
from uuid import uuid4

from takekeeper.clickhouse_memory import ClickHouseProductionMemory
from takekeeper.extraction import FixtureExtractionTransport, GovernedMultimodalExtractor, HERO_PROPERTY_REGISTRY, TakeExtractionRequest
from takekeeper.extraction_store import ClickHouseExtractionProvenanceStore
from takekeeper.fixtures import PRODUCTION_ID, SCENE_ID, scene_28_baselines, take_47_observations
from takekeeper.models import Observation
from takekeeper.queries import EditorialConstraints, editorial_retrieval_sql
from takekeeper.review import ClickHouseReviewDecisionStore, FindingReviewService, stable_finding_id
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


def _extraction_request(*, media_uri: str = "fixture://s28-t47?v=1") -> TakeExtractionRequest:
    return TakeExtractionRequest(
        production_id=PRODUCTION_ID,
        scene_id=SCENE_ID,
        take_id="S28-T47",
        media_uri=media_uri,
        duration_ms=10_000,
        properties=tuple(HERO_PROPERTY_REGISTRY[:1]),
        extractor_model="gemini-fixture",
        extractor_version="fixture-v1",
    )


def _extraction_result(request: TakeExtractionRequest, *, run_id: str, value: str):
    payload = {
        "observations": [
            {
                "entity_id": "hero_mug",
                "property_key": "hand",
                "normalized_value": value,
                "raw_model_value": value,
                "evidence_start_ms": 1000,
                "evidence_end_ms": 5000,
                "confidence": 0.95,
                "source_type": "vision",
                "evidence_rationale_short": f"fixture sees mug in {value} hand",
                "visibility_state": "clear",
                "temporal_support": "sustained",
            }
        ]
    }
    return GovernedMultimodalExtractor(
        FixtureExtractionTransport({request.media_uri: payload}),
        run_id_factory=lambda: run_id,
    ).extract(request)


@unittest.skipUnless(
    _env_bool("TAKEKEEPER_CLICKHOUSE_INTEGRATION"),
    "set TAKEKEEPER_CLICKHOUSE_INTEGRATION=1 to run against a real ClickHouse instance",
)
class RealClickHouseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            import clickhouse_connect
        except ImportError as exc:  # pragma: no cover - only exercised in integration mode
            raise unittest.SkipTest("install TakeKeeper with the [clickhouse] extra") from exc

        host = os.getenv("CLICKHOUSE_HOST", "localhost")
        port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
        username = os.getenv("CLICKHOUSE_USER", "default")
        password = os.getenv("CLICKHOUSE_PASSWORD", "")
        secure = _env_bool("CLICKHOUSE_SECURE", False)
        bootstrap_database = os.getenv("CLICKHOUSE_BOOTSTRAP_DATABASE", "default")

        cls.client = clickhouse_connect.get_client(
            host=host,
            port=port,
            username=username,
            password=password,
            secure=secure,
            database=bootstrap_database,
        )
        cls.database = f"takekeeper_it_{uuid4().hex[:12]}"
        cls.client.command(f"CREATE DATABASE {cls.database}")

        schema = (REPO_ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
        schema = schema.replace("CREATE DATABASE IF NOT EXISTS takekeeper;", "")
        schema = schema.replace("takekeeper.", f"{cls.database}.")
        _execute_sql_script(cls.client, schema)

        cls.seed_sql = (REPO_ROOT / "sql" / "seed_demo.sql").read_text(encoding="utf-8")
        cls.seed_sql = cls.seed_sql.replace("takekeeper.", f"{cls.database}.")

        cls.memory = ClickHouseProductionMemory(cls.client, database=cls.database)
        cls.service = TakeAnalysisService(cls.memory)
        cls.decision_store = ClickHouseReviewDecisionStore(cls.client, database=cls.database)
        cls.review_service = FindingReviewService(cls.memory, cls.decision_store)
        cls.extraction_store = ClickHouseExtractionProvenanceStore(cls.client, database=cls.database)

    def setUp(self) -> None:
        # Every acceptance case starts from the exact same deterministic fixture.
        # This prevents re-analysis, review history, or extraction history from
        # leaking across tests.
        for table in (
            "extracted_observations",
            "extraction_runs",
            "human_decisions",
            "continuity_findings",
            "continuity_baselines",
            "observations",
            "takes",
        ):
            self.client.command(f"TRUNCATE TABLE {self.database}.{table}")
        _execute_sql_script(self.client, self.seed_sql)

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

    def test_seed_contract_and_editorial_retrieval(self) -> None:
        baselines = self.memory.list_baselines(production_id=PRODUCTION_ID, scene_id=SCENE_ID)
        self.assertEqual(3, len(baselines))

        seeded = self.memory.list_observations(
            production_id=PRODUCTION_ID,
            scene_id=SCENE_ID,
            take_id="S28-T47",
        )
        self.assertEqual(6, len(seeded))

        query = editorial_retrieval_sql(
            EditorialConstraints(PRODUCTION_ID, SCENE_ID, min_rating=4),
            database=self.database,
        )
        result = self.client.query(query)
        self.assertEqual(["S28-T31", "S28-T47"], [str(row[0]) for row in result.result_set])

    def test_analysis_persists_exact_scene_28_findings(self) -> None:
        # Re-upserting the same baselines proves the trusted write path can safely
        # replace seeded rows before analysis.
        self.memory.upsert_baselines(scene_28_baselines())
        findings = self.service.analyze(
            production_id=PRODUCTION_ID,
            scene_id=SCENE_ID,
            take_id="S28-T47",
            observations=take_47_observations(),
        )

        by_property = {finding.property_key: finding.status for finding in findings}
        self.assertEqual(
            {
                "prop.mug.hand": "mismatch",
                "wardrobe.jacket.state": "mismatch",
                "set.practical_lamp.state": "needs_confirmation",
            },
            by_property,
        )

        persisted = self.memory.list_findings(
            production_id=PRODUCTION_ID,
            scene_id=SCENE_ID,
            take_id="S28-T47",
        )
        self.assertEqual(by_property, {finding.property_key: finding.status for finding in persisted})

    def test_stable_finding_identity_and_append_only_review_history(self) -> None:
        findings = self.service.analyze(
            production_id=PRODUCTION_ID,
            scene_id=SCENE_ID,
            take_id="S28-T47",
            observations=take_47_observations(),
        )
        mug = next(row for row in findings if row.property_key == "prop.mug.hand")
        expected_finding_id = stable_finding_id(mug)

        persisted_id = self.client.query(
            f"SELECT finding_id FROM {self.database}.continuity_findings "
            "WHERE production_id = {production_id:String} "
            "AND scene_id = {scene_id:String} "
            "AND current_take_id = {take_id:String} "
            "AND entity_id = {entity_id:String} "
            "AND property_key = {property_key:String}",
            parameters={
                "production_id": PRODUCTION_ID,
                "scene_id": SCENE_ID,
                "take_id": "S28-T47",
                "entity_id": "maya",
                "property_key": "prop.mug.hand",
            },
        ).result_set
        self.assertEqual([(expected_finding_id,)], persisted_id)

        first = self.review_service.review(
            production_id=PRODUCTION_ID,
            scene_id=SCENE_ID,
            take_id="S28-T47",
            entity_id="maya",
            property_key="prop.mug.hand",
            actor_id="script-supervisor-1",
            decision="needs_followup",
            note="Recheck insert shot before locking picture.",
        )
        second = self.review_service.review(
            production_id=PRODUCTION_ID,
            scene_id=SCENE_ID,
            take_id="S28-T47",
            entity_id="maya",
            property_key="prop.mug.hand",
            actor_id="script-supervisor-1",
            decision="confirmed",
            note="Confirmed against the approved master.",
        )

        self.assertEqual(expected_finding_id, first.finding_id)
        self.assertEqual(expected_finding_id, second.finding_id)
        self.assertNotEqual(first.decision_id, second.decision_id)

        history = self.review_service.history(
            production_id=PRODUCTION_ID,
            scene_id=SCENE_ID,
            take_id="S28-T47",
            entity_id="maya",
            property_key="prop.mug.hand",
        )
        self.assertEqual(["needs_followup", "confirmed"], [row.decision for row in history])
        self.assertEqual([first.decision_id, second.decision_id], [row.decision_id for row in history])

        count = self.client.query(
            f"SELECT count() FROM {self.database}.human_decisions "
            "WHERE production_id = {production_id:String} AND finding_id = {finding_id:String}",
            parameters={"production_id": PRODUCTION_ID, "finding_id": expected_finding_id},
        ).result_set
        self.assertEqual([(2,)], count)

    def test_extraction_reprocessing_preserves_independent_history(self) -> None:
        request = _extraction_request()
        first_result = _extraction_result(request, run_id="integration-run-1", value="left")
        second_result = _extraction_result(request, run_id="integration-run-2", value="right")

        first_run = self.extraction_store.append(request, first_result)
        second_run = self.extraction_store.append(request, second_result)

        self.assertEqual("integration-run-1", first_run.run_id)
        self.assertEqual("integration-run-2", second_run.run_id)

        runs = self.extraction_store.list_runs(
            production_id=PRODUCTION_ID,
            scene_id=SCENE_ID,
            take_id="S28-T47",
        )
        self.assertEqual({"integration-run-1", "integration-run-2"}, {row.run_id for row in runs})
        self.assertEqual(2, len(runs))

        first_history = self.extraction_store.list_observations(
            production_id=PRODUCTION_ID,
            run_id="integration-run-1",
        )
        second_history = self.extraction_store.list_observations(
            production_id=PRODUCTION_ID,
            run_id="integration-run-2",
        )
        self.assertEqual(["left"], [row.normalized_value for row in first_history])
        self.assertEqual(["right"], [row.normalized_value for row in second_history])
        self.assertNotEqual(first_history[0].observation_id, second_history[0].observation_id)

        counts = self.client.query(
            f"SELECT run_id, count() FROM {self.database}.extracted_observations "
            "WHERE production_id = {production_id:String} "
            "AND scene_id = {scene_id:String} AND take_id = {take_id:String} "
            "GROUP BY run_id ORDER BY run_id",
            parameters={
                "production_id": PRODUCTION_ID,
                "scene_id": SCENE_ID,
                "take_id": "S28-T47",
            },
        ).result_set
        self.assertEqual([("integration-run-1", 1), ("integration-run-2", 1)], counts)

        wrong_tenant = self.extraction_store.list_observations(
            production_id="other-production",
            run_id="integration-run-1",
        )
        self.assertEqual([], wrong_tenant)

    def test_reanalysis_removes_stale_findings(self) -> None:
        corrected = [
            Observation(PRODUCTION_ID, SCENE_ID, "S28-T47", "maya", "prop.mug.hand", "right", 0.97, 4200, 8200),
            Observation(PRODUCTION_ID, SCENE_ID, "S28-T47", "maya", "wardrobe.jacket.state", "zipped", 0.96, 1500, 9000),
            Observation(PRODUCTION_ID, SCENE_ID, "S28-T47", "set-lamp-a", "set.practical_lamp.state", "on", 0.95, 1200, 9000),
        ]
        findings = self.service.analyze(
            production_id=PRODUCTION_ID,
            scene_id=SCENE_ID,
            take_id="S28-T47",
            observations=corrected,
        )
        self.assertEqual([], findings)
        self.assertEqual(
            [],
            self.memory.list_findings(
                production_id=PRODUCTION_ID,
                scene_id=SCENE_ID,
                take_id="S28-T47",
            ),
        )


if __name__ == "__main__":
    unittest.main()
