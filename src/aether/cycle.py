from __future__ import annotations

from typing import Any

from aether.activity import log
from aether.briefing import render_brief, write_brief
from aether.broker import apply_marks, load_account, rollover_halts, save_account, status_view
from aether.market import usd_quoted_map
from aether.models import Quote
from aether.scan import run_scan
from aether.strategist import propose, save_hypotheses


def quotes_from_scan(scan: dict[str, Any]) -> dict[str, Quote]:
    out: dict[str, Quote] = {}
    for k, v in (scan.get("quotes") or {}).items():
        try:
            out[k] = Quote(**{key: v.get(key) for key in Quote.__dataclass_fields__})
        except TypeError:
            continue
    return out


def run_cycle(*, mode: str = "full", retry: bool = True) -> dict[str, Any]:
    """Scan → mark book → research/strategist → briefing. Never places tickets."""
    label = "midday" if mode == "midday" else "scan"
    acct = rollover_halts(load_account())
    if mode == "midday" and not acct.get("positions"):
        log("cycle", "midday skipped — no open positions")
        return {"skipped": True, "reason": "midday: no open position (high-vol path not separately flagged)"}

    scan = run_scan(retry=retry, label=label)
    quotes = quotes_from_scan(scan)
    marks = {k: v.last for k, v in quotes.items() if v.last is not None}
    uq = usd_quoted_map()
    acct = apply_marks(acct, marks, uq)
    acct = rollover_halts(acct)
    save_account(acct)

    ideas = [] if mode == "us_close" else propose(quotes, acct)
    save_hypotheses(ideas)
    body, phone, note = render_brief(quotes, acct, ideas, marks=marks)
    p1, p2 = write_brief(body, phone)
    log("brief", f"published {p1}", overseer=note)
    book = status_view(acct, marks)
    return {
        "skipped": False,
        "brief": p1,
        "phone": p2,
        "n_ideas": len(ideas),
        "unknown": scan.get("unknown") or [],
        "stale": scan.get("stale") or [],
        "equity": book["equity"],
        "overseer": note,
    }
