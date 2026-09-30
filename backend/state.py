"""
Shared application state.

This object is created once during startup and attached to FastAPI as:

    app.state.app_state
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class AppState:
    cfg: Any
    auction: Any
    store: Any
    hub: Any
    rate_limiter: Any
    admin_pin: str

    # token -> team_id
    team_tokens: Dict[str, int] = field(default_factory=dict)

    # team_id -> login_code
    team_logins: Dict[int, str] = field(default_factory=dict)