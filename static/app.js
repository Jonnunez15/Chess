let DATA = null;
let GAME_FILTER = 'all';

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

  return String(
    s ?? ''
  ).replace(
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

  const p = s.split('-');

  return (
    `${p[1]}/${p[2]}/${p[0]}`
  );
}


function formatMonth(s) {

  if (!s) return '—';

  const [y, m] =
    s.split('-');

  const names = [
    'Jan', 'Feb', 'Mar',
    'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep',
    'Oct', 'Nov', 'Dec'
  ];

  return (
    `${names[Number(m) - 1]} ${y}`
  );
}


function signed(n) {

  if (n > 0) {
    return `+${n}`;
  }

  return String(n);
}


async function load() {

  const u =
    $('#username')
    .value
    .trim();

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

    const r = await fetch(
      url,
      {
        method: 'GET',
        cache: 'no-store',
        headers: {
          Accept:
            'application/json'
        }
      }
    );

    const d =
      await r.json();

    if (!r.ok) {

      throw new Error(
        d.error ||
        `Unable to load games. HTTP ${r.status}`
      );
    }

    DATA = d;

    const t =
      d.totals;

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
                ${o.games.toLocaleString()}
                games · Avg
                ${o.avg_opp_rating ?? '—'}
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
        o => `
          <option
            value="${esc(o.opponent)}">

            ${esc(o.opponent)}

          </option>
        `
      )
      .join('');


    renderH2H();

    renderExtraAnalytics();

    $('#content')
      .classList
      .remove('hidden');

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

    $('#loadBtn').disabled =
      false;

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
      document.createElement(
        'div'
      );

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
        PEAKS
      </div>

      <h2>
        Career-high ratings
      </h2>

      <div
        id="peakRatings"
        class="analytics-grid">
      </div>

    </section>


    <section class="analytics-section">

      <div class="section-label">
        COLOR
      </div>

      <h2>
        White vs Black
      </h2>

      <div
        id="colorStats"
        class="analytics-grid">
      </div>

    </section>


    <section class="analytics-section">

      <div class="section-label">
        STREAKS
      </div>

      <h2>
        Career streaks
      </h2>

      <div
        id="streakStats"
        class="analytics-grid">
      </div>

    </section>


    <section class="analytics-section">

      <div class="section-label">
        FORM
      </div>

      <h2>
        Recent form
      </h2>

      <div
        id="recentForm"
        class="analytics-grid">
      </div>

    </section>


    <section class="analytics-section">

      <div class="section-label">
        MATCHUPS
      </div>

      <h2>
        By rating difference
      </h2>

      <div
        id="ratingDifference"
        class="analytics-stack">
      </div>

    </section>


    <section class="analytics-section">

      <div class="section-label">
        SCHEDULE
      </div>

      <h2>
        Day-of-week performance
      </h2>

      <div
        id="weekdayStats"
        class="analytics-stack">
      </div>

    </section>


    <section class="analytics-section">

      <div class="section-label">
        CLOCK
      </div>

      <h2>
        Time-of-day performance
      </h2>

      <div
        id="timeOfDay"
        class="analytics-grid">
      </div>

      <div class="analytics-note">
        Times shown in Eastern Time.
      </div>

    </section>


    <section class="analytics-section">

      <div class="section-label">
        MONTHS
      </div>

      <h2>
        Best & worst months
      </h2>

      <div
        id="monthlyStats"
        class="monthly-columns">
      </div>

    </section>


    <section class="analytics-section">

      <div class="section-label">
        ACTIVITY
      </div>

      <h2>
        Career activity
      </h2>

      <div
        id="activitySummary"
        class="analytics-grid single-feature">
      </div>

      <div
        id="activityHeatmap"
        class="heatmap-shell">
      </div>

    </section>


    <section class="analytics-section">

      <div class="section-label">
        MOMENTUM
      </div>

      <h2>
        30-day rating swings
      </h2>

      <div
        id="ratingMoves"
        class="analytics-grid">
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
  renderRatingChart('blitz');
  renderPeakRatings();
  renderColorStats();
  renderStreaks();
  renderRecentForm();
  renderRatingDifference();
  renderWeekdays();
  renderTimeOfDay();
  renderMonths();
  renderActivity();
  renderRatingMoves();
  renderRivals();
  renderUpsets();


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

  $('#timeControlAnalytics')
    .innerHTML =
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


function renderPeakRatings() {

  const p =
    DATA.peak_ratings;

  const labels = [
    ['blitz', 'Blitz'],
    ['rapid', 'Rapid'],
    ['bullet', 'Bullet']
  ];

  $('#peakRatings').innerHTML =
    labels
    .map(
      ([key, label]) => {

        const x = p[key];

        if (!x) return '';

        return `
          <div class="analytics-card">

            <div class="analytics-card-title">
              ${label}
            </div>

            <b>
              ${x.rating.toLocaleString()}
            </b>

            <span>
              peak rating
            </span>

            <div class="analytics-detail">
              ${formatDate(x.date)}
            </div>

          </div>
        `;
      }
    )
    .join('');
}


