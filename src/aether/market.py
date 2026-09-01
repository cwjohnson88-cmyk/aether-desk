"""Public market data. Never invents a print. UNKNOWN if all sources fail."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from aether import config
from aether.activity import log
from aether.indicators import atr, pct_change, regime, unusual_move
from aether.models import Quote
from aether.paths import quotes_snapshot_path

USER_AGENT = "aether-desk/0.1 (paper-research; +local)"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_snapshot() -> dict[str, Any]:
    path = quotes_snapshot_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_snapshot(quotes: dict[str, Quote]) -> None:
    blob = {
        "as_of": _now_iso(),
        "quotes": {k: q.to_dict() for k, q in quotes.items()},
    }
    path = quotes_snapshot_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    tmp.replace(path)


def _quote_from_ohlc(
    row: dict[str, Any],
    *,
    source: str,
    as_of: str,
    highs: list[float],
    lows: list[float],
    closes: list[float],
    last: float,
    prev_close: float | None,
    week_close: float | None,
    headlines: list[str] | None = None,
) -> Quote:
    atr20 = atr(highs, lows, closes, 20)
    last_reg = regime(closes, atr20)
    prev = prev_close if prev_close is not None else (closes[-2] if len(closes) >= 2 else None)
    unusual = unusual_move(last, prev, atr20)
    news = headlines or []
    vacuum = unusual and not news
    return Quote(
        symbol=str(row["id"]),
        asset_class=str(row.get("class") or "unknown"),
        last=last,
        prev_close=prev,
        pct_day=pct_change(last, prev),
        pct_week=pct_change(last, week_close),
        high=highs[-1] if highs else None,
        low=lows[-1] if lows else None,
        atr20=atr20,
        regime=last_reg,
        unusual=unusual,
        news_vacuum=vacuum,
        source=source,
        as_of=as_of,
        quality="ok",
        reason="",
        tradable=bool(row.get("tradable", True)),
        cluster=str(row.get("cluster") or ""),
        usd_quoted=bool(row.get("usd_quoted", True)),
        yahoo=str(row.get("yahoo") or ""),
        bars_1d_closes=closes[-60:],
        headlines=news[:5],
    )


def _fetch_yfinance(row: dict[str, Any]) -> Quote | None:
    yahoo = str(row.get("yahoo") or "")
    if not yahoo:
        return None
    try:
        import yfinance as yf
    except ImportError:
        return None
    try:
        t = yf.Ticker(yahoo)
        hist = t.history(period="6mo", interval="1d", auto_adjust=True)
        if hist is None or getattr(hist, "empty", True) or len(hist) < 2:
            return None
        closes = [float(x) for x in hist["Close"].tolist() if x == x]
        highs = [float(x) for x in hist["High"].tolist() if x == x]
        lows = [float(x) for x in hist["Low"].tolist() if x == x]
        if len(closes) < 2:
            return None
        last = closes[-1]
        prev = closes[-2]
        week_close = closes[-6] if len(closes) >= 6 else closes[0]
        as_of = str(hist.index[-1])
        headlines: list[str] = []
        try:
            news = getattr(t, "news", None) or []
            for item in news[:8]:
                title = ""
                if isinstance(item, dict):
                    title = str(item.get("title") or item.get("headline") or "")
                    content = item.get("content") if isinstance(item.get("content"), dict) else {}
                    if not title and content:
                        title = str(content.get("title") or "")
                if title:
                    headlines.append(title)
        except Exception:
            headlines = []
        return _quote_from_ohlc(
            row,
            source=f"yfinance:{yahoo}",
            as_of=as_of,
            highs=highs,
            lows=lows,
            closes=closes,
            last=last,
            prev_close=prev,
            week_close=week_close,
            headlines=headlines,
        )
    except Exception as exc:
        log("data", f"yfinance fail {row.get('id')}: {exc}")
        return None


def _fetch_stooq(row: dict[str, Any], client: httpx.Client) -> Quote | None:
    sid = str(row.get("stooq") or "").strip()
    if not sid:
        return None
    url = f"https://stooq.com/q/d/l/?s={sid}&i=d"
    try:
        r = client.get(url, timeout=12.0)
        r.raise_for_status()
        text = r.text.strip()
        if not text or text.lower().startswith("<"):
            return None
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) < 3:
            return None
        # Date,Open,High,Low,Close,Volume
        highs: list[float] = []
        lows: list[float] = []
        closes: list[float] = []
        dates: list[str] = []
        for ln in lines[1:]:
            parts = ln.split(",")
            if len(parts) < 5:
                continue
            try:
                dates.append(parts[0])
                highs.append(float(parts[2]))
                lows.append(float(parts[3]))
                closes.append(float(parts[4]))
            except ValueError:
                continue
        if len(closes) < 2:
            return None
        last = closes[-1]
        prev = closes[-2]
        week_close = closes[-6] if len(closes) >= 6 else closes[0]
        return _quote_from_ohlc(
            row,
            source=f"stooq:{sid}",
            as_of=dates[-1],
            highs=highs,
            lows=lows,
            closes=closes,
            last=last,
            prev_close=prev,
            week_close=week_close,
            headlines=[],
        )
    except Exception as exc:
        log("data", f"stooq fail {row.get('id')}: {exc}")
        return None


def _from_snapshot(row: dict[str, Any], snap: dict[str, Any]) -> Quote:
    q = (snap.get("quotes") or {}).get(row["id"])
    if not q:
        return Quote.unknown(
            str(row["id"]),
            str(row.get("class") or "unknown"),
            "no live print and no last-good snapshot",
            tradable=row.get("tradable", True),
            cluster=row.get("cluster") or "",
            usd_quoted=row.get("usd_quoted", True),
            yahoo=row.get("yahoo") or "",
        )
    q = dict(q)
    q["quality"] = "stale"
    q["reason"] = f"using last-good snapshot from {snap.get('as_of') or q.get('as_of') or 'UNKNOWN'}"
    q["source"] = f"snapshot:{q.get('source') or 'unknown'}"
    try:
        return Quote(**{k: q.get(k) for k in Quote.__dataclass_fields__})
    except TypeError:
        return Quote.unknown(
            str(row["id"]),
            str(row.get("class") or "unknown"),
            "snapshot unreadable",
            tradable=row.get("tradable", True),
            cluster=row.get("cluster") or "",
            usd_quoted=row.get("usd_quoted", True),
        )


def fetch_one(row: dict[str, Any], client: httpx.Client, snap: dict[str, Any], retry: bool = True) -> Quote:
    q = _fetch_yfinance(row)
    if q is None and retry:
        time.sleep(1.2)
        q = _fetch_yfinance(row)
    if q is None:
        q = _fetch_stooq(row, client)
    if q is None and retry:
        time.sleep(0.8)
        q = _fetch_stooq(row, client)
    if q is None:
        q = _from_snapshot(row, snap)
    return q


def fetch_universe(*, retry: bool = True) -> dict[str, Quote]:
    snap = load_snapshot()
    rows = config.all_symbol_rows()
    out: dict[str, Quote] = {}
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for row in rows:
            sid = str(row["id"])
            out[sid] = fetch_one(row, client, snap, retry=retry)
    # Merge: keep previous last-good for unknown only if we already used snapshot
    save_snapshot(out)
    unknown = [k for k, v in out.items() if v.quality == "unknown"]
    stale = [k for k, v in out.items() if v.quality == "stale"]
    log(
        "scan",
        f"fetched {len(out)} symbols; unknown={len(unknown)} stale={len(stale)}",
        unknown=unknown,
        stale=stale,
    )
    return out


def marks_from_quotes(quotes: dict[str, Quote]) -> dict[str, float]:
    return {k: v.last for k, v in quotes.items() if v.last is not None}


def usd_quoted_map() -> dict[str, bool]:
    return {str(r["id"]): bool(r.get("usd_quoted", True)) for r in config.all_symbol_rows()}
