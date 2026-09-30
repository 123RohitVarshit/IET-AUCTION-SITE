from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_state, require_admin
from ..schemas import (
    ExtendRequest,
    FreezeRequest,
    ManualModeRequest,
    NextPlayerRequest,
    PurseEditRequest,
    ResetTimerRequest,
    SetTimesRequest,
    SubstituteBidRequest,
)
from ...realtime.sync import sync_all


router = APIRouter()


async def commit_admin_action(state, action: str, payload: dict, fn):
    try:
        result = fn()
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    state.store.log_admin_action(action, payload)
    state.store.save_state(state.auction.to_dict())

    await sync_all(state)

    return {
        "ok": True,
        "action": action,
        "result": result,
    }


@router.post("/api/admin/start")
async def admin_start(state=Depends(get_state), _=Depends(require_admin)):
    return await commit_admin_action(
        state,
        "start",
        {},
        lambda: state.auction.start(),
    )


@router.post("/api/admin/next")
async def admin_next(
    payload: Optional[NextPlayerRequest] = None,
    state=Depends(get_state),
    _=Depends(require_admin),
):
    candidate_id = payload.candidate_id if payload else None

    return await commit_admin_action(
        state,
        "next_candidate",
        {"candidate_id": candidate_id},
        lambda: state.auction.next_candidate(candidate_id),
    )


@router.post("/api/admin/pause")
async def admin_pause(state=Depends(get_state), _=Depends(require_admin)):
    return await commit_admin_action(
        state,
        "pause",
        {},
        lambda: state.auction.pause(),
    )


@router.post("/api/admin/resume")
async def admin_resume(state=Depends(get_state), _=Depends(require_admin)):
    return await commit_admin_action(
        state,
        "resume",
        {},
        lambda: state.auction.resume(),
    )


@router.post("/api/admin/freeze")
async def admin_freeze(
    payload: FreezeRequest,
    state=Depends(get_state),
    _=Depends(require_admin),
):
    return await commit_admin_action(
        state,
        "freeze",
        {"on": payload.on},
        lambda: state.auction.freeze(payload.on),
    )


@router.post("/api/admin/extend")
async def admin_extend(
    payload: ExtendRequest,
    state=Depends(get_state),
    _=Depends(require_admin),
):
    return await commit_admin_action(
        state,
        "extend",
        {"seconds": payload.seconds},
        lambda: state.auction.extend(payload.seconds),
    )


@router.post("/api/admin/reset-timer")
async def admin_reset_timer(
    payload: ResetTimerRequest,
    state=Depends(get_state),
    _=Depends(require_admin),
):
    return await commit_admin_action(
        state,
        "reset_timer",
        {"seconds": payload.seconds},
        lambda: state.auction.reset_timer(payload.seconds),
    )


@router.post("/api/admin/set-manual-mode")
async def admin_set_manual_mode(
    payload: ManualModeRequest,
    state=Depends(get_state),
    _=Depends(require_admin),
):
    return await commit_admin_action(
        state,
        "set_manual_mode",
        {"on": payload.on},
        lambda: state.auction.set_manual_mode(payload.on),
    )


@router.post("/api/admin/confirm-sale")
async def admin_confirm_sale(state=Depends(get_state), _=Depends(require_admin)):
    return await commit_admin_action(
        state,
        "confirm_sale",
        {},
        lambda: state.auction.confirm_sale(),
    )


@router.post("/api/admin/mark-unsold")
async def admin_mark_unsold(state=Depends(get_state), _=Depends(require_admin)):
    return await commit_admin_action(
        state,
        "mark_unsold",
        {},
        lambda: state.auction.mark_unsold(),
    )


@router.post("/api/admin/undo-last-bid")
async def admin_undo_last_bid(state=Depends(get_state), _=Depends(require_admin)):
    try:
        ok, message = state.auction.undo_last_bid()
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    state.store.log_admin_action("undo_last_bid", {})

    if ok:
        state.store.save_state(state.auction.to_dict())

    await sync_all(state)

    return {
        "ok": ok,
        "message": message,
    }


@router.post("/api/admin/set-purse")
async def admin_set_purse(
    payload: PurseEditRequest,
    state=Depends(get_state),
    _=Depends(require_admin),
):
    return await commit_admin_action(
        state,
        "set_purse",
        {
            "team_id": payload.team_id,
            "amount": payload.amount,
        },
        lambda: state.auction.set_purse(payload.team_id, payload.amount),
    )


@router.post("/api/admin/substitute-bid")
async def admin_substitute_bid(
    payload: SubstituteBidRequest,
    state=Depends(get_state),
    _=Depends(require_admin),
):
    def action():
        price = payload.price

        if price is None:
            if state.auction.phase != "LIVE" or state.auction.current is None:
                raise ValueError("Bidding is not open right now.")

            price = state.auction.next_price()

        verdict = state.auction.place_bid(payload.team_id, price)

        state.store.record_bid(
            candidate_id=state.auction.current,
            team_id=payload.team_id,
            amount=price,
            status="ACCEPTED" if verdict.ok else "REJECTED",
            reason=verdict.reason,
        )

        if not verdict.ok:
            raise ValueError(f"{verdict.code}: {verdict.reason}")

        return {
            "team_id": payload.team_id,
            "price": price,
            "code": verdict.code,
            "reason": verdict.reason,
        }

    return await commit_admin_action(
        state,
        "substitute_bid",
        {
            "team_id": payload.team_id,
            "price": payload.price,
        },
        action,
    )


@router.post("/api/admin/set-times")
async def admin_set_times(
    payload: SetTimesRequest,
    state=Depends(get_state),
    _=Depends(require_admin),
):
    return await commit_admin_action(
        state,
        "set_times",
        {
            "preview": payload.preview,
            "bid": payload.bid,
            "result": payload.result,
        },
        lambda: state.auction.set_times(
            preview=payload.preview,
            bid=payload.bid,
            result=payload.result,
        ),
    )