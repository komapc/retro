"""
Duel Report — TruthMachine vs Polymarket on 70-event main dataset.

For each event that has both a Polymarket price cache and oracle_question,
computes temporally-valid Brier scores for both sides and renders duel.html.

Comparison protocol:
  T = 7 days before outcome_date
  PM probability  : last available price on or before T (inverted if ev["polymarket"]["invert"])
  TM probability  : Oracle API forecast using articles published <= T, converted (stance+1)/2

TM predictions are fetched live from oracle.daatan.com (or ORACLE_URL) and
cached in data/duel_oracle/{event_id}.json.  Set ORACLE_API_KEY or configure
AWS Secrets Manager (openclaw/oracle-api-key) before running.

Usage:
    ORACLE_API_KEY=sk-... DATA_DIR=data python -m tm.duel_report
    ORACLE_API_KEY=sk-... DATA_DIR=data python -m tm.duel_report --out duel.html --t-days 7
    DATA_DIR=data python -m tm.duel_report --html-only  # re-render from cache, no API calls
"""

import argparse
import html
import json
import math
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console

console = Console()

T_DAYS_DEFAULT = 7


# ── Data loading ───────────────────────────────────────────────────────────────

def load_events_with_pm(data_dir: Path) -> list[dict]:
    """Return main events that have a polymarket URL and a non-empty price cache."""
    events = []
    pm_dir = data_dir / "polymarket"
    for f in sorted((data_dir / "events").glob("*.json")):
        ev = json.loads(f.read_text())
        pm_meta = ev.get("polymarket") or {}
        if not pm_meta.get("url"):
            continue
        cache = pm_dir / f"{ev['id']}.json"
        if not cache.exists():
            continue
        pm_data = json.loads(cache.read_text())
        if not pm_data.get("prices"):
            continue
        ev["_pm"] = pm_data
        events.append(ev)
    return events


def pm_probability(ev: dict, t_days: int) -> Optional[float]:
    """
    PM probability of our event happening, measured at T = outcome_date - t_days.
    Applies polarity inversion if ev["polymarket"]["invert"] is True.
    Falls back to earliest available price if no price exists before T.
    """
    prices = ev["_pm"].get("prices", [])
    if not prices:
        return None
    outcome_dt = datetime.strptime(ev["outcome_date"], "%Y-%m-%d").date()
    cutoff = outcome_dt - timedelta(days=t_days)
    candidates = [p for p in prices if datetime.strptime(p["date"], "%Y-%m-%d").date() <= cutoff]
    if not candidates:
        candidates = prices[:1]  # use earliest available if nothing before cutoff
    raw_prob = candidates[-1]["probability"]
    if (ev.get("polymarket") or {}).get("invert"):
        raw_prob = 1.0 - raw_prob
    return round(raw_prob, 4)


def _load_vault2_articles(data_dir: Path, eid: str, cutoff_str: str) -> list[dict]:
    """
    Return vault2 articles for event ``eid`` published on or before ``cutoff_str``.
    Each dict has url, title, text, published_date — ready for Oracle ArticleInput.
    """
    from urllib.parse import urlparse

    extractions_dir = data_dir / "vault2" / "extractions"
    articles_dir = data_dir / "vault2" / "articles"
    cutoff_dt = datetime.strptime(cutoff_str, "%Y-%m-%d").date()

    seen_hashes: set[str] = set()
    articles = []
    n_total = 0
    n_date_ok = 0
    for path in extractions_dir.glob(f"*_{eid}_v*.json"):
        article_hash = path.stem.split("_")[0]
        if article_hash in seen_hashes:
            continue
        seen_hashes.add(article_hash)
        n_total += 1
        art_path = articles_dir / f"{article_hash}.json"
        if not art_path.exists():
            console.print(f"  [yellow]Warning: article file missing for hash {article_hash} (event {eid})[/yellow]")
            continue
        art = json.loads(art_path.read_text())
        pub = datetime.strptime(art["published_at"], "%Y-%m-%d").date()
        if pub > cutoff_dt:
            continue
        n_date_ok += 1
        url = art.get("url", "")
        domain = re.sub(r"^www\.", "", urlparse(url).netloc)
        articles.append({
            "url": url,
            "title": art.get("headline", ""),
            "snippet": "",
            "source": domain,
            "published_date": art["published_at"],
            "text": art.get("text", ""),
        })
    console.print(f"  [dim]{eid}: {n_total} extractions, {n_date_ok} before {cutoff_str}, {len(articles)} returned[/dim]")
    return articles


