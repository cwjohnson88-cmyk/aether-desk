"""Blotter and progress stats from the paper ledger. Never invents fills."""

from __future__ import annotations

import csv
from typing import Any

from aether.paths import trades_path


def load_trades() -> list[dict[str, Any]]:
    path = trades_path()
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows


def _f(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def blotter_stats(trades: list[dict[str, Any]], book: dict[str, Any]) -> dict[str, Any]:
    closed: list[dict[str, Any]] = []
    for t in trades:
        pnl = _f(t.get("pnl_usd"))
        if pnl is None:
            continue
        row = dict(t)
        row["pnl_usd"] = pnl
        closed.append(row)

    pnls = [t["pnl_usd"] for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    n = len(pnls)
    start = float(book.get("starting_equity") or 100000.0)
    equity = float(book.get("equity") or start)

    curve = [{"t": "start", "eq": start, "label": "start"}]
    run = start
    for t in closed:
        run += float(t["pnl_usd"])
        curve.append({"t": t.get("ts") or "", "eq": run, "label": t.get("id") or ""})
    if not closed or abs(curve[-1]["eq"] - equity) > 1e-6:
        curve.append({"t": "now", "eq": equity, "label": "mark"})

    return {
        "n_fills": len(trades),
        "n_closed": n,
        "n_wins": len(wins),
        "n_losses": len(losses),
        "hit_rate": (len(wins) / n * 100.0) if n else None,
        "avg_win": (sum(wins) / len(wins)) if wins else None,
        "avg_loss": (sum(losses) / len(losses)) if losses else None,
        "avg_pnl": (sum(pnls) / n) if n else None,
        "gross_closed_pnl": sum(pnls) if pnls else 0.0,
        "curve": curve,
    }


def trades_newest(trades: list[dict[str, Any]], limit: int = 80) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in reversed(trades[-limit:]):
        row = dict(t)
        row["pnl_num"] = _f(t.get("pnl_usd"))
        row["price_num"] = _f(t.get("price"))
        row["qty_num"] = _f(t.get("qty"))
        out.append(row)
    return out
