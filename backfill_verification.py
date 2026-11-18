"""Backfill past race days for verification (no training).

backtest_result.csv already holds walk-forward probabilities for every
simulated race: the models for day D were trained only on days before D,
exactly like the night prediction. This script turns those rows into
data/predictions/<date>.json for a date range, fetches the closing odds
for those days, and re-runs the verification, so the verification table
has data without waiting for new race days.

Fairness: the trio calibration used here is refitted only on backtest
races BEFORE the start of the range (the stored trio_calibration.json
covers the range itself and would be in-sample).

Backfilled races are marked prediction_kind = "backfill" and are never
written to prediction_history.csv. Days that already have a prediction
file are left untouched.

Usage:
  python backfill_verification.py                 # last 30 backtest days
  python backfill_verification.py --days 60
  python backfill_verification.py --from 2026-10-01 --to 2026-11-17
"""
import argparse
import json
import os
from datetime import date, timedelta

import pandas as pd

import verify_trio
from boatrace_sources import iso_jst, target_stadium_ids
from calibrate_trio import BACKTEST_CSV, fit_map, race_samples
from closing_odds import fetch_and_store
from race_store import PRED_DIR, pred_path, write_json
from trio_prob import apply_calibration, harville_trio


def build_day(day, rows, calibration, created_at):
    races = {}
    for r in rows.itertuples():
        d = json.loads(r.boats_json)
        raw = harville_trio(d["bn"], d["p1"])
        cal = apply_calibration(raw, calibration)
        sid = str(r.stadium_id).zfill(2)
        key = f"{sid}-{int(r.race_number):02d}"
        races[key] = {
            "date": day.isoformat(), "stadium_id": sid,
            "race_number": int(r.race_number), "closed_at": None,
            "entry_source": "backtest_result.csv",
            "entries": [{"boat": int(b), "racer_number": None,
                         "racer_class": None} for b in d["bn"]],
            "boats": [{"boat": int(b), "p_win": float(p1),
                       "p_top3": float(p3)}
                      for b, p1, p3 in zip(d["bn"], d["p1"], d["p3"])],
            "predictions": [{"combination": k, "probability": round(v, 5),
                             "raw_probability": round(raw[k], 5)}
                            for k, v in sorted(cal.items(),
                                               key=lambda kv: -kv[1])],
            "strategy_tickets": [],
            "prediction_kind": "backfill",
            "predicted_at": created_at,
            "model_id": "walk-forward backtest",
        }
    return {"date": day.isoformat(), "updated_at": created_at,
            "model": {"model_id": "walk-forward backtest"},
            "calibration": {"method": calibration.get("method"),
                            "fit_period": calibration.get("fit_period")},
            "races": dict(sorted(races.items()))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start")
    ap.add_argument("--to", dest="end")
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()

    stadiums = target_stadium_ids()
    bt = pd.read_csv(BACKTEST_CSV).sort_values("race_date")
    bt = bt[bt["stadium_id"].astype(int).astype(str).str.zfill(2)
            .isin(stadiums)]
    last = date.fromisoformat(bt["race_date"].max())
    end = date.fromisoformat(args.end) if args.end else last
    start = (date.fromisoformat(args.start) if args.start
             else end - timedelta(days=args.days - 1))

    before = bt[bt["race_date"] < start.isoformat()]
    samples = list(race_samples(before))
    if not samples:
        raise SystemExit("No backtest races before the range to calibrate on")
    calibration = {"method": "harville_from_p_win+isotonic (backfill)",
                   "fit_period": [samples[0][0], samples[-1][0]],
                   **fit_map(samples)}
    print(f"Backfill {start} .. {end}; calibration fitted on "
          f"{len(samples)} races {samples[0][0]} .. {samples[-1][0]}")

    created = iso_jst()
    n_days = n_races = 0
    day = start
    while day <= end:
        rows = bt[bt["race_date"] == day.isoformat()]
        if not rows.empty and not os.path.exists(pred_path(day)):
            doc = build_day(day, rows, calibration, created)
            write_json(pred_path(day), doc)
            n_days += 1
            n_races += len(doc["races"])
            fetch_and_store(day, stadiums)
        day += timedelta(days=1)
    print(f"Backfilled {n_races} races on {n_days} days into {PRED_DIR}/")
    verify_trio.main()


if __name__ == "__main__":
    main()
