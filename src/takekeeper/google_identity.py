from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key"
IAP_ISSUER = "https://cloud.google.com/iap"
GOOGLE_OIDC_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})
MAX_ACTOR_COMPONENT_LENGTH = 512
MAX_TOKEN_LENGTH = 16_384
MAX_AUTHORIZED_SUBJECTS = 256


class TokenVerifier(Protocol):
    def __call__(self, token: str, audience: str) -> Mapping[str, object]: ...


class GoogleIdentityConfigurationError(ValueError):
    """Google identity configuration is structurally invalid."""


@dataclass(frozen=True, slots=True)
class GoogleIdentityClaims:
    subject: str
    issuer: str
    audience: str
    expires_at: int


def _default_oidc_verifier(token: str, audience: str) -> Mapping[str, object]:
    try:
        from google.auth.transport import requests
        from google.oauth2 import id_token
    except ImportError as exc:  # pragma: no cover - optional production dependency
        raise RuntimeError("google-auth is required for Google identity verification") from exc
    return id_token.verify_oauth2_token(token, requests.Request(), audience=audience)


def _default_iap_verifier(token: str, audience: str) -> Mapping[str, object]:
    try:
        from google.auth.transport import requests
        from google.oauth2 import id_token
    except ImportError as exc:  # pragma: no cover - optional production dependency
        raise RuntimeError("google-auth is required for IAP identity verification") from exc
    return id_token.verify_token(
        token,
        requests.Request(),
        audience=audience,
        certs_url=IAP_CERTS_URL,
    )


class GoogleOidcIdentityProvider:
    """Verify Google OIDC and optionally require a deployment-owned subject mapping.

    ``authorized_subjects`` maps verified Google ``sub`` values to bounded TakeKeeper actor
    IDs. Production composition always supplies this mapping. Keeping it optional here lets
    embedders use the verifier as a pure authentication primitive, but callers that need an
    authorization boundary should always configure it explicitly.
    """

    def __init__(
        self,
        expected_audience: str,
        *,
        verifier: TokenVerifier | None = None,
        clock: Callable[[], float] = time.time,
        clock_skew_seconds: int = 60,
        actor_prefix: str = "google",
        authorized_subjects: Mapping[str, str] | None = None,
    ) -> None:
        self._audience = _bounded_config(expected_audience, "expected audience", 2_048)
        self._verifier = verifier or _default_oidc_verifier
        self._clock = clock
        self._clock_skew_seconds = _validate_skew(clock_skew_seconds)
        self._actor_prefix = _bounded_config(actor_prefix, "actor prefix", 64)
        self._authorized_subjects = _validate_subject_mapping(authorized_subjects)

    def authenticate(self, authorization: str | None) -> str:
        token = _bearer_token(authorization)
        claims = _verify_bounded(
            token,
            expected_audience=self._audience,
            allowed_issuers=GOOGLE_OIDC_ISSUERS,
            verifier=self._verifier,
            now=self._clock(),
            clock_skew_seconds=self._clock_skew_seconds,
        )
        return _authorized_actor(
            claims.subject,
            self._authorized_subjects,
            default=f"{self._actor_prefix}:{claims.subject}",
        )


class IapIdentityProvider:
    """Verify an IAP signed-header JWT and optionally enforce subject authorization."""

    def __init__(
        self,
        expected_audience: str,
        *,
        verifier: TokenVerifier | None = None,
        clock: Callable[[], float] = time.time,
        clock_skew_seconds: int = 60,
        actor_prefix: str = "iap",
        authorized_subjects: Mapping[str, str] | None = None,
    ) -> None:
        self._audience = _bounded_config(expected_audience, "expected audience", 2_048)
        self._verifier = verifier or _default_iap_verifier
        self._clock = clock
        self._clock_skew_seconds = _validate_skew(clock_skew_seconds)
        self._actor_prefix = _bounded_config(actor_prefix, "actor prefix", 64)
        self._authorized_subjects = _validate_subject_mapping(authorized_subjects)

    def authenticate(self, assertion: str | None) -> str:
        if not isinstance(assertion, str) or not assertion or len(assertion) > MAX_TOKEN_LENGTH:
            raise PermissionError("authentication required")
        claims = _verify_bounded(
            assertion,
            expected_audience=self._audience,
            allowed_issuers=frozenset({IAP_ISSUER}),
            verifier=self._verifier,
            now=self._clock(),
            clock_skew_seconds=self._clock_skew_seconds,
        )
        return _authorized_actor(
            claims.subject,
            self._authorized_subjects,
            default=f"{self._actor_prefix}:{claims.subject}",
        )


