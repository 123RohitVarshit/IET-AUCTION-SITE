# IET Hackathon Live Auction Platform: Master System Specification & Deep-Dive Analysis

---

## 1. Executive Summary & Core System Vision

The **IET Auction Site** is a high-concurrency, real-time live auction platform engineered for the annual **IET Hackathon**. Following rigorous aptitude and group discussion (GD) screening rounds, 30 to 60 qualifying candidates ("players") enter a live draft pool. Captains of participating teams bid for candidates in real time using virtual budgets ("purses") to assemble balanced, competitive squads (rosters).

### The Prime Architectural Directive
> **"The Server is the Only Referee."**
> 
> No client (Captain laptop, Stage projector, or Admin tablet) possesses decision-making authority. Every user interface is a thin presentation and event-dispatching layer. All validation, state transitions, clock deadlines, financial calculations, and tie-breakers are strictly computed and enforced on the server within an atomic, single-process execution model.

### Evolution of System Specifications
The codebase captures an evolution from initial concepts in the requirements document (`IET Auction Website.docx`) to the refined engineering specification (`auction_handbook.md`) and implementation files (`auction.py`, `server.py`, `test_core.py`):

| Parameter / Feature | Original Brief (`.docx`) | Final Engineered Design (`handbook.md` & code) | Engineering Rationale |
| :--- | :--- | :--- | :--- |
| **Purse Budget** | 1,000 points | **10,000 points** | Finer increment granularity (+100 / +250 vs +10 / +25); prevents integer division truncations. |
| **Roster Size** | 5 candidates | **4 candidates** (+ captain = 5) | Matches hackathon squad size of 5 without treating captains as auctionable inventory. |
| **Auction Mode** | Manual Hammer only | **Dual Mode (Auto by default + Manual Override)** | High throughput (1–2 mins/player) via automated timers, while preserving human auctioneer control on demand. |
| **Candidate Rating** | Static weighted PVI | **Percentile Elo-Style Reverse Valuation** | Relative cohort ranking guarantees balanced tier distribution regardless of raw test score skew. |
| **Money Timing** | Bid-time deduction implied | **Deducted ONLY upon confirmed sale** | Bids are audit log entries; allows zero-friction undos without complex escrow or refund rollbacks. |
| **Architecture** | Generic Web/DB | **Single-process FastAPI + In-Memory State Machine + SQLite WAL** | Eliminates distributed race conditions; sub-millisecond lock acquisition ensures instant bid arbitration. |

---

## 2. Comprehensive Codebase & File Breakdown

The repository currently consists of core architectural documentation and baseline backend logic:

```
d:\ROHIT\IET\AUCTION_SITE\
├── IET Auction Website.docx     # Product & UI specification brief
├── auction_handbook.md          # Engineering handbook, operational runbook & design rationale
├── auction.py                   # Core in-memory state machine, clock & concurrency engine
├── server.py                    # FastAPI server, WebSocket hub, REST endpoints & rate limiter
├── test_core.py                 # Core unit & concurrency test suite (18 test scenarios)
└── burst_test.py                # Placeholder for high-concurrency load testing
```

### Detailed File-by-File Analysis

#### 1. `IET Auction Website.docx` (Product Specification Brief)
- **Candidate Valuation (PVI)**: Defines the Participant Valuation Index based on Aptitude (40%), Group Discussion (25%), and Resume Profile (35%).
- **Four-Tier Structure**: Tier 1 (Marquee), Tier 2 (Core Specialists), Tier 3 (Design & Pitch Leads), and Tier 4 (Emerging Developers).
- **Three Core Personas & Screen Layouts**:
  - `Captain Console (/captain)`: Left pane for live bidding and candidate spotlight; right pane for squad composition, skill coverage matrix (Frontend, Backend, AI/ML, UI/Pitch), and reserve guardrail indicator.
  - `Stage Screen (/stage)`: Auditorium projector display featuring candidate card, big countdown timer, current high bid, squad standings table, and live bid feed.
  - `Admin Console (/admin)`: Auctioneer controls for clock (Pause, +10s, Reset), hammer (Confirm Sale, Mark Unsold), bid freeze, undo/rollback, substitute bidding, and captain connection health monitoring.