function renderColorStats() {

  const c =
    DATA.color_stats;

  $('#colorStats').innerHTML =
    [
      ['♙ White', c.white],
      ['♟ Black', c.black]
    ]
    .map(
      ([label, x]) => `

        <div class="analytics-card">

          <div class="analytics-card-title">
            ${label}
          </div>

          <b>
            ${x.score_pct}%
          </b>

          <span>
            score
          </span>

          <div class="analytics-detail">
            ${x.games.toLocaleString()} games
          </div>

          <div class="analytics-detail">
            ${x.record}
          </div>

        </div>
      `
    )
    .join('');
}


function renderStreaks() {

  const s =
    DATA.streaks;

  const items = [
    [
      '🔥 Win streak',
      s.wins
    ],
    [
      '🧊 Losing streak',
      s.losses
    ],
    [
      '🛡️ Unbeaten streak',
      s.unbeaten
    ]
  ];

  $('#streakStats').innerHTML =
    items
    .map(
      ([title, x]) => `

        <div class="analytics-card">

          <div class="analytics-card-title">
            ${title}
          </div>

          <b>
            ${x.games}
          </b>

          <span>
            games
          </span>

          <div class="analytics-detail">
            ${formatDate(x.start_date)}
            –
            ${formatDate(x.end_date)}
          </div>

        </div>
      `
    )
    .join('');
}


function renderRecentForm() {

  const f =
    DATA.recent_form;

  $('#recentForm').innerHTML =
    ['10', '25', '50', '100']
    .map(
      n => {

        const x = f[n];

        const cls =
          x.vs_career > 0
            ? 'positive'
            : (
              x.vs_career < 0
                ? 'negative'
                : ''
            );

        return `
          <div class="analytics-card">

            <div class="analytics-card-title">
              Last ${n}
            </div>

            <b>
              ${x.score_pct}%
            </b>

            <span>
              score
            </span>

            <div class="analytics-detail">
              ${x.record}
            </div>

            <div class="analytics-detail ${cls}">
              ${signed(x.vs_career)}
              pts vs career
            </div>

          </div>
        `;
      }
    )
    .join('');
}


function horizontalRow(
  label,
  games,
  score,
  record
) {

  return `
    <div class="stat-row">

      <div>

        <div class="stat-row-name">
          ${esc(label)}
        </div>

        <div class="sub">
          ${games.toLocaleString()} games
          ·
          ${record}
        </div>

      </div>

      <div class="stat-row-value">
        ${score}%
      </div>

    </div>
  `;
}


function renderRatingDifference() {

  $('#ratingDifference')
    .innerHTML =
    DATA.rating_difference
    .map(
      x =>
        horizontalRow(
          x.bucket,
          x.games,
          x.score_pct,
          x.record
        )
    )
    .join('');
}


function renderWeekdays() {

  $('#weekdayStats')
    .innerHTML =
    DATA.weekday_stats
    .map(
      x =>
        horizontalRow(
          x.day,
          x.games,
          x.score_pct,
          x.record
        )
    )
    .join('');
}


function renderTimeOfDay() {

  $('#timeOfDay')
    .innerHTML =
    DATA.time_of_day
    .map(
      x => `

        <div class="analytics-card">

          <div class="analytics-card-title">
            ${esc(x.period)}
          </div>

          <b>
            ${x.score_pct}%
          </b>

          <span>
            score
          </span>

          <div class="analytics-detail">
            ${x.games.toLocaleString()} games
          </div>

          <div class="analytics-detail">
            ${x.record}
          </div>

        </div>
      `
    )
    .join('');
}


function renderMonths() {

  const m =
    DATA.monthly_stats;

  const list = (
    title,
    data
  ) => `

    <div>

      <h3 class="mini-heading">
        ${title}
      </h3>

      ${data.map(
        (x, i) => `

          <div class="month-card">

            <div>
              <strong>
                ${i + 1}.
                ${formatMonth(x.month)}
              </strong>

              <div class="sub">
                ${x.games.toLocaleString()}
                games ·
                ${x.record}
              </div>
            </div>

            <b>
              ${x.score_pct}%
            </b>

          </div>
        `
      ).join('')}

    </div>
  `;

  $('#monthlyStats').innerHTML =
    list(
      'Best',
      m.best
    ) +
    list(
      'Worst',
      m.worst
    );
}


