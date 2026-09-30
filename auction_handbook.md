# IET Hackathon Auction: Team Handbook

*Everything decided so far, how the system works, how to run it on the day, and what to do when something breaks. Written so someone new can take over.*

---

## 1. What we are building

A live auction website for the hackathon. Team **captains bid on players** (the students who passed the aptitude and GD rounds) to build their squads. Each captain uses their own device. A projector shows the **stage screen**. One person, the **admin**, controls the flow.

**The one rule that explains the whole design:** the **server is the only referee**. Screens never decide anything. They send a request ("Team 3 wants to bid 1500") and show whatever the server says happened.

### Event numbers (current expectation)

| Item | Value |
|---|---|
| Students at the start | 150-200 |
| Players available for auction (after Aptitude + GD) | **30 to 60** (worst case 30-40, best case 40-60) |
| Roster per team | **4 players**, captain not counted |
| Captains | A separate group from the players |
| Teams | `floor(players / 4)` at most: 30 players = 7 teams, 40 = 10, 60 = 15 |
| Purse per team | **10,000** (assumed, see section 12) |
| Expected auction length | 1-2 hours for 30-60 sales |

Team count is fixed **after the final player list is locked**. That makes "not enough players" impossible by construction, and the setup check (section 8) is a safety net on top.

---

## 2. Auction flow (what everyone sees)

For each player, the system runs these phases automatically:

1. **PREVIEW** (default 30 s). Every screen shows the player's profile: name, projects, experience, rating. Bidding is locked. The base price is hidden.
2. **LIVE** (default 30 s). The base price appears. Captains see their purse, the current bid, the leading team, the next valid bid, and a countdown.
3. **RESULT** (default 8 s). When the timer ends, the **highest bidder wins automatically**. All screens show a "SOLD" animation with the player and winning team. If nobody bid, it shows "UNSOLD". This window is also the admin's chance to **undo**.
4. **Next player** loads automatically.

Unsold players come back in a later **round** at a lower base price (section 4).

### Auto mode vs. Manual mode (admin toggle)

The system defaults to the flow above, fully **automatic**. The admin console has one switch, **Manual Override**, that hands every decision to the admin instead — this is the "conduct the whole auction by hand" mode, useful if the automation feels wrong on the day, or for a more theatrical auctioneer-style event.

| | **Auto (default)** | **Manual Override (admin switch on)** |
|---|---|---|
| When the clock hits 0 | Sells automatically to the highest bidder | Bidding just locks and **waits** for the admin |
| Ending a sale | Happens by the clock | Admin presses **Confirm Sale** (sells to the current highest bidder — can even be pressed *before* the clock runs out, like a real "going once, going twice, sold") or **Mark Unsold** (forces the player to Unsold and discards any bids, e.g. to resolve a dispute — safe, since no points are charged until a sale is confirmed) |
| After a result | Next player loads automatically | Admin must press **Next Player** |
| Bids while waiting on the hammer | N/A | Locked — captains see "Waiting for the auctioneer to close this player" |

The switch can be flipped **at any point** without disturbing whatever is currently on screen — it only changes what happens at the *next* transition. So the admin can run most of the event on auto and drop into manual only for a tricky player, or run the whole thing manually from the start. Both modes use the exact same bid-validation rules, reserve formula and undo logic underneath, so nothing about fairness changes — only who pulls the trigger.

This mirrors the "auctioneer hammer" idea from the original brief, but implemented as a toggle rather than the only mode, so you get the speed of automation by default and the safety of manual control on demand.

The auction ends when every team has 4 players, or candidates run out, or the maximum number of rounds is reached.

---

## 3. The three screens

### Captain screen
- Team name, purse, squad count (e.g. 2/4), connection dot.
- Current player, current price, leading team, countdown.
- Status badge: **LEADING**, **OUTBID**, **INACTIVE**, or **FULL**.
- One big button showing the exact next bid, e.g. **BID 1500**. If the bid is not allowed, the button is disabled and a plain-English reason is shown under it (e.g. "Max bid is 9700: keep 100 for each of your 3 other empty slots").
- "Max bid you can place" always displayed, so nobody does mental maths.
- Optimistic feel: the button shows "sending..." and reverts with a message if the server rejects it.

### Stage screen (projector, read-only)
- Huge player name, price, leading team, countdown.
- SOLD / UNSOLD animation with player details and team name.
- Live bid feed and all-team standings (purse, squad count).
- Shows "BIDS FROZEN" or "PAUSED" clearly so the room understands any delay.

