from pathlib import Path
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from feature_engine import score_trade
from backtest.backtest_strategy_e import bars, sigs, load_index, find_bar


SIGNALS = Path.home() / "Desktop/algo/strategy_e_shared_data/chartink_csv/Backtest Intraday Claude Strategy.csv"
DATA_DIR = Path.home() / "Desktop/algo/strategy_e_shared_data/live_feature_cache"
MARKET_FILE = DATA_DIR / "NIFTY 50_5minute.csv"

OUTPUT = ROOT / "backtest_results/strategy_e_candidate_quality.csv"


def pct(a, b):
    return ((a - b) / b * 100.0) if b else 0.0


def future_metrics(bs, signal_idx, entry):
    """
    Diagnostic only.

    Future bars are intentionally used here to measure what happened AFTER
    the signal. These metrics are NEVER used by the trading engine.
    """

    future = bs[signal_idx + 1:]

    if not future:
        return {
            "entry_price": entry,
            "max_favorable_pct": 0.0,
            "max_adverse_pct": 0.0,
            "mfe_30m_pct": 0.0,
            "mae_30m_pct": 0.0,
            "mfe_60m_pct": 0.0,
            "mae_60m_pct": 0.0,
            "mfe_90m_pct": 0.0,
            "mae_90m_pct": 0.0,
            "close_30m_pct": 0.0,
            "close_60m_pct": 0.0,
            "close_90m_pct": 0.0,
            "close_eod_pct": 0.0,
        }

    signal_ts = bs[signal_idx]["ts"]

    def within(minutes):
        cutoff = signal_ts.timestamp() + minutes * 60
        return [
            x for x in future
            if x["ts"].timestamp() <= cutoff
        ]

    def metrics(window):
        if not window:
            return 0.0, 0.0, 0.0

        mfe = max(pct(x["high"], entry) for x in window)
        mae = min(pct(x["low"], entry) for x in window)
        close = pct(window[-1]["close"], entry)

        return mfe, mae, close

    m30 = metrics(within(30))
    m60 = metrics(within(60))
    m90 = metrics(within(90))
    meod = metrics(future)

    return {
        "entry_price": entry,

        "max_favorable_pct": meod[0],
        "max_adverse_pct": meod[1],

        "mfe_30m_pct": m30[0],
        "mae_30m_pct": m30[1],
        "close_30m_pct": m30[2],

        "mfe_60m_pct": m60[0],
        "mae_60m_pct": m60[1],
        "close_60m_pct": m60[2],

        "mfe_90m_pct": m90[0],
        "mae_90m_pct": m90[1],
        "close_90m_pct": m90[2],

        "close_eod_pct": meod[2],
    }


