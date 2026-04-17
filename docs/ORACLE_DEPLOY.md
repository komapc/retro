# Oracle API — Deploy

Zero-downtime deploy flow for the Oracle API on the retro EC2 box.

## Topology

One EC2 box, **two independent checkouts** of this repo:

| Path | Role | Git lifecycle |
|------|------|---------------|
| `/home/ubuntu/truthmachine/` | Pipeline worktree — ingest loop, orchestrator, atlas render | `ec2_run.sh` commits `data/progress.json` + `factum_atlas.html`, rebases on `origin/main`, pushes. May accumulate unpushed commits when rebase fails. |
| `/home/ubuntu/oracle-api/`   | Oracle API worktree — FastAPI service under `oracle-api.service` | Deploys `reset --hard` to `origin/main`. Never diverges. |

Both checkouts read the same `data/` directory — it lives in the pipeline's tree, and the API's `.env` points `DATA_DIR=/home/ubuntu/truthmachine/data` at it. Data is shared, **code is not**. This is what lets auto-deploy stay trivial: the deploy script never has to reason about the pipeline's work-in-progress commits because it only touches the API checkout.

## Deploy flow

`infra/deploy_oracle.sh` runs on the box and does:

1. `git fetch origin main` in `/home/ubuntu/oracle-api`
2. `git reset --hard <ref>` (defaults to `origin/main`, override with a SHA to pin)
3. `uv sync --frozen` in `api/`
4. `sudo systemctl reload oracle-api` — gunicorn SIGHUPs its workers, new code is imported into fresh workers, old workers drain gracefully. The listening socket on `:8001` is never closed, so there's no 502 window.
5. Poll `/health` until 200 (up to 10s).

No-op fast-path: if `git reset` produces the same SHA as before, the script skips `uv sync` and the reload entirely.

### Invocation

By hand:

```bash
ssh oracle-ec2
bash /home/ubuntu/oracle-api/infra/deploy_oracle.sh
```

From GitHub Actions (future Tier 4 workflow) via SSM `send-command`:

```yaml
- run: |
    aws ssm send-command \
      --instance-ids i-00ac444b94c5ff9b2 \
      --document-name AWS-RunShellScript \
      --parameters "commands=['sudo -u ubuntu bash /home/ubuntu/oracle-api/infra/deploy_oracle.sh ${{ github.sha }}']" \
      --comment "deploy oracle-api ${{ github.sha }}"
```

## Why the split?

Before this split, a single checkout at `/home/ubuntu/truthmachine/` served both roles. The pipeline's continuous `git commit` / `git rebase` / `git push` loop for atlas data meant:

- The working tree was never in sync with `origin/main` — there were always a few local WIP commits.
- Any `git pull --rebase` during deploy could fail, block, or (worse) interleave with an in-flight pipeline commit.
- A `git reset --hard` would silently nuke unpushed atlas/progress data the pipeline had just produced.

Separating the two checkouts removes the class of problem. The pipeline's messy branch state is now irrelevant to deploys.

## One-time migration (pipeline EC2, `i-00ac444b94c5ff9b2`)

Run on the box, once:

```bash
# 1. Create the API-only checkout next to the pipeline checkout.
cd /home/ubuntu
git clone https://github.com/komapc/retro.git oracle-api
cd oracle-api
git checkout main

# 2. Install deps for the API.
cd api
~/.local/bin/uv sync --frozen

# 3. Swap the systemd unit file to point at the new checkout.
sudo cp /home/ubuntu/oracle-api/infra/oracle-api.service /etc/systemd/system/oracle-api.service
sudo systemctl daemon-reload
sudo systemctl restart oracle-api   # one restart to pick up new WorkingDirectory

# 4. Verify.
curl -s http://127.0.0.1:8001/health
systemctl status oracle-api --no-pager | head -15
```

After this, every subsequent deploy is just `deploy_oracle.sh`, which only touches `/home/ubuntu/oracle-api/`.

## Rollback

To pin to a previous good SHA:

```bash
bash /home/ubuntu/oracle-api/infra/deploy_oracle.sh <prev-sha>
```

If the box is completely wedged, `sudo systemctl restart oracle-api` (2-5s 502 window) is the hard-reset escape hatch.
