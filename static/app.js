let DATA = null;

const $ = (s) => document.querySelector(s);
const status = $('#status');

function metric(label, val) {
  return `
    <div class="metric">
      <b>${val}</b>
      <span>${label}</span>
    </div>
  `;
}

function esc(s) {
  return String(s ?? '').replace(
    /[&<>"]/g,
    c => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;'
    }[c])
  );
}

async function load() {
  const u = $('#username').value.trim();

  if (!u) {
    status.textContent = 'Please enter a Chess.com username.';
    return;
  }

  status.textContent = `Loading games for ${u}…`;
  $('#loadBtn').disabled = true;

  try {
    // Build a full URL instead of relying on a relative URL
    const url =
      window.location.origin +
      '/api/analytics?username=' +
      encodeURIComponent(u) +
      '&_=' +
      Date.now();

    console.log('Requesting:', url);

    const r = await fetch(url, {
      method: 'GET',
      cache: 'no-store',
      headers: {
        'Accept': 'application/json'
      }
    });

    let d;

    try {
      d = await r.json();
    } catch (jsonError) {
      throw new Error(
        'The server returned an invalid response. HTTP ' +
        r.status
      );
    }

    if (!r.ok) {
      throw new Error(
        d.error ||
        `Unable to load games. HTTP ${r.status}`
      );
    }

    DATA = d;

    const t = d.totals;

    $('#metrics').innerHTML =
      metric('Games', t.games.toLocaleString()) +
      metric('Wins', t.wins.toLocaleString()) +
      metric('Losses', t.losses.toLocaleString()) +
      metric('Draws', t.draws.toLocaleString()) +
      metric('Score', t.score_pct + '%');

    $('#opponents').innerHTML = d.top_opponents
      .map(
        (o, i) => `
          <div class="opp">
            <div class="rank">${i + 1}</div>

            <div>
              <div class="name">
                ${esc(o.opponent)}
              </div>

              <div class="sub">
                ${o.games.toLocaleString()} games ·
                Avg ${o.avg_opp_rating ?? '—'}
              </div>
            </div>

            <div class="record">
              ${o.record}
              <small>
                ${o.score_pct}% score
              </small>
            </div>
          </div>
        `
      )
      .join('');

    $('#oppSelect').innerHTML = d.opponents
      .map(
        o =>
          `<option value="${esc(o.opponent)}">${esc(o.opponent)}</option>`
      )
      .join('');

    renderH2H();

    $('#content').classList.remove('hidden');

    status.textContent =
      `Loaded ${t.games.toLocaleString()} games for ${d.username}`;

  } catch (e) {
    console.error(e);

    status.textContent =
      'Error: ' +
      (e.message || 'Unable to load Chess.com games.');

  } finally {
    $('#loadBtn').disabled = false;
  }
}

function renderH2H() {
  if (!DATA) return;

  const name = $('#oppSelect').value;

  const o = DATA.opponents.find(
    x => x.opponent === name
  );

  const games = DATA.games.filter(
    g => g.opponent === name
  );

  if (!o) return;

  $('#h2hStats').innerHTML =
    metric('Games', o.games.toLocaleString()) +
    metric('Record', o.record) +
    metric('As White', o.white_games.toLocaleString()) +
    metric('As Black', o.black_games.toLocaleString());

  const grouped = {};

  for (const g of games) {
    if (!grouped[g.time_class]) {
      grouped[g.time_class] = {
        g: 0,
        w: 0,
        l: 0,
        d: 0
      };
    }

    const x = grouped[g.time_class];

    x.g++;

    const result = g.result.toLowerCase();

    if (result === 'w') x.w++;
    if (result === 'l') x.l++;
    if (result === 'd') x.d++;
  }

  $('#timeControls').innerHTML =
    Object.entries(grouped)
      .map(
        ([k, v]) =>
          `<div class="chip">
            ${esc(k)} · ${v.w}-${v.l}-${v.d}
          </div>`
      )
      .join('');
}

$('#loadBtn').addEventListener(
  'click',
  load
);

$('#username').addEventListener(
  'keydown',
  e => {
    if (e.key === 'Enter') {
      load();
    }
  }
);

$('#oppSelect').addEventListener(
  'change',
  renderH2H
);

window.addEventListener(
  'load',
  load
);
