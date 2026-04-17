#!/bin/bash
# restore_atlas.sh — pull the most recent atlas+vault2 snapshot from S3.
#
# Called from ec2_bootstrap.sh between data-dir creation and service start,
# so a replaced EC2 instance can resume with prior state instead of starting
# the 910-cell matrix from scratch.
#
# Safety: NEVER clobbers an already-populated atlas. If data/atlas/ has any
# entry_*.json files, restore is a no-op. This means running this script on
# a healthy box is harmless.
#
# Also a no-op if the S3 snapshot doesn't exist (fresh account). Pipeline
# will just start from empty — atlas will populate on the first cycle.
#
# Usage:
#   bash infra/restore_atlas.sh
#
# Env overrides: see snapshot_atlas.sh
set -eu

BUCKET="${ATLAS_SNAPSHOT_BUCKET:-truthmachine-atlas-snapshots-272007598366}"
REGION="${AWS_REGION:-eu-central-1}"
WORKDIR="${WORKDIR:-$HOME/truthmachine}"
DATA_DIR="${DATA_DIR:-$WORKDIR/data}"

log() { echo "[restore_atlas $(date -u '+%H:%M:%S')] $*" >&2; }

# Safety: never overwrite a populated state
if [ -d "$DATA_DIR/atlas" ] && [ -n "$(find "$DATA_DIR/atlas" -name 'entry_*.json' 2>/dev/null | head -n1)" ]; then
  log "atlas already populated, skipping restore"
  exit 0
fi

# Check if snapshot exists; aws s3 ls returns non-zero if object missing
if ! aws s3 ls --region "$REGION" "s3://${BUCKET}/latest.tgz" >/dev/null 2>&1; then
  log "no s3://${BUCKET}/latest.tgz found, starting with empty atlas"
  exit 0
fi

TMPFILE=$(mktemp --suffix=.tgz)
trap 'rm -f "$TMPFILE"' EXIT

log "downloading latest.tgz..."
if ! aws s3 cp --region "$REGION" --only-show-errors "s3://${BUCKET}/latest.tgz" "$TMPFILE"; then
  log "WARNING: download failed, starting with empty atlas"
  exit 0
fi

SIZE=$(stat -c%s "$TMPFILE" 2>/dev/null || stat -f%z "$TMPFILE" 2>/dev/null || echo "?")
log "downloaded ${SIZE}B"

mkdir -p "$DATA_DIR"
cd "$DATA_DIR"
if ! tar -xzf "$TMPFILE"; then
  log "WARNING: tar extract failed, atlas may be partial — pipeline will reconcile"
  exit 0
fi

atlas_count=$(find atlas -name 'entry_*.json' 2>/dev/null | wc -l)
vault_count=$(find vault2/extractions -name '*.json' 2>/dev/null | wc -l)
log "ok — restored ${atlas_count} atlas entries, ${vault_count} vault extractions"