### Admin console
| Group | Controls |
|---|---|
| Flow | Next player, jump to a specific player |
| Mode | **Manual Override** switch — auto-sell/auto-advance (default) vs. admin conducts every step |
| Clock | Pause / Resume, +10 s, Reset timer, set preview / bid / result durations |
| Hammer (manual mode only) | **Confirm Sale** (sell to current leader, any time), **Mark Unsold** (force unsold, discard bids) |
| Safety | **Freeze bids**, **Undo last bid**, undo a sale during the result window |
| Money | Edit any team's purse (always logged with old and new value) |
| Substitute bidding | Bid on behalf of a team whose device died (uses the same validation as a captain) |
| Info | Team panel (purse, squad, connected/disconnected dot), export state to CSV for the paper fallback |

---

## 4. Rules (single source of truth)

All numbers live in `config.py`. Change them there, nowhere else.

| Rule | Default |
|---|---|
| Purse | 10,000 |
| Base prices by tier | Tier 1 = 1000, Tier 2 = 600, Tier 3 = 400, Tier 4 = 200 |
| Increment | **+100** while the current bid is below 1500, **+250** at 1500 and above |
| First bid | Exactly the base price |
| Floor price | 100 (lowest any base price can fall to) |
| **Reserve formula** | `Max bid = purse - (empty slots after this purchase x 100)` |
| Anti-snipe | A bid with **less than 8 s** left resets the clock to 8 s |
| No bids | Player is UNSOLD and returns in the next round |
| Round price drop | Base price falls **50% per round**, rounded to a multiple of 100, never below floor |
| Max rounds | 5, then the auction stops and the admin assigns leftovers manually |
| Money timing | **Points are deducted only when a sale is finalised**, not at bid time |

**Why the reserve formula exists:** it guarantees every team can always afford to fill all 4 slots. A team can never blow its whole purse on one player and get stuck. Example: purse 10,000, buying the first player, 3 slots stay empty, so max bid = 10,000 - 300 = 9,700.

**Why deduct at sale, not at bid:** bids are just a log. Undoing a bid means marking it void, and the previous bidder is leader again. No refunds, no reversing transactions.

**Bid checks, in this order** (first failure is returned with a reason):
1. Auction is LIVE, not paused, not frozen.
2. Team's squad is not full.
3. Team is not already the leader.
4. The submitted price equals the current next valid price. (Otherwise it is stale: someone bid first. This also stops double-clicks.)
5. Price is within the team's purse.
6. Price is within the reserve limit.

Two captains clicking at the same instant: the server handles bids one at a time. The first is accepted, the second is stale and rejected, and gets the updated price back. This is covered by an automated test with 40 simultaneous bids: exactly one wins.

---

## 5. Player rating (Elo-style, computed before the event)

We do **not** calculate anything live. A script produces a CSV before the event and the auction only reads it.

Real Elo needs head-to-head matches, which we do not have. So we use the Elo formula in reverse:

```
rating = 1500 + 400 x log10( p / (1 - p) )
```

`p` is the share of the *other* candidates a player beats.

**Steps** (all in `rating.py`):
1. For each of Aptitude, GD and Profile, rank all players. Turn each rank into `p` = share of others beaten (ties count half).
2. Combine: `p = 0.40 x Aptitude + 0.25 x GD + 0.35 x Profile`.
3. Clamp `p` to [0.02, 0.98], then apply the formula. Ratings land roughly between 820 and 2180.
4. Assign tiers by rank: **top 10% = Tier 1, next 20% = Tier 2, next 30% = Tier 3, rest = Tier 4.** Players with equal ratings share a tier.
5. Base price comes from the tier.

**Important:** percentiles depend on who is in the pool. **Run the script once the final list is locked**, never on the 150-200 list. It takes seconds.

---

## 6. System design and code layout

```
Captain devices ─┐
Stage screen ────┼── WebSocket ──► one FastAPI server ──► database (SQLite/Postgres)
Admin console ───┘                 (live state in memory, one lock,
                                    server-side clock)
```

**Why one server and one process:** one process means one lock, so "two bids at once" is solved trivially, the timer is server-authoritative for free, and there are few moving parts. **Run exactly one instance. Never run two copies or use serverless.**

**Load check:** 15 captains is trivial. Even 60 clicking at once is a few hundred requests in a second, and each bid check is a few integer comparisons. The real-world risk is venue Wi-Fi, not the server.

### Modules

Each file has one job and can be tested alone.

| File | Job | Status |
|---|---|---|
| `config.py` | Every tunable number | Built |
| `rating.py` | Offline: scores to Elo rating, tier, base price | Built + tested |
| `loader.py` | Reads the rated CSV into the auction | Built |
| `rules.py` | Pure functions: increments, reserve, bid validation, round prices | Built + tested |
| `auction.py` | State machine, clock, lock, rounds, undo, admin controls, views for screens | Built + tested |
| `store.py` | Save and restore state after every action | **Not built yet** |
| `server.py` | WebSocket/HTTP endpoints, team login, admin PIN, 10x/sec `tick()` | **Not built yet** |
| `static/` | Captain, stage and admin pages (plain HTML/JS) | **Not built yet** |

