"""Local phone-access token. Never commit the token file."""

from __future__ import annotations

import secrets
from pathlib import Path

from aether.paths import ledger_dir

TOKEN_NAME = "phone_token.txt"


def token_path() -> Path:
    return ledger_dir() / TOKEN_NAME


def load_or_create() -> str:
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        tok = path.read_text(encoding="utf-8").strip()
        if tok:
            return tok
    tok = secrets.token_urlsafe(24)
    path.write_text(tok + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return tok
