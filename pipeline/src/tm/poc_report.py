"""
PoC Report Generator — renders duel.html from harvested Polymarket data + TM predictions.

Generates a self-contained interactive HTML report comparing TruthMachine
forecasts against Polymarket crowd prices.

Works progressively:
  - Phase 0 (harvest only): event browser + outcome breakdown
  - Phase 1 (+ prices):     Polymarket calibration chart
  - Phase 2 (+ TM data):    TM vs PM Brier comparison, source leaderboard

Usage:
    python -m tm.poc_report
    python -m tm.poc_report --data-dir data/poc --out duel.html
"""

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Console

console = Console()


# ── Data loading ──────────────────────────────────────────────────────────────

def load_events(data_dir: Path) -> list[dict]:
    path = data_dir / "pm_harvest" / "events.jsonl"
    if not path.exists():
        return []
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def get_final_price(event: dict, days_before: int = 1) -> float | None:
    """Return PM probability N days before resolution, or None if unavailable."""
    prices = event.get("prices") or []
    if not prices:
        return None
    outcome_date = datetime.strptime(event["outcome_date"], "%Y-%m-%d").date()
    cutoff = outcome_date - timedelta(days=days_before)
    candidates = [p for p in prices if datetime.strptime(p["date"], "%Y-%m-%d").date() <= cutoff]
    if not candidates:
        candidates = prices  # fallback: use any available
    return candidates[-1]["probability"]


