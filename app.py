from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from config import SETTINGS, validate_settings
from logging_setup import configure_logging, logger
from kite_client import KiteBroker
from state_store import StateStore
from risk_manager import RiskManager
from execution import ExecutionEngine
from reconciliation import Reconciler
from monitor import PositionMonitor
from webhook import router as webhook_router, set_processor
from market_data import MarketData
from live_gate import evaluate
from runtime_state import RuntimeState
from feature_cache import FeatureBarCache
from feature_cache_loader import load_dir
from live_feature_gate import LiveFeatureGate

configure_logging()
runtime_state=RuntimeState()
broker=store=risk=execution=reconciler=monitor=market_data=processor=feature_cache=feature_gate=None

class Processor:
    def __init__(self, broker, store, risk, execution, reconciler, monitor, runtime):
        self.broker=broker; self.store=store; self.risk=risk; self.execution=execution; self.reconciler=reconciler; self.monitor=monitor; self.runtime=runtime
    def ready_for_webhook(self):
        if SETTINGS.mode=="LIVE" and not evaluate(SETTINGS).allowed: return False
        return self.runtime.ready(require_market_data=(SETTINGS.mode=="LIVE"))

def _admin(x):
    if not SETTINGS.admin_token or x!=SETTINGS.admin_token: raise HTTPException(401,"Unauthorized")

def positions_view():
    items=[]
    if not store or not broker: return items
    for symbol,p in store.positions().items():
        d=dict(p); d["current_ltp"]=None
        try:d["current_ltp"]=broker.ltp(symbol)
        except Exception: pass
        if d["current_ltp"] is not None:
            d["unrealized_pnl"]=(float(d["current_ltp"])-float(d["entry_price"]))*int(d.get("remaining_quantity",0))
        else:d["unrealized_pnl"]=None
        items.append(d)
    return items

@asynccontextmanager
async def lifespan(app):
    global broker,store,risk,execution,reconciler,monitor,processor,market_data,feature_cache,feature_gate
    logger.info("="*70)
    logger.info("STRATEGY E V6.2 STARTUP | runtime=V7.4")
    logger.info("STRATEGY E V7.4 STARTUP")
    logger.info("STRATEGY E V7.4 STARTUP | delayed entry enabled=%s mode=%s", SETTINGS.delayed_entry_enabled, SETTINGS.delayed_entry_mode)
    logger.info("MODE=%s PORT=%s LIVE_ORDERS_ARMED=%s FINAL_R=%s POST_PARTIAL_TIMEOUT=%sm",SETTINGS.mode,SETTINGS.port,SETTINGS.live_orders_armed,SETTINGS.final_r_multiple,SETTINGS.post_partial_time_stop_minutes)
    errors=validate_settings()
    if errors:
        runtime_state.update(last_error="; ".join(errors)); logger.error("CONFIG VALIDATION FAILED: %s",errors); raise RuntimeError("; ".join(errors))
    store=StateStore(); logger.info("STATE STORE ready path=%s positions=%s",store.path,len(store.positions()))
    feature_cache=FeatureBarCache(); loaded=load_dir(SETTINGS.feature_cache_dir,feature_cache); logger.info("FEATURE CACHE loaded symbols=%s dir=%s",loaded,SETTINGS.feature_cache_dir)
    feature_gate=LiveFeatureGate(feature_cache)
    broker=KiteBroker(state_store=store); broker.instruments(); logger.info("KITE instruments preloaded symbols=%s",len(broker.instruments())); runtime_state.update(broker_ok=True)
    risk=RiskManager(store,broker,feature_gate); execution=ExecutionEngine(broker,store,risk,runtime_state,feature_gate); execution.market_bars_provider=lambda: feature_cache.get(SETTINGS.market_regime_symbol)
    reconciler=Reconciler(broker,store)
    problems=reconciler.reconcile(); runtime_state.update(reconciliation=problems,last_reconciliation_at=datetime.now().isoformat())
    if problems and SETTINGS.startup_reconcile_required:
        runtime_state.update(last_error=f"STARTUP RECONCILIATION FAILED: {problems}"); logger.error("STARTUP RECONCILIATION FAILED: %s",problems); raise RuntimeError(f"STARTUP RECONCILIATION FAILED: {problems}")
    if problems: logger.warning("STARTUP RECONCILIATION WARNINGS: %s",problems)
    market_data=MarketData(broker,runtime_state); broker.market_data=market_data; market_data.start()
    monitor=PositionMonitor(broker,store,execution,reconciler,runtime_state); monitor.market_data=market_data
    processor=Processor(broker,store,risk,execution,reconciler,monitor,runtime_state); set_processor(processor); monitor.start()
    runtime_state.update(startup_complete=True)
    logger.info("STARTUP COMPLETE ticker_connected=%s",market_data.connected)
    yield
    runtime_state.update(startup_complete=False)
    if monitor: monitor.stop()
    if market_data: market_data.stop()
    logger.info("STRATEGY E shutdown complete")

