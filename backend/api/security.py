"""
Security helpers.

Admin PIN and team login codes are compared using timing-safe comparison.
"""

import secrets


def verify_admin_pin(provided: str, expected: str) -> bool:
    return secrets.compare_digest(
        str(provided or ""),
        str(expected or ""),
    )


def verify_secret(provided: str, expected: str) -> bool:
    return secrets.compare_digest(
        str(provided or ""),
        str(expected or ""),
    )


def generate_token() -> str:
    return secrets.token_urlsafe(24)