import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional


class Scorer:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.atlas_dir = data_dir / "atlas"
        self.events_dir = data_dir / "events"
        self.sources_dir = data_dir / "sources"
        self.scores_path = data_dir / "leaderboard.json"

    # ─────────────────────────────────────────────
    # Core scoring primitives
    # ─────────────────────────────────────────────

    def calculate_brier(self, stance: float, outcome: bool) -> float:
        """Brier score for a single prediction."""
        prob = (stance + 1) / 2          # stance [-1,1] → prob [0,1]
        actual = 1.0 if outcome else 0.0
        return (prob - actual) ** 2

    def confidence_weight(self, certainty: float) -> float:
        """
        Higher certainty → higher weight when correct, higher penalty when wrong.
        Returns a multiplier in [0.5, 2.0] so low-certainty predictions still count.
        """
        certainty = max(0.0, min(1.0, certainty))
        return 0.5 + 1.5 * certainty

    def weighted_brier(self, stance: float, certainty: float, outcome: bool) -> float:
        """Confidence-weighted Brier score."""
        return self.calculate_brier(stance, outcome) * self.confidence_weight(certainty)

    # ─────────────────────────────────────────────
    # Stat buckets
    # ─────────────────────────────────────────────

    def _empty_bucket(self, name: str = "") -> dict:
        return {
            "name": name,
            "brier_total": 0.0,
            "weighted_brier_total": 0.0,
            "prediction_count": 0,
            "events_covered": 0,
            "elo": 1200.0,
        }

    # ─────────────────────────────────────────────
    # Main run
    # ─────────────────────────────────────────────

    def run(self):
        # global stats:  sid → bucket
        global_stats: Dict[str, dict] = {}
        # category stats: sid → category → bucket
        category_stats: Dict[str, Dict[str, dict]] = defaultdict(dict)

        # Initialise buckets for all sources
        for source_file in self.sources_dir.glob("*.json"):
            source = json.loads(source_file.read_text())
            sid = source["id"]
            global_stats[sid] = self._empty_bucket(source["name"])

        # Score every event
        for event_file in sorted(self.events_dir.glob("*.json")):
            event = json.loads(event_file.read_text())
            eid = event["id"]
            outcome = event["outcome"]
            categories: List[str] = event.get("category", [])

            atlas_event_dir = self.atlas_dir / eid
            if not atlas_event_dir.exists():
                continue

            event_predictions = []   # (sid, stance) for ELO update

            for source_dir in atlas_event_dir.iterdir():
                if not source_dir.is_dir():
                    continue
                sid = source_dir.name
                if sid not in global_stats:
                    continue

                entry_files = list(source_dir.glob("*.json"))
                if not entry_files:
                    continue

                # Ensure per-category buckets exist for this source
                for cat in categories:
                    if cat not in category_stats[sid]:
                        category_stats[sid][cat] = self._empty_bucket(
                            global_stats[sid]["name"]
                        )

                covered = False
                for entry_file in entry_files:
                    entry = json.loads(entry_file.read_text())
                    preds = entry.get("predictions", [])
                    if not preds:
                        continue

                    stances    = [p.get("stance", 0.0) for p in preds]
                    certainties = [p.get("certainty", 0.5) for p in preds]
                    avg_stance    = sum(stances) / len(stances)
                    avg_certainty = sum(certainties) / len(certainties)

                    b  = self.calculate_brier(avg_stance, outcome)
                    wb = self.weighted_brier(avg_stance, avg_certainty, outcome)

                    # Global bucket
                    global_stats[sid]["brier_total"]          += b
                    global_stats[sid]["weighted_brier_total"] += wb
                    global_stats[sid]["prediction_count"]     += 1

                    # Per-category buckets
                    for cat in categories:
                        category_stats[sid][cat]["brier_total"]          += b
                        category_stats[sid][cat]["weighted_brier_total"] += wb
                        category_stats[sid][cat]["prediction_count"]     += 1

                    event_predictions.append((sid, avg_stance))
                    covered = True

                if covered:
                    global_stats[sid]["events_covered"] += 1
                    for cat in categories:
                        category_stats[sid][cat]["events_covered"] += 1

            # ELO update (global only — per-category ELO can be added later)
            if len(event_predictions) > 1:
                self._update_elo(global_stats, event_predictions, outcome)

        # ── Build leaderboard ────────────────────
        leaderboard = []
        for sid, stats in global_stats.items():
            n = stats["prediction_count"]
            if n == 0:
                continue

            # Per-category scores for this source
            per_category = {}
            for cat, cstats in category_stats.get(sid, {}).items():
                cn = cstats["prediction_count"]
                if cn == 0:
                    continue
                per_category[cat] = {
                    "brier_score":          round(cstats["brier_total"] / cn, 4),
                    "weighted_brier_score": round(cstats["weighted_brier_total"] / cn, 4),
                    "predictions":          cn,
                    "events":               cstats["events_covered"],
                }

            leaderboard.append({
                "id":                   sid,
                "name":                 stats["name"],
                "brier_score":          round(stats["brier_total"] / n, 4),
                "weighted_brier_score": round(stats["weighted_brier_total"] / n, 4),
                "elo":                  round(stats["elo"], 0),
                "predictions":          n,
                "events":               stats["events_covered"],
                "by_category":          per_category,
            })

        leaderboard.sort(key=lambda x: x["elo"], reverse=True)

        self.scores_path.write_text(json.dumps(leaderboard, indent=2))
        print(f"Scoring complete. {len(leaderboard)} sources scored → {self.scores_path}")
        return leaderboard

    # ─────────────────────────────────────────────
    # ELO helper
    # ─────────────────────────────────────────────

    def _update_elo(self, stats: dict, predictions: list, outcome: bool, K: int = 32):
        """Zero-sum ELO adjustment: sources that predicted correctly gain from those that didn't."""
        for sid, stance in predictions:
            is_correct = (stance > 0) == outcome
            delta = K / len(predictions)
            stats[sid]["elo"] += delta if is_correct else -delta

    # Backwards-compat alias
    def update_elo(self, stats, predictions, outcome, K=32):
        self._update_elo(stats, predictions, outcome, K)


def main():
    import sys
    data_dir = Path("/app/data")
    if len(sys.argv) > 1:
        data_dir = Path(sys.argv[1])
    scorer = Scorer(data_dir)
    scorer.run()


if __name__ == "__main__":
    main()
