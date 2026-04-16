# TruthMachine / Factum Atlas — Status & Runbook

_Last updated: 2026-04-16_

---

## What Is This

TruthMachine is a retroactive media prediction pipeline. It:
1. **Ingests** news articles from 13 Israeli/international sources via GNews API
2. **Extracts** forward-looking predictions from each article using AWS Bedrock (LLM)
3. **Aggregates** predictions into a cell signal per (event × source) pair
4. **Renders** the Factum Atlas — an HTML matrix of prediction signals
5. **Publishes** the atlas to GitHub (`factum_atlas.html` on `main`)

The matrix has **840 cells** = 70 events × 13 sources (not all combinations have articles).

---

## Current State (2026-04-16)

| Metric | Value |
|--------|-------|
| EC2 instance | `i-00ac444b94c5ff9b2` (eu-central-1) |
| Instance type | t4g.small (ARM64, Ubuntu 24.04) |
| Batch pipeline service | `truthmachine.service` — **running** |
| Oracle API service | `oracle-api.service` — **running** |
| Cells done | 193 / 840 (23%) |
| Cells no_predictions | 647 |
| Cells failed | 0 |
| Cells pending | 0 |
| Cycle interval | 300s (5 min sleep between cycles) |

The matrix is fully processed — no pending or failed cells remain. The 77% "no predictions" rate reflects cells where no articles were found or the gatekeeper rejected all articles.

### Oracle API (oracle.daatan.com)

