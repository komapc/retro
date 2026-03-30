#!/bin/bash
# TruthMachine log viewer
#
# Usage:
#   bash infra/logs.sh              — tail last 30 lines
#   bash infra/logs.sh tail [N]     — tail last N lines (default 30)
#   bash infra/logs.sh warn         — show warnings/errors only
#   bash infra/logs.sh progress     — show only progress lines (done | )
#   bash infra/logs.sh grep <pat>   — grep for pattern

INSTANCE="i-00ac444b94c5ff9b2"
REGION="eu-central-1"
LOG="/home/ubuntu/truthmachine/pipeline_log.txt"

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

MODE="${1:-tail}"
ARG="${2:-30}"

case "$MODE" in
  tail)
    echo "=== Last $ARG lines ==="
    run_remote "tail -$ARG $LOG 2>/dev/null"
    ;;
  warn|warnings)
    echo "=== Warnings & errors (aggregated) ==="
    run_remote "grep -iE 'warning|error|failed|quota|429|401|403|timeout' $LOG \
      | grep -v 'Slug → HTTP' \
      | sort | uniq -c | sort -rn | head -30"
    ;;
  progress)
    echo "=== Progress lines ==="
    run_remote "grep -E 'done \|' $LOG | tail -20"
    ;;
  grep)
    PAT="${ARG}"
    echo "=== grep: $PAT ==="
    run_remote "grep -E '$PAT' $LOG | tail -30"
    ;;
  *)
    echo "Usage: $0 [tail [N] | warn | progress | grep <pattern>]"
    exit 1
    ;;
esac
