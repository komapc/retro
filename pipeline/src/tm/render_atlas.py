"""
Factum Atlas — static HTML renderer.

Usage:
    DATA_DIR=/path/to/data uv run python -m tm.render_atlas
    # Writes factum_atlas.html next to the data dir.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

# ── palette ───────────────────────────────────────────────────────────────────
SOURCE_COLORS = {
    "ynet":         "#60a5fa",
    "haaretz":      "#f472b6",
    "toi":          "#34d399",
    "globes":       "#fb923c",
    "reuters":      "#a78bfa",
    "israel_hayom": "#facc15",
    "n12":          "#f87171",
    "jpost":        "#4ade80",
    "bloomberg":    "#38bdf8",
    "bbc":          "#e879f9",
    "walla":        "#94a3b8",
    "calcalist":    "#fbbf24",
    "kan11":        "#c084fc",
    "aljazeera":    "#34d399",
}
SOURCES = list(SOURCE_COLORS.keys())

MVP_EVENTS = [
    "A01", "A02", "A03", "A04", "A05",
    "A06", "A07", "A08", "A09",
    "A12", "A13", "A14", "A15", "A19",
    "C05", "C06", "C07", "C08", "C09",
    "B04", "B08", "B09", "B10", "B11", "B13",
    "D02", "D03",
    "E07", "E08",
    "G02", "G05", "G06",
    "F05",
]

TEMPLATE_PATH = Path(__file__).parent / "templates" / "atlas.html"


# ── data helpers ──────────────────────────────────────────────────────────────

def load_json(p: Path) -> Any:
    with open(p) as f:
        return json.load(f)


def stance_to_color(stance: float) -> str:
    """Map stance [-1, 1] to a CSS rgb colour (red → grey → green)."""
    if stance > 0.15:
        g = int(80 + 110 * min(stance, 1))
        return f"rgb(30,{g},70)"
    if stance < -0.15:
        r = int(80 + 110 * min(-stance, 1))
        return f"rgb({r},30,50)"
    return "rgb(50,55,70)"


def load_atlas_data(data_dir: Path) -> dict:
    events, sources, cells, polymarket = {}, {}, {}, {}

    for eid in MVP_EVENTS:
        p = data_dir / "events" / f"{eid}.json"
        if p.exists():
            events[eid] = load_json(p)

    for sid in SOURCES:
        p = data_dir / "sources" / f"{sid}.json"
        if p.exists():
            sources[sid] = load_json(p)

    for eid in events:
        for sid in SOURCES:
            cell_dir = data_dir / "atlas" / eid / sid
            if not cell_dir.exists():
                continue
            entries = [load_json(fp) for fp in sorted(cell_dir.glob("*.json"))]
            if entries:
                cells[(eid, sid)] = entries

    pm_dir = data_dir / "polymarket"
    if pm_dir.exists():
        for eid in events:
            p = pm_dir / f"{eid}.json"
            if p.exists():
                d = load_json(p)
                if d.get("prices"):
                    polymarket[eid] = d["prices"]

    return dict(events=events, sources=sources, cells=cells, polymarket=polymarket)


def load_search_status(data_dir: Path) -> dict[tuple, str]:
    """
    Returns {(eid, sid): status} for all cells that were ever searched.
    Status is one of: 'done', 'no_predictions', 'failed'.
    Cells absent from progress.json were never searched.
    """
    p = data_dir / "progress.json"
    if not p.exists():
        return {}
    raw = load_json(p)
    result = {}
    for key, cell in raw.get("cells", {}).items():
        eid = cell.get("event_id") or key.split(":")[0]
        sid = cell.get("source_id") or key.split(":")[1]
        result[(eid, sid)] = cell.get("status", "pending")
    return result


def build_timeseries(cells: dict, events: dict, eid: str) -> dict:
    ev = events.get(eid)
    if not ev:
        return {}
    outcome_dt = datetime.strptime(ev["outcome_date"], "%Y-%m-%d")
    series = {}
    for sid in SOURCES:
        points = []
        for entry in cells.get((eid, sid), []):
            art_date_str = entry.get("article_date", "")
            try:
                art_dt = datetime.strptime(art_date_str[:10], "%Y-%m-%d")
            except ValueError:
                continue
            days_before = (outcome_dt - art_dt).days
            if days_before < 0:
                continue
            for p in entry.get("predictions", []):
                points.append({
                    "days_before": days_before,
                    "date": art_date_str[:10],
                    "stance": round(p.get("stance", 0), 3),
                    "certainty": round(p.get("certainty", 0), 3),
                    "hedge_index": round(p.get("hedge_index", p.get("hedge_ratio", 0)), 3),
                    "quote": p.get("quote", "")[:120],
                    "claim": p.get("claim", ""),
                    "headline": entry.get("headline", ""),
                })
        if points:
            series[sid] = sorted(points, key=lambda x: -x["days_before"])
    return series


# ── scoring ───────────────────────────────────────────────────────────────────

def compute_brier_scores(cells: dict, events: dict) -> dict:
    """
    Returns {
      'by_event': {eid: {n, avg_stance, implied_p, brier, outcome}},
      'by_source': {sid: {n, brier}},
      'overall': {n, brier, skill},
    }
    skill = 1 - (brier / 0.25)  — positive means better than random (always-50%)
    """
    by_event: dict[str, dict] = {}
    by_source: dict[str, list] = {sid: [] for sid in SOURCES}

    for eid in MVP_EVENTS:
        ev = events.get(eid)
        if not ev:
            continue
        outcome = 1.0 if ev.get("outcome") else 0.0
        scores = []
        for sid in SOURCES:
            for entry in cells.get((eid, sid), []):
                for pred in entry.get("predictions", []):
                    stance = pred.get("stance", 0.0)
                    p = (stance + 1.0) / 2.0          # map [-1,1] → [0,1]
                    bs = (p - outcome) ** 2
                    scores.append(bs)
                    by_source[sid].append(bs)

        if scores:
            avg_bs = sum(scores) / len(scores)
            avg_stance = sum(
                (pred.get("stance", 0.0) + 1.0) / 2.0
                for s_ in SOURCES
                for entry in cells.get((eid, s_), [])
                for pred in entry.get("predictions", [])
            ) / len(scores)
            by_event[eid] = {
                "n": len(scores),
                "implied_p": round(avg_stance * 100, 1),
                "brier": round(avg_bs, 3),
                "outcome": int(outcome),
            }

    all_scores = [bs for lst in by_source.values() for bs in lst]
    overall_brier = round(sum(all_scores) / len(all_scores), 3) if all_scores else None
    skill = round(1 - overall_brier / 0.25, 3) if overall_brier is not None else None

    source_summary = {}
    for sid, lst in by_source.items():
        if lst:
            source_summary[sid] = {
                "n": len(lst),
                "brier": round(sum(lst) / len(lst), 3),
            }

    return dict(by_event=by_event, by_source=source_summary,
                overall=dict(n=len(all_scores), brier=overall_brier, skill=skill))


# ── HTML fragments ─────────────────────────────────────────────────────────────

def _render_matrix(matrix_rows: list, search_status: dict) -> str:
    parts = [
        '<table class="matrix"><thead><tr>',
        '<th class="event-label">Event</th>',
    ]
    for sid in SOURCES:
        parts.append(f'<th style="color:{SOURCE_COLORS[sid]}">{sid}</th>')
    parts.append('</tr></thead><tbody>')

    for row in matrix_rows:
        eid = row["id"]
        badge = (
            '<span class="outcome-badge badge-false">FALSE</span>'
            if not row["outcome"] else ""
        )
        parts.append(
            f'<tr>'
            f'<td class="event-label">'
            f'<span class="event-name">'
            f'<span class="event-id">{eid}</span>'
            f'<a href="#event-{eid}">{row["name"][:42]}</a>'
            f'</span>'
            f'{badge}'
            f'</td>'
        )
        for cell in row["cells"]:
            sid = cell["sid"]
            status = search_status.get((eid, sid), "pending")

            if cell["article_count"] > 0:
                bg = stance_to_color(cell["avg_stance"] or 0)
                stance_str = f'{cell["avg_stance"]:+.2f}' if cell["avg_stance"] is not None else "—"
                title = f'{cell["pred_count"]} predictions, avg stance {stance_str}'
                onclick = f"document.getElementById('event-{eid}').scrollIntoView({{behavior:'smooth'}})"
                parts.append(
                    f'<td class="cell has-data" style="background:{bg}"'
                    f' onclick="{onclick}" title="{title}">'
                    f'<div class="cell-inner">'
                    f'<span class="cell-count">{cell["article_count"]}</span>'
                    f'<span class="cell-stance">{stance_str}</span>'
                    f'</div></td>'
                )
            elif status in ("no_predictions", "done", "failed"):
                # Searched but found nothing
                title = "Searched — no predictions found"
                parts.append(
                    f'<td class="cell cell-searched" title="{title}">'
                    f'<div class="cell-empty searched">—</div>'
                    f'</td>'
                )
            else:
                # Never searched
                parts.append('<td class="cell"><div class="cell-empty">·</div></td>')

        parts.append('</tr>')

    parts.append('</tbody></table>')
    return ''.join(parts)


def _render_event_sections(event_ids: list, events: dict, polymarket: dict) -> str:
    parts = []
    for eid in event_ids:
        ev = events.get(eid)
        if not ev:
            continue
        badge_cls = "badge-true" if ev["outcome"] else "badge-false"
        badge_txt = "TRUE" if ev["outcome"] else "FALSE"
        pm_note = ""
        if eid in polymarket:
            prices = polymarket[eid]
            if prices:
                last_prob = prices[-1]["probability"]
                pm_note = (
                    f' &nbsp;<span style="color:#a78bfa;font-size:11px">'
                    f'Polymarket final: {last_prob*100:.0f}%</span>'
                )
        parts.append(
            f'<div class="event-section" id="event-{eid}">'
            f'<div class="event-header">'
            f'<h2><span style="font-family:monospace;color:#58a6ff;margin-right:8px">{eid}</span>'
            f'{ev["name"]}</h2>'
            f'<span class="outcome-badge {badge_cls}">{badge_txt}</span>'
            f'<span class="event-meta">{ev["outcome_date"]}{pm_note}</span>'
            f'</div>'
            f'<div class="chart-wrap">'
            f'<div class="chart-container"><canvas id="chart-{eid}"></canvas></div>'
            f'</div>'
            f'</div>'
        )
    return ''.join(parts)


def _render_scoring(scores: dict, events: dict) -> str:
    overall = scores["overall"]
    by_event = scores["by_event"]
    by_source = scores["by_source"]

    if overall["brier"] is None:
        return '<p style="color:var(--muted)">Not enough data to compute scores.</p>'

    skill_color = "#3fb950" if (overall["skill"] or 0) > 0 else "#f85149"
    skill_str = f'{overall["skill"]:+.3f}' if overall["skill"] is not None else "—"

    # ── overall bar ──
    html = f"""
