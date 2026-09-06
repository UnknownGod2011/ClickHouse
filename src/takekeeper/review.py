from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Protocol
from uuid import NAMESPACE_URL, uuid4, uuid5

from .memory import ProductionMemory
from .models import Finding

ReviewOutcome = Literal["confirmed", "rejected", "needs_followup"]


def stable_finding_id(finding: Finding) -> str:
    """Return a deterministic identity for one logical finding across re-analysis."""
    identity = "\x1f".join(
        (
            "takekeeper:finding:v1",
            finding.production_id,
            finding.scene_id,
            finding.take_id,
            finding.entity_id,
            finding.property_key,
        )
    )
    return str(uuid5(NAMESPACE_URL, identity))


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    production_id: str
    scene_id: str
    take_id: str
    entity_id: str
    property_key: str
    finding_id: str
    actor_id: str
    decision: ReviewOutcome
    note: str = ""
    decision_id: str = ""
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.actor_id.strip():
            raise ValueError("actor_id must not be empty")
        if self.decision not in ("confirmed", "rejected", "needs_followup"):
            raise ValueError("invalid review decision")


class ReviewDecisionStore(Protocol):
    def append(self, decision: ReviewDecision) -> ReviewDecision: ...
    def list_for_finding(
        self,
        *,
        production_id: str,
        scene_id: str,
        take_id: str,
        entity_id: str,
        property_key: str,
        finding_id: str,
    ) -> list[ReviewDecision]: ...


class InMemoryReviewDecisionStore:
    def __init__(self) -> None:
        self._rows: list[ReviewDecision] = []

    def append(self, decision: ReviewDecision) -> ReviewDecision:
        persisted = ReviewDecision(
            production_id=decision.production_id,
            scene_id=decision.scene_id,
            take_id=decision.take_id,
            entity_id=decision.entity_id,
            property_key=decision.property_key,
            finding_id=decision.finding_id,
            actor_id=decision.actor_id,
            decision=decision.decision,
            note=decision.note,
            decision_id=decision.decision_id or str(uuid4()),
            created_at=decision.created_at or datetime.now(timezone.utc),
        )
        self._rows.append(persisted)
        return persisted

    def list_for_finding(
        self,
        *,
        production_id: str,
        scene_id: str,
        take_id: str,
        entity_id: str,
        property_key: str,
        finding_id: str,
    ) -> list[ReviewDecision]:
        return [
            row
            for row in self._rows
            if row.production_id == production_id and row.finding_id == finding_id
        ]


class ClickHouseReviewDecisionStore:
    """Append-only human review history on the trusted application connection."""

    def __init__(self, client, *, database: str = "takekeeper") -> None:
        if not database.replace("_", "").isalnum():
            raise ValueError("database must contain only letters, digits, and underscores")
        self._client = client
        self._database = database

    @property
    def _table(self) -> str:
        return f"{self._database}.human_decisions"

    def append(self, decision: ReviewDecision) -> ReviewDecision:
        decision_id = decision.decision_id or str(uuid4())
        created_at = decision.created_at or datetime.now(timezone.utc)
        persisted = ReviewDecision(
            production_id=decision.production_id,
            scene_id=decision.scene_id,
            take_id=decision.take_id,
            entity_id=decision.entity_id,
            property_key=decision.property_key,
            finding_id=decision.finding_id,
            actor_id=decision.actor_id,
            decision=decision.decision,
            note=decision.note,
            decision_id=decision_id,
            created_at=created_at,
        )
        self._client.insert(
            self._table,
            [[
                persisted.production_id,
                persisted.decision_id,
                persisted.finding_id,
                persisted.actor_id,
                persisted.decision,
                persisted.note,
                persisted.created_at,
            ]],
            column_names=[
                "production_id",
                "decision_id",
                "finding_id",
                "actor_id",
                "decision",
                "note",
                "created_at",
            ],
        )
        return persisted

    def list_for_finding(
        self,
        *,
        production_id: str,
        scene_id: str,
        take_id: str,
        entity_id: str,
        property_key: str,
        finding_id: str,
    ) -> list[ReviewDecision]:
        result = self._client.query(
            f"SELECT decision_id, actor_id, decision, note, created_at "
            f"FROM {self._table} "
            "WHERE production_id = {production_id:String} AND finding_id = {finding_id:String} "
            "ORDER BY created_at, decision_id",
            parameters={"production_id": production_id, "finding_id": finding_id},
        )
        return [
            ReviewDecision(
                production_id=production_id,
                scene_id=scene_id,
                take_id=take_id,
                entity_id=entity_id,
                property_key=property_key,
                finding_id=finding_id,
                decision_id=str(row[0]),
                actor_id=str(row[1]),
                decision=str(row[2]),
                note=str(row[3]),
                created_at=row[4],
            )
            for row in result.result_set
        ]


class FindingReviewService:
    """Record decisions only for findings currently present in the requested scope."""

    def __init__(self, memory: ProductionMemory, decisions: ReviewDecisionStore) -> None:
        self._memory = memory
        self._decisions = decisions

    def _find(
        self,
        *,
        production_id: str,
        scene_id: str,
        take_id: str,
        entity_id: str,
        property_key: str,
    ) -> Finding:
        findings = self._memory.list_findings(
            production_id=production_id,
            scene_id=scene_id,
            take_id=take_id,
        )
        target = next(
            (
                row
                for row in findings
                if row.entity_id == entity_id and row.property_key == property_key
            ),
            None,
        )
        if target is None:
            raise LookupError("finding not present in requested production/scene/take scope")
        return target

    def review(
        self,
        *,
        production_id: str,
        scene_id: str,
        take_id: str,
        entity_id: str,
        property_key: str,
        actor_id: str,
        decision: ReviewOutcome,
        note: str = "",
    ) -> ReviewDecision:
        target = self._find(
            production_id=production_id,
            scene_id=scene_id,
            take_id=take_id,
            entity_id=entity_id,
            property_key=property_key,
        )
        return self._decisions.append(
            ReviewDecision(
                production_id=production_id,
                scene_id=scene_id,
                take_id=take_id,
                entity_id=entity_id,
                property_key=property_key,
                finding_id=stable_finding_id(target),
                actor_id=actor_id,
                decision=decision,
                note=note,
            )
        )

    def history(
        self,
        *,
        production_id: str,
        scene_id: str,
        take_id: str,
        entity_id: str,
        property_key: str,
    ) -> list[ReviewDecision]:
        target = self._find(
            production_id=production_id,
            scene_id=scene_id,
            take_id=take_id,
            entity_id=entity_id,
            property_key=property_key,
        )
        return self._decisions.list_for_finding(
            production_id=production_id,
            scene_id=scene_id,
            take_id=take_id,
            entity_id=entity_id,
            property_key=property_key,
            finding_id=stable_finding_id(target),
        )