Rule of thumb for fixes: money or rule problem? Look in `rules.py`. Flow, timer or state problem? Look in `auction.py`. Screen problem? Look in `static/`. Nearly all bug risk is in the first two, and both are testable without a browser.

### State machine

```
SETUP ─start()─► IDLE ─next─► PREVIEW ─time─► LIVE ─time─► RESULT ─auto─► next player ...
                                            (pause / freeze possible)        │
                                                                  undo sale ─┘ (back to LIVE)
                                     ... ─► DONE (all squads full / no candidates / max rounds)

Manual Override ON, LIVE at 0 seconds goes to a fourth phase instead of auto-selling:

              ┌─ Confirm Sale ─► SOLD (RESULT)
LIVE ─time─► AWAITING_HAMMER ─┤
   ▲                          └─ Mark Unsold ─► UNSOLD (RESULT) ── admin must press Next Player
   └── Confirm Sale / Mark Unsold can also be pressed early, any time bidding is LIVE
```

---

## 7. What is built and tested today

`python3 -m unittest -v` runs 18 tests, all passing. They cover:
- Increments, reserve formula, stale bids, leader re-bid, full squad
- Round price drops and floor
- Elo rating and tier assignment
- Full flow with fake clock: preview, live, auto-sell, auto-advance
- Anti-snipe reset
- Unsold players returning in round 2 at a lower price
- Undo during live bidding and undo of a sale
- Pause, resume and freeze
- Setup check failing when players are short
- Purse edits being logged
- **40 simultaneous bids: exactly one wins**
- Random bots across 5 seeds: auction always finishes with every squad full and no negative purse
- **Manual Override:** the clock hitting 0 waits for the admin instead of auto-selling, bidding is locked while waiting, the admin can't skip the hammer, an early Confirm Sale works before the clock runs out, Mark Unsold discards bids without charging anyone, and the mode can be toggled mid-event without disturbing whatever is on screen

Not covered yet, because it is not built: the network layer, saving/restoring state, and the screens.

---

## 8. Setup checklist (before the event)

1. **Lock the player list** after the GD and aptitude rounds.
2. Prepare `raw.csv` with columns `id, name, aptitude, gd, profile`, plus any extra columns you want shown on screen (e.g. `projects`, `experience`).
3. Run `python3 rating.py raw.csv rated.csv`. Open `rated.csv` and sanity check the top and bottom players.
4. Decide the team count: `floor(players / 4)`. Prepare the teams list (id, team name, login code).
5. Run the **setup check** (`Auction.setup_report()`). It shows teams, players, players needed, shortfall, spares, and whether every purse covers 4 x floor price. **The auction cannot start unless this is green.**
6. Confirm timings (preview, bid, result) with the organisers.

### If players are short (fallback ladder, decided in advance by organisers)
1. **Reduce team count** so that `teams x 4 <= players`. Preferred. Update the teams file.
2. **Lower the roster size** for everyone (e.g. 3), by changing one config value.
3. **Allow short squads.** Least fair, so a last resort.

Setup check example from the sample data: 40 players and 10 teams gives `needed 40, short_by 0, ok = True`.

---

## 9. Event-day runbook

### Before doors open
- [ ] Server running, all teams can log in, admin PIN works
- [ ] Every captain device tested on the **actual venue network**, all connected at once
- [ ] Stage screen on the projector, checked from the back of the room
- [ ] **Mock auction** with fake players and real captains (shows the anti-snipe, a disabled button with its reason, and the sold animation)
- [ ] Captain cheat sheet handed out (section 10)
- [ ] Paper fallback ready: printed squad sheet and purse tracker
- [ ] Database backup copied to a laptop that can run the server as standby

### During the auction
- One person operates the admin console. A second person watches the stage screen and the paper tracker.
- Announce out loud when you freeze or pause, so captains do not think it is a bug.

### Incident playbook

