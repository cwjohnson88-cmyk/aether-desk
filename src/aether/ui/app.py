from __future__ import annotations

import hmac
import html
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from aether.phone_token import load_or_create

from aether.activity import tail
from aether.broker import apply_marks, load_account, local_now, rollover_halts, save_account, status_view, utcnow
from aether.market import refresh_lasts, usd_quoted_map
from aether.paths import reports_daily
from aether.progress import blotter_stats, load_trades, trades_newest
from aether.scan import load_scan
from aether.strategist import load_hypotheses

HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(HERE / "templates"))

_stop = threading.Event()
_refresh_lock = threading.Lock()


def _refresh_loop() -> None:
    """Background last-print refresh while the dashboard is up. Never invents."""
    time.sleep(2)
    while not _stop.is_set():
        try:
            with _refresh_lock:
                refresh_lasts()
        except Exception:
            pass
        _stop.wait(45)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _stop.clear()
    t = threading.Thread(target=_refresh_loop, name="aether-tape", daemon=True)
    t.start()
    yield
    _stop.set()


app = FastAPI(title="Aether Desk", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

PHONE_TOKEN = ""
try:
    PHONE_TOKEN = load_or_create()
except Exception:
    PHONE_TOKEN = ""


def _loopback(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost")


@app.middleware("http")
async def phone_gate(request: Request, call_next):
    """LAN/phone needs the token. Loopback (desktop shortcut) does not."""
    if not PHONE_TOKEN or _loopback(request):
        return await call_next(request)
    qk = request.query_params.get("k") or ""
    ck = request.cookies.get("k") or ""

    def _ok(got: str) -> bool:
        if not got or len(got) != len(PHONE_TOKEN):
            return False
        return hmac.compare_digest(got, PHONE_TOKEN)

    if not (_ok(qk) or _ok(ck)):
        return Response(status_code=404, content=b"")
    resp = await call_next(request)
    if _ok(qk):
        resp.set_cookie("k", PHONE_TOKEN, httponly=True, samesite="lax", path="/")
    return resp


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


def desk_payload() -> dict:
    acct = rollover_halts(load_account())
    scan = load_scan()
    marks = dict(scan.get("marks") or {})
    uq = usd_quoted_map()
    orig_ids = [p["id"] for p in acct.get("positions") or []]
    day0 = acct.get("day_start_date")
    try:
        marked = apply_marks(acct, marks, uq)
        marked = rollover_halts(marked)
        new_ids = [p["id"] for p in marked.get("positions") or []]
        if new_ids != orig_ids or marked.get("day_start_date") != day0:
            save_account(marked)
        acct = marked
    except Exception:
        pass
    book = status_view(acct, marks)
    quotes = list((scan.get("quotes") or {}).values())
    quotes.sort(key=lambda q: abs(q.get("pct_day") or 0), reverse=True)
    trades = load_trades()
    stats = blotter_stats(trades, book)
    day = local_now().date().isoformat()
    brief_path = reports_daily() / f"{day}.md"
    brief = brief_path.read_text(encoding="utf-8") if brief_path.exists() else "No briefing yet. Run python -m aether brief."
    return {
        "paper_only": True,
        "now": utcnow().isoformat(),
        "scan_as_of": scan.get("as_of") or "UNKNOWN — no scan",
        "book": book,
        "stats": stats,
        "trades": trades_newest(trades, 80),
        "quotes": quotes,
        "hypotheses": load_hypotheses(),
        "activity": list(reversed(tail(40))),
        "brief_html": _md_lite(brief),
    }


@app.get("/", response_class=HTMLResponse)
def desk(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "desk.html", desk_payload())


@app.get("/data")
def data() -> JSONResponse:
    payload = desk_payload()
    payload.pop("brief_html", None)
    return JSONResponse(payload)


@app.get("/manifest.webmanifest")
def manifest() -> Response:
    body = {
        "name": "Aether Desk",
        "short_name": "Aether",
        "description": "Read-only paper blotter. Not live trading.",
        "start_url": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#12141a",
        "theme_color": "#12141a",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }
    import json as _json

    return Response(_json.dumps(body), media_type="application/manifest+json")


@app.get("/sw.js")
def sw() -> Response:
    body = """
const SHELL='aether-shell-v1';
self.addEventListener('install', e=>{
  e.waitUntil(caches.open(SHELL).then(c=>c.addAll(['/','/static/desk.css','/static/desk.js'])));
  self.skipWaiting();
});
self.addEventListener('activate', e=>{
  e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(n=>n!==SHELL).map(n=>caches.delete(n)))));
  self.clients.claim();
});
self.addEventListener('fetch', e=>{
  const u=new URL(e.request.url);
  if(u.pathname.startsWith('/data')) return;
  e.respondWith(fetch(e.request).then(r=>{
    const copy=r.clone();
    caches.open(SHELL).then(c=>c.put(e.request,copy)).catch(()=>{});
    return r;
  }).catch(()=>caches.match(e.request).then(r=>r||caches.match('/'))));
});
"""
    return Response(body, media_type="application/javascript")


@app.get("/icon-192.png")
@app.get("/icon-512.png")
def icon(request: Request):
    for name in ("icon-192.png", "icon-512.png", "aether.ico"):
        p = Path(__file__).resolve().parents[3] / name if name.endswith(".png") else Path(__file__).resolve().parents[3] / "aether.ico"
        if name.endswith(".png"):
            p = Path(__file__).resolve().parents[3] / name
        if p.exists():
            return FileResponse(p, media_type="image/png" if name.endswith(".png") else "image/x-icon")
    return Response(status_code=404)