- **Operational Edge Cases**: Double clicks, unsold candidate recycling at a 50% discount, hardware failures, and simultaneous bids.

#### 2. `auction_handbook.md` (Operational Guide & System Blueprint)
- Establishes the authoritative architectural decisions and single source of truth (`config.py`).
- Defines mathematical formulas for bidding tiers, reserve limits, and round price drops.
- Clarifies the dual-mode execution model (Auto vs. Manual Override).
- Supplies pre-event setup procedures, setup check health report (`setup_report()`), and event-day disaster recovery runbooks.

#### 3. `auction.py` (Core State Machine Engine)
- Implements `Auction`, `Team`, `Candidate`, and `Bid` dataclasses.
- **Concurrency Management**: Uses a single re-entrant lock (`threading.RLock`) protecting all mutable state.
- **Injectable Clock**: `clock=time.monotonic` parameter enables millisecond-precise determinism and simulated time testing (`FakeClock`).
- **Phases**: `SETUP` -> `IDLE` -> `PREVIEW` -> `LIVE` -> `AWAITING_HAMMER` (manual mode only) -> `RESULT` -> `DONE`.
- **Administrative Interventions**: `pause()`, `resume()`, `freeze()`, `extend()`, `reset_timer()`, `set_purse()`, `undo_last_bid()`, `confirm_sale()`, `mark_unsold()`.
- **State Snapshotting**: `to_dict()` and `from_dict()` serialize state using relative countdown seconds (`seconds_to_deadline`, `seconds_ago`) ensuring seamless recovery across server restarts.

#### 4. `server.py` (FastAPI & WebSocket Communication Hub)
- **FastAPI Lifespan**: Initializes store, attempts crash recovery from SQLite, auto-loads CSV data, and starts a background `tick_loop()` running at 10 Hz with 1 Hz heartbeat syncs (`broadcast_sync()`).
- **Authentication**: Admin PIN verification with timing-safe comparison (`secrets.compare_digest`), team login codes exchanging for bearer tokens (`token_urlsafe(24)`).
- **Real-Time WebSockets**: Dedicated multiplexed channels for `/ws/captain`, `/ws/stage`, and `/ws/admin`.
- **Rate Limiting**: Sliding-window rate limiter restricting each captain to at most 3 bids per second to mitigate button mashing and denial-of-service.
- **REST Endpoints**: Data ingest (`/api/admin/upload`), setup verification (`/api/setup`), auction start (`/api/admin/start`), and CSV audit exports (`/api/admin/export/audit.csv`, `/api/admin/export/bids.csv`).

#### 5. `test_core.py` (Specification-by-Example Test Suite)
- Validates pure rule functions (`rules.py`), candidate rating calculations (`rating.py`), and auction transitions.
- Concurrency test: 40 threads waiting on a `threading.Barrier` fire bids simultaneously; verifies that **exactly one** bid wins and 39 are rejected as stale.
- Monte Carlo simulation: 5 random bot seeds run auctions through completion; verifies that every team finishes with full rosters, no negative purse balances, and zero deadlocks.

#### 6. `burst_test.py` (Load Testing Suite - Pending Implementation)
- Placeholder dedicated to end-to-end WebSocket stress testing under venue network conditions (simulating 40+ concurrent clients placing rapid bids against a live HTTP/WS server).

---

## 3. Mathematical Foundations & Core Business Rules

### 1. The Solvency Reserve Formula (Crucial Guardrail)
To prevent aggressive or naive captains from spending their entire budget on 1 or 2 marquee players and being mathematically unable to purchase remaining players, the platform enforces an inviolable reserve guardrail:

```
Max Allowable Bid = Purse - (Empty Slots Remaining After This Purchase * Floor Price)
```

Where:
- `Empty Slots After Purchase = Roster Size - (Current Roster Count + 1)`
- `Floor Price = 100 points`
- `Roster Size = 4`

**Concrete Scenarios:**
- **0 players acquired (3 empty slots remaining):**  
  `Max Bid = 10,000 - (3 * 100) = 9,700 pts`.
