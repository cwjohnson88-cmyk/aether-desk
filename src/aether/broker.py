"""In-process paper broker. Never sends orders anywhere."""

from __future__ import annotations

import csv
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from aether import config
from aether.activity import log
from aether.paths import account_path, trades_path

SCHEMA = "aether.account.v1"
TRADE_FIELDS = [
    "id",
    "ts",
    "symbol",
    "side",
    "qty",
    "price",
    "notional_usd",
    "reason",
    "why",
    "pnl_usd",
    "ticket_id",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(config.timezone_name())
    except Exception:
        return ZoneInfo("America/Chicago")


def local_now() -> datetime:
    return utcnow().astimezone(_tz())


def seed_account(starting: float | None = None) -> dict[str, Any]:
    eq = float(starting if starting is not None else config.risk().get("starting_equity", 100000.0))
    now = local_now()
    monday = now.date()
    # week starts Monday
    monday = monday.fromordinal(monday.toordinal() - monday.weekday())
    return {
        "schema": SCHEMA,
        "currency": "USD",
        "starting_equity": eq,
        "cash": eq,
        "day_start_equity": eq,
        "week_start_equity": eq,
        "day_start_date": now.date().isoformat(),
        "week_start_date": monday.isoformat(),
        "halt_daily": False,
        "halt_weekly": False,
        "next_ticket_id": 1,
        "positions": [],
        "pending": [],
        "updated_at": utcnow().isoformat(),
    }


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def load_account() -> dict[str, Any]:
    path = account_path()
    if not path.exists():
        acct = seed_account()
        save_account(acct)
        return acct
    acct = json.loads(path.read_text(encoding="utf-8"))
    return rollover_halts(acct)


def save_account(acct: dict[str, Any]) -> None:
    acct = deepcopy(acct)
    acct["updated_at"] = utcnow().isoformat()
    _atomic_write(account_path(), json.dumps(acct, indent=2) + "\n")


def spread_bps(asset_class: str, risk_cfg: dict[str, Any] | None = None) -> float:
    risk_cfg = risk_cfg or config.risk()
    table = risk_cfg.get("spreads_bps") or {}
    return float(table.get(asset_class, table.get("equity", 2.0)))


def fill_price(
    mid: float,
    side: str,
    asset_class: str,
    risk_cfg: dict[str, Any] | None = None,
    *,
    is_limit: bool = False,
    limit_price: float | None = None,
) -> float:
    """Buy pays mid + half-spread + slippage; sell receives mid - half-spread - slippage."""
    risk_cfg = risk_cfg or config.risk()
    sp = spread_bps(asset_class, risk_cfg)
    sl = float(risk_cfg.get("slippage_bps", 2.0))
    half = mid * (sp / 10_000.0) / 2.0
    slip = mid * (sl / 10_000.0)
    if side == "buy":
        px = mid + half + slip
        if is_limit and limit_price is not None:
            px = min(px, float(limit_price))
    else:
        px = mid - half - slip
        if is_limit and limit_price is not None:
            px = max(px, float(limit_price))
    return px


def point_value(last: float, usd_quoted: bool) -> float:
    """USD per 1.0 price point per 1.0 unit of qty."""
    if usd_quoted:
        return 1.0
    if last == 0:
        return 0.0
    return 1.0 / last


def notional_usd(qty: float, price: float, usd_quoted: bool) -> float:
    return abs(qty) * price * point_value(price, usd_quoted)


def signed_qty(pos: dict[str, Any]) -> float:
    q = float(pos["qty"])
    return q if pos["side"] == "buy" else -q


def position_mtm(pos: dict[str, Any], last: float, usd_quoted: bool) -> float:
    return signed_qty(pos) * last * point_value(last, usd_quoted)


def mark_equity(acct: dict[str, Any], marks: dict[str, float], usd_quoted: dict[str, bool] | None = None) -> float:
    usd_quoted = usd_quoted or {}
    total = float(acct["cash"])
    for pos in acct.get("positions") or []:
        last = marks.get(pos["symbol"])
        if last is None:
            last = float(pos["entry"])
        uq = usd_quoted.get(pos["symbol"], bool(pos.get("usd_quoted", True)))
        total += position_mtm(pos, float(last), uq)
    return total


def apply_marks(acct: dict[str, Any], marks: dict[str, float], usd_quoted: dict[str, bool] | None = None) -> dict[str, Any]:
    """Update unrealized P&L and trigger stops/targets. Returns a new account dict."""
    acct = deepcopy(acct)
    usd_quoted = usd_quoted or {}
    for pos in list(acct.get("positions") or []):
        last = marks.get(pos["symbol"])
        if last is None:
            continue
        last = float(last)
        uq = usd_quoted.get(pos["symbol"], bool(pos.get("usd_quoted", True)))
        live = next((p for p in acct.get("positions") or [] if p["id"] == pos["id"]), None)
        if live is None:
            continue
        live["last_mark"] = last
        live["unrealized_usd"] = position_mtm(live, last, uq) - signed_qty(live) * float(live["entry"]) * point_value(
            float(live["entry"]), uq
        )
        stop = live.get("stop")
        target = live.get("target")
        hit = None
        if live["side"] == "buy":
            if stop is not None and last <= float(stop):
                hit = "stop"
            elif target is not None and last >= float(target):
                hit = "target"
        else:
            if stop is not None and last >= float(stop):
                hit = "stop"
            elif target is not None and last <= float(target):
                hit = "target"
        if hit:
            acct, _ = close_position(acct, live["id"], last, reason=hit, why=f"auto {hit}")
    return acct


def rollover_halts(acct: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    acct = deepcopy(acct)
    now = now or local_now()
    today = now.date().isoformat()
    monday = now.date()
    monday = monday.fromordinal(monday.toordinal() - monday.weekday()).isoformat()
    marks: dict[str, float] = {}
    uq: dict[str, bool] = {}
    for p in acct.get("positions") or []:
        marks[p["symbol"]] = float(p.get("last_mark") or p["entry"])
        uq[p["symbol"]] = bool(p.get("usd_quoted", True))
    eq = mark_equity(acct, marks, uq)
    if acct.get("day_start_date") != today:
        acct["day_start_date"] = today
        acct["day_start_equity"] = eq
        acct["halt_daily"] = False
    if acct.get("week_start_date") != monday:
        acct["week_start_date"] = monday
        acct["week_start_equity"] = eq
        acct["halt_weekly"] = False
    risk_cfg = config.risk()
    day_start = float(acct.get("day_start_equity") or eq)
    week_start = float(acct.get("week_start_equity") or eq)
    if day_start > 0 and (eq / day_start - 1.0) * 100.0 <= -float(risk_cfg.get("daily_loss_halt_pct", 3.0)):
        acct["halt_daily"] = True
    if week_start > 0 and (eq / week_start - 1.0) * 100.0 <= -float(risk_cfg.get("weekly_loss_halt_pct", 6.0)):
        acct["halt_weekly"] = True
    return acct


def _append_trade(row: dict[str, Any]) -> None:
    path = trades_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TRADE_FIELDS, extrasaction="ignore")
        if new_file:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in TRADE_FIELDS})


