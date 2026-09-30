import threading
import unittest

from backend.core.auction import Auction
from backend.core.config import Config


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def make_cfg(**overrides) -> Config:
    defaults = dict(
        roster_size=1,
        purse=10_000,
        preview_seconds=0,
        bid_seconds=30,
        result_seconds=8,
        anti_snipe_seconds=8,
        undo_extend_seconds=10,
        auto_advance=True,
        max_rounds=5,
    )

    defaults.update(overrides)

    return Config(**defaults)


def make_teams(count: int, purse: int = 10_000):
    return [
        {
            "id": i,
            "name": f"Team {i}",
            "purse": purse,
        }
        for i in range(1, count + 1)
    ]


def make_candidates(count: int, base_price: int = 1000, tier: int = 1):
    return [
        {
            "id": i,
            "name": f"Player {i}",
            "rating": 1500,
            "tier": tier,
            "base_price": base_price,
        }
        for i in range(1, count + 1)
    ]


def make_ready_auction(
    clock,
    team_count=2,
    candidate_count=2,
    base_price=1000,
    tier=1,
    **cfg_overrides,
):
    cfg = make_cfg(**cfg_overrides)

    teams = make_teams(team_count)
    candidates = make_candidates(candidate_count, base_price=base_price, tier=tier)

    auction = Auction(cfg, teams, candidates, clock=clock)
    auction.start()

    return auction


class SetupTests(unittest.TestCase):
    def test_setup_report_ok_and_start(self):
        clock = FakeClock()
        auction = make_ready_auction(clock, team_count=2, candidate_count=2)

        self.assertEqual(auction.phase, "IDLE")

    def test_setup_report_fails_when_candidates_short(self):
        clock = FakeClock()

        cfg = make_cfg(roster_size=1)
        teams = make_teams(2)
        candidates = make_candidates(1)

        auction = Auction(cfg, teams, candidates, clock=clock)

        report = auction.setup_report()

        self.assertFalse(report["ok"])
        self.assertEqual(report["short_by"], 1)

        with self.assertRaises(ValueError):
            auction.start()

    def test_start_twice_raises(self):
        clock = FakeClock()
        auction = make_ready_auction(clock)

        with self.assertRaises(ValueError):
            auction.start()



class BasicBiddingTests(unittest.TestCase):
    def test_first_bid_and_auto_sell(self):
        clock = FakeClock()
        auction = make_ready_auction(clock)

        auction.next_candidate()

        self.assertEqual(auction.phase, "LIVE")
        self.assertEqual(auction.current, 1)

        verdict = auction.place_bid(1, 1000)

        self.assertTrue(verdict.ok)
        self.assertEqual(auction.leader(), 1)
        self.assertEqual(auction.current_bid(), 1000)

        clock.advance(31)
        auction.tick()

        self.assertEqual(auction.phase, "RESULT")
        self.assertEqual(auction.last_result["outcome"], "SOLD")
        self.assertEqual(auction.last_result["team"], 1)
        self.assertEqual(auction.last_result["price"], 1000)

        team = auction.teams[1]

        self.assertEqual(team.purse, 9000)
        self.assertEqual(team.roster, [1])

        candidate = auction.cands[1]

        self.assertEqual(candidate.status, "SOLD")
        self.assertEqual(candidate.sold_to, 1)
        self.assertEqual(candidate.sold_price, 1000)

    def test_stale_bid_rejected(self):
        clock = FakeClock()
        auction = make_ready_auction(clock)

        auction.next_candidate()

        first = auction.place_bid(1, 1000)
        self.assertTrue(first.ok)

        stale = auction.place_bid(2, 1000)
        self.assertFalse(stale.ok)
        self.assertEqual(stale.code, "STALE")

        good = auction.place_bid(2, 1100)
        self.assertTrue(good.ok)
        self.assertEqual(auction.leader(), 2)

    def test_leader_cannot_bid_again(self):
        clock = FakeClock()
        auction = make_ready_auction(clock)

        auction.next_candidate()

        first = auction.place_bid(1, 1000)
        self.assertTrue(first.ok)

        again = auction.place_bid(1, 1100)

        self.assertFalse(again.ok)
        self.assertEqual(again.code, "ALREADY_LEADING")

    def test_freeze_blocks_bids(self):
        clock = FakeClock()
        auction = make_ready_auction(clock)

        auction.next_candidate()
        auction.freeze(True)

        verdict = auction.place_bid(1, 1000)

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.code, "FROZEN")

        auction.freeze(False)

        verdict = auction.place_bid(1, 1000)

        self.assertTrue(verdict.ok)


