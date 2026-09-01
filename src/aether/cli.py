"""Aether Desk CLI. Paper tickets only."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from typing import Any

from aether import config
from aether.activity import log
from aether.broker import (
    add_to_position,
    close_position,
    load_account,
    open_market,
    rollover_halts,
    save_account,
    status_view,
)
from aether.cycle import run_cycle
from aether.market import fetch_universe
from aether.paths import reports_daily, reports_weekly, trades_path
from aether.risk import check_ticket
from aether.scan import load_scan, run_scan


def _mid_for(symbol: str, quotes_marks: dict[str, float] | None = None) -> float:
    if quotes_marks and symbol in quotes_marks:
        return float(quotes_marks[symbol])
    scan = load_scan()
    marks = scan.get("marks") or {}
    if symbol in marks and marks[symbol] is not None:
        return float(marks[symbol])
    quotes = fetch_universe(retry=True)
    q = quotes.get(symbol)
    if q and q.last is not None:
        return float(q.last)
    raise SystemExit(f"UNKNOWN price for {symbol} — no live print and no snapshot. Ticket blocked.")


def _row(symbol: str) -> dict[str, Any]:
    row = config.symbol_by_id(symbol)
    if row is None:
        raise SystemExit(f"Unknown symbol {symbol}. Edit config/universe.yaml.")
    if not row.get("tradable", True):
        raise SystemExit(f"{symbol} is macro context, not tradable.")
    return row


def cmd_status(_args: argparse.Namespace) -> int:
    acct = rollover_halts(load_account())
    scan = load_scan()
    marks = dict(scan.get("marks") or {})
    book = status_view(acct, marks)
    print("AETHER DESK — PAPER TRADING ONLY")
    print(f"equity  ${book['equity']:,.2f}   cash ${book['cash']:,.2f}")
    print(f"day PnL ${book['day_pnl']:,.2f} ({book['day_pnl_pct']:+.2f}%)   week {book['week_pnl_pct']:+.2f}%")
    print(f"open {book['n_open']}   open risk ${book['open_risk_usd']:,.2f}   halt daily={book['halt_daily']} weekly={book['halt_weekly']}")
    if book["positions"]:
        print("positions:")
        for p in book["positions"]:
            print(
                f"  {p['id']} {p['side']} {p['qty']} {p['symbol']} entry={p['entry']:.6g} "
                f"last={p.get('last')} uPnL={p.get('unrealized_usd'):.2f}"
            )
    else:
        print("positions: none")
    quotes = (scan.get("quotes") or {}) if scan else {}
    if quotes:
        print("watchlist:")
        for sid, q in quotes.items():
            last = q.get("last")
            last_s = "UNKNOWN" if last is None else f"{last:.6g}"
            day = q.get("pct_day")
            day_s = "UNKNOWN" if day is None else f"{day:+.2f}%"
            wk = q.get("pct_week")
            wk_s = "UNKNOWN" if wk is None else f"{wk:+.2f}%"
            print(f"  {sid:10} {last_s:>12}  d {day_s:>8}  w {wk_s:>8}  {q.get('regime')}  {q.get('quality')}")
    else:
        print("watchlist: no scan yet — run `python -m aether scan`")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    payload = run_scan(retry=not args.no_retry, label=getattr(args, "label", "scan") or "scan")
    print(f"scan {payload['as_of']}  n={payload['n']}  unusual={len(payload['unusual'])}")
    print(f"UNKNOWN: {payload['unknown'] or 'none'}")
    print(f"stale:   {payload['stale'] or 'none'}")
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    result = run_cycle(mode="full", retry=not args.no_retry)
    print(result.get("brief"))
    print(result.get("phone"))
    print(f"ideas: {result.get('n_ideas')}  overseer: {result.get('overseer')}")
    return 0


def cmd_cycle(args: argparse.Namespace) -> int:
    result = run_cycle(mode=args.mode, retry=not args.no_retry)
    print(json.dumps(result, indent=2, default=str))
    return 0


def _load_trades() -> list[dict[str, Any]]:
    path = trades_path()
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def cmd_ticket(args: argparse.Namespace) -> int:
    row = _row(args.symbol)
    acct = rollover_halts(load_account())
    scan = load_scan()
    marks = dict(scan.get("marks") or {})
    mid = float(args.mid) if args.mid is not None else _mid_for(args.symbol, marks)
    uq = bool(row.get("usd_quoted", True))
    trades = _load_trades()
    gate = check_ticket(
        acct,
        symbol=args.symbol,
        side=args.side,
        qty=args.size,
        entry=mid,
        stop=args.stop,
        usd_quoted=uq,
        trades=trades,
    )
    print("risk:", gate["code"], gate["detail"])
    if not gate.get("ok"):
        log("risk_block", gate["detail"], code=gate["code"], symbol=args.symbol)
        return 2
    existing = [p for p in acct.get("positions") or [] if p["symbol"] == args.symbol and p["side"] == args.side]
    if existing and args.add:
        acct, trade = add_to_position(acct, existing[0]["id"], qty=args.size, mid=mid, why=args.why)
    else:
        acct, trade = open_market(
            acct,
            symbol=args.symbol,
            side=args.side,
            qty=args.size,
            mid=mid,
            asset_class=str(row.get("class") or "equity"),
            usd_quoted=uq,
            stop=args.stop,
            target=args.target,
            why=args.why,
        )
    save_account(acct)
    print(json.dumps(trade, indent=2, default=str))
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    acct = rollover_halts(load_account())
    pos = next((p for p in acct.get("positions") or [] if p["id"] == args.id), None)
    if pos is None:
        print(f"no open ticket {args.id}", file=sys.stderr)
        return 2
    scan = load_scan()
    marks = dict(scan.get("marks") or {})
    mid = _mid_for(pos["symbol"], marks)
    acct, trade = close_position(acct, args.id, mid, reason="manual_close", why=args.why or "manual close")
    save_account(acct)
    print(json.dumps(trade, indent=2, default=str))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    if args.weekly:
        return _weekly()
    day = args.date
    if day in (None, "today"):
        from aether.broker import local_now

        day = local_now().date().isoformat()
    path = reports_daily() / f"{day}.md"
    phone = reports_daily() / f"{day}-phone.md"
    if not path.exists():
        print(f"no briefing at {path} — run python -m aether brief")
        return 1
    print(path.read_text(encoding="utf-8"))
    if phone.exists():
        print("\n----- phone card -----\n")
        print(phone.read_text(encoding="utf-8"))
    return 0


def _weekly() -> int:
    from aether.broker import local_now

    trades = _load_trades()
    closed = [t for t in trades if t.get("pnl_usd") not in ("", None)]
    pnls = []
    for t in closed:
        try:
            pnls.append(float(t["pnl_usd"]))
        except ValueError:
            pass
    wins = sum(1 for x in pnls if x > 0)
    n = len(pnls)
    hit = (wins / n * 100.0) if n else None
    avg = (sum(pnls) / n) if n else None
    day = local_now().date().isoformat()
    body = f"""# Aether Weekly Post-mortem — {day}

