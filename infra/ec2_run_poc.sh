#!/bin/bash
# TruthMachine PoC Run Loop
# Runs the "beat Polymarket" PoC pipeline alongside the main atlas pipeline.
#
# Phase 1: fetch-prices pass on harvested events (Polymarket price history)
# Phase 2: generate event JSONs via Nova Micro (poc_event_gen.py)
# Phase 3: ingest articles for PoC events (gnews_ingest with DATA_DIR=data/poc)
# Phase 4: extract predictions (orchestrator with DATA_DIR=data/poc)
#
# Data durability:
#   git  — events.jsonl, events.tar.gz, progress.json, duel.html
#   S3   — raw_ingest/, atlas/ (bulk intermediate data)
#
# Usage (systemd manages this via truthmachine-poc.service):
#   sudo systemctl start truthmachine-poc
#   sudo journalctl -fu truthmachine-poc
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

WORKDIR="$HOME/truthmachine"
POC_DIR="$WORKDIR/data/poc"
PIPELINE_DIR="$WORKDIR/pipeline"
SLEEP_INTERVAL=600   # 10 min between full cycles
S3_BUCKET="s3://daatan-db-backups-staging-272007598366/poc"

# Load secrets
set -a; source "$WORKDIR/.env"; set +a

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [poc] $*"; }

export POC_DIR

