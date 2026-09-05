"""Build-independent Strategy E environment and path loading.

Shared credentials/data are authoritative when present. A package-local .env is
kept only as a backward-compatible fallback for old installations.
"""
from pathlib import Path
import os
from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parent
_DEFAULT_SECRETS_DIR = Path.home() / "Desktop" / "algo" / "kite_credentials"
_DEFAULT_DATA_DIR = Path.home() / "Desktop" / "algo" / "strategy_e_shared_data"


def _bootstrap_value(name: str, default: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    for candidate in (ROOT / ".env", _DEFAULT_SECRETS_DIR / ".env"):
        try:
            value = dotenv_values(candidate).get(name)
            if value:
                return str(value)
        except Exception:
            pass
    return default


SECRETS_DIR = Path(_bootstrap_value("STRATEGY_E_SECRETS_DIR", str(_DEFAULT_SECRETS_DIR))).expanduser()
DATA_DIR = Path(_bootstrap_value("STRATEGY_E_DATA_DIR", str(_DEFAULT_DATA_DIR))).expanduser()
PACKAGE_ENV_FILE = ROOT / ".env"
SHARED_ENV_FILE = SECRETS_DIR / ".env"

# Shared environment is authoritative. Package-local .env is a compatibility
# fallback only when a shared environment does not exist.
ENV_FILE = SHARED_ENV_FILE if SHARED_ENV_FILE.exists() else PACKAGE_ENV_FILE


def load_env():
    """Load the selected environment and make it authoritative for the process."""
    global ENV_FILE
    chosen = SHARED_ENV_FILE if SHARED_ENV_FILE.exists() else PACKAGE_ENV_FILE
    ENV_FILE = chosen
    if chosen.exists():
        load_dotenv(dotenv_path=chosen, override=True)
        return dotenv_values(chosen)
    return {}


load_env()


def ensure_shared_dirs() -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        SECRETS_DIR.chmod(0o700)
    except OSError:
        pass
    DATA_DIR.mkdir(parents=True, exist_ok=True)
