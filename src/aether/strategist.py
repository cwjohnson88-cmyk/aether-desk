"""0–3 paper ideas per cycle. Hypotheses, not advice. Empty book is valid."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from aether import config
from aether.models import Hypothesis, Quote
from aether.paths import hypotheses_path
from aether.risk import check_ticket, cluster_of


def _horizon_for(q: Quote) -> str:
    if q.regime in ("uptrend", "downtrend"):
        return "2–5 days"
    return "session"


def _build_idea(q: Quote, acct: dict[str, Any], open_clusters: list[str], idx: int) -> Hypothesis | None:
    if q.last is None or q.atr20 is None or q.atr20 <= 0 or q.quality != "ok":
        return None
    if not q.tradable:
        return None
    last = float(q.last)
    atr = float(q.atr20)
    if q.regime == "uptrend" and (q.unusual or (q.pct_day or 0) > 0):
        direction = "bull"
        stop = last - 1.0 * atr
        target = last + 2.0 * atr
        tag = "unusual print vs 20d ATR" if q.unusual else "positive session print while tagged uptrend"
        setup = f"{q.symbol} tagged uptrend; {tag}. Thesis is continuation, not a chase-at-any-price."
        trigger = f"Hold above last print {last:.6g} on 4h close; do not buy a breakdown through stop."
    elif q.regime == "downtrend" and (q.unusual or (q.pct_day or 0) < 0):
        direction = "bear"
        stop = last + 1.0 * atr
        target = last - 2.0 * atr
        tag = "unusual print vs 20d ATR" if q.unusual else "negative session print while tagged downtrend"
        setup = f"{q.symbol} tagged downtrend; {tag}. Thesis is continuation."
        trigger = f"Hold below last print {last:.6g} on 4h close; do not short a squeeze through stop."
    elif q.regime == "range" and q.unusual:
        # fade the stretch
        if (q.pct_day or 0) > 0:
            direction = "bear"
            stop = last + 0.75 * atr
            target = last - 1.5 * atr
            setup = f"{q.symbol} range regime with upside stretch >1.5× ATR. Thesis is mean reversion, easily wrong if it is a breakout."
            trigger = "Only if next 4h fails to make a new high."
        else:
            direction = "bull"
            stop = last - 0.75 * atr
            target = last + 1.5 * atr
            setup = f"{q.symbol} range regime with downside stretch >1.5× ATR. Thesis is mean reversion, easily wrong if it is a breakdown."
            trigger = "Only if next 4h fails to make a new low."
    else:
        return None

    r = abs(target - last) / abs(stop - last) if stop != last else None
    risk_cfg = config.risk()
    # Size so stop risk ≈ 1% equity (inside the 2% cap) using a dummy qty solve
    eq = float(acct.get("cash") or 0)
    for p in acct.get("positions") or []:
        eq += float(p.get("unrealized_usd") or 0)
    if eq <= 0:
        eq = float(risk_cfg.get("starting_equity") or 100000)
    risk_budget = 0.01 * eq
    stop_dist = abs(last - stop)
    pv = 1.0 if q.usd_quoted else (1.0 / last if last else 0)
    qty = risk_budget / (stop_dist * pv) if stop_dist * pv > 0 else 0
    side = "buy" if direction == "bull" else "sell"
    gate = check_ticket(
        acct,
        symbol=q.symbol,
        side=side,
        qty=qty,
        entry=last,
        stop=stop,
        usd_quoted=q.usd_quoted,
    )
    if not gate.get("ok"):
        return None

    cl = cluster_of(q.symbol)
    corr_note = "No open book."
    if open_clusters:
        if cl in open_clusters:
            corr_note = f"WARNING: cluster {cl} already has open risk. Adding this stacks the same bet."
        else:
            corr_note = f"Cluster {cl or 'n/a'} is not in the open book clusters ({', '.join(open_clusters)})."

    contrary = {
        "bull": "Bears believe this is a bull trap / overbought stretch and that the stop will be tagged first.",
        "bear": "Bulls believe this is a washout / oversold stretch and that a squeeze takes out the stop.",
        "range": "Breakout traders believe the range is done and the unusual print is the start of trend.",
    }[direction]

    return Hypothesis(
        id=f"H{idx}",
        symbol=q.symbol,
        direction=direction,  # type: ignore[arg-type]
        horizon=_horizon_for(q),
        setup=setup,
        trigger=trigger,
        entry_zone=f"near {last:.6g} (paper; use next 4h/1D close, not a market-on-print chase)",
        stop=round(stop, 6),
        target=round(target, 6),
        r_multiple=round(r, 2) if r else None,
        invalidation=f"4h close through {stop:.6g} or regime flip away from {q.regime}.",
        confidence=min(62, 38 + (12 if q.unusual else 0) + (8 if q.regime != "range" else 0)),
        contrary=contrary,
        correlation_note=corr_note,
        status="open",
    )


def propose(quotes: dict[str, Quote], acct: dict[str, Any]) -> list[Hypothesis]:
    max_n = int(config.risk().get("max_hypotheses_per_cycle") or 3)
    if acct.get("halt_daily") or acct.get("halt_weekly"):
        return []
    open_syms = {p["symbol"] for p in acct.get("positions") or []}
    open_clusters = []
    for p in acct.get("positions") or []:
        c = cluster_of(p["symbol"])
        if c and c not in open_clusters:
            open_clusters.append(c)

    scored: list[tuple[float, Quote]] = []
    for q in quotes.values():
        if q.symbol in open_syms:
            continue
        if q.quality != "ok" or q.last is None:
            continue
        score = 0.0
        if q.unusual:
            score += 5
        if q.news_vacuum:
            score += 1  # interesting, but we will not treat vacuum as a catalyst
        if q.regime in ("uptrend", "downtrend"):
            score += 2
        if q.pct_day is not None:
            score += min(abs(q.pct_day) / 2.0, 4)
        if score <= 0:
            continue
        scored.append((score, q))
    scored.sort(key=lambda t: t[0], reverse=True)

    ideas: list[Hypothesis] = []
    used_clusters: list[str] = list(open_clusters)
    idx = 1
    for _, q in scored:
        if len(ideas) >= max_n:
            break
        cl = cluster_of(q.symbol)
        # prefer not stacking the same cluster in one cycle
        if cl and cl in used_clusters and len(ideas) > 0:
            continue
        h = _build_idea(q, acct, open_clusters, idx)
        if h is None:
            continue
        ideas.append(h)
        if cl:
            used_clusters.append(cl)
        idx += 1
    return ideas


def save_hypotheses(ideas: list[Hypothesis]) -> None:
    blob = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "ideas": [h.to_dict() for h in ideas],
        "disclaimer": "Hypotheses for paper practice. Not advice. Not live orders.",
    }
    path = hypotheses_path()
    path.write_text(json.dumps(blob, indent=2), encoding="utf-8")


def load_hypotheses() -> list[dict[str, Any]]:
    path = hypotheses_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return list(data.get("ideas") or [])
