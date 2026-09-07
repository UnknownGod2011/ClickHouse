from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from .clickhouse_memory import ClickHouseClientLike
from .extraction import ExtractionRunResult, TakeExtractionRequest
from .extraction_store import ExtractionProvenanceStore, ExtractionRunRecord
from .schema_preflight import ClickHouseSchemaNotReady, SchemaPreflightReport, require_extraction_schema_ready

ReadinessState = Literal["ready", "not_ready"]


class IngestNotReady(RuntimeError):
    """The production ingestion boundary is closed."""


class IngestBootstrapError(RuntimeError):
    """TakeKeeper could not safely open the production ingestion boundary."""


@dataclass(frozen=True, slots=True)
class IngestReadiness:
    state: ReadinessState
    schema_checked: bool

    @property
    def ready(self) -> bool:
        return self.state == "ready"


@dataclass(frozen=True, slots=True)
class IngestedTake:
    result: ExtractionRunResult
    persisted_run: ExtractionRunRecord


class ExtractorLike(Protocol):
    def extract(self, request: TakeExtractionRequest) -> ExtractionRunResult: ...


class SchemaGatedIngestService:
    """Canonical trusted ingestion boundary for production extraction.

    The service starts closed. ``start`` performs the bounded ClickHouse extraction-schema
    preflight with the same trusted application client used by persistence. Only after that
    check succeeds can ``ingest`` invoke the multimodal extractor and append provenance.

    A repeated ``start`` is intentionally a recheck: readiness is revoked before querying,
    so a failed post-deploy verification cannot leave a previously-ready process accepting
    takes. Readiness is deliberately coarse and contains no database, schema-diff, provider,
    media, tenant, or credential details.
    """

    def __init__(
        self,
        *,
        clickhouse_client: ClickHouseClientLike,
        extractor: ExtractorLike,
        provenance_store: ExtractionProvenanceStore,
        database: str = "takekeeper",
    ) -> None:
        self._clickhouse_client = clickhouse_client
        self._extractor = extractor
        self._provenance_store = provenance_store
        self._database = database
        self._ready = False
        self._schema_checked = False

    def readiness(self) -> IngestReadiness:
        return IngestReadiness(
            state="ready" if self._ready else "not_ready",
            schema_checked=self._schema_checked,
        )

    def start(self) -> SchemaPreflightReport:
        """Open ingestion only after the trusted ClickHouse schema passes preflight."""

        self._ready = False
        self._schema_checked = False
        try:
            report = require_extraction_schema_ready(
                self._clickhouse_client,
                database=self._database,
            )
        except ClickHouseSchemaNotReady:
            self._schema_checked = True
            raise
        except Exception as exc:
            raise IngestBootstrapError(
                "TakeKeeper ingestion is not ready because the ClickHouse schema preflight could not complete."
            ) from exc

        self._schema_checked = True
        self._ready = True
        return report

    def close(self) -> None:
        """Fail closed without touching ClickHouse or persisted extraction history."""

        self._ready = False

    def ingest(self, request: TakeExtractionRequest) -> IngestedTake:
        """Extract and append one trusted take only while the runtime is ready."""

        if not self._ready:
            raise IngestNotReady(
                "TakeKeeper ingestion is not ready. Complete the trusted ClickHouse schema preflight first."
            )

        result = self._extractor.extract(request)
        persisted = self._provenance_store.append(request, result)
        return IngestedTake(result=result, persisted_run=persisted)
