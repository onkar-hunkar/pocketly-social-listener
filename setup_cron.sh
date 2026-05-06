#!/usr/bin/env bash
# Sets up a weekly cron job to run the Pocketly Social Listener every Monday at 8 AM.
# Run this once: bash setup_cron.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(which python3)"
LOG="$SCRIPT_DIR/cron.log"

# The cron line: every Monday at 08:00
CRON_JOB="0 8 * * 1 cd \"$SCRIPT_DIR\" && source .venv/bin/activate && $PYTHON main.py --skip-quora >> \"$LOG\" 2>&1 && $PYTHON build_dashboard.py >> \"$LOG\" 2>&1"

# Add only if not already present
if crontab -l 2>/dev/null | grep -qF "pocketly-social-listener"; then
    echo "✓ Cron job already exists — no changes made."
else
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✓ Cron job installed: every Monday at 08:00"
    echo "  Script: $SCRIPT_DIR/main.py"
    echo "  Log:    $LOG"
fi

echo ""
echo "Current crontab:"
crontab -l
