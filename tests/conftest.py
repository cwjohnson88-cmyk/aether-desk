from __future__ import annotations

import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def desk(tmp_path, monkeypatch):
    shutil.copytree(ROOT / "config", tmp_path / "config")
    (tmp_path / "ledger").mkdir()
    (tmp_path / "data" / "snapshots").mkdir(parents=True)
    (tmp_path / "reports" / "daily").mkdir(parents=True)
    (tmp_path / "reports" / "weekly").mkdir(parents=True)
    monkeypatch.setenv("AETHER_ROOT", str(tmp_path))
    from aether import config
    from aether.broker import save_account, seed_account

    config.clear_cache()
    save_account(seed_account(100_000.0))
    yield tmp_path
    config.clear_cache()