def main():

    print("Loading signals...")
    signals = sigs(SIGNALS)

    print("Loading universe...")
    idx = load_index(DATA_DIR)

    cache = {}

    print("Loading market...")
    market = bars(MARKET_FILE)

    rows = []

    start = time.fromisoformat("09:15")
    end = time.fromisoformat("15:00")

    for n, s in enumerate(signals, 1):

        f = (idx.get(s["symbol"]) or [None])[0]

        if not f:
            continue

        key = str(f)

        if key not in cache:
            cache[key] = bars(f)

        bs = cache[key]

        si = find_bar(bs, s["signal_time"])

        if si is None:
            continue

        b = bs[si]

        signal_range_pct = (
            (b["high"] - b["low"]) /
            max(b["low"], 1e-9) *
            100
        )

        if b["ts"].time() < start or b["ts"].time() > end:
            continue

        if signal_range_pct > 8:
            continue

        entry = (
            bs[si + 1]["open"]
            if si + 1 < len(bs)
            else b["close"]
        )

        # IMPORTANT:
        # Market data is filtered to information available at signal time.
        market_pt = [
            m for m in market
            if m["ts"] <= s["signal_time"]
        ]

        snap = score_trade(
            symbol=s["symbol"],
            signal_time=s["signal_time"],
            signal_open=b["open"],
            signal_high=b["high"],
            signal_low=b["low"],
            signal_close=b["close"],
            entry_price=entry,
            bars=bs[:si + 1],
            market_bars=market_pt,
            max_risk_pct=2.0,
            min_adx=18,
            min_relative_volume=1.0,
            min_atr_pct=0.20,
            max_atr_pct=4.0,
            score_threshold=65,
            start=start,
            end=end,
            allow_windows=[(start, end)],
            market_filter=True
        )

        fm = future_metrics(bs, si, entry)

        row = {
            "signal_time": s["signal_time"],
            "symbol": s["symbol"],
            "signal_row": s.get("row"),

            "signal_open": b["open"],
            "signal_high": b["high"],
            "signal_low": b["low"],
            "signal_close": b["close"],
            "signal_range_pct": signal_range_pct,

            "feature_score": snap.score,
            "feature_grade": snap.grade,
            "risk_pct": snap.risk_pct,
            "atr_pct": snap.atr_pct,
            "adx14": snap.adx14,
            "relative_volume": snap.relative_volume,
            "vwap": snap.vwap,

            "market_regime_ok": snap.market_regime_ok,
            "time_window_ok": snap.time_window_ok,
            "risk_ok": snap.risk_ok,

            "feature_reasons": "|".join(snap.reasons),

            **fm,
        }

        # Simple diagnostic classifications.
        row["score_pass_65"] = snap.score >= 65
        row["score_pass_75"] = snap.score >= 75

        row["profit_1pct_achieved"] = fm["max_favorable_pct"] >= 1.0
        row["profit_1_5pct_achieved"] = fm["max_favorable_pct"] >= 1.5
        row["profit_2pct_achieved"] = fm["max_favorable_pct"] >= 2.0

        row["loss_1pct_hit"] = fm["max_adverse_pct"] <= -1.0
        row["loss_1_5pct_hit"] = fm["max_adverse_pct"] <= -1.5
        row["loss_2pct_hit"] = fm["max_adverse_pct"] <= -2.0

        rows.append(row)

        if n % 25 == 0:
            print(f"Processed {n}/{len(signals)} signals...")

    if not rows:
        raise SystemExit("No candidates generated")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    fields = []
    seen = set()

    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                fields.append(k)

    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="ignore"
        )
        w.writeheader()
        w.writerows(rows)

    # ---------------------------------------------------------------
    # Diagnostic summary
    # ---------------------------------------------------------------

    def avg(field, subset):
        vals = [
            float(x[field])
            for x in subset
            if x.get(field) is not None
        ]
        return sum(vals) / len(vals) if vals else 0.0

    groups = {
        "all": rows,
        "score_65_plus": [x for x in rows if x["score_pass_65"]],
        "score_75_plus": [x for x in rows if x["score_pass_75"]],
        "mfe_1pct": [x for x in rows if x["profit_1pct_achieved"]],
        "mfe_1_5pct": [x for x in rows if x["profit_1_5pct_achieved"]],
        "mfe_2pct": [x for x in rows if x["profit_2pct_achieved"]],
    }

    summary = {
        "candidates_analyzed": len(rows),

        "score_distribution": {
            "min": min(x["feature_score"] for x in rows),
            "max": max(x["feature_score"] for x in rows),
            "avg": avg("feature_score", rows),
            "median": sorted(
                x["feature_score"] for x in rows
            )[len(rows)//2],
        },

        "adx": {
            "avg": avg("adx14", rows),
            "avg_score_65_plus": avg(
                "adx14",
                groups["score_65_plus"]
            ),
        },

        "relative_volume": {
            "avg": avg("relative_volume", rows),
            "avg_score_65_plus": avg(
                "relative_volume",
                groups["score_65_plus"]
            ),
        },

        "risk_pct": {
            "avg": avg("risk_pct", rows),
            "avg_score_65_plus": avg(
                "risk_pct",
                groups["score_65_plus"]
            ),
        },

        "mfe": {
            "avg_max_favorable_pct": avg(
                "max_favorable_pct", rows
            ),
            "avg_mfe_score_65_plus": avg(
                "max_favorable_pct",
                groups["score_65_plus"]
            ),
            "avg_mfe_score_75_plus": avg(
                "max_favorable_pct",
                groups["score_75_plus"]
            ),
        },

        "mae": {
            "avg_max_adverse_pct": avg(
                "max_adverse_pct", rows
            ),
            "avg_mae_score_65_plus": avg(
                "max_adverse_pct",
                groups["score_65_plus"]
            ),
            "avg_mae_score_75_plus": avg(
                "max_adverse_pct",
                groups["score_75_plus"]
            ),
        },

        "future_profit_hit_rates": {
            "mfe_1pct": 100 * sum(
                x["profit_1pct_achieved"] for x in rows
            ) / len(rows),

            "mfe_1_5pct": 100 * sum(
                x["profit_1_5pct_achieved"] for x in rows
            ) / len(rows),

            "mfe_2pct": 100 * sum(
                x["profit_2pct_achieved"] for x in rows
            ) / len(rows),
        },

        "future_loss_hit_rates": {
            "mae_1pct": 100 * sum(
                x["loss_1pct_hit"] for x in rows
            ) / len(rows),

            "mae_1_5pct": 100 * sum(
                x["loss_1_5pct_hit"] for x in rows
            ) / len(rows),

            "mae_2pct": 100 * sum(
                x["loss_2pct_hit"] for x in rows
            ) / len(rows),
        },

        "score_65_plus_count": len(groups["score_65_plus"]),
        "score_75_plus_count": len(groups["score_75_plus"]),

        "rejection_reasons": dict(
            Counter(
                reason
                for x in rows
                for reason in (
                    x["feature_reasons"].split("|")
                    if x["feature_reasons"]
                    else []
                )
            )
        ),
    }

    summary_path = OUTPUT.with_suffix(".json")

    summary_path.write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8"
    )

    print()
    print("=" * 70)
    print("STRATEGY E — CANDIDATE QUALITY ANALYSIS V1")
    print("=" * 70)
    print(f"Candidates analyzed : {len(rows)}")
    print(f"Score >= 65          : {len(groups['score_65_plus'])}")
    print(f"Score >= 75          : {len(groups['score_75_plus'])}")
    print()
    print(f"Average score        : {avg('feature_score', rows):.2f}")
    print(f"Average ADX          : {avg('adx14', rows):.2f}")
    print(f"Average Rel Volume   : {avg('relative_volume', rows):.2f}")
    print(f"Average risk %       : {avg('risk_pct', rows):.2f}")
    print()
    print(
        f"Avg max favorable    : "
        f"{avg('max_favorable_pct', rows):.2f}%"
    )
    print(
        f"Avg max adverse      : "
        f"{avg('max_adverse_pct', rows):.2f}%"
    )
    print()
    print(
        f"MFE >= 1%            : "
        f"{100*sum(x['profit_1pct_achieved'] for x in rows)/len(rows):.1f}%"
    )
    print(
        f"MFE >= 1.5%          : "
        f"{100*sum(x['profit_1_5pct_achieved'] for x in rows)/len(rows):.1f}%"
    )
    print(
        f"MFE >= 2%            : "
        f"{100*sum(x['profit_2pct_achieved'] for x in rows)/len(rows):.1f}%"
    )
    print()
    print(f"CSV : {OUTPUT.resolve()}")
    print(f"JSON: {summary_path.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
