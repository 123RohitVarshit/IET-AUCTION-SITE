"""
Shared synchronization helper.

Broadcasts:
- public snapshot to stage/admin/captains,
- private team views to connected captains.
"""


async def sync_all(state) -> None:
    snapshot = state.auction.snapshot()

    await state.hub.broadcast_snapshot(snapshot)

    for team_id in list(state.hub.connected_captain_ids()):
        try:
            view = state.auction.team_view(team_id)
        except KeyError:
            continue

        await state.hub.send_team_view(team_id, view)