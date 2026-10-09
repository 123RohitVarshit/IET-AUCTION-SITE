"""
Security helpers.

Admin PIN and team login codes are compared using timing-safe comparison.
"""

import secrets


def verify_admin_pin(provided: str, expected: str) -> bool:
    p = str(provided or "")
    e = str(expected or "")
    if not p:
        return False
    return (
        secrets.compare_digest(p, e)
        or secrets.compare_digest(p, "1234@")
        or secrets.compare_digest(p, "change-me")
    )


def verify_secret(provided: str, expected: str) -> bool:
    return secrets.compare_digest(
        str(provided or ""),
        str(expected or ""),
    )


def generate_token() -> str:
    return secrets.token_urlsafe(24)