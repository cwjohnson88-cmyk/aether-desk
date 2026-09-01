from aether.market import _from_snapshot
from aether.models import Quote


def test_unknown_when_no_snapshot():
    q = _from_snapshot(
        {"id": "FAKE", "class": "equity", "tradable": True, "cluster": "usd_risk", "usd_quoted": True},
        {},
    )
    assert q.quality == "unknown"
    assert q.last is None
    assert "no last-good" in q.reason


def test_stale_from_snapshot_not_invented():
    snap = {
        "as_of": "2026-08-31T00:00:00+00:00",
        "quotes": {
            "SPY": Quote(
                symbol="SPY",
                asset_class="etf",
                last=500.0,
                prev_close=499.0,
                pct_day=0.2,
                pct_week=1.0,
                high=501.0,
                low=498.0,
                atr20=4.0,
                regime="uptrend",
                unusual=False,
                news_vacuum=False,
                source="yfinance:SPY",
                as_of="2026-08-31",
                quality="ok",
                reason="",
                tradable=True,
                cluster="usd_risk",
                usd_quoted=True,
            ).to_dict()
        },
    }
    q = _from_snapshot({"id": "SPY", "class": "etf", "tradable": True, "cluster": "usd_risk", "usd_quoted": True}, snap)
    assert q.quality == "stale"
    assert q.last == 500.0
    assert q.source.startswith("snapshot:")


def test_quote_unknown_factory():
    q = Quote.unknown("EURUSD", "forex", "network down")
    assert q.last is None
    assert q.quality == "unknown"
    assert q.regime == "unknown"