app=FastAPI(title="Strategy E Production V7.4",version="7.4",lifespan=lifespan)
app.include_router(webhook_router)

@app.get("/",response_class=HTMLResponse)
def dashboard():
    return HTMLResponse("""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Strategy E V7.4 Control</title><style>body{font-family:system-ui,sans-serif;margin:0;background:#f4f6f8;color:#17202a}.wrap{max-width:1200px;margin:auto;padding:20px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}.card{background:#fff;border-radius:14px;padding:16px;box-shadow:0 2px 10px #0001}.ok{color:#087443}.bad{color:#b42318}.btn{border:0;border-radius:8px;padding:9px 12px;cursor:pointer}.danger{background:#b42318;color:#fff}.warn{background:#b76e00;color:#fff}.muted{color:#667085}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}th,td{padding:8px;border-bottom:1px solid #eee;text-align:left}input{padding:8px;border:1px solid #ccc;border-radius:8px}</style></head><body><div class='wrap'><h1>Strategy E V7.4</h1><p class='muted'>Production control console. Manual exits are isolated per symbol and do not stop the application.</p><div class='grid'><div class='card'><b>Health</b><div id='health'>Loading...</div></div><div class='card'><b>Readiness</b><div id='ready'>Loading...</div></div><div class='card'><b>Live Gate</b><div id='gate'>Loading...</div></div><div class='card'><b>Exit Policy</b><div>50% @ 1R<br>Remaining target: 3R<br>Stagnation: 90 min<br>Trailing: 0.5R lock / 1R distance<br>Basket target: ₹4,500</div></div></div><div class='card' style='margin-top:14px'><label>Admin token <input id='tok' type='password' size='46' placeholder='Enter ADMIN_TOKEN'></label> <button class='btn warn' onclick='reconcile()'>Reconcile</button> <button class='btn danger' onclick='flattenAll()'>Flatten All</button></div><div class='card' style='margin-top:14px'><h2>Open Positions</h2><div class='table-wrap' id='pos'>Loading...</div></div></div><script>const tok=()=>document.getElementById('tok').value;async function api(path,opt={}){const h=opt.headers||{};h['X-Admin-Token']=tok();if(opt.body){h['Content-Type']='application/json'}const r=await fetch(path,{...opt,headers:h});let d={};try{d=await r.json()}catch{};return {status:r.status,data:d}}async function reconcile(){const x=await api('/admin/reconcile',{method:'POST'});alert(JSON.stringify(x.data));refresh()}async function manualExit(s){if(!confirm('Exit '+s+' immediately?'))return;const x=await api('/admin/exit/'+encodeURIComponent(s),{method:'POST',body:JSON.stringify({reason:'DASHBOARD_MANUAL_EXIT'})});alert(JSON.stringify(x.data));refresh()}async function flattenAll(){if(!confirm('Flatten ALL Strategy E positions now?'))return;const x=await api('/admin/flatten',{method:'POST',body:JSON.stringify({reason:'DASHBOARD_MANUAL_FLATTEN_ALL'})});alert(JSON.stringify(x.data));refresh()}async function refresh(){const h=await (await fetch('/health')).json();document.getElementById('health').innerHTML=h.mode+' / '+(h.startup_complete?'RUNNING':'STOPPED');const r=await (await fetch('/readiness')).json();document.getElementById('ready').innerHTML='<span class='+ (r.ready?'ok':'bad') +'>'+r.ready+'</span>';const g=await (await fetch('/live-gate')).json();document.getElementById('gate').innerHTML='<span class='+(g.allowed?'ok':'bad')+'>'+g.allowed+'</span><br>'+g.reasons.join(', ');const p=await (await fetch('/admin/positions',{headers:{'X-Admin-Token':tok()}})).json();let html='<table><tr><th>Symbol</th><th>Qty</th><th>Entry</th><th>LTP</th><th>1R</th><th>3R</th><th>Trail SL</th><th>Unrealized</th><th>Status</th><th>Action</th></tr>';for(const x of p.positions){html+='<tr><td>'+x.symbol+'</td><td>'+x.remaining_quantity+'</td><td>'+Number(x.entry_price).toFixed(2)+'</td><td>'+Number(x.current_ltp||0).toFixed(2)+'</td><td>'+Number(x.one_r).toFixed(2)+'</td><td>'+Number(x.two_r).toFixed(2)+'</td><td>'+Number(x.trailing_stop_price||0).toFixed(2)+'</td><td>'+Number(x.unrealized_pnl||0).toFixed(0)+'</td><td>'+x.status+(x.manual_exit_pending?' / MANUAL PENDING':'')+'</td><td><button class=\"btn danger\" onclick=\"manualExit(\\''+x.symbol+'\\')\">Exit</button></td></tr>'}html+='</table>';document.getElementById('pos').innerHTML=html}setInterval(refresh,3000);refresh();</script></body></html>""")

