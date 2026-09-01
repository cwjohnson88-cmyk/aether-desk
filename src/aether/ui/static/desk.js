(function () {
  const $ = (id) => document.getElementById(id);

  function money(n, d) {
    if (n === null || n === undefined || Number.isNaN(n)) return "UNKNOWN";
    const x = Number(n);
    const sign = x < 0 ? "-" : "";
    return sign + "$" + Math.abs(x).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function pct(n) {
    if (n === null || n === undefined || Number.isNaN(n)) return "UNKNOWN";
    return (n >= 0 ? "+" : "") + Number(n).toFixed(2) + "%";
  }
  function cls(n) {
    if (n === null || n === undefined) return "";
    return n >= 0 ? "up" : "down";
  }
  function fmtPx(n) {
    if (n === null || n === undefined) return "UNKNOWN";
    return Number(n).toPrecision(6);
  }
  function shortTs(ts) {
    if (!ts) return "";
    return String(ts).replace("T", " ").slice(0, 19);
  }

  function spark(curve) {
    const svg = $("spark");
    if (!svg || !curve || curve.length < 2) {
      if (svg) svg.innerHTML = "";
      return;
    }
    const ys = curve.map((p) => p.eq);
    const min = Math.min(...ys);
    const max = Math.max(...ys);
    const span = max - min || 1;
    const w = 320, h = 64, p = 4;
    const pts = curve.map((pt, i) => {
      const x = p + (i / (curve.length - 1)) * (w - 2 * p);
      const y = h - p - ((pt.eq - min) / span) * (h - 2 * p);
      return x.toFixed(1) + "," + y.toFixed(1);
    }).join(" ");
    const last = curve[curve.length - 1].eq;
    const color = last >= curve[0].eq ? "#7dba7d" : "#e07070";
    svg.setAttribute("viewBox", "0 0 " + w + " " + h);
    svg.innerHTML = '<polyline fill="none" stroke="' + color + '" stroke-width="2" points="' + pts + '"/>';
  }

  function render(d) {
    const b = d.book || {};
    const s = d.stats || {};
    $("kpi-eq").textContent = money(b.equity, 2);
    $("kpi-cash").textContent = money(b.cash, 2);
    const dayEl = $("kpi-day");
    dayEl.textContent = money(b.day_pnl, 2) + " (" + pct(b.day_pnl_pct) + ")";
    dayEl.className = cls(b.day_pnl);
    const totEl = $("kpi-total");
    totEl.textContent = money(b.total_pnl, 2) + " (" + pct(b.starting_equity ? (b.total_pnl / b.starting_equity) * 100 : 0) + ")";
    totEl.className = cls(b.total_pnl);
    $("kpi-open").textContent = String(b.n_open || 0);
    $("kpi-risk").textContent = money(b.open_risk_usd, 2);
    const halt = b.halt_daily || b.halt_weekly;
    $("kpi-halt").textContent = halt ? "HALT" : "open";
    $("kpi-halt").className = halt ? "down" : "up";
    $("scan-asof").textContent = d.scan_as_of || "UNKNOWN";
    $("clock").textContent = shortTs(d.now) + " UTC";

    const start = b.starting_equity || 100000;
    const eq = b.equity || start;
    const bar = Math.max(0, Math.min(100, (eq / start) * 100));
    $("prog-bar").style.width = bar.toFixed(1) + "%";
    $("prog-bar").className = "bar " + (eq >= start ? "upbg" : "downbg");
    $("prog-label").textContent = money(eq, 0) + " / " + money(start, 0) + " start";

    $("stat-closed").textContent = String(s.n_closed || 0);
    $("stat-fills").textContent = String(s.n_fills || 0);
    $("stat-hit").textContent = s.hit_rate == null ? "—" : s.hit_rate.toFixed(0) + "%";
    $("stat-wl").textContent = (s.n_wins || 0) + " / " + (s.n_losses || 0);
    $("stat-avg").textContent = s.avg_pnl == null ? "—" : money(s.avg_pnl, 2);
    spark(s.curve);

    const posBody = $("pos-body");
    const pos = b.positions || [];
    if (!pos.length) {
      posBody.innerHTML = '<tr><td colspan="8">No open paper positions.</td></tr>';
    } else {
      posBody.innerHTML = pos.map(function (p) {
        return "<tr>" +
          "<td>" + (p.id || "") + "</td>" +
          "<td>" + (p.symbol || "") + "</td>" +
          "<td>" + (p.side || "") + "</td>" +
          "<td>" + (p.qty || "") + "</td>" +
          "<td>" + fmtPx(p.entry) + "</td>" +
          "<td>" + fmtPx(p.last) + "</td>" +
          "<td>" + (p.stop == null ? "—" : fmtPx(p.stop)) + "</td>" +
          "<td class='" + cls(p.unrealized_usd) + "'>" + money(p.unrealized_usd, 2) + "</td>" +
          "</tr>";
      }).join("");
    }
    $("exposure").textContent = "Exposure by class: " + (JSON.stringify(b.exposure_by_class || {}) === "{}" ? "flat" : JSON.stringify(b.exposure_by_class));

    const trBody = $("tr-body");
    const trades = d.trades || [];
    if (!trades.length) {
      trBody.innerHTML = '<tr><td colspan="8">No paper fills yet. Book is flat at start.</td></tr>';
    } else {
      trBody.innerHTML = trades.map(function (t) {
        const pnl = t.pnl_num;
        const pnlS = pnl == null ? "—" : money(pnl, 2);
        return "<tr>" +
          "<td>" + shortTs(t.ts) + "</td>" +
          "<td>" + (t.id || "") + "</td>" +
          "<td>" + (t.ticket_id || "") + "</td>" +
          "<td>" + (t.symbol || "") + "</td>" +
          "<td>" + (t.side || "") + " " + (t.qty || "") + "</td>" +
          "<td>" + fmtPx(t.price_num) + "</td>" +
          "<td>" + (t.reason || "") + "</td>" +
          "<td class='" + (pnl == null ? "" : cls(pnl)) + "'>" + pnlS + "</td>" +
          "</tr>";
      }).join("");
    }

    const qBody = $("q-body");
    const quotes = d.quotes || [];
    if (!quotes.length) {
      qBody.innerHTML = '<tr><td colspan="6">No scan yet.</td></tr>';
    } else {
      qBody.innerHTML = quotes.map(function (q) {
        return "<tr>" +
          "<td>" + (q.symbol || "") + "</td>" +
          "<td>" + (q.last == null ? "UNKNOWN" : fmtPx(q.last)) + "</td>" +
          "<td class='" + cls(q.pct_day) + "'>" + pct(q.pct_day) + "</td>" +
          "<td>" + pct(q.pct_week) + "</td>" +
          "<td>" + (q.regime || "") + (q.unusual ? " · unusual" : "") + "</td>" +
          "<td class='" + (q.quality || "") + "'>" + (q.quality || "") + "</td>" +
          "</tr>";
      }).join("");
    }

    const hyp = $("hyp-list");
    const ideas = d.hypotheses || [];
    if (!ideas.length) {
      hyp.innerHTML = "<p>None. Do nothing is valid.</p>";
    } else {
      hyp.innerHTML = ideas.map(function (h) {
        return "<p><strong>" + (h.id || "") + " " + (h.symbol || "") + "</strong> " +
          (h.direction || "") + " · " + (h.horizon || "") + " · conf " + (h.confidence || "") +
          "<br>stop " + (h.stop == null ? "—" : h.stop) + " target " + (h.target == null ? "—" : h.target) +
          " R " + (h.r_multiple == null ? "—" : h.r_multiple) +
          "<br><span class='meta'>" + (h.invalidation || "") + "</span></p>";
      }).join("");
    }

    const act = $("act-list");
    const activity = d.activity || [];
    if (!activity.length) {
      act.innerHTML = "<div>Quiet.</div>";
    } else {
      act.innerHTML = activity.map(function (a) {
        return "<div>" + shortTs(a.ts) + " · " + (a.kind || "") + " — " + (a.message || "") + "</div>";
      }).join("");
    }
  }

  async function poll() {
    try {
      const k = new URLSearchParams(location.search).get("k") || "";
      const q = k ? ("?k=" + encodeURIComponent(k) + "&_=") : "?_=";
      const r = await fetch("/data" + q + Date.now(), { cache: "no-store", credentials: "same-origin" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      render(await r.json());
      $("live-dot").className = "dot on";
    } catch (e) {
      $("live-dot").className = "dot off";
    }
  }

  poll();
  setInterval(poll, 2000);
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(function () {});
})();
