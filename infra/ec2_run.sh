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

# Ensure uv is on PATH (not set in non-interactive SSM shells)
export PATH="$HOME/.local/bin:$PATH"

WORKDIR="$HOME/truthmachine"
DATA_DIR="$WORKDIR/data"
PIPELINE_DIR="$WORKDIR/pipeline"
SLEEP_INTERVAL=300   # seconds between cycles (5 min — short pause to avoid hammering APIs)

# Load secrets
set -a; source "$WORKDIR/.env"; set +a
export DATA_DIR

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

cell_stats() {
  python3 - <<'PY'
import json, os
p = os.path.join(os.environ["DATA_DIR"], "progress.json")
try:
    s = json.load(open(p))
    cells = s.get("cells", {})
    done  = sum(1 for v in cells.values() if v.get("status") == "done")
    nopred= sum(1 for v in cells.values() if v.get("status") == "no_predictions")
    fail  = sum(1 for v in cells.values() if v.get("status") == "failed")
    pend  = sum(1 for v in cells.values() if v.get("status") == "pending")
    total = len(cells)
    print(f"{done}/{total} done | {nopred} no_pred | {fail} failed | {pend} pending")
except Exception:
    print("?/? (progress.json unreadable)")
PY
}

commit_and_push() {
  local msg="$1"
  cd "$WORKDIR"
  # Render latest atlas before committing
  uv run --project "$PIPELINE_DIR" python -m tm.render_atlas 2>&1 | tail -5
  STATS=$(cell_stats)
  git add factum_atlas.html data/progress.json 2>/dev/null || true
  if ! git diff --cached --quiet; then
    git commit -m "atlas: ${msg} — ${STATS}"
    git push origin main
    log "Pushed: ${msg} — ${STATS}"
  fi
}

run_pipeline() {
  cd "$WORKDIR"

  # ── 1. Pull latest event/source definitions ───────────────────────────────
  log "Pulling latest from main..."
  git fetch origin main
  git merge --ff-only origin/main || log "Already up to date"

  # ── 2. Ingest: fetch articles for pending cells ───────────────────────────
  log "Ingest starting — $(cell_stats)"
  uv run --project "$PIPELINE_DIR" python -m tm.gnews_ingest 2>&1
  log "Ingest complete — $(cell_stats)"

  # ── 3. Extract: run orchestrator in batches of 5 events, commit after each ─
  log "Extraction starting — $(cell_stats)"

  # Get all event IDs that have articles in raw_ingest
  EVENTS=$(python3 -c "
import os, pathlib
raw = pathlib.Path(os.environ['DATA_DIR']) / 'raw_ingest'
events = set()
if raw.exists():
    for src_dir in raw.iterdir():
        for evt_dir in src_dir.iterdir():
            if any(evt_dir.glob('*.json')):
                events.add(evt_dir.name)
print(' '.join(sorted(events)))
" 2>/dev/null)

  if [[ -z "$EVENTS" ]]; then
    log "No raw_ingest articles found — skipping orchestrator."
  else
    read -ra EVENT_ARR <<< "$EVENTS"
    TOTAL_EVENTS=${#EVENT_ARR[@]}
    log "Orchestrating ${TOTAL_EVENTS} events in batches of 5..."

    BATCH=0
    for (( i=0; i<TOTAL_EVENTS; i+=5 )); do
      BATCH=$((BATCH + 1))
      BATCH_EVENTS=("${EVENT_ARR[@]:i:5}")
      log "Batch ${BATCH}: events ${BATCH_EVENTS[*]}"

      uv run --project "$PIPELINE_DIR" python -m tm.orchestrator local_file \
        --events "${BATCH_EVENTS[@]}" 2>&1

      log "Batch ${BATCH} done — $(cell_stats)"
      commit_and_push "batch ${BATCH} (${BATCH_EVENTS[*]})"
    done
  fi

  log "Extraction complete — $(cell_stats)"
}

# ── Main loop ─────────────────────────────────────────────────────────────────
log "=== TruthMachine pipeline starting ==="
log "DATA_DIR=$DATA_DIR"
log "Cycle interval: ${SLEEP_INTERVAL}s (5 min)"

while true; do
  log "─── Cycle start ───────────────────────────────────"

  run_pipeline || log "ERROR: cycle failed, will retry next interval"

  log "─── Cycle done. Sleeping ${SLEEP_INTERVAL}s... ────"
  sleep "$SLEEP_INTERVAL"
done
