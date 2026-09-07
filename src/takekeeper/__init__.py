"""TakeKeeper production-memory core."""

from .clickhouse_memory import ClickHouseProductionMemory
from .continuity import compare_observations
from .extraction import (
    HERO_PROPERTY_REGISTRY,
    ExtractedObservation,
    ExtractionError,
    ExtractionPrompt,
    ExtractionRunResult,
    ExtractionSchemaError,
    ExtractionTransportError,
    FixtureExtractionTransport,
    GovernedMultimodalExtractor,
    PropertySpec,
    TakeExtractionRequest,
    build_extraction_prompt,
)
from .extraction_eval import ExtractionEvaluation, TruthObservation, evaluate_extraction
from .extraction_projection import (
    ContinuityProjection,
    ExtractionProjectionError,
    ProjectionDecision,
    compare_extraction_to_baselines,
    project_extraction_for_continuity,
)
from .extraction_store import (
    ClickHouseExtractionProvenanceStore,
    ExtractedObservationRecord,
    ExtractionPersistenceError,
    ExtractionProvenanceStore,
    ExtractionRunRecord,
    InMemoryExtractionProvenanceStore,
    media_fingerprint,
    observation_record_id,
)
from .google_genai_transport import (
    GoogleGenAIExtractionTransport,
    GoogleGenAITransportConfig,
    GoogleGenAITransportError,
    create_google_genai_client,
)
from .mcp_reader import (
    ContinuityEvidenceRow,
    EditorialHit,
    McpEvidenceReader,
    McpQueryTrace,
    McpReadError,
)
from .memory import InMemoryProductionMemory, ProductionMemory
from .models import Baseline, Finding, Observation
from .review import (
    ClickHouseReviewDecisionStore,
    FindingReviewService,
    InMemoryReviewDecisionStore,
    ReviewDecision,
    ReviewDecisionStore,
    stable_finding_id,
)
from .review_api import ReviewHttpApp, ReviewerIdentityProvider, StaticBearerIdentityProvider
from .review_console import ReviewConsoleApp
from .service import TakeAnalysisService

__all__ = [
    "Baseline",
    "ClickHouseExtractionProvenanceStore",
    "ClickHouseProductionMemory",
    "ClickHouseReviewDecisionStore",
    "ContinuityEvidenceRow",
    "ContinuityProjection",
    "EditorialHit",
    "ExtractedObservation",
    "ExtractedObservationRecord",
    "ExtractionError",
    "ExtractionEvaluation",
    "ExtractionPersistenceError",
    "ExtractionProjectionError",
    "ExtractionPrompt",
    "ExtractionProvenanceStore",
    "ExtractionRunRecord",
    "ExtractionRunResult",
    "ExtractionSchemaError",
    "ExtractionTransportError",
    "Finding",
    "FindingReviewService",
    "FixtureExtractionTransport",
    "GoogleGenAIExtractionTransport",
    "GoogleGenAITransportConfig",
    "GoogleGenAITransportError",
    "GovernedMultimodalExtractor",
    "HERO_PROPERTY_REGISTRY",
    "InMemoryExtractionProvenanceStore",
    "InMemoryProductionMemory",
    "InMemoryReviewDecisionStore",
    "McpEvidenceReader",
    "McpQueryTrace",
    "McpReadError",
    "Observation",
    "ProductionMemory",
    "ProjectionDecision",
    "PropertySpec",
    "ReviewConsoleApp",
    "ReviewDecision",
    "ReviewDecisionStore",
    "ReviewHttpApp",
    "ReviewerIdentityProvider",
    "StaticBearerIdentityProvider",
    "TakeAnalysisService",
    "TakeExtractionRequest",
    "TruthObservation",
    "build_extraction_prompt",
    "compare_extraction_to_baselines",
    "compare_observations",
    "create_google_genai_client",
    "evaluate_extraction",
    "media_fingerprint",
    "observation_record_id",
    "project_extraction_for_continuity",
    "stable_finding_id",
]
