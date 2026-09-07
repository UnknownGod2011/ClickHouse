from __future__ import annotations

import unittest
from types import SimpleNamespace

from takekeeper import schema_preflight
from takekeeper.production_ingest import (
    ProductionIngestConfig,
    ProductionIngestConfigurationError,
    ProductionIngestStartupError,
    build_ingest_deployment_from_env,
)


class _SchemaClient:
    def __init__(self, *, ready: bool = True) -> None:
        self.ready = ready
        self.queries = []

    def query(self, sql, *, parameters=None, settings=None):
        self.queries.append((sql, parameters, settings))
        table = parameters["table"]
        requirements = schema_preflight._REQUIRED[table]
        rows = [(item.name, next(iter(item.accepted_types))) for item in requirements]
        if not self.ready and table == "extraction_runs":
            rows = [row for row in rows if row[0] != "media_content_sha256"]
        return SimpleNamespace(result_set=rows)

    def insert(self, *args, **kwargs):
        raise AssertionError("composition/schema preflight must never insert")


class ProductionIngestCompositionTests(unittest.TestCase):
    def vertex_env(self):
        return {
            "TAKEKEEPER_CLICKHOUSE_HOST": "example.clickhouse.cloud",
            "TAKEKEEPER_CLICKHOUSE_PORT": "8443",
            "TAKEKEEPER_CLICKHOUSE_USERNAME": "takekeeper_ingest",
            "TAKEKEEPER_CLICKHOUSE_PASSWORD": "clickhouse-password-secret",
            "TAKEKEEPER_CLICKHOUSE_DATABASE": "takekeeper",
            "TAKEKEEPER_CLICKHOUSE_SECURE": "true",
            "TAKEKEEPER_GEMINI_MODE": "vertex",
            "TAKEKEEPER_GEMINI_MODEL": "gemini-model-configured-by-operator",
            "TAKEKEEPER_GOOGLE_CLOUD_PROJECT": "takekeeper-prod",
            "TAKEKEEPER_GOOGLE_CLOUD_LOCATION": "us-central1",
            "TAKEKEEPER_EXTRACTOR_VERSION": "deploy-2026-09-07",
            "TAKEKEEPER_INGEST_BEARER_TOKEN": "b" * 48,
            "TAKEKEEPER_INGEST_ACTOR_ID": "production-ingest",
        }

    def _google_identity_env(self, mode: str, audience: str):
        env = self.vertex_env()
        env["TAKEKEEPER_INGEST_IDENTITY_MODE"] = mode
        env["TAKEKEEPER_INGEST_EXPECTED_AUDIENCE"] = audience
        env["TAKEKEEPER_INGEST_SUBJECT_MAP"] = '{"verified-subject":"production-ingest"}'
        env.pop("TAKEKEEPER_INGEST_BEARER_TOKEN")
        env.pop("TAKEKEEPER_INGEST_ACTOR_ID")
        return env

    def test_vertex_composition_opens_only_after_schema_preflight(self):
        env = self.vertex_env()
        client = _SchemaClient()
        clickhouse_kwargs = {}
        genai_kwargs = {}

        def clickhouse_factory(**kwargs):
            clickhouse_kwargs.update(kwargs)
            return client

        def genai_factory(**kwargs):
            genai_kwargs.update(kwargs)
            return SimpleNamespace(models=object())

        deployment = build_ingest_deployment_from_env(
            env,
            clickhouse_client_factory=clickhouse_factory,
            genai_client_factory=genai_factory,
        )

        self.assertTrue(deployment.service.readiness().ready)
        self.assertTrue(deployment.service.readiness().schema_checked)
        self.assertEqual(len(client.queries), 2)
        self.assertEqual(clickhouse_kwargs["host"], "example.clickhouse.cloud")
        self.assertEqual(clickhouse_kwargs["password"], "clickhouse-password-secret")
        self.assertTrue(clickhouse_kwargs["secure"])
        self.assertTrue(genai_kwargs["vertex_ai"])
        self.assertIsNone(genai_kwargs["api_key"])
        self.assertEqual(genai_kwargs["project"], "takekeeper-prod")
        self.assertEqual(deployment.app._credential_environ_key, "HTTP_AUTHORIZATION")

    def test_iap_mode_uses_only_signed_iap_assertion_header(self):
        env = self._google_identity_env(
            "iap",
            "/projects/123/global/backendServices/456",
        )
        deployment = build_ingest_deployment_from_env(
            env,
            clickhouse_client_factory=lambda **_: _SchemaClient(),
            genai_client_factory=lambda **_: SimpleNamespace(models=object()),
        )
        self.assertEqual(
            deployment.app._credential_environ_key,
            "HTTP_X_GOOG_IAP_JWT_ASSERTION",
        )

    def test_google_oidc_mode_keeps_authorization_header(self):
        env = self._google_identity_env(
            "google_oidc",
            "https://takekeeper.example.run.app",
        )
        deployment = build_ingest_deployment_from_env(
            env,
            clickhouse_client_factory=lambda **_: _SchemaClient(),
            genai_client_factory=lambda **_: SimpleNamespace(models=object()),
        )
        self.assertEqual(deployment.app._credential_environ_key, "HTTP_AUTHORIZATION")

    def test_schema_drift_fails_startup_closed(self):
        env = self.vertex_env()
        client = _SchemaClient(ready=False)
        with self.assertRaises(ProductionIngestStartupError) as caught:
            build_ingest_deployment_from_env(
                env,
                clickhouse_client_factory=lambda **_: client,
                genai_client_factory=lambda **_: SimpleNamespace(models=object()),
            )
        self.assertEqual(
            str(caught.exception),
            "TakeKeeper production ingestion could not start safely.",
        )

    def test_missing_configuration_fails_before_factories(self):
        env = self.vertex_env()
        del env["TAKEKEEPER_CLICKHOUSE_PASSWORD"]
        called = []
        with self.assertRaises(ProductionIngestConfigurationError) as caught:
            build_ingest_deployment_from_env(
                env,
                clickhouse_client_factory=lambda **_: called.append("clickhouse"),
                genai_client_factory=lambda **_: called.append("genai"),
            )
        self.assertEqual(called, [])
        self.assertIn("TAKEKEEPER_CLICKHOUSE_PASSWORD", str(caught.exception))

    def test_config_repr_redacts_all_secret_values(self):
        env = self.vertex_env()
        env["TAKEKEEPER_GEMINI_MODE"] = "developer"
        env["TAKEKEEPER_GEMINI_API_KEY"] = "gemini-api-key-secret"
        env.pop("TAKEKEEPER_GOOGLE_CLOUD_PROJECT")
        env.pop("TAKEKEEPER_GOOGLE_CLOUD_LOCATION")
        config = ProductionIngestConfig.from_environ(env)
        rendered = repr(config)
        self.assertNotIn("clickhouse-password-secret", rendered)
        self.assertNotIn("gemini-api-key-secret", rendered)
        self.assertNotIn("b" * 48, rendered)
        self.assertIn("gemini_mode='developer'", rendered)

    def test_provider_failure_message_cannot_escape_secret_values(self):
        env = self.vertex_env()
        leaked = "clickhouse-password-secret"

        def broken_factory(**_kwargs):
            raise RuntimeError(f"provider failed with {leaked}")

        with self.assertRaises(ProductionIngestStartupError) as caught:
            build_ingest_deployment_from_env(
                env,
                clickhouse_client_factory=broken_factory,
                genai_client_factory=lambda **_: SimpleNamespace(models=object()),
            )
        self.assertNotIn(leaked, str(caught.exception))

    def test_developer_mode_cannot_mix_vertex_configuration(self):
        env = self.vertex_env()
        env["TAKEKEEPER_GEMINI_MODE"] = "developer"
        env["TAKEKEEPER_GEMINI_API_KEY"] = "developer-key"
        with self.assertRaises(ProductionIngestConfigurationError):
            ProductionIngestConfig.from_environ(env)

    def test_short_bearer_token_is_rejected_without_echo(self):
        env = self.vertex_env()
        env["TAKEKEEPER_INGEST_BEARER_TOKEN"] = "too-short-secret"
        with self.assertRaises(ProductionIngestConfigurationError) as caught:
            ProductionIngestConfig.from_environ(env)
        self.assertNotIn("too-short-secret", str(caught.exception))
        self.assertIn("TAKEKEEPER_INGEST_BEARER_TOKEN", str(caught.exception))

    def test_google_identity_requires_audience_and_rejects_static_secret(self):
        env = self.vertex_env()
        env["TAKEKEEPER_INGEST_IDENTITY_MODE"] = "google_oidc"
        env.pop("TAKEKEEPER_INGEST_ACTOR_ID")
        with self.assertRaises(ProductionIngestConfigurationError) as missing:
            ProductionIngestConfig.from_environ(env)
        self.assertIn("TAKEKEEPER_INGEST_EXPECTED_AUDIENCE", str(missing.exception))

        env["TAKEKEEPER_INGEST_EXPECTED_AUDIENCE"] = "https://takekeeper.example.run.app"
        env["TAKEKEEPER_INGEST_SUBJECT_MAP"] = '{"verified-subject":"production-ingest"}'
        with self.assertRaises(ProductionIngestConfigurationError) as mixed:
            ProductionIngestConfig.from_environ(env)
        self.assertIn("TAKEKEEPER_INGEST_BEARER_TOKEN", str(mixed.exception))

    def test_static_identity_rejects_google_audience_configuration(self):
        env = self.vertex_env()
        env["TAKEKEEPER_INGEST_EXPECTED_AUDIENCE"] = "https://takekeeper.example.run.app"
        with self.assertRaises(ProductionIngestConfigurationError) as caught:
            ProductionIngestConfig.from_environ(env)
        self.assertIn("TAKEKEEPER_INGEST_EXPECTED_AUDIENCE", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
