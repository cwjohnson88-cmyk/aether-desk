from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from aether.paths import config_dir


def _load(name: str) -> dict[str, Any]:
    path = config_dir() / name
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a YAML mapping")
    return data


@lru_cache(maxsize=8)
def universe() -> dict[str, Any]:
    return _load("universe.yaml")


@lru_cache(maxsize=8)
def risk() -> dict[str, Any]:
    return _load("risk.yaml")


@lru_cache(maxsize=8)
def schedule() -> dict[str, Any]:
    return _load("schedule.yaml")


def clear_cache() -> None:
    universe.cache_clear()
    risk.cache_clear()
    schedule.cache_clear()


def all_symbol_rows() -> list[dict[str, Any]]:
    u = universe()
    rows = list(u.get("symbols") or [])
    rows.extend(u.get("macro") or [])
    return rows


def symbol_by_id(sid: str) -> dict[str, Any] | None:
    sid_u = sid.upper()
    for row in all_symbol_rows():
        if str(row.get("id", "")).upper() == sid_u:
            return row
    return None


def tradable_ids() -> list[str]:
    return [str(r["id"]) for r in universe().get("symbols") or [] if r.get("tradable", True)]


def timezone_name() -> str:
    return str(schedule().get("timezone") or "America/Chicago")
