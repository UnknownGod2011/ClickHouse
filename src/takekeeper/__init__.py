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
    "ClickHouseProductionMemory",
    "ClickHouseReviewDecisionStore",
    "ContinuityEvidenceRow",
    "EditorialHit",
    "ExtractedObservation",
    "ExtractionError",
    "ExtractionEvaluation",
    "ExtractionPrompt",
    "ExtractionRunResult",
    "ExtractionSchemaError",
    "ExtractionTransportError",
    "Finding",
    "FindingReviewService",
    "FixtureExtractionTransport",
    "GovernedMultimodalExtractor",
    "HERO_PROPERTY_REGISTRY",
    "InMemoryProductionMemory",
    "InMemoryReviewDecisionStore",
    "McpEvidenceReader",
    "McpQueryTrace",
    "McpReadError",
    "Observation",
    "ProductionMemory",
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
    "compare_observations",
    "evaluate_extraction",
    "stable_finding_id",
]