poc_cell_stats() {
  python3 - <<'PY'
import json, os
from pathlib import Path
poc = Path(os.environ.get("POC_DIR", "/home/ubuntu/truthmachine/data/poc"))
p = poc / "progress.json"
try:
    cells = json.loads(p.read_text()).get("cells", {})
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

# Commit lightweight PoC outputs to git (events.jsonl, events.tar.gz, progress.json)
commit_poc_data() {
  local msg="$1"
  cd "$WORKDIR"

  # Pack event JSONs directory into a single tarball (18k files → 1 git object)
  if [[ -d "$POC_DIR/events" ]] && [[ "$(ls -A "$POC_DIR/events" 2>/dev/null)" ]]; then
    tar -czf "$POC_DIR/events.tar.gz" -C "$POC_DIR" events/
    log "Packed $(ls "$POC_DIR/events/" | wc -l) event JSONs → events.tar.gz"
  fi

  git add \
    "data/poc/pm_harvest/events.jsonl" \
    "data/poc/events.tar.gz" \
    "data/poc/progress.json" \
    2>/dev/null || true

  if ! git diff --cached --quiet; then
    STATS=$(poc_cell_stats)
    git commit -m "poc: ${msg} — ${STATS}"
    git fetch origin main
    git rebase origin/main || { git rebase --abort; log "WARNING: rebase failed, skipping push"; return 0; }
    git push origin main
    log "Pushed poc data: ${msg}"
  else
    log "No poc data changes to commit."
  fi
}

# Sync bulk intermediate data to S3
s3_sync_poc() {
  log "Syncing raw_ingest/ and atlas/ to S3..."
  if [[ -d "$POC_DIR/raw_ingest" ]]; then
    aws s3 sync "$POC_DIR/raw_ingest/" "$S3_BUCKET/raw_ingest/" \
      --quiet --no-progress 2>&1 | tail -3 || log "WARNING: S3 sync raw_ingest failed"
  fi
  if [[ -d "$POC_DIR/atlas" ]]; then
    aws s3 sync "$POC_DIR/atlas/" "$S3_BUCKET/atlas/" \
      --quiet --no-progress 2>&1 | tail -3 || log "WARNING: S3 sync atlas failed"
  fi
  log "S3 sync complete."
}

run_poc_cycle() {
  cd "$WORKDIR"

  # ── Pull latest code ──────────────────────────────────────────────────────
  log "Pulling latest from main..."
  git fetch origin main 2>&1 | tail -2
  git rebase --autostash origin/main 2>&1 | tail -3 || { git rebase --abort; log "WARNING: rebase failed, continuing with current code"; }

  # ── Phase 1: Fetch Polymarket price history for events missing prices ─────
  # First: backfill clob_token_yes from cached raw pages (no-op if all events already have it)
  NO_TOKEN=$(python3 -c "
import json
from pathlib import Path
p = Path('$POC_DIR/pm_harvest/events.jsonl')
if not p.exists():
    print(0)
else:
    def bad_token(e):
        t = e.get('clob_token_yes')
        return not t or len(str(t)) <= 10
    n = sum(1 for line in p.read_text().splitlines() if line.strip() and bad_token(json.loads(line)))
    print(n)
" 2>/dev/null || echo 0)

  if [[ "$NO_TOKEN" -gt 0 ]]; then
    log "Backfilling CLOB tokens for $NO_TOKEN events from cached raw pages..."
    DATA_DIR="$POC_DIR" uv run --project "$PIPELINE_DIR" \
      python -m tm.polymarket_harvest --data-dir "$POC_DIR" --backfill-clob-tokens 2>&1 | tail -5
  fi

  NEED_PRICES=$(python3 -c "
import json
from pathlib import Path
p = Path('$POC_DIR/pm_harvest/events.jsonl')
if not p.exists():
    print(0)
else:
    n = sum(1 for line in p.read_text().splitlines() if line.strip() and not json.loads(line).get('prices_fetched', False))
    print(n)
" 2>/dev/null || echo 0)

  if [[ "$NEED_PRICES" -gt 0 ]]; then
    log "Fetching prices for $NEED_PRICES events via CLOB API..."
    DATA_DIR="$POC_DIR" uv run --project "$PIPELINE_DIR" \
      python -m tm.polymarket_harvest --data-dir "$POC_DIR" --fetch-prices 2>&1 | tail -10
    log "Price fetch complete — regenerating duel.html..."
    DATA_DIR="$POC_DIR" uv run --project "$PIPELINE_DIR" \
      python -m tm.poc_report --data-dir "$POC_DIR" --out "$WORKDIR/duel.html" 2>&1 | tail -3
    git add "$WORKDIR/duel.html" 2>/dev/null || true
    # Commit updated events.jsonl + duel.html (now has price history + calibration)
    commit_poc_data "price fetch complete ($NEED_PRICES events had no prices)"
  else
    log "All events have price history — skipping price fetch."
  fi

  # ── Phase 2: Generate event JSONs for new harvested events ───────────────
  HARVESTED=$(python3 -c "from pathlib import Path; p=Path('$POC_DIR/pm_harvest/events.jsonl'); print(sum(1 for _ in p.open()) if p.exists() else 0)" 2>/dev/null || echo 0)
  GENERATED=$(python3 -c "from pathlib import Path; p=Path('$POC_DIR/events'); print(sum(1 for _ in p.glob('*.json')) if p.exists() else 0)" 2>/dev/null || echo 0)
  log "Harvested: $HARVESTED events, $GENERATED event JSONs generated"

  if [[ "$GENERATED" -lt "$HARVESTED" ]]; then
    log "Generating event JSONs ($(( HARVESTED - GENERATED )) new)..."
    DATA_DIR="$POC_DIR" uv run --project "$PIPELINE_DIR" \
      python -m tm.poc_event_gen --data-dir "$POC_DIR" --batch-size 50 2>&1 | tail -10
    GENERATED=$(ls "$POC_DIR/events/" 2>/dev/null | wc -l || echo 0)
    log "Event JSONs: $GENERATED total"
    # Commit events.tar.gz
    commit_poc_data "event JSONs generated ($GENERATED total)"
  fi

  # ── Phase 3: Ingest articles (batch of 50 qualified PoC events per cycle) ──
  log "Starting PoC ingest — $(poc_cell_stats)"

  # Option 5: only ingest events with >5 Polymarket price points (meaningful markets)
  ALL_POC_EVENTS=$(python3 -c "
import json, pathlib
harvest = pathlib.Path('$POC_DIR/pm_harvest/events.jsonl')
events_dir = pathlib.Path('$POC_DIR/events')
# Build set of pm_ids with >5 price points
qualified_ids = set()
if harvest.exists():
    for line in harvest.read_text().splitlines():
        if not line.strip(): continue
        ev = json.loads(line)
        # Use event_id format from poc_event_gen: pm + first 8 alphanum chars of pm_id
        import re
        safe = re.sub(r'[^a-zA-Z0-9]', '', str(ev['pm_id']))[:8]
        event_id = f'pm{safe}'
        if len(ev.get('prices') or []) > 5:
            qualified_ids.add(event_id)
# Return only qualified event IDs that have a JSON file
result = sorted(p.stem for p in events_dir.glob('*.json') if p.stem in qualified_ids)
print(' '.join(result))
" 2>/dev/null)

  if [[ -z "$ALL_POC_EVENTS" ]]; then
    log "No qualified PoC events yet — skipping ingest."
    return
  fi

  read -ra ALL_ARR <<< "$ALL_POC_EVENTS"
  TOTAL_ALL=${#ALL_ARR[@]}
  BATCH_SIZE=50
  OFFSET_FILE="$POC_DIR/ingest_offset"
  OFFSET=$(cat "$OFFSET_FILE" 2>/dev/null || echo 0)
  OFFSET=$(( OFFSET % TOTAL_ALL ))
  INGEST_EVENTS=("${ALL_ARR[@]:OFFSET:BATCH_SIZE}")
  REMAINING=$(( BATCH_SIZE - ${#INGEST_EVENTS[@]} ))
  if [[ $REMAINING -gt 0 ]]; then
    INGEST_EVENTS+=("${ALL_ARR[@]:0:REMAINING}")
  fi
  NEW_OFFSET=$(( (OFFSET + BATCH_SIZE) % TOTAL_ALL ))
  echo "$NEW_OFFSET" > "$OFFSET_FILE"

  log "Ingesting PoC events (offset $OFFSET/$TOTAL_ALL qualified): ${INGEST_EVENTS[*]:0:5}..."
  DATA_DIR="$POC_DIR" uv run --project "$PIPELINE_DIR" \
    python -m tm.gnews_ingest --events "${INGEST_EVENTS[@]}" --max-concurrent 5 2>&1 | tail -10
  log "PoC ingest done — $(poc_cell_stats)"

  # ── Phase 4: Extract predictions for PoC events with articles ────────────
  log "Starting PoC extraction — $(poc_cell_stats)"
  POC_EVENTS_WITH_ARTICLES=$(python3 -c "
import os, pathlib
raw = pathlib.Path('$POC_DIR/raw_ingest')
events = set()
if raw.exists():
    for src_dir in raw.iterdir():
        for evt_dir in src_dir.iterdir():
            if any(evt_dir.glob('*.json')):
                events.add(evt_dir.name)
print(' '.join(sorted(events)))
" 2>/dev/null)

  if [[ -z "$POC_EVENTS_WITH_ARTICLES" ]]; then
    log "No PoC articles ingested yet — skipping extraction."
    return
  fi

  read -ra EVENT_ARR <<< "$POC_EVENTS_WITH_ARTICLES"
  TOTAL_EVENTS=${#EVENT_ARR[@]}
  log "Orchestrating $TOTAL_EVENTS PoC events in batches of 3..."

  BATCH=0
  for (( i=0; i<TOTAL_EVENTS; i+=3 )); do
    BATCH=$((BATCH + 1))
    BATCH_EVENTS=("${EVENT_ARR[@]:i:3}")
    log "PoC batch $BATCH: ${BATCH_EVENTS[*]}"
    timeout 600 env DATA_DIR="$POC_DIR" uv run --project "$PIPELINE_DIR" \
      python -m tm.orchestrator local_file --events "${BATCH_EVENTS[@]}" 2>&1 | tail -5 \
      || log "WARNING: PoC batch $BATCH timed out — continuing"
  done

  log "PoC extraction complete — $(poc_cell_stats)"

  # ── Render duel.html and commit ──────────────────────────────────────────
  log "Rendering duel.html..."
  DATA_DIR="$POC_DIR" uv run --project "$PIPELINE_DIR" \
    python -m tm.poc_report --data-dir "$POC_DIR" --out "$WORKDIR/duel.html" 2>&1 | tail -3
  git add "$WORKDIR/duel.html" 2>/dev/null || true

  # ── Commit progress + sync bulk data to S3 ───────────────────────────────
  commit_poc_data "batch $(date '+%Y-%m-%d %H:%M')"
  s3_sync_poc
}

# ── Main loop ──────────────────────────────────────────────────────────────
log "=== TruthMachine PoC pipeline starting ==="
log "POC_DIR=$POC_DIR"
log "S3_BUCKET=$S3_BUCKET"
log "Cycle interval: ${SLEEP_INTERVAL}s"

while true; do
  log "─── PoC cycle start ────────────────────────────────"
  run_poc_cycle || log "ERROR: PoC cycle failed, retrying next interval"
  log "─── PoC cycle done. Sleeping ${SLEEP_INTERVAL}s... ─"
  sleep "$SLEEP_INTERVAL"
done
