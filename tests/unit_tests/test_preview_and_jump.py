import unittest

from .helpers import make_started_auction


class PreviewPhaseTests(unittest.TestCase):
    def test_preview_blocks_bids_and_hides_base_price(self):
        auction, clock = make_started_auction(
            preview_seconds=10,
            bid_seconds=30,
            base_price=1000,
        )

        auction.next_candidate()

        self.assertEqual(auction.phase, "PREVIEW")

        # Bids must be rejected during PREVIEW.
        verdict = auction.place_bid(1, 1000)
        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.code, "NOT_LIVE")

        # Base price must be hidden during PREVIEW.
        snap = auction.snapshot()
        self.assertIsNotNone(snap["candidate"])
        self.assertIsNone(snap["candidate"]["base_price"])

        # Move past PREVIEW.
        clock.advance(11)
        auction.tick()

        self.assertEqual(auction.phase, "LIVE")

        # Base price is revealed in LIVE.
        snap = auction.snapshot()
        self.assertEqual(snap["candidate"]["base_price"], 1000)

        # Bids are allowed now.
        verdict = auction.place_bid(1, 1000)
        self.assertTrue(verdict.ok)

    def test_team_view_does_not_expose_bidding_before_live(self):
        auction, clock = make_started_auction(
            preview_seconds=10,
            base_price=1000,
        )

        auction.next_candidate()

        view = auction.team_view(1)

        # During PREVIEW, private bidding state is not included.
        self.assertNotIn("next_price", view)
        self.assertNotIn("can_bid", view)

        clock.advance(11)
        auction.tick()

        view = auction.team_view(1)

        self.assertEqual(view["next_price"], 1000)
        self.assertTrue(view["can_bid"])


class AdminJumpTests(unittest.TestCase):
    def test_jump_to_queued_player(self):
        auction, clock = make_started_auction(
            team_count=2,
            candidate_count=3,
        )

        auction.next_candidate()
        self.assertEqual(auction.current, 1)

        auction.next_candidate(candidate_id=2)

        self.assertEqual(auction.current, 2)
        self.assertEqual(auction.cands[1].status, "QUEUED")
        self.assertEqual(auction.cands[2].status, "LIVE")

    def test_jump_rejected_when_current_player_has_bids(self):
        auction, clock = make_started_auction(
            team_count=2,
            candidate_count=3,
        )

        auction.next_candidate()

        verdict = auction.place_bid(1, 1000)
        self.assertTrue(verdict.ok)

        with self.assertRaises(ValueError):
            auction.next_candidate(candidate_id=2)

    def test_jump_rejected_to_sold_player(self):
        auction, clock = make_started_auction(
            team_count=2,
            candidate_count=3,
            roster_size=1,
        )

        # Sell player 1 to team 1.
        auction.next_candidate()
        auction.place_bid(1, 1000)

        clock.advance(31)
        auction.tick()

        self.assertEqual(auction.last_result["outcome"], "SOLD")

        # Move to player 2.
        auction.next_candidate()
        self.assertEqual(auction.current, 2)

        # Sell player 2 to team 2.
        auction.place_bid(2, 1000)

        clock.advance(31)
        auction.tick()

        self.assertEqual(auction.last_result["outcome"], "SOLD")

        # Move to player 3.
        auction.next_candidate()
        self.assertEqual(auction.current, 3)

        # Jumping back to sold player 2 must fail.
        with self.assertRaises(ValueError):
            auction.next_candidate(candidate_id=2)

    def test_jump_to_unsold_player_is_allowed(self):
        auction, clock = make_started_auction(
            team_count=1,
            candidate_count=2,
            roster_size=1,
            result_seconds=1,
        )

        # Let player 1 become UNSOLD.
        auction.next_candidate()

        clock.advance(31)
        auction.tick()

        self.assertEqual(auction.last_result["outcome"], "UNSOLD")

        # Move to player 2.
        auction.next_candidate()
        self.assertEqual(auction.current, 2)

        # Player 1 is now UNSOLD and may be jumped to.
        auction.next_candidate(candidate_id=1)

        self.assertEqual(auction.current, 1)
        self.assertEqual(auction.cands[1].status, "LIVE")


if __name__ == "__main__":
    unittest.main()