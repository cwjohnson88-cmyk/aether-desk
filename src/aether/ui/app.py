from __future__ import annotations

import html
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from aether.activity import tail
from aether.broker import load_account, rollover_halts, status_view
from aether.paths import reports_daily
from aether.scan import load_scan
from aether.strategist import load_hypotheses

HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
app = FastAPI(title="Aether Desk", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")


def _md_lite(text: str) -> str:
    lines = []
    for raw in text.splitlines():
        s = html.escape(raw)
        if s.startswith("### "):
            lines.append(f"<h3>{s[4:]}</h3>")
        elif s.startswith("## "):
            lines.append(f"<h2>{s[3:]}</h2>")
        elif s.startswith("# "):
            lines.append(f"<h1>{s[2:]}</h1>")
        elif s.startswith("- "):
            lines.append(f"<li>{s[2:]}</li>")
        elif s.strip() == "":
            lines.append("<br>")
        else:
            lines.append(f"<p>{s}</p>")
    return "\n".join(lines)


def _ctx() -> dict:
    acct = rollover_halts(load_account())
    scan = load_scan()
    marks = dict(scan.get("marks") or {})
    book = status_view(acct, marks)
    quotes = list((scan.get("quotes") or {}).values())
    quotes.sort(key=lambda q: q.get("symbol") or "")
    from aether.broker import local_now

    day = local_now().date().isoformat()
    brief_path = reports_daily() / f"{day}.md"
    brief = brief_path.read_text(encoding="utf-8") if brief_path.exists() else "No briefing yet. Run python -m aether brief."
    return {
        "book": book,
        "quotes": quotes,
        "hypotheses": load_hypotheses(),
        "activity": list(reversed(tail(30))),
        "brief_html": _md_lite(brief),
        "scan_as_of": scan.get("as_of") or "UNKNOWN — no scan",
    }


@app.get("/", response_class=HTMLResponse)
def desk(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "desk.html", _ctx())


@app.get("/partials/desk", response_class=HTMLResponse)
def desk_partial(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "desk.html", _ctx())
