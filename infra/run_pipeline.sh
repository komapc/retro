#!/bin/bash
export PATH=/home/mark/.local/bin:/home/mark/.nvm/versions/node/v24.13.0/bin:/home/mark/.atuin/bin:/home/mark/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin:/snap/bin
cd ~/projects/retro

echo "=== PIPELINE START $(date) ==="

python3 -c "
import json
with open('data/progress.json') as f: state = json.load(f)
cells = state.get('cells', {})
n = sum(1 for v in cells.values() if v['status'] == 'no_predictions')
for v in cells.values():
    if v['status'] == 'no_predictions': v['status'] = 'pending'
with open('data/progress.json', 'w') as f: json.dump({'cells': cells}, f)
print(f'Reset {n} cells to pending')
"

cd pipeline
DATA_DIR=/home/ubuntu/projects/retro/data uv run python -m tm.gnews_ingest --force
DATA_DIR=/home/ubuntu/projects/retro/data uv run python -m tm.orchestrator local_file
DATA_DIR=/home/ubuntu/projects/retro/data uv run python -m tm.render_atlas
cd ..
git add -A
git commit -m "atlas: pipeline run $(date +%Y-%m-%dT%H:%M)" && git push origin main || echo no_changes
echo "=== DONE $(date) ==="
