---
name: risk-gate
description: Apply Aether risk.yaml to a proposed paper idea. Do nothing is valid.
---

# Risk gate

Fail closed:

- Stop risk > 2% of paper equity
- >6 correlated names or >6 open
- Daily halt 3% / weekly halt 6%
- Martingale (size ≥ 2× last losing size on that symbol)
- Average down more than once
- Missing stop
- Quality UNKNOWN/stale tape

Do not widen a stop to fit the cap. Cut size or do nothing.