class ReserveAndPurseTests(unittest.TestCase):
    def test_reserve_limit_blocks_overdraft(self):
        clock = FakeClock()

        auction = make_ready_auction(
            clock,
            team_count=1,
            candidate_count=4,
            base_price=200,
            tier=4,
            roster_size=4,
        )

        auction.next_candidate()

        # Setup started with default 10,000 purse.
        # Now simulate a corrupted/edited purse.
        auction.set_purse(1, 300)

        verdict = auction.place_bid(1, 200)

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.code, "RESERVE")

    def test_purse_edit_is_logged(self):
        clock = FakeClock()
        auction = make_ready_auction(clock)

        auction.set_purse(1, 1234)

        events = [e for e in auction.events if e["kind"] == "set_purse"]

        self.assertEqual(len(events), 1)

        event = events[0]

        self.assertEqual(event["team"], 1)
        self.assertEqual(event["old"], 10_000)
        self.assertEqual(event["new"], 1234)


class TimerTests(unittest.TestCase):
    def test_anti_snipe_resets_clock(self):
        clock = FakeClock()
        auction = make_ready_auction(clock)

        auction.next_candidate()

        auction.place_bid(1, 1000)

        # Original deadline is 1030.
        # Move to 1025, leaving 5 seconds.
        clock.advance(25)

        verdict = auction.place_bid(2, 1100)

        self.assertTrue(verdict.ok)

        # Deadline should reset to now + 8 seconds.
        self.assertAlmostEqual(auction.time_left(), 8.0, delta=0.001)

    def test_pause_and_resume(self):
        clock = FakeClock()
        auction = make_ready_auction(clock)

        auction.next_candidate()

        before = auction.time_left()

        auction.pause()

        clock.advance(5)

        self.assertAlmostEqual(auction.time_left(), before, delta=0.001)

        auction.resume()

        self.assertAlmostEqual(auction.time_left(), before, delta=0.001)


class UndoTests(unittest.TestCase):
    def test_undo_last_bid_while_live(self):
        clock = FakeClock()
        auction = make_ready_auction(clock)

        auction.next_candidate()

        auction.place_bid(1, 1000)
        auction.place_bid(2, 1100)

        ok, message = auction.undo_last_bid()

        self.assertTrue(ok)
        self.assertEqual(message, "Last bid removed.")

        self.assertEqual(auction.leader(), 1)
        self.assertEqual(auction.current_bid(), 1000)
        self.assertEqual(auction.next_price(), 1100)

    def test_undo_sale_reverses_finalized_sale(self):
        clock = FakeClock()
        auction = make_ready_auction(clock)

        auction.next_candidate()
        auction.place_bid(1, 1000)

        clock.advance(31)
        auction.tick()

        self.assertEqual(auction.phase, "RESULT")
        self.assertEqual(auction.last_result["outcome"], "SOLD")

        team = auction.teams[1]

        self.assertEqual(team.purse, 9000)
        self.assertEqual(team.roster, [1])

        ok, message = auction.undo_last_bid()

        self.assertTrue(ok)
        self.assertEqual(message, "Sale reversed. Bidding reopened.")

        self.assertEqual(team.purse, 10_000)
        self.assertEqual(team.roster, [])

        self.assertEqual(auction.phase, "LIVE")
        self.assertEqual(auction.cands[1].status, "LIVE")
        self.assertIsNone(auction.cands[1].sold_to)
        self.assertIsNone(auction.cands[1].sold_price)

        self.assertAlmostEqual(auction.time_left(), 10.0, delta=0.001)


