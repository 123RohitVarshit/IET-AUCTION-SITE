import unittest

from backend.core.config import Config
from backend.core import rules


class IncrementTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()

    def test_increment_below_threshold_is_100(self):
        self.assertEqual(rules.increment(1499, self.cfg), 100)

    def test_increment_at_threshold_is_250(self):
        self.assertEqual(rules.increment(1500, self.cfg), 250)

    def test_increment_above_threshold_is_250(self):
        self.assertEqual(rules.increment(2000, self.cfg), 250)


class NextPriceTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()

    def test_first_bid_is_base_price(self):
        self.assertEqual(rules.next_price(None, 1000, self.cfg), 1000)

    def test_next_bid_below_threshold_adds_100(self):
        self.assertEqual(rules.next_price(1400, 1000, self.cfg), 1500)

    def test_next_bid_at_threshold_adds_250(self):
        self.assertEqual(rules.next_price(1500, 1000, self.cfg), 1750)

    def test_next_bid_above_threshold_adds_250(self):
        self.assertEqual(rules.next_price(2000, 1000, self.cfg), 2250)


class RoundBasePriceTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()

    def test_round_one_keeps_base_price(self):
        self.assertEqual(rules.round_base_price(1000, 1, self.cfg), 1000)
        self.assertEqual(rules.round_base_price(600, 1, self.cfg), 600)
        self.assertEqual(rules.round_base_price(400, 1, self.cfg), 400)
        self.assertEqual(rules.round_base_price(200, 1, self.cfg), 200)

    def test_round_two_halves_base_price(self):
        self.assertEqual(rules.round_base_price(1000, 2, self.cfg), 500)
        self.assertEqual(rules.round_base_price(600, 2, self.cfg), 300)
        self.assertEqual(rules.round_base_price(400, 2, self.cfg), 200)
        self.assertEqual(rules.round_base_price(200, 2, self.cfg), 100)

    def test_round_three_uses_rounding(self):
        # 1000 * 0.25 = 250, rounded to nearest 100 => 300
        self.assertEqual(rules.round_base_price(1000, 3, self.cfg), 300)

    def test_price_never_below_floor(self):
        # 1000 * 0.5^4 = 62.5, rounds/clamps to 100
        self.assertEqual(rules.round_base_price(1000, 5, self.cfg), 100)

        # 200 round 3 = 50, clamps to floor 100
        self.assertEqual(rules.round_base_price(200, 3, self.cfg), 100)


class ReserveFormulaTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()

    def test_max_bid_with_zero_players_acquired(self):
        # purse 10,000, buying first player leaves 3 empty slots
        # max bid = 10,000 - 3 * 100 = 9,700
        self.assertEqual(rules.max_bid(10_000, 0, self.cfg), 9_700)

    def test_max_bid_with_two_players_acquired(self):
        # purse 3,000, buying third player leaves 1 empty slot
        # max bid = 3,000 - 1 * 100 = 2,900
        self.assertEqual(rules.max_bid(3_000, 2, self.cfg), 2_900)

    def test_max_bid_with_three_players_acquired(self):
        # purse 500, buying fourth player leaves 0 empty slots
        # max bid = 500
        self.assertEqual(rules.max_bid(500, 3, self.cfg), 500)

    def test_max_bid_never_negative(self):
        self.assertEqual(rules.max_bid(0, 0, self.cfg), 0)


class CheckBidTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()

    def test_successful_first_bid(self):
        verdict = rules.check_bid(
            price=1000,
            current_bid=None,
            base=1000,
            purse=10_000,
            roster_count=0,
            is_leader=False,
            cfg=self.cfg,
        )

        self.assertTrue(verdict.ok)
        self.assertEqual(verdict.code, "OK")

    def test_successful_followup_bid(self):
        verdict = rules.check_bid(
            price=1100,
            current_bid=1000,
            base=1000,
            purse=10_000,
            roster_count=0,
            is_leader=False,
            cfg=self.cfg,
        )

        self.assertTrue(verdict.ok)

    def test_reject_full_squad(self):
        verdict = rules.check_bid(
            price=1000,
            current_bid=None,
            base=1000,
            purse=10_000,
            roster_count=4,
            is_leader=False,
            cfg=self.cfg,
        )

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.code, "ROSTER_FULL")

    def test_reject_already_leader(self):
        verdict = rules.check_bid(
            price=1000,
            current_bid=None,
            base=1000,
            purse=10_000,
            roster_count=0,
            is_leader=True,
            cfg=self.cfg,
        )

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.code, "ALREADY_LEADING")

    def test_reject_bid_below_minimum(self):
        # Bid below the base price should be rejected (STALE)
        verdict = rules.check_bid(
            price=800,
            current_bid=None,
            base=1000,
            purse=10_000,
            roster_count=0,
            is_leader=False,
            cfg=self.cfg,
        )

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.code, "STALE")

    def test_accept_jump_bid_above_minimum(self):
        # A jump bid (+500 on top of base) should be accepted
        verdict = rules.check_bid(
            price=1500,
            current_bid=None,
            base=1000,
            purse=10_000,
            roster_count=0,
            is_leader=False,
            cfg=self.cfg,
        )

        self.assertTrue(verdict.ok)
        self.assertEqual(verdict.code, "OK")

    def test_reject_stale_followup_bid(self):
        # Bidding the same amount as current bid (no increase) should be rejected
        verdict = rules.check_bid(
            price=1000,
            current_bid=1000,
            base=1000,
            purse=10_000,
            roster_count=0,
            is_leader=False,
            cfg=self.cfg,
        )

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.code, "STALE")

    def test_reject_insufficient_purse(self):
        verdict = rules.check_bid(
            price=200,
            current_bid=None,
            base=200,
            purse=50,
            roster_count=3,
            is_leader=False,
            cfg=self.cfg,
        )

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.code, "PURSE")

    def test_reject_reserve_limit(self):
        # Purse 300, no players bought.
        # Reserve requires keeping 3 * 100 = 300.
        # Max bid is therefore 0.
        verdict = rules.check_bid(
            price=200,
            current_bid=None,
            base=200,
            purse=300,
            roster_count=0,
            is_leader=False,
            cfg=self.cfg,
        )

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.code, "RESERVE")


if __name__ == "__main__":
    unittest.main()