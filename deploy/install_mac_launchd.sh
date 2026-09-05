#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(id -un)"
VENV_PY="$ROOT/.venv/bin/python"
PLIST="$HOME/Library/LaunchAgents/com.strategyE.trading.plist"

if [[ ! -x "$VENV_PY" ]]; then
  echo "ERROR: $VENV_PY not found."
  echo "Create/activate the project virtualenv first."
  exit 1
fi

mkdir -p "$ROOT/logs" "$HOME/Library/LaunchAgents"

python3 - "$ROOT" "$PLIST" "$VENV_PY" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
plist=Path(sys.argv[2])
venv_py=sys.argv[3]
text=(root/"deploy/com.strategyE.trading.plist.template").read_text()
text=text.replace("/Users/YOUR_USER/strategy_e_production_v6", str(root))
text=text.replace("/Users/YOUR_USER", str(Path.home()))
text=text.replace("/Users/YOUR_USER/strategy_e_production_v6/.venv/bin/python", venv_py)
plist.write_text(text)
PY

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/com.strategyE.trading"
launchctl kickstart -k "gui/$(id -u)/com.strategyE.trading"

echo "Installed: $PLIST"
echo "Status:"
launchctl print "gui/$(id -u)/com.strategyE.trading" | head -40
