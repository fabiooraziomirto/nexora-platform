from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from typing import Any

import jwt


@dataclass
class OIDCClaims:
    sub: str
    iss: str
    aud: str | list[str] | None
    exp: int | None
    raw: dict[str, Any]


class OIDCVerifier:
    """Lightweight OIDC JWT verifier with JWKS cache."""

    def __init__(self, jwks_url: str, issuer: str | None = None, audience: str | None = None, ttl_seconds: int = 300):
        self.jwks_url = jwks_url
        self.issuer = issuer
        self.audience = audience
        self.ttl_seconds = ttl_seconds
        self._jwks: dict[str, Any] | None = None
        self._jwks_cached_at = 0.0

    def _load_jwks(self) -> dict[str, Any]:
        now = time.time()
        if self._jwks and now - self._jwks_cached_at < self.ttl_seconds:
            return self._jwks
        with urllib.request.urlopen(self.jwks_url, timeout=5) as response:
            self._jwks = json.loads(response.read().decode("utf-8"))
            self._jwks_cached_at = now
            return self._jwks

    def verify(self, token: str) -> OIDCClaims:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        jwks = self._load_jwks()
        keys = jwks.get("keys", [])
        key = next((k for k in keys if k.get("kid") == kid), None)
        if not key:
            raise ValueError("signing key not found for token kid")
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
        payload = jwt.decode(
            token,
            key=public_key,
            algorithms=[header.get("alg", "RS256")],
            issuer=self.issuer if self.issuer else None,
            audience=self.audience if self.audience else None,
            options={"verify_aud": bool(self.audience), "verify_iss": bool(self.issuer)},
        )
        return OIDCClaims(
            sub=str(payload.get("sub", "")),
            iss=str(payload.get("iss", "")),
            aud=payload.get("aud"),
            exp=payload.get("exp"),
            raw=payload,
        )
