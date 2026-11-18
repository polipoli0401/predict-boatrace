"""Race-day update: entry changes, deadlines, exhibition status, trio odds,
expected return, decision and the race board.

Light by design: no model training. Re-prediction (only for races that
were not predicted at night or whose entrants changed) uses the boosters
saved by predict_boatrace.py.

Usage:
  python race_day.py                 # refresh info + odds + board
  python race_day.py --no-odds       # refresh info + board only
  python race_day.py --repredict never|auto|force
  TARGET_DATE=YYYY-MM-DD python race_day.py   # other day (testing)

Outputs:
  data/raceinfo/<date>.json, data/odds/<date>.json,
  data/predictions/<date>.json (only when re-predicted),
  site/index.html, and the Actions job summary when available.
"""
import argparse
import os
import time

import requests

from board import build_rows, load_verification, render_html, render_markdown
from boatrace_sources import (
    fetch_trio_odds,
    fetch_v1_day,
    iso_jst,
    load_day_programs,
    now_jst,
    odds_source_configured,
    race_key,
    race_status_from_v1,
    target_stadium_ids,
    today_jst,
)
from ev_judge import DECISION_CANDIDATE, evaluate_race, load_config, parse_jst
from race_store import (
    VERIFY_DIR,
    info_path,
    odds_path,
    pred_path,
    read_json,
    write_json_if_changed,
)
from trio_prob import load_calibration

SITE_DIR = "site"

ENTRY_OK = "Received"
ENTRY_CHANGED = "Changed"
ENTRY_MISSING = "Not yet"
EX_OK = "Received"
EX_MISSING = "Not yet"


# ------------------------------------------------------------
# race info (entrants / deadline / exhibition)
# ------------------------------------------------------------
def refresh_race_info(day, stadiums, preds_doc, prev_info):
    """Merge the latest deadline/entrants/exhibition status per race.
    Previously captured values are kept when a source returns nothing."""
    v1 = fetch_v1_day(day)
    status = race_status_from_v1(v1, stadiums) if v1 else {}
    prog_df, prog_meta = load_day_programs(day, stadiums, v1_data=v1)

    preds = (preds_doc or {}).get("races", {})
    prev = (prev_info or {}).get("races", {})
    races = {}
    keys = set(preds) | set(prev) | set(status) | \
        {race_key(s, r) for s, r in prog_meta}
    for key in keys:
        sid, rno = key.split("-")
        rno = int(rno)
        st = status.get(key, {})
        pv = prev.get(key, {})
        meta = prog_meta.get((sid, rno), {})
        pred = preds.get(key)

        entrants = st.get("entrants") or {}
        if not entrants and not prog_df.empty:
            rd = prog_df[(prog_df["stadium_id"] == sid)
                         & (prog_df["race_number"] == rno)]
            entrants = {str(int(b)): int(n) for b, n in
                        zip(rd["boat_number"], rd["racer_number"])
                        if n == n}
        if not entrants:
            entrants = pv.get("entrants") or {}

        closed_at = (st.get("closed_at") or meta.get("closed_at")
                     or pv.get("closed_at") or (pred or {}).get("closed_at"))

        note = None
        if not entrants:
            entry_status = ENTRY_MISSING
        elif pred:
            predicted = {str(e["boat"]): e["racer_number"]
                         for e in pred.get("entries", [])}
            if predicted and predicted != entrants:
                entry_status = ENTRY_CHANGED
                changed = sorted(set(predicted) ^ set(entrants)
                                 | {b for b in predicted
                                    if b in entrants
                                    and predicted[b] != entrants[b]})
                note = f"Boat {','.join(changed)} differs from the prediction"
            else:
                entry_status = ENTRY_OK
        else:
            entry_status = ENTRY_OK
            note = "Not predicted yet"

        ex_boats = st.get("exhibition_boats") or pv.get("exhibition_boats") or []
        if ex_boats and len(entrants) and len(ex_boats) < len(entrants):
            missing = sorted(set(entrants) - {str(b) for b in ex_boats})
            note = ((note + " / ") if note else "") + \
                f"No exhibition for boat {','.join(missing)} (possibly scratched)"
        races[key] = {
            "stadium_id": sid, "race_number": rno,
            "closed_at": closed_at,
            "entrants": entrants,
            "entry_status": entry_status,
            "entry_note": note,
            "exhibition_boats": ex_boats,
            "exhibition_status": EX_OK if ex_boats else EX_MISSING,
            "finished": bool(st.get("finished") or pv.get("finished")),
        }
    return {"date": day.isoformat(), "updated_at": iso_jst(),
            "races": dict(sorted(races.items()))}, prog_df, prog_meta


