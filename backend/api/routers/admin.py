from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from ..deps import get_state, require_admin
from ..schemas import (
    ExtendRequest,
    FreezeRequest,
    ManualModeRequest,
    NextPlayerRequest,
    PurseEditRequest,
    ResetTimerRequest,
    RosterSizeRequest,
    SetTimesRequest,
    SubstituteBidRequest,
)
from ...realtime.sync import sync_all


router = APIRouter()


@router.get("/api/admin/auth/check")
def admin_auth_check(_=Depends(require_admin)):
    return {"ok": True}


@router.get("/api/admin/candidates")
def get_candidates(state=Depends(get_state), _=Depends(require_admin)):
    with state.auction.lock:
        return [
            {
                "id": c.id,
                "name": c.name,
                "tier": c.tier,
                "rating": c.rating,
                "base_price": c.base_price,
                "status": c.status,
                "sold_to": c.sold_to,
                "sold_price": c.sold_price,
                "profile": c.profile,
            }
            for c in state.auction.cands.values()
        ]


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
    payload: Optional[NextPlayerRequest] = Body(default=None),
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
    payload: Optional[FreezeRequest] = Body(default=None),
    state=Depends(get_state),
    _=Depends(require_admin),
):
    on = payload.on if (payload and payload.on is not None) else not state.auction.frozen
    return await commit_admin_action(
        state,
        "freeze",
        {"on": on},
        lambda: state.auction.freeze(on),
    )


@router.post("/api/admin/extend")
async def admin_extend(
    payload: Optional[ExtendRequest] = Body(default=None),
    state=Depends(get_state),
    _=Depends(require_admin),
):
    seconds = payload.seconds if (payload and payload.seconds is not None) else 10.0
    return await commit_admin_action(
        state,
        "extend",
        {"seconds": seconds},
        lambda: state.auction.extend(seconds),
    )


@router.post("/api/admin/reset-timer")
async def admin_reset_timer(
    payload: Optional[ResetTimerRequest] = Body(default=None),
    state=Depends(get_state),
    _=Depends(require_admin),
):
    seconds = payload.seconds if payload else None
    return await commit_admin_action(
        state,
        "reset_timer",
        {"seconds": seconds},
        lambda: state.auction.reset_timer(seconds),
    )


@router.post("/api/admin/set-manual-mode")
async def admin_set_manual_mode(
    payload: Optional[ManualModeRequest] = Body(default=None),
    state=Depends(get_state),
    _=Depends(require_admin),
):
    on = payload.on if (payload and payload.on is not None) else not state.auction.manual_mode
    return await commit_admin_action(
        state,
        "set_manual_mode",
        {"on": on},
        lambda: state.auction.set_manual_mode(on),
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
    payload: Optional[SetTimesRequest] = Body(default=None),
    state=Depends(get_state),
    _=Depends(require_admin),
):
    preview = payload.preview if payload else None
    bid = payload.bid if payload else None
    result = payload.result if payload else None
    return await commit_admin_action(
        state,
        "set_times",
        {
            "preview": preview,
            "bid": bid,
            "result": result,
        },
        lambda: state.auction.set_times(
            preview=preview,
            bid=bid,
            result=result,
        ),
    )


@router.post("/api/admin/set-roster-size")
async def admin_set_roster_size(
    payload: RosterSizeRequest,
    state=Depends(get_state),
    _=Depends(require_admin),
):
    return await commit_admin_action(
        state,
        "set_roster_size",
        {"size": payload.size},
        lambda: state.auction.set_roster_size(payload.size),
    )


@router.post("/api/admin/reset")
async def admin_reset(
    state=Depends(get_state),
    _=Depends(require_admin),
):
    from pathlib import Path
    from ...core.auction import Auction
    from ...core.config import Config
    from ...core.loader import load_candidates, load_teams

    data_dir = Path("data")
    teams_path = data_dir / "teams.csv"
    rated_path = data_dir / "rated.csv"

    teams = load_teams(str(teams_path)) if teams_path.exists() else []
    candidates = load_candidates(str(rated_path)) if rated_path.exists() else []

    state.store.clear_state()

    cfg = Config()
    state.cfg = cfg
    state.auction = Auction(cfg=cfg, teams=teams, candidates=candidates)
    state.team_tokens.clear()
    state.team_logins = {team["id"]: team["login_code"] for team in teams}

    state.store.log_admin_action("reset_auction", {"teams_count": len(teams), "candidates_count": len(candidates)})
    state.store.save_state(state.auction.to_dict())

    await sync_all(state)

    return {
        "ok": True,
        "action": "reset",
        "message": f"Auction reset successfully. Loaded {len(teams)} teams and {len(candidates)} candidates.",
    }