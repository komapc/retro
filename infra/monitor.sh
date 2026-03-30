#!/bin/bash
# TruthMachine EC2 Monitor — full status dashboard
# Usage: bash infra/monitor.sh

INSTANCE="i-00ac444b94c5ff9b2"
REGION="eu-central-1"
WORKDIR="/home/ubuntu/truthmachine"

run_remote() {
  local CMD_ID
  CMD_ID=$(aws ssm send-command \
    --region "$REGION" \
    --instance-ids "$INSTANCE" \
    --document-name "AWS-RunShellScript" \
    --parameters "commands=[\"$1\"]" \
    --query "Command.CommandId" --output text 2>/dev/null)
  sleep 6
  aws ssm get-command-invocation \
    --region "$REGION" \
    --command-id "$CMD_ID" \
    --instance-id "$INSTANCE" \
    --query "StandardOutputContent" --output text 2>/dev/null
}

clear
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  TruthMachine Monitor  $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Instance: $INSTANCE ($REGION)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Service status ──────────────────────────────────────
echo ""
echo "  SERVICE"
run_remote "sudo systemctl is-active truthmachine && sudo systemctl show truthmachine --property=ActiveEnterTimestamp | cut -d= -f2" \
  | while read -r line; do echo "    $line"; done

# ── Cell progress ───────────────────────────────────────
echo ""
echo "  PROGRESS"
run_remote "python3 -c \"
import json
try:
    cells = json.load(open('$WORKDIR/data/progress.json')).get('cells', {})
    d  = sum(1 for v in cells.values() if v.get('status')=='done')
    n  = sum(1 for v in cells.values() if v.get('status')=='no_predictions')
    f  = sum(1 for v in cells.values() if v.get('status')=='failed')
    p  = sum(1 for v in cells.values() if v.get('status')=='pending')
    t  = len(cells)
    pct = int(100*d/t) if t else 0
    bar = '#'*pct + '.'*(100-pct)
    print(f'  done={d}  no_pred={n}  failed={f}  pending={p}  total={t}  ({pct}%)')
    print(f'  [{bar[:50]}] {pct}%')
except Exception as e:
    print('  no progress.json:', e)
\"" | while read -r line; do echo "  $line"; done

# ── Ingest counts ───────────────────────────────────────
echo ""
echo "  INGEST  (raw_ingest articles per source)"
run_remote "find $WORKDIR/data/raw_ingest -name 'article_*.json' 2>/dev/null | sed 's|.*/raw_ingest/||' | cut -d/ -f1 | sort | uniq -c | sort -rn | awk '{printf \"    %-20s %s\n\", \$2, \$1}'; echo \"    ---\"; echo \"    TOTAL: \$(find $WORKDIR/data/raw_ingest -name 'article_*.json' 2>/dev/null | wc -l)\"" \
  | while read -r line; do echo "$line"; done

# ── Last log lines ──────────────────────────────────────
echo ""
echo "  LOG (last 10 lines)"
run_remote "tail -10 $WORKDIR/pipeline_log.txt 2>/dev/null || echo 'no log yet'" \
  | while read -r line; do echo "    $line"; done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Other scripts:"
echo "    bash infra/logs.sh [tail|warn|grep <pattern>]"
echo "    bash infra/check_keys.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