function renderActivity() {

  const a =
    DATA.activity;

  const busiest =
    a.busiest_day;

  $('#activitySummary').innerHTML =
    busiest
      ? `
        <div class="analytics-card">

          <div class="analytics-card-title">
            Busiest day
          </div>

          <b>
            ${busiest.games}
          </b>

          <span>
            games played
          </span>

          <div class="analytics-detail">
            ${formatDate(busiest.date)}
          </div>

        </div>
      `
      : '';


  if (!a.days.length) {

    $('#activityHeatmap')
      .innerHTML =
      '<div class="sub">No activity data.</div>';

    return;
  }


  const map =
    new Map(
      a.days.map(
        x => [
          x.date,
          x.games
        ]
      )
    );


  const first =
    new Date(
      a.days[0].date +
      'T12:00:00'
    );

  const last =
    new Date(
      a.days[
        a.days.length - 1
      ].date +
      'T12:00:00'
    );


  const start =
    new Date(first);

  const startDay =
    (start.getDay() + 6) % 7;

  start.setDate(
    start.getDate()
    - startDay
  );


  const end =
    new Date(last);

  const endDay =
    (end.getDay() + 6) % 7;

  end.setDate(
    end.getDate()
    + (6 - endDay)
  );


  const maxGames =
    Math.max(
      ...a.days.map(
        x => x.games
      )
    );


  let cells = '';

  let current =
    new Date(start);

  let week = 0;


  while (current <= end) {

    const day =
      (current.getDay() + 6) % 7;

    const date =
      current
      .toISOString()
      .slice(0, 10);

    const games =
      map.get(date) || 0;

    let level = 0;

    if (games > 0) {

      const ratio =
        games / maxGames;

      if (ratio > 0.75) level = 4;
      else if (ratio > 0.5) level = 3;
      else if (ratio > 0.25) level = 2;
      else level = 1;
    }


    cells += `
      <rect
        x="${week * 14}"
        y="${day * 14}"
        width="11"
        height="11"
        rx="2"
        class="heat-${level}">

        <title>
          ${date}: ${games} games
        </title>

      </rect>
    `;


    if (day === 6) {
      week++;
    }


    current.setDate(
      current.getDate() + 1
    );
  }


  const width =
    Math.max(
      1,
      (week + 1) * 14
    );


  $('#activityHeatmap')
    .innerHTML = `

      <div class="heatmap-scroll">

        <svg
          class="heatmap-svg"
          viewBox="0 0 ${width} 100"
          width="${width}"
          height="100">

          ${cells}

        </svg>

      </div>

      <div class="heatmap-legend">

        Less

        <span class="heat-box heat-1"></span>
        <span class="heat-box heat-2"></span>
        <span class="heat-box heat-3"></span>
        <span class="heat-box heat-4"></span>

        More

      </div>
    `;
}


function renderRatingMoves() {

  const x =
    DATA.rating_moves_30;

  const cards = [];


  if (x.biggest_gain) {

    cards.push(
      `
        <div class="analytics-card">

          <div class="analytics-card-title">
            📈 Biggest 30-day climb
          </div>

          <b class="positive">
            +${x.biggest_gain.change}
          </b>

          <span>
            ${esc(x.biggest_gain.time_class)}
          </span>

          <div class="analytics-detail">
            ${x.biggest_gain.start_rating}
            →
            ${x.biggest_gain.end_rating}
          </div>

          <div class="analytics-detail">
            ${formatDate(x.biggest_gain.start_date)}
            →
            ${formatDate(x.biggest_gain.end_date)}
          </div>

        </div>
      `
    );
  }


  if (x.biggest_drop) {

    cards.push(
      `
        <div class="analytics-card">

          <div class="analytics-card-title">
            📉 Biggest 30-day drop
          </div>

          <b class="negative">
            ${x.biggest_drop.change}
          </b>

          <span>
            ${esc(x.biggest_drop.time_class)}
          </span>

          <div class="analytics-detail">
            ${x.biggest_drop.start_rating}
            →
            ${x.biggest_drop.end_rating}
          </div>

          <div class="analytics-detail">
            ${formatDate(x.biggest_drop.start_date)}
            →
            ${formatDate(x.biggest_drop.end_date)}
          </div>

        </div>
      `
    );
  }


  $('#ratingMoves')
    .innerHTML =
    cards.join('');
}


function renderRivals() {

  const r =
    DATA.rivals;

  const cards = [
    {
      title:
        '😈 Nemesis',

      data:
        r.nemesis
    },
    {
      title:
        '🥊 Punching Bag',

      data:
        r.punching_bag
    },
    {
      title:
        '⚔️ Closest Rival',

      data:
        r.closest_rival
    }
  ];


  $('#rivalCards')
    .innerHTML =
    cards
    .map(
      item => {

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
              ${x.games.toLocaleString()}
              games
            </span>

            <div class="analytics-detail">
              ${x.record}
            </div>

            <div class="analytics-detail">
              ${x.score_pct}% score
            </div>

          </div>
        `;
      }
    )
    .join('');
}


function renderUpsets() {

  $('#upsetList')
    .innerHTML =
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
    Math.min(
      ...ratings
    );

  let max =
    Math.max(
      ...ratings
    );


  if (min === max) {

    min -= 50;
    max += 50;
  }


  min -= 25;
  max += 25;


  const points =
    data
    .map(
      (d, i) => {

        const x =
          pad +
          (
            i /
            (
              data.length - 1
            )
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
            )
            /
            (
              max - min
            )
          )
          *
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
