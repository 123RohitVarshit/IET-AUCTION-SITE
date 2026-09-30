import unittest

from .helpers import make_started_auction


class ManualModeTests(unittest.TestCase):
    def test_manual_mode_timer_expiry_enters_awaiting_hammer(self):
        auction, clock = make_started_auction(preview_seconds=0)

        auction.set_manual_mode(True)
        auction.next_candidate()

        verdict = auction.place_bid(1, 1000)
        self.assertTrue(verdict.ok)

        clock.advance(31)
        auction.tick()

        self.assertEqual(auction.phase, "AWAITING_HAMMER")
        self.assertEqual(auction.last_result, None)

        # Bidding must be locked while awaiting hammer.
        verdict = auction.place_bid(2, 1100)
        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.code, "NOT_LIVE")

    def test_manual_mode_confirm_sale_after_timer_expiry(self):
        auction, clock = make_started_auction(preview_seconds=0)

        auction.set_manual_mode(True)
        auction.next_candidate()

        verdict = auction.place_bid(1, 1000)
        self.assertTrue(verdict.ok)

        clock.advance(31)
        auction.tick()

        self.assertEqual(auction.phase, "AWAITING_HAMMER")

        auction.confirm_sale()

        self.assertEqual(auction.phase, "RESULT")
        self.assertEqual(auction.last_result["outcome"], "SOLD")
        self.assertEqual(auction.last_result["team"], 1)
        self.assertEqual(auction.last_result["price"], 1000)

    def test_manual_mode_early_hammer_before_timer_expiry(self):
        auction, clock = make_started_auction(preview_seconds=0)

        auction.set_manual_mode(True)
        auction.next_candidate()

        verdict = auction.place_bid(1, 1000)
        self.assertTrue(verdict.ok)

        # Admin sells early, without waiting for the clock.
        auction.confirm_sale()

        self.assertEqual(auction.phase, "RESULT")
        self.assertEqual(auction.last_result["outcome"], "SOLD")

    def test_manual_mode_mark_unsold_discards_bids_without_charging(self):
        auction, clock = make_started_auction(preview_seconds=0)

        auction.set_manual_mode(True)
        auction.next_candidate()

        verdict = auction.place_bid(1, 1000)
        self.assertTrue(verdict.ok)

        before_purse = auction.teams[1].purse

        auction.mark_unsold()

        self.assertEqual(auction.phase, "RESULT")
        self.assertEqual(auction.last_result["outcome"], "UNSOLD")

        # No money should be deducted.
        self.assertEqual(auction.teams[1].purse, before_purse)

        # Candidate should be unsold.
        candidate = auction.cands[1]
        self.assertEqual(candidate.status, "UNSOLD")
        self.assertIsNone(candidate.sold_to)
        self.assertIsNone(candidate.sold_price)

        # All bids should be void.
        self.assertEqual(auction._valid_bids(), [])

    def test_confirm_sale_requires_at_least_one_bid(self):
        auction, clock = make_started_auction(preview_seconds=0)

        auction.set_manual_mode(True)
        auction.next_candidate()

        with self.assertRaises(ValueError):
            auction.confirm_sale()

    def test_mark_unsold_works_with_no_bids(self):
        auction, clock = make_started_auction(preview_seconds=0)

        auction.set_manual_mode(True)
        auction.next_candidate()

        auction.mark_unsold()

        self.assertEqual(auction.phase, "RESULT")
        self.assertEqual(auction.last_result["outcome"], "UNSOLD")

    def test_mid_event_toggle_to_manual_mode(self):
        auction, clock = make_started_auction(preview_seconds=0)

        auction.next_candidate()

        verdict = auction.place_bid(1, 1000)
        self.assertTrue(verdict.ok)

        # Switch to manual mode before timer expires.
        auction.set_manual_mode(True)

        clock.advance(31)
        auction.tick()

        # Should not auto-sell now.
        self.assertEqual(auction.phase, "AWAITING_HAMMER")

        auction.confirm_sale()

        self.assertEqual(auction.phase, "RESULT")
        self.assertEqual(auction.last_result["outcome"], "SOLD")

    def test_cannot_skip_hammer_when_bids_exist(self):
        auction, clock = make_started_auction(preview_seconds=0)

        auction.set_manual_mode(True)
        auction.next_candidate()

        verdict = auction.place_bid(1, 1000)
        self.assertTrue(verdict.ok)

        clock.advance(31)
        auction.tick()

        self.assertEqual(auction.phase, "AWAITING_HAMMER")

        with self.assertRaises(ValueError):
            auction.next_candidate()


if __name__ == "__main__":
    unittest.main()