<div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:24px">
  <div class="stat">
    <div class="stat-n">{overall['brier']:.3f}</div>
    <div class="stat-l">Overall Brier Score</div>
  </div>
  <div class="stat">
    <div class="stat-n" style="color:{skill_color}">{skill_str}</div>
    <div class="stat-l">Skill vs. Random (0.25)</div>
  </div>
  <div class="stat">
    <div class="stat-n">{overall['n']}</div>
    <div class="stat-l">Predictions Scored</div>
  </div>
</div>
<p style="color:var(--muted);font-size:12px;margin-bottom:16px">
  <strong style="color:var(--text)">Brier score</strong>: mean squared error between
  implied probability (stance mapped from [&minus;1,&thinsp;+1] to [0%,&thinsp;100%]) and the binary outcome.
  Lower&nbsp;=&nbsp;better. Random baseline&nbsp;=&nbsp;0.250.
  <strong style="color:var(--text)">Skill</strong>&nbsp;= 1&nbsp;&minus;&nbsp;Brier/0.25; positive means better than random.
</p>
"""

    # ── per-event table ──
    html += """
<table class="pred-table" style="margin-bottom:32px">
  <thead><tr>
    <th>Event</th><th>Outcome</th><th>N preds</th>
    <th>Avg implied P</th><th>Brier Score</th><th>Skill</th>
  </tr></thead>
  <tbody>
