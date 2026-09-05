from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from threading import RLock
import uuid
import risk_manager
from models import Signal, PositionState
from live_gate import assert_live_allowed, assert_live_exit_allowed
from logging_setup import logger
from entry_engine import build_setup, confirmation

IST=ZoneInfo("Asia/Kolkata")

class ExecutionEngine:
    def __init__(self, broker, store, risk, runtime=None, feature_gate=None, market_bars_provider=None):
        self.broker=broker; self.store=store; self.risk=risk; self.runtime=runtime; self.feature_gate=feature_gate; self.market_bars_provider=market_bars_provider
        self._locks={}; self._guard=RLock()
    def _lock_for(self,symbol):
        with self._guard:return self._locks.setdefault(symbol,RLock())
    def _paper(self):
        s=risk_manager.SETTINGS
        return s.mode!="LIVE" or not s.live_orders_armed
    def _entry(self,symbol,quantity):
        if self._paper(): return "PAPER-"+uuid.uuid4().hex[:12],quantity,self.broker.ltp(symbol)
        assert_live_allowed(); oid=self.broker.place_market_buy(symbol,quantity); qty,price,_=self.broker.finalize_entry(oid,quantity)
        logger.info("ENTRY COMPLETE symbol=%s order=%s qty=%s price=%.4f",symbol,oid,qty,price); return str(oid),qty,price
    # ENTRY PARTIAL cleanup is fail-safe for live orders.
    def _flatten_after_partial_entry(self,symbol,qty):
        if qty<=0:return
        assert_live_allowed(); oid=self.broker.place_market_sell(symbol,qty); filled,_,snap=self.broker.completed_fill(oid)
        if filled!=qty: raise RuntimeError(f"Partial entry cleanup incomplete symbol={symbol} requested={qty} filled={filled} status={snap.get('status')}")
    def process_signal(self,signal:Signal,reference_price=None):
        if self.runtime and risk_manager.SETTINGS.mode=="LIVE" and not self.runtime.ready(require_market_data=True): return {"accepted":False,"symbol":signal.symbol,"reason":"RUNTIME_NOT_READY"}
        s=risk_manager.SETTINGS
        # Backward-compatible immediate mode is retained for unit tests/controlled fallback.
        # Production V7.4 defaults to delayed entry.
        if not s.delayed_entry_enabled:
            trade_number=self.store.entry_count(signal.signal_time.date().isoformat())+1
            ok,reason=self.risk.validate_signal(signal,reference_price,trade_number)
            if not ok:return {"accepted":False,"symbol":signal.symbol,"reason":reason}
            ins=self.broker.instrument(signal.symbol); reference_price=reference_price if reference_price is not None else self.broker.ltp(signal.symbol)
            qty=self.risk.quantity(reference_price,signal.signal_low)
            if reference_price<=signal.signal_low or qty<2:return {"accepted":False,"symbol":signal.symbol,"reason":"REFERENCE_PRICE_AT_OR_BELOW_SIGNAL_LOW" if reference_price<=signal.signal_low else "CALCULATED_QUANTITY_LT_2"}
            oid,filled_qty,fill=self._entry(signal.symbol,qty)
            if filled_qty!=qty:
                if not self._paper() and filled_qty:self._flatten_after_partial_entry(signal.symbol,filled_qty)
                return {"accepted":False,"symbol":signal.symbol,"reason":"ENTRY_FILL_NOT_FULL","requested_quantity":qty,"filled_quantity":filled_qty}
            risk_per_share=fill-signal.signal_low
            if risk_per_share<=0:
                if not self._paper():self._flatten_after_partial_entry(signal.symbol,filled_qty)
                return {"accepted":False,"symbol":signal.symbol,"reason":"ENTRY_AT_OR_BELOW_SIGNAL_LOW"}
            q1=filled_qty//2;q2=filled_qty-q1
            p=PositionState(symbol=signal.symbol,instrument_token=int(ins["instrument_token"]),signal_time=signal.signal_time,entry_order_id=str(oid),entry_price=fill,entry_quantity=filled_qty,remaining_quantity=filled_qty,signal_low=signal.signal_low,risk_per_share=risk_per_share,one_r=fill+risk_per_share,two_r=fill+s.final_r_multiple*risk_per_share,partial_quantity=q1,final_quantity=q2,entry_risk_pct=((fill-signal.signal_low)/fill*100.0))
            self.store.upsert_position(p);self.store.increment_entry(signal.signal_time.date().isoformat())
            if getattr(self.broker,'market_data',None):self.broker.market_data.subscribe(p.instrument_token)
            return {"accepted":True,"symbol":signal.symbol,"order_id":str(oid),"quantity":filled_qty,"fill_price":fill,"one_r":p.one_r,"two_r":p.two_r,"final_target":p.two_r,"mode":"PAPER" if self._paper() else "LIVE"}
        trade_number=self.store.entry_count(signal.signal_time.date().isoformat())+len(self.store.pending_entries())+1
        ok,reason=self.risk.validate_signal(signal, None, trade_number)
        if not ok:return {"accepted":False,"symbol":signal.symbol,"reason":reason}
        if signal.symbol in self.store.pending_entries():return {"accepted":False,"symbol":signal.symbol,"reason":"ENTRY_SETUP_ALREADY_PENDING"}
        if len(self.store.positions())+len(self.store.pending_entries())>=s.max_open_positions:return {"accepted":False,"symbol":signal.symbol,"reason":"MAX_OPEN_POSITIONS"}
        ins=self.broker.instrument(signal.symbol)
        # Feature scoring is setup validation only. Actual entry risk is calculated after confirmation.
        bars=self.feature_gate.cache.get(signal.symbol) if self.feature_gate and self.feature_gate.cache else []
        if len(bars)>=s.feature_min_bars:
            t0=datetime.now(); from feature_engine import score_trade
            snap=score_trade(symbol=signal.symbol,signal_time=signal.signal_time,signal_open=signal.signal_open,signal_high=signal.signal_high,signal_low=signal.signal_low,signal_close=signal.signal_close,entry_price=signal.signal_close,bars=bars,market_bars=self.market_bars_provider() if self.market_bars_provider else None,max_risk_pct=999,min_adx=s.feature_min_adx,min_relative_volume=s.feature_min_relative_volume,min_atr_pct=s.feature_min_atr_pct,max_atr_pct=s.feature_max_atr_pct,score_threshold=s.feature_score_threshold,market_filter=s.market_regime_filter)
            elapsed_ms=(datetime.now()-t0).total_seconds()*1000
            threshold=s.feature_trade2_score_threshold if trade_number>=2 else s.feature_score_threshold
            if s.feature_gate_mode=='ENFORCE' and not (snap.score>=threshold and snap.market_regime_ok and snap.time_window_ok):
                return {"accepted":False,"symbol":signal.symbol,"reason":"FEATURE_REJECT_SETUP","feature":snap.to_dict()}
        else:
            snap=None;elapsed_ms=0.0
            if s.feature_gate_mode=='ENFORCE': return {"accepted":False,"symbol":signal.symbol,"reason":"FEATURE_CACHE_NOT_READY"}
        five=self.feature_gate.cache.get(signal.symbol) if self.feature_gate and self.feature_gate.cache else []
        signal_bar={'ts':signal.signal_time,'open':signal.signal_open,'high':signal.signal_high,'low':signal.signal_low,'close':signal.signal_close,'volume':0.0}
        # Live cache may lag the just-closed signal candle. Add Chartink's closed 5m bar in memory.
        five=[b for b in five if b['ts']<signal.signal_time]+[signal_bar]
        # Prefer the prior cached 5m candle; otherwise derive it from the in-memory 1m stream.
        prevs=[b for b in five if b['ts']<signal.signal_time]
        if not prevs:
            md=getattr(self.broker,'market_data',None)
            if md:
                m1=md.get_1m(int(ins['instrument_token']),limit=12)
                prior=[b for b in m1 if b['ts']<signal.signal_time]
                if prior:
                    prior=prior[-5:]
                    if prior:
                        prevs=[{'ts':signal.signal_time-timedelta(minutes=5),'open':prior[0]['open'],'high':max(x['high'] for x in prior),'low':min(x['low'] for x in prior),'close':prior[-1]['close'],'volume':sum(x.get('volume',0) for x in prior)}]
        if not prevs:return {"accepted":False,"symbol":signal.symbol,"reason":"PREVIOUS_CANDLE_NOT_AVAILABLE"}
        setup=build_setup(signal.signal_time,prevs[-1],signal_bar,five,ema_tolerance_pct=s.fib_ema_tolerance_pct,wait_minutes=s.delayed_entry_wait_minutes)
        setup.update({'symbol':signal.symbol,'instrument_token':int(ins['instrument_token']),'trade_number':trade_number,'feature':snap.to_dict() if snap else None,'feature_score':snap.score if snap else None,'feature_grade':snap.grade if snap else None})
        self.store.upsert_pending_entry(signal.symbol,setup)
        if getattr(self.broker,'market_data',None):self.broker.market_data.subscribe(ins['instrument_token'])
        self.store.append_signal_intelligence({'signal_time':signal.signal_time,'symbol':signal.symbol,'trade_number':trade_number,'reference_price':reference_price or signal.signal_close,'entry_mode':s.delayed_entry_mode,'pending':True,'feature':snap.to_dict() if snap else None,'feature_calc_ms':round(elapsed_ms,3),'fib_50':setup['fib_50'],'fib_618':setup['fib_618'],'ema9':setup['ema9']})
        logger.info('PENDING ENTRY created symbol=%s mode=%s fib50=%.4f fib618=%.4f ema9=%s expires=%s',signal.symbol,s.delayed_entry_mode,setup['fib_50'],setup['fib_618'],setup['ema9'],setup['expires_at'])
        return {"accepted":True,"status":"PENDING_ENTRY","symbol":signal.symbol,"method":s.delayed_entry_mode,"fib_50":setup['fib_50'],"fib_618":setup['fib_618'],"ema9":setup['ema9'],"expires_at":setup['expires_at'],"feature_score":setup.get('feature_score')}

    def process_pending_entries(self):
        s=risk_manager.SETTINGS
        md=getattr(self.broker,'market_data',None)
        if not md:return
        for symbol,setup in list(self.store.pending_entries().items()):
            try:
                expires=datetime.fromisoformat(setup['expires_at'])
                if datetime.now(IST).replace(tzinfo=None)>expires:
                    self.store.remove_pending_entry(symbol);logger.info('PENDING ENTRY EXPIRED symbol=%s',symbol);continue
                bars=md.get_1m(int(setup['instrument_token']),limit=60,closed_only=True)
                c=confirmation(setup,bars,mode=s.delayed_entry_mode,allow_continuation=s.delayed_entry_allow_continuation,zone_tolerance_pct=s.entry_zone_tolerance_pct)
                if not c:continue
                entry=float(c['entry_price']); stop=min(entry,max(float(setup['signal_low']),float(c['structure_low']))-(entry*s.entry_zone_tolerance_pct/100.0))
                # Never allow the stop to equal/exceed entry. Use the signal low as final fallback.
                stop=min(stop,entry-0.01)
                risk=entry-stop
                if risk<=0 or risk/entry*100>s.max_entry_risk_pct:
                    self.store.remove_pending_entry(symbol);logger.info('PENDING ENTRY REJECTED symbol=%s reason=ENTRY_RISK_OVER_LIMIT',symbol);continue
                qty=self.risk.quantity(entry,stop)
                if qty<2:self.store.remove_pending_entry(symbol);continue
                signal=Signal(symbol=symbol,signal_time=datetime.fromisoformat(setup['signal_time']),signal_open=setup['previous_low'],signal_high=setup['signal_high'],signal_low=setup['signal_low'],signal_close=setup.get('ema9') or entry)
                oid,filled,fill=self._entry(symbol,qty)
                if filled!=qty:
                    if not self._paper() and filled:self._flatten_after_partial_entry(symbol,filled)
                    self.store.remove_pending_entry(symbol);continue
                risk=fill-stop
                if risk<=0 or risk/fill*100>s.max_entry_risk_pct:
                    if not self._paper():self._flatten_after_partial_entry(symbol,filled)
                    self.store.remove_pending_entry(symbol);continue
                q1=filled//2;q2=filled-q1
                p=PositionState(symbol=symbol,instrument_token=int(setup['instrument_token']),signal_time=signal.signal_time,entry_order_id=str(oid),entry_price=fill,entry_quantity=filled,remaining_quantity=filled,signal_low=signal.signal_low,risk_per_share=risk,one_r=fill+risk,two_r=fill+s.final_r_multiple*risk,partial_quantity=q1,final_quantity=q2,feature_score=setup.get('feature_score'),feature_grade=setup.get('feature_grade'),entry_risk_pct=risk/fill*100,initial_stop_price=stop,entry_method=c['method'],entry_confirmation_time=c['entry_time'],fib_50=setup.get('fib_50'),fib_618=setup.get('fib_618'))
                self.store.remove_pending_entry(symbol);self.store.upsert_position(p);self.store.increment_entry(signal.signal_time.date().isoformat())
                md.subscribe(p.instrument_token)
                logger.info('DELAYED ENTRY CONFIRMED symbol=%s method=%s entry=%.4f stop=%.4f qty=%s',symbol,c['method'],fill,stop,filled)
            except Exception as exc:logger.exception('PENDING ENTRY ERROR symbol=%s: %s',symbol,exc)
    def process_signals(self,signals):
        candidates=[]
        for signal in signals:
            ok,reason=self.risk.validate_signal(signal);candidates.append(signal if ok else (signal,reason))
        valid=[x for x in candidates if not isinstance(x,tuple)];prices=self.broker.ltp_many([x.symbol for x in valid]) if valid else {};out=[]
        for x in candidates:
            if isinstance(x,tuple):signal,reason=x;out.append({"accepted":False,"symbol":signal.symbol,"reason":reason})
            else:out.append(self.process_signal(x,reference_price=prices.get(x.symbol)))
        return out
    def _start_exit(self,p,qty,cancel_on_timeout=False):
        if qty<=0:return None
        if self._paper():return {"order_id":"PAPER-"+uuid.uuid4().hex[:12],"filled":qty,"price":self.broker.ltp(p["symbol"]),"status":"COMPLETE"}
        assert_live_exit_allowed();oid=self.broker.place_market_sell(p["symbol"],qty);snap=self.broker.wait_for_order(oid,cancel_on_timeout=cancel_on_timeout)
        if not snap:raise RuntimeError(f"Exit order not found: {oid}")
        return {"order_id":str(oid),"filled":int(snap.get("filled_quantity") or 0),"price":float(snap.get("average_price") or 0),"status":snap.get("status")}
    def exit_partial(self,p):
        with self._lock_for(p["symbol"]):
            if p.get("manual_exit_pending"):return
            if p.get("partial_exit_order_id") and int(p.get("partial_filled",0))<int(p["partial_quantity"]):return
            qty=int(p["partial_quantity"])-int(p.get("partial_filled",0));
            if qty<=0:return
            r=self._start_exit(p,qty);p["partial_exit_order_id"]=r["order_id"];p["partial_order_requested"]=qty;p["partial_order_base_filled"]=int(p.get("partial_filled",0));p["partial_filled"]=int(p.get("partial_filled",0))+int(r["filled"]);p["remaining_quantity"]=max(0,int(p["remaining_quantity"])-int(r["filled"]))
            if r["filled"]>0:
                fill_price=float(r["price"] or 0)
                p["realized_pnl"]=float(p.get("realized_pnl",0.0))+(fill_price-float(p["entry_price"]))*int(r["filled"])
                p["partial_exit_filled_at"]=datetime.now().isoformat();p["partial_exit_price"]=fill_price;p["max_price_since_partial"]=fill_price
                p["trailing_stop_active"]=False
                p["trailing_stop_price"]=None
            p["updated_at"]=datetime.now().isoformat();self.store.upsert_position_dict(p);logger.info("PARTIAL EXIT symbol=%s qty=%s price=%s",p["symbol"],r["filled"],r["price"])
    def exit_final(self,p,reason="FINAL_TARGET"):
        with self._lock_for(p["symbol"]):
            if p.get("manual_exit_pending"):return
            partial_pending=p.get("partial_exit_order_id") and int(p.get("partial_filled",0))<int(p.get("partial_quantity",0))
            if partial_pending:return
            qty=int(p.get("remaining_quantity",0));
            if qty<=0:self.store.remove_position(p["symbol"]);return
            if p.get("final_exit_order_id") and int(p.get("final_filled",0))<int(p.get("final_order_requested",0)):return
            r=self._start_exit(p,qty)
            if r["filled"]>0:
                fill_price=float(r["price"] or 0)
                realized=(fill_price-float(p["entry_price"]))*int(r["filled"]);p["realized_pnl"]=float(p.get("realized_pnl",0.0))+realized
            p["final_exit_order_id"]=r["order_id"];p["final_order_requested"]=qty;p["final_order_base_filled"]=int(p.get("final_filled",0));p["final_filled"]=int(p.get("final_filled",0))+int(r["filled"]);p["remaining_quantity"]=max(0,qty-int(r["filled"]));p["last_exit_reason"]=reason;p["updated_at"]=datetime.now().isoformat()
            if p["remaining_quantity"]==0:
                day=str(p["signal_time"])[:10]; self.store.record_closed_trade(day,float(p.get("realized_pnl",0.0))); self.store.remove_position(p["symbol"])
            else:self.store.upsert_position_dict(p)
            logger.info("FINAL EXIT symbol=%s qty=%s filled=%s price=%s reason=%s",p["symbol"],qty,r["filled"],r["price"],reason)
    def manual_exit(self,symbol,reason="MANUAL_EXIT"):
        symbol=symbol.upper().strip()
        with self._lock_for(symbol):
            p=self.store.positions().get(symbol)
            if not p:return {"ok":False,"symbol":symbol,"reason":"POSITION_NOT_FOUND"}
            if p.get("manual_exit_pending"):return {"ok":False,"symbol":symbol,"reason":"MANUAL_EXIT_ALREADY_PENDING"}
            qty=int(p.get("remaining_quantity",0));p["manual_exit_pending"]=True;p["manual_exit_reason"]=reason;p["updated_at"]=datetime.now().isoformat();self.store.upsert_position_dict(p)
            if qty<=0:self.store.remove_position(symbol);return {"ok":True,"symbol":symbol,"status":"ALREADY_FLAT"}
            if not self._paper():
                for kind in ("partial","final"):
                    oid=p.get(f"{kind}_exit_order_id")
                    if oid:
                        snap=self.broker.order_snapshot(oid)
                        if snap and str(snap.get("status")) not in {"COMPLETE","REJECTED","CANCELLED"}:
                            try:self.broker.cancel_order(oid)
                            except Exception:logger.exception("Manual exit could not cancel %s order %s",kind,oid)
            r=self._start_exit(p,qty,cancel_on_timeout=False)
            if r["filled"]>0:
                fill_price=float(r["price"] or 0)
                p["realized_pnl"]=float(p.get("realized_pnl",0.0))+(fill_price-float(p["entry_price"]))*int(r["filled"])
            p["manual_exit_order_id"]=r["order_id"];p["manual_exit_requested"]=qty;p["manual_exit_filled"]=int(r["filled"]);p["remaining_quantity"]=max(0,qty-int(r["filled"]));p["updated_at"]=datetime.now().isoformat()
            if r["status"]=="COMPLETE" and p["remaining_quantity"]==0:
                self.store.record_closed_trade(str(p["signal_time"])[:10],float(p.get("realized_pnl",0.0))); self.store.remove_position(symbol);logger.warning("MANUAL EXIT COMPLETE symbol=%s qty=%s price=%s reason=%s",symbol,qty,r["price"],reason);return {"ok":True,"symbol":symbol,"status":"FLAT","order_id":r["order_id"],"filled":r["filled"],"price":r["price"]}
            self.store.upsert_position_dict(p);logger.warning("MANUAL EXIT PENDING symbol=%s order=%s filled=%s remaining=%s",symbol,r["order_id"],r["filled"],p["remaining_quantity"])
            return {"ok":True,"symbol":symbol,"status":"PENDING","order_id":r["order_id"],"filled":r["filled"],"remaining":p["remaining_quantity"]}
    def flatten_all_manual(self,reason="MANUAL_FLATTEN_ALL"):
        return [self.manual_exit(s,reason) for s in list(self.store.positions().keys())]
    def refresh_pending_exits(self):
        if self._paper():return
        for symbol,p in list(self.store.positions().items()):
            if p.get("manual_exit_pending"):
                oid=p.get("manual_exit_order_id");
                if not oid:continue
                snap=self.broker.order_snapshot(oid)
                if not snap:continue
                old_filled=int(p.get("manual_exit_filled",0) or 0); broker_filled=int(snap.get("filled_quantity") or 0); newly=max(0,broker_filled-old_filled)
                p["manual_exit_filled"]=broker_filled; p["remaining_quantity"]=max(0,int(p.get("entry_quantity",0))-int(p.get("partial_filled",0))-int(p.get("final_filled",0))-broker_filled); status=str(snap.get("status") or "")
                avg=float(snap.get("average_price") or 0)
                if newly>0 and avg>0: p["realized_pnl"]=float(p.get("realized_pnl",0.0))+(avg-float(p["entry_price"]))*newly
                if status=="COMPLETE" and p["remaining_quantity"]==0:
                    self.store.record_closed_trade(str(p["signal_time"])[:10],float(p.get("realized_pnl",0.0))); self.store.remove_position(symbol);logger.warning("MANUAL EXIT COMPLETED symbol=%s order=%s",symbol,oid);continue
                if status in {"REJECTED","CANCELLED"}:p["manual_exit_pending"]=False;p["manual_exit_order_id"]=None;p["updated_at"]=datetime.now().isoformat();self.store.upsert_position_dict(p);logger.error("MANUAL EXIT FAILED symbol=%s order=%s status=%s",symbol,oid,status);continue
                self.store.upsert_position_dict(p);continue
            for kind in ("partial","final"):
                oid=p.get(f"{kind}_exit_order_id")
                if not oid:continue
                requested=int(p.get(f"{kind}_order_requested",0));base=int(p.get(f"{kind}_order_base_filled",0));current=int(p.get(f"{kind}_filled",0))
                if current>=base+requested:continue
                snap=self.broker.order_snapshot(oid)
                if not snap:continue
                broker_filled=int(snap.get("filled_quantity") or 0);delta=max(0,broker_filled-base)
                if delta>current-base:
                    newly=delta-(current-base);p[f"{kind}_filled"]=current+newly;p["remaining_quantity"]=max(0,int(p["remaining_quantity"])-newly)
                    avg=float(snap.get("average_price") or 0)
                    if avg>0: p["realized_pnl"]=float(p.get("realized_pnl",0.0))+(avg-float(p["entry_price"]))*newly
                    if kind=="partial" and newly>0 and not p.get("partial_exit_filled_at"):p["partial_exit_filled_at"]=datetime.now().isoformat();p["partial_exit_price"]=avg;p["max_price_since_partial"]=avg
                    p["updated_at"]=datetime.now().isoformat();self.store.upsert_position_dict(p);current+=newly
                status=str(snap.get("status") or "")
                if status in {"COMPLETE","REJECTED","CANCELLED"}:
                    if current>=base+requested:
                        p[f"{kind}_exit_complete"]=True
                        if kind=="final" and p.get("remaining_quantity",0)<=0:
                            self.store.record_closed_trade(str(p["signal_time"])[:10],float(p.get("realized_pnl",0.0)));self.store.remove_position(symbol);continue
                    else:p[f"{kind}_exit_order_id"]=None;p[f"{kind}_order_requested"]=0;p[f"{kind}_order_base_filled"]=int(p.get(f"{kind}_filled",0))
                    self.store.upsert_position_dict(p)
