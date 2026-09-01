---
name: scan-universe
description: Pull Aether universe prices, ATR, regime, unusual flags, correlation snapshot. Never invent prints.
---

# Scan universe

1. Prefer `python -m aether scan`.
2. Universe is `config/universe.yaml` (editable). Timeframes 15m/1h/4h/1D.
3. On failure: retry once, then Stooq, then last-good snapshot (`stale`), else UNKNOWN.
4. Flag unusual: |day move| > 1.5 × ATR20. Flag news vacuum if unusual and no headline.
5. Do not write a trade idea. Return the scan summary and quality holes.
