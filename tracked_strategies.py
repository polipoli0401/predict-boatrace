"""Pre-registered ticket strategies tracked on new races only.

strategies.json holds a small set of strategies frozen on a given date
(frozen_at), chosen from past data. Their parameters must not be changed
afterwards: the point is to see whether they hold on races that were not
used to choose them.

At prediction time (night run and race-day re-prediction) the tickets of
every tracked strategy are computed from the pre-race probabilities and
stored in the race's prediction record ("tracked_tickets"), so the bets
are fixed before the race. verify_trio.py scores them on races dated on
or after frozen_at (never on backfilled races).
"""
import json
import os

import pandas as pd

from predict_boatrace_lib import build_ticket

STRATEGIES_JSON = "strategies.json"


def load_strategies(path=STRATEGIES_JSON):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("strategies", [])


def tickets_for(strategy, stadium_id, boats_df):
    """boats_df: boat_number, p1 (normalised win prob), p3.
    Returns a list of trio strings ("1-2-3"), or for a win-bet rule
    (rule["bet"] == "win") the model's top boat as ["1"]; the market
    condition of such a rule is checked after the race with the closing
    odds (verify_trio.py)."""
    rule = strategy["rule"]
    if rule.get("stadiums") and str(stadium_id).zfill(2) not in rule["stadiums"]:
        return []
    by = boats_df.sort_values("p1", ascending=False)
    if rule.get("bet") == "win":
        return [str(int(by.iloc[0]["boat_number"]))]
    top = float(by.iloc[0]["p1"])
    gap = top - (float(by.iloc[1]["p1"]) if len(by) > 1 else 0.0)
    if not (rule.get("prob_min", 0) <= top < rule.get("prob_max", 1.01)):
        return []
    if gap < rule.get("gap_min", 0):
        return []
    tickets = build_ticket(rule["ticket"], boats_df)
    return ["-".join(map(str, sorted(int(b) for b in t))) for t in tickets]


def tracked_tickets(stadium_id, boats_df, strategies=None):
    strategies = load_strategies() if strategies is None else strategies
    return {s["id"]: tickets_for(s, stadium_id, boats_df) for s in strategies}


def boats_df_from_record(race):
    return pd.DataFrame({"boat_number": [b["boat"] for b in race["boats"]],
                         "p1": [b["p_win"] for b in race["boats"]],
                         "p3": [b["p_top3"] for b in race["boats"]]})
