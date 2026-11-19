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
