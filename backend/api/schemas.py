"""
Pydantic request models for HTTP API.
"""

from typing import Optional

from pydantic import BaseModel


class CaptainLoginRequest(BaseModel):
    team_id: int
    login_code: str


class BidRequest(BaseModel):
    price: int


class NextPlayerRequest(BaseModel):
    candidate_id: Optional[int] = None


class FreezeRequest(BaseModel):
    on: Optional[bool] = None


class ExtendRequest(BaseModel):
    seconds: float = 10.0


class ResetTimerRequest(BaseModel):
    seconds: Optional[float] = None


class ManualModeRequest(BaseModel):
    on: Optional[bool] = None


class PurseEditRequest(BaseModel):
    team_id: int
    amount: int


class SubstituteBidRequest(BaseModel):
    team_id: int
    price: Optional[int] = None


class SetTimesRequest(BaseModel):
    preview: Optional[float] = None
    bid: Optional[float] = None
    result: Optional[float] = None


class RosterSizeRequest(BaseModel):
    size: int