class RoundTests(unittest.TestCase):
    def test_unsold_player_returns_next_round_at_discount(self):
        clock = FakeClock()

        auction = make_ready_auction(
            clock,
            team_count=1,
            candidate_count=1,
            base_price=1000,
            result_seconds=1,
        )

        auction.next_candidate()

        # Let LIVE expire with no bids.
        clock.advance(31)
        auction.tick()

        self.assertEqual(auction.phase, "RESULT")
        self.assertEqual(auction.last_result["outcome"], "UNSOLD")

        # Let RESULT expire and auto-advance.
        clock.advance(2)
        auction.tick()

        self.assertEqual(auction.round_no, 2)
        self.assertEqual(auction.phase, "LIVE")
        self.assertEqual(auction.current_base(), 500)

    def test_max_rounds_reached_done(self):
        clock = FakeClock()

        auction = make_ready_auction(
            clock,
            team_count=1,
            candidate_count=1,
            base_price=1000,
            result_seconds=1,
            max_rounds=1,
        )

        auction.next_candidate()

        clock.advance(31)
        auction.tick()

        self.assertEqual(auction.last_result["outcome"], "UNSOLD")

        clock.advance(2)
        auction.tick()

        self.assertEqual(auction.phase, "DONE")
        self.assertIn("Max rounds reached", auction.done_reason)


class ViewTests(unittest.TestCase):
    def test_snapshot_and_team_view_during_live(self):
        clock = FakeClock()
        auction = make_ready_auction(clock)

        auction.next_candidate()

        snapshot = auction.snapshot()

        self.assertEqual(snapshot["phase"], "LIVE")
        self.assertEqual(snapshot["candidate"]["id"], 1)
        self.assertEqual(snapshot["next_price"], 1000)

        view = auction.team_view(1)

        self.assertEqual(view["team"], "Team 1")
        self.assertEqual(view["purse"], 10_000)
        self.assertEqual(view["next_price"], 1000)
        self.assertTrue(view["can_bid"])
        self.assertEqual(view["reason"], "")


class SnapshotRestoreTests(unittest.TestCase):
    def test_to_dict_from_dict_restores_state(self):
        clock = FakeClock()
        auction = make_ready_auction(clock)

        auction.next_candidate()
        auction.place_bid(1, 1000)

        data = auction.to_dict()

        restored_clock = FakeClock(start=5000.0)
        restored = Auction.from_dict(data, clock=restored_clock)

        self.assertEqual(restored.phase, auction.phase)
        self.assertEqual(restored.round_no, auction.round_no)
        self.assertEqual(restored.current, auction.current)
        self.assertEqual(restored.leader(), auction.leader())
        self.assertEqual(restored.current_bid(), auction.current_bid())

        self.assertEqual(len(restored.bids), 1)
        self.assertEqual(restored.bids[0].team_id, 1)
        self.assertEqual(restored.bids[0].amount, 1000)

        self.assertEqual(restored.teams[1].purse, 10_000)
        self.assertEqual(restored.teams[1].roster, [])


class ConcurrencyTests(unittest.TestCase):
    def test_40_simultaneous_bids_exactly_one_wins(self):
        clock = FakeClock()

        auction = make_ready_auction(
            clock,
            team_count=40,
            candidate_count=40,
            base_price=1000,
        )

        auction.next_candidate()

        results = []
        results_lock = threading.Lock()

        barrier = threading.Barrier(40)

        def worker(team_id):
            barrier.wait()
            verdict = auction.place_bid(team_id, 1000)

            with results_lock:
                results.append(verdict.ok)

        threads = [
            threading.Thread(target=worker, args=(team_id,))
            for team_id in range(1, 41)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(sum(results), 1)
        self.assertEqual(len(results), 40)


if __name__ == "__main__":
    unittest.main()
