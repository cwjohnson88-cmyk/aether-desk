"""Resolve the Aether repo root. Override with AETHER_ROOT for tests."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    env = os.environ.get("AETHER_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "config" / "universe.yaml").exists():
            return p
    raise FileNotFoundError(
        "Cannot find Aether root (no config/universe.yaml). Set AETHER_ROOT."
    )


def config_dir() -> Path:
    return repo_root() / "config"


def ledger_dir() -> Path:
    return repo_root() / "ledger"


def data_dir() -> Path:
    return repo_root() / "data"


def snapshots_dir() -> Path:
    p = data_dir() / "snapshots"
    p.mkdir(parents=True, exist_ok=True)
    return p


def reports_daily() -> Path:
    p = repo_root() / "reports" / "daily"
    p.mkdir(parents=True, exist_ok=True)
    return p


def reports_weekly() -> Path:
    p = repo_root() / "reports" / "weekly"
    p.mkdir(parents=True, exist_ok=True)
    return p


def account_path() -> Path:
    return ledger_dir() / "paper_account.json"


def trades_path() -> Path:
    return ledger_dir() / "trades.csv"


def hypotheses_path() -> Path:
    return ledger_dir() / "hypotheses.json"


def activity_path() -> Path:
    return ledger_dir() / "activity.jsonl"


def quotes_snapshot_path() -> Path:
    return snapshots_dir() / "quotes.json"


def scan_snapshot_path() -> Path:
    return snapshots_dir() / "scan.json"
