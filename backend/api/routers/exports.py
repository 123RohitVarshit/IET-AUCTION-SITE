import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from ..deps import get_state, require_admin


router = APIRouter()


@router.get("/api/admin/export/bids.csv")
def export_bids_csv(state=Depends(get_state), _=Depends(require_admin)):
    rows = state.store.fetch_bids()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "id",
            "created_at",
            "candidate_id",
            "team_id",
            "amount",
            "status",
            "reason",
        ]
    )

    for row in rows:
        writer.writerow(
            [
                row["id"],
                row["created_at"],
                row["candidate_id"],
                row["team_id"],
                row["amount"],
                row["status"],
                row["reason"],
            ]
        )

    return PlainTextResponse(
        output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=bids.csv",
        },
    )


@router.get("/api/admin/export/squads.csv")
def export_squads_csv(state=Depends(get_state), _=Depends(require_admin)):
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "team_id",
            "team_name",
            "purse",
            "roster_count",
            "candidate_ids",
            "candidate_names",
        ]
    )

    auction = state.auction

    for team in auction.teams.values():
        candidate_ids = ";".join(str(cid) for cid in team.roster)

        candidate_names = ";".join(
            auction.cands[cid].name
            for cid in team.roster
            if cid in auction.cands
        )

        writer.writerow(
            [
                team.id,
                team.name,
                team.purse,
                len(team.roster),
                candidate_ids,
                candidate_names,
            ]
        )

    return PlainTextResponse(
        output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=squads.csv",
        },
    )


@router.get("/api/admin/export/admin-actions.csv")
def export_admin_actions_csv(state=Depends(get_state), _=Depends(require_admin)):
    rows = state.store.fetch_admin_actions()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "id",
            "created_at",
            "action",
            "payload_json",
        ]
    )

    for row in rows:
        writer.writerow(
            [
                row["id"],
                row["created_at"],
                row["action"],
                row["payload_json"],
            ]
        )

    return PlainTextResponse(
        output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=admin_actions.csv",
        },
    )