#!/bin/zsh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export STRATEGY_E_SECRETS_DIR="${STRATEGY_E_SECRETS_DIR:-$HOME/Desktop/algo/kite_credentials}"
export STRATEGY_E_DATA_DIR="${STRATEGY_E_DATA_DIR:-$HOME/Desktop/algo/strategy_e_shared_data}"
printf 'Strategy E clean start\n'
printf 'Build root: %s\n' "$ROOT"
printf 'Shared secrets: %s\n' "$STRATEGY_E_SECRETS_DIR"
printf 'Shared data: %s\n' "$STRATEGY_E_DATA_DIR"
python3 "$ROOT/run.py" setup-shared
