import random
import unittest

from backend.core import rules
from backend.core.auction import Auction

from .helpers import (
    FakeClock,
    make_candidates,
    make_cfg,
    make_teams,
)


class MonteCarloSimulationTests(unittest.TestCase):
    def _run_seed(self, seed: int) -> None:
        rng = random.Random(seed)

        cfg = make_cfg(
            roster_size=2,
            preview_seconds=0,
            bid_seconds=10,
            result_seconds=1,
            max_rounds=5,
        )

        teams = make_teams(4)
        candidates = make_candidates(
            8,
            base_price=200,
            tier=4,
        )

        clock = FakeClock()

        auction = Auction(
            cfg,
            teams,
            candidates,
            clock=clock,
        )

        auction.start()
        auction.next_candidate()

        steps = 0
        max_steps = 20_000

        while auction.phase != "DONE" and steps < max_steps:
            steps += 1

            if auction.phase == "IDLE":
                auction.next_candidate()

            elif auction.phase == "PREVIEW":
                clock.advance(cfg.preview_seconds + 0.1)
                auction.tick()

            elif auction.phase == "LIVE":
                # If there is no bid yet, force one random team that still
                # needs players and can legally afford the next price.
                if auction.current_bid() is None:
                    price = auction.next_price()

                    eligible_team_ids = []

                    for team in auction.teams.values():
                        if len(team.roster) >= cfg.roster_size:
                            continue

                        if rules.max_bid(team.purse, len(team.roster), cfg) >= price:
                            eligible_team_ids.append(team.id)

                    if eligible_team_ids:
                        team_id = rng.choice(eligible_team_ids)
                        verdict = auction.place_bid(team_id, price)

                        self.assertTrue(
                            verdict.ok,
                            f"Seed {seed}: unexpected bid rejection: {verdict}",
                        )

                clock.advance(cfg.bid_seconds + 0.1)
                auction.tick()

            elif auction.phase == "RESULT":
                clock.advance(cfg.result_seconds + 0.1)
                auction.tick()

            elif auction.phase == "AWAITING_HAMMER":
                # This simulation runs in auto mode, so this should not happen.
                self.fail(f"Seed {seed}: entered AWAITING_HAMMER in auto mode")

            else:
                break

        self.assertEqual(
            auction.phase,
            "DONE",
            f"Seed {seed}: auction did not finish. phase={auction.phase}",
        )

        for team in auction.teams.values():
            self.assertEqual(
                len(team.roster),
                cfg.roster_size,
                f"Seed {seed}: team {team.id} roster is not full",
            )

            self.assertGreaterEqual(
                team.purse,
                0,
                f"Seed {seed}: team {team.id} has negative purse",
            )

    def test_random_bots_finish_with_full_rosters_seed_1(self):
        self._run_seed(1)

    def test_random_bots_finish_with_full_rosters_seed_2(self):
        self._run_seed(2)

    def test_random_bots_finish_with_full_rosters_seed_3(self):
        self._run_seed(3)

    def test_random_bots_finish_with_full_rosters_seed_4(self):
        self._run_seed(4)

    def test_random_bots_finish_with_full_rosters_seed_5(self):
        self._run_seed(5)


if __name__ == "__main__":
    unittest.main()