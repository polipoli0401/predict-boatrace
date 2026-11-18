"""Expected-return calculation and race-level decision.

expected return = calibrated trio probability x odds
(1.20 == 120%). Decision per race:

  Undecidable : no prediction, no usable odds, odds too old,
                          or the odds are the closing odds of a race
                          that has no pre-close decision.
  Candidate   : at least one combination with
                          expected return >= ev_min AND probability >=
                          prob_min, using fresh odds.
  Pass        : otherwise.

A high expected return alone never makes a candidate (prob_min guard).
"""
import json
from datetime import datetime

from boatrace_sources import JST
from trio_prob import combo_key, trio_probabilities

CONFIG_JSON = "ev_config.json"

DECISION_CANDIDATE = "Candidate"
DECISION_PASS = "Pass"
DECISION_UNDECIDABLE = "Undecidable"


def load_config(path=CONFIG_JSON):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.pop("_notes", None)
    return cfg


def parse_jst(text):
    """Accepts ISO-8601 with offset or 'YYYY-MM-DD HH:MM:SS' (JST)."""
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(str(text).replace(" ", "T"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=JST)


def required_odds(prob, cfg):
    """Break-even odds for the decision rule: the odds at which this
    combination would reach ev_min. None when the probability is below
    prob_min (such a combination is never a candidate)."""
    if prob is None or prob <= 0 or prob < cfg["prob_min"]:
        return None
    return cfg["ev_min"] / prob


def scratched_boats(odds_map):
    """Boats whose every combination has no odds while others do
    (shown as scratched on the odds page)."""
    if not odds_map or not any(v is not None for v in odds_map.values()):
        return []
    boats = {int(b) for k in odds_map for b in k.split("-")}
    out = []
    for b in sorted(boats):
        vals = [v for k, v in odds_map.items() if str(b) in k.split("-")]
        if vals and all(v is None for v in vals):
            out.append(b)
    return out


def evaluate_race(pred, odds_entry, now, cfg, calibration=None):
    """Return dict(decision, reason, rows, stale, scratched, odds_at).
    rows: list of {combination, probability, odds, expected_return,
    candidate} for display (candidates first, then by probability)."""
    result = {"decision": DECISION_UNDECIDABLE, "reason": None,
              "rows": [], "stale": False, "scratched": [],
              "odds_at": None, "recomputed": False}
    if not pred or not pred.get("predictions"):
        result["reason"] = "No prediction"
        return result

    probs = {p["combination"]: p["probability"] for p in pred["predictions"]}
    odds_map = None
    if odds_entry and odds_entry.get("odds"):
        odds_map = {o["combination"]: o["value"] for o in odds_entry["odds"]}
        result["odds_at"] = odds_entry.get("odds_fetched_at")

    scratched = scratched_boats(odds_map)
    if scratched and pred.get("boats"):
        _, probs = trio_probabilities(
            [b["boat"] for b in pred["boats"]],
            [b["p_win"] for b in pred["boats"]],
            calibration, exclude=scratched)
        result["scratched"] = scratched
        result["recomputed"] = True

    rows = []
    for combo, p in probs.items():
        o = odds_map.get(combo) if odds_map else None
        ev = p * o if (o is not None and o > 0) else None
        rows.append({"combination": combo_key(combo.split("-")),
                     "probability": p, "odds": o, "expected_return": ev,
                     "required_odds": required_odds(p, cfg),
                     "candidate": False})

    if odds_map is None:
        result["reason"] = "No odds"
        result["rows"] = _display_rows(rows, cfg)
        return result

    fetched = parse_jst(result["odds_at"])
    age_min = (now - fetched).total_seconds() / 60 if fetched else None
    if age_min is None or age_min > cfg["stale_minutes"]:
        result["stale"] = True

    cands = [r for r in rows
             if r["expected_return"] is not None
             and r["expected_return"] >= cfg["ev_min"]
             and r["probability"] >= cfg["prob_min"]]
    cands.sort(key=lambda r: -r["expected_return"])
    for r in cands[:cfg["max_candidates_per_race"]]:
        r["candidate"] = True

    if result["stale"]:
        result["decision"] = DECISION_UNDECIDABLE
        result["reason"] = "Odds too old"
    elif any(r["candidate"] for r in rows):
        result["decision"] = DECISION_CANDIDATE
    else:
        result["decision"] = DECISION_PASS
    if scratched:
        result["reason"] = ((result["reason"] + " / ") if result["reason"]
                            else "") + \
            f"Recomputed without scratched boat {','.join(map(str, scratched))}"
    result["rows"] = _display_rows(rows, cfg)
    return result


def _display_rows(rows, cfg):
    cands = [r for r in rows if r["candidate"]]
    cands.sort(key=lambda r: -r["expected_return"])
    rest = [r for r in rows if not r["candidate"]]
    rest.sort(key=lambda r: -r["probability"])
    n = max(cfg["show_combinations"], len(cands))
    return (cands + rest)[:n]
