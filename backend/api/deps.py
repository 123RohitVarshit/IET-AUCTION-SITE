"""
FastAPI dependencies.
"""

from typing import Optional
from fastapi import Depends, Header, HTTPException, Query, Request

from .security import verify_admin_pin


def get_state(request: Request):
    return request.app.state.app_state


def require_admin(
    state=Depends(get_state),
    x_admin_pin: str = Header(default=""),
    pin: Optional[str] = Query(default=None),
):
    provided = x_admin_pin or pin or ""
    if not verify_admin_pin(provided, state.admin_pin):
        raise HTTPException(status_code=401, detail="Invalid admin PIN")

    return True


def require_team(
    state=Depends(get_state),
    x_team_token: str = Header(default=""),
):
    team_id = state.team_tokens.get(x_team_token)

    if team_id is None:
        raise HTTPException(status_code=401, detail="Invalid team token")

    return team_id