from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Quality = Literal["ok", "stale", "unknown"]
Side = Literal["buy", "sell"]
Regime = Literal["uptrend", "downtrend", "range", "unknown"]
Direction = Literal["bull", "bear", "range"]


@dataclass
class Quote:
    symbol: str
    asset_class: str
    last: float | None
    prev_close: float | None
    pct_day: float | None
    pct_week: float | None
    high: float | None
    low: float | None
    atr20: float | None
    regime: Regime
    unusual: bool
    news_vacuum: bool
    source: str
    as_of: str
    quality: Quality
    reason: str
    tradable: bool
    cluster: str
    usd_quoted: bool
    yahoo: str = ""
    bars_1d_closes: list[float] = field(default_factory=list)
    headlines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def unknown(cls, symbol: str, asset_class: str, reason: str, **extra: Any) -> Quote:
        return cls(
            symbol=symbol,
            asset_class=asset_class,
            last=None,
            prev_close=None,
            pct_day=None,
            pct_week=None,
            high=None,
            low=None,
            atr20=None,
            regime="unknown",
            unusual=False,
            news_vacuum=False,
            source="none",
            as_of="",
            quality="unknown",
            reason=reason,
            tradable=bool(extra.get("tradable", False)),
            cluster=str(extra.get("cluster", "")),
            usd_quoted=bool(extra.get("usd_quoted", True)),
            yahoo=str(extra.get("yahoo", "")),
        )


@dataclass
class Hypothesis:
    id: str
    symbol: str
    direction: Direction
    horizon: str
    setup: str
    trigger: str
    entry_zone: str
    stop: float | None
    target: float | None
    r_multiple: float | None
    invalidation: str
    confidence: int
    contrary: str
    correlation_note: str
    status: str = "open"  # open | skipped | taken | invalidated

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
