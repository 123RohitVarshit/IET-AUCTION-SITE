from fastapi import APIRouter, Depends

from ..deps import get_state


router = APIRouter()


@router.get("/api/stage/state")
def stage_state(state=Depends(get_state)):
    return state.auction.snapshot()