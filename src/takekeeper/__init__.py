"""TakeKeeper production-memory core."""

from .clickhouse_memory import ClickHouseProductionMemory
from .continuity import compare_observations
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
from .service import TakeAnalysisService

__all__ = [
    "Baseline",
    "ClickHouseProductionMemory",
    "ClickHouseReviewDecisionStore",
    "ContinuityEvidenceRow",
    "EditorialHit",
    "Finding",
    "FindingReviewService",
    "InMemoryProductionMemory",
    "InMemoryReviewDecisionStore",
    "McpEvidenceReader",
    "McpQueryTrace",
    "McpReadError",
    "Observation",
    "ProductionMemory",
    "ReviewDecision",
    "ReviewDecisionStore",
    "ReviewHttpApp",
    "ReviewerIdentityProvider",
    "StaticBearerIdentityProvider",
    "TakeAnalysisService",
    "compare_observations",
    "stable_finding_id",
]
