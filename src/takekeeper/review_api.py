from __future__ import annotations

import hmac
import json
from dataclasses import asdict
from datetime import datetime
from typing import Mapping, Protocol

from .review import FindingReviewService, ReviewDecision, stable_finding_id

MAX_BODY_BYTES = 16_384
MAX_NOTE_LENGTH = 2_000
_SCOPE_FIELDS = ("production_id", "scene_id", "take_id", "entity_id", "property_key")
_ALLOWED_DECISIONS = {"confirmed", "rejected", "needs_followup"}


class ReviewerIdentityProvider(Protocol):
    def authenticate(self, authorization: str | None) -> str: ...


class StaticBearerIdentityProvider:
    """Small deployment-safe identity adapter for local/self-hosted installs.

    Tokens are configured by the operator and mapped to stable actor IDs. Comparison is
    constant-time and the token is never returned or persisted by this module.
    """

    def __init__(self, token_to_actor: Mapping[str, str]) -> None:
        if not token_to_actor:
            raise ValueError("at least one reviewer token is required")
        self._entries = tuple((token.encode(), actor.strip()) for token, actor in token_to_actor.items())
        if any(not token or not actor for token, actor in self._entries):
            raise ValueError("reviewer tokens and actor IDs must not be empty")

    def authenticate(self, authorization: str | None) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise PermissionError("authentication required")
        supplied = authorization[7:].encode()
        for expected, actor in self._entries:
            if hmac.compare_digest(supplied, expected):
                return actor
        raise PermissionError("invalid credentials")


class ReviewHttpApp:
    """Narrow WSGI boundary for evidence review.

    Exposes only two operations: read one current finding with its append-only history,
    and append one bounded human decision. It intentionally exposes no SQL, table,
    finding-ID, actor-ID, or generic mutation primitive.
    """

    def __init__(self, service: FindingReviewService, identity: ReviewerIdentityProvider) -> None:
        self._service = service
        self._identity = identity

    def __call__(self, environ, start_response):
        try:
            status, payload = self._dispatch(environ)
        except PermissionError as exc:
            status, payload = 401, {"error": str(exc)}
        except LookupError:
            status, payload = 404, {"error": "finding not found in requested scope"}
        except (ValueError, json.JSONDecodeError):
            status, payload = 400, {"error": "invalid request"}
        except Exception:
            status, payload = 500, {"error": "internal server error"}

        body = json.dumps(payload, separators=(",", ":"), default=_json_default).encode()
        start_response(
            f"{status} {_status_text(status)}",
            [("Content-Type", "application/json"), ("Content-Length", str(len(body))), ("Cache-Control", "no-store")],
        )
        return [body]

    def _dispatch(self, environ) -> tuple[int, dict]:
        method = str(environ.get("REQUEST_METHOD", "")).upper()
        path = str(environ.get("PATH_INFO", ""))
        if method != "POST":
            return 405, {"error": "method not allowed"}
        actor_id = self._identity.authenticate(environ.get("HTTP_AUTHORIZATION"))
        payload = _read_json_body(environ)

        if path == "/v1/review/context":
            scope = _scope(payload, allowed=set(_SCOPE_FIELDS))
            finding = self._service.get_finding(**scope)
            history = self._service.history(**scope)
            return 200, {
                "finding": {**asdict(finding), "finding_id": stable_finding_id(finding)},
                "history": [_decision_dict(row) for row in history],
            }

        if path == "/v1/review/decision":
            allowed = set(_SCOPE_FIELDS) | {"decision", "note"}
            scope = _scope(payload, allowed=allowed)
            decision = payload.get("decision")
            note = payload.get("note", "")
            if decision not in _ALLOWED_DECISIONS or not isinstance(note, str) or len(note) > MAX_NOTE_LENGTH:
                raise ValueError("invalid decision")
            persisted = self._service.review(actor_id=actor_id, decision=decision, note=note, **scope)
            return 201, {"decision": _decision_dict(persisted)}

        return 404, {"error": "not found"}


def _scope(payload: dict, *, allowed: set[str]) -> dict[str, str]:
    if set(payload) - allowed:
        raise ValueError("unexpected fields")
    result: dict[str, str] = {}
    for field in _SCOPE_FIELDS:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise ValueError("invalid scope")
        result[field] = value
    return result


def _read_json_body(environ) -> dict:
    raw_length = environ.get("CONTENT_LENGTH") or "0"
    try:
        length = int(raw_length)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid content length") from exc
    if length <= 0 or length > MAX_BODY_BYTES:
        raise ValueError("invalid body size")
    body = environ["wsgi.input"].read(length)
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    return payload


def _decision_dict(row: ReviewDecision) -> dict:
    data = asdict(row)
    if isinstance(row.created_at, datetime):
        data["created_at"] = row.created_at.isoformat()
    return data


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _status_text(status: int) -> str:
    return {
        200: "OK",
        201: "Created",
        400: "Bad Request",
        401: "Unauthorized",
        404: "Not Found",
        405: "Method Not Allowed",
        500: "Internal Server Error",
    }[status]