- **2 players acquired (1 empty slot remaining, purse 3,000):**  
  `Max Bid = 3,000 - (1 * 100) = 2,900 pts`.
- **3 players acquired (0 empty slots remaining, purse 500):**  
  `Max Bid = 500 - (0 * 100) = 500 pts` (Can spend entire remaining balance on the 4th player).

### 2. Tiered Increment Logic
Bids do not increment arbitrarily; the server computes the exact valid next price:
- **First bid on player**: Exactly the Base Price.
- **Current bid < 1,500**: Increment is **+100**.
- **Current bid >= 1,500**: Increment is **+250**.

### 3. Anti-Snipe Extension Mechanism
To neutralize automated sniper scripts, Wi-Fi latency disparities, and physical room contention:
- If a valid bid is recorded when `Time Left < 8.0 seconds`, the clock deadline is automatically reset:
  `Deadline_new = Current Time + 8.0 seconds`.

### 4. Unsold Recycling & Exponential Price Decay
When a candidate receives zero bids throughout the bidding window:
1. Candidate status changes to `UNSOLD` and moves into the secondary pool.
2. When all queued candidates in the current round conclude, unsold players are re-queued for Round R + 1.
3. Base price is discounted by 50% per round, rounded to multiples of 100, clamped at `Floor Price` (100 pts):
   `Base Price_R = max(100, round_to_100(Base Price_1 * (0.5)^(R - 1)))`.
4. Auction halts after Round 5 (`max_rounds`), delegating remaining unfilled slots to manual administrative assignment.

### 5. Candidate Valuation & Elo Rating (Offline Pre-Computation)
Rather than subjective scoring on the fly, candidates are evaluated offline using an Elo-style comparative ranking:
1. Normalize individual Aptitude, GD, and Profile metrics into percentile ranks `p_metric in [0, 1]` representing the share of competitors defeated.
2. Compute composite percentile:
   `p = 0.40 * p_Aptitude + 0.25 * p_GD + 0.35 * p_Profile`.
3. Clamp `p in [0.02, 0.98]` and calculate Elo rating:
   `Rating = 1500 + 400 * log10(p / (1 - p))`.
4. Rank candidates by Rating into 4 tiers:
   - **Tier 1 (Top 10%)**: Base Price = 1,000 pts
   - **Tier 2 (Next 20%)**: Base Price = 600 pts
   - **Tier 3 (Next 30%)**: Base Price = 400 pts
   - **Tier 4 (Bottom 40%)**: Base Price = 200 pts

---

## 4. State Machine Architecture & Operational Modes

```
SETUP -> start() -> IDLE -> next -> PREVIEW -> time -> LIVE -> time -> RESULT -> auto -> next ...
                                                         |                   ^
                                                         |      undo sale ---| (back to LIVE)
                                                         v
                                              DONE (all squads full)

Manual Override ON:
LIVE -> time -> AWAITING_HAMMER --+-- Confirm Sale -> SOLD (RESULT)
                                  +-- Mark Unsold   -> UNSOLD (RESULT) -> admin presses Next
```

### Mode Comparison: Auto vs. Manual Override

| Feature | Auto Mode (`manual_mode = False`, Default) | Manual Override (`manual_mode = True`) |
| :--- | :--- | :--- |
| **Clock Expiry in LIVE** | Automatically finalizes sale to current leader. | Enters `AWAITING_HAMMER`; locks bids; waits for admin. |
| **Closing a Sale** | Driven strictly by countdown clock. | Admin clicks `Confirm Sale` or `Mark Unsold`. |
| **Early Hammer** | Admin can intervene early if needed. | Admin can trigger `Confirm Sale` at any second ("Going twice..."). |
| **Advancing to Next** | Auto-advances after 8s result animation. | Admin must explicitly click `Next Player`. |
| **Mid-Event Toggle** | Seamless: switch takes effect at next state boundary without disrupting current bids. |

---

## 5. Screen Specifications & User Interactions