# ------------------------------------------------------------
# re-prediction with saved models (no training)
# ------------------------------------------------------------
def races_to_repredict(info_doc, preds_doc, now, mode):
    if mode == "never":
        return []
    preds = (preds_doc or {}).get("races", {})
    out = []
    for key, r in info_doc["races"].items():
        closed = parse_jst(r.get("closed_at"))
        if closed and closed <= now:
            continue
        if not r.get("entrants"):
            continue
        if mode == "force" or key not in preds or r["entry_status"] == ENTRY_CHANGED:
            out.append(key)
    return out


def repredict(day, keys, prog_df, prog_meta, now):
    """Inference-only prediction for the given race keys.
    Not written to prediction_history.csv: the forward test keeps the
    night prediction only."""
    import json

    import numpy as np
    import pandas as pd

    from predict_boatrace_lib import FEATURE_COLS, prepare_features, strategy_tickets
    from race_store import build_race_prediction, load_models, merge_predictions
    from trio_prob import trio_probabilities

    b_win, b_top3, ident = load_models()
    if b_win is None:
        print("Re-predict skipped: no saved models")
        return 0
    if ident.get("features") != FEATURE_COLS:
        print("Re-predict skipped: saved model features differ")
        return 0
    stadiums = target_stadium_ids()
    want = {(k.split("-")[0], int(k.split("-")[1])) for k in keys}
    prog = prog_df[[ (s, int(r)) in want for s, r in
                     zip(prog_df["stadium_id"], prog_df["race_number"])]] \
        if not prog_df.empty else prog_df
    if prog.empty:
        return 0

    raw = pd.read_csv("boatrace_results.csv")
    raw["stadium_id"] = raw["stadium_id"].astype(int).astype(str).str.zfill(2)
    raw = raw[raw["stadium_id"].isin(stadiums)]
    raw = raw.dropna(subset=["place", "boat_number"])
    raw = raw[raw["race_date"] < day.isoformat()]
    p = prog.copy()
    p["place"] = np.nan
    p["course_number"] = np.nan
    combined = prepare_features(pd.concat([raw, p], ignore_index=True))
    today = combined[combined["race_date"] == pd.Timestamp(day)]

    strategy, strat_filter = "honmei_1pt", {}
    if os.path.exists("optimal_strategy.json"):
        with open("optimal_strategy.json") as f:
            sj = json.load(f)
        strategy, strat_filter = sj.get("strategy", strategy), sj.get("filter", {})
    calibration = load_calibration()
    records = []
    for (sid, rno), race_df in today.groupby(["stadium_id", "race_number"]):
        race_df = race_df.copy()
        p1 = b_win.predict(race_df[FEATURE_COLS])
        p3 = b_top3.predict(race_df[FEATURE_COLS])
        race_df["p1"] = p1 / p1.sum() if p1.sum() > 0 else 1 / len(race_df)
        race_df["p3"] = p3
        tickets = strategy_tickets(strategy, strat_filter, race_df)
        trio_raw, trio_cal = trio_probabilities(
            race_df["boat_number"].tolist(), race_df["p1"].tolist(), calibration)
        meta = prog_meta.get((sid, int(rno)), {})
        records.append(build_race_prediction(
            day, sid, rno, meta.get("closed_at"), race_df, trio_raw, trio_cal,
            tickets, iso_jst(now), ident, meta.get("source"),
            kind="race-day update"))
    if records:
        merge_predictions(day, records, ident, calibration, iso_jst(now))
    return len(records)


# ------------------------------------------------------------
# odds
# ------------------------------------------------------------
def odds_targets(info_doc, odds_doc, now, cfg):
    """Races to fetch now, nearest deadline first:
    - deadline within the next odds_window_minutes, or
    - closed within odds_after_close_minutes and no closing odds yet."""
    out = []
    for key, r in info_doc["races"].items():
        closed = parse_jst(r.get("closed_at"))
        if not closed:
            continue
        mins = (closed - now).total_seconds() / 60
        entry = (odds_doc.get("races") or {}).get(key, {})
        if 0 < mins <= cfg["odds_window_minutes"]:
            out.append((closed, key))
        elif -cfg["odds_after_close_minutes"] <= mins <= 0 \
                and not entry.get("is_final"):
            out.append((closed, key))
    out.sort()
    return [k for _, k in out][:cfg["odds_max_requests_per_run"]]


def new_odds_entry(sid, rno):
    return {"stadium_id": sid, "race_number": rno, "status": "pending",
            "odds_fetched_at": None, "last_attempt_at": None,
            "last_failure_at": None, "last_error": None,
            "official_label": None, "is_final": False, "odds": None,
            "pre_close": None}


