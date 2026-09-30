"""
WebSocket message type constants.
"""


class Msg:
    STATE = "state"
    TEAM_VIEW = "team_view"
    BID = "bid"
    BID_RESULT = "bid_result"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"