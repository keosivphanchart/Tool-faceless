#!/usr/bin/env bash
# Daily trend-finder cron entry point.
# Crontab example (runs every day at 06:00):
#   0 6 * * * /path/to/repo/scripts/cron_trend_finder.sh >> /var/log/faceless_trends.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
python -m app.modules.trends.run
