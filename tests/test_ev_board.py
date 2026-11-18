from datetime import datetime, timedelta

import pytest

from board import build_rows, render_html, render_markdown, sort_key
from boatrace_sources import JST
from ev_judge import (DECISION_CANDIDATE, DECISION_PASS, DECISION_UNDECIDABLE,
                      evaluate_race, required_odds)
from trio_prob import harville_trio

CFG = {"ev_min": 1.2, "prob_min": 0.05, "stale_minutes": 15,
       "max_candidates_per_race": 3, "show_combinations": 3}
NOW = datetime(2026, 11, 19, 12, 0, tzinfo=JST)
P_WIN = [0.45, 0.2, 0.12, 0.1, 0.08, 0.05]


def make_pred(sid="18", rno=1, closed="2026-11-19 12:30:00"):
    trio = harville_trio([1, 2, 3, 4, 5, 6], P_WIN)
    return {"stadium_id": sid, "race_number": rno, "closed_at": closed,
            "boats": [{"boat": b, "p_win": p, "p_top3": 0.5}
                      for b, p in zip(range(1, 7), P_WIN)],
            "entries": [{"boat": b, "racer_number": 4000 + b}
                        for b in range(1, 7)],
            "predictions": [{"combination": k, "probability": v}
                            for k, v in trio.items()],
            "predicted_at": "2026-11-19T00:40:00+09:00"}


def make_odds(values, fetched=NOW - timedelta(minutes=5), status="success"):
    return {"status": status,
            "odds_fetched_at": fetched.isoformat() if fetched else None,
            "odds": [{"combination": k, "value": v}
                     for k, v in values.items()] if values else None}


def flat_odds(value):
    return {k: value for k in harville_trio([1, 2, 3, 4, 5, 6], P_WIN)}


def test_expected_return_is_probability_times_odds():
    pred = make_pred()
    ev = evaluate_race(pred, make_odds(flat_odds(10.0)), NOW, CFG)
    for r in ev["rows"]:
        assert r["expected_return"] == pytest.approx(r["probability"] * 10.0)


def test_no_prediction_is_undecidable():
    ev = evaluate_race(None, make_odds(flat_odds(10.0)), NOW, CFG)
    assert ev["decision"] == DECISION_UNDECIDABLE
    assert ev["reason"] == "No prediction"


def test_no_odds_is_undecidable_but_keeps_rows():
    ev = evaluate_race(make_pred(), None, NOW, CFG)
    assert ev["decision"] == DECISION_UNDECIDABLE
    assert ev["reason"] == "No odds"
    assert ev["rows"] and all(r["odds"] is None for r in ev["rows"])


def test_stale_odds_are_undecidable():
    old = make_odds(flat_odds(100.0), fetched=NOW - timedelta(minutes=40))
    ev = evaluate_race(make_pred(), old, NOW, CFG)
    assert ev["stale"] is True
    assert ev["decision"] == DECISION_UNDECIDABLE


def test_candidate_and_pass():
    ev = evaluate_race(make_pred(), make_odds(flat_odds(10.0)), NOW, CFG)
    # top trio has p ~0.17 -> EV ~1.7 >= 1.2 and p >= 0.05
    assert ev["decision"] == DECISION_CANDIDATE
    assert 1 <= sum(r["candidate"] for r in ev["rows"]) <= 3
    ev = evaluate_race(make_pred(), make_odds(flat_odds(1.5)), NOW, CFG)
    assert ev["decision"] == DECISION_PASS


def test_high_ev_with_low_probability_is_not_candidate():
    odds = flat_odds(1.0)
    odds["4-5-6"] = 5000.0          # p tiny, EV huge
    ev = evaluate_race(make_pred(), make_odds(odds), NOW, CFG)
    assert ev["decision"] == DECISION_PASS
    assert not any(r["candidate"] for r in ev["rows"])


def test_scratched_boat_is_excluded_and_recomputed():
    odds = flat_odds(10.0)
    for k in odds:
        if "6" in k.split("-"):
            odds[k] = None
    ev = evaluate_race(make_pred(), make_odds(odds), NOW, CFG)
    assert ev["scratched"] == [6]
    assert all("6" not in r["combination"].split("-") for r in ev["rows"])


def test_required_odds():
    assert required_odds(0.08, CFG) == pytest.approx(15.0)
    assert required_odds(0.01, CFG) is None


def test_board_sort_and_keeps_races_without_odds():
    preds = {"races": {
        "24-01": make_pred("24", 1, "2026-11-19 15:16:00"),
        "18-02": make_pred("18", 2, "2026-11-19 09:13:00"),
        "21-01": make_pred("21", 1, "2026-11-19 09:13:00"),
        "18-01": make_pred("18", 1, "2026-11-19 09:13:00"),
    }}
    info = {"races": {}}
    odds = {"races": {"18-01": make_odds(flat_odds(10.0)),
                      "21-01": {"status": "failed", "odds": None,
                                "odds_fetched_at": None,
                                "last_error": "HTTP 500"}}}
    rows = build_rows(preds, info, odds, CFG, None,
                      datetime(2026, 11, 19, 9, 0, tzinfo=JST))
    assert [r["key"] for r in rows] == ["18-01", "18-02", "21-01", "24-01"]
    by = {r["key"]: r for r in rows}
    assert by["18-02"]["odds_status"] == "pending"
    assert by["21-01"]["odds_status"] == "failed"
    assert by["21-01"]["decision"] == DECISION_UNDECIDABLE
    html = render_html(rows, NOW.date(), NOW, CFG)
    assert html.count('<tr class=') == 4
    md = render_markdown(rows, NOW.date(), NOW, CFG)
    assert "Failed" in md and "Pending" in md


def test_sort_key_missing_deadline_last():
    a = {"closed_at": None, "stadium_id": "18", "race_number": 1}
    b = {"closed_at": "2026-11-19 20:00:00", "stadium_id": "24",
         "race_number": 12}
    assert sorted([a, b], key=sort_key)[0] is b
