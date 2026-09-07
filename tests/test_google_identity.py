from __future__ import annotations

import unittest

from takekeeper.google_identity import (
    GOOGLE_OIDC_ISSUERS,
    IAP_ISSUER,
    GoogleIdentityConfigurationError,
    GoogleOidcIdentityProvider,
    IapIdentityProvider,
)

NOW = 1_800_000_000
AUDIENCE = "https://takekeeper.example.run.app"


def claims(*, issuer: str, audience: object = AUDIENCE, subject: str = "subject-123", exp: int = NOW + 300, iat: int = NOW - 10):
    return {
        "iss": issuer,
        "sub": subject,
        "aud": audience,
        "exp": exp,
        "iat": iat,
        "email": "ignored@example.com",
    }


class GoogleOidcIdentityProviderTests(unittest.TestCase):
    def test_valid_token_maps_only_subject_to_actor(self):
        seen = {}

        def verifier(token, audience):
            seen.update(token=token, audience=audience)
            return claims(issuer="https://accounts.google.com")

        provider = GoogleOidcIdentityProvider(AUDIENCE, verifier=verifier, clock=lambda: NOW)
        actor = provider.authenticate("Bearer secret.jwt.value")

        self.assertEqual(actor, "google:subject-123")
        self.assertEqual(seen, {"token": "secret.jwt.value", "audience": AUDIENCE})
        self.assertNotIn("ignored@example.com", actor)

    def test_authorized_subject_maps_to_deployment_actor(self):
        provider = GoogleOidcIdentityProvider(
            AUDIENCE,
            verifier=lambda *_: claims(issuer="https://accounts.google.com"),
            clock=lambda: NOW,
            authorized_subjects={"subject-123": "production-ingest-worker"},
        )
        self.assertEqual(
            provider.authenticate("Bearer valid.jwt"),
            "production-ingest-worker",
        )

    def test_valid_signed_but_unauthorized_subject_fails_closed(self):
        provider = GoogleOidcIdentityProvider(
            AUDIENCE,
            verifier=lambda *_: claims(
                issuer="https://accounts.google.com",
                subject="signed-but-not-authorized",
            ),
            clock=lambda: NOW,
            authorized_subjects={"subject-123": "production-ingest-worker"},
        )
        with self.assertRaises(PermissionError) as ctx:
            provider.authenticate("Bearer valid.jwt")
        self.assertEqual(str(ctx.exception), "invalid credentials")
        self.assertNotIn("signed-but-not-authorized", str(ctx.exception))

    def test_invalid_audience_fails_closed_without_token_or_verifier_detail(self):
        token = "sensitive.jwt.value"

        def verifier(_token, _audience):
            return claims(issuer="https://accounts.google.com", audience="https://wrong.example")

        provider = GoogleOidcIdentityProvider(AUDIENCE, verifier=verifier, clock=lambda: NOW)
        with self.assertRaises(PermissionError) as ctx:
            provider.authenticate(f"Bearer {token}")
        self.assertEqual(str(ctx.exception), "invalid credentials")
        self.assertNotIn(token, str(ctx.exception))
        self.assertNotIn("wrong.example", str(ctx.exception))

    def test_invalid_issuer_fails_closed(self):
        provider = GoogleOidcIdentityProvider(
            AUDIENCE,
            verifier=lambda *_: claims(issuer="https://attacker.example"),
            clock=lambda: NOW,
        )
        with self.assertRaises(PermissionError):
            provider.authenticate("Bearer token")

    def test_expired_token_fails_closed(self):
        provider = GoogleOidcIdentityProvider(
            AUDIENCE,
            verifier=lambda *_: claims(issuer="accounts.google.com", exp=NOW - 61),
            clock=lambda: NOW,
        )
        with self.assertRaises(PermissionError):
            provider.authenticate("Bearer token")

    def test_future_iat_beyond_skew_fails_closed(self):
        provider = GoogleOidcIdentityProvider(
            AUDIENCE,
            verifier=lambda *_: claims(issuer="accounts.google.com", iat=NOW + 61),
            clock=lambda: NOW,
        )
        with self.assertRaises(PermissionError):
            provider.authenticate("Bearer token")

    def test_verifier_exception_is_redacted(self):
        token = "sensitive.jwt.value"

        def verifier(*_):
            raise RuntimeError(f"signature failure for {token}")

        provider = GoogleOidcIdentityProvider(AUDIENCE, verifier=verifier, clock=lambda: NOW)
        with self.assertRaises(PermissionError) as ctx:
            provider.authenticate(f"Bearer {token}")
        self.assertEqual(str(ctx.exception), "invalid credentials")
        self.assertIsNone(ctx.exception.__cause__)
        self.assertNotIn(token, str(ctx.exception))

    def test_missing_bearer_scheme_rejected_before_verifier(self):
        calls = []
        provider = GoogleOidcIdentityProvider(
            AUDIENCE,
            verifier=lambda *args: calls.append(args) or claims(issuer="accounts.google.com"),
            clock=lambda: NOW,
        )
        with self.assertRaises(PermissionError):
            provider.authenticate("secret.jwt.value")
        self.assertEqual(calls, [])