def compute_calibration(events: list[dict], days_before: int = 7, n_bins: int = 10) -> dict | None:
    """Bin PM final probabilities vs actual outcome rate."""
    bins = [[] for _ in range(n_bins)]
    for ev in events:
        p = get_final_price(ev, days_before)
        if p is None:
            continue
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx].append(1 if ev["outcome"] else 0)

    if sum(len(b) for b in bins) < 10:
        return None

    labels, predicted, actual, counts = [], [], [], []
    for i, b in enumerate(bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        labels.append(f"{int(lo*100)}–{int(hi*100)}%")
        predicted.append(round((lo + hi) / 2, 3))
        actual.append(round(sum(b) / len(b), 3) if b else 0)
        counts.append(len(b))

    return {"labels": labels, "predicted": predicted, "actual": actual, "counts": counts}


def category_breakdown(events: list[dict]) -> dict:
    cats: dict[str, dict] = defaultdict(lambda: {"yes": 0, "no": 0})
    for ev in events:
        cat = (ev.get("category") or "Politics").strip()[:30]
        if ev["outcome"]:
            cats[cat]["yes"] += 1
        else:
            cats[cat]["no"] += 1
    # Sort by total desc, top 10
    sorted_cats = sorted(cats.items(), key=lambda x: -(x[1]["yes"] + x[1]["no"]))[:10]
    return {
        "labels": [c for c, _ in sorted_cats],
        "yes": [v["yes"] for _, v in sorted_cats],
        "no": [v["no"] for _, v in sorted_cats],
    }


def outcome_by_year(events: list[dict]) -> dict:
    years: dict[str, dict] = defaultdict(lambda: {"yes": 0, "no": 0})
    for ev in events:
        y = ev["outcome_date"][:4]
        if ev["outcome"]:
            years[y]["yes"] += 1
        else:
            years[y]["no"] += 1
    sorted_years = sorted(years.items())
    return {
        "labels": [y for y, _ in sorted_years],
        "yes": [v["yes"] for _, v in sorted_years],
        "no": [v["no"] for _, v in sorted_years],
    }


def build_event_rows(events: list[dict]) -> list[dict]:
    """Compact event summaries for the browser table."""
    rows = []
    for ev in events:
        final_p = get_final_price(ev, days_before=1)
        rows.append({
            "q": ev["question"][:120],
            "out": ev["outcome"],
            "date": ev["outcome_date"],
            "cat": (ev.get("category") or "Politics")[:25],
            "pm_p": round(final_p, 3) if final_p is not None else None,
            "url": ev.get("pm_url", ""),
        })
    return rows


# ── HTML generation ───────────────────────────────────────────────────────────

def render(data_dir: Path, out_path: Path) -> None:
    console.print("[bold cyan]PoC Report[/bold cyan] — loading data...")

    events = load_events(data_dir)
    console.print(f"  {len(events)} events loaded")

    has_prices = sum(1 for e in events if e.get("prices"))
    console.print(f"  {has_prices} with price history")

    calib = compute_calibration(events, days_before=7) if has_prices >= 50 else None
    cat_data = category_breakdown(events)
    year_data = outcome_by_year(events)
    rows = build_event_rows(events)

    yes_count = sum(1 for e in events if e["outcome"])
    no_count = len(events) - yes_count
    prices_pct = round(has_prices / len(events) * 100) if events else 0

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    # Inline all chart data as JSON
    calib_json = json.dumps(calib) if calib else "null"
    cat_json = json.dumps(cat_data)
    year_json = json.dumps(year_data)
    rows_json = json.dumps(rows)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Duel: TruthMachine vs Polymarket</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3a;
    --text: #e2e8f0; --muted: #8892a4; --accent: #6366f1;
    --green: #10b981; --red: #ef4444; --yellow: #f59e0b;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, sans-serif; font-size: 14px; line-height: 1.6; }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  header {{ padding: 2rem 2rem 1rem; border-bottom: 1px solid var(--border); }}
  header h1 {{ font-size: 1.8rem; font-weight: 700; color: var(--text); }}
  header h1 span {{ color: var(--accent); }}
  .subtitle {{ color: var(--muted); margin-top: 0.25rem; font-size: 0.9rem; }}

  .hero {{ display: flex; gap: 1rem; padding: 1.5rem 2rem; flex-wrap: wrap; }}
  .stat-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem 1.5rem; min-width: 150px; }}
  .stat-card .val {{ font-size: 2rem; font-weight: 700; color: var(--accent); }}
  .stat-card .lbl {{ color: var(--muted); font-size: 0.8rem; margin-top: 0.2rem; }}

  .coverage-bar {{ margin: 0 2rem 1.5rem; }}
  .coverage-bar .bar {{ background: var(--border); border-radius: 4px; height: 8px; margin-top: 0.5rem; }}
  .coverage-bar .fill {{ background: var(--accent); height: 100%; border-radius: 4px; transition: width 0.5s; }}
  .coverage-bar .label {{ color: var(--muted); font-size: 0.85rem; }}

  .section {{ padding: 1.5rem 2rem; border-top: 1px solid var(--border); }}
  .section h2 {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; color: var(--text); }}
  .section .hint {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 1rem; }}

  .charts-row {{ display: flex; gap: 1.5rem; flex-wrap: wrap; }}
  .chart-box {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; flex: 1; min-width: 300px; max-width: 600px; }}
  .chart-box h3 {{ font-size: 0.9rem; font-weight: 600; margin-bottom: 0.75rem; color: var(--muted); }}
  .chart-box canvas {{ max-height: 260px; }}

  .placeholder {{ background: var(--surface); border: 1px dashed var(--border); border-radius: 8px;
    padding: 2rem; text-align: center; color: var(--muted); }}
  .placeholder .icon {{ font-size: 2rem; margin-bottom: 0.5rem; }}

  /* Table */
  .table-controls {{ display: flex; gap: 0.75rem; margin-bottom: 1rem; flex-wrap: wrap; }}
  .table-controls input, .table-controls select {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
    color: var(--text); padding: 0.4rem 0.75rem; font-size: 0.85rem; outline: none;
  }}
  .table-controls input {{ flex: 1; min-width: 200px; }}
  .table-controls input:focus, .table-controls select:focus {{ border-color: var(--accent); }}

  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ text-align: left; padding: 0.5rem 0.75rem; color: var(--muted); font-weight: 500;
    border-bottom: 1px solid var(--border); white-space: nowrap; cursor: pointer; user-select: none; }}
  th:hover {{ color: var(--text); }}
  td {{ padding: 0.45rem 0.75rem; border-bottom: 1px solid var(--border); vertical-align: top; }}
  tr:hover td {{ background: var(--surface); }}
  .out-yes {{ color: var(--green); font-weight: 600; }}
  .out-no  {{ color: var(--red); font-weight: 600; }}
  .prob-bar {{ display: inline-block; width: 40px; height: 6px; background: var(--border); border-radius: 3px; vertical-align: middle; margin-right: 4px; }}
  .prob-fill {{ height: 100%; border-radius: 3px; background: var(--accent); }}

  .pagination {{ display: flex; gap: 0.5rem; align-items: center; margin-top: 1rem; justify-content: center; color: var(--muted); font-size: 0.85rem; }}
  .pagination button {{ background: var(--surface); border: 1px solid var(--border); border-radius: 4px;
    color: var(--text); padding: 0.3rem 0.7rem; cursor: pointer; font-size: 0.82rem; }}
  .pagination button:hover {{ border-color: var(--accent); }}
  .pagination button:disabled {{ opacity: 0.4; cursor: default; }}

  footer {{ padding: 1rem 2rem; color: var(--muted); font-size: 0.8rem; border-top: 1px solid var(--border); }}
