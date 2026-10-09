"""
Pure auction rules.

No clock.
No network.
No database.
No UI.

These functions must be easy to test and reason about.
"""

from collections import namedtuple
from typing import List, Optional


Verdict = namedtuple("Verdict", "ok code reason")


def increment(price: int, cfg) -> int:
    """
    Return the increment that applies after this price.

    +100 while current bid is below 1500.
    +250 at 1500 and above.
    """
    return cfg.inc_low if price < cfg.inc_threshold else cfg.inc_high


def next_price(current_bid: Optional[int], base: int, cfg) -> int:
    """
    Return the exact minimum next valid bid amount.

    First bid is the base price.
    Later bids are current bid + active increment.
    """
    if current_bid is None:
        return base

    return current_bid + increment(current_bid, cfg)


def round_base_price(base: int, round_no: int, cfg) -> int:
    """
    Return base price after `round_no - 1` price drops.

    Rules:
    - base price falls 50% per extra round,
    - rounded to a multiple of inc_low,
    - never below floor price.
    """
    if round_no < 1:
        raise ValueError("round_no must be >= 1")

    base = max(base, cfg.floor_price)

    price = base * (1.0 - cfg.round_drop) ** (round_no - 1)

    # Round to nearest multiple of inc_low.
    # Example with inc_low = 100:
    #   250 -> 300
    #   249 -> 200
    price = int(price / cfg.inc_low + 0.5) * cfg.inc_low

    return max(price, cfg.floor_price)


def empty_slots_after_buy(roster_count: int, cfg) -> int:
    """
    Return how many squad slots remain empty after buying one more player.
    """
    return max(cfg.roster_size - roster_count - 1, 0)


def max_bid(purse: int, roster_count: int, cfg) -> int:
    """
    Reserve formula:

        Max bid = purse - (empty slots after this purchase * floor price)

    This guarantees that a team can always afford to fill all roster slots.
    """
    reserved = empty_slots_after_buy(roster_count, cfg) * cfg.floor_price
    return max(0, purse - reserved)


# Fixed jump increments captains can add on top of the minimum next price.
BID_INCREMENTS: List[int] = [250, 500, 1000, 1500]


def bid_options(
    current_bid: Optional[int],
    base: int,
    purse: int,
    roster_count: int,
    is_leader: bool,
    cfg,
) -> List[int]:
    """
    Return the list of valid bid amounts a captain can choose.

    The first option is always the minimum next price.
    Each subsequent option is minimum + one of BID_INCREMENTS.

    An amount is only included when:
      - the captain is not already leading, and
      - the amount does not exceed the team's available purse, and
      - the amount does not exceed the team's max_bid (reservation rule).
    """
    if is_leader:
        return []

    mb = max_bid(purse, roster_count, cfg)
    minimum = next_price(current_bid, base, cfg)

    candidates = [minimum] + [minimum + inc for inc in BID_INCREMENTS]
    return [a for a in candidates if a <= purse and a <= mb]


def check_bid(
    price: int,
    current_bid: Optional[int],
    base: int,
    purse: int,
    roster_count: int,
    is_leader: bool,
    cfg,
) -> Verdict:
    """
    Validate a bid.

    This function only checks pure bid rules.
    It does not check LIVE / paused / frozen state.
    Those are checked by the auction state machine.

    Accepted prices: any amount >= next_price(current_bid, base) that also
    does not exceed the team's max_bid.  This allows captains to place
    jump bids (+250, +500, +1000, +1500) instead of only the minimum increment.
    """

    if price is None or price <= 0:
        return Verdict(False, "BAD_PRICE", "Bid price must be positive.")

    if roster_count >= cfg.roster_size:
        return Verdict(False, "ROSTER_FULL", "Your squad is already full.")

    if is_leader:
        return Verdict(False, "ALREADY_LEADING", "You already have the highest bid.")

    minimum = next_price(current_bid, base, cfg)

    if price < minimum:
        return Verdict(
            False,
            "STALE",
            f"The price has moved. The minimum valid bid is {minimum}.",
        )

    if price > purse:
        return Verdict(False, "PURSE", f"Not enough purse ({purse}).")

    mb = max_bid(purse, roster_count, cfg)

    if price > mb:
        n = empty_slots_after_buy(roster_count, cfg)
        return Verdict(
            False,
            "RESERVE",
            f"Max bid is {mb}: keep {cfg.floor_price} for each of your {n} other empty slot(s).",
        )

    return Verdict(True, "OK", "Bid accepted.")