def fetch_tm_probabilities_oracle(data_dir: Path, events: list[dict], t_days: int) -> dict[str, dict]:
    """
    For each event with oracle_question, run Oracle's full pipeline on vault2 articles.

    Flow per event:
      1. Gather vault2 articles published on or before outcome_date - t_days
      2. POST /forecast with question + articles (text= pre-fetched → skips trafilatura)
    Results cached in data/duel_oracle/{event_id}.json keyed on cutoff_date.

    Returns {event_id: {"probability": float, "articles_used": int, "mean_stance": float, ...}}
    """
    oracle_url = os.environ.get("ORACLE_URL", "https://oracle.daatan.com").rstrip("/")
    api_key = os.environ.get("ORACLE_API_KEY", "")
    if not api_key:
        try:
            import boto3
            sm = boto3.client("secretsmanager", region_name="eu-central-1")
            api_key = sm.get_secret_value(SecretId="openclaw/oracle-api-key")["SecretString"]
            console.print("[dim]Oracle API key loaded from Secrets Manager[/dim]")
        except Exception as e:
            console.print(f"[red]ORACLE_API_KEY not set and AWS fetch failed: {e}[/red]")

    if not api_key:
        console.print("[red bold]No Oracle API key — cannot fetch TM predictions. Set ORACLE_API_KEY.[/red bold]")
        return {}

    cache_dir = data_dir / "duel_oracle"
    cache_dir.mkdir(exist_ok=True)

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    result: dict[str, dict] = {}
    forecast_calls = 0  # pace /forecast calls under 10/min

    for ev in events:
        question = ev.get("oracle_question")
        if not question:
            console.print(f"  [yellow]{ev['id']}: no oracle_question — skipped[/yellow]")
            continue

        eid = ev["id"]
        outcome_dt = datetime.strptime(ev["outcome_date"], "%Y-%m-%d").date()
        cutoff = outcome_dt - timedelta(days=t_days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        # Serve from cache when cutoff and t_days match
        cache_path = cache_dir / f"{eid}.json"
        if cache_path.exists():
            cached = json.loads(cache_path.read_text())
            if (cached.get("cutoff_date") == cutoff_str
                    and cached.get("t_days") == t_days
                    and cached.get("probability") is not None):
                result[eid] = cached
                console.print(f"  [dim]{eid}: cache hit → p={cached['probability']} (n={cached.get('articles_used', '?')})[/dim]")
                continue

        # Gather vault2 articles pre-dating the cutoff
        articles = _load_vault2_articles(data_dir, eid, cutoff_str)
        console.print(f"  [cyan]{eid}: {len(articles)} vault2 articles before {cutoff_str}[/cyan]")
        if not articles:
            console.print(f"  [yellow]{eid}: no vault2 articles before cutoff — skipped[/yellow]")
            continue

        # Rate-limit: /forecast is 10/min, space calls ≥7s apart
        if forecast_calls > 0:
            time.sleep(7)

        payload = {
            "question": question,
            "articles": [
                {
                    "url": a["url"],
                    "title": a["title"],
                    "snippet": a["snippet"],
                    "source": a["source"],
                    "published_date": a["published_date"],
                    "text": a["text"] or None,
                }
                for a in articles
            ],
        }
        forecast = None
        for attempt in range(3):
            if attempt > 0:
                backoff = 15 * (2 ** (attempt - 1))
                console.print(f"  [dim]Oracle retry {attempt}/2 — backoff {backoff}s[/dim]")
                time.sleep(backoff)
            try:
                fr = httpx.post(
                    f"{oracle_url}/forecast",
                    json=payload,
                    headers=headers,
                    timeout=120,
                )
                forecast_calls += 1
                if fr.status_code in (429, 500, 502, 503):
                    console.print(f"  [dim yellow]{eid}: /forecast {fr.status_code} — will retry[/dim yellow]")
                    continue
                if fr.status_code != 200:
                    console.print(f"  [red]{eid}: /forecast {fr.status_code} — {fr.text[:120]}[/red]")
                    break
                forecast = fr.json()
                break
            except Exception as e:
                console.print(f"  [dim yellow]{eid}: /forecast error: {e}[/dim yellow]")
        if forecast is None:
            continue

        if forecast.get("placeholder"):
            console.print(f"  [yellow]{eid}: Oracle returned placeholder (no usable articles)[/yellow]")

        mean = forecast.get("mean", 0.0)
        articles_used = forecast.get("articles_used", 0)
        probability = round((mean + 1) / 2, 4)

        entry = {
            "event_id": eid,
            "probability": probability,
            "mean_stance": round(mean, 4),
            "articles_used": articles_used,
            "question": question,
            "cutoff_date": cutoff_str,
            "t_days": t_days,
            "placeholder": forecast.get("placeholder", False),
        }
        cache_path.write_text(json.dumps(entry, indent=2))
        result[eid] = entry
        console.print(f"  [green]{eid}: p={probability} (n={articles_used} Oracle articles)[/green]")

    return result


def brier(predicted: float, outcome: bool) -> float:
    return round((predicted - (1 if outcome else 0)) ** 2, 4)


# ── Build comparison rows ──────────────────────────────────────────────────────

def build_rows(events: list[dict], tm_probs: dict, t_days: int) -> list[dict]:
    rows = []
    for ev in events:
        eid = ev["id"]
        pm_p = pm_probability(ev, t_days)
        tm_info = tm_probs.get(eid)
        tm_p = tm_info["probability"] if tm_info else None
        outcome = bool(ev.get("outcome", False))

        pm_brier = brier(pm_p, outcome) if pm_p is not None else None
        tm_brier = brier(tm_p, outcome) if tm_p is not None else None

        pm_meta = ev.get("polymarket") or {}
        rows.append({
            "id": eid,
            "name": ev.get("name", ""),
            "outcome": outcome,
            "outcome_date": ev.get("outcome_date", ""),
            "category": ev.get("category", ""),
            "pm_question": ev["_pm"].get("question", ""),
            "pm_url": pm_meta.get("url", ""),
            "pm_invert": pm_meta.get("invert", False),
            "pm_p": pm_p,
            "tm_p": tm_p,
            "tm_articles_used": tm_info["articles_used"] if tm_info else 0,
            "tm_mean_stance": tm_info["mean_stance"] if tm_info else None,
            "pm_brier": pm_brier,
            "tm_brier": tm_brier,
            "pm_prices": ev["_pm"].get("prices", []),
            "winner": (
                "tm" if (tm_brier is not None and pm_brier is not None and tm_brier < pm_brier)
                else "pm" if (tm_brier is not None and pm_brier is not None and pm_brier < tm_brier)
                else "tie" if (tm_brier is not None and pm_brier is not None)
                else None
            ),
        })
    return rows


# ── Statistics ─────────────────────────────────────────────────────────────────

def avg_brier(rows: list[dict], key: str) -> Optional[float]:
    vals = [r[key] for r in rows if r[key] is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


# ── HTML rendering ─────────────────────────────────────────────────────────────

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #0f1117; color: #e2e8f0; min-height: 100vh; }
.container { max-width: 1100px; margin: 0 auto; padding: 2rem 1rem; }

/* Header scorecard */
.scorecard { display: flex; gap: 2rem; justify-content: center; margin: 2rem 0; flex-wrap: wrap; }
.scorecard-side { flex: 1; min-width: 200px; max-width: 280px; background: #1e2130;
                  border-radius: 12px; padding: 1.5rem; text-align: center; }
.scorecard-side h2 { font-size: 1rem; color: #94a3b8; margin-bottom: 0.5rem; }
.scorecard-side .brier { font-size: 2.5rem; font-weight: 700; }
.scorecard-side .label { font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }
.winner-badge { background: #facc15; color: #0f1117; border-radius: 8px;
                padding: 0.3rem 1rem; font-weight: 700; font-size: 0.85rem;
                display: inline-block; margin-top: 0.75rem; }
.tm-color { color: #60a5fa; }
.pm-color { color: #fb923c; }

.vs-divider { display: flex; align-items: center; font-size: 1.5rem;
              color: #475569; font-weight: 700; padding-top: 1rem; }

/* Section */
h1 { font-size: 1.8rem; font-weight: 700; margin-bottom: 0.5rem; }
.subtitle { color: #64748b; font-size: 0.9rem; margin-bottom: 2rem; }
h2 { font-size: 1.2rem; font-weight: 600; margin: 2.5rem 0 1rem; color: #cbd5e1; border-bottom: 1px solid #2d3748; padding-bottom: 0.5rem; }
.note { background: #1e2130; border-left: 3px solid #475569; padding: 0.75rem 1rem;
        font-size: 0.82rem; color: #94a3b8; margin-bottom: 1.5rem; border-radius: 0 6px 6px 0; }

/* Per-event cards */
.events-grid { display: flex; flex-direction: column; gap: 1rem; }
.event-card { background: #1e2130; border-radius: 10px; padding: 1rem 1.25rem;
              border-left: 4px solid #2d3748; }
.event-card.tm-wins { border-left-color: #3b82f6; }
.event-card.pm-wins { border-left-color: #f97316; }
.event-card.tie     { border-left-color: #64748b; }
.event-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
.event-name { font-weight: 600; font-size: 0.95rem; }
.event-meta { font-size: 0.75rem; color: #64748b; margin-top: 0.2rem; }
.event-pm-q { font-size: 0.75rem; color: #475569; margin-top: 0.15rem; font-style: italic; }
.event-pm-q .inv { color: #94a3b8; }
.badge { font-size: 0.7rem; font-weight: 700; padding: 0.2rem 0.6rem; border-radius: 999px;
         white-space: nowrap; }
.badge-tm { background: #1e3a5f; color: #60a5fa; }
.badge-pm { background: #431407; color: #fb923c; }
.badge-tie { background: #1e293b; color: #94a3b8; }

.event-body { display: flex; gap: 2rem; margin-top: 0.85rem; flex-wrap: wrap; }
.prob-block { flex: 1; min-width: 120px; }
.prob-label { font-size: 0.7rem; color: #64748b; margin-bottom: 0.2rem; }
.prob-bar-wrap { background: #0f1117; border-radius: 4px; height: 8px; margin: 4px 0; overflow: hidden; }
.prob-bar { height: 100%; border-radius: 4px; }
.prob-bar.tm { background: #3b82f6; }
.prob-bar.pm { background: #f97316; }
.prob-val { font-size: 0.85rem; font-weight: 600; }
.brier-val { font-size: 0.75rem; color: #64748b; }
.sparkline-wrap { flex: 2; min-width: 180px; }

/* Bar chart */
.bar-chart { display: flex; flex-direction: column; gap: 0.5rem; }
.bar-row { display: flex; align-items: center; gap: 0.75rem; font-size: 0.78rem; }
.bar-label { width: 120px; text-align: right; color: #94a3b8; white-space: nowrap;
             overflow: hidden; text-overflow: ellipsis; flex-shrink: 0; }
.bar-pair { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.bar-seg { height: 12px; border-radius: 2px; min-width: 2px; display: inline-block; }
.bar-seg.tm { background: #3b82f6; }
.bar-seg.pm { background: #f97316; }
.bar-num { width: 42px; font-size: 0.72rem; color: #64748b; }

/* Scatter */
#scatter-wrap { background: #1e2130; border-radius: 10px; padding: 1rem; }

/* Table */
table { width: 100%; border-collapse: collapse; font-size: 0.82rem; margin-top: 1rem; }
th { text-align: left; color: #64748b; font-weight: 600; padding: 0.5rem 0.75rem;
     border-bottom: 1px solid #2d3748; }
td { padding: 0.5rem 0.75rem; border-bottom: 1px solid #1a2030; vertical-align: middle; }
tr:hover td { background: #242840; }
.outcome-yes { color: #4ade80; font-weight: 600; }
.outcome-no  { color: #f87171; font-weight: 600; }
.better { color: #4ade80; font-weight: 600; }
.worse  { color: #f87171; }
.no-data { color: #475569; font-style: italic; }

footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #2d3748;
         font-size: 0.75rem; color: #475569; text-align: center; }
"""

_SPARKLINE_JS = """
function drawSparkline(canvas, prices, outcomeDate, tmP, invertedPm) {
  if (!canvas || !prices || prices.length === 0) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  const vals = prices.map(p => invertedPm ? 1 - p.probability : p.probability);
  const minV = 0, maxV = 1;

  function xFor(i) { return (i / (prices.length - 1)) * (W - 20) + 10; }
  function yFor(v) { return H - 8 - (v - minV) / (maxV - minV) * (H - 16); }

  // Grid lines
  ctx.strokeStyle = '#2d3748';
  ctx.lineWidth = 0.5;
  [0.25, 0.5, 0.75].forEach(g => {
    ctx.beginPath();
    ctx.moveTo(0, yFor(g));
    ctx.lineTo(W, yFor(g));
    ctx.stroke();
  });

  // PM price line
  ctx.beginPath();
  ctx.strokeStyle = '#f97316';
  ctx.lineWidth = 1.5;
  vals.forEach((v, i) => {
    if (i === 0) ctx.moveTo(xFor(i), yFor(v));
    else ctx.lineTo(xFor(i), yFor(v));
  });
  ctx.stroke();

  // TM horizontal line (if available)
  if (tmP !== null) {
    ctx.beginPath();
    ctx.strokeStyle = '#3b82f6';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.moveTo(10, yFor(tmP));
    ctx.lineTo(W - 10, yFor(tmP));
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // T-7 vertical marker
  const tIdx = prices.length - 1; // approximation: last point before outcome
  ctx.beginPath();
  ctx.strokeStyle = '#475569';
  ctx.lineWidth = 1;
  ctx.setLineDash([2, 2]);
  ctx.moveTo(xFor(tIdx), 0);
  ctx.lineTo(xFor(tIdx), H);
  ctx.stroke();
  ctx.setLineDash([]);
}
"""


def _bar_width(brier_val: Optional[float], max_brier: float = 0.5) -> int:
    if brier_val is None:
        return 0
    return max(2, int((brier_val / max_brier) * 300))


def render_html(rows: list[dict], t_days: int, out_path: Path) -> None:
    compared = [r for r in rows if r["pm_p"] is not None and r["tm_p"] is not None]
    tm_avg = avg_brier(compared, "tm_brier")
    pm_avg = avg_brier(compared, "pm_brier")

    if tm_avg is not None and pm_avg is not None:
        if tm_avg < pm_avg:
            overall_winner = "TruthMachine"
            winner_css = "tm-color"
        elif pm_avg < tm_avg:
            overall_winner = "Polymarket"
            winner_css = "pm-color"
        else:
            overall_winner = "Tie"
            winner_css = ""
    else:
        overall_winner = "—"
        winner_css = ""

    # Scatter data
    scatter_data = json.dumps([
        {"x": r["pm_p"], "y": r["tm_p"], "label": r["id"]}
        for r in compared
    ])

    # Build event cards HTML
    cards_html = []
    for r in rows:
        card_class = {"tm": "tm-wins", "pm": "pm-wins", "tie": "tie"}.get(r["winner"] or "", "")
        winner_badge = ""
        if r["winner"] == "tm":
            winner_badge = '<span class="badge badge-tm">TM wins</span>'
        elif r["winner"] == "pm":
            winner_badge = '<span class="badge badge-pm">PM wins</span>'
        elif r["winner"] == "tie":
            winner_badge = '<span class="badge badge-tie">Tie</span>'

        inv_note = ' <span class="inv">(inverted)</span>' if r["pm_invert"] else ""
        pm_q_html = f'<div class="event-pm-q">PM: {html.escape(r["pm_question"])}{inv_note}</div>'

        # Probability bars
        def _prob_block(label, val, css_class, brier_val, n_art=None):
            if val is None:
                return f'<div class="prob-block"><div class="prob-label">{label}</div><div class="no-data">no data</div></div>'
            pct = int(val * 100)
            w = int(val * 100)
            art_note = f" ({n_art} art.)" if n_art is not None else ""
            return f"""
            <div class="prob-block">
              <div class="prob-label">{label}{art_note}</div>
              <div class="prob-bar-wrap"><div class="prob-bar {css_class}" style="width:{w}%"></div></div>
              <span class="prob-val">{pct}%</span>
              <span class="brier-val"> Brier: {brier_val if brier_val is not None else '—'}</span>
            </div>"""

        tm_block = _prob_block("TruthMachine", r["tm_p"], "tm", r["tm_brier"], r["tm_articles_used"])
        pm_block = _prob_block(f"Polymarket (T-{t_days}d)", r["pm_p"], "pm", r["pm_brier"])

        # Sparkline
        prices_json = json.dumps(r["pm_prices"])
        tm_p_js = "null" if r["tm_p"] is None else str(r["tm_p"])
        invert_js = "true" if r["pm_invert"] else "false"
        canvas_id = f"spark-{r['id']}"
        sparkline = f"""
        <div class="sparkline-wrap">
          <div class="prob-label">PM price history  <span style="color:#f97316">━</span> PM  <span style="color:#3b82f6">╌</span> TM</div>
          <canvas id="{canvas_id}" width="260" height="60" style="width:100%;max-width:260px;height:60px"></canvas>
          <script>
            (function(){{
              var el=document.getElementById('{canvas_id}');
              drawSparkline(el,{prices_json},{{}},{tm_p_js},{invert_js});
            }})();
          </script>
        </div>"""

        cards_html.append(f"""
        <div class="event-card {card_class}">
          <div class="event-header">
            <div>
              <div class="event-name">{r['id']} — {r['name']}</div>
              <div class="event-meta">{r['outcome_date']} · outcome: <span class="outcome-yes">YES</span> · {r['category']}</div>
              {pm_q_html}
            </div>
            {winner_badge}
          </div>
          <div class="event-body">
            {tm_block}
            {pm_block}
            {sparkline}
          </div>
        </div>""")

    cards_joined = "\n".join(cards_html)

    # Bar chart
    max_brier = max(
        (r["pm_brier"] or 0 for r in compared),
        default=0.5
    )
    max_brier = max(max_brier, 0.1)
    bar_rows = []
    for r in sorted(compared, key=lambda x: abs((x["tm_brier"] or 0) - (x["pm_brier"] or 0)), reverse=True):
        tw = _bar_width(r["tm_brier"], max_brier)
        pw = _bar_width(r["pm_brier"], max_brier)
        bar_rows.append(f"""
        <div class="bar-row">
          <div class="bar-label">{r['id']}</div>
          <div class="bar-pair">
            <div><span class="bar-seg tm" style="width:{tw}px"></span></div>
            <div><span class="bar-seg pm" style="width:{pw}px"></span></div>
          </div>
          <div class="bar-num">{r['tm_brier']}</div>
          <div class="bar-num">{r['pm_brier']}</div>
        </div>""")
    bar_chart_html = "\n".join(bar_rows)

    # Table
    table_rows = []
    for r in rows:
        tm_p_str = f"{int(r['tm_p']*100)}%" if r["tm_p"] is not None else '<span class="no-data">—</span>'
        pm_p_str = f"{int((r['pm_p'] or 0)*100)}%" if r["pm_p"] is not None else '<span class="no-data">—</span>'
        inv_mark = " ↻" if r["pm_invert"] else ""
        tm_b = r["tm_brier"]
        pm_b = r["pm_brier"]
        if tm_b is not None and pm_b is not None:
            tm_b_str = f'<span class="{"better" if tm_b < pm_b else "worse"}">{tm_b}</span>'
            pm_b_str = f'<span class="{"better" if pm_b < tm_b else "worse"}">{pm_b}</span>'
        else:
            tm_b_str = f"{tm_b}" if tm_b is not None else '<span class="no-data">—</span>'
            pm_b_str = f"{pm_b}" if pm_b is not None else '<span class="no-data">—</span>'
        winner_str = {"tm": "TM ✓", "pm": "PM ✓", "tie": "Tie"}.get(r["winner"] or "", "—")
        table_rows.append(f"""
        <tr>
          <td>{r['id']}</td>
          <td>{r['name'][:45]}</td>
          <td class="outcome-yes">YES</td>
          <td>{html.escape(r['pm_question'][:40])}{inv_mark}</td>
          <td>{pm_p_str}</td>
          <td>{tm_p_str} <span style="font-size:0.7rem;color:#475569">({r['tm_articles_used']}art)</span></td>
          <td>{pm_b_str}</td>
          <td>{tm_b_str}</td>
          <td>{winner_str}</td>
        </tr>""")
    table_rows_html = "\n".join(table_rows)

    # Score summary line
    n_compared = len(compared)
    tm_wins = sum(1 for r in compared if r["winner"] == "tm")
    pm_wins = sum(1 for r in compared if r["winner"] == "pm")
    ties = sum(1 for r in compared if r["winner"] == "tie")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>TruthMachine vs Polymarket — Duel</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{_CSS}</style>
</head>
<body>
<div class="container">

<h1>TruthMachine <span style="color:#475569">vs</span> Polymarket</h1>
<p class="subtitle">Phase 1 · {n_compared} events · T = {t_days} days before resolution · all outcomes YES</p>

<div class="note">
  <strong>Methodology:</strong>
  PM probability = last CLOB price on or before <em>outcome_date − {t_days} days</em>
  (inverted where PM question is framed as "will X survive?" vs our event "X was killed").<br>
  TM probability = Oracle API forecast (gatekeeper+extractor+credibility weighting) on vault2 articles published ≤ T, converted (stance+1)/2.<br>
  All 11 events resolved YES (our dataset captures things that happened).
  Brier score: lower = better. Range [0, 1].
</div>

<!-- Scorecard -->
<div class="scorecard">
  <div class="scorecard-side">
    <h2>TruthMachine</h2>
    <div class="brier tm-color">{tm_avg if tm_avg is not None else "—"}</div>
    <div class="label">avg Brier ({n_compared} events)</div>
    <div class="label" style="margin-top:0.5rem">wins: {tm_wins} / {n_compared}</div>
  </div>
  <div class="vs-divider">VS</div>
  <div class="scorecard-side">
    <h2>Polymarket</h2>
    <div class="brier pm-color">{pm_avg if pm_avg is not None else "—"}</div>
    <div class="label">avg Brier ({n_compared} events)</div>
    <div class="label" style="margin-top:0.5rem">wins: {pm_wins} / {n_compared}</div>
  </div>
</div>
<div style="text-align:center;margin-bottom:2rem">
  <span class="winner-badge {winner_css}">
    {"🏆 " if overall_winner not in ("Tie","—") else ""}{overall_winner} wins
  </span>
  &nbsp;
  <span style="color:#64748b;font-size:0.82rem">
    (ties: {ties} · ⚠ n={n_compared} is small — results are indicative, not conclusive)
  </span>
</div>

<!-- Sparkline helper -->
<script>{_SPARKLINE_JS}</script>

<!-- Per-event cards -->
<h2>Per-event breakdown</h2>
<div class="events-grid">
{cards_joined}
</div>

<!-- Bar chart -->
<h2>Brier score comparison <span style="font-size:0.75rem;color:#475569">(shorter = better · <span style="color:#3b82f6">■</span> TM  <span style="color:#f97316">■</span> PM · sorted by |Δ|)</span></h2>
<div style="background:#1e2130;border-radius:10px;padding:1rem">
  <div style="font-size:0.72rem;color:#64748b;margin-bottom:0.75rem">
    TM (top bar) vs PM (bottom bar) per event
  </div>
  <div class="bar-chart">
{bar_chart_html}
  </div>
</div>

<!-- Scatter -->
<h2>Agreement scatter <span style="font-size:0.75rem;color:#475569">(diagonal = perfect agreement)</span></h2>
<div id="scatter-wrap">
  <canvas id="scatter-canvas" width="500" height="400" style="max-width:100%;display:block;margin:0 auto"></canvas>
</div>

<!-- Data table -->
<h2>Full data table</h2>
<div style="overflow-x:auto">
<table>
  <thead>
    <tr>
      <th>ID</th><th>TM Event</th><th>Out</th><th>PM Question</th>
      <th>PM@T-{t_days}d</th><th>TM prob</th><th>PM Brier</th><th>TM Brier</th><th>Winner</th>
    </tr>
  </thead>
  <tbody>
{table_rows_html}
  </tbody>
</table>
</div>

<footer>
  Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC ·
  TruthMachine data: Oracle API (oracle.daatan.com) ·
  Polymarket data: CLOB API (gamma-api.polymarket.com) ·
  T = {t_days} days before outcome_date
</footer>

<script>
// Scatter plot
(function() {{
  var data = {scatter_data};
  var canvas = document.getElementById('scatter-canvas');
  if (!canvas || !data.length) return;
  var ctx = canvas.getContext('2d');
  var W = canvas.width, H = canvas.height;
  var pad = 50;
  function sx(v) {{ return pad + v * (W - 2*pad); }}
  function sy(v) {{ return H - pad - v * (H - 2*pad); }}

  // Axes
  ctx.strokeStyle = '#2d3748';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad, pad); ctx.lineTo(pad, H-pad); ctx.lineTo(W-pad, H-pad); ctx.stroke();

  // Diagonal
  ctx.strokeStyle = '#334155';
  ctx.setLineDash([4,4]);
  ctx.beginPath(); ctx.moveTo(pad,H-pad); ctx.lineTo(W-pad,pad); ctx.stroke();
  ctx.setLineDash([]);

  // Grid
  ctx.strokeStyle = '#1e2130';
  [0.25,0.5,0.75].forEach(g => {{
    ctx.beginPath(); ctx.moveTo(sx(g),pad); ctx.lineTo(sx(g),H-pad);
    ctx.moveTo(pad,sy(g)); ctx.lineTo(W-pad,sy(g)); ctx.stroke();
  }});

  // Axis labels
  ctx.fillStyle = '#64748b';
  ctx.font = '12px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('PM probability at T-{t_days}', W/2, H-10);
  ctx.save(); ctx.translate(14, H/2); ctx.rotate(-Math.PI/2);
  ctx.fillText('TM probability', 0, 0); ctx.restore();
  [0,0.25,0.5,0.75,1].forEach(v => {{
    ctx.fillText(Math.round(v*100)+'%', sx(v), H-pad+18);
    ctx.textAlign='right';
    ctx.fillText(Math.round(v*100)+'%', pad-6, sy(v)+4);
    ctx.textAlign='center';
  }});

  // Points
  data.forEach(d => {{
    ctx.beginPath();
    ctx.arc(sx(d.x), sy(d.y), 7, 0, 2*Math.PI);
    ctx.fillStyle = '#22c55e';
    ctx.fill();
    ctx.strokeStyle = '#15803d';
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = '#e2e8f0';
    ctx.font = 'bold 9px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(d.label, sx(d.x), sy(d.y)-10);
  }});
}})();
</script>

</div>
</body>
</html>"""

    out_path.write_text(html)
    console.print(f"[bold green]Wrote {out_path}[/bold green] ({out_path.stat().st_size // 1024} KB)")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=os.environ.get("DATA_DIR", "data"))
    ap.add_argument("--out", default="duel.html")
    ap.add_argument("--t-days", type=int, default=T_DAYS_DEFAULT)
    ap.add_argument(
        "--html-only",
        action="store_true",
        help="Re-render duel.html from existing duel_oracle cache — no API calls",
    )
    ap.add_argument(
        "--clear-cache",
        action="store_true",
        help="Delete all duel_oracle/*.json cache files before fetching",
    )
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    out_path = Path(args.out)

    if args.clear_cache:
        cache_dir = data_dir / "duel_oracle"
        removed = list(cache_dir.glob("*.json"))
        for f in removed:
            f.unlink()
        console.print(f"[yellow]Cleared {len(removed)} cached Oracle results[/yellow]")

    events = load_events_with_pm(data_dir)
    console.print(f"Events with PM price data: {len(events)}")

    if args.html_only:
        # Load from cache only — no API calls
        cache_dir = data_dir / "duel_oracle"
        tm_probs: dict[str, dict] = {}
        outcome_dt_map = {ev["id"]: ev["outcome_date"] for ev in events}
        for ev in events:
            eid = ev["id"]
            cache_path = cache_dir / f"{eid}.json"
            if cache_path.exists():
                cached = json.loads(cache_path.read_text())
                if cached.get("probability") is not None:
                    tm_probs[eid] = cached
        console.print(f"Events loaded from cache (--html-only): {len(tm_probs)}")
    else:
        console.print(f"Fetching TM predictions from Oracle API (T-{args.t_days}d cutoff)...")
        tm_probs = fetch_tm_probabilities_oracle(data_dir, events, args.t_days)
        console.print(f"Events with Oracle predictions: {len(tm_probs)}")

    rows = build_rows(events, tm_probs, args.t_days)

    compared = [r for r in rows if r["pm_p"] is not None and r["tm_p"] is not None]
    console.print(f"Events in Brier comparison: {len(compared)}")

    for r in rows:
        tm_str = f"TM={r['tm_p']}" if r["tm_p"] is not None else "TM=—"
        pm_str = f"PM={r['pm_p']}" if r["pm_p"] is not None else "PM=—"
        w = r["winner"] or "—"
        console.print(f"  {r['id']}: {tm_str} {pm_str} → {w}")

    render_html(rows, args.t_days, out_path)


if __name__ == "__main__":
    main()
