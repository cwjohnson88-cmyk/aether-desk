from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from aether.paths import activity_path


def log(kind: str, message: str, **extra: Any) -> None:
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "message": message,
        **extra,
    }
    path = activity_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def tail(n: int = 40) -> list[dict[str, Any]]:
    path = activity_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