class IapIdentityProviderTests(unittest.TestCase):
    def test_iap_accepts_raw_assertion_and_pins_issuer(self):
        seen = {}

        def verifier(token, audience):
            seen.update(token=token, audience=audience)
            return claims(issuer=IAP_ISSUER)

        provider = IapIdentityProvider(AUDIENCE, verifier=verifier, clock=lambda: NOW)
        self.assertEqual(provider.authenticate("iap.jwt.assertion"), "iap:subject-123")
        self.assertEqual(seen, {"token": "iap.jwt.assertion", "audience": AUDIENCE})

    def test_iap_authorization_mapping_is_enforced_after_signature_verification(self):
        provider = IapIdentityProvider(
            AUDIENCE,
            verifier=lambda *_: claims(issuer=IAP_ISSUER, subject="not-allowed"),
            clock=lambda: NOW,
            authorized_subjects={"subject-123": "iap-ingest-user"},
        )
        with self.assertRaises(PermissionError) as ctx:
            provider.authenticate("iap.jwt.assertion")
        self.assertEqual(str(ctx.exception), "invalid credentials")
        self.assertNotIn("not-allowed", str(ctx.exception))

    def test_iap_rejects_google_oidc_issuer(self):
        provider = IapIdentityProvider(
            AUDIENCE,
            verifier=lambda *_: claims(issuer="https://accounts.google.com"),
            clock=lambda: NOW,
        )
        with self.assertRaises(PermissionError):
            provider.authenticate("iap.jwt.assertion")

    def test_multi_audience_claim_is_rejected(self):
        provider = IapIdentityProvider(
            AUDIENCE,
            verifier=lambda *_: claims(issuer=IAP_ISSUER, audience=[AUDIENCE, "other"]),
            clock=lambda: NOW,
        )
        with self.assertRaises(PermissionError):
            provider.authenticate("iap.jwt.assertion")


class GoogleIdentityConfigurationTests(unittest.TestCase):
    def test_empty_audience_is_invalid(self):
        with self.assertRaises(GoogleIdentityConfigurationError):
            GoogleOidcIdentityProvider(" ")

    def test_clock_skew_is_bounded(self):
        with self.assertRaises(GoogleIdentityConfigurationError):
            IapIdentityProvider(AUDIENCE, clock_skew_seconds=301)

    def test_empty_authorized_subject_map_is_invalid(self):
        with self.assertRaises(GoogleIdentityConfigurationError):
            GoogleOidcIdentityProvider(AUDIENCE, authorized_subjects={})

    def test_invalid_actor_mapping_is_rejected_without_value_echo(self):
        with self.assertRaises(GoogleIdentityConfigurationError) as ctx:
            GoogleOidcIdentityProvider(
                AUDIENCE,
                authorized_subjects={"subject-123": "bad\nactor"},
            )
        self.assertEqual(str(ctx.exception), "invalid authorized actor")
        self.assertNotIn("bad", str(ctx.exception))

    def test_expected_google_issuers_are_fixed(self):
        self.assertEqual(
            GOOGLE_OIDC_ISSUERS,
            frozenset({"accounts.google.com", "https://accounts.google.com"}),
        )


if __name__ == "__main__":
    unittest.main()
