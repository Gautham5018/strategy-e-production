from pathlib import Path
from dataclasses import dataclass
from datetime import time
from env_loader import ENV_FILE, SECRETS_DIR, DATA_DIR, load_env

APP_TIMEZONE = "Asia/Kolkata"
ROOT = Path(__file__).resolve().parent
# env_loader selects package-local .env when present, otherwise the shared environment.
load_env()

def _bool(name: str, default: bool=False) -> bool:
    return str(__import__("os").getenv(name, str(default))).strip().lower() in {"1","true","yes","on"}

def _time(name: str, default: str) -> time:
    return time.fromisoformat(str(__import__("os").getenv(name, default)).strip())

def _path(name: str, default: Path) -> str:
    raw = str(__import__("os").getenv(name, str(default))).strip()
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = Path(default.parent) / p
    return str(p)

@dataclass(frozen=True)
class Settings:
    mode: str = __import__("os").getenv("MODE", "PAPER").upper()
    port: int = int(__import__("os").getenv("PORT", "8081"))
    bind_host: str = __import__("os").getenv("BIND_HOST", "127.0.0.1")

    total_capital: float = float(__import__("os").getenv("TOTAL_CAPITAL", "70000"))
    trade_capital_per_position: float = float(__import__("os").getenv("TRADE_CAPITAL_PER_POSITION", "35000"))
    mis_leverage: float = float(__import__("os").getenv("MIS_LEVERAGE", "5"))
    max_open_positions: int = int(__import__("os").getenv("MAX_OPEN_POSITIONS", "2"))
    max_entries_per_day: int = int(__import__("os").getenv("MAX_ENTRIES_PER_DAY", "2"))

    partial_r_fraction: float = float(__import__("os").getenv("PARTIAL_R_FRACTION", "0.50"))
    final_r_multiple: float = float(__import__("os").getenv("FINAL_R_MULTIPLE", "3.0"))
    post_partial_time_stop_minutes: int = int(__import__("os").getenv("POST_PARTIAL_TIME_STOP_MINUTES", "90"))
    post_partial_stagnation_pct: float = float(__import__("os").getenv("POST_PARTIAL_STAGNATION_PCT", "0.20"))

    # New profit-protection controls. Defaults are enabled in V6.5.
    trailing_stop_enabled: bool = _bool("TRAILING_STOP_ENABLED", True)
    trailing_activate_after_partial: bool = _bool("TRAILING_ACTIVATE_AFTER_PARTIAL", True)
    trailing_lock_r: float = float(__import__("os").getenv("TRAILING_LOCK_R", "0.50"))
    trailing_distance_r: float = float(__import__("os").getenv("TRAILING_DISTANCE_R", "1.00"))
    portfolio_profit_target_enabled: bool = _bool("PORTFOLIO_PROFIT_TARGET_ENABLED", True)
    portfolio_profit_target_inr: float = float(__import__("os").getenv("PORTFOLIO_PROFIT_TARGET_INR", "4500"))
    portfolio_profit_target_min_positions: int = int(__import__("os").getenv("PORTFOLIO_PROFIT_TARGET_MIN_POSITIONS", "2"))
    portfolio_profit_trailing_enabled: bool = _bool("PORTFOLIO_PROFIT_TRAILING_ENABLED", True)
    portfolio_profit_trailing_distance_inr: float = float(__import__("os").getenv("PORTFOLIO_PROFIT_TRAILING_DISTANCE_INR", "1000"))
    daily_loss_limit_enabled: bool = _bool("DAILY_LOSS_LIMIT_ENABLED", True)
    daily_loss_limit_inr: float = float(__import__("os").getenv("DAILY_LOSS_LIMIT_INR", "7000"))
    daily_profit_lock_enabled: bool = _bool("DAILY_PROFIT_LOCK_ENABLED", True)
    daily_profit_lock_inr: float = float(__import__("os").getenv("DAILY_PROFIT_LOCK_INR", "6000"))
    max_consecutive_losses: int = int(__import__("os").getenv("MAX_CONSECUTIVE_LOSSES", "2"))
    max_entry_risk_pct: float = float(__import__("os").getenv("MAX_ENTRY_RISK_PCT", "2.0"))
    risk_based_sizing_enabled: bool = _bool("RISK_BASED_SIZING_ENABLED", False)
    risk_per_trade_inr: float = float(__import__("os").getenv("RISK_PER_TRADE_INR", "1750"))
    break_even_enabled: bool = _bool("BREAK_EVEN_ENABLED", True)
    break_even_activate_r: float = float(__import__("os").getenv("BREAK_EVEN_ACTIVATE_R", "0.80"))
    break_even_lock_r: float = float(__import__("os").getenv("BREAK_EVEN_LOCK_R", "0.00"))
    feature_gate_mode: str = __import__("os").getenv("FEATURE_GATE_MODE", "SHADOW").upper()
    feature_score_threshold: float = float(__import__("os").getenv("FEATURE_SCORE_THRESHOLD", "65"))
    feature_trade2_score_threshold: float = float(__import__("os").getenv("FEATURE_TRADE2_SCORE_THRESHOLD", "75"))
    feature_min_bars: int = int(__import__("os").getenv("FEATURE_MIN_BARS", "30"))
    feature_min_adx: float = float(__import__("os").getenv("FEATURE_MIN_ADX", "18"))
    feature_min_relative_volume: float = float(__import__("os").getenv("FEATURE_MIN_RELATIVE_VOLUME", "1.0"))
    feature_min_atr_pct: float = float(__import__("os").getenv("FEATURE_MIN_ATR_PCT", "0.20"))
    feature_max_atr_pct: float = float(__import__("os").getenv("FEATURE_MAX_ATR_PCT", "4.0"))
    market_regime_filter: bool = _bool("MARKET_REGIME_FILTER", True)
    feature_universe_file: str = _path("FEATURE_UNIVERSE_FILE", DATA_DIR / "universe" / "feature_universe.txt")
    feature_cache_dir: str = _path("FEATURE_CACHE_DIR", DATA_DIR / "live_feature_cache")
    one_minute_cache_dir: str = _path("ONE_MINUTE_CACHE_DIR", DATA_DIR / "live_1m_cache")
    universe_sync_enabled: bool = _bool("UNIVERSE_SYNC_ENABLED", True)
    ohlc_initial_history_days: int = int(__import__("os").getenv("OHLC_INITIAL_HISTORY_DAYS", "90"))
    market_regime_symbol: str = __import__("os").getenv("MARKET_REGIME_SYMBOL", "NIFTY 50").upper()
    # V7.4 delayed-entry controls: Chartink signal becomes a setup, not an immediate buy.
    delayed_entry_enabled: bool = _bool("DELAYED_ENTRY_ENABLED", True)
    delayed_entry_mode: str = __import__("os").getenv("DELAYED_ENTRY_MODE", "PULLBACK_BOS").upper()
    delayed_entry_wait_minutes: int = int(__import__("os").getenv("DELAYED_ENTRY_WAIT_MINUTES", "20"))
    fib_min: float = float(__import__("os").getenv("FIB_RETRACE_MIN", "0.50"))
    fib_max: float = float(__import__("os").getenv("FIB_RETRACE_MAX", "0.618"))
    fib_ema_tolerance_pct: float = float(__import__("os").getenv("FIB_EMA_TOLERANCE_PCT", "0.25"))
    entry_zone_tolerance_pct: float = float(__import__("os").getenv("ENTRY_ZONE_TOLERANCE_PCT", "0.15"))
    delayed_entry_allow_continuation: bool = _bool("DELAYED_ENTRY_ALLOW_CONTINUATION", True)

    trading_start: time = _time("TRADING_START", "09:15")
    trading_end: time = _time("TRADING_END", "15:00")
    first_signal_cutoff: time = _time("FIRST_SIGNAL_CUTOFF", "09:35")
    max_signal_candle_pct: float = float(__import__("os").getenv("MAX_SIGNAL_CANDLE_PCT", "8.0"))

    entry_order_type: str = __import__("os").getenv("ENTRY_ORDER_TYPE", "MARKET").upper()
    market_protection: float = float(__import__("os").getenv("MARKET_PROTECTION", "-1"))
    product: str = __import__("os").getenv("PRODUCT", "MIS").upper()
    exchange: str = __import__("os").getenv("EXCHANGE", "NSE").upper()
    validity: str = __import__("os").getenv("VALIDITY", "DAY").upper()
    order_timeout_seconds: int = int(__import__("os").getenv("ORDER_TIMEOUT_SECONDS", "8"))
    reconcile_interval_seconds: int = int(__import__("os").getenv("RECONCILE_INTERVAL_SECONDS", "5"))
    ltp_stale_seconds: int = int(__import__("os").getenv("LTP_STALE_SECONDS", "5"))

    trading_enabled: bool = _bool("TRADING_ENABLED")
    allow_live_orders: bool = _bool("ALLOW_LIVE_ORDERS")
    kill_switch: bool = _bool("KILL_SWITCH")
    startup_reconcile_required: bool = _bool("STARTUP_RECONCILE_REQUIRED", True)
    flatten_on_fatal_error: bool = _bool("FLATTEN_ON_FATAL_ERROR")

    chartink_webhook_token: str = __import__("os").getenv("CHARTINK_WEBHOOK_TOKEN", "").strip()
    kite_api_key: str = __import__("os").getenv("KITE_API_KEY", "").strip()
    kite_api_secret: str = __import__("os").getenv("KITE_API_SECRET", "").strip()
    kite_access_token: str = __import__("os").getenv("KITE_ACCESS_TOKEN", "").strip()
    kite_access_token_file: str = _path("KITE_ACCESS_TOKEN_FILE", SECRETS_DIR / ".kite_access_token")
    kite_redirect_url: str = __import__("os").getenv("KITE_REDIRECT_URL", "").strip()
    admin_token: str = __import__("os").getenv("ADMIN_TOKEN", "").strip()

    @property
    def live_orders_armed(self) -> bool:
        return self.mode == "LIVE" and self.trading_enabled and self.allow_live_orders and not self.kill_switch

