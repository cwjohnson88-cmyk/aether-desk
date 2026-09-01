# Set up Aether on a phone (Grok Bot)

PAPER TRADING ONLY. These bots research and write. They do not send live orders.
They do not hold keys.

You already have the constitutions in this repo. The phone bots **read the same
files** the local desk writes: `reports/`, `ledger/`, `config/`.

## 0. What you need

- This folder on a machine that can run `python -m aether` (home PC), **or**
  a copy of `bots/`, `AGENTS.md`, `config/`, and the latest `reports/daily/`
  synced however you sync files to your phone.
- A Grok account that can create Gots / routines (names vary by client).
- Timezone in `config/schedule.yaml` set to yours (`America/Chicago` by default).

## 1. Create one bot per named role

Create nine Grok Bots. Paste the matching file as the standing instructions
(system / custom instructions / “about this bot”):

| Bot display name | Paste |
|---|---|
| Aether Prime (Overseer) | `bots/overseer.md` + first half of `AGENTS.md` |
| Aether Scanner | `bots/market_scanner.md` |
| Aether Research | `bots/research_desk.md` |
| Aether Macro | `bots/macro.md` |
| Aether Strategist | `bots/strategist.md` |
| Aether Risk | `bots/risk_officer.md` |
| Aether Clerk | `bots/execution_clerk.md` |
| Aether Brief | `bots/briefing_editor.md` |
| Aether Engineer | `bots/desk_engineer.md` |

In every bot, also paste this one-liner at the top:

> Paper trading only. Never ask for keys. Never place a live order. If data is missing, write UNKNOWN.

## 2. One routine per job (owned by that bot)

Map `config/schedule.yaml` like this:

| Local time | Routine name | Owner bot | What you tell it |
|---|---|---|---|
| 06:30 weekdays | Morning scan | Scanner | “Run the Market Scanner skill. If you cannot execute `python -m aether scan`, ask me for the latest `data/snapshots/scan.json` and summarize it. Do not invent prints.” |
| 07:15 weekdays | Morning brief | Brief + Overseer | “Write today’s briefing using `skills/write-briefing/SKILL.md`. Overseer reviews before I treat it as published.” |
| 12:00 weekdays | Midday check | Overseer | “Only if a paper position is open or a high-vol flag exists. Otherwise reply SKIP.” |
| 16:15 weekdays | US close | Scanner | “Close snapshot. Mark-to-market language only. No new tickets.” |
| Sunday 17:00 | Weekly post-mortem | Overseer + Engineer | “Fill `reports/weekly/` template. One concrete next-week change.” |

If the phone bot **cannot** run Python, the routine’s job is to *demand the
artifact* (paste the CLI output or the markdown file) and then edit/review it.
The PC remains the fetcher of prices.

## 3. Grok Build (PC) vs Grok Automations (fallback)

**A — Grok Build / local loop (preferred)**

On the PC:

```
python -m aether cycle
```

Optional: Windows Task Scheduler, same times as `schedule.yaml`, action
`python -m aether cycle`. Grok Build `/loop` can call the same command.

**B — Grok Bot routines**

Phone bots own the *judgment* (is this briefing honest, is this ticket legal
under risk.yaml). The PC owns the *tape*.

**C — Grok Automations, briefing-only fallback**

If nothing else runs: an automation that pings Briefing Editor with
“produce the phone card from the last scan; if no scan, say UNKNOWN.”
Automations must **never** place tickets.

## 4. How a paper ticket happens from the phone

1. Strategist proposes ≤3 ideas (hypothesis form).
2. Risk Officer sizes or says **do nothing**.
3. Overseer blocks anything that violates `config/risk.yaml`.
4. You (human) send: `python -m aether ticket --symbol ... --side ... --size ... --stop ... --target ... --why "..."`
   on the PC, **or** you paste that command to Desk Engineer / Execution Clerk
   to run locally.
5. Execution Clerk confirms the fill from `ledger/trades.csv` (paper).
6. Nobody here talks to a real broker.

## 5. Skills to attach

Attach from `skills/` (copy SKILL.md into the bot’s knowledge):

- `paper-only` — every bot
- `scan-universe` — Scanner
- `write-briefing` — Briefing Editor
- `paper-ticket` — Clerk
- `risk-gate` — Risk Officer
- `overseer-review` — Overseer
- `desk-cycle` — Prime / Engineer

## 6. What success looks like on the phone

You open Grok at 07:20, the Brief bot (or a paste of `reports/daily/YYYY-MM-DD-phone.md`)
gives you 12–18 lines: equity, halt, five movers, 0–3 hypotheses with
falsifiers, data holes, one overseer line. You do not get a “sure thing.”
