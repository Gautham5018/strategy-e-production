"""Shared persistent paths for build-independent Strategy E state/data."""
from pathlib import Path
from env_loader import SECRETS_DIR, DATA_DIR

KITE_ENV_FILE = SECRETS_DIR / ".env"
KITE_ACCESS_TOKEN_FILE = SECRETS_DIR / ".kite_access_token"
SHARED_UNIVERSE_DIR = DATA_DIR / "universe"
FEATURE_CACHE_DIR = DATA_DIR / "live_feature_cache"
ONE_MINUTE_CACHE_DIR = DATA_DIR / "live_1m_cache"
BACKTEST_OHLC_DIR = DATA_DIR / "backtest_ohlc"
STATE_DIR = DATA_DIR / "state"
LOG_DIR = DATA_DIR / "logs"


def ensure_dirs() -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        SECRETS_DIR.chmod(0o700)
    except OSError:
        pass
    for p in (DATA_DIR, SHARED_UNIVERSE_DIR, FEATURE_CACHE_DIR, ONE_MINUTE_CACHE_DIR, BACKTEST_OHLC_DIR, STATE_DIR, LOG_DIR):
        p.mkdir(parents=True, exist_ok=True)