SETTINGS = Settings()

def validate_settings() -> list[str]:
    s=SETTINGS; errors=[]
    if s.mode not in {"PAPER","LIVE"}: errors.append("MODE must be PAPER or LIVE")
    if s.total_capital <= 0: errors.append("TOTAL_CAPITAL must be > 0")
    if s.trade_capital_per_position <= 0: errors.append("TRADE_CAPITAL_PER_POSITION must be > 0")
    if abs(s.trade_capital_per_position * s.max_open_positions - s.total_capital) > 0.01: errors.append("TRADE_CAPITAL_PER_POSITION * MAX_OPEN_POSITIONS must equal TOTAL_CAPITAL")
    if s.mis_leverage <= 0: errors.append("MIS_LEVERAGE must be > 0")
    if s.max_open_positions != 2: errors.append("Production Strategy E requires MAX_OPEN_POSITIONS=2")
    if s.max_entries_per_day < 1 or s.max_entries_per_day > 2: errors.append("Production Strategy E max entries/day must be 1 or 2")
    if not 0 < s.partial_r_fraction <= 1: errors.append("PARTIAL_R_FRACTION must be in (0,1]")
    if s.final_r_multiple <= 1: errors.append("FINAL_R_MULTIPLE must be > 1")
    if s.post_partial_time_stop_minutes < 1: errors.append("POST_PARTIAL_TIME_STOP_MINUTES must be >= 1")
    if s.post_partial_stagnation_pct < 0: errors.append("POST_PARTIAL_STAGNATION_PCT must be >= 0")
    if s.trailing_lock_r < 0: errors.append("TRAILING_LOCK_R must be >= 0")
    if s.trailing_distance_r <= 0: errors.append("TRAILING_DISTANCE_R must be > 0")
    if s.portfolio_profit_target_min_positions < 2 or s.portfolio_profit_target_min_positions > s.max_open_positions:
        errors.append("PORTFOLIO_PROFIT_TARGET_MIN_POSITIONS must be 2..MAX_OPEN_POSITIONS")
    if s.portfolio_profit_target_inr <= 0: errors.append("PORTFOLIO_PROFIT_TARGET_INR must be > 0")
    if s.portfolio_profit_trailing_distance_inr <= 0: errors.append("PORTFOLIO_PROFIT_TRAILING_DISTANCE_INR must be > 0")
    if s.daily_loss_limit_enabled and s.daily_loss_limit_inr <= 0: errors.append("DAILY_LOSS_LIMIT_INR must be > 0")
    if s.daily_profit_lock_enabled and s.daily_profit_lock_inr <= 0: errors.append("DAILY_PROFIT_LOCK_INR must be > 0")
    if s.max_consecutive_losses < 1: errors.append("MAX_CONSECUTIVE_LOSSES must be >= 1")
    if s.max_entry_risk_pct <= 0: errors.append("MAX_ENTRY_RISK_PCT must be > 0")
    if s.risk_based_sizing_enabled and s.risk_per_trade_inr <= 0: errors.append("RISK_PER_TRADE_INR must be > 0")
    if s.break_even_activate_r <= 0: errors.append("BREAK_EVEN_ACTIVATE_R must be > 0")
    if s.break_even_lock_r < 0: errors.append("BREAK_EVEN_LOCK_R must be >= 0")
    if s.feature_gate_mode not in {"SHADOW","ENFORCE","OFF"}: errors.append("FEATURE_GATE_MODE must be SHADOW, ENFORCE or OFF")
    if s.feature_score_threshold < 0 or s.feature_score_threshold > 100: errors.append("FEATURE_SCORE_THRESHOLD must be 0..100")
    if s.feature_trade2_score_threshold < s.feature_score_threshold or s.feature_trade2_score_threshold > 100: errors.append("FEATURE_TRADE2_SCORE_THRESHOLD must be >= FEATURE_SCORE_THRESHOLD and <=100")
    if s.delayed_entry_mode not in {"PULLBACK_BOS","CONTINUATION_BOS","ADAPTIVE"}: errors.append("DELAYED_ENTRY_MODE must be PULLBACK_BOS, CONTINUATION_BOS or ADAPTIVE")
    if s.delayed_entry_wait_minutes < 1 or s.delayed_entry_wait_minutes > 60: errors.append("DELAYED_ENTRY_WAIT_MINUTES must be 1..60")
    if not 0 < s.fib_min < s.fib_max < 1: errors.append("FIB_RETRACE_MIN/MAX invalid")
    if s.fib_ema_tolerance_pct < 0 or s.entry_zone_tolerance_pct < 0: errors.append("Fib/entry tolerance must be >= 0")
    if s.trading_start >= s.trading_end: errors.append("Trading window invalid")
    if s.entry_order_type != "MARKET": errors.append("Only MARKET entry is implemented")
    if s.product != "MIS": errors.append("Production Strategy E is restricted to MIS")
    if s.exchange != "NSE": errors.append("Production Strategy E is restricted to NSE")
    if not s.chartink_webhook_token: errors.append("CHARTINK_WEBHOOK_TOKEN is required")
    if s.mode == "LIVE" and (not s.kite_api_key or not s.kite_api_secret): errors.append("KITE_API_KEY and KITE_API_SECRET are required in LIVE")
    if not s.admin_token and s.mode == "LIVE": errors.append("ADMIN_TOKEN is required in LIVE")
    return errors
