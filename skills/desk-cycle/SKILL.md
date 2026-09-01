---
name: desk-cycle
description: Run a full Aether cycle (scan, mark, 0–3 hypotheses, briefing). Does not place tickets.
---

# Desk cycle

```
python -m aether cycle
python -m aether cycle --mode midday
python -m aether cycle --mode us_close
```

Midday skips if the book is flat. Cycle never calls the paper broker to open risk. Tickets are a separate Clerk step after Risk + Overseer.
