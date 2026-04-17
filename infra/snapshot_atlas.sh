#!/bin/bash
# snapshot_atlas.sh — back up expensive-to-regenerate pipeline state to S3.
#
# What's in the tarball:
#   - data/atlas/    (per-cell entry_*.json + cell_signal.json — the LLM output,
#                    already committed as factum_atlas.html but individual entries
#                    are the source of truth the render pulls from)
#   - data/vault2/   (raw articles + extracted predictions — what the LLM calls
#                    actually produced, expensive to regenerate)
#
# What's NOT in the tarball:
#   - data/raw_ingest/  (re-fetchable from GNews/DDG, and GNews caches upstream)
#   - data/pages/       (local scrape cache, disposable)
#   - data/events/      (tracked in git)
#   - data/sources/     (tracked in git)
#   - data/progress.json (tracked in git, committed each cycle)
#
# Called from ec2_run.sh at the tail of each cycle. Non-fatal on any failure —
# a bad snapshot should never break the pipeline, it should just skip.
#
# Usage:
#   bash infra/snapshot_atlas.sh
#
# Env overrides:
#   ATLAS_SNAPSHOT_BUCKET   (default: truthmachine-atlas-snapshots-272007598366)
#   AWS_REGION              (default: eu-central-1)
#   WORKDIR                 (default: $HOME/truthmachine)
#   DATA_DIR                (default: $WORKDIR/data)
set -eu  # not -o pipefail — dash compat; we handle errors explicitly below

BUCKET="${ATLAS_SNAPSHOT_BUCKET:-truthmachine-atlas-snapshots-272007598366}"
REGION="${AWS_REGION:-eu-central-1}"
WORKDIR="${WORKDIR:-$HOME/truthmachine}"
DATA_DIR="${DATA_DIR:-$WORKDIR/data}"

log() { echo "[snapshot_atlas $(date -u '+%H:%M:%S')] $*" >&2; }

# Skip if atlas dir has nothing worth saving — don't overwrite a healthy
# latest.tgz with an empty tarball if this cycle ran on a data-wiped box.
if [ ! -d "$DATA_DIR/atlas" ] || [ -z "$(find "$DATA_DIR/atlas" -name 'entry_*.json' 2>/dev/null | head -n1)" ]; then
  log "no atlas entries, skipping snapshot"
  exit 0
fi

TMPFILE=$(mktemp --suffix=.tgz)
trap 'rm -f "$TMPFILE"' EXIT

cd "$DATA_DIR"
# --warning=no-file-changed tolerates the pipeline writing new extractions
# mid-tar (active cycle). Without it, a concurrent write returns exit 1 from
# tar even though the tarball is fine.
if ! tar --warning=no-file-changed --warning=no-file-removed \
         -czf "$TMPFILE" atlas vault2 2>/dev/null; then
  rc=$?
  if [ "$rc" -ne 1 ]; then
    log "WARNING: tar failed with rc=$rc, skipping upload"
    exit 0
  fi
fi

SIZE=$(stat -c%s "$TMPFILE" 2>/dev/null || stat -f%z "$TMPFILE" 2>/dev/null || echo "?")
TS=$(date -u +%Y-%m-%dT%H-%M-%SZ)

# Upload per-cycle archive (30d retention via bucket lifecycle) first so even
# if latest.tgz update fails we have a point-in-time copy.
if ! aws s3 cp --region "$REGION" --only-show-errors "$TMPFILE" "s3://${BUCKET}/snapshots/${TS}.tgz"; then
  log "WARNING: snapshots/${TS}.tgz upload failed"
  exit 0
fi

# latest.tgz is the restore pointer. Bucket versioning retains prior versions
# for 7 days in case we ever need to rollback a bad snapshot.
if ! aws s3 cp --region "$REGION" --only-show-errors "$TMPFILE" "s3://${BUCKET}/latest.tgz"; then
  log "WARNING: latest.tgz upload failed (point-in-time snapshots/${TS}.tgz is still ok)"
  exit 0
fi

log "ok — ${SIZE}B to s3://${BUCKET}/ (latest.tgz + snapshots/${TS}.tgz)"
