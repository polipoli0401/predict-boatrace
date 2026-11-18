from datetime import datetime, timedelta

import race_day
from boatrace_sources import JST
from test_ev_board import CFG, flat_odds, make_pred

DAY = datetime(2026, 11, 19).date()


def info_doc(closed):
    return {"races": {"18-01": {"stadium_id": "18", "race_number": 1,
                                "closed_at": closed, "entrants": {"1": 1}}}}


def run_update(monkeypatch, results, now, odds_doc=None,
               closed="2026-11-19 12:30:00"):
    calls = iter(results)
    monkeypatch.setattr(race_day, "fetch_trio_odds",
                        lambda *a, **k: next(calls))
    monkeypatch.setattr(race_day, "now_jst", lambda: now)
    monkeypatch.setattr(race_day.time, "sleep", lambda s: None)
    monkeypatch.setattr(race_day, "odds_source_configured", lambda: True)
    cfg = dict(CFG, odds_window_minutes=150, odds_after_close_minutes=40,
               odds_request_interval_sec=0, odds_max_requests_per_run=40)
    preds = {"races": {"18-01": make_pred(closed=closed)}}
    return race_day.update_odds(DAY, info_doc(closed),
                                odds_doc or {"races": {}}, preds, cfg, None)


def ok(value=10.0, final=False):
    # labels as published by the odds page (Japanese source strings)
    return {"ok": True, "odds": flat_odds(value), "error": None,
            "label": "締切時オッズ" if final else "オッズ更新時間 12:00",
            "is_final": final}


FAIL = {"ok": False, "odds": None, "label": None, "is_final": False,
        "error": "HTTP 503"}


def test_success_then_failure_keeps_previous_odds(monkeypatch):
    t1 = datetime(2026, 11, 19, 12, 0, tzinfo=JST)
    doc = run_update(monkeypatch, [ok()], t1)
    e = doc["races"]["18-01"]
    assert e["status"] == "success" and e["odds"]
    assert e["odds_fetched_at"].startswith("2026-11-19T12:00")
    assert e["pre_close"]["decision"] == "Candidate"

    t2 = t1 + timedelta(minutes=10)
    doc = run_update(monkeypatch, [FAIL], t2, odds_doc=doc)
    e = doc["races"]["18-01"]
    assert e["status"] == "failed"
    assert e["last_error"] == "HTTP 503"
    assert e["odds"]                                  # previous odds kept
    assert e["odds_fetched_at"].startswith("2026-11-19T12:00")
    assert e["last_failure_at"].startswith("2026-11-19T12:10")


def test_pending_when_outside_window(monkeypatch):
    t = datetime(2026, 11, 19, 6, 0, tzinfo=JST)   # 6.5h before deadline
    doc = run_update(monkeypatch, [], t)
    assert doc["races"]["18-01"]["status"] == "pending"


def test_closing_odds_do_not_replace_pre_close_decision(monkeypatch):
    t1 = datetime(2026, 11, 19, 12, 20, tzinfo=JST)
    doc = run_update(monkeypatch, [ok(10.0)], t1)
    before = doc["races"]["18-01"]["pre_close"]
    t2 = datetime(2026, 11, 19, 12, 45, tzinfo=JST)   # after the deadline
    doc = run_update(monkeypatch, [ok(1.1, final=True)], t2, odds_doc=doc)
    e = doc["races"]["18-01"]
    assert e["is_final"] is True
    assert e["pre_close"] == before


def test_no_odds_source_configured_stays_pending(monkeypatch):
    monkeypatch.setattr(race_day, "odds_source_configured", lambda: False)
    monkeypatch.setattr(race_day, "fetch_trio_odds",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    preds = {"races": {"18-01": make_pred()}}
    doc = race_day.update_odds(DAY, info_doc("2026-11-19 12:30:00"),
                               {"races": {}}, preds, dict(CFG), None)
    assert doc["races"]["18-01"]["status"] == "pending"
