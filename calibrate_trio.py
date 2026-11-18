"""Fit the trio-probability calibration map from backtest_result.csv.

backtest_result.csv holds walk-forward (out-of-sample) morning-model
probabilities for every simulated race. For each race the 20 raw
Harville trio probabilities are computed and labelled hit / miss; an
isotonic regression maps raw -> observed frequency.

Validation: the map is first fitted on the oldest 80% of races and
evaluated on the newest 20% (time split). The stored map is then refitted
on all races. Both results are written into trio_calibration.json and
printed, so the calibration status can be checked at any time.
"""
import json
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from trio_prob import CALIBRATION_JSON, PROB_FLOOR, apply_calibration, harville_trio

BACKTEST_CSV = "backtest_result.csv"
HOLDOUT_SHARE = 0.2
BINS = [0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 1.0]


def race_samples(bt, pkey="p1"):
    """Yield (race_date, {combo: raw_prob}, actual_combo).
    pkey: "p1" (morning model) or "p1L" (live model)."""
    for row in bt.itertuples():
        d = json.loads(row.boats_json)
        actual = "-".join(str(b) for b in sorted(json.loads(row.actual_trio)))
        yield row.race_date, harville_trio(d["bn"], d[pkey]), actual


def fit_map(samples):
    x, y = [], []
    for _, raw, actual in samples:
        for k, v in raw.items():
            x.append(v)
            y.append(1.0 if k == actual else 0.0)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=PROB_FLOOR,
                             y_max=1.0).fit(x, y)
    return {"x": [float(v) for v in iso.X_thresholds_],
            "y": [float(v) for v in iso.y_thresholds_]}


def evaluate(samples, calibration):
    rows, ll = [], []
    for _, raw, actual in samples:
        probs = apply_calibration(raw, calibration)
        ll.append(-np.log(max(probs.get(actual, PROB_FLOOR), PROB_FLOOR)))
        for k, v in probs.items():
            rows.append((v, 1.0 if k == actual else 0.0))
    df = pd.DataFrame(rows, columns=["p", "hit"])
    df["bin"] = pd.cut(df["p"], BINS)
    table = df.groupby("bin", observed=True).agg(
        n=("hit", "size"), predicted=("p", "mean"), observed=("hit", "mean"))
    return {
        "log_loss": round(float(np.mean(ll)), 4),
        "brier": round(float(((df["p"] - df["hit"]) ** 2).mean()), 5),
        "table": [{"bin": str(b), "n": int(r.n),
                   "predicted": round(float(r.predicted), 4),
                   "observed": round(float(r.observed), 4)}
                  for b, r in table.iterrows()],
    }


def main():
    bt = pd.read_csv(BACKTEST_CSV).sort_values("race_date")
    samples = list(race_samples(bt))
    cut = int(len(samples) * (1 - HOLDOUT_SHARE))
    train, hold = samples[:cut], samples[cut:]

    holdout_map = fit_map(train)
    raw_eval = evaluate(hold, None)
    cal_eval = evaluate(hold, holdout_map)

    final_map = fit_map(samples)
    out = {
        "method": "harville_from_p_win+isotonic",
        "source": BACKTEST_CSV,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "n_races": len(samples),
        "fit_period": [samples[0][0], samples[-1][0]],
        "holdout": {
            "train_period": [train[0][0], train[-1][0]],
            "test_period": [hold[0][0], hold[-1][0]],
            "n_test_races": len(hold),
            "raw": raw_eval,
            "calibrated": cal_eval,
        },
        **final_map,
    }
    with open(CALIBRATION_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print(f"Calibration fitted on {len(samples)} races "
          f"({samples[0][0]} .. {samples[-1][0]})")
    print(f"Holdout {hold[0][0]} .. {hold[-1][0]} ({len(hold)} races): "
          f"log-loss raw {raw_eval['log_loss']} -> "
          f"calibrated {cal_eval['log_loss']}")
    print("  bin            n     raw pred/obs        calibrated pred/obs")
    raw_t = {r["bin"]: r for r in raw_eval["table"]}
    for r in cal_eval["table"]:
        rr = raw_t.get(r["bin"])
        raw_txt = (f"{rr['predicted']:.3f}/{rr['observed']:.3f}"
                   if rr else "   -   ")
        print(f"  {r['bin']:<14}{r['n']:>6}   {raw_txt}       "
              f"{r['predicted']:.3f}/{r['observed']:.3f}")
    print(f"Saved: {CALIBRATION_JSON}")


if __name__ == "__main__":
    main()
