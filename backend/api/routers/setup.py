from fastapi import APIRouter, Depends

from ..deps import get_state


router = APIRouter()


@router.get("/api/setup/report")
def setup_report(state=Depends(get_state)):
    return state.auction.setup_report()