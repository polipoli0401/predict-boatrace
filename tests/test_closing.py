from closing_odds import parse_trio_closing
from verify_trio import closing_odds_of, rule_candidates

CFG = {"ev_min": 1.2, "prob_min": 0.05, "max_candidates_per_race": 3}


def test_parse_trio_closing_nested_layout():
    doc = {"programs": {"stadiums": {
        "18": {"races": {"1": {"odds": {"trio": {
            "1": {"2": {"3": 4.2, "4": None}},
            "2": {"3": {"4": 120}}}}}}},
        "5": {"races": {"1": {"odds": {"trio": {"1": {"2": {"3": 9.9}}}}}}},
    }}}
    out = parse_trio_closing(doc, ["18"])
    assert set(out) == {"18-01"}
    assert out["18-01"] == {"1-2-3": 4.2, "1-2-4": None, "2-3-4": 120.0}


def test_closing_odds_prefers_closing_then_final_live():
    e = {"closing": {"odds": [{"combination": "1-2-3", "value": 5.0}]},
         "is_final": True, "odds": [{"combination": "1-2-3", "value": 6.0}]}
    assert closing_odds_of(e) == {"1-2-3": 5.0}
    e = {"is_final": True, "odds": [{"combination": "1-2-3", "value": 6.0}]}
    assert closing_odds_of(e) == {"1-2-3": 6.0}
    assert closing_odds_of({"is_final": False, "odds": []}) is None


def test_rule_candidates_respects_prob_min_and_limit():
    probs = {"1-2-3": 0.2, "1-2-4": 0.1, "1-2-5": 0.08, "1-2-6": 0.06,
             "4-5-6": 0.001}
    odds = {"1-2-3": 7.0, "1-2-4": 13.0, "1-2-5": 16.0, "1-2-6": 21.0,
            "4-5-6": 9000.0}
    got = rule_candidates(probs, odds, CFG)
    assert [g[0] for g in got] == ["1-2-3", "1-2-4", "1-2-5"]  # EV 1.40,1.30,1.28
    assert all(g[0] != "4-5-6" for g in got)
