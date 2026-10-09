import unittest
from fastapi.testclient import TestClient

from backend.core.auction import Auction
from backend.core.config import Config
from backend.core.loader import load_teams
from .helpers import (
    FakeClock,
    make_candidates,
    make_cfg,
    make_teams,
    make_test_app,
)


class TestFlexibleRosterAndCaptain(unittest.TestCase):
    def test_set_roster_size_in_setup(self):
        clock = FakeClock()
        cfg = make_cfg(roster_size=4)
        teams = [
            {"id": 1, "name": "Team 1", "purse": 10000, "captain": "Capt. Alice"},
            {"id": 2, "name": "Team 2", "purse": 10000, "captain": "Capt. Bob"},
        ]
        candidates = make_candidates(15)
        auction = Auction(cfg=cfg, teams=teams, candidates=candidates, clock=clock)

        self.assertEqual(auction.cfg.roster_size, 4)
        self.assertEqual(auction.phase, "SETUP")

        # Test changing to 3
        res3 = auction.set_roster_size(3)
        self.assertEqual(auction.cfg.roster_size, 3)
        self.assertEqual(res3["roster_size"], 3)
        self.assertEqual(auction.snapshot()["roster_size"], 3)

        # Test changing to 5
        res5 = auction.set_roster_size(5)
        self.assertEqual(auction.cfg.roster_size, 5)
        self.assertEqual(res5["roster_size"], 5)
        self.assertEqual(auction.snapshot()["roster_size"], 5)

        # Test changing to 4
        res4 = auction.set_roster_size(4)
        self.assertEqual(auction.cfg.roster_size, 4)
        self.assertEqual(res4["roster_size"], 4)

    def test_set_roster_size_invalid_values(self):
        clock = FakeClock()
        cfg = make_cfg(roster_size=4)
        teams = make_teams(2)
        candidates = make_candidates(10)
        auction = Auction(cfg=cfg, teams=teams, candidates=candidates, clock=clock)

        for invalid in [0, 1, 2, 6, 10, -1]:
            with self.assertRaises(ValueError):
                auction.set_roster_size(invalid)

    def test_set_roster_size_rejected_after_start(self):
        clock = FakeClock()
        cfg = make_cfg(roster_size=3)
        teams = make_teams(2)
        candidates = make_candidates(10)
        auction = Auction(cfg=cfg, teams=teams, candidates=candidates, clock=clock)

        auction.start()
        self.assertNotEqual(auction.phase, "SETUP")

        with self.assertRaises(ValueError):
            auction.set_roster_size(5)

    def test_captain_name_in_team_and_views(self):
        clock = FakeClock()
        cfg = make_cfg(roster_size=3)
        teams = [
            {"id": 1, "name": "Code Crusaders", "purse": 10000, "captain": "Capt. Devendra"},
            {"id": 2, "name": "Byte Brawlers", "purse": 10000, "captain": "Capt. Radhika"},
        ]
        candidates = make_candidates(10)
        auction = Auction(cfg=cfg, teams=teams, candidates=candidates, clock=clock)

        # Check team models
        self.assertEqual(auction.teams[1].captain, "Capt. Devendra")
        self.assertEqual(auction.teams[2].captain, "Capt. Radhika")

        # Check team_view for captain
        view1 = auction.team_view(1)
        self.assertEqual(view1["captain"], "Capt. Devendra")
        self.assertEqual(view1["roster_size"], 3)
        self.assertEqual(view1["roster"], 0)
        self.assertEqual(view1["squad"], [])

        # Check snapshot for stage display
        snap = auction.snapshot()
        self.assertEqual(snap["roster_size"], 3)
        team_snaps = {t["id"]: t for t in snap["teams"]}
        self.assertEqual(team_snaps[1]["captain"], "Capt. Devendra")
        self.assertEqual(team_snaps[2]["captain"], "Capt. Radhika")

    def test_loader_parses_captain_column_and_fallback(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "teams.csv"
            # With captain column
            csv_path.write_text(
                "id,name,login_code,purse,captain\n"
                "1,Alpha,a1,10000,Leader Alice\n"
                "2,Beta,b2,10000,\n"
            )
            teams = load_teams(str(csv_path))
            self.assertEqual(teams[0]["captain"], "Leader Alice")
            self.assertEqual(teams[1]["captain"], "Capt. Beta")  # Fallback

            # Without captain column at all
            csv_no_cap = Path(tmpdir) / "teams_no_cap.csv"
            csv_no_cap.write_text(
                "id,name,login_code,purse\n"
                "1,Gamma,g1,10000\n"
            )
            teams_no_cap = load_teams(str(csv_no_cap))
            self.assertEqual(teams_no_cap[0]["captain"], "Capt. Gamma")

    def test_admin_api_set_roster_size(self):
        app, state, tmp = make_test_app(
            team_count=2,
            candidate_count=15,
            roster_size=4,
            admin_pin="test-admin",
        )
        self.addCleanup(tmp.cleanup)
        self.addCleanup(state.store.close)
        client = TestClient(app)

        admin_pin = state.admin_pin

        # Unauthorized request
        res = client.post("/api/admin/set-roster-size", json={"size": 5})
        self.assertEqual(res.status_code, 401)

        # Valid admin request to set 5
        res = client.post(
            "/api/admin/set-roster-size",
            headers={"X-Admin-Pin": admin_pin},
            json={"size": 5},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])
        self.assertEqual(state.auction.cfg.roster_size, 5)

        # Valid admin request to set 3
        res = client.post(
            "/api/admin/set-roster-size",
            headers={"X-Admin-Pin": admin_pin},
            json={"size": 3},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(state.auction.cfg.roster_size, 3)

        # Invalid size rejected with 400
        res = client.post(
            "/api/admin/set-roster-size",
            headers={"X-Admin-Pin": admin_pin},
            json={"size": 7},
        )
        self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
