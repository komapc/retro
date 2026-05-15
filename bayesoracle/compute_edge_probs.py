#!/usr/bin/env python3
"""
Compute empirical edge probabilities from price correlation, then blend with LLM estimates.

For each edge (A→B):
  - Load aligned daily price history for A and B
  - Linear regression: P_B = α + β·P_A
  - pY_corr = clip(α+β, 0.01, 0.99)  [predicted P_B when P_A=1]
  - pN_corr = clip(α,   0.01, 0.99)  [predicted P_B when P_A=0]
  - w_corr  = R² × 3.0

Blend:
  w_llm  = 1.0 (baseline)
  w_corr = R² × 3.0 (up-weighted when correlation is strong)
  pY_blend = (w_llm·pY_llm + w_corr·pY_corr) / (w_llm + w_corr)

Writes corr + blend fields back to bayesoracle/edge_weights.json.

Usage:
    cd /home/mark/projects/retro
    source pipeline/.venv/bin/activate
    python bayesoracle/compute_edge_probs.py
"""

import json
from pathlib import Path

import numpy as np
from scipy import stats

HISTORY_DIR  = Path(__file__).parent / "node_history"
WEIGHTS_FILE = Path(__file__).parent / "edge_weights.json"


# ─── Price history ────────────────────────────────────────────────────────────

def _load_prices(node_id: str) -> dict[str, float]:
    path = HISTORY_DIR / f"{node_id}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {pt["date"]: pt["probability"] for pt in data["prices"]}


def _align(pa: dict[str, float], pb: dict[str, float]) -> tuple[list[float], list[float]]:
    dates = sorted(pa.keys() & pb.keys())
    return [pa[d] for d in dates], [pb[d] for d in dates]


# ─── Correlation estimate ─────────────────────────────────────────────────────

def corr_estimate(src: str, tgt: str) -> dict:
    pa = _load_prices(src)
    pb = _load_prices(tgt)
    xa, xb = _align(pa, pb)
    n = len(xa)

    if n < 20:
        return {"pY_corr": None, "pN_corr": None, "r2_corr": 0.0, "n_corr": n}

    xa_arr = np.array(xa)
    xb_arr = np.array(xb)
    slope, intercept, r, _, _ = stats.linregress(xa_arr, xb_arr)
    r2 = r ** 2

    pY = float(np.clip(intercept + slope, 0.01, 0.99))
    pN = float(np.clip(intercept,         0.01, 0.99))

    # Binned sanity check
    hi_mask = xa_arr > 0.65
    lo_mask = xa_arr < 0.35
    pY_bin = float(xb_arr[hi_mask].mean()) if hi_mask.sum() >= 5 else None
    pN_bin = float(xb_arr[lo_mask].mean()) if lo_mask.sum() >= 5 else None

    return {
        "pY_corr": round(pY, 3),
        "pN_corr": round(pN, 3),
        "r2_corr": round(r2, 4),
        "n_corr":  n,
        "pY_bin":  round(pY_bin, 3) if pY_bin is not None else None,
        "pN_bin":  round(pN_bin, 3) if pN_bin is not None else None,
    }


# ─── Blend ───────────────────────────────────────────────────────────────────

def blend(pY_llm: float, pN_llm: float, corr: dict) -> dict:
    w_llm  = 1.0
    w_corr = (corr.get("r2_corr") or 0.0) * 3.0

    if corr.get("pY_corr") is not None and corr.get("pN_corr") is not None and w_corr > 0:
        total  = w_llm + w_corr
        pY_b   = (w_llm * pY_llm + w_corr * corr["pY_corr"]) / total
        pN_b   = (w_llm * pN_llm + w_corr * corr["pN_corr"]) / total
    else:
        total  = w_llm
        pY_b   = pY_llm
        pN_b   = pN_llm

    return {
        "pY_blend": round(float(np.clip(pY_b, 0.01, 0.99)), 3),
        "pN_blend": round(float(np.clip(pN_b, 0.01, 0.99)), 3),
        "w_llm":    round(w_llm,  3),
        "w_corr":   round(w_corr, 3),
    }


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    edges = json.loads(WEIGHTS_FILE.read_text())
    results = []

    for edge in edges:
        src, tgt = edge["source"], edge["target"]
        print(f"{src} → {tgt}")

        corr = corr_estimate(src, tgt)
        bl   = blend(edge["pY"], edge["pN"], corr)

        r2_str = f"R²={corr['r2_corr']:.3f}  n={corr['n_corr']}"
        print(f"  corr:  pY={corr['pY_corr']}  pN={corr['pN_corr']}  {r2_str}")
        print(f"  blend: pY={bl['pY_blend']}  pN={bl['pN_blend']}  "
              f"(w: llm={bl['w_llm']}  corr={bl['w_corr']:.2f})")

        # Drop old resolved/blend fields if present; write fresh
        clean = {k: v for k, v in edge.items()
                 if k not in {"pY_corr","pN_corr","r2_corr","n_corr","pY_bin","pN_bin",
                              "pY_resolved","pN_resolved","n_pairs","n_src","n_tgt",
                              "pY_blend","pN_blend","w_llm","w_corr","w_res"}}
        results.append({**clean, **corr, **bl})
        print()

    WEIGHTS_FILE.write_text(json.dumps(results, indent=2))
    print(f"Saved {len(results)} edges to {WEIGHTS_FILE}")

    high_r2 = [(r["source"], r["target"], r["r2_corr"]) for r in results if (r.get("r2_corr") or 0) > 0.15]
    if high_r2:
        print(f"\nEdges with R²>0.15:")
        for s, t, r2 in sorted(high_r2, key=lambda x: -x[2]):
            r = next(x for x in results if x["source"]==s and x["target"]==t)
            llm_dir  = "+" if r["pY"] > r["pN"] else "-"
            corr_dir = "+" if (r["pY_corr"] or 0) > (r["pN_corr"] or 0) else "-"
            flip = " ← DIRECTION FLIP" if llm_dir != corr_dir else ""
            print(f"  {s}→{t}: R²={r2:.3f}  LLM={llm_dir}  corr={corr_dir}{flip}")


if __name__ == "__main__":
    main()