def update_odds(day, info_doc, odds_doc, preds_doc, cfg, calibration):
    races = odds_doc.setdefault("races", {})
    for key, r in info_doc["races"].items():
        races.setdefault(key, new_odds_entry(r["stadium_id"], r["race_number"]))
    if not odds_source_configured():
        print("Odds: no odds source configured (ODDS_BASE_URL); "
              "all races stay pending")
        return odds_doc
    targets = odds_targets(info_doc, odds_doc, now_jst(), cfg)
    session = requests.Session()
    ok = fail = 0
    for i, key in enumerate(targets):
        if i:
            time.sleep(cfg["odds_request_interval_sec"])
        entry = races[key]
        attempt_at = now_jst()
        res = fetch_trio_odds(day, entry["stadium_id"], entry["race_number"],
                              session=session)
        entry["last_attempt_at"] = iso_jst(attempt_at)
        if res["ok"]:
            ok += 1
            entry.update({
                "status": "success",
                "odds_fetched_at": iso_jst(attempt_at),
                "last_error": None,
                "official_label": res["label"],
                "is_final": res["is_final"],
                "odds": [{"combination": k, "value": v}
                         for k, v in sorted(res["odds"].items())],
            })
            closed = parse_jst(info_doc["races"][key].get("closed_at"))
            if closed and attempt_at < closed and not res["is_final"]:
                ev = evaluate_race((preds_doc or {}).get("races", {}).get(key),
                                   entry, attempt_at, cfg, calibration)
                entry["pre_close"] = {
                    "odds_fetched_at": entry["odds_fetched_at"],
                    "decision": ev["decision"], "reason": ev["reason"],
                    "candidates": [
                        {k: c[k] for k in ("combination", "probability",
                                           "odds", "expected_return")}
                        for c in ev["rows"] if c["candidate"]],
                }
        else:
            fail += 1
            # keep the previous successful odds; only the status changes
            entry["status"] = "failed"
            entry["last_failure_at"] = iso_jst(attempt_at)
            entry["last_error"] = res["error"]
    odds_doc["updated_at"] = iso_jst()
    print(f"Odds: {len(targets)} targeted, {ok} ok, {fail} failed")
    return odds_doc


# ------------------------------------------------------------
# main
# ------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-odds", action="store_true")
    ap.add_argument("--repredict", choices=["never", "auto", "force"],
                    default="auto")
    args = ap.parse_args()

    day = today_jst()
    cfg = load_config()
    stadiums = target_stadium_ids()
    calibration = load_calibration()

    preds_doc = read_json(pred_path(day))
    info_doc, prog_df, prog_meta = refresh_race_info(
        day, stadiums, preds_doc, read_json(info_path(day)))
    print(f"Race info: {len(info_doc['races'])} races "
          f"({sum(r['entry_status'] == ENTRY_CHANGED for r in info_doc['races'].values())} changed)")

    keys = races_to_repredict(info_doc, preds_doc, now_jst(), args.repredict)
    if keys:
        n = repredict(day, keys, prog_df, prog_meta, now_jst())
        print(f"Re-predicted {n} races: {', '.join(keys)}")
        preds_doc = read_json(pred_path(day))
        info_doc, _, _ = refresh_race_info(day, stadiums, preds_doc, info_doc)
    write_json_if_changed(info_path(day), info_doc)

    odds_doc = read_json(odds_path(day)) or {"date": day.isoformat(),
                                              "races": {}}
    if not args.no_odds:
        odds_doc = update_odds(day, info_doc, odds_doc, preds_doc, cfg,
                               calibration)
    else:
        for key, r in info_doc["races"].items():
            odds_doc["races"].setdefault(
                key, new_odds_entry(r["stadium_id"], r["race_number"]))
    write_json_if_changed(odds_path(day), odds_doc)

    now = now_jst()
    rows = build_rows(preds_doc, info_doc, odds_doc, cfg, calibration, now)
    verification = load_verification(os.path.join(VERIFY_DIR, "summary.json"))
    os.makedirs(SITE_DIR, exist_ok=True)
    with open(os.path.join(SITE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_html(rows, day, now, cfg, verification))
    md = render_markdown(rows, day, now, cfg)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(md + "\n")
    cands = sum(r["decision"] == DECISION_CANDIDATE and not r["is_closed"] for r in rows)
    print(f"Board: {len(rows)} races, {cands} open candidates -> "
          f"{SITE_DIR}/index.html")


if __name__ == "__main__":
    main()
