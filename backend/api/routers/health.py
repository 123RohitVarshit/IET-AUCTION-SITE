from fastapi import APIRouter, Depends

from ..deps import get_state


router = APIRouter()


@router.get("/api/health")
def health(state=Depends(get_state)):
    return {
        "status": "ok",
        "phase": state.auction.phase,
        "round": state.auction.round_no,
        "manual_mode": state.auction.manual_mode,
        "paused": state.auction.paused,
        "frozen": state.auction.frozen,
    }