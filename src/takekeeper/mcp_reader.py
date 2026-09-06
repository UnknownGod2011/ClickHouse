from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Mapping, Sequence

from .queries import EditorialConstraints, continuity_evidence_sql, editorial_retrieval_sql


class McpReadError(RuntimeError):
    """Raised when the read-only MCP evidence path cannot return trustworthy rows."""


@dataclass(frozen=True, slots=True)
class McpQueryTrace:
    query: str
    latency_ms: float
    row_count: int


@dataclass(frozen=True, slots=True)
class ContinuityEvidenceRow:
    production_id: str
    scene_id: str
    take_id: str
    entity_id: str
    property_key: str
    observed_value: str
    confidence: float
    evidence_start_ms: int
    evidence_end_ms: int
    baseline_value: str | None
    baseline_source_take_id: str | None


@dataclass(frozen=True, slots=True)
class EditorialHit:
    production_id: str
    scene_id: str
    take_id: str
    take_number: int
    director_rating: int
    dialogue_evidence_ms: int | None
    eyeline_evidence_ms: int | None


ToolCaller = Callable[[str, Mapping[str, Any]], Any]


def _decode_json_text(value: str) -> Any:
    decoded: Any = value
    for _ in range(3):
        if not isinstance(decoded, str):
            return decoded
        text = decoded.strip()
        if not text:
            return []
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise McpReadError("run_query returned non-JSON text") from exc
    return decoded


def _text_from_content(content: Any) -> str | None:
    if not isinstance(content, Sequence) or isinstance(content, (str, bytes, bytearray)):
        return None

    chunks: list[str] = []
    for item in content:
        if isinstance(item, Mapping):
            item_type = item.get("type")
            text = item.get("text")
        else:
            item_type = getattr(item, "type", None)
            text = getattr(item, "text", None)
        if item_type == "text" and isinstance(text, str):
            chunks.append(text)
    return "\n".join(chunks) if chunks else None


def _unwrap_payload(payload: Any) -> list[Mapping[str, Any]]:
    structured = getattr(payload, "structuredContent", None)
    if structured is None:
        structured = getattr(payload, "structured_content", None)
    if structured is not None:
        payload = structured

    if isinstance(payload, Mapping):
        if payload.get("isError") is True or payload.get("is_error") is True:
            raise McpReadError("run_query returned an MCP tool error")
        if "structuredContent" in payload:
            payload = payload["structuredContent"]
        elif "structured_content" in payload:
            payload = payload["structured_content"]
        elif "content" in payload:
            text = _text_from_content(payload["content"])
            if text is not None:
                payload = text
    else:
        is_error = getattr(payload, "isError", None)
        if is_error is None:
            is_error = getattr(payload, "is_error", None)
        if is_error is True:
            raise McpReadError("run_query returned an MCP tool error")
        text = _text_from_content(getattr(payload, "content", None))
        if text is not None:
            payload = text

    if isinstance(payload, str):
        payload = _decode_json_text(payload)

    if isinstance(payload, Mapping):
        # Official mcp-clickhouse currently returns JSON text for run_query. These
        # aliases tolerate a future structured wrapper without weakening row checks.
        if isinstance(payload.get("data"), list):
            payload = payload["data"]
        elif isinstance(payload.get("rows"), list):
            payload = payload["rows"]
        elif isinstance(payload.get("result"), list):
            payload = payload["result"]

    if not isinstance(payload, list):
        raise McpReadError("run_query payload was not a row list")
    if not all(isinstance(row, Mapping) for row in payload):
        raise McpReadError("run_query payload contained a non-object row")
    return payload


