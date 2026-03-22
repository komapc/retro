#!/bin/bash
# TruthMachine EC2 Bootstrap — run once on a fresh instance.
# Access via SSM: aws ssm start-session --target <instance-id> --region eu-central-1
set -euo pipefail

REGION="eu-central-1"
REPO="https://github.com/komapc/retro.git"
WORKDIR="$HOME/truthmachine"

log() { echo "[bootstrap] $*"; }

# ── 1. System dependencies ────────────────────────────────────────────────────
log "Installing system packages..."
sudo apt-get update -q
sudo apt-get install -y git curl python3-pip python3-venv jq

# Install uv (fast Python package manager)
if ! command -v uv &>/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
fi
log "uv $(uv --version)"

# ── 2. Pull secrets from AWS Secrets Manager ─────────────────────────────────
log "Fetching secrets..."
get_secret() {
  aws secretsmanager get-secret-value \
    --secret-id "$1" --region "$REGION" \
    --query SecretString --output text 2>/dev/null
}

OPENROUTER_KEY=$(get_secret "openclaw/openrouter-api-key")
BRAVE_KEY=$(get_secret "openclaw/brave-api-key")
GH_TOKEN=$(get_secret "openclaw/github-pat")

if [[ -z "$OPENROUTER_KEY" ]]; then
  echo "ERROR: openclaw/openrouter-api-key not found in Secrets Manager" >&2
  exit 1
fi
if [[ -z "$GH_TOKEN" ]]; then
  echo "ERROR: openclaw/github-pat not found in Secrets Manager" >&2
  echo "Create it: aws secretsmanager create-secret --name openclaw/github-pat --secret-string ghp_..." >&2
  exit 1
fi

# ── 3. Clone repository ───────────────────────────────────────────────────────
log "Cloning repo..."
mkdir -p "$WORKDIR"

# Use token-authenticated URL so the run loop can push
AUTHED_REPO="https://x-token:${GH_TOKEN}@github.com/komapc/retro.git"

if [[ -d "$WORKDIR/.git" ]]; then
  log "Repo already cloned, pulling latest..."
  git -C "$WORKDIR" remote set-url origin "$AUTHED_REPO"
  git -C "$WORKDIR" pull --ff-only origin main
else
  git clone "$AUTHED_REPO" "$WORKDIR"
fi

# Git identity for commits from this machine
git -C "$WORKDIR" config user.email "pipeline@truthmachine"
git -C "$WORKDIR" config user.name "TruthMachine EC2"

# ── 4. Write .env file ────────────────────────────────────────────────────────
log "Writing .env..."
cat > "$WORKDIR/.env" <<EOF
OPENROUTER_API_KEY=${OPENROUTER_KEY}
BRAVE_API_KEY=${BRAVE_KEY}
EOF
chmod 600 "$WORKDIR/.env"

# ── 5. Install Python dependencies ───────────────────────────────────────────
log "Installing Python dependencies..."
uv sync --project "$WORKDIR/pipeline"

# ── 6. Create data directories ────────────────────────────────────────────────
mkdir -p "$WORKDIR/data/events" \
         "$WORKDIR/data/sources" \
         "$WORKDIR/data/raw_ingest" \
         "$WORKDIR/data/vault2/articles" \
         "$WORKDIR/data/vault2/extractions" \
         "$WORKDIR/data/atlas"

# ── 7. Install systemd service ────────────────────────────────────────────────
log "Installing systemd service..."
sudo cp "$WORKDIR/infra/truthmachine.service" /etc/systemd/system/truthmachine.service
sudo systemctl daemon-reload
sudo systemctl enable truthmachine
sudo systemctl start truthmachine
log "Service status: $(sudo systemctl is-active truthmachine)"

log "Bootstrap complete."
log "Monitor: sudo journalctl -u truthmachine -f"
log "Or:      tail -f $WORKDIR/pipeline_log.txt"
