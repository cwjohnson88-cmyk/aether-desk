from aether.broker import load_account, open_market, save_account
from aether.risk import check_ticket, idea_risk_usd


CFG = {
    "paper_only": True,
    "max_risk_pct_per_idea": 2.0,
    "max_correlated_positions": 6,
    "max_open_positions": 6,
    "daily_loss_halt_pct": 3.0,
    "weekly_loss_halt_pct": 6.0,
    "max_average_down": 1,
    "martingale": False,
    "require_stop": True,
    "spreads_bps": {"equity": 2.0, "etf": 2.0, "crypto": 5.0, "forex": 1.0},
    "slippage_bps": 2.0,
    "clusters": {
        "usd_risk": ["SPY", "QQQ", "NVDA", "AAPL", "MSFT", "AMZN", "META", "TSLA", "BTC-USD"],
        "gold": ["GLD"],
    },
    "starting_equity": 100000.0,
}


def test_idea_risk_math():
    # 100 shares, $2 stop → $200 risk
    assert abs(idea_risk_usd(100, 50.0, 48.0, True) - 200.0) < 1e-9


def test_blocks_missing_stop(desk):
    acct = load_account()
    g = check_ticket(acct, symbol="SPY", side="buy", qty=10, entry=100, stop=None, usd_quoted=True, risk_cfg=CFG)
    assert g["ok"] is False
    assert g["code"] == "STOP_REQUIRED"


def test_blocks_over_2pct(desk):
    acct = load_account()
    # 2% of 100k = 2000. qty 1000 * $3 stop = 3000 > 2000
    g = check_ticket(acct, symbol="SPY", side="buy", qty=1000, entry=100, stop=97, usd_quoted=True, risk_cfg=CFG)
    assert g["ok"] is False
    assert g["code"] == "IDEA_RISK"


def test_allows_inside_2pct(desk):
    acct = load_account()
    g = check_ticket(acct, symbol="SPY", side="buy", qty=100, entry=100, stop=98, usd_quoted=True, risk_cfg=CFG)
    assert g["ok"] is True
    assert g["risk_usd"] == 200.0


def test_daily_halt(desk):
    acct = load_account()
    acct["halt_daily"] = True
    g = check_ticket(acct, symbol="SPY", side="buy", qty=10, entry=100, stop=99, usd_quoted=True, risk_cfg=CFG)
    assert g["code"] == "HALT_DAILY"


def test_weekly_halt(desk):
    acct = load_account()
    acct["halt_weekly"] = True
    g = check_ticket(acct, symbol="SPY", side="buy", qty=10, entry=100, stop=99, usd_quoted=True, risk_cfg=CFG)
    assert g["code"] == "HALT_WEEKLY"


def test_cluster_cap(desk):
    acct = load_account()
    names = ["SPY", "QQQ", "NVDA", "AAPL", "MSFT", "AMZN"]
    for i, sym in enumerate(names):
        acct, _ = open_market(
            acct,
            symbol=sym,
            side="buy",
            qty=1,
            mid=100.0,
            asset_class="equity",
            usd_quoted=True,
            stop=99.0,
            target=110.0,
            why="cluster",
            risk_cfg=CFG,
        )
    save_account(acct)
    g = check_ticket(acct, symbol="TSLA", side="buy", qty=1, entry=100, stop=99, usd_quoted=True, risk_cfg=CFG)
    assert g["ok"] is False
    assert g["code"] in ("CLUSTER", "MAX_OPEN")


def test_no_martingale(desk):
    acct = load_account()
    trades = [{"symbol": "NVDA", "qty": "10", "pnl_usd": "-50", "reason": "stop"}]
    g = check_ticket(
        acct, symbol="NVDA", side="buy", qty=20, entry=100, stop=99, usd_quoted=True, trades=trades, risk_cfg=CFG
    )
    assert g["ok"] is False
    assert g["code"] == "MARTINGALE"


def test_average_down_once_then_block(desk):
    acct = load_account()
    acct, t = open_market(
        acct,
        symbol="GLD",
        side="buy",
        qty=10,
        mid=200.0,
        asset_class="etf",
        usd_quoted=True,
        stop=190.0,
        target=220.0,
        why="first",
        risk_cfg=CFG,
    )
    # first average down allowed
    from aether.broker import add_to_position

    acct, _ = add_to_position(acct, t["ticket_id"], qty=5, mid=190.0, why="add", risk_cfg=CFG)
    pos = acct["positions"][0]
    assert pos["average_down_count"] == 1
    g = check_ticket(
        acct, symbol="GLD", side="buy", qty=5, entry=180.0, stop=170.0, usd_quoted=True, risk_cfg=CFG
    )
    assert g["ok"] is False
    assert g["code"] == "AVG_DOWN"
