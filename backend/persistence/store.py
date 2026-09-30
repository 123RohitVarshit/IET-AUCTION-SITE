"""
SQLite persistence layer.

Responsibilities:
- save full auction state snapshot after important actions,
- restore state after restart,
- store bid audit log,
- store admin action audit log.
"""

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.lock = threading.RLock()

        self.conn = sqlite3.connect(
            str(self.path),
            check_same_thread=False,
        )

        self.conn.row_factory = sqlite3.Row

        # WAL mode is important for live reliability.
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")

        self._create_tables()

    def _create_tables(self) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS state_snapshot (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    state_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )

            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at REAL NOT NULL,
                    candidate_id INTEGER,
                    team_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT ''
                )
                """
            )

            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at REAL NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )

    # ------------------------------------------------------------------
    # State snapshot
    # ------------------------------------------------------------------

    def save_state(self, state_dict: Dict[str, Any]) -> None:
        payload = json.dumps(state_dict, default=str)
        now = time.time()

        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO state_snapshot (id, state_json, updated_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (payload, now),
            )

    def load_state(self) -> Optional[Dict[str, Any]]:
        with self.lock:
            row = self.conn.execute(
                """
                SELECT state_json
                FROM state_snapshot
                WHERE id = 1
                """
            ).fetchone()

        if row is None:
            return None

        return json.loads(row["state_json"])

    def clear_state(self) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM state_snapshot WHERE id = 1")

    # ------------------------------------------------------------------
    # Audit logs
    # ------------------------------------------------------------------

    def record_bid(
        self,
        candidate_id: Optional[int],
        team_id: int,
        amount: int,
        status: str,
        reason: str = "",
    ) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO bids (
                    created_at,
                    candidate_id,
                    team_id,
                    amount,
                    status,
                    reason
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    time.time(),
                    candidate_id,
                    team_id,
                    amount,
                    status,
                    reason,
                ),
            )

    def log_admin_action(self, action: str, payload: Dict[str, Any]) -> None:
        payload_json = json.dumps(payload or {}, default=str)

        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO admin_actions (
                    created_at,
                    action,
                    payload_json
                )
                VALUES (?, ?, ?)
                """,
                (
                    time.time(),
                    action,
                    payload_json,
                ),
            )

    def fetch_bids(self) -> List[Dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT
                    id,
                    created_at,
                    candidate_id,
                    team_id,
                    amount,
                    status,
                    reason
                FROM bids
                ORDER BY id
                """
            ).fetchall()

        return [dict(row) for row in rows]

    def fetch_admin_actions(self) -> List[Dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT
                    id,
                    created_at,
                    action,
                    payload_json
                FROM admin_actions
                ORDER BY id
                """
            ).fetchall()

        return [dict(row) for row in rows]

    def close(self) -> None:
        with self.lock:
            self.conn.close()