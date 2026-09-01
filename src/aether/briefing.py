from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from aether import config
from aether.broker import local_now, status_view
from aether.macro import cross_asset_paragraph
from aether.models import Hypothesis, Quote
from aether.overseer import improvement_note, review_briefing_text, review_hypotheses
from aether.paths import reports_daily
from aether.research import notes_for
from aether.scan import fmt_pct, fmt_px, heat


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(config.timezone_name())
    except Exception:
        return ZoneInfo("America/Chicago")


def tape_paragraph(quotes: dict[str, Quote]) -> str:
    movers = sorted(
        (q for q in quotes.values() if q.pct_day is not None and q.tradable),
        key=lambda q: abs(q.pct_day or 0),
        reverse=True,
    )
    if not movers:
        return (
            "Tape is UNKNOWN across the tradable universe — no usable day-change prints. "
            "This is not a quiet tape; it is a data gap. Do not invent direction."
        )
    top = movers[:4]
    parts = [f"{q.symbol} {fmt_pct(q.pct_day)} ({q.regime})" for q in top]
    n_ok = sum(1 for q in quotes.values() if q.quality == "ok")
    n_bad = sum(1 for q in quotes.values() if q.quality != "ok")
    unusual = [q.symbol for q in quotes.values() if q.unusual]
    u = f" Unusual vs 20d ATR: {', '.join(unusual)}." if unusual else " No unusual 1.5×ATR prints."
    return (
        f"Tradable tape (live or marked): {n_ok} ok, {n_bad} stale/unknown. "
        f"Largest |day| names: {', '.join(parts)}.{u} "
        + cross_asset_paragraph(quotes)
    )


def heat_block(quotes: dict[str, Quote]) -> str:
    h = heat(quotes)
    if not h:
        return "UNKNOWN — no class has a day-change print."
    lines = []
    for cls, row in sorted(h.items()):
        avg = row.get("avg_pct_day")
        lines.append(
            f"- {cls}: n={row.get('n')} avg {fmt_pct(avg)}  "
            f"range {fmt_pct(row.get('min_pct_day'))} to {fmt_pct(row.get('max_pct_day'))}"
        )
    return "\n".join(lines)


def hypotheses_block(ideas: list[Hypothesis]) -> str:
    if not ideas:
        return (
            "None. Strategist output is empty — 'do nothing' is valid. "
            "No forced paper ticket this cycle."
        )
    chunks = []
    for h in ideas:
        chunks.append(
            f"### {h.id} {h.symbol} — {h.direction} ({h.horizon})  confidence {h.confidence}/100\n"
            f"- **Thesis (not advice):** {h.setup}\n"
            f"- **Trigger:** {h.trigger}\n"
            f"- **Entry zone:** {h.entry_zone}\n"
            f"- **Stop / invalidation:** {h.stop} — {h.invalidation}\n"
            f"- **Target / R:** {h.target} / {h.r_multiple}R\n"
            f"- **What the other side believes:** {h.contrary}\n"
            f"- **Book correlation:** {h.correlation_note}"
        )
    return "\n\n".join(chunks)


def will_not_trade(quotes: dict[str, Quote], ideas: list[Hypothesis], book: dict[str, Any]) -> str:
    skip = []
    idea_syms = {h.symbol for h in ideas}
    if book.get("halt_daily") or book.get("halt_weekly"):
        skip.append("Everything — a loss halt is on.")
    skip.append("Any name with quality UNKNOWN or stale — no ticket off a hole.")
    skip.append("Martingale / doubling after a loss. Averaging down more than once.")
    skip.append("Live markets, withdrawals, API keys. This desk is paper only.")
    quiet = [
        q.symbol
        for q in quotes.values()
        if q.tradable and q.symbol not in idea_syms and not q.unusual and q.regime == "range"
    ]
    if quiet:
        skip.append("Quiet range names with no unusual print: " + ", ".join(quiet[:8]) + ".")
    return "\n".join(f"- {s}" for s in skip)


def data_quality_block(quotes: dict[str, Quote]) -> str:
    unknown = [q.symbol for q in quotes.values() if q.quality == "unknown"]
    stale = [q.symbol for q in quotes.values() if q.quality == "stale"]
    ok = [q.symbol for q in quotes.values() if q.quality == "ok"]
    lines = [f"- ok: {', '.join(ok) if ok else 'none'}"]
    lines.append(f"- stale (last-good snapshot): {', '.join(stale) if stale else 'none'}")
    lines.append(f"- UNKNOWN: {', '.join(unknown) if unknown else 'none'}")
    if unknown:
        reasons = "; ".join(f"{q.symbol}: {q.reason}" for q in quotes.values() if q.quality == "unknown")
        lines.append(f"- reasons: {reasons}")
    return "\n".join(lines)


