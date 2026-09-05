import threading,time
from datetime import datetime
from zoneinfo import ZoneInfo
from config import SETTINGS
from logging_setup import logger
import risk_manager
IST=ZoneInfo("Asia/Kolkata")

class PositionMonitor:
    def __init__(self,broker,store,execution,reconciler=None,runtime=None):
        self.broker=broker;self.store=store;self.execution=execution;self.reconciler=reconciler;self.runtime=runtime
        self.market_data=None;self.stop_event=threading.Event();self.thread=threading.Thread(target=self.run,daemon=True,name="position-monitor")
        self.last_reconcile=0.0
        ps=self.store.portfolio_state()
        self.basket_trailing_armed=bool(ps.get("trailing_armed",False))
        self.basket_peak_pnl=float(ps.get("peak_pnl",0.0) or 0.0)
    def start(self): self.thread.start();logger.info("Position monitor started")
    def stop(self): self.stop_event.set();logger.info("Position monitor stopping")
    def run(self):
        while not self.stop_event.is_set():
            try:self.check_once()
            except Exception as exc: logger.exception("MONITOR ERROR: %s",exc)
            self.stop_event.wait(0.5)
    def _ltp(self,p):
        token=int(p["instrument_token"]); ltp=self.market_data.fresh(token,SETTINGS.ltp_stale_seconds) if self.market_data else None
        if ltp is None:
            try:ltp=self.broker.ltp(p["symbol"])
            except Exception:ltp=None
        return ltp
    def _position_pnl(self,p,ltp):
        return float(p.get("realized_pnl",0.0)) + (float(ltp)-float(p["entry_price"]))*int(p.get("remaining_quantity",0))
    def _basket_snapshot(self):
        positions=[];total=0.0
        for symbol,p in list(self.store.positions().items()):
            if p.get("manual_exit_pending"): continue
            ltp=self._ltp(p)
            if ltp is None: return None
            pnl=self._position_pnl(p,ltp); total+=pnl
            positions.append((p,ltp,pnl))
        return positions,total
    def _reset_basket_trailing(self):
        if self.basket_trailing_armed or self.basket_peak_pnl:
            self.basket_trailing_armed=False
            self.basket_peak_pnl=0.0
            self.store.update_portfolio_state(trailing_armed=False, peak_pnl=0.0, trailing_stop_pnl=None)

    def _check_basket_profit(self):
        if not SETTINGS.portfolio_profit_target_enabled:
            self._reset_basket_trailing()
            return False
        snap=self._basket_snapshot()
        if snap is None:return False
        positions,total=snap
        minp=SETTINGS.portfolio_profit_target_min_positions
        if len(positions)<minp:
            self._reset_basket_trailing()
            return False

        target=SETTINGS.portfolio_profit_target_inr
        if not SETTINGS.portfolio_profit_trailing_enabled and total>=target:
            logger.warning("PORTFOLIO_PROFIT_TARGET hit -> immediate basket exit positions=%s pnl=%.2f", [p["symbol"] for p,_,_ in positions], total)
            for p,_,_ in positions:
                try:self.execution.exit_final(p,reason="PORTFOLIO_PROFIT_TARGET")
                except Exception as exc:logger.exception("BASKET EXIT FAILED symbol=%s: %s",p.get("symbol"),exc)
            return True

        if SETTINGS.portfolio_profit_trailing_enabled and not self.basket_trailing_armed and total>=target:
            self.basket_trailing_armed=True
            self.basket_peak_pnl=total
            self.store.update_portfolio_state(trailing_armed=True, peak_pnl=total, trailing_stop_pnl=target)
            logger.warning(
                "BASKET TARGET HIT -> TRAILING ARMED positions=%s pnl=%.2f target=%.2f distance=%.2f",
                [p["symbol"] for p,_,_ in positions], total, target, SETTINGS.portfolio_profit_trailing_distance_inr)

        if not self.basket_trailing_armed:
            return False

        if total>self.basket_peak_pnl:
            self.basket_peak_pnl=total
            self.store.update_portfolio_state(trailing_armed=True, peak_pnl=total)

        basket_stop=max(target, self.basket_peak_pnl-SETTINGS.portfolio_profit_trailing_distance_inr)
        ps=self.store.portfolio_state()
        old_stop=float(ps.get("trailing_stop_pnl") or 0.0)
        if basket_stop!=old_stop:
            self.store.update_portfolio_state(trailing_armed=True, peak_pnl=self.basket_peak_pnl, trailing_stop_pnl=basket_stop)
            logger.info("BASKET TRAILING UPDATED pnl=%.2f peak=%.2f stop=%.2f",total,self.basket_peak_pnl,basket_stop)

        if total<=basket_stop:
            logger.warning("BASKET PORTFOLIO_PROFIT_TARGET TRAILING STOP HIT positions=%s pnl=%.2f stop=%.2f peak=%.2f",[p["symbol"] for p,_,_ in positions],total,basket_stop,self.basket_peak_pnl)
            for p,_,_ in positions:
                try:self.execution.exit_final(p,reason="PORTFOLIO_PROFIT_TARGET_TRAILING_STOP")  # PORTFOLIO_TRAILING_STOP legacy analytics label
                except Exception as exc:logger.exception("BASKET TRAILING EXIT FAILED symbol=%s: %s",p.get("symbol"),exc)
            return True
        return False
    def _check_daily_loss(self):
        if not SETTINGS.daily_loss_limit_enabled:return False
        snap=self._basket_snapshot()
        if snap is None:return False
        positions,open_total=snap
        day=datetime.now(IST).date().isoformat()
        realized=self.store.daily_realized_pnl(day)
        total=realized+open_total
        if positions and total<=-SETTINGS.daily_loss_limit_inr:
            logger.error("DAILY LOSS LIMIT HIT realized=%.2f open=%.2f total=%.2f limit=-%.2f",realized,open_total,total,SETTINGS.daily_loss_limit_inr)
            for p,_,_ in positions:
                try:self.execution.exit_final(p,reason="DAILY_LOSS_LIMIT")
                except Exception as exc:logger.exception("LOSS-LIMIT EXIT FAILED symbol=%s: %s",p.get("symbol"),exc)
            return True
        return False
    def check_once(self):
        now=time.time()
        try:self.execution.refresh_pending_exits()
        except Exception as exc:logger.exception("PENDING EXIT REFRESH ERROR: %s",exc)
        if now-self.last_reconcile>=SETTINGS.reconcile_interval_seconds:
            self.last_reconcile=now
            try:
                recon=self.reconciler.reconcile() if self.reconciler else []
                if self.runtime:self.runtime.update(reconciliation=recon,last_reconciliation_at=datetime.now().isoformat())
                if recon:logger.error("RECONCILIATION MISMATCH: %s",recon)
            except Exception as exc:
                logger.exception("RECONCILIATION ERROR: %s",exc)
                if self.runtime:self.runtime.update(reconciliation=[{"type":"RECONCILIATION_ERROR","error":str(exc)}],last_reconciliation_at=datetime.now().isoformat())
        try:self.execution.process_pending_entries()
        except Exception as exc:logger.exception("PENDING ENTRY MONITOR ERROR: %s",exc)
        if self._check_basket_profit():
            if not self.store.positions(): self._reset_basket_trailing()
            return
        if self._check_daily_loss(): return
        for symbol,p in list(self.store.positions().items()):
            if p.get("manual_exit_pending"):continue
            ltp=self._ltp(p)
            if ltp is None:continue
            # Hard original stop is always respected, unless a tighter trailing stop is active.
            hard_stop=float(p.get("initial_stop_price") or p.get("signal_low"));
            if ltp<=hard_stop: self.execution.exit_final(p,reason="STOP_LOSS");continue
            partial_done=int(p.get("partial_filled",0))>=int(p.get("partial_quantity",0))
            if not partial_done and not p.get("partial_exit_order_id") and ltp>=float(p["one_r"]):
                self.execution.exit_partial(p);continue
            final_pending=p.get("final_exit_order_id") and int(p.get("final_filled",0))<int(p.get("final_order_requested",0))
            if partial_done:
                # Break-even/profit-lock: never allow the remaining piece to fall back below the locked level.
                if SETTINGS.break_even_enabled and not final_pending:
                    rsk=float(p["risk_per_share"]);ent=float(p["entry_price"]);be_trigger=ent+SETTINGS.break_even_activate_r*rsk
                    if ltp>=be_trigger:
                        be=ent+SETTINGS.break_even_lock_r*rsk; old_be=float(p.get("break_even_stop_price") or 0)
                        if be>old_be:
                            p["break_even_stop_price"]=be;p["break_even_active"]=True;p["updated_at"]=datetime.now().isoformat();self.store.upsert_position_dict(p)
                    be_stop=float(p.get("break_even_stop_price") or 0)
                    if be_stop>0 and ltp<=be_stop:
                        self.execution.exit_final(p,reason="BREAK_EVEN_PROFIT_LOCK");continue
                mp=max(float(p.get("max_price_since_partial") or 0),float(ltp))
                if mp!=float(p.get("max_price_since_partial") or 0):p["max_price_since_partial"]=mp;p["updated_at"]=datetime.now().isoformat();self.store.upsert_position_dict(p)
                # Trailing stop: ratchet only upward and never below the configured profit-lock floor.
                if SETTINGS.trailing_stop_enabled and SETTINGS.trailing_activate_after_partial and not final_pending:
                    risk=float(p["risk_per_share"]);entry=float(p["entry_price"])
                    floor=entry+SETTINGS.trailing_lock_r*risk
                    candidate=mp-SETTINGS.trailing_distance_r*risk
                    trail=max(floor,candidate,float(p.get("initial_stop_price") or p.get("signal_low",0)))
                    old=float(p.get("trailing_stop_price") or 0)
                    if trail>old:
                        p["trailing_stop_price"]=trail;p["trailing_stop_active"]=True;p["updated_at"]=datetime.now().isoformat();self.store.upsert_position_dict(p)
                    active_stop=float(p.get("trailing_stop_price") or 0)
                    if active_stop>0 and ltp<=active_stop:
                        self.execution.exit_final(p,reason="TRAILING_STOP");continue
                started=p.get("partial_exit_filled_at")
                if started and not final_pending:
                    try:elapsed=(datetime.now()-datetime.fromisoformat(str(started))).total_seconds()/60
                    except Exception:elapsed=0
                    threshold=float(p.get("partial_exit_price") or p["one_r"]) * (1+SETTINGS.post_partial_stagnation_pct/100)
                    if elapsed>=SETTINGS.post_partial_time_stop_minutes and mp<threshold:self.execution.exit_final(p,reason="TIME_STAGNATION");continue
                if not final_pending and ltp>=float(p["two_r"]):self.execution.exit_final(p,reason="FINAL_TARGET")
        if datetime.now(IST).time()>=SETTINGS.trading_end:self.flatten_all()
    def flatten_all(self):
        for _,p in list(self.store.positions().items()):
            if p.get("manual_exit_pending"):continue
            try:self.execution.exit_final(p,reason="EOD_FLATTEN")
            except Exception as exc:logger.exception("FLATTEN ERROR %s: %s",p.get("symbol"),exc)
