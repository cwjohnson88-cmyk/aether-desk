---
name: paper-ticket
description: Place or close an Aether in-process paper ticket after risk gate. Never a live broker.
---

# Paper ticket

```
python -m aether ticket --symbol SYM --side buy|sell --size Q --stop S --target T --why "thesis..."
python -m aether close --id T1 --why "..."
```

Size is units. Stop is required. If the CLI prints a risk block code, stop. Confirm fill from stdout / `ledger/trades.csv`. This is not a live order.
