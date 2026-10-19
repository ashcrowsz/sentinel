"""Webhook signature verification.

GitHub signs every delivery with HMAC-SHA256 using the App's webhook secret.
Without this check anyone who finds the URL could make Sentinel review
(and spend tokens on) arbitrary payloads.
"""

from __future__ import annotations

import hashlib
import hmac

SIGNATURE_PREFIX = "sha256="


def compute_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def verify_signature(secret: str, body: bytes, header: str | None) -> bool:
    if not header or not header.startswith(SIGNATURE_PREFIX):
        return False
    expected = compute_signature(secret, body)
    # constant-time compare: no timing side channel on the digest
    return hmac.compare_digest(expected, header)
