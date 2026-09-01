# Creator Dashboard handoff — Aether Desk

- **Status:** building
- **Published:** no
- **Path:** `C:\Users\cwjoh\Projects\aether-desk`
- **Last worked:** v1 scaffold. Paper desk, 100k USD, CLI status/brief, UI :8791. Hermes left running on :8787.
- **Last opened from Creator Dashboard:** —

## Notes

PAPER TRADING ONLY. Multi-asset research desk (FX + crypto + large-cap/ETFs).
Do not kill the Hermes worker. Do not wire a wallet. Do not put keys in this repo.

## Testing / improvements

`python -m aether status` and `python -m aether brief`. pytest for broker/risk.
Watch `reports/daily/` and `data/snapshots/quotes.json` quality tags.
