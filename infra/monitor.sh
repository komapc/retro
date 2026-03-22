#!/bin/bash
# TruthMachine EC2 Monitor
# Usage: bash infra/monitor.sh

INSTANCE="i-0f1ba4900a0a7af14"
REGION="eu-central-1"
WORKDIR="/home/ubuntu/truthmachine"

run_remote() {
  local CMD_ID
  CMD_ID=$(aws ssm send-command \
    --region "$REGION" \
    --instance-ids "$INSTANCE" \
    --document-name "AWS-RunShellScript" \
    --parameters "$(printf '{"commands":["%s"]}' "$1")" \
    --query "Command.CommandId" --output text 2>/dev/null)
  sleep 7
  aws ssm get-command-invocation \
    --region "$REGION" \
    --command-id "$CMD_ID" \
    --instance-id "$INSTANCE" \
    --query "StandardOutputContent" --output text 2>/dev/null
}

clear
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  TruthMachine Monitor  $(date '+%Y-%m-%d %H:%M:%S')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Processes ──────────────────────────────────────────
echo ""
echo "  PROCESSES"
run_remote "ps aux | grep -E 'gnews_ingest|orchestrator|ec2_run|render_atlas' | grep -v grep | awk '{print \$8, \$11, \$12}' | sed 's|.*/tm/||'" \
  | while read -r line; do echo "    $line"; done

# ── Article ingest ─────────────────────────────────────
echo ""
echo "  INGEST  (raw_ingest/)"
run_remote "echo TOTAL:\$(find $WORKDIR/data/raw_ingest -name 'article_*.json' 2>/dev/null | wc -l); find $WORKDIR/data/raw_ingest -name 'article_*.json' 2>/dev/null | sed 's|.*/raw_ingest/||' | cut -d/ -f1 | sort | uniq -c | sort -rn" \
  | while read -r line; do echo "    $line"; done

# ── Extractions + cell progress ────────────────────────
echo ""
echo "  EXTRACTIONS"
run_remote "echo \"vault: \$(ls $WORKDIR/data/vault2/extractions/*.json 2>/dev/null | wc -l) files\"; python3 -c \"
import json
p = '$WORKDIR/data/progress.json'
try:
    cells = json.load(open(p)).get('cells', {})
    d = sum(1 for v in cells.values() if v.get('status')=='done')
    n = sum(1 for v in cells.values() if v.get('status')=='no_predictions')
    f = sum(1 for v in cells.values() if v.get('status')=='failed')
    p2 = sum(1 for v in cells.values() if v.get('status')=='pending')
    t = len(cells)
    pct = int(100*d/t) if t else 0
    print(f'cells:  done={d}  no_pred={n}  pending={p2}  failed={f}  total={t}  ({pct}%)')
except Exception as e:
    print('no progress.json yet')
\"" | while read -r line; do echo "    $line"; done

# ── Last log lines ─────────────────────────────────────
echo ""
echo "  LOG (last 8 lines)"
run_remote "tail -8 $WORKDIR/pipeline_log.txt 2>/dev/null || echo 'no log yet'" \
  | while read -r line; do echo "    $line"; done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