### 1. Captain Console (`/captain`)
- **Header**: Team identifier, live purse balance, roster indicator (`2/4 Filled`), connection status dot (green/yellow/red).
- **Bidding Arena**:
  - Live candidate card (name, tier, rating, skill tags, project highlights).
  - Current bid amount and leading team badge.
  - Personal state pill: `LEADING` (blue/green), `OUTBID` (amber pulse), `INACTIVE` (gray), `FULL` (purple).
  - **The Action Button**: Large, touch-friendly button labeled with the exact price: **"BID 1,500"**.
  - **Optimistic State & Rejection Feedback**: Button immediately transitions to "Sending..." on click. If rejected by the server, it reverts and displays a clear message (e.g., *"Cannot bid: Must reserve 200 pts for 2 remaining empty slots"*).
  - **Budget Tracker**: Displays current maximum allowable single bid so captains do not perform mental arithmetic.

### 2. Stage Screen (`/stage`)
- **Auditorium Projector Optimized**: High-contrast, typography scaled for 1080p/4K viewing from 30+ meters.
- **Candidate Showcase**: High-res photo/avatar, full name, branch, technical domain tag, tier badge, rating.
- **Dynamic Clock**: Massive visual countdown timer with audio-visual cues during the final 5 seconds.
- **Standings Grid**: Real-time table displaying all competing teams, remaining purses, and filled slots.
- **Audit Feed**: Rolling live feed showing the last 4 bids with timestamps.
- **Overlays**: Clear banners for `PAUSED`, `BIDS FROZEN`, `SOLD`, or `UNSOLD`.

### 3. Admin Console (`/admin`)
- **Flow & Timing**: Next Player, Jump to Candidate, Pause/Resume, Extend (+10s), Reset Timer.
- **Hammer Controls**: Manual Override Toggle, Confirm Sale, Mark Unsold, Freeze Bids.
- **Dispute Resolution Tools**:
  - `Undo Last Bid`: Immediately revokes erroneous bid; previous bidder becomes leader.
  - `Undo Sale`: Available during Result window; restores team purse, removes player from roster, reopens bidding for 10s.
  - `Edit Purse`: Manually adjust team points with full audit logging (records old and new balance).
  - `Substitute Bid (Proxy)`: Place bid on behalf of a team experiencing hardware or network failure (enforces identical validation rules).
- **Diagnostics**: Real-time WebSocket connection monitor displaying ping/latency per captain device.

---

## 6. Non-Negotiable Invariants: Features That Must ALWAYS Be Correct

Any bug in these areas invalidates the competitive integrity of the hackathon:

1. **Zero-Race Concurrency Guarantee**:
   - When 40 captains click bid simultaneously, exactly **one** bid must succeed. The remaining 39 must be cleanly rejected with `STALE_BID`.
   - Guaranteed by: Single-threaded Python GIL + explicit `threading.RLock()` wrapping all read-modify-write cycles in `auction.py`.

2. **Absolute Solvency Invariant**:
   - Under no circumstances can a team's purse drop below `(4 - roster) * 100`.
   - A team must never be unable to afford a candidate at the base floor price of 100.
   - Guaranteed by: `rules.check_bid` validating `rules.max_bid` prior to accepting any bid.

3. **Strict Next-Price Matching**:
   - A client cannot submit an arbitrary price. The submitted price must equal `auction.next_price()`.
   - Prevents race conditions, malicious client payloads, double increments, and price skipping.

4. **Self-Outbidding Prevention**:
   - A team that currently holds the highest bid cannot place another bid.
   - Guaranteed by: `auction.leader() == team_id` rejection.

5. **Financial Timing Guarantee (No Premature Deductions)**:
   - Purse points are deducted **only upon finalized sale**, never during the bidding sequence.
   - Allows undos and bid rollbacks to remain pure in-memory operations without requiring distributed transaction reversals.

6. **Crash-Resilient State Recovery**:
   - If the server process crashes or power fails, restoring from SQLite must resume the auction at the exact phase, candidate, leading bid, roster, and remaining countdown time.

---

## 7. Security Architecture & Threat Mitigation

