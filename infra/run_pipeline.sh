#!/bin/bash
export PATH=/home/mark/.local/bin:/home/mark/.nvm/versions/node/v24.13.0/bin:/home/mark/.atuin/bin:/home/mark/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin:/snap/bin
cd ~/projects/retro

echo "=== PIPELINE START $(date) ==="

python3 -c "
import json, os
path = 'data/progress.json'
if not os.path.exists(path):
    with open(path, 'w') as f: json.dump({'cells': {}}, f)
with open(path) as f: state = json.load(f)
cells = state.get('cells', {})
n = sum(1 for v in cells.values() if v['status'] == 'no_predictions')
for v in cells.values():
    if v['status'] == 'no_predictions': v['status'] = 'pending'
with open(path, 'w') as f: json.dump({'cells': cells}, f)
print(f'Reset {n} cells to pending')
"

cd pipeline
echo '--- gnews ingest ---'
DATA_DIR=/home/ubuntu/projects/retro/data uv run python -m tm.gnews_ingest --force 2>&1
echo '--- orchestrator ---'
DATA_DIR=/home/ubuntu/projects/retro/data uv run python -m tm.orchestrator local_file 2>&1
echo '--- render atlas ---'
DATA_DIR=/home/ubuntu/projects/retro/data uv run python -m tm.render_atlas 2>&1
cd ..
echo '--- commit & push ---'
git add -A
git commit -m "atlas: pipeline run $(date +%Y-%m-%dT%H:%M)" && git push origin main || echo no_changes
echo "=== DONE $(date) ==="
