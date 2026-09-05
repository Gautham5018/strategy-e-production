from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import hashlib,json,time,threading
from fastapi import APIRouter,HTTPException,Request
from config import SETTINGS
from models import Signal
from logging_setup import logger
from universe_manager import enroll

router=APIRouter(); PROCESSOR=None; IST=ZoneInfo("Asia/Kolkata"); _warm_locks={}; _warm_lock=threading.RLock()

def set_processor(processor):
    global PROCESSOR; PROCESSOR=processor

def _latest_completed_candle_time(now=None):
    now=now or datetime.now(IST); now=now.replace(tzinfo=None); minute=(now.minute//5)*5; current=now.replace(minute=minute,second=0,microsecond=0); return current-timedelta(minutes=5)

def parse_chartink(payload):
    cols=payload.get("columns") or []
    if not isinstance(cols,list) or not cols: raise ValueError("columns missing")
    signal_time=_latest_completed_candle_time(datetime.now(IST)); signals=[]
    for c in cols:
        symbol=str(c.get("symbol","")).strip().upper()
        if not symbol: continue
        try: vals={k:float(c[k]) for k in ("open","high","low","close")}
        except Exception as exc: raise ValueError(f"{symbol}: invalid OHLC: {exc}") from exc
        signals.append(Signal(symbol=symbol,signal_time=signal_time,signal_open=vals["open"],signal_high=vals["high"],signal_low=vals["low"],signal_close=vals["close"]))
    if not signals: raise ValueError("No valid symbols")
    return signals

def _webhook_id(payload):
    raw=json.dumps(payload,sort_keys=True,separators=(",",":")); candle=_latest_completed_candle_time(datetime.now(IST)).isoformat(); return hashlib.sha256((candle+"|"+raw).encode()).hexdigest()

def _schedule_background_warm(broker, symbol):
    """Warm missing OHLC outside the signal execution path; never blocks the webhook."""
    from backtest.incremental_ohlc import update_symbol
    from config import SETTINGS
    s=symbol.upper()
    with _warm_lock:
        if _warm_locks.get(s):
            return
        _warm_locks[s]=True
    def job():
        try:
            result=update_symbol(broker,s,SETTINGS.feature_cache_dir,SETTINGS.ohlc_initial_history_days)
            logger.info("BACKGROUND OHLC WARM COMPLETE symbol=%s mode=%s added=%s total=%s",s,result.get("mode"),result.get("downloaded"),result.get("rows"))
        except Exception:
            logger.exception("BACKGROUND OHLC WARM FAILED symbol=%s",s)
        finally:
            with _warm_lock:
                _warm_locks.pop(s,None)
    threading.Thread(target=job,daemon=True,name=f"ohlc-warm-{s}").start()

@router.post("/chartink/webhook/{token}")
async def chartink_webhook(token:str,request:Request):
    if not SETTINGS.chartink_webhook_token or not hashlib.sha256(token.encode()).hexdigest()==hashlib.sha256(SETTINGS.chartink_webhook_token.encode()).hexdigest(): raise HTTPException(404,"Not found")
    processor_ready = True if PROCESSOR is None else getattr(PROCESSOR, "ready_for_webhook", lambda: True)()
    if PROCESSOR is None or not processor_ready:
        logger.warning("Webhook rejected: processor not ready")
        raise HTTPException(503,"Execution processor not ready")
    try: payload=await request.json()
    except Exception as exc: raise HTTPException(400,f"Invalid JSON: {exc}") from exc
    webhook_id=_webhook_id(payload)
    if PROCESSOR.store.processed(webhook_id):
        logger.info("Duplicate webhook ignored id=%s",webhook_id); return {"accepted_for_processing":False,"duplicate":True,"webhook_id":webhook_id}
    try: signals=parse_chartink(payload)
    except ValueError as exc: logger.warning("Webhook payload rejected: %s",exc); raise HTTPException(400,str(exc)) from exc
    for signal in signals:
        signal.webhook_id=webhook_id
        try:
            broker=getattr(PROCESSOR,"broker",None)
            if broker is not None:
                # Validate against the cached NSE instruments table. app.py preloads
                # instruments at startup, so this is a local lookup in normal operation.
                broker.instrument(signal.symbol)
                _schedule_background_warm(broker, signal.symbol)
            enroll(signal.symbol)
        except Exception as exc:
            logger.warning("DYNAMIC UNIVERSE ENROLL/VALIDATION FAILED symbol=%s: %s", signal.symbol, exc)
    try:
        started=time.perf_counter(); results=PROCESSOR.execution.process_signals(signals); elapsed_ms=(time.perf_counter()-started)*1000.0
        PROCESSOR.store.mark_processed(webhook_id); logger.info("Webhook processed id=%s elapsed_ms=%.2f results=%s",webhook_id,elapsed_ms,results); return {"accepted_for_processing":True,"webhook_id":webhook_id,"processing_ms":round(elapsed_ms,2),"results":results}
    except Exception:
        logger.exception("Webhook processing failed id=%s",webhook_id); raise HTTPException(500,"Signal processing failed; check Strategy E logs")