| Threat Vector | Severity | Vulnerability Description | Defensive Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Captain Impersonation** | Critical | Unauthorized users submitting bids on behalf of other teams. | High-entropy bearer tokens (`secrets.token_urlsafe(24)`) generated upon authenticating with sealed team login codes; tokens stored in server memory and matched strictly to `team_id`. |
| **Admin Privilege Escalation** | Critical | Attackers guessing admin PIN or executing timing attacks. | Constant-time PIN verification (`secrets.compare_digest`); environment variable configuration (`ADMIN_PIN`); rate limiting on admin login endpoint. |
| **Bid Spamming / Denial of Service** | High | Malicious scripts or panicking captains mashing the bid button (e.g. 50 bids/sec). | Server-side sliding-window rate limiter per team (`BID_RATE_LIMIT = 3 bids/sec`). Rejected instantly before reaching the state machine lock. |
| **Arbitrary Bid Amount Tampering** | High | Attackers manipulating client JS to send illegal bids (e.g. 1 point or skipping increments). | Zero client trust: `rules.check_bid` enforces exact match `price == next_price`, purse limits, and reserve constraints. |
| **Client Clock Manipulation** | Medium | Captain altering device clock to claim they placed a bid before expiry. | All deadlines and timestamps calculated strictly via server-side monotonic clock (`time.monotonic()`); clients receive relative `seconds_left`. |
| **XSS & CSV Injection** | Medium | Malicious payloads in candidate names, projects, or team names displayed on projector. | Proper HTML escaping on frontend rendering (no unescaped `innerHTML`); strict type coercion in CSV loaders. |
| **Venue Wi-Fi Partitioning** | High | Unstable venue Wi-Fi causing captain disconnections during bidding. | Automatic WebSocket reconnect with exponential backoff on clients; 1 Hz synchronization heartbeat; Admin "Substitute Bid" tool to act on physical placard raises. |
| **Server Mid-Event Crash** | Critical | Process crash due to OS restart, power loss, or unhandled exception. | Incremental state snapshotting to SQLite on every bid, sale, and phase change. Stateless monotonic delta reconstruction (`from_dict`). |

---

## 8. Missing Modules & Implementation Roadmap

To transition from the current core state machine to a fully operational, deployable system, the following modular components must be created:

| Module | Primary Responsibility |
| :--- | :--- |
| **`config.py`** | Centralized configuration dataclass (`purse`, `roster_size`, `tier_base`, `bid_seconds`, etc.). |
| **`rules.py`** | Pure business logic (`Verdict`, `next_price`, `max_bid`, `round_base_price`, `check_bid`). |
| **`rating.py`** | Offline Elo-style ranking and tiering script (`elo_rating`, `build`). |
| **`loader.py`** | Candidate CSV parser and validator (`load_candidates`). |
| **`teams_loader.py`** | Teams and secret login codes CSV loader (`load_teams`). |
| **`store.py`** | SQLite persistence engine (WAL mode, state snapshots, audit logs, bid logs, CSV export). |
| **`burst_test.py`** | High-concurrency WebSocket load tester (40+ clients). |
| **`static/`** | Responsive HTML5/Tailwind/Vanilla JS frontends (`captain.html`, `stage.html`, `admin.html`). |

---

## 9. Recommended Implementation Sequence

1. **Step 1: Core Engine Completion (`config.py`, `rules.py`)**  
   Implement the configuration and pure rule engine. Validate with `python -m unittest test_core.RulesTests`.
2. **Step 2: Candidate Rating & Ingestion (`rating.py`, `loader.py`, `teams_loader.py`)**  
   Implement the Elo ranking calculator and CSV loaders. Validate with `python -m unittest test_core.RatingTests`.
3. **Step 3: State Persistence Engine (`store.py`)**  
   Implement the SQLite WAL store with JSON state serialization and CSV export capabilities. Validate with `python -m unittest test_core.AuctionTests`.
4. **Step 4: Concurrency Load Testing (`burst_test.py`)**  
   Populate `burst_test.py` to simulate 40 concurrent WebSocket captains firing burst bids against `server.py`.
5. **Step 5: Frontend Development (`static/`)**  
   Build responsive, zero-build, plain HTML/CSS/JS interfaces for `/captain`, `/stage`, and `/admin`.
