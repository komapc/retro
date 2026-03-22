import json
from pathlib import Path
from typing import Dict, List
import math

class Scorer:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.atlas_dir = data_dir / "atlas"
        self.events_dir = data_dir / "events"
        self.sources_dir = data_dir / "sources"
        self.scores_path = data_dir / "leaderboard.json"

    def calculate_brier(self, stance: float, outcome: bool) -> float:
        # Map stance (-1 to 1) to probability (0 to 1)
        # Note: ML model will eventually do this, for now we use linear mapping
        prob = (stance + 1) / 2
        actual = 1.0 if outcome else 0.0
        return (prob - actual) ** 2

    def run(self):
        source_stats = {} # sid -> {brier_sum, count, elo}
        
        # Initialize ELO and Brier for all sources
        for source_file in self.sources_dir.glob("*.json"):
            with open(source_file, "r") as f:
                source = json.load(f)
            source_stats[source["id"]] = {
                "name": source["name"],
                "brier_total": 0.0,
                "prediction_count": 0,
                "elo": 1200.0,
                "events_covered": 0
            }

        # Iterate through events to update scores
        for event_file in self.events_dir.glob("*.json"):
            with open(event_file, "r") as f:
                event = json.load(f)
            
            eid = event["id"]
            outcome = event["outcome"]
            
            atlas_event_dir = self.atlas_dir / eid
            if not atlas_event_dir.exists():
                continue

            event_predictions = [] # List of (sid, stance)
            
            for source_dir in atlas_event_dir.iterdir():
                if not source_dir.is_dir():
                    continue
                
                sid = source_dir.name
                if sid not in source_stats:
                    continue

                # Get all predictions for this source/event
                for entry_file in source_dir.glob("*.json"):
                    with open(entry_file, "r") as f:
                        entry = json.load(f)
                    
                    preds = entry.get("predictions", [])
                    if not preds:
                        continue
                        
                    # Aggregate stance for this article (simple mean for MVP)
                    import numpy as np
                    avg_stance = float(np.mean([p.get("stance", 0) for p in preds]))
                    
                    brier = self.calculate_brier(avg_stance, outcome)
                    
                    source_stats[sid]["brier_total"] += brier
                    source_stats[sid]["prediction_count"] += 1
                    event_predictions.append((sid, avg_stance))
                
                if any(source_dir.glob("*.json")):
                    source_stats[sid]["events_covered"] += 1

            # Simple ELO-like relative update per event
            # Correct sources gain from incorrect ones
            if len(event_predictions) > 1:
                self.update_elo(source_stats, event_predictions, outcome)

        # Finalize averages
        leaderboard = []
        for sid, stats in source_stats.items():
            if stats["prediction_count"] > 0:
                stats["brier_score"] = stats["brier_total"] / stats["prediction_count"]
                leaderboard.append({
                    "id": sid,
                    "name": stats["name"],
                    "brier_score": round(stats["brier_score"], 4),
                    "elo": round(stats["elo"], 0),
                    "predictions": stats["prediction_count"],
                    "events": stats["events_covered"]
                })

        # Sort by ELO descending
        leaderboard.sort(key=lambda x: x["elo"], reverse=True)
        
        with open(self.scores_path, "w") as f:
            json.dump(leaderboard, f, indent=2)
        
        print(f"Scoring complete. Leaderboard saved to {self.scores_path}")

    def update_elo(self, stats, predictions, outcome, K=32):
        # Very simplified zero-sum adjustment for MVP
        for sid, stance in predictions:
            # Did they lean the right way?
            is_correct = (stance > 0) == outcome
            if is_correct:
                stats[sid]["elo"] += K / len(predictions)
            else:
                stats[sid]["elo"] -= K / len(predictions)

def main():
    import sys
    data_dir = Path("/app/data")
    if len(sys.argv) > 1:
        data_dir = Path(sys.argv[1])
    scorer = Scorer(data_dir)
    scorer.run()

if __name__ == "__main__":
    main()