def _required_str(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None:
        raise McpReadError(f"run_query row is missing {key}")
    return str(value)


def _required_int(row: Mapping[str, Any], key: str) -> int:
    value = row.get(key)
    if isinstance(value, bool) or value is None:
        raise McpReadError(f"run_query row has invalid {key}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise McpReadError(f"run_query row has invalid {key}") from exc


def _optional_int(row: Mapping[str, Any], key: str) -> int | None:
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        raise McpReadError(f"run_query row has invalid {key}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise McpReadError(f"run_query row has invalid {key}") from exc


def _required_float(row: Mapping[str, Any], key: str) -> float:
    value = row.get(key)
    if isinstance(value, bool) or value is None:
        raise McpReadError(f"run_query row has invalid {key}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise McpReadError(f"run_query row has invalid {key}") from exc


def _optional_str(row: Mapping[str, Any], key: str) -> str | None:
    value = row.get(key)
    return None if value is None else str(value)


class McpEvidenceReader:
    """Bounded analytical adapter for the official ClickHouse MCP ``run_query`` tool.

    A transport-specific ``call_tool(name, arguments)`` function is injected by the
    host. This class never accepts arbitrary SQL from an agent; it only emits the
    checked, tenant-scoped TakeKeeper query builders.
    """

    def __init__(
        self,
        call_tool: ToolCaller,
        *,
        database: str = "takekeeper",
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._call_tool = call_tool
        self._database = database
        self._clock = clock
        self.traces: list[McpQueryTrace] = []

    def _run_query(self, query: str) -> list[Mapping[str, Any]]:
        started = self._clock()
        try:
            raw = self._call_tool("run_query", {"query": query})
            rows = _unwrap_payload(raw)
        except McpReadError:
            raise
        except Exception as exc:
            raise McpReadError("run_query transport failed") from exc
        elapsed_ms = max(0.0, (self._clock() - started) * 1000.0)
        self.traces.append(McpQueryTrace(query=query, latency_ms=elapsed_ms, row_count=len(rows)))
        return rows

    @staticmethod
    def _assert_scope(
        row: Mapping[str, Any],
        *,
        production_id: str,
        scene_id: str,
        take_id: str | None = None,
    ) -> None:
        if _required_str(row, "production_id") != production_id:
            raise McpReadError("run_query returned a row from the wrong production")
        if _required_str(row, "scene_id") != scene_id:
            raise McpReadError("run_query returned a row from the wrong scene")
        if take_id is not None and _required_str(row, "take_id") != take_id:
            raise McpReadError("run_query returned a row from the wrong take")

    def continuity_evidence(
        self,
        *,
        production_id: str,
        scene_id: str,
        take_id: str,
    ) -> tuple[ContinuityEvidenceRow, ...]:
        query = continuity_evidence_sql(
            production_id,
            scene_id,
            take_id,
            database=self._database,
        )
        rows = self._run_query(query)
        result: list[ContinuityEvidenceRow] = []
        for row in rows:
            self._assert_scope(
                row,
                production_id=production_id,
                scene_id=scene_id,
                take_id=take_id,
            )
            confidence = _required_float(row, "confidence")
            if not 0.0 <= confidence <= 1.0:
                raise McpReadError("run_query returned confidence outside [0, 1]")
            start_ms = _required_int(row, "evidence_start_ms")
            end_ms = _required_int(row, "evidence_end_ms")
            if start_ms < 0 or end_ms < start_ms:
                raise McpReadError("run_query returned an invalid evidence window")
            result.append(
                ContinuityEvidenceRow(
                    production_id=production_id,
                    scene_id=scene_id,
                    take_id=take_id,
                    entity_id=_required_str(row, "entity_id"),
                    property_key=_required_str(row, "property_key"),
                    observed_value=_required_str(row, "observed_value"),
                    confidence=confidence,
                    evidence_start_ms=start_ms,
                    evidence_end_ms=end_ms,
                    baseline_value=_optional_str(row, "baseline_value"),
                    baseline_source_take_id=_optional_str(row, "baseline_source_take_id"),
                )
            )
        return tuple(result)

    def editorial_search(self, constraints: EditorialConstraints) -> tuple[EditorialHit, ...]:
        query = editorial_retrieval_sql(constraints, database=self._database)
        rows = self._run_query(query)
        result: list[EditorialHit] = []
        for row in rows:
            self._assert_scope(
                row,
                production_id=constraints.production_id,
                scene_id=constraints.scene_id,
            )
            result.append(
                EditorialHit(
                    production_id=constraints.production_id,
                    scene_id=constraints.scene_id,
                    take_id=_required_str(row, "take_id"),
                    take_number=_required_int(row, "take_number"),
                    director_rating=_required_int(row, "director_rating"),
                    dialogue_evidence_ms=_optional_int(row, "dialogue_evidence_ms"),
                    eyeline_evidence_ms=_optional_int(row, "eyeline_evidence_ms"),
                )
            )
        return tuple(result)
