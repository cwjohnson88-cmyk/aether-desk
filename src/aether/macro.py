from __future__ import annotations

from aether.models import Quote
from aether.scan import fmt_pct, fmt_px


def cross_asset_paragraph(quotes: dict[str, Quote]) -> str:
    def g(sid: str) -> Quote | None:
        return quotes.get(sid)

    dxy, tnx, gld, btc, spy = g("DXY"), g("US10Y"), g("GLD"), g("BTC-USD"), g("SPY")
    eurusd, usdjpy = g("EURUSD"), g("USDJPY")

    bits: list[str] = []
    for name, q in [("DXY", dxy), ("US10Y", tnx), ("GLD", gld), ("BTC-USD", btc), ("SPY", spy)]:
        if q is None:
            bits.append(f"{name} UNKNOWN (not in scan).")
        elif q.quality == "unknown" or q.last is None:
            bits.append(f"{name} UNKNOWN ({q.reason or 'no print'}).")
        else:
            bits.append(f"{name} {fmt_px(q)} day {fmt_pct(q.pct_day)} ({q.regime}).")

    rhyme = []
    def day(q: Quote | None) -> float | None:
        return None if q is None else q.pct_day

    spy_d, btc_d, dxy_d, gld_d = day(spy), day(btc), day(dxy), day(gld)
    if spy_d is not None and btc_d is not None:
        if spy_d * btc_d > 0:
            rhyme.append("SPY and BTC are rhyming on the day (both risk-sensitive prints moving the same way).")
        else:
            rhyme.append("SPY and BTC are diverging on the day — treat BTC as a noisy risk proxy, not a confirmation.")
    elif spy_d is None or btc_d is None:
        rhyme.append("Cannot score SPY/BTC rhyme: at least one print is UNKNOWN.")

    if dxy_d is not None and eurusd is not None and eurusd.pct_day is not None:
        if dxy_d * eurusd.pct_day < 0:
            rhyme.append("DXY vs EURUSD is the usual inverse on the day.")
        else:
            rhyme.append("DXY and EURUSD are not showing the usual inverse today — FX/dollar tape may be crossed by rates or risk.")
    if usdjpy is not None and tnx is not None and usdjpy.pct_day is not None and tnx.pct_day is not None:
        if usdjpy.pct_day * tnx.pct_day > 0:
            rhyme.append("USDJPY and 10y yield are rhyming (yield-up / dollar-yen-up is the textbook tape).")
        else:
            rhyme.append("USDJPY and 10y yield are diverging — do not force a rates story.")
    if gld_d is not None and dxy_d is not None:
        if gld_d * dxy_d < 0:
            rhyme.append("Gold vs DXY is the usual inverse on the day.")
        else:
            rhyme.append("Gold and DXY are not inversely printing today.")

    missing = [n for n, q in [("DXY", dxy), ("US10Y", tnx)] if q is None or q.quality != "ok"]
    if missing:
        rhyme.append("Macro gap: " + ", ".join(missing) + " not live — do not invent a dollar/yield narrative.")

    return " ".join(bits) + " " + " ".join(rhyme)