| Problem | What to do |
|---|---|
| A captain says a bid did not register | Check the bid feed. If it is missing, use **substitute bid** for that team. |
| Captain's device or Wi-Fi died | Admin uses **substitute bid** on their behalf, same validation applies. |
| Dispute in the last seconds | **Freeze bids** or **Pause**, resolve verbally, then **Undo last bid** if needed, then resume. |
| Wrong sale confirmed | During the result window, press **Undo**. Bidding reopens for 10 s. |
| Wrong purse | **Edit purse.** The old and new values are logged automatically. |
| Wrong player shown | **Jump to player.** Allowed only if the current player has no bids (otherwise undo the bids first). |
| Timer feels wrong | Pause, **Reset timer** or **+10 s**. |
| Server crashed | Restart it. State reloads from the database (once `store.py` exists). Screens reconnect and get the full state. |
| Server will not come back | Copy the database to the standby laptop and start it there. Captains switch to the new address. |
| Everything is down | Switch to the paper tracker. Continue verbally. Enter results afterward. |
| A team cannot afford anyone | Should not happen because of the reserve formula. If it does, check whether a purse was edited. |
| Auction stops with empty slots ("max rounds reached") | Admin assigns the remaining players manually to teams that still have empty slots. Log it. |

---

## 10. Captain cheat sheet (give this to every captain)

1. **Budget:** You have 10,000 points and must buy exactly **4 players**. The system blocks bids that would leave you unable to fill your squad, and tells you why.
2. **Increments:** Bids go up by 100 below 1500, and by 250 from 1500. The button always shows the exact amount.
3. **The clock:** If someone bids in the last 8 seconds, the clock resets to 8.
4. **The hammer:** When the clock ends, the highest bidder wins **automatically**. There is a short window where the admin can undo an error.

---

## 11. Risks and how we handle them

| Risk | Handling |
|---|---|
| Player pool ends up smaller than planned | Team count comes from the final pool. Setup check blocks starting if short. Fallback ladder in section 8. |
| Venue Wi-Fi congestion | Test with all devices on the real network. Prefer a dedicated router (few captains makes this realistic). Run the server on a laptop as backup. |
| Server crash mid-event | Save state after every accepted bid and every result. Standby laptop with database copy. Test a mid-auction restart. |
| Timer wrong after pause or restart | On pause, store the *remaining* time. On resume, recompute the deadline. |
| Admin mistakes | Log every admin action. Confirmation clicks on destructive actions. Undo available. |
| Free hosting sleeping or throttling | Use an always-on host (small VPS, or a single always-on instance). Avoid free tiers that sleep. Check current terms before choosing. |
| Ratings look unfair | Publish the formula and the rated list early. It is deterministic and anyone can verify it. |
| Rules confuse captains | Mock auction, cheat sheet, and every disabled button shows its reason. |

**Hosting plan:** cloud is the priority, local is the backup. Serve the frontend from the same server, so there is one thing to deploy and one thing that can fail. Keep a laptop plus router ready as a hot standby.

---

## 12. Decisions still open

These were assumed or not confirmed. Please settle them before building the rest.

1. **Purse:** 10,000 assumed. Run a simulation on the real rated list to check it is not too loose or too tight.
2. **Base prices and tier cut-offs:** 1000/600/400/200 and top 10/20/30/40% are proposals.
3. **Timings:** 30 s preview, 30 s bidding, 8 s result are defaults.
4. **Team count and who decides the fallback:** organisers decide before the event, not the admin live.
5. **Leftover assignment:** an "auto-fill" tool for the end-game (when remaining players equal remaining empty slots) is designed but **not built**. Today the admin assigns manually.
6. **Hosting choice:** specific provider not chosen.
7. **Who runs the admin console, and who is the backup operator?**

---

## 13. Build status and next steps

**Done:** config, rating script, rules, auction state machine, loader, 15 passing tests, sample data.

**Next, in order:**
1. `store.py`: save state after every action and reload on start. Test a restart mid-auction.
2. `server.py`: WebSocket layer, team login codes, admin PIN, rate limit (about 3 bids/second per captain), tick loop.
3. Load test: 40 fake captains bidding at once against the real server.
4. Admin console page (most critical), then captain page, then stage page. Plain HTML/JS.
5. Auto-fill tool and CSV export.
6. Mock auction, venue network test, standby laptop rehearsal.

---

## 14. Quick commands

```bash
# Run all tests
python3 -m unittest -v

# Compute ratings, tiers and base prices from raw scores
python3 rating.py raw.csv rated.csv

# Check setup in Python
from loader import load_candidates
from auction import Auction
from config import Config
a = Auction(Config(), teams, load_candidates("rated.csv"))
print(a.setup_report())
```

## 15. Glossary

- **Purse:** points a team can spend.
- **Roster / squad:** the 4 players a team buys (captain not counted).
- **Tier:** price band a player is placed in, based on rating rank.
- **Base price:** starting price for a player, set by tier and round.
- **Reserve formula:** cap on a bid so a team can always afford its remaining empty slots.
- **Anti-snipe:** a late bid resets the clock to 8 s.
- **Round:** a pass through the players. Unsold players return in the next round at a lower base price.
- **Freeze:** locks all bidding while the clock keeps its state. **Pause** stops the clock too.
- **Substitute bid:** admin bids for a team whose device failed.