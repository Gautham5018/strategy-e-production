#!/bin/bash
set -euo pipefail
PLIST="$HOME/Library/LaunchAgents/com.strategyE.trading.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "Strategy E launchd service removed."
