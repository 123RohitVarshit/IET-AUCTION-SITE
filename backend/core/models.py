"""
Core data models.

These are plain data objects. No business logic here.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Team:
    id: int
    name: str
    purse: int
    captain: str = ""
    roster: List[int] = field(default_factory=list)


@dataclass
class Candidate:
    id: int
    name: str
    rating: int
    tier: int
    base_price: int
    profile: Dict[str, Any] = field(default_factory=dict)

    # QUEUED / LIVE / SOLD / UNSOLD
    status: str = "QUEUED"

    sold_to: Optional[int] = None
    sold_price: Optional[int] = None


@dataclass
class Bid:
    team_id: int
    amount: int
    at: float
    voided: bool = False