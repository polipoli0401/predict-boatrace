import pandas as pd

from tracked_strategies import tickets_for, tracked_tickets
from verify_trio import tracked_summary

S = {"id": "S1", "name": "fav", "frozen_at": "2026-11-19",
     "rule": {"ticket": "honmei_1pt", "prob_min": 0.3, "prob_max": 0.4,
              "gap_min": 0.2, "stadiums": ["18"]}}


def boats(p1):
    return pd.DataFrame({"boat_number": range(1, 7), "p1": p1,
                         "p3": [0.9, 0.6, 0.5, 0.4, 0.3, 0.2]})


def test_filter_and_stadium():
    ok = boats([0.36, 0.10, 0.15, 0.14, 0.13, 0.12])     # top 0.36, gap 0.21
    assert tickets_for(S, "18", ok) == ["1-3-4"]          # top-3 by P(win)
    assert tickets_for(S, "24", ok) == []                 # other stadium
    weak_gap = boats([0.35, 0.30, 0.1, 0.1, 0.1, 0.05])
    assert tickets_for(S, "18", weak_gap) == []
    too_strong = boats([0.5, 0.1, 0.1, 0.1, 0.1, 0.1])
    assert tickets_for(S, "18", too_strong) == []
    assert tracked_tickets("24", ok, [S]) == {"S1": []}


def test_tracked_summary_counts_only_new_live_races(tmp_path):
    import json
    def write(day, kind, tickets):
        p = tmp_path / f"{day}.json"
        p.write_text(json.dumps({"date": day, "races": {"18-01": {
            "stadium_id": "18", "race_number": 1, "prediction_kind": kind,
            "tracked_tickets": {"S1": tickets}}}}))
        return str(p)
    files = [write("2026-11-18", "night", ["1-2-3"]),     # before frozen_at
             write("2026-11-19", "night", ["1-2-3"]),     # counted, hit
             write("2026-11-20", "backfill", ["1-2-3"]),  # backfill: ignored
             write("2026-11-21", "night", ["1-2-4"])]     # counted, miss
    results = {(d, "18", 1): ("1-2-3", 500.0)
               for d in ["2026-11-18", "2026-11-19", "2026-11-20", "2026-11-21"]}
    out = tracked_summary(files, results, [S])["S1"]
    assert out["races"] == 2 and out["hits"] == 1
    assert out["invest"] == 200 and out["return"] == 500
    assert out["roi"] == 250.0


S4 = {"id": "S4", "name": "win", "frozen_at": "2026-11-20",
      "rule": {"bet": "win", "condition": "not_favourite"}}


def test_win_rule_ticket_is_model_top_boat():
    df = boats([0.20, 0.45, 0.10, 0.10, 0.10, 0.05])
    assert tickets_for(S4, "21", df) == ["2"]


def test_win_bet_result_condition():
    from verify_trio import win_bet_result
    closing = {"closing": {"win_odds": {"1": 2.8, "2": 1.9, "3": 6.0},
                           "win_payouts": [["1", 280]]}}
    assert win_bet_result(["1"], closing, S4["rule"]) == (100, 280.0)   # not fav, hit
    assert win_bet_result(["2"], closing, S4["rule"]) is None           # favourite
    assert win_bet_result(["3"], closing, S4["rule"]) == (100, 0.0)     # miss
    assert win_bet_result(["1"], {}, S4["rule"]) is None                # no data


def test_parse_win_closing():
    from closing_odds import parse_win_closing
    doc = {"programs": {"stadiums": {"18": {"races": {"1": {
        "odds": {"win": {"1": 2.8, "2": 1.9, "3": None}},
        "result": {"payouts": {"win": [{"combination": "1", "amount": 280}]}}}}}}}}
    out = parse_win_closing(doc, ["18"])
    assert out["18-01"]["odds"] == {"1": 2.8, "2": 1.9}
    assert out["18-01"]["payouts"] == [["1", 280]]
