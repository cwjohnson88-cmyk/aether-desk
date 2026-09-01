"""Aether Prime — quality bar. Never places tickets."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aether.models import Hypothesis

REQUIRED_BRIEF_HEADERS = [
    "# Aether Daily Brief",
    "## Tape in one paragraph",
    "## Book:",
    "## Asset class heat",
    "## Per-symbol notes",
    "## Hypotheses",
    "## What we will not trade",
    "## Data quality",
    "## Overseer notes",
]


def review_hypotheses(ideas: list[Hypothesis]) -> list[str]:
    issues: list[str] = []
    if len(ideas) > 3:
        issues.append(f"BLOCK: {len(ideas)} hypotheses (max 3).")
    for h in ideas:
        if not h.invalidation:
            issues.append(f"BLOCK {h.id}: missing invalidation.")
        if h.confidence < 0 or h.confidence > 100:
            issues.append(f"BLOCK {h.id}: confidence out of 0–100.")
        if not h.contrary:
            issues.append(f"BLOCK {h.id}: missing contrary view.")
        if h.stop is None:
            issues.append(f"BLOCK {h.id}: missing stop.")
        if h.direction not in ("bull", "bear", "range"):
            issues.append(f"BLOCK {h.id}: direction must be bull/bear/range.")
    return issues


def review_briefing_text(text: str) -> list[str]:
    issues = []
    for hdr in REQUIRED_BRIEF_HEADERS:
        if hdr not in text:
            issues.append(f"Brief missing section starting {hdr!r}.")
    if "PAPER" not in text.upper():
        issues.append("Brief must say this is paper trading.")
    return issues


def improvement_note(
    *,
    unknown: list[str],
    stale: list[str],
    issues: list[str],
    n_ideas: int,
    n_open: int,
) -> str:
    bits = []
    if unknown:
        bits.append(f"Data holes on {', '.join(unknown)} — next: harden that adapter or widen fallback.")
    if stale:
        bits.append(f"Stale tape on {', '.join(stale)} — next: retry cadence / snapshot age in the UI.")
    if issues:
        bits.append("Quality flags: " + "; ".join(issues[:4]))
    if n_ideas == 0 and n_open == 0:
        bits.append("Empty idea set is valid. Next engineering: calendar adapter so 'will not trade' can cite real events.")
    if not bits:
        bits.append("No breakage this cycle. Next engineering: weekly MAE tracker once the blotter has closed paper trades.")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"{ts} — " + " ".join(bits)


def publish_ok(issues: list[str]) -> bool:
    return not any(i.startswith("BLOCK") for i in issues)