def _verify_bounded(
    token: str,
    *,
    expected_audience: str,
    allowed_issuers: frozenset[str],
    verifier: TokenVerifier,
    now: float,
    clock_skew_seconds: int,
) -> GoogleIdentityClaims:
    try:
        raw = verifier(token, expected_audience)
        if not isinstance(raw, Mapping):
            raise ValueError("invalid claims")
        issuer = _claim_text(raw, "iss", 256)
        subject = _claim_text(raw, "sub", MAX_ACTOR_COMPONENT_LENGTH)
        audience = _claim_audience(raw.get("aud"), expected_audience)
        expires_at = _claim_int(raw, "exp")
        issued_at = _claim_int(raw, "iat")
        if issuer not in allowed_issuers:
            raise ValueError("invalid issuer")
        if audience != expected_audience:
            raise ValueError("invalid audience")
        if expires_at <= int(now - clock_skew_seconds):
            raise ValueError("expired token")
        if issued_at > int(now + clock_skew_seconds):
            raise ValueError("token issued in future")
    except PermissionError:
        raise
    except Exception:
        raise PermissionError("invalid credentials") from None
    return GoogleIdentityClaims(
        subject=subject,
        issuer=issuer,
        audience=audience,
        expires_at=expires_at,
    )


def _authorized_actor(
    subject: str,
    authorized_subjects: Mapping[str, str] | None,
    *,
    default: str,
) -> str:
    if authorized_subjects is None:
        return default
    actor = authorized_subjects.get(subject)
    if actor is None:
        # Deliberately identical to malformed/invalid credentials: never disclose whether a
        # signed subject exists in the deployment's authorization policy.
        raise PermissionError("invalid credentials")
    return actor


def _validate_subject_mapping(
    value: Mapping[str, str] | None,
) -> Mapping[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or not value or len(value) > MAX_AUTHORIZED_SUBJECTS:
        raise GoogleIdentityConfigurationError("invalid authorized subject mapping")
    normalized: dict[str, str] = {}
    for subject, actor in value.items():
        checked_subject = _bounded_config(subject, "authorized subject", MAX_ACTOR_COMPONENT_LENGTH)
        checked_actor = _bounded_config(actor, "authorized actor", MAX_ACTOR_COMPONENT_LENGTH)
        if checked_subject in normalized:
            raise GoogleIdentityConfigurationError("invalid authorized subject mapping")
        normalized[checked_subject] = checked_actor
    return normalized


def _bearer_token(authorization: str | None) -> str:
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        raise PermissionError("authentication required")
    token = authorization[7:]
    if not token or len(token) > MAX_TOKEN_LENGTH or any(ord(ch) < 33 for ch in token):
        raise PermissionError("invalid credentials")
    return token


def _claim_text(claims: Mapping[str, object], name: str, max_length: int) -> str:
    value = claims.get(name)
    if not isinstance(value, str):
        raise ValueError("missing claim")
    value = value.strip()
    if not value or len(value) > max_length or any(ord(ch) < 32 for ch in value):
        raise ValueError("invalid claim")
    return value


def _claim_int(claims: Mapping[str, object], name: str) -> int:
    value = claims.get(name)
    if type(value) not in {int, float}:
        raise ValueError("invalid numeric claim")
    return int(value)


def _claim_audience(value: object, expected: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and len(value) == 1 and value[0] == expected:
        return expected
    raise ValueError("invalid audience")


def _bounded_config(value: str, label: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise GoogleIdentityConfigurationError(f"invalid {label}")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > max_length or any(ord(ch) < 32 for ch in cleaned):
        raise GoogleIdentityConfigurationError(f"invalid {label}")
    return cleaned


def _validate_skew(value: int) -> int:
    if type(value) is not int or not 0 <= value <= 300:
        raise GoogleIdentityConfigurationError("invalid clock skew")
    return value
