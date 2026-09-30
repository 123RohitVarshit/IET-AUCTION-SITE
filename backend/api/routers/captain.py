import secrets

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_state, require_team
from ..schemas import BidRequest, CaptainLoginRequest
from ..security import generate_token
from ...realtime.sync import sync_all


router = APIRouter()


@router.post("/api/captain/login")
def captain_login(payload: CaptainLoginRequest, state=Depends(get_state)):
    expected_code = state.team_logins.get(payload.team_id)

    if expected_code is None:
        raise HTTPException(status_code=401, detail="Invalid team id")

    if not secrets.compare_digest(
        str(expected_code),
        str(payload.login_code),
    ):
        raise HTTPException(status_code=401, detail="Invalid login code")

    token = generate_token()
    state.team_tokens[token] = payload.team_id

    return {
        "token": token,
        "team_id": payload.team_id,
    }


@router.get("/api/captain/view")
def captain_view(state=Depends(get_state), team_id: int = Depends(require_team)):
    return state.auction.team_view(team_id)


@router.post("/api/captain/bid")
async def captain_bid(
    payload: BidRequest,
    state=Depends(get_state),
    team_id: int = Depends(require_team),
):
    if not state.rate_limiter.allow(team_id):
        raise HTTPException(status_code=429, detail="Rate limited")

    verdict = state.auction.place_bid(team_id, payload.price)

    state.store.record_bid(
        candidate_id=state.auction.current,
        team_id=team_id,
        amount=payload.price,
        status="ACCEPTED" if verdict.ok else "REJECTED",
        reason=verdict.reason,
    )

    if verdict.ok:
        state.store.save_state(state.auction.to_dict())

    await sync_all(state)

    return {
        "ok": verdict.ok,
        "code": verdict.code,
        "reason": verdict.reason,
    }