import unittest

from fastapi.testclient import TestClient

from .helpers import make_test_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.app, self.state, self.tmp = make_test_app(
            team_count=2,
            candidate_count=2,
            roster_size=1,
            admin_pin="test-admin",
        )

        # Cleanup order matters on Windows:
        # close SQLite before removing the temporary directory.
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.state.store.close)

        self.client = TestClient(self.app)

        self.admin_headers = {
            "x-admin-pin": "test-admin",
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def admin_start_and_next(self):
        response = self.client.post(
            "/api/admin/start",
            headers=self.admin_headers,
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            "/api/admin/next",
            headers=self.admin_headers,
            json={},
        )
        self.assertEqual(response.status_code, 200)

    def captain_login(self, team_id: int = 1, login_code: str = "code1") -> str:
        response = self.client.post(
            "/api/captain/login",
            json={
                "team_id": team_id,
                "login_code": login_code,
            },
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("token", data)

        return data["token"]

    # ------------------------------------------------------------------
    # Basic endpoints
    # ------------------------------------------------------------------

    def test_health_endpoint(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["status"], "ok")
        self.assertIn("phase", data)

    def test_setup_report_is_ok(self):
        response = self.client.get("/api/setup/report")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue(data["ok"])
        self.assertEqual(data["teams"], 2)
        self.assertEqual(data["candidates"], 2)
        self.assertEqual(data["roster_size"], 1)
        self.assertEqual(data["needed"], 2)

    def test_stage_state_before_start(self):
        response = self.client.get("/api/stage/state")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["phase"], "SETUP")
        self.assertIsNone(data["candidate"])

    # ------------------------------------------------------------------
    # Admin auth
    # ------------------------------------------------------------------

    def test_admin_endpoint_requires_pin(self):
        response = self.client.post("/api/admin/start")

        self.assertEqual(response.status_code, 401)

    def test_admin_endpoint_rejects_wrong_pin(self):
        response = self.client.post(
            "/api/admin/start",
            headers={
                "x-admin-pin": "wrong-pin",
            },
        )

        self.assertEqual(response.status_code, 401)

    # ------------------------------------------------------------------
    # Admin flow
    # ------------------------------------------------------------------

    def test_admin_start_and_next_moves_to_live(self):
        self.admin_start_and_next()

        response = self.client.get("/api/stage/state")
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["phase"], "LIVE")
        self.assertEqual(data["candidate"]["id"], 1)
        self.assertEqual(data["candidate"]["base_price"], 200)

    def test_admin_set_purse(self):
        response = self.client.post(
            "/api/admin/set-purse",
            headers=self.admin_headers,
            json={
                "team_id": 1,
                "amount": 5000,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.state.auction.teams[1].purse, 5000)

    # ------------------------------------------------------------------
    # Captain auth and bidding
    # ------------------------------------------------------------------

    def test_captain_login_rejects_bad_code(self):
        response = self.client.post(
            "/api/captain/login",
            json={
                "team_id": 1,
                "login_code": "wrong-code",
            },
        )

        self.assertEqual(response.status_code, 401)

    def test_captain_view_requires_token(self):
        response = self.client.get("/api/captain/view")

        self.assertEqual(response.status_code, 401)

    def test_captain_login_view_and_bid(self):
        self.admin_start_and_next()

        token = self.captain_login()

        headers = {
            "x-team-token": token,
        }

        response = self.client.get(
            "/api/captain/view",
            headers=headers,
        )

        self.assertEqual(response.status_code, 200)

        view = response.json()

        self.assertEqual(view["team"], "Team 1")
        self.assertEqual(view["next_price"], 200)
        self.assertTrue(view["can_bid"])

        response = self.client.post(
            "/api/captain/bid",
            headers=headers,
            json={
                "price": 200,
            },
        )

        self.assertEqual(response.status_code, 200)

        result = response.json()

        self.assertTrue(result["ok"])
        self.assertEqual(result["code"], "OK")

        # Stage state should now show the bid.
        response = self.client.get("/api/stage/state")
        data = response.json()

        self.assertEqual(data["current_bid"], 200)
        self.assertEqual(data["leader"], "Team 1")

    # ------------------------------------------------------------------
    # CSV exports
    # ------------------------------------------------------------------

    def test_csv_exports(self):
        self.admin_start_and_next()

        token = self.captain_login()

        response = self.client.post(
            "/api/captain/bid",
            headers={
                "x-team-token": token,
            },
            json={
                "price": 200,
            },
        )

        self.assertEqual(response.status_code, 200)

        # Bids CSV
        response = self.client.get(
            "/api/admin/export/bids.csv",
            headers=self.admin_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/csv"))
        self.assertIn("team_id", response.text)
        self.assertIn("200", response.text)

        # Squads CSV
        response = self.client.get(
            "/api/admin/export/squads.csv",
            headers=self.admin_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/csv"))
        self.assertIn("Team 1", response.text)

        # Admin actions CSV
        response = self.client.get(
            "/api/admin/export/admin-actions.csv",
            headers=self.admin_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/csv"))
        self.assertIn("start", response.text)
        self.assertIn("next_candidate", response.text)


if __name__ == "__main__":
    unittest.main()
