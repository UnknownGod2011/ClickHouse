from __future__ import annotations

import os
import unittest
from pathlib import Path
from uuid import uuid4

from takekeeper.clickhouse_memory import ClickHouseProductionMemory
from takekeeper.fixtures import PRODUCTION_ID, SCENE_ID, scene_28_baselines, take_47_observations
from takekeeper.models import Observation
from takekeeper.queries import EditorialConstraints, editorial_retrieval_sql
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

        seed = (REPO_ROOT / "sql" / "seed_demo.sql").read_text(encoding="utf-8")
        seed = seed.replace("takekeeper.", f"{cls.database}.")
        _execute_sql_script(cls.client, seed)

        cls.memory = ClickHouseProductionMemory(cls.client, database=cls.database)
        cls.service = TakeAnalysisService(cls.memory)

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