</style>
</head>
<body>

<header>
  <h1>⚔ <span>Duel</span>: TruthMachine vs Polymarket</h1>
  <div class="subtitle">Comparing AI-aggregated news forecasts against prediction market crowd prices &nbsp;·&nbsp; Generated {generated_at}</div>
</header>

<div class="hero">
  <div class="stat-card"><div class="val">{len(events):,}</div><div class="lbl">Resolved markets</div></div>
  <div class="stat-card"><div class="val">{yes_count:,}</div><div class="lbl">Resolved YES</div></div>
  <div class="stat-card"><div class="val">{no_count:,}</div><div class="lbl">Resolved NO</div></div>
  <div class="stat-card"><div class="val">{has_prices:,}</div><div class="lbl">With price history</div></div>
  <div class="stat-card" style="border-color:{'#6366f1' if calib else 'var(--border)'}">
    <div class="val" style="color:{'#10b981' if calib else 'var(--muted)'}">{'✓' if calib else '…'}</div>
    <div class="lbl">Calibration ready</div>
  </div>
</div>

<div class="coverage-bar">
  <div class="label">Price history coverage: {prices_pct}% ({has_prices:,} / {len(events):,} events)</div>
  <div class="bar"><div class="fill" style="width:{prices_pct}%"></div></div>
</div>

<div class="section">
  <h2>Polymarket Analysis</h2>
  <div class="charts-row">
    <div class="chart-box">
      <h3>Outcome Breakdown by Category</h3>
      <canvas id="catChart"></canvas>
    </div>
    <div class="chart-box">
      <h3>Events by Year</h3>
      <canvas id="yearChart"></canvas>
    </div>
    {'<div class="chart-box"><h3>Calibration: PM Probability vs Actual Outcome Rate (7d before resolution)</h3><canvas id="calibChart"></canvas></div>' if calib else '<div class="placeholder"><div class="icon">📈</div><div>Calibration chart — available once price history is loaded<br><small>(' + str(has_prices) + ' / ' + str(len(events)) + ' events have prices so far)</small></div></div>'}
  </div>
</div>

<div class="section">
  <h2>TruthMachine vs Polymarket</h2>
  <div class="placeholder">
    <div class="icon">🤖</div>
    <div>TM predictions not yet available<br>
    <small>Pipeline is ingesting articles and extracting predictions — check back soon</small></div>
  </div>
</div>

