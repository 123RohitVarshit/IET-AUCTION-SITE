"""
The auction state machine.

Owns all live state, one lock, and the server-side clock.

Phases:

    SETUP -> IDLE -> PREVIEW -> LIVE -> RESULT -> next player ... -> DONE

Manual override adds:

    LIVE -> AWAITING_HAMMER

No network.
No database.
No UI.

The clock is injectable so tests can fake time.
"""

import threading
import time
from typing import Any, Callable, Dict, List, Optional

from . import rules
from .config import Config
from .models import Bid, Candidate, Team


class Auction:
    def __init__(
        self,
        cfg: Config,
        teams: List[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
        clock: Callable[[], float] = time.monotonic,
    ):
        self.cfg = cfg
        self.clock = clock
        self.lock = threading.RLock()

        self.teams: Dict[int, Team] = {}
        for t in teams:
            self.teams[t["id"]] = Team(
                id=t["id"],
                name=t["name"],
                purse=t.get("purse", cfg.purse),
                roster=list(t.get("roster", [])),
            )

        self.cands: Dict[int, Candidate] = {}
        for c in candidates:
            c = dict(c)
            c.setdefault("base_price", cfg.tier_base[c["tier"]])
            self.cands[c["id"]] = Candidate(**c)

        self.order: List[int] = [c["id"] for c in candidates]

        self.phase = "SETUP"
        self.round_no = 1
        self.current: Optional[int] = None

        # Bids for the current candidate only.
        self.bids: List[Bid] = []

        self.deadline = 0.0
        self.paused = False
        self.paused_left = 0.0
        self.frozen = False

        self.last_result: Optional[Dict[str, Any]] = None
        self.done_reason: Optional[str] = None

        # False = auto-sell / auto-advance.
        # True = admin runs every step.
        self.manual_mode = False

        # Audit log.
        self.events: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log(self, kind: str, **data) -> None:
        self.events.append({"t": self.clock(), "kind": kind, **data})

    def _valid_bids(self) -> List[Bid]:
        return [b for b in self.bids if not b.voided]

    def leader(self) -> Optional[int]:
        v = self._valid_bids()
        return v[-1].team_id if v else None

    def current_bid(self) -> Optional[int]:
        v = self._valid_bids()
        return v[-1].amount if v else None

    def current_base(self) -> int:
        return rules.round_base_price(
            self.cands[self.current].base_price,
            self.round_no,
            self.cfg,
        )

    def next_price(self) -> int:
        return rules.next_price(
            self.current_bid(),
            self.current_base(),
            self.cfg,
        )

    def time_left(self) -> float:
        if self.paused:
            return self.paused_left

        if self.phase in ("PREVIEW", "LIVE", "RESULT"):
            return max(0.0, self.deadline - self.clock())

        return 0.0

    def _all_full(self) -> bool:
        return all(
            len(t.roster) >= self.cfg.roster_size
            for t in self.teams.values()
        )

    def _done(self, reason: str) -> None:
        self.phase = "DONE"
        self.current = None
        self.done_reason = reason
        self._log("done", reason=reason)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup_report(self) -> Dict[str, Any]:
        with self.lock:
            T = len(self.teams)
            N = len(self.cands)
            R = self.cfg.roster_size

            purse_ok = all(
                t.purse >= R * self.cfg.floor_price
                for t in self.teams.values()
            )

            needed = T * R

            return {
                "teams": T,
                "candidates": N,
                "roster_size": R,
                "needed": needed,
                "short_by": max(0, needed - N),
                "spare_candidates": max(0, N - needed),
                "max_teams_supported": N // R if R > 0 else 0,
                "purse_ok": purse_ok,
                "ok": T > 0 and N > 0 and N >= needed and purse_ok,
            }

    def start(self) -> None:
        with self.lock:
            if self.phase != "SETUP":
                raise ValueError(f"Auction already started (current phase: {self.phase}).")

            rep = self.setup_report()
            if not rep["ok"]:
                raise ValueError(f"Setup check failed: {rep}")

            self.phase = "IDLE"
            self._log("start", **rep)

    # ------------------------------------------------------------------
    # Flow
    # ------------------------------------------------------------------

    def next_candidate(self, candidate_id: Optional[int] = None, by: str = "admin") -> None:
        """
        Show the next queued player, or a specific one if admin jumps.
        """

        with self.lock:
            if self.phase in ("PREVIEW", "LIVE", "AWAITING_HAMMER"):
                if self._valid_bids():
                    raise ValueError("Current player already has bids. Undo them first.")

                if self.current is not None:
                    self.cands[self.current].status = "QUEUED"

                self.paused = False

            elif self.phase not in ("IDLE", "RESULT"):
                raise ValueError(f"Cannot move to next player from {self.phase}")

            self._pick(candidate_id)

    def _pick(self, candidate_id: Optional[int] = None) -> None:
        still_queued = any(
            self.cands[i].status == "QUEUED" for i in self.order
        )

        if self._all_full() and not still_queued:
            return self._done("All squads are full.")

        if candidate_id is not None:
            c = self.cands.get(candidate_id)

            if c is None:
                raise ValueError("Unknown candidate.")

            if c.status not in ("QUEUED", "UNSOLD"):
                raise ValueError("That player is not available.")

        else:
            c = next(
                (
                    self.cands[i]
                    for i in self.order
                    if self.cands[i].status == "QUEUED"
                ),
                None,
            )

            if c is None:
                unsold = [
                    self.cands[i]
                    for i in self.order
                    if self.cands[i].status == "UNSOLD"
                ]

                if not unsold:
                    return self._done("No candidates left.")

                if self.round_no >= self.cfg.max_rounds:
                    return self._done("Max rounds reached. Assign remaining slots manually.")

                self.round_no += 1

                for u in unsold:
                    u.status = "QUEUED"

                self._log("new_round", round=self.round_no, players=len(unsold))

                c = unsold[0]

        c.status = "LIVE"
        self.current = c.id
        self.bids = []

        self.paused = False
        self.frozen = False
        self.last_result = None

        self._log("show", candidate=c.id, round=self.round_no)

        if self.cfg.preview_seconds > 0:
            self.phase = "PREVIEW"
            self.deadline = self.clock() + self.cfg.preview_seconds
        else:
            self._go_live()

    def _go_live(self) -> None:
        self.phase = "LIVE"
        self.deadline = self.clock() + self.cfg.bid_seconds

    def _finalize(self) -> None:
        if self.current is None:
            return

        c = self.cands[self.current]
        valid = self._valid_bids()

        if valid:
            b = valid[-1]
            team = self.teams[b.team_id]

            # Money moves only when sale is finalized.
            team.purse -= b.amount
            team.roster.append(c.id)

            c.status = "SOLD"
            c.sold_to = team.id
            c.sold_price = b.amount

            self.last_result = {
                "outcome": "SOLD",
                "candidate": c.id,
                "team": team.id,
                "price": b.amount,
            }

        else:
            c.status = "UNSOLD"
            self.last_result = {
                "outcome": "UNSOLD",
                "candidate": c.id,
            }

        self.phase = "RESULT"
        self.deadline = self.clock() + self.cfg.result_seconds

        self._log("result", **self.last_result)

    def tick(self, now: Optional[float] = None) -> None:
        """
        Advance clock-driven transitions.

        The server calls this around 10 times per second.

        AUTO mode:
            LIVE deadline -> automatic sale.
            RESULT deadline -> automatic next player.

        MANUAL mode:
            LIVE deadline -> AWAITING_HAMMER.
            RESULT deadline -> wait for admin.
        """

        with self.lock:
            if self.paused:
                return

            if now is None:
                now = self.clock()

            if self.phase == "PREVIEW" and now >= self.deadline:
                self._go_live()

            elif self.phase == "LIVE" and now >= self.deadline:
                if self.manual_mode:
                    self.phase = "AWAITING_HAMMER"
                    self._log("awaiting_hammer")
                else:
                    self._finalize()

            elif (
                self.phase == "RESULT"
                and self.cfg.auto_advance
                and not self.manual_mode
                and now >= self.deadline
            ):
                self._pick()

    def set_manual_mode(self, on: bool, by: str = "admin") -> None:
        """
        Toggle admin-conducted mode.

        Safe to flip at any point. It only affects the next transition.
        """

        with self.lock:
            self.manual_mode = bool(on)
            self._log("set_manual_mode", on=self.manual_mode, by=by)

    def confirm_sale(self, by: str = "admin") -> None:
        """
        Admin hammer: sell to current highest bidder now.

        Works during LIVE and AWAITING_HAMMER.
        """

        with self.lock:
            if self.phase not in ("LIVE", "AWAITING_HAMMER"):
                raise ValueError(f"Cannot confirm a sale from {self.phase}")

            if not self._valid_bids():
                raise ValueError("No bids on this player yet. Use Mark Unsold instead.")

            self._log("manual_confirm", by=by)
            self._finalize()

    def mark_unsold(self, by: str = "admin") -> None:
        """
        Admin hammer: force this player to UNSOLD now.

        Bids are voided. Nothing has been charged yet.
        """

        with self.lock:
            if self.phase not in ("LIVE", "AWAITING_HAMMER"):
                raise ValueError(f"Cannot mark unsold from {self.phase}")

            self._log(
                "manual_unsold",
                by=by,
                discarded_bids=len(self._valid_bids()),
            )

            for b in self.bids:
                b.voided = True

            self._finalize()

    # ------------------------------------------------------------------
    # Bidding
    # ------------------------------------------------------------------

    def place_bid(self, team_id: int, price: int) -> rules.Verdict:
        """
        Place a bid.

        This is the only write path for captain bidding.
        The server layer should rate-limit before calling this.
        """

        with self.lock:
            now = self.clock()

            # Use one consistent timestamp for this decision.
            self.tick(now)

            if self.phase != "LIVE" or self.paused:
                return rules.Verdict(False, "NOT_LIVE", "Bidding is not open right now.")

            if self.frozen:
                return rules.Verdict(False, "FROZEN", "Bids are frozen by the admin.")

            # If the deadline passed between tick and this exact timestamp,
            # reject safely.
            if now >= self.deadline:
                self.tick(now)
                return rules.Verdict(False, "NOT_LIVE", "Bidding is not open right now.")

            team = self.teams.get(team_id)

            if team is None:
                return rules.Verdict(False, "NO_TEAM", "Unknown team.")

            v = rules.check_bid(
                price,
                self.current_bid(),
                self.current_base(),
                team.purse,
                len(team.roster),
                self.leader() == team_id,
                self.cfg,
            )

            if not v.ok:
                return v

            self.bids.append(Bid(team_id, price, now))

            # Anti-snipe: late bid resets clock to anti_snipe_seconds.
            if self.deadline - now < self.cfg.anti_snipe_seconds:
                self.deadline = now + self.cfg.anti_snipe_seconds

            self._log("bid", team=team_id, amount=price)

            return v

    def undo_last_bid(self, by: str = "admin") -> tuple[bool, str]:
        """
        Live:
            Void the last bid. Previous bidder becomes leader.

        During RESULT after SOLD:
            Reverse the sale, void the winning bid, reopen bidding.
        """

        with self.lock:
            now = self.clock()
            self.tick(now)

            if self.phase in ("LIVE", "AWAITING_HAMMER"):
                v = self._valid_bids()

                if not v:
                    return False, "No bid to undo."

                last = v[-1]
                last.voided = True

                self._log(
                    "undo",
                    by=by,
                    team=last.team_id,
                    amount=last.amount,
                )

                return True, "Last bid removed."

            if (
                self.phase == "RESULT"
                and self.last_result
                and self.last_result["outcome"] == "SOLD"
            ):
                c = self.cands[self.current]
                team = self.teams[c.sold_to]

                # Reverse the finalized sale.
                team.purse += c.sold_price
                team.roster.remove(c.id)

                # Void winning bid so previous bidder becomes leader.
                last = self._valid_bids()[-1]
                last.voided = True

                c.status = "LIVE"
                c.sold_to = None
                c.sold_price = None

                self.phase = "LIVE"
                self.paused = False
                self.deadline = now + self.cfg.undo_extend_seconds
                self.last_result = None

                self._log(
                    "undo_sale",
                    by=by,
                    team=team.id,
                    amount=last.amount,
                )

                return True, "Sale reversed. Bidding reopened."

            return False, "Nothing to undo."

    # ------------------------------------------------------------------
    # Admin controls
    # ------------------------------------------------------------------

    def pause(self) -> None:
        with self.lock:
            if self.phase in ("PREVIEW", "LIVE") and not self.paused:
                self.paused_left = max(0.0, self.deadline - self.clock())
                self.paused = True
                self._log("pause")

    def resume(self) -> None:
        with self.lock:
            if self.paused:
                self.paused = False
                self.deadline = self.clock() + self.paused_left
                self._log("resume")

    def freeze(self, on: bool = True) -> None:
        with self.lock:
            self.frozen = on
            self._log("freeze", on=on)

    def extend(self, seconds: float) -> None:
        with self.lock:
            if self.phase not in ("PREVIEW", "LIVE"):
                return

            if self.paused:
                self.paused_left += seconds
            else:
                self.deadline += seconds

            self._log("extend", seconds=seconds)

    def reset_timer(self, seconds: Optional[float] = None) -> None:
        with self.lock:
            if self.phase not in ("PREVIEW", "LIVE"):
                return

            if seconds is not None:
                s = seconds
            elif self.phase == "PREVIEW":
                s = self.cfg.preview_seconds
            else:
                s = self.cfg.bid_seconds

            if self.paused:
                self.paused_left = s
            else:
                self.deadline = self.clock() + s

            self._log("reset_timer", seconds=s)

    def set_purse(self, team_id: int, amount: int, by: str = "admin") -> None:
        with self.lock:
            team = self.teams.get(team_id)

            if team is None:
                raise ValueError(f"Unknown team {team_id}")

            self._log(
                "set_purse",
                team=team_id,
                old=team.purse,
                new=amount,
                by=by,
            )

            team.purse = amount

    def set_times(
        self,
        preview: Optional[float] = None,
        bid: Optional[float] = None,
        result: Optional[float] = None,
    ) -> None:
        with self.lock:
            if preview is not None:
                if preview < 0:
                    raise ValueError("preview seconds cannot be negative")
                self.cfg.preview_seconds = preview

            if bid is not None:
                if bid < 0:
                    raise ValueError("bid seconds cannot be negative")
                self.cfg.bid_seconds = bid

            if result is not None:
                if result < 0:
                    raise ValueError("result seconds cannot be negative")
                self.cfg.result_seconds = result

            self._log("set_times", preview=preview, bid=bid, result=result)

    # ------------------------------------------------------------------
    # Persistence / crash recovery
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """
        Complete JSON-safe snapshot.

        Times are stored as offsets from now, not absolute monotonic values,
        because monotonic clock values do not survive process restarts.
        """

        with self.lock:
            now = self.clock()

            return {
                "cfg": {
                    **vars(self.cfg),
                    "tier_base": {
                        str(k): v
                        for k, v in self.cfg.tier_base.items()
                    },
                },
                "teams": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "purse": t.purse,
                        "roster": list(t.roster),
                    }
                    for t in self.teams.values()
                ],
                "cands": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "rating": c.rating,
                        "tier": c.tier,
                        "base_price": c.base_price,
                        "profile": c.profile,
                        "status": c.status,
                        "sold_to": c.sold_to,
                        "sold_price": c.sold_price,
                    }
                    for c in self.cands.values()
                ],
                "order": self.order,
                "phase": self.phase,
                "round_no": self.round_no,
                "current": self.current,
                "manual_mode": self.manual_mode,
                "frozen": self.frozen,
                "paused": self.paused,
                "paused_left": self.paused_left if self.paused else None,
                "seconds_to_deadline": (
                    None
                    if self.phase not in ("PREVIEW", "LIVE", "RESULT")
                    else max(0.0, self.deadline - now)
                ),
                "bids": [
                    {
                        "team_id": b.team_id,
                        "amount": b.amount,
                        "voided": b.voided,
                        "seconds_ago": max(0.0, now - b.at),
                    }
                    for b in self.bids
                ],
                "last_result": self.last_result,
                "done_reason": self.done_reason,
                "saved_at_unix": time.time(),
            }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        clock: Callable[[], float] = time.monotonic,
    ) -> "Auction":
        cfg_data = dict(data["cfg"])

        cfg_data["tier_base"] = {
            int(k): v
            for k, v in cfg_data.get("tier_base", {}).items()
        }

        # Ignore unknown config fields from older snapshots.
        allowed_config_fields = set(Config.__dataclass_fields__.keys())
        cfg_data = {
            k: v
            for k, v in cfg_data.items()
            if k in allowed_config_fields
        }

        cfg = Config(**cfg_data)

        a = cls(
            cfg,
            [
                {
                    "id": t["id"],
                    "name": t["name"],
                    "purse": t["purse"],
                    "roster": list(t.get("roster", [])),
                }
                for t in data["teams"]
            ],
            [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "rating": c["rating"],
                    "tier": c["tier"],
                    "base_price": c["base_price"],
                    "profile": c["profile"],
                }
                for c in data["cands"]
            ],
            clock=clock,
        )

        for t in data["teams"]:
            a.teams[t["id"]].roster = list(t.get("roster", []))

        for c in data["cands"]:
            cand = a.cands[c["id"]]
            cand.status = c["status"]
            cand.sold_to = c["sold_to"]
            cand.sold_price = c["sold_price"]

        a.order = data["order"]
        a.phase = data["phase"]
        a.round_no = data["round_no"]
        a.current = data["current"]
        a.manual_mode = data["manual_mode"]
        a.frozen = data["frozen"]
        a.paused = data["paused"]
        a.last_result = data["last_result"]
        a.done_reason = data["done_reason"]

        now = clock()

        a.bids = [
            Bid(
                team_id=b["team_id"],
                amount=b["amount"],
                at=now - max(0.0, b.get("seconds_ago", 0.0)),
                voided=b["voided"],
            )
            for b in data.get("bids", [])
        ]

        if data["paused"]:
            a.paused_left = data.get("paused_left", 0.0)
        else:
            a.paused_left = 0.0

        if data.get("seconds_to_deadline") is not None:
            a.deadline = now + data["seconds_to_deadline"]
        else:
            a.deadline = 0.0

        a._log("restored", saved_at_unix=data.get("saved_at_unix"))

        return a

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------

    def team_view(self, team_id: int) -> Dict[str, Any]:
        """
        Private view for one captain.
        """

        with self.lock:
            t = self.teams[team_id]

            full = len(t.roster) >= self.cfg.roster_size

            info = {
                "team": t.name,
                "purse": t.purse,
                "roster": len(t.roster),
                "full": full,
            }

            if self.phase in ("LIVE", "AWAITING_HAMMER"):
                mine = any(
                    b.team_id == team_id
                    for b in self._valid_bids()
                )

                if self.leader() == team_id:
                    status = "LEADING"
                elif mine:
                    status = "OUTBID"
                else:
                    status = "INACTIVE"

                price = self.next_price()

                if self.phase == "AWAITING_HAMMER":
                    can = False
                    reason = "Waiting for the auctioneer to close this player."
                    options = []
                else:
                    v = rules.check_bid(
                        price,
                        self.current_bid(),
                        self.current_base(),
                        t.purse,
                        len(t.roster),
                        self.leader() == team_id,
                        self.cfg,
                    )

                    can = v.ok and not self.frozen and not self.paused

                    if can:
                        reason = ""
                    elif self.frozen:
                        reason = "Bids are frozen."
                    elif self.paused:
                        reason = "Paused."
                    else:
                        reason = v.reason

                    # Compute affordability-filtered bid options for the captain UI.
                    if not self.frozen and not self.paused and not full:
                        options = rules.bid_options(
                            self.current_bid(),
                            self.current_base(),
                            t.purse,
                            len(t.roster),
                            self.leader() == team_id,
                            self.cfg,
                        )
                    else:
                        options = []

                info.update(
                    status="FULL" if full else status,
                    next_price=price,
                    can_bid=can,
                    reason=reason,
                    max_bid=rules.max_bid(t.purse, len(t.roster), self.cfg),
                    bid_options=options,
                )

            return info

    def snapshot(self) -> Dict[str, Any]:
        """
        Public view for stage and shared client state.
        """

        with self.lock:
            cand = self.cands.get(self.current) if self.current is not None else None

            leader_id = self.leader()

            return {
                "phase": self.phase,
                "round": self.round_no,
                "paused": self.paused,
                "frozen": self.frozen,
                "manual_mode": self.manual_mode,
                "seconds_left": round(self.time_left(), 1),
                "candidate": (
                    None
                    if cand is None
                    else {
                        "id": cand.id,
                        "name": cand.name,
                        "rating": cand.rating,
                        "tier": cand.tier,
                        "profile": cand.profile,
                        "base_price": (
                            self.current_base()
                            if self.phase != "PREVIEW"
                            else None
                        ),
                    }
                ),
                "current_bid": self.current_bid() if cand else None,
                "leader": (
                    self.teams[leader_id].name
                    if leader_id is not None and leader_id in self.teams
                    else None
                ),
                "next_price": (
                    self.next_price()
                    if self.phase == "LIVE" and cand is not None
                    else None
                ),
                "result": self.last_result,
                "done_reason": self.done_reason,
                "teams": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "purse": t.purse,
                        "roster": len(t.roster),
                    }
                    for t in self.teams.values()
                ],
            }
