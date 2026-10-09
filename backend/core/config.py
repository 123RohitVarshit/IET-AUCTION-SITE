"""
All tunable settings in one place.

Nothing else in the code should hardcode auction numbers.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Config:
    # Squad rules
    roster_size: int = 4              # players per team, captain not counted
    purse: int = 10_000               # starting purse per team
    min_purse: int = 0                # minimum purse guardrail (0 = standard floor reserve only)

    # Tier base prices
    tier_base: Dict[int, int] = field(
        default_factory=lambda: {
            1: 1000,
            2: 600,
            3: 400,
            4: 200,
        }
    )

    # Bidding increments
    inc_low: int = 100                # increment below threshold
    inc_high: int = 250               # increment at/above threshold
    inc_threshold: int = 1500

    # Floor price is also the reserve amount kept per empty slot
    floor_price: int = 100

    # Unsold player price decay
    round_drop: float = 0.5
    max_rounds: int = 5

    preview_seconds: float = 0.0
    bid_seconds: float = 120.0
    result_seconds: float = 8.0
    anti_snipe_seconds: float = 8.0
    undo_extend_seconds: float = 10.0

    # Flow
    auto_advance: bool = True