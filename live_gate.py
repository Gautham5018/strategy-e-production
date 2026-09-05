"""Independent fail-closed authorization gate. Never places orders."""
from dataclasses import dataclass
from config import SETTINGS

@dataclass(frozen=True)
class LiveGateResult:
    allowed: bool
    reasons: tuple[str,...]

REQUIRED_ACK="I_UNDERSTAND_LIVE_TRADING_RISK"

def evaluate(settings=None):
    s=settings or SETTINGS; reasons=[]
    if s.mode!="LIVE": reasons.append("MODE_NOT_LIVE")
    if not s.trading_enabled: reasons.append("TRADING_DISABLED")
    if not s.allow_live_orders: reasons.append("LIVE_ORDERS_NOT_ALLOWED")
    if not s.live_orders_armed: reasons.append("LIVE_ORDERS_NOT_ARMED")
    if s.kill_switch: reasons.append("KILL_SWITCH_ACTIVE")
    import os
    if os.getenv("LIVE_TRADING_ACK","").strip()!=REQUIRED_ACK: reasons.append("LIVE_TRADING_ACK_MISSING")
    if os.getenv("KITE_STATIC_IP_VERIFIED","false").strip().lower()!="true": reasons.append("KITE_STATIC_IP_NOT_VERIFIED")
    if os.getenv("PRODUCTION_ENVIRONMENT","").strip().upper()!="LOCAL_MAC": reasons.append("PRODUCTION_ENVIRONMENT_NOT_LOCAL_MAC")
    return LiveGateResult(not reasons,tuple(reasons))

def assert_live_allowed():
    r=evaluate(SETTINGS)
    if not r.allowed: raise RuntimeError("LIVE ORDER GATE BLOCKED: "+",".join(r.reasons))
    return True


def assert_live_exit_allowed():
    import os
    reasons=[]
    s=SETTINGS
    if s.mode!="LIVE": reasons.append("MODE_NOT_LIVE")
    if os.getenv("LIVE_TRADING_ACK","").strip()!=REQUIRED_ACK: reasons.append("LIVE_TRADING_ACK_MISSING")
    if os.getenv("KITE_STATIC_IP_VERIFIED","false").strip().lower()!="true": reasons.append("KITE_STATIC_IP_NOT_VERIFIED")
    if os.getenv("PRODUCTION_ENVIRONMENT","").strip().upper()!="LOCAL_MAC": reasons.append("PRODUCTION_ENVIRONMENT_NOT_LOCAL_MAC")
    if reasons: raise RuntimeError("LIVE EXIT GATE BLOCKED: "+",".join(reasons))
    return True
