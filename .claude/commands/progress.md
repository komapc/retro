Check the status of the Factum Atlas pipeline running on the EC2 server (openclaw-worker, ubuntu@63.182.142.184).

SSH into the server using `ssh -i ~/.ssh/daatan-key.pem -o StrictHostKeyChecking=no ubuntu@63.182.142.184` and run the following to report status:

1. Read `~/truthmachine/pipeline_log.txt` — extract the last 10 lines and identify the current event being processed (look for patterns like `C05/toi`, `B09/haaretz`, etc.)
2. Read `/home/ubuntu/truthmachine/data/progress.json` — count cells by status: done, no_predictions, failed, pending
3. Check if the systemd service is running: `systemctl --user status truthmachine.service 2>/dev/null || sudo systemctl status truthmachine.service 2>/dev/null`

Report back in this format:
- **Status:** running / finished / crashed
- **Current event:** (event/source being processed, or last one seen)
- **Cells:** X done | Y no_predictions | Z failed | W pending (total: N)
- **Last log lines:** (last 5 lines of pipeline_log.txt)
