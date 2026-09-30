"""
WebSocket endpoints.

/ws/captain
/ws/stage
/ws/admin
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..api.security import verify_admin_pin
from .messages import Msg
from .sync import sync_all


router = APIRouter()


@router.websocket("/ws/captain")
async def captain_websocket(websocket: WebSocket, token: str = ""):
    state = websocket.app.state.app_state

    await websocket.accept()

    team_id = state.team_tokens.get(token)

    if team_id is None:
        await websocket.close(code=4001, reason="Invalid team token")
        return

    state.hub.connect_captain(team_id, websocket)

    try:
        await websocket.send_json(
            {
                "type": Msg.TEAM_VIEW,
                "view": state.auction.team_view(team_id),
            }
        )

        await websocket.send_json(
            {
                "type": Msg.STATE,
                "state": state.auction.snapshot(),
            }
        )

        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                raise
            except Exception:
                await websocket.send_json(
                    {
                        "type": Msg.ERROR,
                        "reason": "BAD_JSON",
                    }
                )
                continue

            message_type = data.get("type")

            if message_type == Msg.PING:
                await websocket.send_json({"type": Msg.PONG})
                continue

            if message_type == Msg.BID:
                if not state.rate_limiter.allow(team_id):
                    await websocket.send_json(
                        {
                            "type": Msg.BID_RESULT,
                            "ok": False,
                            "code": "RATE_LIMITED",
                            "reason": "Too many bids. Slow down.",
                        }
                    )
                    continue

                price = data.get("price")

                if price is None:
                    if (
                        state.auction.phase != "LIVE"
                        or state.auction.current is None
                    ):
                        await websocket.send_json(
                            {
                                "type": Msg.BID_RESULT,
                                "ok": False,
                                "code": "NOT_LIVE",
                                "reason": "Bidding is not open right now.",
                            }
                        )
                        continue

                    price = state.auction.next_price()

                verdict = state.auction.place_bid(team_id, price)

                state.store.record_bid(
                    candidate_id=state.auction.current,
                    team_id=team_id,
                    amount=price,
                    status="ACCEPTED" if verdict.ok else "REJECTED",
                    reason=verdict.reason,
                )

                if verdict.ok:
                    state.store.save_state(state.auction.to_dict())

                await websocket.send_json(
                    {
                        "type": Msg.BID_RESULT,
                        "ok": verdict.ok,
                        "code": verdict.code,
                        "reason": verdict.reason,
                    }
                )

                await sync_all(state)
                continue

            await websocket.send_json(
                {
                    "type": Msg.ERROR,
                    "reason": "UNKNOWN_MESSAGE",
                }
            )

    except WebSocketDisconnect:
        pass
    finally:
        state.hub.disconnect_captain(team_id, websocket)


@router.websocket("/ws/stage")
async def stage_websocket(websocket: WebSocket):
    state = websocket.app.state.app_state

    await websocket.accept()
    state.hub.connect_stage(websocket)

    try:
        await websocket.send_json(
            {
                "type": Msg.STATE,
                "state": state.auction.snapshot(),
            }
        )

        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                raise
            except Exception:
                continue

            if data.get("type") == Msg.PING:
                await websocket.send_json({"type": Msg.PONG})

    except WebSocketDisconnect:
        pass
    finally:
        state.hub.disconnect_stage(websocket)


@router.websocket("/ws/admin")
async def admin_websocket(websocket: WebSocket, pin: str = ""):
    state = websocket.app.state.app_state

    await websocket.accept()

    if not verify_admin_pin(pin, state.admin_pin):
        await websocket.close(code=4003, reason="Invalid admin PIN")
        return

    state.hub.connect_admin(websocket)

    try:
        await websocket.send_json(
            {
                "type": Msg.STATE,
                "state": state.auction.snapshot(),
            }
        )

        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                raise
            except Exception:
                continue

            if data.get("type") == Msg.PING:
                await websocket.send_json({"type": Msg.PONG})

    except WebSocketDisconnect:
        pass
    finally:
        state.hub.disconnect_admin(websocket)