def render_brief(
    quotes: dict[str, Quote],
    acct: dict[str, Any],
    ideas: list[Hypothesis],
    *,
    marks: dict[str, float] | None = None,
) -> tuple[str, str, str]:
    now = local_now()
    tzname = config.timezone_name()
    book = status_view(acct, marks)
    halt = "HALT" if (book["halt_daily"] or book["halt_weekly"]) else "open"
    halt_detail = []
    if book["halt_daily"]:
        halt_detail.append("daily")
    if book["halt_weekly"]:
        halt_detail.append("weekly")
    halt_s = halt if halt == "open" else "HALT (" + ",".join(halt_detail) + ")"

    open_syms = {p["symbol"] for p in book["positions"]}
    notes = notes_for(quotes, open_syms)
    hyp_issues = review_hypotheses(ideas)
    unknown = [q.symbol for q in quotes.values() if q.quality == "unknown"]
    stale = [q.symbol for q in quotes.values() if q.quality == "stale"]
    note = improvement_note(
        unknown=unknown,
        stale=stale,
        issues=hyp_issues,
        n_ideas=len(ideas),
        n_open=book["n_open"],
    )

    body = f"""# Aether Daily Brief — {now.date().isoformat()} {tzname}

PAPER TRADING ONLY. Hypotheses, not advice. No live orders.

## Tape in one paragraph
{tape_paragraph(quotes)}

## Book: equity, day P&L, open risk, halt status
- Equity: ${book['equity']:,.2f}  cash ${book['cash']:,.2f}  starting ${book['starting_equity']:,.2f}
- Day P&L: ${book['day_pnl']:,.2f} ({book['day_pnl_pct']:+.2f}%)
- Week P&L: ${book['week_pnl']:,.2f} ({book['week_pnl_pct']:+.2f}%)
- Open risk (stop distance): ${book['open_risk_usd']:,.2f}
- Open positions: {book['n_open']}  halt: {halt_s}
- Exposure by class: {book['exposure_by_class'] or 'flat'}

## Asset class heat
{heat_block(quotes)}

## Per-symbol notes (only names that moved or matter)
{chr(10).join(notes) if notes else 'None — quiet or data-dark.'}

## Hypotheses (max 3) with confidence and falsifiers
{hypotheses_block(ideas)}

## What we will not trade and why
{will_not_trade(quotes, ideas, book)}

## Data quality / gaps
{data_quality_block(quotes)}

## Overseer notes / next engineering task
{note}
"""
    brief_issues = review_briefing_text(body)
    if brief_issues:
        body += "\n\n<!-- overseer: " + "; ".join(brief_issues) + " -->\n"

    phone = _phone_card(now, tzname, quotes, book, ideas, halt_s, note)
    return body, phone, note


def _phone_card(now: datetime, tzname: str, quotes: dict[str, Quote], book: dict[str, Any], ideas: list[Hypothesis], halt_s: str, note: str) -> str:
    movers = sorted(
        (q for q in quotes.values() if q.pct_day is not None),
        key=lambda q: abs(q.pct_day or 0),
        reverse=True,
    )[:5]
    mv = ", ".join(f"{q.symbol} {fmt_pct(q.pct_day)}" for q in movers) or "UNKNOWN"
    unknown = [q.symbol for q in quotes.values() if q.quality != "ok"]
    heat_s = ", ".join(
        f"{cls} {fmt_pct(row.get('avg_pct_day'))}"
        for cls, row in sorted(heat(quotes).items())
        if cls != "macro"
    ) or "UNKNOWN"
    lines = [
        f"AETHER PHONE CARD {now.date().isoformat()} {tzname} — PAPER ONLY",
        f"Eq ${book['equity']:,.0f} cash ${book['cash']:,.0f} day {book['day_pnl_pct']:+.2f}% open {book['n_open']} halt {halt_s}",
        f"Tape: {mv}",
        f"Heat: {heat_s}",
        f"Data holes: {', '.join(unknown) if unknown else 'none'}",
        "Book: flat." if book["n_open"] == 0 else f"Open risk ${book['open_risk_usd']:,.0f}.",
    ]
    if ideas:
        for h in ideas:
            lines.append(
                f"{h.id} {h.symbol} {h.direction} {h.horizon} conf {h.confidence} "
                f"stop {h.stop} inv: {h.invalidation[:80]}"
            )
    else:
        lines.append("Hypotheses: none (do nothing).")
    lines.append("Will not: unknown/stale names, martingale, live orders.")
    lines.append("Decision TF: 4h and 1D. 15m is context only.")
    lines.append("Overseer: " + note[:160])
    lines.append("Not advice. Falsify every thesis. Human arms live later, in writing, only.")
    return "\n".join(lines) + "\n"


def write_brief(body: str, phone: str, when: datetime | None = None) -> tuple[str, str]:
    when = when or local_now()
    day = when.date().isoformat()
    p1 = reports_daily() / f"{day}.md"
    p2 = reports_daily() / f"{day}-phone.md"
    p1.write_text(body, encoding="utf-8")
    p2.write_text(phone, encoding="utf-8")
    return str(p1), str(p2)
