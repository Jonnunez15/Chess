let DATA = null;

const $ = s => document.querySelector(s);

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


function formatDate(s) {
  if (!s) return '—';

  const parts = s.split('-');

  return `${parts[1]}/${parts[2]}/${parts[0]}`;
}


async function load() {

  const u = $('#username').value.trim();

  if (!u) {
    status.textContent =
      'Please enter a Chess.com username.';
    return;
  }

  status.textContent =
    `Loading games for ${u}…`;

  $('#loadBtn').disabled = true;

  try {

    const url =
      window.location.origin +
      '/api/analytics?username=' +
      encodeURIComponent(u) +
      '&_=' +
      Date.now();

    const r = await fetch(url, {
      method: 'GET',
      cache: 'no-store',
      headers: {
        'Accept': 'application/json'
      }
    });

    const d = await r.json();

    if (!r.ok) {
      throw new Error(
        d.error ||
        `Unable to load games. HTTP ${r.status}`
      );
    }

    DATA = d;

    const t = d.totals;

    $('#metrics').innerHTML =
      metric(
        'Games',
        t.games.toLocaleString()
      ) +
      metric(
        'Wins',
        t.wins.toLocaleString()
      ) +
      metric(
        'Losses',
        t.losses.toLocaleString()
      ) +
      metric(
        'Draws',
        t.draws.toLocaleString()
      ) +
      metric(
        'Score',
        t.score_pct + '%'
      );


    $('#opponents').innerHTML =
      d.top_opponents
      .map(
        (o, i) => `
          <div class="opp">

            <div class="rank">
              ${i + 1}
            </div>

            <div>

              <div class="name">
                ${esc(o.opponent)}
              </div>

              <div class="sub">
                ${o.games.toLocaleString()} games
                · Avg ${o.avg_opp_rating ?? '—'}
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


    $('#oppSelect').innerHTML =
      d.opponents
      .map(
        o =>
          `<option value="${esc(o.opponent)}">
            ${esc(o.opponent)}
          </option>`
      )
      .join('');


    renderH2H();

    renderExtraAnalytics();

    $('#content').classList.remove(
      'hidden'
    );

    status.textContent =
      `Loaded ${t.games.toLocaleString()} games for ${d.username}`;

  }

  catch (e) {

    console.error(e);

    status.textContent =
      'Error: ' +
      (
        e.message ||
        'Unable to load Chess.com games.'
      );

  }

  finally {

    $('#loadBtn').disabled = false;

  }
}


function renderH2H() {

  if (!DATA) return;

  const name =
    $('#oppSelect').value;

  const o =
    DATA.opponents.find(
      x => x.opponent === name
    );

  const games =
    DATA.games.filter(
      g => g.opponent === name
    );

  if (!o) return;


  $('#h2hStats').innerHTML =
    metric(
      'Games',
      o.games.toLocaleString()
    ) +
    metric(
      'Record',
      o.record
    ) +
    metric(
      'As White',
      o.white_games.toLocaleString()
    ) +
    metric(
      'As Black',
      o.black_games.toLocaleString()
    );


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


    const x =
      grouped[g.time_class];

    x.g++;

    const result =
      g.result.toLowerCase();

    if (result === 'w') x.w++;

    if (result === 'l') x.l++;

    if (result === 'd') x.d++;

  }


  $('#timeControls').innerHTML =
    Object.entries(grouped)
    .map(
      ([k, v]) => `
        <div class="chip">
          ${esc(k)}
          ·
          ${v.w}-${v.l}-${v.d}
        </div>
      `
    )
    .join('');
}


function renderExtraAnalytics() {

  let area =
    document.querySelector(
      '#extraAnalytics'
    );

  if (!area) {

    area =
      document.createElement('div');

    area.id =
      'extraAnalytics';

    $('#content')
      .appendChild(area);

  }


  area.innerHTML = `

    <section class="analytics-section">

      <div class="section-label">
        PERFORMANCE
      </div>

      <h2>
        By time control
      </h2>

      <div
        id="timeControlAnalytics"
        class="analytics-grid">
      </div>

    </section>


    <section class="analytics-section">

      <div class="section-label">
        CAREER
      </div>

      <h2>
        Rating history
      </h2>

      <div class="chart-box">

        <div class="chart-tabs">

          <button
            class="chart-tab active"
            data-chart="blitz">
            Blitz
          </button>

          <button
            class="chart-tab"
            data-chart="rapid">
            Rapid
          </button>

          <button
            class="chart-tab"
            data-chart="bullet">
            Bullet
          </button>

        </div>

        <div id="ratingChart"></div>

      </div>

    </section>


    <section class="analytics-section">

      <div class="section-label">
        RIVALS
      </div>

      <h2>
        Friends & enemies
      </h2>

      <div
        id="rivalCards"
        class="analytics-grid">
      </div>

    </section>


    <section class="analytics-section">

      <div class="section-label">
        RECORD BOOK
      </div>

      <h2>
        Biggest upset wins
      </h2>

      <div id="upsetList"></div>

    </section>
  `;


  renderTimeControlAnalytics();

  renderRivals();

  renderUpsets();

  renderRatingChart(
    'blitz'
  );


  document
    .querySelectorAll(
      '.chart-tab'
    )
    .forEach(btn => {

      btn.addEventListener(
        'click',
        () => {

          document
            .querySelectorAll(
              '.chart-tab'
            )
            .forEach(
              x =>
                x.classList.remove(
                  'active'
                )
            );

          btn.classList.add(
            'active'
          );

          renderRatingChart(
            btn.dataset.chart
          );

        }
      );

    });

}


function renderTimeControlAnalytics() {

  const el =
    $('#timeControlAnalytics');


  el.innerHTML =
    DATA.time_controls
    .map(
      x => `

        <div class="analytics-card">

          <div class="analytics-card-title">
            ${esc(x.time_class)}
          </div>

          <b>
            ${x.games.toLocaleString()}
          </b>

          <span>
            games
          </span>

          <div class="analytics-detail">

            ${x.record}
            ·
            ${x.score_pct}% score

          </div>

          <div class="analytics-detail">

            Peak:
            ${x.peak_rating ?? '—'}

          </div>

        </div>

      `
    )
    .join('');

}


function renderRivals() {

  const r =
    DATA.rivals;

  const cards = [

    {
      title: '😈 Nemesis',
      data: r.nemesis
    },

    {
      title: '🥊 Punching Bag',
      data: r.punching_bag
    },

    {
      title: '⚔️ Closest Rival',
      data: r.closest_rival
    }

  ];


  $('#rivalCards').innerHTML =
    cards
    .map(item => {

      const x =
        item.data;

      if (!x) return '';

      return `

        <div class="analytics-card">

          <div class="analytics-card-title">
            ${item.title}
          </div>

          <b class="rival-name">
            ${esc(x.opponent)}
          </b>

          <span>
            ${x.games.toLocaleString()} games
          </span>

          <div class="analytics-detail">
            ${x.record}
          </div>

          <div class="analytics-detail">
            ${x.score_pct}% score
          </div>

        </div>

      `;

    })
    .join('');

}


function renderUpsets() {

  $('#upsetList').innerHTML =
    DATA.biggest_upsets
    .map(
      (g, i) => `

        <div class="opp">

          <div class="rank">
            ${i + 1}
          </div>

          <div>

            <div class="name">
              ${esc(g.opponent)}
            </div>

            <div class="sub">

              ${g.my_rating}
              vs
              ${g.opp_rating}

              ·
              ${esc(g.time_class)}

              ·
              ${formatDate(g.date)}

            </div>

          </div>

          <div class="record upset">

            +${g.rating_difference}

            <small>
              rating upset
            </small>

          </div>

        </div>

      `
    )
    .join('');

}


function renderRatingChart(
  timeClass
) {

  const data =
    DATA.rating_history[
      timeClass
    ] || [];


  const el =
    $('#ratingChart');


  if (data.length < 2) {

    el.innerHTML =
      '<div class="sub">Not enough rating history.</div>';

    return;

  }


  const width = 700;
  const height = 280;

  const pad = 35;


  const ratings =
    data.map(
      d => d.rating
    );


  let min =
    Math.min(...ratings);

  let max =
    Math.max(...ratings);


  if (min === max) {
    min -= 50;
    max += 50;
  }


  min -= 25;
  max += 25;


  const points =
    data.map(
      (d, i) => {

        const x =
          pad +
          (
            i /
            (data.length - 1)
          ) *
          (
            width -
            pad * 2
          );

        const y =
          height -
          pad -
          (
            (
              d.rating - min
            ) /
            (
              max - min
            )
          ) *
          (
            height -
            pad * 2
          );

        return `${x},${y}`;

      }
    )
    .join(' ');


  const first =
    data[0];

  const last =
    data[
      data.length - 1
    ];


  el.innerHTML = `

    <svg
      viewBox="0 0 ${width} ${height}"
      class="rating-svg">

      <line
        x1="${pad}"
        x2="${width - pad}"
        y1="${height - pad}"
        y2="${height - pad}"
        class="chart-axis"
      />

      <polyline
        points="${points}"
        class="rating-line"
      />

      <text
        x="${pad}"
        y="22"
        class="chart-text">

        ${Math.round(max)}

      </text>

      <text
        x="${pad}"
        y="${height - 8}"
        class="chart-text">

        ${formatDate(first.date)}

      </text>

      <text
        x="${width - pad}"
        y="${height - 8}"
        text-anchor="end"
        class="chart-text">

        ${formatDate(last.date)}

      </text>

    </svg>

  `;

}


$('#loadBtn')
  .addEventListener(
    'click',
    load
  );


$('#username')
  .addEventListener(
    'keydown',
    e => {

      if (e.key === 'Enter') {
        load();
      }

    }
  );


$('#oppSelect')
  .addEventListener(
    'change',
    renderH2H
  );


window.addEventListener(
  'load',
  load
);