| Item | Status |
|------|--------|
| API skeleton (`api/`) | ✅ Merged |
| Test console | ✅ Live at [komapc.github.io/retro/oracle-test.html](https://komapc.github.io/retro/oracle-test.html) |
| Pipeline wired (web_search → gatekeeper → extractor → aggregate) | ✅ Complete |
| Leaderboard credibility weighting (TrueSkill) | ✅ Complete |
| EC2 deployment (`oracle-api.service`) | ✅ Running |
| DNS + TLS (`oracle.daatan.com`) | ✅ Live |
| nginx vhost (`infra/nginx/oracle.conf`) | ✅ Deployed |
| daatan secrets (`ORACLE_URL` + `ORACLE_API_KEY`) | 🔲 Pending |
| daatan bot integration | 🔲 Pending |

### Duel: TruthMachine vs Polymarket

| Item | Status |
|------|--------|
| Polymarket harvest pipeline (`polymarket_harvest.py`) | ✅ Complete |
| PoC event generation (`poc_event_gen.py`) | ✅ Complete |
| Duel report generator (`poc_report.py`) | ✅ Complete |
| `duel.html` generated and deployed to GitHub Pages | ✅ Live |
| TM vs PM Brier comparison section | 🔲 Placeholder (TM predictions not yet wired into duel) |

### Why is it sleeping?

`ec2_run.sh` always sleeps 300s after each cycle — even when pending cells remain. It only skips sleep when there are `failed` cells. This is a known inefficiency (see Future Fixes below).

---

## Architecture

```
ec2_run.sh (systemd loop)
  ├── 1. git pull origin main          (pick up code/config updates)
  ├── 2. gnews_ingest (batch of 10 events)
  │       └── GNews API → DDG fallback → Wayback fallback
  │           → raw_ingest/{source}/{event}/article_*.json
  ├── 3. orchestrator local_file (batches of 5 events)
  │       └── for each article:
  │           ├── Gatekeeper (Nova Micro) → is_prediction?
  │           ├── Extractor (Nova Lite) → PredictionExtraction × N
  │           ├── Article aggregator (Nova Lite) → 1 signal if spread > 0.4
  │           └── → vault2/extractions/{hash}_{event}_v1.json
  │               → atlas/{event}/{source}/entry_{hash[:8]}.json
  ├── 4. render_atlas → factum_atlas.html
  └── 5. git commit + push factum_atlas.html
```

**Models:**
- Gatekeeper: `bedrock/amazon.nova-micro-v1:0` (us-east-1)
- Extractor: `bedrock/amazon.nova-lite-v1:0` (us-east-1)
- Article aggregator: `bedrock/amazon.nova-lite-v1:0`

---

## Pipeline Stages

### Stage 1: Gatekeeper
- Uses first ~2500 chars of article
- Returns `is_prediction: bool`
- Skips article if False → cell marked `no_predictions`

### Stage 2: Extractor
- Extracts up to 10 `PredictionExtraction` objects per article
- Fields: quote, claim, stance (−1 to +1), sentiment, certainty, specificity, hedge_ratio, conditionality, magnitude, time_horizon, prediction_type, source_authority

### Stage 2b: Article Aggregator (new, 2026-03-28)
- Triggered when a single article produces predictions with stance spread > 0.4
- Collapses N predictions into 1 using editorial judgment (not averaging)
- Prompt: `TruthMachine/prompts/02b_article_aggregator.md`
- Script for post-processing: `pipeline/src/tm/reaggregate.py`

### Stage 3: Cell Signal
- Aggregates all predictions across all articles for one (event, source) cell
- Weighted mean (weight = certainty × specificity) for continuous fields
- Majority vote for categorical fields
- Written to `atlas/{event}/{source}/cell_signal.json`

---

## Failed Attempts & Issues Encountered

### 1. OpenRouter monthly quota exceeded
- **Symptom:** 403 errors on all LLM calls
- **Fix:** Switched to AWS Bedrock Nova models

### 2. `instructor.Mode.TOOLS` not supported by Bedrock
- **Symptom:** All LLM calls failed with tool-use errors
- **Fix:** Switched to `instructor.Mode.MD_JSON`

### 3. Nova Lite JSON object mode returns `<thinking>` tags
- **Symptom:** JSON parsing failed due to reasoning preamble
- **Fix:** MD_JSON mode strips markdown code blocks correctly

### 4. `KeyError: '"predictions"'` in extractor prompt
- **Symptom:** `PROMPT.format()` interpreted `{"predictions": [...]}` as a format placeholder
- **Fix:** Escaped to `{{"predictions": [...]}}`

### 5. `boto3` missing from uv venv on EC2
- **Symptom:** All LLM calls failed with `No module named 'boto3'`; cells silently marked `no_predictions` instead of `failed`
- **Root cause:** `uv sync` during bootstrap ran before venv was created (no `.venv` dir); `uv pip install` requires `--system` or an active venv
- **Fix:** `uv pip install boto3 botocore -p .venv/bin/python3` directly into the existing venv
- **Silent failure bug:** `runner.py` marks cell `failed` on exception, but `orchestrator.py` overwrites to `no_predictions` if no predictions found — hides the real error

### 6. EC2 bootstrap fails silently on secrets fetch
- **Symptom:** Bootstrap exits after `[bootstrap] Fetching secrets...` with no error
- **Root cause 1:** IAM role not propagated yet when bootstrap ran (takes ~60s)
- **Root cause 2:** `get_secret()` uses `2>/dev/null`; `set -e` exits on empty return without logging
- **Fix:** Added `|| true` to all `get_secret` calls; also `chmod 644` on `.env` (was 600, systemd runs as root)

### 7. `.env` permission denied
- **Symptom:** Service crashes immediately with `permission denied` on `.env`
- **Root cause:** Setup script ran as root via SSM, `.env` owned by root; `chmod 600` prevents ubuntu user from reading
- **Fix:** `chmod 644 /home/ubuntu/truthmachine/.env`

### 8. Git "dubious ownership" on EC2
- **Symptom:** `git fetch` fails; pipeline can't pull code updates
- **Root cause:** Repo cloned as ubuntu but SSM runs commands as root → git sees ownership mismatch
- **Fix:** `git config --global --add safe.directory /home/ubuntu/truthmachine` for ubuntu user; `chown -R ubuntu:ubuntu ~/truthmachine`

### 9. EC2 overwrites `factum_atlas.html` with empty atlas
- **Symptom:** Atlas page went blank after EC2 started pushing
- **Root cause:** EC2 started fresh with no atlas data; `commit_and_push` always renders and commits, even with 0 done cells
- **Partial fix:** Atlas data from local machine uploaded to EC2 via S3 tarball
- **Proper fix needed:** Only commit `factum_atlas.html` when `done > 0` (see Future Fixes)

### 10. DDG / Brave ingest failures
- **Symptom:** ~60–70% of article URL resolution fails
- **Root cause:** Brave API quota exhausted (402); DDG rate-limits heavily (connection errors)
- **Status:** Articles still get ingested — the ones that resolve are enough to fill the atlas gradually
- **Potential fix:** Add SerpAPI or Serper.dev as fallback; refresh Brave quota

---

## Future Fixes (Priority Order)

### High Priority

1. **Skip sleep when pending cells exist**
   - Change `ec2_run.sh`: only sleep if `pending == 0`
   - Currently wastes 5 min after every cycle even when work remains

2. **Fix silent `no_predictions` masking failures**
   - In `orchestrator.py`: don't overwrite `failed` status with `no_predictions`
   - Or: check `has_predictions` only if no runner errors occurred

3. **Don't commit empty atlas**
   - In `commit_and_push()`: skip commit when `done == 0`
   - Prevents overwriting good atlas data with empty render on fresh EC2

4. **Fix boto3 in bootstrap**
   - `ec2_bootstrap.sh`: after `uv sync`, explicitly verify `import boto3` works
   - If not: `uv pip install boto3 botocore -p pipeline/.venv/bin/python3`

### Medium Priority

5. **Refresh Brave API quota or add SerpAPI fallback**
   - Brave is quota-exhausted (402 on every call)
   - Add `openclaw/serpapi-key` or `openclaw/serperdev-key` to Secrets Manager

6. **Persist atlas data on EC2 across restarts**
   - Currently: if EC2 restarts, all vault/atlas data is lost (not in git)
   - Option A: commit `data/atlas/` and `data/progress.json` to git (small enough)
   - Option B: sync to S3 on each cycle, restore on startup

7. **Reduce sleep interval or make it adaptive**
   - `SLEEP_INTERVAL=60` would be more responsive
   - Or: skip sleep entirely when ingest found new articles

### Low Priority

8. **Article-level aggregation on full re-run**
   - The `reaggregate.py` script fixed 81 local entries
   - EC2 will re-aggregate inline during extraction (already wired in orchestrator)
   - No action needed unless we re-use local data

9. **Ground truth scoring**
   - `pipeline/src/tm/backtest.py` — not yet run on EC2
   - Requires resolved events with known outcomes

---

## Monitoring

```bash
# Quick status via SSM
bash /home/mark/projects/retro/infra/monitor.sh

# Live log tail
aws ssm send-command --region eu-central-1 \
  --instance-ids i-00ac444b94c5ff9b2 \
  --document-name AWS-RunShellScript \
  --parameters 'commands=["tail -30 ~/truthmachine/pipeline_log.txt"]'

# Git log (EC2 commits progress here)
cd /home/mark/projects/retro && git fetch && git log --oneline -10
```

---

## Instance Details

| Field | Value |
|-------|-------|
| Instance ID | `i-00ac444b94c5ff9b2` |
| Region | `eu-central-1` |
| AMI | Ubuntu 24.04 LTS arm64 |
| Type | t4g.small |
| IAM Role | `truthmachine-ec2-role` |
| Permissions | SSM + Bedrock (Nova) + Secrets Manager (`openclaw/*`) |
| Workdir | `/home/ubuntu/truthmachine/` |
| Service | `systemctl status truthmachine` |
| Log | `/home/ubuntu/truthmachine/pipeline_log.txt` |
| Access | AWS SSM only (port 22 blocked) |
