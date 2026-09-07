from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .clickhouse_memory import ClickHouseClientLike


class ClickHouseSchemaNotReady(RuntimeError):
    """The trusted application ClickHouse schema is incompatible with this build."""


@dataclass(frozen=True, slots=True)
class ColumnRequirement:
    name: str
    accepted_types: frozenset[str]


@dataclass(frozen=True, slots=True)
class SchemaPreflightReport:
    ready: bool
    checked_tables: tuple[str, ...]
    missing_columns: tuple[str, ...]
    incompatible_columns: tuple[str, ...]

    def require_ready(self) -> None:
        if self.ready:
            return
        raise ClickHouseSchemaNotReady(
            "ClickHouse schema is not ready for extraction persistence. "
            "Apply sql/schema.sql for a fresh deployment or the pending sql/migrations/*.sql "
            "for an existing deployment, then rerun the schema preflight."
        )


# These requirements intentionally cover the application-write extraction boundary rather
# than every TakeKeeper table. The three nullable media fields are migration 002's contract.
_REQUIRED: Mapping[str, tuple[ColumnRequirement, ...]] = {
    "extraction_runs": (
        ColumnRequirement("production_id", frozenset({"String"})),
        ColumnRequirement("scene_id", frozenset({"String"})),
        ColumnRequirement("take_id", frozenset({"String"})),
        ColumnRequirement("run_id", frozenset({"String"})),
        ColumnRequirement("media_uri", frozenset({"String"})),
        ColumnRequirement("media_fingerprint", frozenset({"FixedString(64)"})),
        ColumnRequirement(
            "media_mime_type",
            frozenset({"LowCardinality(Nullable(String))", "Nullable(LowCardinality(String))"}),
        ),
        ColumnRequirement("media_content_sha256", frozenset({"Nullable(FixedString(64))"})),
        ColumnRequirement("media_byte_size", frozenset({"Nullable(UInt64)"})),
        ColumnRequirement("duration_ms", frozenset({"UInt64"})),
        ColumnRequirement("extractor_model", frozenset({"String"})),
        ColumnRequirement("extractor_version", frozenset({"String"})),
        ColumnRequirement("prompt_schema_version", frozenset({"String"})),
        ColumnRequirement("created_at", frozenset({"DateTime64(3, 'UTC')", "DateTime64(3,\'UTC\')"})),
    ),
    "extracted_observations": (
        ColumnRequirement("production_id", frozenset({"String"})),
        ColumnRequirement("scene_id", frozenset({"String"})),
        ColumnRequirement("take_id", frozenset({"String"})),
        ColumnRequirement("run_id", frozenset({"String"})),
        ColumnRequirement("observation_id", frozenset({"String"})),
        ColumnRequirement("entity_id", frozenset({"String"})),
        ColumnRequirement("property_key", frozenset({"LowCardinality(String)"})),
        ColumnRequirement("normalized_value", frozenset({"String"})),
        ColumnRequirement("raw_model_value", frozenset({"String"})),
        ColumnRequirement("confidence", frozenset({"Float32"})),
        ColumnRequirement("evidence_start_ms", frozenset({"UInt64"})),
        ColumnRequirement("evidence_end_ms", frozenset({"UInt64"})),
        ColumnRequirement("source_type", frozenset({"LowCardinality(String)"})),
        ColumnRequirement("visibility_state", frozenset({"LowCardinality(String)"})),
        ColumnRequirement("temporal_support", frozenset({"LowCardinality(String)"})),
        ColumnRequirement("disposition", frozenset({"LowCardinality(String)"})),
        ColumnRequirement("verification_state", frozenset({"LowCardinality(String)"})),
        ColumnRequirement("evidence_rationale_short", frozenset({"String"})),
        ColumnRequirement("created_at", frozenset({"DateTime64(3, 'UTC')", "DateTime64(3,\'UTC\')"})),
    ),
}


def _validate_database(database: str) -> str:
    if not database or not database.replace("_", "").isalnum():
        raise ValueError("database must contain only letters, digits, and underscores")
    return database


def check_extraction_schema(
    client: ClickHouseClientLike,
    *,
    database: str = "takekeeper",
) -> SchemaPreflightReport:
    """Bounded, read-only schema check for the trusted extraction persistence path.

    Only `system.columns` is queried. The database and table are bound parameters and each
    query is capped well above the expected column count, preventing readiness checks from
    becoming an unbounded metadata scan. No row data, media locator, hash, credential, or
    production identifier is read.
    """

    database = _validate_database(database)
    missing: list[str] = []
    incompatible: list[str] = []

    for table, requirements in _REQUIRED.items():
        result = client.query(
            "SELECT name, type FROM system.columns "
            "WHERE database = {database:String} AND table = {table:String} "
            "ORDER BY position",
            parameters={"database": database, "table": table},
            settings={"max_result_rows": 64, "result_overflow_mode": "throw"},
        )
        rows = list(result.result_set)
        observed: dict[str, str] = {}
        for row in rows:
            if len(row) < 2:
                continue
            observed[str(row[0])] = str(row[1])

        for requirement in requirements:
            actual = observed.get(requirement.name)
            qualified = f"{table}.{requirement.name}"
            if actual is None:
                missing.append(qualified)
            elif actual not in requirement.accepted_types:
                incompatible.append(qualified)

    report = SchemaPreflightReport(
        ready=not missing and not incompatible,
        checked_tables=tuple(_REQUIRED),
        missing_columns=tuple(sorted(missing)),
        incompatible_columns=tuple(sorted(incompatible)),
    )
    return report


def require_extraction_schema_ready(
    client: ClickHouseClientLike,
    *,
    database: str = "takekeeper",
) -> SchemaPreflightReport:
    """Fail closed before ingestion when application/schema rollout versions drift."""

    report = check_extraction_schema(client, database=database)
    report.require_ready()
    return report
