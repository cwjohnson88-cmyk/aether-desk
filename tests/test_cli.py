from aether.cli import build_parser, main


def test_parser_has_required_commands():
    p = build_parser()
    choices = None
    for a in p._actions:
        if a.dest == "cmd":
            choices = set(a.choices)
    assert choices == {"status", "brief", "scan", "ticket", "close", "report", "cycle", "ui"}


def test_status_smoke(desk, capsys):
    rc = main(["status"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "PAPER TRADING ONLY" in out
    assert "100,000.00" in out or "100000" in out