<div class="section">
  <h2>Event Browser</h2>
  <div class="hint">All {len(events):,} resolved markets — search, filter, and sort.</div>
  <div class="table-controls">
    <input type="text" id="search" placeholder="Search questions…" oninput="filterTable()">
    <select id="catFilter" onchange="filterTable()">
      <option value="">All categories</option>
    </select>
    <select id="outFilter" onchange="filterTable()">
      <option value="">All outcomes</option>
      <option value="yes">YES</option>
      <option value="no">NO</option>
    </select>
    <select id="yearFilter" onchange="filterTable()">
      <option value="">All years</option>
    </select>
  </div>
  <table id="evtTable">
    <thead><tr>
      <th onclick="sortTable('q')">Question ↕</th>
      <th onclick="sortTable('cat')">Category ↕</th>
      <th onclick="sortTable('date')">Date ↕</th>
      <th onclick="sortTable('out')">Outcome ↕</th>
      <th onclick="sortTable('pm_p')">PM Prob ↕</th>
    </tr></thead>
    <tbody id="evtBody"></tbody>
  </table>
  <div class="pagination">
    <button id="prevBtn" onclick="changePage(-1)" disabled>← Prev</button>
    <span id="pageInfo"></span>
    <button id="nextBtn" onclick="changePage(1)">Next →</button>
  </div>
</div>

<footer>
  Data sourced from <a href="https://polymarket.com" target="_blank">Polymarket</a> via Gamma API &nbsp;·&nbsp;
  TruthMachine pipeline by <a href="https://github.com/komapc/retro" target="_blank">komapc/retro</a>
</footer>

<script>
const EVENTS = {rows_json};
const CALIB  = {calib_json};
const CAT    = {cat_json};
const YEAR   = {year_json};

// ── Charts ────────────────────────────────────────────────────────────────────
const GRID   = 'rgba(255,255,255,0.06)';
const ACCENT = '#6366f1';
const GREEN  = '#10b981';
const RED    = '#ef4444';

Chart.defaults.color = '#8892a4';
Chart.defaults.borderColor = GRID;

new Chart(document.getElementById('catChart'), {{
  type: 'bar',
  data: {{
    labels: CAT.labels,
    datasets: [
      {{ label: 'YES', data: CAT.yes, backgroundColor: GREEN + 'cc' }},
      {{ label: 'NO',  data: CAT.no,  backgroundColor: RED   + 'cc' }},
    ]
  }},
  options: {{ responsive: true, plugins: {{ legend: {{ position: 'top' }} }},
    scales: {{ x: {{ stacked: true, grid: {{ color: GRID }} }}, y: {{ stacked: true, grid: {{ color: GRID }} }} }} }}
}});

new Chart(document.getElementById('yearChart'), {{
  type: 'bar',
  data: {{
    labels: YEAR.labels,
    datasets: [
      {{ label: 'YES', data: YEAR.yes, backgroundColor: GREEN + 'cc' }},
      {{ label: 'NO',  data: YEAR.no,  backgroundColor: RED   + 'cc' }},
    ]
  }},
  options: {{ responsive: true, plugins: {{ legend: {{ position: 'top' }} }},
    scales: {{ x: {{ stacked: true, grid: {{ color: GRID }} }}, y: {{ stacked: true, grid: {{ color: GRID }} }} }} }}
}});

if (CALIB) {{
  new Chart(document.getElementById('calibChart'), {{
    type: 'scatter',
    data: {{
      datasets: [
        {{ label: 'PM Actual',  data: CALIB.predicted.map((x,i) => ({{x, y: CALIB.actual[i]}})),
           backgroundColor: ACCENT, pointRadius: CALIB.counts.map(c => Math.max(4, Math.min(14, c/30))),
           pointHoverRadius: 8 }},
        {{ label: 'Perfect calibration', data: [{{x:0,y:0}},{{x:1,y:1}}],
           type: 'line', borderColor: '#4b5563', borderDash: [4,4], pointRadius: 0 }},
      ]
    }},
    options: {{ responsive: true,
      scales: {{
        x: {{ min:0, max:1, title: {{ display:true, text:'Predicted probability' }}, grid: {{ color: GRID }} }},
        y: {{ min:0, max:1, title: {{ display:true, text:'Actual YES rate' }}, grid: {{ color: GRID }} }},
      }},
      plugins: {{ tooltip: {{ callbacks: {{ label: (ctx) => {{
        const i = ctx.dataIndex;
        return `${{CALIB.labels[i]}}: actual=${{(CALIB.actual[i]*100).toFixed(1)}}% (n=${{CALIB.counts[i]}})`;
      }}}}}}}}
    }}
  }});
}}