PAPER TRADING ONLY.

## Ideas taken vs skipped
See ledger/hypotheses.json vs ledger/trades.csv. Closed paper fills this week: {n}.

## Hit rate / avg P&L
- Hit rate: {f'{hit:.1f}%' if hit is not None else 'UNKNOWN (no closed trades)'}
- Avg P&L: {f'${avg:.2f}' if avg is not None else 'UNKNOWN'}
- Max adverse excursion: UNKNOWN (MAE not stored on the v1 blotter — next engineering task)

## Process errors
- Review ledger/journal.md and activity.jsonl for late data / bad size / thesis drift.

## One concrete change for next week
- Record MAE on each open position (high-water / low-water vs entry) so this report is not UNKNOWN.

Desk Engineer: implement only with tests. Do not change risk.yaml without a human command.
"""
    path = reports_weekly() / f"{day}.md"
    path.write_text(body, encoding="utf-8")
    print(path)
    print(body)
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    import uvicorn

    from aether.ui.app import app

    host = args.host
    port = args.port
    print(f"Aether desk UI (PAPER ONLY)  http://{host}:{port}/")
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aether",
        description="Aether Desk — paper-trading research platform. Never live.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Account, positions, last scan").set_defaults(func=cmd_status)

    sc = sub.add_parser("scan", help="Pull universe tape")
    sc.add_argument("--no-retry", action="store_true")
    sc.add_argument("--label", default="scan")
    sc.set_defaults(func=cmd_scan)

    br = sub.add_parser("brief", help="Scan + briefing + phone card")
    br.add_argument("--no-retry", action="store_true")
    br.set_defaults(func=cmd_brief)

    cy = sub.add_parser("cycle", help="Full desk cycle (does not place tickets)")
    cy.add_argument("--mode", default="full", choices=["full", "midday", "us_close"])
    cy.add_argument("--no-retry", action="store_true")
    cy.set_defaults(func=cmd_cycle)

    tk = sub.add_parser("ticket", help="Paper ticket through Risk Officer")
    tk.add_argument("--symbol", required=True)
    tk.add_argument("--side", required=True, choices=["buy", "sell"])
    tk.add_argument("--size", required=True, type=float)
    tk.add_argument("--stop", type=float, default=None)
    tk.add_argument("--target", type=float, default=None)
    tk.add_argument("--why", required=True)
    tk.add_argument("--mid", type=float, default=None, help="Override mid (tests)")
    tk.add_argument("--add", action="store_true", help="Add to existing same-side position")
    tk.set_defaults(func=cmd_ticket)

    cl = sub.add_parser("close", help="Close a paper ticket")
    cl.add_argument("--id", required=True)
    cl.add_argument("--why", default="manual close")
    cl.set_defaults(func=cmd_close)

    rp = sub.add_parser("report", help="Print a daily briefing or weekly post-mortem")
    rp.add_argument("--date", default="today")
    rp.add_argument("--weekly", action="store_true")
    rp.set_defaults(func=cmd_report)

    ui = sub.add_parser("ui", help="Local desk web UI")
    ui.add_argument("--host", default="127.0.0.1")
    ui.add_argument("--port", type=int, default=8791)
    ui.set_defaults(func=cmd_ui)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
