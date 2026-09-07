from __future__ import annotations

import json
import unittest

from takekeeper.production_ingest import (
    ProductionIngestConfig,
    ProductionIngestConfigurationError,
)


class ProductionSubjectAuthorizationTests(unittest.TestCase):
    def base_env(self):
        return {
            "TAKEKEEPER_CLICKHOUSE_HOST": "example.clickhouse.cloud",
            "TAKEKEEPER_CLICKHOUSE_USERNAME": "takekeeper_ingest",
            "TAKEKEEPER_CLICKHOUSE_PASSWORD": "clickhouse-password-secret",
            "TAKEKEEPER_GEMINI_MODE": "vertex",
            "TAKEKEEPER_GEMINI_MODEL": "gemini-model",
            "TAKEKEEPER_GOOGLE_CLOUD_PROJECT": "takekeeper-prod",
            "TAKEKEEPER_GOOGLE_CLOUD_LOCATION": "us-central1",
            "TAKEKEEPER_EXTRACTOR_VERSION": "deploy-1",
            "TAKEKEEPER_INGEST_IDENTITY_MODE": "google_oidc",
            "TAKEKEEPER_INGEST_EXPECTED_AUDIENCE": "https://takekeeper.example.run.app",
        }

    def test_google_mode_requires_explicit_subject_map(self):
        with self.assertRaises(ProductionIngestConfigurationError) as ctx:
            ProductionIngestConfig.from_environ(self.base_env())
        self.assertEqual(
            str(ctx.exception),
            "missing or invalid TAKEKEEPER_INGEST_SUBJECT_MAP",
        )

    def test_subject_map_parses_to_bounded_deployment_actor_mapping(self):
        env = self.base_env()
        env["TAKEKEEPER_INGEST_SUBJECT_MAP"] = json.dumps(
            {"google-subject-123": "production-ingest-worker"}
        )
        config = ProductionIngestConfig.from_environ(env)
        self.assertEqual(
            config.ingest_subject_map,
            {"google-subject-123": "production-ingest-worker"},
        )

    def test_subject_map_is_redacted_from_config_repr(self):
        env = self.base_env()
        env["TAKEKEEPER_INGEST_SUBJECT_MAP"] = json.dumps(
            {"sensitive-subject": "sensitive-actor"}
        )
        rendered = repr(ProductionIngestConfig.from_environ(env))
        self.assertNotIn("sensitive-subject", rendered)
        self.assertNotIn("sensitive-actor", rendered)

    def test_static_mode_rejects_subject_map(self):
        env = self.base_env()
        env["TAKEKEEPER_INGEST_IDENTITY_MODE"] = "static"
        env.pop("TAKEKEEPER_INGEST_EXPECTED_AUDIENCE")
        env["TAKEKEEPER_INGEST_BEARER_TOKEN"] = "b" * 48
        env["TAKEKEEPER_INGEST_SUBJECT_MAP"] = '{"subject":"actor"}'
        with self.assertRaises(ProductionIngestConfigurationError) as ctx:
            ProductionIngestConfig.from_environ(env)
        self.assertIn("TAKEKEEPER_INGEST_SUBJECT_MAP", str(ctx.exception))

    def test_invalid_json_does_not_echo_policy_contents(self):
        env = self.base_env()
        secretish = "subject-that-should-not-escape"
        env["TAKEKEEPER_INGEST_SUBJECT_MAP"] = "{" + secretish
        with self.assertRaises(ProductionIngestConfigurationError) as ctx:
            ProductionIngestConfig.from_environ(env)
        self.assertNotIn(secretish, str(ctx.exception))

    def test_iap_mode_uses_same_explicit_authorization_contract(self):
        env = self.base_env()
        env["TAKEKEEPER_INGEST_IDENTITY_MODE"] = "iap"
        env["TAKEKEEPER_INGEST_EXPECTED_AUDIENCE"] = "/projects/123/global/backendServices/456"
        env["TAKEKEEPER_INGEST_SUBJECT_MAP"] = '{"iap-subject":"script-supervisor"}'
        config = ProductionIngestConfig.from_environ(env)
        self.assertEqual(config.ingest_subject_map, {"iap-subject": "script-supervisor"})


if __name__ == "__main__":
    unittest.main()