// ── Event browser ─────────────────────────────────────────────────────────────
const PAGE_SIZE = 50;
let filtered = [...EVENTS];
let currentPage = 0;
let sortKey = 'date';
let sortDir = -1;

// Populate filter dropdowns
const cats = [...new Set(EVENTS.map(e => e.cat))].sort();
const years = [...new Set(EVENTS.map(e => e.date.slice(0,4)))].sort().reverse();
const catSel = document.getElementById('catFilter');
cats.forEach(c => {{ const o = document.createElement('option'); o.value = c; o.textContent = c; catSel.appendChild(o); }});
const yrSel = document.getElementById('yearFilter');
years.forEach(y => {{ const o = document.createElement('option'); o.value = y; o.textContent = y; yrSel.appendChild(o); }});

function filterTable() {{
  const q = document.getElementById('search').value.toLowerCase();
  const cat = document.getElementById('catFilter').value;
  const out = document.getElementById('outFilter').value;
  const yr  = document.getElementById('yearFilter').value;
  filtered = EVENTS.filter(e =>
    (!q   || e.q.toLowerCase().includes(q)) &&
    (!cat || e.cat === cat) &&
    (!out || (out === 'yes') === e.out) &&
    (!yr  || e.date.startsWith(yr))
  );
  currentPage = 0;
  renderTable();
}}

function sortTable(key) {{
  if (sortKey === key) sortDir *= -1; else {{ sortKey = key; sortDir = -1; }}
  filtered.sort((a, b) => {{
    const av = a[key] ?? '', bv = b[key] ?? '';
    return av < bv ? -sortDir : av > bv ? sortDir : 0;
  }});
  renderTable();
}}

function changePage(delta) {{
  currentPage = Math.max(0, Math.min(currentPage + delta, Math.ceil(filtered.length / PAGE_SIZE) - 1));
  renderTable();
}}

function renderTable() {{
  const start = currentPage * PAGE_SIZE;
  const page  = filtered.slice(start, start + PAGE_SIZE);
  const tbody = document.getElementById('evtBody');
  tbody.innerHTML = page.map(e => {{
    const probBar = e.pm_p !== null
      ? `<div class="prob-bar"><div class="prob-fill" style="width:${{(e.pm_p*100).toFixed(0)}}%"></div></div>${{(e.pm_p*100).toFixed(0)}}%`
      : '<span style="color:var(--muted)">—</span>';
    const link = e.url ? `<a href="${{e.url}}" target="_blank">${{e.q}}</a>` : e.q;
    return `<tr>
      <td>${{link}}</td>
      <td>${{e.cat}}</td>
      <td>${{e.date}}</td>
      <td class="${{e.out ? 'out-yes' : 'out-no'}}">${{e.out ? 'YES' : 'NO'}}</td>
      <td>${{probBar}}</td>
    </tr>`;
  }}).join('');

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  document.getElementById('pageInfo').textContent =
    `${{start+1}}–${{Math.min(start+PAGE_SIZE, filtered.length)}} of ${{filtered.length.toLocaleString()}}`;
  document.getElementById('prevBtn').disabled = currentPage === 0;
  document.getElementById('nextBtn').disabled = currentPage >= totalPages - 1;
}}

filterTable();
</script>
</body>
</html>"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    console.print(f"[bold green]Done.[/bold green] → {out_path} ({out_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate duel.html PoC report")
    parser.add_argument("--data-dir", default="data/poc", help="PoC data directory")
    parser.add_argument("--out", default="duel.html", help="Output HTML file")
    args = parser.parse_args()

    base = Path(os.environ.get("DATA_DIR", args.data_dir))
    render(base, Path(args.out))
