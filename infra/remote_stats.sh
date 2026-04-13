#!/bin/bash
# Runs ON EC2 — called by monitor.sh via SSM.
# Outputs structured stats without complex quoting.

WORKDIR="/home/ubuntu/truthmachine"
PROG="$WORKDIR/data/progress.json"

echo "=== SERVICE ==="
systemctl is-active truthmachine 2>/dev/null || echo "unknown"

echo ""
echo "=== PROGRESS ==="
if [[ -f "$PROG" ]]; then
  python3 - "$PROG" <<'PY'
import json, sys
cells = json.load(open(sys.argv[1])).get("cells", {})
counts = {}
for v in cells.values():
    s = v.get("status", "unknown")
    counts[s] = counts.get(s, 0) + 1
total = len(cells)
done = counts.get("done", 0)
pct = int(100 * done / total) if total else 0
for status, n in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {status:<20} {n}")
print(f"  {'total':<20} {total}")
print(f"  {'done %':<20} {pct}%")
PY
else
  echo "  no progress.json"
fi

echo ""
echo "=== INGEST ==="
TOTAL=$(find "$WORKDIR/data/raw_ingest" -name 'article_*.json' 2>/dev/null | wc -l)
find "$WORKDIR/data/raw_ingest" -name 'article_*.json' 2>/dev/null \
  | sed 's|.*/raw_ingest/||' | cut -d/ -f1 \
  | sort | uniq -c | sort -rn \
  | awk '{printf "  %-20s %s\n", $2, $1}'
echo "  ----"
echo "  total                $TOTAL"

echo ""
echo "=== LOG (last 8) ==="
tail -8 "$WORKDIR/pipeline_log.txt" 2>/dev/null || echo "  no log"
