"""Risk Officer gates. 'Do nothing' is a valid output. Never loosens limits here."""

from __future__ import annotations

from typing import Any

from aether import config
from aether.broker import mark_equity, notional_usd, point_value


def _equity(acct: dict[str, Any], mid: float | None, symbol: str, usd_quoted: bool) -> float:
    marks = {}
    uq = {}
    for p in acct.get("positions") or []:
        marks[p["symbol"]] = float(p.get("last_mark") or p["entry"])
        uq[p["symbol"]] = bool(p.get("usd_quoted", True))
    if mid is not None:
        marks[symbol] = mid
        uq[symbol] = usd_quoted
    return mark_equity(acct, marks, uq)


def idea_risk_usd(qty: float, entry: float, stop: float | None, usd_quoted: bool) -> float | None:
    if stop is None:
        return None
    return abs(float(qty)) * abs(float(entry) - float(stop)) * point_value(entry, usd_quoted)


def cluster_of(symbol: str, risk_cfg: dict[str, Any] | None = None) -> str | None:
    risk_cfg = risk_cfg or config.risk()
    sid = symbol.upper()
    for name, members in (risk_cfg.get("clusters") or {}).items():
        if sid in {str(m).upper() for m in members}:
            return str(name)
    row = config.symbol_by_id(symbol)
    if row:
        return str(row.get("cluster") or "")
    return None


def last_closed_loss_qty(trades: list[dict[str, Any]], symbol: str) -> float | None:
    """If the most recent closed trade on symbol was a loss, return its qty."""
    closed = [t for t in trades if t.get("symbol") == symbol and t.get("reason") in ("stop", "target", "manual_close")]
    if not closed:
        return None
    last = closed[-1]
    try:
        pnl = float(last.get("pnl_usd") or 0)
    except (TypeError, ValueError):
        return None
    if pnl >= 0:
        return None
    try:
        return float(last.get("qty") or 0)
    except (TypeError, ValueError):
        return None


def check_ticket(
    acct: dict[str, Any],
    *,
    symbol: str,
    side: str,
    qty: float,
    entry: float,
    stop: float | None,
    usd_quoted: bool,
    trades: list[dict[str, Any]] | None = None,
    risk_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return {ok, code, detail}. ok=False blocks the Execution Clerk."""
    risk_cfg = risk_cfg or config.risk()
    trades = trades or []
    if not risk_cfg.get("paper_only", True):
        return {"ok": False, "code": "LIVE_FORBIDDEN", "detail": "Aether is paper-only. Refusing."}

    if acct.get("halt_daily"):
        return {"ok": False, "code": "HALT_DAILY", "detail": "Daily loss halt is on. No new tickets."}
    if acct.get("halt_weekly"):
        return {"ok": False, "code": "HALT_WEEKLY", "detail": "Weekly loss halt is on. No new tickets."}

    if risk_cfg.get("require_stop", True) and stop is None:
        return {"ok": False, "code": "STOP_REQUIRED", "detail": "Every idea needs a stop."}

    qty = float(qty)
    if qty <= 0:
        return {"ok": False, "code": "BAD_QTY", "detail": "Size must be positive."}

    positions = list(acct.get("positions") or [])
    max_open = int(risk_cfg.get("max_open_positions") or 6)
    existing = [p for p in positions if p["symbol"] == symbol and p["side"] == side]
    adding = bool(existing)

    if not adding and len(positions) >= max_open:
        return {
            "ok": False,
            "code": "MAX_OPEN",
            "detail": f"Already {len(positions)} open positions (max {max_open}).",
        }

    eq = _equity(acct, entry, symbol, usd_quoted)
    risk_usd = idea_risk_usd(qty, entry, stop, usd_quoted)
    cap = float(risk_cfg.get("max_risk_pct_per_idea", 2.0)) / 100.0 * eq
    if risk_usd is not None and risk_usd > cap + 1e-8:
        return {
            "ok": False,
            "code": "IDEA_RISK",
            "detail": f"Stop risk ${risk_usd:.2f} exceeds {risk_cfg.get('max_risk_pct_per_idea')}% of equity (${cap:.2f}).",
            "risk_usd": risk_usd,
            "cap_usd": cap,
            "equity": eq,
        }

    # Cluster cap
    cluster = cluster_of(symbol, risk_cfg)
    max_corr = int(risk_cfg.get("max_correlated_positions") or 6)
    if cluster:
        same = [p for p in positions if cluster_of(p["symbol"], risk_cfg) == cluster]
        if not adding and len(same) >= max_corr:
            return {
                "ok": False,
                "code": "CLUSTER",
                "detail": f"Cluster {cluster} already has {len(same)} names (max {max_corr}).",
            }

    # Average down more than once
    if adding:
        pos = existing[0]
        is_down = (side == "buy" and entry < float(pos["entry"])) or (
            side == "sell" and entry > float(pos["entry"])
        )
        max_ad = int(risk_cfg.get("max_average_down") or 1)
        if is_down and int(pos.get("average_down_count") or 0) >= max_ad:
            return {
                "ok": False,
                "code": "AVG_DOWN",
                "detail": f"Already averaged down {pos.get('average_down_count')} time(s); max {max_ad}.",
            }

    # No martingale: doubling size after a loss on the same symbol
    if not risk_cfg.get("martingale", False):
        lost_qty = last_closed_loss_qty(trades, symbol)
        if lost_qty and qty >= lost_qty * 2 - 1e-9 and not adding:
            return {
                "ok": False,
                "code": "MARTINGALE",
                "detail": f"Qty {qty} is >= 2x last losing size {lost_qty} on {symbol}.",
            }

    return {
        "ok": True,
        "code": "OK",
        "detail": "Risk Officer: ticket within limits.",
        "risk_usd": risk_usd,
        "cap_usd": cap,
        "equity": eq,
        "notional_usd": notional_usd(qty, entry, usd_quoted),
        "cluster": cluster,
    }
