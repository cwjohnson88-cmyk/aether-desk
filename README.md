# Aether Desk

**PAPER TRADING ONLY.** No live orders. No real money. No broker withdrawal.
No private keys, seed phrases, or API secrets belong in this repo or in chat.

Aether is a local research and practice desk for a mixed universe (FX, crypto,
large-cap stocks/ETFs). It pulls public prices, writes a daily briefing, holds
paper tickets in an in-process broker, and keeps named bot constitutions so the
same files can be handed to Grok Bots on a phone.

Predictions are **hypotheses** (thesis, confidence 0–100, horizon, falsifier) —
not advice. If a data source is down, the field is **UNKNOWN** plus a reason.
Nothing is invented.

Hermes (the older crypto paper trainer) is a separate project and is left running.
Aether does not talk to it. Aether’s UI is `127.0.0.1:8791`.

## Quick start

```powershell
cd C:\Users\cwjoh\Projects\aether-desk
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m aether status
.\.venv\Scripts\python.exe -m aether brief
.\.venv\Scripts\python.exe -m aether ui
```

Then open http://127.0.0.1:8791/

Paper account starts at **100,000 USD cash**, no positions.

## CLI

```
python -m aether status
python -m aether scan
python -m aether brief
python -m aether cycle
python -m aether ticket --symbol EURUSD --side buy --size 10000 --stop ... --target ... --why "..."
python -m aether close --id T1
python -m aether report --date today
python -m aether report --weekly
python -m aether ui
```

`--size` is units (shares / coins / FX base). Risk is measured at the **stop**,
capped at 2% of paper equity. Tickets that fail `config/risk.yaml` are blocked.

## Layout

```
config/          universe, risk, schedule (edit symbols here)
src/aether/      Python package
ledger/          paper_account.json, trades.csv, journal.md
reports/daily/   YYYY-MM-DD.md + phone card
reports/weekly/  post-mortems
bots/            standing instructions per named bot
skills/          Grok Build / Grok Bot skills
data/snapshots/  last-good quotes (desk still runs if an API blips)
```

## Risk defaults (do not change without a human command)

- Max 2% of paper equity per idea (stop distance)
- Max 6 correlated positions
- Daily loss halt 3%, weekly halt 6%
- No martingale
- Average down at most once
- Human is the only person who can later “arm” live trading, and only after an
  explicit written command naming size and venue

## Tests

```
.\.venv\Scripts\python.exe -m pytest -q
```

## Phone / Grok Bot

See `SETUP_GROK_BOT.md` and `AGENTS.md`.
