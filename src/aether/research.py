from __future__ import annotations

from aether.models import Quote
from aether.news import format_headlines
from aether.scan import fmt_pct, fmt_px


def one_pager(q: Quote) -> str:
    """Fact / inference / speculation separated. No invented catalysts."""
    facts = [
        f"last={fmt_px(q)}  day={fmt_pct(q.pct_day)}  week={fmt_pct(q.pct_week)}",
        f"source={q.source or 'UNKNOWN'}  as_of={q.as_of or 'UNKNOWN'}  quality={q.quality}",
        f"ATR20={q.atr20 if q.atr20 is not None else 'UNKNOWN'}  regime={q.regime}",
        f"headlines: {format_headlines(q)}",
    ]
    inferences: list[str] = []
    if q.regime in ("uptrend", "downtrend") and q.quality == "ok":
        inferences.append(f"Tape is tagged {q.regime} on 20-day MA vs ATR slope — a classification, not a forecast.")
    if q.unusual:
        inferences.append("Session/day change exceeds 1.5× 20-day ATR (unusual print).")
    if q.news_vacuum:
        inferences.append("Unusual print with no attached public headline (news vacuum). Do not invent a cause.")
    if q.quality != "ok":
        inferences.append("Do not size a ticket off this name until a live print returns.")

    speculation = [
        "No positioning census (CFTC/exchange OI) is wired in v1 — positioning narrative is UNKNOWN.",
        "Calendar: no economic-calendar adapter in v1 — next release dates are UNKNOWN.",
    ]
    art = "an" if q.regime[0] in "aeiou" else "a"
    contrary = (
        f"The other side: if this is {art} {q.regime} tape, fades argue mean-reversion inside ATR; "
        "trend-followers argue continuation until an ATR trailing stop."
    )
    lines = [f"### {q.symbol} ({q.asset_class}, cluster={q.cluster or 'n/a'})"]
    lines.append("**Fact**")
    lines.extend(f"- {x}" for x in facts)
    lines.append("**Inference**")
    if inferences:
        lines.extend(f"- {x}" for x in inferences)
    else:
        lines.append("- Nothing beyond the prints above.")
    lines.append("**Speculation / gaps**")
    lines.extend(f"- {x}" for x in speculation)
    lines.append(f"**Contrary view:** {contrary}")
    return "\n".join(lines)


def notes_for(quotes: dict[str, Quote], open_symbols: set[str], limit: int = 8) -> list[str]:
    scored: list[tuple[float, Quote]] = []
    for q in quotes.values():
        if not q.tradable and q.symbol not in open_symbols:
            # still include macro if unusual
            if not q.unusual:
                continue
        score = 0.0
        if q.symbol in open_symbols:
            score += 100
        if q.unusual:
            score += 50
        if q.pct_day is not None:
            score += abs(q.pct_day)
        if q.quality != "ok":
            score += 5
        scored.append((score, q))
    scored.sort(key=lambda t: t[0], reverse=True)
    picked = [q for _, q in scored[:limit] if _ > 0 or q.symbol in open_symbols]
    if not picked:
        # still show top movers by |day|
        by_day = sorted(
            (q for q in quotes.values() if q.pct_day is not None),
            key=lambda q: abs(q.pct_day or 0),
            reverse=True,
        )
        picked = by_day[:5]
    return [one_pager(q) for q in picked]
