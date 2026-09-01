"""Open the Aether paper desk dashboard. Boots the UI if it is down.

PAPER TRADING ONLY. Listens on 8791 (loopback + LAN if a phone token exists).
Does not touch Hermes on :8787.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8791/"
PORT = 8791
LOG = ROOT / "ledger" / "dashboard.log"

BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

CREATE_NO_WINDOW = 0x08000000


def _server_up() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1):
            return True
    except OSError:
        return False


def _pythonw() -> str:
    venv = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if venv.exists():
        return str(venv)
    return sys.executable.replace("python.exe", "pythonw.exe")


def _ensure_server() -> str:
    if _server_up():
        return "already-up"
    pyw = _pythonw()
    err = ROOT / "ledger" / "dashboard.err.log"
    err.parent.mkdir(parents=True, exist_ok=True)
    try:
        logf = open(err, "ab")
        subprocess.Popen(
            [pyw, "-m", "aether", "ui", "--host", "0.0.0.0", "--port", str(PORT)],
            cwd=str(ROOT),
            stdout=logf,
            stderr=logf,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception as exc:  # noqa: BLE001
        return f"launch-failed:{exc!r}"
    # Cold import of pandas/yfinance can take a bit.
    for _ in range(50):
        time.sleep(0.4)
        if _server_up():
            return "started"
    return "starting"


def _open_url(url: str) -> str:
    for exe in BROWSERS:
        if os.path.exists(exe):
            try:
                subprocess.Popen([exe, "--new-window", url])
                return f"ok:{os.path.basename(exe)}"
            except Exception:
                continue
    try:
        webbrowser.open(url)
        return "ok:webbrowser"
    except Exception as exc:  # noqa: BLE001
        return f"FAILED:{exc!r}"


def main() -> int:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ensured = _ensure_server()
    opened = "skipped" if "--no-open" in sys.argv else _open_url(URL)
    line = f"{datetime.now(timezone.utc).isoformat()} server={ensured} opened={opened} {URL}\n"
    try:
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass
    print(f"server={ensured}  opened={opened}  (live {URL})")
    return 0 if ensured in ("already-up", "started", "starting") else 1


if __name__ == "__main__":
    raise SystemExit(main())
