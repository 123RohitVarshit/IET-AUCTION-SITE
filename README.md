[![Keep Render Server Alive](https://github.com/SohanRaidev/IET-AUCTION-SITE/actions/workflows/keep-alive.yml/badge.svg)](https://github.com/SohanRaidev/IET-AUCTION-SITE/actions/workflows/keep-alive.yml)

# IET Auction System

Real-time team auction platform for the IET Hackathon.

## Architecture

Single-process FastAPI server — one asyncio event loop, one in-memory `Auction` state machine, one `threading.RLock`.  
**Never run with `--workers > 1`.**

```
backend/
├── core/
│   ├── auction.py      # State machine (SETUP → IDLE → PREVIEW → LIVE → RESULT → DONE)
│   ├── config.py       # All tuneable numbers (purse, timers, increments)
│   ├── rules.py        # Pure bid validation — no state, no I/O
│   ├── rating.py       # Offline Elo rating script (run once before event)
│   ├── loader.py       # CSV parsers for candidates and teams
│   └── models.py       # Team, Candidate, Bid dataclasses
├── api/
│   ├── routers/        # FastAPI route handlers (admin, captain, stage, exports, …)
│   ├── deps.py         # FastAPI dependency injectors (get_state, require_admin, require_team)
│   ├── schemas.py      # Pydantic request bodies
│   ├── security.py     # Timing-safe PIN / token comparison
│   └── rate_limit.py   # Sliding-window rate limiter (3 bids / sec per team)
├── realtime/
│   ├── handlers.py     # WebSocket endpoints (/ws/captain, /ws/stage, /ws/admin)
│   ├── hub.py          # WebSocket connection registry
│   ├── tick.py         # 10 Hz clock loop — drives phase transitions, persists on change
│   ├── sync.py         # broadcast_snapshot + per-team team_view push
│   └── messages.py     # WS message type constants
├── persistence/
│   └── store.py        # SQLite WAL — state snapshots + bid + admin-action audit logs
├── bootstrap.py        # Wires all components together at startup
├── state.py            # AppState dataclass (single shared object)
└── main.py             # FastAPI app + lifespan

static/                 # Frontend HTML/JS (captain, stage, admin) — TBD
tests/
└── unit_tests/         # 112 tests covering rules, auction engine, API, WebSockets
```

## Setup

```bash
# 1. Install dependencies
pip install fastapi uvicorn[standard] httpx websockets python-dotenv

# 2. Set the admin PIN
cp .env.example .env
# edit .env:  ADMIN_PIN=your-secret-pin

# 3. (First run only) Rate and tier candidates
#    Put raw scores in data/raw.csv, then:
python -m backend.core.rating data/raw.csv data/rated.csv

# 4. Prepare teams CSV (data/teams.csv):
#    id,name,login_code[,purse]

# 5. Start the server
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## Running Tests

```bash
python -m unittest discover tests
# Expected: Ran 112 tests in ~0.4s   OK
```

## Key Rules

| Rule | Value |
|---|---|
| Purse per team | 10,000 pts |
| Roster size | 4 players |
| Floor price | 100 pts |
| Tier base prices | T1 1000 / T2 600 / T3 400 / T4 200 |
| Bid increment | +100 below 1500 / +250 at or above 1500 |
| Anti-snipe window | 8 s |
| Max unsold rounds | 5 |
| Round price drop | 50%, rounded to 100, min 100 |

## WebSocket Channels

| Endpoint | Auth | Role |
|---|---|---|
| `/ws/captain?token=<TOKEN>` | Team bearer token | Place bids, see private view |
| `/ws/stage` | None | Projector display (read-only) |
| `/ws/admin?pin=<PIN>` | Admin PIN | Auctioneer controls |

## REST Endpoints (Admin — `x-admin-pin` header required)

`POST /api/admin/start` · `POST /api/admin/next` · `POST /api/admin/pause` · `POST /api/admin/resume`  
`POST /api/admin/freeze` · `POST /api/admin/extend` · `POST /api/admin/reset-timer`  
`POST /api/admin/confirm-sale` · `POST /api/admin/mark-unsold` · `POST /api/admin/undo-last-bid`  
`POST /api/admin/set-manual-mode` · `POST /api/admin/set-purse` · `POST /api/admin/substitute-bid`  
`GET /api/admin/export/bids.csv` · `GET /api/admin/export/squads.csv` · `GET /api/admin/export/admin_actions.csv`

## Captain Endpoints

`POST /api/captain/login` → `{ token, team_id }` · `GET /api/captain/view` · `POST /api/captain/bid`
