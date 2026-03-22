#!/bin/bash
# TruthMachine EC2 Run Loop
# Continuously ingests articles, extracts predictions, renders atlas, and pushes to GitHub.
#
# Usage:
#   nohup bash ~/truthmachine/infra/ec2_run.sh >> ~/truthmachine/pipeline_log.txt 2>&1 &
#   echo $! > ~/truthmachine/run.pid
#
# Monitor:  tail -f ~/truthmachine/pipeline_log.txt
# Stop:     kill $(cat ~/truthmachine/run.pid)
set -euo pipefail

WORKDIR="$HOME/truthmachine"
DATA_DIR="$WORKDIR/data"
PIPELINE_DIR="$WORKDIR/pipeline"
SLEEP_INTERVAL=3600  # seconds between cycles (1 hour)

# Load secrets
set -a; source "$WORKDIR/.env"; set +a
export DATA_DIR

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

run_pipeline() {
  cd "$WORKDIR"

  # ── 1. Pull latest event/source definitions ───────────────────────────────
  log "Pulling latest from main..."
  git fetch origin main
  # Only fast-forward — never overwrite local data dirs
  git merge --ff-only origin/main || log "Already up to date"

  # ── 2. Ingest: fetch articles for pending cells ───────────────────────────
  log "Running gnews_ingest..."
  uv run --project "$PIPELINE_DIR" python -m tm.gnews_ingest 2>&1 | tail -30
  log "Ingest complete."

  # ── 3. Extract: run orchestrator on all pending cells ─────────────────────
  log "Running orchestrator (local_file mode)..."
  uv run --project "$PIPELINE_DIR" python -m tm.orchestrator local_file 2>&1 | tail -40
  log "Extraction complete."

  # ── 4. Render atlas HTML ──────────────────────────────────────────────────
  log "Rendering atlas..."
  uv run --project "$PIPELINE_DIR" python -m tm.render_atlas
  log "Atlas rendered."

  # ── 5. Push if atlas changed ──────────────────────────────────────────────
  if ! git diff --quiet factum_atlas.html 2>/dev/null; then
    # Count completed cells for commit message
    DONE=$(python3 - <<'PY'
import json, os
p = os.path.join(os.environ["DATA_DIR"], "progress.json")
try:
    s = json.load(open(p))
    cells = s.get("cells", {})
    done = sum(1 for v in cells.values() if v.get("status") == "done")
    total = len(cells)
    print(f"{done}/{total}")
except Exception:
    print("?/?")
PY
)
    git add factum_atlas.html
    git commit -m "atlas: ${DONE} cells complete"
    git push origin main
    log "Pushed atlas — ${DONE} cells done. GitHub Actions deploying to Pages."
  else
    log "No changes to atlas, skipping push."
  fi
}

# ── Main loop ─────────────────────────────────────────────────────────────────
log "=== TruthMachine pipeline starting ==="
log "DATA_DIR=$DATA_DIR"
log "Cycle interval: ${SLEEP_INTERVAL}s"

while true; do
  log "─── Cycle start ───────────────────────────────────"

  run_pipeline || log "ERROR: cycle failed, will retry next interval"

  log "─── Cycle done. Sleeping ${SLEEP_INTERVAL}s... ────"
  sleep "$SLEEP_INTERVAL"
done
