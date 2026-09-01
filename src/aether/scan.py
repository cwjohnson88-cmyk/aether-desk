from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from aether.activity import log
from aether.indicators import pct_change
from aether.market import fetch_universe, marks_from_quotes
from aether.models import Quote
from aether.paths import scan_snapshot_path


def _corr(a: list[float], b: list[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 10:
        return None
    a, b = a[-n:], b[-n:]
    rets_a = [(a[i] / a[i - 1] - 1.0) for i in range(1, n) if a[i - 1]]
    rets_b = [(b[i] / b[i - 1] - 1.0) for i in range(1, n) if b[i - 1]]
    m = min(len(rets_a), len(rets_b))
    if m < 8:
        return None
    xa, xb = rets_a[-m:], rets_b[-m:]
    ma = sum(xa) / m
    mb = sum(xb) / m
    cov = sum((x - ma) * (y - mb) for x, y in zip(xa, xb)) / m
    va = sum((x - ma) ** 2 for x in xa) / m
    vb = sum((y - mb) ** 2 for y in xb) / m
    if va <= 0 or vb <= 0:
        return None
    return cov / (va ** 0.5 * vb ** 0.5)


def correlation_snapshot(quotes: dict[str, Quote], threshold: float = 0.7) -> list[dict[str, Any]]:
    ids = [k for k, q in quotes.items() if len(q.bars_1d_closes) >= 12]
    pairs: list[dict[str, Any]] = []
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            c = _corr(quotes[a].bars_1d_closes, quotes[b].bars_1d_closes)
            if c is None:
                continue
            if abs(c) >= threshold:
                pairs.append({"a": a, "b": b, "corr": round(c, 3)})
    pairs.sort(key=lambda x: abs(x["corr"]), reverse=True)
    return pairs[:24]


def heat(quotes: dict[str, Quote]) -> dict[str, dict[str, float | None]]:
    buckets: dict[str, list[float]] = {}
    for q in quotes.values():
        if q.pct_day is None:
            continue
        buckets.setdefault(q.asset_class, []).append(q.pct_day)
    out: dict[str, dict[str, float | None]] = {}
    for cls, xs in buckets.items():
        out[cls] = {
            "n": len(xs),
            "avg_pct_day": sum(xs) / len(xs) if xs else None,
            "max_pct_day": max(xs) if xs else None,
            "min_pct_day": min(xs) if xs else None,
        }
    return out


def run_scan(*, retry: bool = True, label: str = "scan") -> dict[str, Any]:
    quotes = fetch_universe(retry=retry)
    unusual = [q.to_dict() for q in quotes.values() if q.unusual]
    unknown = [q.symbol for q in quotes.values() if q.quality == "unknown"]
    stale = [q.symbol for q in quotes.values() if q.quality == "stale"]
    payload = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "n": len(quotes),
        "unusual": unusual,
        "unknown": unknown,
        "stale": stale,
        "heat": heat(quotes),
        "corr_high": correlation_snapshot(quotes),
        "quotes": {k: v.to_dict() for k, v in quotes.items()},
        "marks": marks_from_quotes(quotes),
    }
    path = scan_snapshot_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)
    log("scan", f"{label}: {len(unusual)} unusual, {len(unknown)} UNKNOWN, {len(stale)} stale")
    return payload


def load_scan() -> dict[str, Any]:
    path = scan_snapshot_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_px(q: Quote | dict[str, Any]) -> str:
    if isinstance(q, Quote):
        last, qual, reason = q.last, q.quality, q.reason
    else:
        last, qual, reason = q.get("last"), q.get("quality"), q.get("reason")
    if last is None or qual == "unknown":
        return f"UNKNOWN ({reason or 'no print'})"
    tag = "" if qual == "ok" else f" [{qual}]"
    return f"{last:.6g}{tag}"


def fmt_pct(v: float | None) -> str:
    if v is None:
        return "UNKNOWN"
    return f"{v:+.2f}%"