"""
    for eid in MVP_EVENTS:
        s = by_event.get(eid)
        if not s:
            continue
        ev_name = events.get(eid, {}).get("name", eid)
        outcome_badge = (
            '<span class="outcome-badge badge-true">TRUE</span>'
            if s["outcome"] else
            '<span class="outcome-badge badge-false">FALSE</span>'
        )
        brier = s["brier"]
        skill = round(1 - brier / 0.25, 3)
        skill_clr = "#3fb950" if skill > 0 else "#f85149"
        p_clr = "#3fb950" if s["implied_p"] >= 50 else "#f85149"
        html += (
            f'<tr>'
            f'<td><span style="font-family:monospace;color:#58a6ff">{eid}</span>'
            f' <span style="color:var(--muted);font-size:11px">{ev_name[:40]}</span></td>'
            f'<td>{outcome_badge}</td>'
            f'<td style="text-align:center">{s["n"]}</td>'
            f'<td style="text-align:center;color:{p_clr}">{s["implied_p"]:.1f}%</td>'
            f'<td style="text-align:center">{brier:.3f}</td>'
            f'<td style="text-align:center;color:{skill_clr};font-weight:600">{skill:+.3f}</td>'
            f'</tr>'
        )
    html += '</tbody></table>'

    # ── per-source table ──
    html += """
<table class="pred-table">
  <thead><tr>
    <th>Source</th><th>N preds</th><th>Brier Score</th><th>Skill vs. Random</th>
  </tr></thead>
  <tbody>
