"""Headline helper. Never invents a story."""

from __future__ import annotations

from aether.models import Quote


def format_headlines(q: Quote, limit: int = 3) -> str:
    if q.headlines:
        return "; ".join(q.headlines[:limit])
    if q.unusual:
        return "UNKNOWN — big print with no public headline attached (news vacuum)"
    return "UNKNOWN — no public headlines attached to this symbol"
