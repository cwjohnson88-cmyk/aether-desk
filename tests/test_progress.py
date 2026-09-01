from aether.progress import blotter_stats, trades_newest


def test_empty_blotter_is_unknown_hit_rate_not_invented():
    book = {"starting_equity": 100000.0, "equity": 100000.0}
    s = blotter_stats([], book)
    assert s["n_closed"] == 0
    assert s["hit_rate"] is None
    assert s["curve"][0]["eq"] == 100000.0
    assert s["curve"][-1]["eq"] == 100000.0


def test_hit_rate_and_curve_from_closed_fills():
    trades = [
        {"id": "F1", "ts": "t1", "pnl_usd": "", "reason": "entry"},
        {"id": "X1", "ts": "t2", "pnl_usd": "50", "reason": "target"},
        {"id": "X2", "ts": "t3", "pnl_usd": "-20", "reason": "stop"},
    ]
    book = {"starting_equity": 100000.0, "equity": 100030.0}
    s = blotter_stats(trades, book)
    assert s["n_fills"] == 3
    assert s["n_closed"] == 2
    assert s["n_wins"] == 1
    assert s["n_losses"] == 1
    assert abs(s["hit_rate"] - 50.0) < 1e-9
    assert abs(s["gross_closed_pnl"] - 30.0) < 1e-9
    assert s["curve"][0]["eq"] == 100000.0
    assert abs(s["curve"][1]["eq"] - 100050.0) < 1e-9
    assert abs(s["curve"][2]["eq"] - 100030.0) < 1e-9


def test_newest_first():
    trades = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    out = trades_newest(trades, 2)
    assert [t["id"] for t in out] == ["3", "2"]