@app.get("/health")
def health():
    snap=runtime_state.snapshot(); return {"status":"ok","version":"7.4","pending_entries":len(store.pending_entries()) if store else 0,"mode":SETTINGS.mode,"startup_complete":snap["startup_complete"],"live_orders_armed":SETTINGS.live_orders_armed,"positions":len(store.positions()) if store else 0,"runtime":snap}

@app.get("/readiness")
def readiness():
    problems=validate_settings(); broker_ok=False; recon=[]
    try:
        if broker:
            broker.profile(); broker_ok=True; recon=reconciler.reconcile() if reconciler else ["RECONCILER_NOT_INITIALIZED"]
            runtime_state.update(broker_ok=True,reconciliation=recon,last_reconciliation_at=datetime.now().isoformat())
    except Exception as e:
        logger.exception("READINESS check failed: %s",e); problems.append(f"KITE: {e}"); runtime_state.update(broker_ok=False,last_error=str(e))
    snap=runtime_state.snapshot(); ready=(not problems and not recon and broker_ok and snap["startup_complete"] and (snap["market_data_connected"] or SETTINGS.mode!="LIVE"))
    return {"ready":ready,"config_errors":problems,"reconciliation":recon,"live_orders_armed":SETTINGS.live_orders_armed,"runtime":snap}

@app.get("/admin/positions")
def positions_admin(x_admin_token:str=Header(default="")):
    _admin(x_admin_token); return {"positions":positions_view()}

@app.post("/admin/reconcile")
def admin_reconcile(x_admin_token:str=Header(default="")):
    _admin(x_admin_token); problems=reconciler.reconcile(); runtime_state.update(reconciliation=problems,last_reconciliation_at=datetime.now().isoformat()); return {"ok":not problems,"problems":problems}

@app.post("/admin/exit/{symbol}")
def admin_exit(symbol:str,x_admin_token:str=Header(default=""),reason:str="MANUAL_EXIT"):
    _admin(x_admin_token)
    if not execution: raise HTTPException(503,"Execution processor not ready")
    try:return execution.manual_exit(symbol,reason=reason)
    except Exception as exc:logger.exception("MANUAL EXIT FAILED symbol=%s",symbol);raise HTTPException(500,str(exc)) from exc

@app.post("/admin/flatten")
def admin_flatten(x_admin_token:str=Header(default=""),reason:str="MANUAL_FLATTEN_ALL"):
    _admin(x_admin_token)
    if not execution: raise HTTPException(503,"Execution processor not ready")
    try:return {"ok":True,"results":execution.flatten_all_manual(reason=reason)}
    except Exception as exc:logger.exception("MANUAL FLATTEN FAILED");raise HTTPException(500,str(exc)) from exc

@app.post("/admin/kill-switch")
def admin_kill_switch(x_admin_token:str=Header(default="")):
    _admin(x_admin_token); return {"ok":True,"instruction":"Set KILL_SWITCH=true in .env and restart the service. Kill switch is fail-closed."}

@app.get("/live-gate")
def live_gate_status():
    r=evaluate(SETTINGS); return {"allowed":r.allowed,"reasons":list(r.reasons)}