"""
    for sid, s in sorted(by_source.items(), key=lambda x: x[1]["brier"]):
        color = SOURCE_COLORS.get(sid, "#888")
        skill = round(1 - s["brier"] / 0.25, 3)
        skill_clr = "#3fb950" if skill > 0 else "#f85149"
        html += (
            f'<tr>'
            f'<td><span class="source-dot" style="background:{color}"></span>{sid}</td>'
            f'<td style="text-align:center">{s["n"]}</td>'
            f'<td style="text-align:center">{s["brier"]:.3f}</td>'
            f'<td style="text-align:center;color:{skill_clr};font-weight:600">{skill:+.3f}</td>'
            f'</tr>'
        )
    html += '</tbody></table>'

    return html


# ── main render ───────────────────────────────────────────────────────────────

def render(data_dir: Path, output_path: Path):
    d = load_atlas_data(data_dir)
    events, sources, cells, polymarket = d["events"], d["sources"], d["cells"], d["polymarket"]
    search_status = load_search_status(data_dir)

    total_articles = sum(len(v) for v in cells.values())
    total_preds = sum(
        sum(len(e.get("predictions", [])) for e in v)
        for v in cells.values()
    )

    # ── matrix rows ──
    matrix_rows = []
    for eid in MVP_EVENTS:
        ev = events.get(eid)
        if not ev:
            continue
        row = {"id": eid, "name": ev["name"], "outcome": ev["outcome"],
               "outcome_date": ev["outcome_date"], "cells": []}
        for sid in SOURCES:
            entries = cells.get((eid, sid), [])
            stances = [p.get("stance", 0) for e in entries for p in e.get("predictions", [])]
            row["cells"].append({
                "sid": sid,
                "article_count": len(entries),
                "pred_count": len(stances),
                "avg_stance": round(sum(stances) / len(stances), 2) if stances else None,
            })
        matrix_rows.append(row)

    # ── chart + predictions data ──
    chart_data = {}
    all_preds = []

    for eid in MVP_EVENTS:
        ev = events.get(eid)
        if not ev:
            continue
        series = build_timeseries(cells, events, eid)
        outcome_dt = datetime.strptime(ev["outcome_date"], "%Y-%m-%d")

        pm_series = []
        for pt in polymarket.get(eid, []):
            try:
                dt = datetime.strptime(pt["date"], "%Y-%m-%d")
                days_before = (outcome_dt - dt).days
                if 0 <= days_before <= ev.get("predictive_window_days", 14) + 5:
                    pm_series.append({"x": days_before, "y": round(pt["probability"] * 100, 1)})
            except ValueError:
                continue
        pm_series.sort(key=lambda p: -p["x"])

        chart_data[eid] = {
            "event_name": ev["name"],
            "outcome": ev["outcome"],
            "outcome_date": ev["outcome_date"],
            "sources": {
                sid: [{"x": pt["days_before"], "y": round(pt["stance"] * 100, 1),
                       "certainty": pt["certainty"], "hedge": pt["hedge_index"],
                       "quote": pt["quote"]}
                      for pt in pts]
                for sid, pts in series.items()
            },
            "polymarket": pm_series,
        }

        for sid, pts in series.items():
            for pt in pts:
                all_preds.append({
                    "eid": eid,
                    "event_name": ev["name"],
                    "sid": sid,
                    "source_name": sources.get(sid, {}).get("name", sid),
                    "date": pt["date"],
                    "days_before": pt["days_before"],
                    "stance": pt["stance"],
                    "certainty": pt["certainty"],
                    "hedge_index": pt["hedge_index"],
                    "quote": pt["quote"],
                    "claim": pt["claim"],
                    "headline": pt["headline"],
                })

    all_preds.sort(key=lambda x: (x["eid"], x["days_before"]))

    # ── scoring ──
    scores = compute_brier_scores(cells, events)
    scoring_html = _render_scoring(scores, events)

    # ── fill template ──
    active_events = [e for e in MVP_EVENTS if e in events]
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.format(
        stats_events=len(active_events),
        stats_articles=total_articles,
        stats_preds=total_preds,
        stats_cells=len(cells),
        stats_pm=len(polymarket),
        run_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        matrix_html=_render_matrix(matrix_rows, search_status),
        event_sections_html=_render_event_sections(MVP_EVENTS, events, polymarket),
        scoring_html=scoring_html,
        event_nav_links=''.join(
            f'<a href="#event-{eid}">{eid}</a>' for eid in MVP_EVENTS if eid in events
        ),
        event_options=''.join(
            f'<option value="{eid}">{eid}</option>' for eid in MVP_EVENTS if eid in events
        ),
        source_options=''.join(
            f'<option value="{sid}">{sid}</option>' for sid in SOURCES
        ),
        source_colors_js=json.dumps(SOURCE_COLORS),
        chart_data_js=json.dumps(chart_data),
        predictions_js=json.dumps(all_preds),
    )

    output_path.write_text(html, encoding="utf-8")
    print(f"Factum Atlas rendered → {output_path}  ({output_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    data_dir = Path(os.environ.get("DATA_DIR", "/app/data"))
    root = data_dir.parent
    render(data_dir, root / "factum_atlas.html")
