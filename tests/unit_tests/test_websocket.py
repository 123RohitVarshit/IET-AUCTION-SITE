import unittest

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from .helpers import make_test_app


class WebSocketTests(unittest.TestCase):
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def start_live_auction(self):
        self.state.auction.start()
        self.state.auction.next_candidate()

        self.assertEqual(self.state.auction.phase, "LIVE")

    def assert_websocket_disconnect(self, url: str, expected_code: int):
        try:
            with self.client.websocket_connect(url) as websocket:
                try:
                    websocket.receive_json()
                except WebSocketDisconnect as exc:
                    self.assertEqual(exc.code, expected_code)
                    return
        except WebSocketDisconnect as exc:
            self.assertEqual(exc.code, expected_code)
            return

        self.fail(f"Expected WebSocketDisconnect with code {expected_code}")

    # ------------------------------------------------------------------
    # Stage socket
    # ------------------------------------------------------------------

    def test_stage_connect_receives_state_and_ping(self):
        with self.client.websocket_connect("/ws/stage") as websocket:
            message = websocket.receive_json()

            self.assertEqual(message["type"], "state")
            self.assertIn("state", message)
            self.assertEqual(message["state"]["phase"], "SETUP")

            websocket.send_json({"type": "ping"})

            message = websocket.receive_json()

            self.assertEqual(message["type"], "pong")

    # ------------------------------------------------------------------
    # Admin socket
    # ------------------------------------------------------------------

    def test_admin_socket_rejects_bad_pin(self):
        self.assert_websocket_disconnect(
            "/ws/admin?pin=wrong-pin",
            expected_code=4003,
        )

    def test_admin_socket_accepts_valid_pin(self):
        with self.client.websocket_connect("/ws/admin?pin=test-admin") as websocket:
            message = websocket.receive_json()

            self.assertEqual(message["type"], "state")
            self.assertIn("state", message)

    # ------------------------------------------------------------------
    # Captain socket
    # ------------------------------------------------------------------

    def test_captain_socket_rejects_bad_token(self):
        self.assert_websocket_disconnect(
            "/ws/captain?token=bad-token",
            expected_code=4001,
        )

    def test_captain_socket_connect_receives_team_view_and_state(self):
        self.start_live_auction()

        self.state.team_tokens["test-token"] = 1

        with self.client.websocket_connect("/ws/captain?token=test-token") as websocket:
            first = websocket.receive_json()
            second = websocket.receive_json()

            self.assertEqual(first["type"], "team_view")
            self.assertEqual(first["view"]["team"], "Team 1")
            self.assertEqual(first["view"]["next_price"], 200)
            self.assertTrue(first["view"]["can_bid"])

            self.assertEqual(second["type"], "state")
            self.assertEqual(second["state"]["phase"], "LIVE")
            self.assertEqual(second["state"]["candidate"]["id"], 1)

    def test_captain_socket_can_place_bid(self):
        self.start_live_auction()

        self.state.team_tokens["test-token"] = 1

        with self.client.websocket_connect("/ws/captain?token=test-token") as websocket:
            # Consume initial team_view and state messages.
            websocket.receive_json()
            websocket.receive_json()

            websocket.send_json(
                {
                    "type": "bid",
                    "price": 200,
                }
            )

            message = websocket.receive_json()

            self.assertEqual(message["type"], "bid_result")
            self.assertTrue(message["ok"])
            self.assertEqual(message["code"], "OK")

        # The auction core must have recorded the bid.
        self.assertEqual(self.state.auction.current_bid(), 200)
        self.assertEqual(self.state.auction.leader(), 1)

    def test_captain_socket_rejects_stale_bid(self):
        self.start_live_auction()

        self.state.team_tokens["team-1-token"] = 1
        self.state.team_tokens["team-2-token"] = 2

        # Team 1 bids first through the core engine.
        verdict = self.state.auction.place_bid(1, 200)
        self.assertTrue(verdict.ok)

        # Team 2 tries to bid the old price through WebSocket.
        with self.client.websocket_connect("/ws/captain?token=team-2-token") as websocket:
            # Consume initial team_view and state messages.
            websocket.receive_json()
            websocket.receive_json()

            websocket.send_json(
                {
                    "type": "bid",
                    "price": 200,
                }
            )

            message = websocket.receive_json()

            self.assertEqual(message["type"], "bid_result")
            self.assertFalse(message["ok"])
            self.assertEqual(message["code"], "STALE")


if __name__ == "__main__":
    unittest.main()