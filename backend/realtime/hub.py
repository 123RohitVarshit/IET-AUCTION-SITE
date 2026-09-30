"""
WebSocket connection hub.

Keeps track of connected captain, stage, and admin sockets.
"""

from collections import defaultdict
from typing import Dict, List, Set

from fastapi import WebSocket


class WebSocketHub:
    def __init__(self):
        self.captains: Dict[int, List[WebSocket]] = defaultdict(list)
        self.stage: Set[WebSocket] = set()
        self.admin: Set[WebSocket] = set()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect_captain(self, team_id: int, websocket: WebSocket) -> None:
        self.captains[team_id].append(websocket)

    def disconnect_captain(self, team_id: int, websocket: WebSocket) -> None:
        connections = self.captains.get(team_id)

        if not connections:
            return

        if websocket in connections:
            connections.remove(websocket)

        if not connections:
            del self.captains[team_id]

    def connect_stage(self, websocket: WebSocket) -> None:
        self.stage.add(websocket)

    def disconnect_stage(self, websocket: WebSocket) -> None:
        self.stage.discard(websocket)

    def connect_admin(self, websocket: WebSocket) -> None:
        self.admin.add(websocket)

    def disconnect_admin(self, websocket: WebSocket) -> None:
        self.admin.discard(websocket)

    def connected_captain_ids(self) -> List[int]:
        return list(self.captains.keys())

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    async def send_json(self, websocket: WebSocket, payload: dict) -> None:
        try:
            await websocket.send_json(payload)
        except Exception:
            # If sending fails, the disconnect handler will clean up.
            pass

    async def broadcast_snapshot(self, snapshot: dict) -> None:
        message = {
            "type": "state",
            "state": snapshot,
        }

        for websocket in list(self.stage):
            await self.send_json(websocket, message)

        for websocket in list(self.admin):
            await self.send_json(websocket, message)

        for connections in list(self.captains.values()):
            for websocket in list(connections):
                await self.send_json(websocket, message)

    async def send_team_view(self, team_id: int, view: dict) -> None:
        message = {
            "type": "team_view",
            "view": view,
        }

        for websocket in list(self.captains.get(team_id, [])):
            await self.send_json(websocket, message)