from __future__ import annotations

from typing import Iterable, Literal

Regime = Literal["uptrend", "downtrend", "range", "unknown"]


def _f(xs: Iterable[float]) -> list[float]:
    return [float(x) for x in xs]


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 20) -> float | None:
    highs, lows, closes = _f(highs), _f(lows), _f(closes)
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return None
    trs: list[float] = []
    for i in range(1, n):
        h, l, pc = highs[i], lows[i], closes[i - 1]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    window = trs[-period:]
    if len(window) < period:
        return None
    return sum(window) / period


def sma(values: list[float], period: int) -> float | None:
    values = _f(values)
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def regime(closes: list[float], atr20: float | None) -> Regime:
    closes = _f(closes)
    if len(closes) < 21 or not atr20 or atr20 <= 0:
        return "unknown"
    ma = sma(closes, 20)
    if ma is None:
        return "unknown"
    slope = (closes[-1] - closes[-20]) / 20.0
    last = closes[-1]
    # Slope vs a fraction of ATR, plus price vs MA.
    if last > ma and slope > 0.05 * atr20:
        return "uptrend"
    if last < ma and slope < -0.05 * atr20:
        return "downtrend"
    return "range"


def unusual_move(last: float | None, prev: float | None, atr20: float | None, k: float = 1.5) -> bool:
    if last is None or prev is None or atr20 is None or atr20 <= 0:
        return False
    return abs(last - prev) > k * atr20


def pct_change(last: float | None, base: float | None) -> float | None:
    if last is None or base is None or base == 0:
        return None
    return (last / base - 1.0) * 100.0
