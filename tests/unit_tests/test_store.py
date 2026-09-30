import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.persistence.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.db_path = Path(self.tmp.name) / "test.db"
        self.store = Store(self.db_path)

    def tearDown(self):
        self.store.close()

    def test_save_and_load_state(self):
        state = {
            "phase": "LIVE",
            "round_no": 2,
            "current": 7,
        }

        self.store.save_state(state)

        loaded = self.store.load_state()

        self.assertEqual(loaded, state)

    def test_load_state_returns_none_when_empty(self):
        self.assertIsNone(self.store.load_state())

    def test_clear_state(self):
        self.store.save_state({"phase": "IDLE"})
        self.store.clear_state()

        self.assertIsNone(self.store.load_state())

    def test_record_and_fetch_bids(self):
        self.store.record_bid(
            candidate_id=1,
            team_id=2,
            amount=1000,
            status="ACCEPTED",
            reason="OK",
        )

        self.store.record_bid(
            candidate_id=1,
            team_id=3,
            amount=900,
            status="REJECTED",
            reason="STALE",
        )

        bids = self.store.fetch_bids()

        self.assertEqual(len(bids), 2)

        self.assertEqual(bids[0]["candidate_id"], 1)
        self.assertEqual(bids[0]["team_id"], 2)
        self.assertEqual(bids[0]["amount"], 1000)
        self.assertEqual(bids[0]["status"], "ACCEPTED")

        self.assertEqual(bids[1]["team_id"], 3)
        self.assertEqual(bids[1]["status"], "REJECTED")

    def test_log_and_fetch_admin_actions(self):
        self.store.log_admin_action(
            "pause",
            {"by": "admin"},
        )

        self.store.log_admin_action(
            "set_purse",
            {
                "team_id": 1,
                "old": 10000,
                "new": 9000,
            },
        )

        actions = self.store.fetch_admin_actions()

        self.assertEqual(len(actions), 2)

        self.assertEqual(actions[0]["action"], "pause")
        self.assertEqual(actions[1]["action"], "set_purse")


if __name__ == "__main__":
    unittest.main()