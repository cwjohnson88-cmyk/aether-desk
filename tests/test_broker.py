from aether.broker import (
    apply_marks,
    close_position,
    fill_price,
    load_account,
    mark_equity,
    notional_usd,
    open_market,
    point_value,
    save_account,
)


def _cfg():
    return {
        "spreads_bps": {"equity": 2.0, "forex": 1.0, "crypto": 5.0, "etf": 2.0},
        "slippage_bps": 2.0,
        "starting_equity": 100000.0,
        "daily_loss_halt_pct": 3.0,
        "weekly_loss_halt_pct": 6.0,
        "paper_only": True,
    }


def test_fill_price_buy_pays_spread_and_slip():
    # mid 100, spread 2bps + slip 2bps → half-spread 0.01 + slip 0.02 = 0.03
    px = fill_price(100.0, "buy", "equity", _cfg())
    assert abs(px - 100.03) < 1e-9
    px_s = fill_price(100.0, "sell", "equity", _cfg())
    assert abs(px_s - 99.97) < 1e-9


def test_usdjpy_point_value():
    assert abs(point_value(150.0, False) - (1.0 / 150.0)) < 1e-12
    assert point_value(150.0, True) == 1.0
    n = notional_usd(10_000, 150.0, False)
    assert abs(n - 10_000) < 1e-6


def test_round_trip_cash_conservation(desk):
    acct = load_account()
    start = float(acct["cash"])
    acct, t = open_market(
        acct,
        symbol="SPY",
        side="buy",
        qty=10,
        mid=100.0,
        asset_class="equity",
        usd_quoted=True,
        stop=95.0,
        target=110.0,
        why="test",
        risk_cfg=_cfg(),
    )
    fill = t["price"]
    assert abs(fill - 100.03) < 1e-9
    assert abs(acct["cash"] - (start - 10 * fill)) < 1e-6
    eq = mark_equity(acct, {"SPY": 100.0}, {"SPY": True})
    # equity = cash + 10*100 = start - 10*fill + 1000 = start - 0.3
    assert abs(eq - (start - 10 * (fill - 100.0))) < 1e-6
    acct, close = close_position(acct, t["ticket_id"], 100.0, reason="manual_close", why="flat", risk_cfg=_cfg())
    # sell fill 99.97; pnl = 10 * (99.97 - 100.03) = -0.6
    assert abs(float(close["pnl_usd"]) - 10 * (99.97 - 100.03)) < 1e-6
    assert abs(acct["cash"] - (start + float(close["pnl_usd"]))) < 1e-6
    assert acct["positions"] == []


def test_stop_triggers_on_mark(desk):
    acct = load_account()
    acct, t = open_market(
        acct,
        symbol="SPY",
        side="buy",
        qty=8,
        mid=100.0,
        asset_class="equity",
        usd_quoted=True,
        stop=99.0,
        target=110.0,
        why="stop test",
        risk_cfg=_cfg(),
    )
    save_account(acct)
    acct = apply_marks(acct, {"SPY": 98.5}, {"SPY": True})
    assert acct["positions"] == []
    # last trade should be a stop
    from aether.paths import trades_path

    text = trades_path().read_text(encoding="utf-8")
    assert "stop" in text


def test_target_triggers_long(desk):
    acct = load_account()
    acct, t = open_market(
        acct,
        symbol="QQQ",
        side="buy",
        qty=5,
        mid=50.0,
        asset_class="etf",
        usd_quoted=True,
        stop=45.0,
        target=51.0,
        why="target test",
        risk_cfg=_cfg(),
    )
    acct = apply_marks(acct, {"QQQ": 51.5}, {"QQQ": True})
    assert acct["positions"] == []