def _next_ids(acct: dict[str, Any]) -> tuple[str, str]:
    n = int(acct.get("next_ticket_id") or 1)
    acct["next_ticket_id"] = n + 1
    tid = f"T{n}"
    return tid, f"F{n}"


def open_market(
    acct: dict[str, Any],
    *,
    symbol: str,
    side: str,
    qty: float,
    mid: float,
    asset_class: str,
    usd_quoted: bool,
    stop: float | None,
    target: float | None,
    why: str,
    risk_cfg: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    acct = deepcopy(acct)
    risk_cfg = risk_cfg or config.risk()
    qty = float(qty)
    if qty <= 0:
        raise ValueError("qty must be positive")
    if side not in ("buy", "sell"):
        raise ValueError("side must be buy or sell")
    px = fill_price(mid, side, asset_class, risk_cfg)
    notion = notional_usd(qty, px, usd_quoted)
    ticket_id, fill_id = _next_ids(acct)
    signed = qty if side == "buy" else -qty
    # Cash: long pays, short receives
    acct["cash"] = float(acct["cash"]) - signed * px * point_value(px, usd_quoted)
    pos = {
        "id": ticket_id,
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "entry": px,
        "stop": stop,
        "target": target,
        "why": why,
        "opened_at": utcnow().isoformat(),
        "average_down_count": 0,
        "asset_class": asset_class,
        "usd_quoted": usd_quoted,
        "last_mark": mid,
        "unrealized_usd": 0.0,
    }
    acct.setdefault("positions", []).append(pos)
    trade = {
        "id": fill_id,
        "ts": utcnow().isoformat(),
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "price": px,
        "notional_usd": round(notion, 6),
        "reason": "entry",
        "why": why,
        "pnl_usd": "",
        "ticket_id": ticket_id,
    }
    _append_trade(trade)
    log("ticket", f"paper {side} {qty} {symbol} @ {px:.6f}", ticket_id=ticket_id, reason="entry")
    return acct, trade


def close_position(
    acct: dict[str, Any],
    ticket_id: str,
    mid: float,
    *,
    reason: str,
    why: str,
    risk_cfg: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    acct = deepcopy(acct)
    risk_cfg = risk_cfg or config.risk()
    pos = next((p for p in acct.get("positions") or [] if p["id"] == ticket_id), None)
    if pos is None:
        raise KeyError(f"no open ticket {ticket_id}")
    close_side = "sell" if pos["side"] == "buy" else "buy"
    px = fill_price(mid, close_side, pos.get("asset_class", "equity"), risk_cfg)
    qty = float(pos["qty"])
    uq = bool(pos.get("usd_quoted", True))
    entry = float(pos["entry"])
    signed = signed_qty(pos)
    # Reverse the cash: add back signed * exit * pv
    acct["cash"] = float(acct["cash"]) + signed * px * point_value(px, uq)
    pnl = signed * (px - entry) * point_value(entry if uq else px, uq)
    if not uq:
        # USDJPY-style: pnl in quote / price
        pnl = signed * (px - entry) * point_value(px, False)
    notion = notional_usd(qty, px, uq)
    n = int(acct.get("next_ticket_id") or 1)
    fill_id = f"X{n}"
    acct["next_ticket_id"] = n + 1
    acct["positions"] = [p for p in acct["positions"] if p["id"] != ticket_id]
    trade = {
        "id": fill_id,
        "ts": utcnow().isoformat(),
        "symbol": pos["symbol"],
        "side": close_side,
        "qty": qty,
        "price": px,
        "notional_usd": round(notion, 6),
        "reason": reason,
        "why": why,
        "pnl_usd": round(pnl, 6),
        "ticket_id": ticket_id,
    }
    _append_trade(trade)
    log("close", f"paper close {ticket_id} {pos['symbol']} {reason} pnl={pnl:.2f}", ticket_id=ticket_id, reason=reason)
    return acct, trade


def add_to_position(
    acct: dict[str, Any],
    ticket_id: str,
    *,
    qty: float,
    mid: float,
    why: str,
    risk_cfg: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Average in (including the one allowed average-down)."""
    acct = deepcopy(acct)
    risk_cfg = risk_cfg or config.risk()
    pos = next((p for p in acct.get("positions") or [] if p["id"] == ticket_id), None)
    if pos is None:
        raise KeyError(f"no open ticket {ticket_id}")
    qty = float(qty)
    px = fill_price(mid, pos["side"], pos.get("asset_class", "equity"), risk_cfg)
    old_qty = float(pos["qty"])
    old_entry = float(pos["entry"])
    new_qty = old_qty + qty
    new_entry = (old_entry * old_qty + px * qty) / new_qty
    signed_add = qty if pos["side"] == "buy" else -qty
    uq = bool(pos.get("usd_quoted", True))
    acct["cash"] = float(acct["cash"]) - signed_add * px * point_value(px, uq)
    is_down = (pos["side"] == "buy" and px < old_entry) or (pos["side"] == "sell" and px > old_entry)
    if is_down:
        pos["average_down_count"] = int(pos.get("average_down_count") or 0) + 1
    pos["qty"] = new_qty
    pos["entry"] = new_entry
    n = int(acct.get("next_ticket_id") or 1)
    fill_id = f"A{n}"
    acct["next_ticket_id"] = n + 1
    trade = {
        "id": fill_id,
        "ts": utcnow().isoformat(),
        "symbol": pos["symbol"],
        "side": pos["side"],
        "qty": qty,
        "price": px,
        "notional_usd": round(notional_usd(qty, px, uq), 6),
        "reason": "add",
        "why": why,
        "pnl_usd": "",
        "ticket_id": ticket_id,
    }
    _append_trade(trade)
    return acct, trade


def status_view(acct: dict[str, Any], marks: dict[str, float] | None = None) -> dict[str, Any]:
    marks = marks or {}
    uq = {p["symbol"]: bool(p.get("usd_quoted", True)) for p in acct.get("positions") or []}
    for p in acct.get("positions") or []:
        if p["symbol"] not in marks:
            marks[p["symbol"]] = float(p.get("last_mark") or p["entry"])
    eq = mark_equity(acct, marks, uq)
    day0 = float(acct.get("day_start_equity") or eq)
    week0 = float(acct.get("week_start_equity") or eq)
    start = float(acct.get("starting_equity") or eq)
    exposure: dict[str, float] = {}
    open_risk = 0.0
    pos_out = []
    for p in acct.get("positions") or []:
        last = float(marks.get(p["symbol"], p["entry"]))
        u = bool(p.get("usd_quoted", True))
        mtm = position_mtm(p, last, u)
        ur = mtm - signed_qty(p) * float(p["entry"]) * point_value(float(p["entry"]), u)
        cls = p.get("asset_class") or "unknown"
        exposure[cls] = exposure.get(cls, 0.0) + abs(notional_usd(float(p["qty"]), last, u))
        if p.get("stop") is not None:
            open_risk += abs(float(p["qty"])) * abs(float(p["entry"]) - float(p["stop"])) * point_value(
                float(p["entry"]), u
            )
        pos_out.append(
            {
                **p,
                "last": last,
                "mtm_usd": mtm,
                "unrealized_usd": ur,
            }
        )
    return {
        "equity": eq,
        "cash": float(acct["cash"]),
        "starting_equity": start,
        "day_pnl": eq - day0,
        "day_pnl_pct": (eq / day0 - 1.0) * 100.0 if day0 else 0.0,
        "week_pnl": eq - week0,
        "week_pnl_pct": (eq / week0 - 1.0) * 100.0 if week0 else 0.0,
        "total_pnl": eq - start,
        "open_risk_usd": open_risk,
        "halt_daily": bool(acct.get("halt_daily")),
        "halt_weekly": bool(acct.get("halt_weekly")),
        "positions": pos_out,
        "exposure_by_class": exposure,
        "n_open": len(pos_out),
        "paper_only": True,
    }
