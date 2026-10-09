const state = {
  snapshot: null,
  teamToken: localStorage.getItem('iet_team_token') || '',
  adminPin: sessionStorage.getItem('iet_admin_pin') || '',
  captainView: null,
  stageSocket: null,
  adminCandidates: [],
  lastResultShown: null,
  splashTimeout: null,
};

const $ = (id) => document.getElementById(id);

const money = (val) => {
  if (val === null || val === undefined) return '—';
  return `${Number(val).toLocaleString('en-IN')} PTS`;
};

const timeStr = (seconds) => {
  const total = Math.max(0, Math.ceil(Number(seconds) || 0));
  const m = String(Math.floor(total / 60)).padStart(2, '0');
  const s = String(total % 60).padStart(2, '0');
  return `${m}:${s}`;
};

const api = async (path, options = {}) => {
  const headers = { ...(options.headers || {}) };
  if (options.body !== undefined && options.body !== null) {
    if (!headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }
  }

  const response = await fetch(path, {
    ...options,
    headers,
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail || body.reason || body.message || 'Request failed';
    throw new Error(
      typeof detail === 'string'
        ? detail
        : detail.map?.((item) => item.msg || JSON.stringify(item)).join(', ') || JSON.stringify(detail)
    );
  }
  return body;
};

const getTeamAcronym = (teamId, teamName) => {
  const acronymsById = {
    1: 'CSK',
    2: 'RCB',
    3: 'MI',
    4: 'RR',
    5: 'KKR',
    6: 'GT',
    7: 'SRH',
    8: 'DC',
  };
  if (teamId && acronymsById[teamId]) return acronymsById[teamId];
  if (!teamName) return 'TM';
  const words = teamName.trim().split(/\s+/);
  if (words.length >= 2) {
    return words.map((w) => w[0]).join('').toUpperCase().slice(0, 4);
  }
  return teamName.slice(0, 3).toUpperCase();
};

const setMessage = (id, message = '', good = false) => {
  const node = $(id);
  if (node) {
    node.textContent = message;
    node.style.color = good ? 'var(--stadium-pitchGreen)' : 'var(--stadium-ctaRed)';
  }
};

let teamsSignature = '';
function populateTeamSelects(teams) {
  if (!teams || !teams.length) return;
  const sig = teams.map((t) => `${t.id}:${t.name}:${t.captain || ''}`).join('|');
  if (sig === teamsSignature) return;
  teamsSignature = sig;

  const captainSelect = $('captain-team-id');
  if (captainSelect) {
    const currentVal = captainSelect.value;
    captainSelect.innerHTML =
      '<option value="" disabled' + (!currentVal ? ' selected' : '') + '>Select your team...</option>' +
      teams.map((t) => `<option value="${t.id}">${t.id} // ${t.name}${t.captain ? ` (Capt: ${t.captain})` : ''}</option>`).join('');
    if (currentVal) captainSelect.value = currentVal;
  }

  const proxySelect = $('admin-proxy-team');
  if (proxySelect) {
    const currentVal = proxySelect.value;
    proxySelect.innerHTML =
      '<option value="" disabled' + (!currentVal ? ' selected' : '') + '>Choose franchise...</option>' +
      teams.map((t) => `<option value="${t.id}">${t.name} (${t.id})${t.captain ? ` [Capt: ${t.captain}]` : ''}</option>`).join('');
    if (currentVal) proxySelect.value = currentVal;
  }
}

function renderSnapshot(snapshot) {
  if (!snapshot) return;
  state.snapshot = snapshot;

  const candidate = snapshot.candidate;
  const profile = candidate?.profile || {};

  if ($('connection-label')) $('connection-label').textContent = 'TELEMETRY LINKED';
  if ($('connection-dot')) $('connection-dot').classList.remove('offline');

  if ($('stage-phase')) $('stage-phase').textContent = snapshot.paused ? 'PAUSED' : snapshot.phase;
  if ($('stage-round')) $('stage-round').textContent = String(snapshot.round || 1).padStart(2, '0');

  if (snapshot.stats && $('stage-progress-text')) {
    const sold = snapshot.stats.sold_count || 0;
    const total = snapshot.stats.total_candidates || 36;
    $('stage-progress-text').textContent = `${sold} / ${total} PLAYERS`;
  }

  const timeLeft = Number(snapshot.seconds_left) || 0;
  if ($('stage-clock')) $('stage-clock').textContent = timeStr(timeLeft);

  const timerBox = $('stage-timer-box');
  if (timerBox) {
    timerBox.classList.remove('danger-time');
    if (snapshot.phase === 'LIVE' && !snapshot.paused) {
      if (timeLeft <= 8) {
        timerBox.classList.add('danger-time');
        if ($('stage-clock-state')) $('stage-clock-state').textContent = '⚠️ ANTI-SNIPE ACTIVE';
      } else {
        if ($('stage-clock-state')) $('stage-clock-state').textContent = 'LIVE BIDDING CLOCK';
      }
    } else if (snapshot.phase === 'PREVIEW') {
      if ($('stage-clock-state')) $('stage-clock-state').textContent = 'PREVIEW CLOCK';
    } else if (snapshot.paused) {
      if ($('stage-clock-state')) $('stage-clock-state').textContent = '⏸ CLOCK PAUSED';
    } else {
      if ($('stage-clock-state')) $('stage-clock-state').textContent = snapshot.phase;
    }
  }

  if (candidate) {
    if ($('stage-candidate-id')) $('stage-candidate-id').textContent = `#${String(candidate.id).padStart(3, '0')}`;

    const tierNames = { 1: 'TIER 1 ⭐ ELITE', 2: 'TIER 2 💎 PRIME', 3: 'TIER 3 🏆 GOLD', 4: 'TIER 4 ⚡ SILVER' };
    if ($('stage-tier')) $('stage-tier').textContent = tierNames[candidate.tier] || `TIER ${candidate.tier}`;
    if ($('stage-candidate-name')) $('stage-candidate-name').textContent = candidate.name;

    if ($('stage-role')) $('stage-role').textContent = profile.role ? `🏏 ${profile.role}` : '🏏 CRICKET PROSPECT';
    if ($('stage-college')) $('stage-college').textContent = profile.college || 'SIES GST';

    if ($('stage-aptitude')) $('stage-aptitude').textContent = profile.aptitude !== undefined ? profile.aptitude : '—';

    if ($('stage-gd')) $('stage-gd').textContent = profile.gd !== undefined ? profile.gd : '—';

    if ($('stage-rating')) $('stage-rating').textContent = candidate.rating ? Number(candidate.rating).toLocaleString() : '—';
    if ($('stage-base')) $('stage-base').textContent = money(candidate.base_price);

    const tags = [];
    if (profile.batting_style) tags.push(`Batting: ${profile.batting_style}`);
    if (profile.bowling_style && profile.bowling_style !== 'None') tags.push(`Bowling: ${profile.bowling_style}`);
    if (profile.skill1) tags.push(`Skill: ${profile.skill1}`);
    if (profile.skill2) tags.push(`Skill: ${profile.skill2}`);
    if (profile.skill3) tags.push(`Skill: ${profile.skill3}`);
    if (profile.cgpa) tags.push(`CGPA: ${profile.cgpa}`);

    for (const [k, v] of Object.entries(profile)) {
      if (!['role', 'college', 'aptitude', 'gd', 'batting_style', 'bowling_style', 'skill', 'skill1', 'skill2', 'skill3', 'cgpa'].includes(k) && v) {
        tags.push(`${k.replace('_', ' ')}: ${v}`);
      }
    }

    if ($('stage-tags')) {
      $('stage-tags').innerHTML = tags.length
        ? tags.map((t) => `<span class="skill-tag-pill">${t}</span>`).join('')
        : '<span class="skill-tag-pill">PROSPECT PROFILE VERIFIED</span>';
    }
  } else {
    if ($('stage-candidate-id')) $('stage-candidate-id').textContent = '#000';
    if ($('stage-tier')) $('stage-tier').textContent = 'STANDBY';
    if ($('stage-candidate-name')) $('stage-candidate-name').textContent = 'WAITING FOR AUCTION';
    if ($('stage-role')) $('stage-role').textContent = '🏏 STANDBY';
    if ($('stage-college')) $('stage-college').textContent = 'SIES GST';
    if ($('stage-aptitude')) $('stage-aptitude').textContent = '—';
    if ($('stage-gd')) $('stage-gd').textContent = '—';
    if ($('stage-rating')) $('stage-rating').textContent = '—';
    if ($('stage-base')) $('stage-base').textContent = '—';
    if ($('stage-tags')) $('stage-tags').innerHTML = '<span class="skill-tag-pill">AUCTION SYSTEM READY</span>';
  }

  if ($('stage-bid')) $('stage-bid').textContent = money(snapshot.current_bid);
  if ($('stage-leader')) $('stage-leader').textContent = snapshot.leader ? snapshot.leader.toUpperCase() : 'NO BIDS PLACED';
  if ($('stage-frozen-badge')) {
    $('stage-frozen-badge').textContent = snapshot.frozen ? 'FROZEN' : 'OPEN';
    $('stage-frozen-badge').style.color = snapshot.frozen ? 'var(--stadium-ctaRed)' : 'var(--stadium-amber)';
  }

  if ($('stage-next-price')) {
    $('stage-next-price').textContent = snapshot.next_price
      ? money(snapshot.next_price)
      : candidate
      ? money(candidate.base_price)
      : '—';
  }

  const feedNode = $('stage-bids-feed');
  if (feedNode) {
    if (snapshot.recent_bids?.length) {
      feedNode.innerHTML = snapshot.recent_bids
        .map(
          (b) => `
        <div class="feed-item-row team-border-${b.team_id || 1}">
          <span style="color:#FFF; font-weight:700;">${b.team_name}</span>
          <strong style="color:var(--stadium-amber); font-weight:800;">${money(b.amount)}</strong>
        </div>
      `
        )
        .join('');
    } else {
      feedNode.innerHTML = '<div class="feed-item-row" style="color:#64748B;">No active bids on current prospect.</div>';
    }
  }

  const teamsNode = $('stage-teams');
  if (teamsNode && snapshot.teams?.length) {
    teamsNode.innerHTML = snapshot.teams
      .map((t) => {
        const isLeader = snapshot.leader_id === t.id;
    const isFull = t.roster >= (snapshot.roster_size || 4);

        const rosterSize = snapshot.roster_size || 4;

        const captainChip = t.captain
          ? `<div class="squad-mini-chip" style="background:var(--stadium-amber); color:var(--stadium-ink);">
              <span>🏆 ${t.captain}</span>
              <strong style="color:var(--stadium-ink);">CAPTAIN</strong>
            </div>`
          : '';

        const playerChips = t.players?.length
          ? t.players
              .map(
                (p) => `
            <div class="squad-mini-chip">
              <span>${p.name}</span>
              <strong style="color:var(--stadium-ink);">${money(p.price)}</strong>
            </div>
          `
              )
              .join('')
          : '';

        const squadContent = (captainChip || playerChips)
          ? captainChip + playerChips
          : `<div style="font-family:var(--font-mono); font-size:9px; color:#94A3B8; padding:2px 0;">Open (0 / ${rosterSize})</div>`;

        return `
        <div class="franchise-card-brutal team-border-${t.id} ${isLeader ? 'is-leader' : ''}">
          <div class="franchise-top">
    if ($('captain-team-name')) {
      const acronym = getTeamAcronym(view.id, view.team);
      $('captain-team-name').innerHTML = `
        <span style="display:inline-flex; align-items:center; gap:6px;">
          <span class="team-monogram-pill team-badge-${view.id || 1}" style="font-size:10px; padding:2px 6px;">${acronym}</span>
          ${view.team || 'MY FRANCHISE'}
        </span>
      `;
    }
    if ($('captain-user-name')) $('captain-user-name').textContent = view.captain || '—';
    if ($('captain-connection')) $('captain-connection').textContent = view.captain
      ? `SIGNED IN: ${view.team} • 👑 CAPTAIN: ${view.captain}`
      : (view.team ? `SIGNED IN: ${view.team}` : 'ONLINE');
  if ($('captain-purse')) $('captain-purse').textContent = money(view.purse);
  if ($('captain-max-bid')) $('captain-max-bid').textContent = money(view.max_bid);
  if ($('captain-roster-count')) $('captain-roster-count').textContent = `${view.roster} / ${view.roster_size || 4} DRAFTED`;

  const current = state.snapshot?.candidate;
  if (current) {
    if ($('captain-candidate')) $('captain-candidate').textContent = current.name;
    if ($('captain-tier')) $('captain-tier').textContent = `T${current.tier}`;
    if ($('captain-aptitude')) $('captain-aptitude').textContent = current.profile?.aptitude !== undefined ? current.profile.aptitude : '—';
    if ($('captain-gd')) $('captain-gd').textContent = current.profile?.gd !== undefined ? current.profile.gd : '—';
    if ($('captain-rating')) $('captain-rating').textContent = current.rating ? Number(current.rating).toLocaleString() : '—';
    if ($('captain-base')) $('captain-base').textContent = money(current.base_price);

    if ($('captain-tags')) {
      $('captain-tags').innerHTML = current.profile?.role
        ? `<span class="category-badge" style="background:#FFF;">🏏 ${current.profile.role}</span>`
        : '';
    }
  } else {
    if ($('captain-candidate')) $('captain-candidate').textContent = 'WAITING FOR AUCTION';
    if ($('captain-tier')) $('captain-tier').textContent = 'T—';
    if ($('captain-aptitude')) $('captain-aptitude').textContent = '—';
    if ($('captain-gd')) $('captain-gd').textContent = '—';
    if ($('captain-rating')) $('captain-rating').textContent = '—';
    if ($('captain-base')) $('captain-base').textContent = '—';
    if ($('captain-tags')) $('captain-tags').innerHTML = '';
  }

  if ($('captain-phase')) {
    $('captain-phase').textContent = state.snapshot?.paused ? 'PAUSED' : (state.snapshot?.phase || 'AUCTION');
  }
  if ($('captain-round')) {
    $('captain-round').textContent = `ROUND ${String(state.snapshot?.round || 1).padStart(2, '0')}`;
  }

  const minNextPrice = view.next_price || (state.snapshot?.phase === 'LIVE' ? (state.snapshot.next_price || current?.base_price) : null);
  if ($('captain-next-bid')) $('captain-next-bid').textContent = minNextPrice ? money(minNextPrice) : '—';

  // Render bid options grid
  const optionsNode = $('captain-bid-options');
  if (optionsNode) {
    const options = view.bid_options || [];
    if (options.length > 0) {
      optionsNode.innerHTML = options.map((amt, i) => {
        const isMin = i === 0;
        const label = isMin ? `BASE BID` : `+${Number(amt - options[0]).toLocaleString('en-IN')}`;
        return `
          <button class="btn-bid-option mechanical-btn ${isMin ? 'btn-bid-option-min' : ''}" data-bid-amount="${amt}">
            <span class="bid-option-label">${label}</span>
            <strong class="bid-option-amount tabular-nums">${money(amt)}</strong>
          </button>
        `;
      }).join('');

      // Attach click handlers
      optionsNode.querySelectorAll('.btn-bid-option').forEach((btn) => {
        btn.addEventListener('click', () => placeBid(Number(btn.dataset.bidAmount)));
      });
    } else {
      // Show reason or a friendly message
      const msg = view.can_bid === false && view.reason
        ? `⚠️ ${view.reason}`
        : view.full
        ? '✅ Your squad is complete!'
        : state.snapshot?.phase === 'PREVIEW'
        ? '⏳ Preview phase — bidding opens soon...'
        : state.snapshot?.phase === 'LIVE' && view.status === 'LEADING'
        ? '👑 You are leading! Wait for another team to bid.'
        : 'No bids available right now.';
      optionsNode.innerHTML = `<div class="bid-option-placeholder">${msg}</div>`;
    }
  }

  const verdictBanner = $('captain-verdict-banner');
  if (verdictBanner) {
    verdictBanner.className = 'verdict-banner-brutal';

    if (view.status === 'LEADING') {
      verdictBanner.classList.add('leading');
      if ($('captain-verdict-text')) $('captain-verdict-text').textContent = '👑 YOU ARE CURRENTLY LEADING THE BID!';
    } else if (view.status === 'OUTBID') {
      verdictBanner.classList.add('outbid');
      if ($('captain-verdict-text')) $('captain-verdict-text').textContent = `🔥 YOU ARE OUTBID! SELECT A BID BELOW TO COUNTER!`;
    } else if (view.full) {
      if ($('captain-verdict-text')) $('captain-verdict-text').textContent = `✅ YOUR ${view.roster_size || 4}-PLAYER SQUAD IS COMPLETE!`;
    } else if (view.can_bid) {
      if ($('captain-verdict-text')) $('captain-verdict-text').textContent = `⚡ BIDDING OPEN! SELECT AN AMOUNT BELOW TO BID.`;
    } else if (view.reason) {
      if ($('captain-verdict-text')) $('captain-verdict-text').textContent = `⚠️ ${view.reason}`;
    } else if (state.snapshot?.phase === 'PREVIEW') {
      if ($('captain-verdict-text')) $('captain-verdict-text').textContent = '⏳ Player preview phase. Bidding starts in a moment...';
    } else if (state.snapshot?.phase === 'SETUP' || state.snapshot?.phase === 'IDLE') {
      if ($('captain-verdict-text')) $('captain-verdict-text').textContent = '⏳ Waiting for auctioneer to bring out the next player...';
    } else {
      if ($('captain-verdict-text')) $('captain-verdict-text').textContent = '⚠️ Bidding closed for current prospect.';
    }
  }

  const rosterNode = $('captain-roster');
  if (rosterNode) {
    const captainEntry = view.captain
      ? `<div class="roster-row-brutal" style="background:#FEF3C7; border:2px solid var(--stadium-amberDark); margin-bottom:8px; padding:10px 12px; border-radius:4px;">
          <div>
            <div style="display:flex; align-items:center; gap:6px;">
              <span style="font-size:14px;">👑</span>
              <span style="font-weight:900; color:var(--stadium-ink); font-size:13px;">${view.captain}</span>
              <span class="category-badge" style="background:var(--stadium-amber); color:var(--stadium-ink); font-size:9px; padding:1px 6px;">CAPTAIN</span>
            </div>
            <small style="color:#64748B; font-family:var(--font-mono); font-size:10px; margin-left:22px;">Team Leader (Franchise Captain)</small>
          </div>
          <strong style="color:var(--stadium-ink); font-size:11px; font-family:var(--font-mono);">LEADER</strong>
        </div>`
      : '';

    const playerRows = view.squad?.length
      ? view.squad
          .map(
            (p, idx) => `
          <div class="roster-row-brutal">
            <div>
              <span style="font-weight:700;">#${idx + 1} ${p.name}</span>
              <small style="color:#64748B; margin-left:4px;">(${p.role || 'Player'})</small>
            </div>
            <strong style="color:var(--stadium-ink); font-weight:800;">${money(p.price)}</strong>
          </div>
        `
          )
          .join('')
      : '';

    const maxSlots = view.roster_size || 4;
    const boughtCount = view.squad?.length || 0;
    const emptySlots = Math.max(0, maxSlots - boughtCount);
    let openSlotRows = '';
    if (emptySlots > 0) {
      openSlotRows = `<div style="font-family:var(--font-mono); font-size:10px; color:#64748B; padding:8px 4px; text-align:center; border:1px dashed #CBD5E1; border-radius:4px; margin-top:6px; background:#F8FAFC;">
        ${emptySlots} player slot${emptySlots > 1 ? 's' : ''} available to buy (${boughtCount} / ${maxSlots} bought)
      </div>`;
    }

    rosterNode.innerHTML = (captainEntry || playerRows)
      ? (captainEntry + playerRows + openSlotRows)
      : '<div style="font-family:var(--font-mono); font-size:11px; color:#64748B; padding:12px 0;">No players signed yet.</div>';
  }
}

async function refreshCaptain() {
  if (!state.teamToken) return;
  try {
    const view = await api('/api/captain/view', {
      headers: { 'X-Team-Token': state.teamToken },
    });
    renderCaptainView(view);
    if ($('captain-login-card')) $('captain-login-card').hidden = true;
    if ($('captain-console')) $('captain-console').hidden = false;
  } catch (error) {
    setMessage('captain-login-message', error.message);
    state.teamToken = '';
    localStorage.removeItem('iet_team_token');
    if ($('captain-login-card')) $('captain-login-card').hidden = false;
    if ($('captain-console')) $('captain-console').hidden = true;
  }
}

function renderAdmin(snapshot) {
  if (!snapshot) return;
  if ($('admin-phase')) $('admin-phase').textContent = snapshot.phase;
  if ($('admin-clock')) $('admin-clock').textContent = timeStr(snapshot.seconds_left);
  if ($('admin-round')) $('admin-round').textContent = String(snapshot.round || 1).padStart(2, '0');
  if ($('admin-mode')) $('admin-mode').textContent = snapshot.manual_mode ? 'MANUAL' : 'AUTO';

  if (snapshot.stats && $('admin-stats-sold')) {
    $('admin-stats-sold').textContent = `${snapshot.stats.sold_count || 0} / ${snapshot.stats.total_candidates || 36}`;
  }

  const cand = snapshot.candidate;
  if ($('admin-current-id')) $('admin-current-id').textContent = cand ? `#${cand.id}` : '#—';
  if ($('admin-candidate')) $('admin-candidate').textContent = cand ? `${cand.name} [T${cand.tier}]` : 'WAITING FOR AUCTION';
  if ($('admin-bid')) $('admin-bid').textContent = money(snapshot.current_bid);
  if ($('admin-leader')) $('admin-leader').textContent = snapshot.leader || '—';

  const currentSize = snapshot.roster_size || 4;
  if ($('admin-roster-current-badge')) {
    $('admin-roster-current-badge').textContent = `${currentSize} PLAYERS / TEAM`;
  }

  [3, 4, 5].forEach((sz) => {
    const btn = $(`roster-btn-${sz}`);
    if (btn) {
      if (sz === currentSize) {
        btn.className = 'btn-brutal btn-amber mechanical-btn active';
        btn.style.boxShadow = '0 0 0 2px var(--stadium-ink)';
        btn.style.fontWeight = '800';
      } else {
        btn.className = 'btn-brutal mechanical-btn';
        btn.style.boxShadow = 'none';
        btn.style.fontWeight = '600';
      }
      btn.disabled = snapshot.phase !== 'SETUP';
      btn.style.opacity = snapshot.phase !== 'SETUP' ? '0.6' : '1';
    }
  });

  const rosterHint = $('admin-roster-status-hint');
  if (rosterHint) {
    if (snapshot.phase !== 'SETUP') {
      rosterHint.textContent = `🔒 Locked at ${currentSize} players per team (Auction is ${snapshot.phase}). To change, reset auction.`;
    } else {
      rosterHint.textContent = `⚡ Currently set to: ${currentSize} players per team. Select 3, 4, or 5 and click Start Auction!`;
    }
  }
}

async function loadAdminCandidates() {
  if (!state.adminPin) return;
  try {
    const list = await api('/api/admin/candidates', {
      headers: { 'X-Admin-Pin': state.adminPin },
    });
    state.adminCandidates = list;

    const select = $('admin-jump-select');
    if (select) {
      select.innerHTML =
        '<option value="">Choose candidate to jump...</option>' +
        list
          .map(
            (c) => `
        <option value="${c.id}">#${c.id} - ${c.name} [T${c.tier} - ${c.status}]</option>
      `
          )
          .join('');
    }
  } catch (err) {
    console.warn('Could not load candidate list:', err);
  }
}

async function loadSetup() {
  try {
    const report = await api('/api/setup/report');
    if ($('setup-status')) {
      $('setup-status').textContent = report.ok ? 'READY' : 'CHECK';
      $('setup-status').style.background = report.ok ? 'var(--stadium-pitchGreen)' : 'var(--stadium-ctaRed)';
      $('setup-status').style.color = '#FFFFFF';
    }

    if ($('setup-health')) {
      $('setup-health').innerHTML = [
        ['TEAMS LOADED', report.teams],
        ['CANDIDATES LOADED', report.candidates],
        ['ROSTER REQUIREMENT', `${report.needed} slots`],
        ['PURSE CHECK', report.purse_ok ? 'PASS' : 'FAIL'],
      ]
        .map(
          ([k, v]) => `
        <div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #E2E8F0;">
          <span>${k}:</span>
          <strong style="color:${v === 'FAIL' ? 'var(--stadium-ctaRed)' : 'var(--stadium-ink)'};">${v}</strong>
        </div>
      `
        )
        .join('');
    }
  } catch (err) {
    if ($('setup-health')) $('setup-health').textContent = err.message;
  }
}

async function adminAction(action, button) {
  const routes = {
    start: '/api/admin/start',
    next: '/api/admin/next',
    pause: '/api/admin/pause',
    resume: '/api/admin/resume',
    extend: '/api/admin/extend',
    freeze: '/api/admin/freeze',
    undo: '/api/admin/undo-last-bid',
    confirm: '/api/admin/confirm-sale',
    unsold: '/api/admin/mark-unsold',
  };

  const secondsVal = button?.dataset?.seconds ? Number(button.dataset.seconds) : 10;
  const bodies = {
    extend: { seconds: secondsVal },
    freeze: { on: !state.snapshot?.frozen },
  };

  try {
    const result = await api(routes[action], {
      method: 'POST',
      headers: { 'X-Admin-Pin': state.adminPin },
      body: bodies[action] ? JSON.stringify(bodies[action]) : undefined,
    });
    setMessage('admin-action-message', result.message || `Action ${action.toUpperCase()} complete.`, true);
    await refreshSnapshot();
  } catch (error) {
    setMessage('admin-action-message', error.message);
  }
}

function connectStageSocket() {
  try {
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${protocol}://${location.host}/ws/stage`);

    socket.onopen = () => {
      if ($('connection-label')) $('connection-label').textContent = 'TELEMETRY LINKED';
      if ($('connection-dot')) $('connection-dot').classList.remove('offline');
    };

    socket.onclose = () => {
      if ($('connection-label')) $('connection-label').textContent = 'RECONNECTING...';
      if ($('connection-dot')) $('connection-dot').classList.add('offline');
      setTimeout(connectStageSocket, 2000);
    };

    socket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.state) {
        renderSnapshot(message.state);
        if (state.teamToken) {
          refreshCaptain();
        }
      }
    };

    state.stageSocket = socket;
  } catch (err) {
    console.error('Socket error:', err);
  }
}

async function refreshSnapshot() {
  try {
    const snap = await api('/api/stage/state');
    renderSnapshot(snap);
  } catch (error) {
    if ($('connection-label')) $('connection-label').textContent = 'OFFLINE';
    if ($('connection-dot')) $('connection-dot').classList.add('offline');
  }
}


async function placeBid(price) {
  if (!price) {
    setMessage('captain-bid-message', 'Invalid bid amount.');
    return;
  }
  // Disable all bid option buttons during API call
  document.querySelectorAll('.btn-bid-option').forEach((b) => (b.disabled = true));
  try {
    const result = await api('/api/captain/bid', {
      method: 'POST',
      headers: { 'X-Team-Token': state.teamToken },
      body: JSON.stringify({ price }),
    });
    setMessage('captain-bid-message', result.reason || 'Bid placed!', result.ok);
    await refreshCaptain();
  } catch (error) {
    setMessage('captain-bid-message', error.message);
    // Re-render to restore buttons
    if (state.captainView) renderCaptainView(state.captainView);
  }
}

function bindEvents() {

  const fsBtn = $('fullscreen-btn');
  if (fsBtn) {
    fsBtn.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
      } else {
        document.exitFullscreen().catch(() => {});
      }
    });
  }

  const captainForm = $('captain-login-form');
  if (captainForm) {
    captainForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const form = new FormData(e.currentTarget);
      try {
        const result = await api('/api/captain/login', {
          method: 'POST',
          body: JSON.stringify({
            team_id: Number(form.get('team_id')),
            login_code: form.get('login_code'),
          }),
        });
        state.teamToken = result.token;
        localStorage.setItem('iet_team_token', state.teamToken);
        setMessage('captain-login-message', 'Authentication successful. Welcome Captain!', true);
        refreshCaptain();
      } catch (error) {
        setMessage('captain-login-message', error.message);
      }
    });
  }

  // Note: bid option buttons are rendered dynamically in renderCaptainView()
  // and each gets a click handler calling placeBid(). No static bind needed.

  const captainLogout = $('captain-logout');
  if (captainLogout) {
    captainLogout.addEventListener('click', () => {
      state.teamToken = '';
      localStorage.removeItem('iet_team_token');
      if ($('captain-login-card')) $('captain-login-card').hidden = false;
      if ($('captain-console')) $('captain-console').hidden = true;
      if ($('captain-connection')) $('captain-connection').textContent = 'NOT SIGNED IN';
      setMessage('captain-bid-message', '');
    });
  }

  const adminForm = $('admin-login-form');
  if (adminForm) {
    adminForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const pin = new FormData(e.currentTarget).get('pin');
      try {
        await api('/api/admin/auth/check', {
          headers: { 'X-Admin-Pin': pin },
        });
        state.adminPin = pin;
        sessionStorage.setItem('iet_admin_pin', pin);
        if ($('admin-login-card')) $('admin-login-card').hidden = true;
        if ($('admin-console')) $('admin-console').hidden = false;
        if ($('admin-connection')) $('admin-connection').textContent = 'CONTROL ROOM UNLOCKED';
        setMessage('admin-login-message', '');
        refreshSnapshot();
        loadSetup();
        loadAdminCandidates();
      } catch (error) {
        setMessage('admin-login-message', error.message);
      }
    });
  }

  const quickPin = $('admin-quick-pin');
  if (quickPin) {
    quickPin.addEventListener('click', () => {
      if ($('admin-pin-input')) $('admin-pin-input').value = '1234@';
    });
  }

  document.querySelectorAll('[data-admin-action]').forEach((btn) => {
    btn.addEventListener('click', () => adminAction(btn.dataset.adminAction, btn));
  });

  document.querySelectorAll('[data-roster-size]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const size = Number(btn.dataset.rosterSize);
      try {
        const res = await api('/api/admin/set-roster-size', {
          method: 'POST',
          headers: { 'X-Admin-Pin': state.adminPin },
          body: JSON.stringify({ size }),
        });
        setMessage('admin-action-message', res.message || `Squad size updated to ${size} players per team!`, true);
        await refreshSnapshot();
        loadSetup();
      } catch (err) {
        setMessage('admin-action-message', err.message);
      }
    });
  });

  const toggleManualBtn = $('btn-toggle-manual');
  if (toggleManualBtn) {
    toggleManualBtn.addEventListener('click', async () => {
      const currentManual = state.snapshot?.manual_mode || false;
      try {
        await api('/api/admin/set-manual-mode', {
          method: 'POST',
          headers: { 'X-Admin-Pin': state.adminPin },
          body: JSON.stringify({ on: !currentManual }),
        });
        setMessage('admin-action-message', `Switched mode to ${!currentManual ? 'MANUAL' : 'AUTO'}.`, true);
        refreshSnapshot();
      } catch (err) {
        setMessage('admin-action-message', err.message);
      }
    });
  }

  const jumpBtn = $('btn-admin-jump');
  if (jumpBtn) {
    jumpBtn.addEventListener('click', async () => {
      const cid = $('admin-jump-select')?.value;
      if (!cid) return setMessage('admin-action-message', 'Please select a candidate to jump to.');
      try {
        await api('/api/admin/next', {
          method: 'POST',
          headers: { 'X-Admin-Pin': state.adminPin },
          body: JSON.stringify({ candidate_id: Number(cid) }),
        });
        setMessage('admin-action-message', `Loaded candidate #${cid} to the pitch.`, true);
        refreshSnapshot();
        loadAdminCandidates();
      } catch (err) {
        setMessage('admin-action-message', err.message);
      }
    });
  }

  const proxyBidBtn = $('btn-admin-proxy-bid');
  if (proxyBidBtn) {
    proxyBidBtn.addEventListener('click', async () => {
      const teamId = Number($('admin-proxy-team')?.value);
      if (!teamId) {
        setMessage('admin-action-message', 'Please select a franchise team.');
        return;
      }
      const priceVal = $('admin-proxy-price')?.value;
      const price = priceVal ? Number(priceVal) : undefined;

      try {
        await api('/api/admin/substitute-bid', {
          method: 'POST',
          headers: { 'X-Admin-Pin': state.adminPin },
          body: JSON.stringify({ team_id: teamId, price }),
        });
        setMessage('admin-action-message', `Proxy bid placed for Team #${teamId}.`, true);
        if ($('admin-proxy-price')) $('admin-proxy-price').value = '';
        refreshSnapshot();
      } catch (err) {
        setMessage('admin-action-message', err.message);
      }
    });
  }

  const resetBtn = $('btn-admin-reset');
  if (resetBtn) {
    resetBtn.addEventListener('click', async () => {
      if (!confirm('Are you sure you want to RESET the entire auction? All current sales and bids will be wiped and freshly loaded from CSV!')) {
        return;
      }

      try {
        const res = await api('/api/admin/reset', {
          method: 'POST',
          headers: { 'X-Admin-Pin': state.adminPin },
        });
        setMessage('admin-action-message', res.message || 'Auction reset successfully!', true);
        refreshSnapshot();
        loadSetup();
        loadAdminCandidates();
      } catch (err) {
        setMessage('admin-action-message', err.message);
      }
    });
  }
}

function route() {
  const hash = location.hash.replace('#', '') || 'stage';

  document.querySelectorAll('.view').forEach((panel) => {
    panel.classList.toggle('active', panel.dataset.viewPanel === hash);
  });

  document.querySelectorAll('.role-link').forEach((link) => {
    link.classList.toggle('active', link.dataset.view === hash);
  });

  if (hash === 'captain') {
    if (state.teamToken) refreshCaptain();
  }

  if (hash === 'admin' && state.adminPin) {
    if ($('admin-login-card')) $('admin-login-card').hidden = true;
    if ($('admin-console')) $('admin-console').hidden = false;
    loadSetup();
    loadAdminCandidates();
  }
}

bindEvents();
window.addEventListener('hashchange', route);
route();
refreshSnapshot();
connectStageSocket();

setInterval(refreshSnapshot, 1000);
setInterval(() => {
  if (state.teamToken) refreshCaptain();
}, 1000);
