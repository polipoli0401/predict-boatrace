"""Compare analysis methods on the same races, out of sample.

Methods (trio probabilities for all 20 combinations):
  A  market        closing odds -> 1/odds, normalised (the bar to beat;
                   closing odds are only known after the deadline)
  B  morning       existing morning features (no race-day information)
  C  live          B + exhibition time / rank, tilt, exhibition ST,
                   wind speed, wave height (existing live features)
  D  live+         C + race-day items not used before: exhibition entry
                   course (and whether it differs from the lane), parts
                   and propeller changes, weight adjustment, head/tail
                   and cross wind components (wind direction is relative
                   to the start line in the source data)
  E  market+model  log-linear pool p ∝ market^a * D^b, (a, b) fitted on
                   earlier months only (does the model add information
                   the market does not price in?)

Protocol: monthly walk-forward from 2026-01. For month M, models
(P(win), LightGBM, same params as production) are trained on all rows
before M; trio probabilities via Harville; isotonic calibration and the
pool weights are fitted on predictions of earlier months only. Months
used only for calibration warm-up are not scored. Scores: log-loss of
the actual trio, top-1 hit rate, and the expected-return rule
(ev_config.json) with closing odds (ROI with bootstrap 95% CI).

Race-day items (D) exist in the day files from 2026-01-01 only; earlier
rows have them as missing. Day files and closing odds come from
CLOSING_ODDS_BASE_URL and are cached in cache/ (not committed).
Writes data/verification/method_comparison.{json,md}.

Usage: python method_comparison.py [--start 2026-01] [--score-from 2026-04]
"""
import argparse
import math
import os
from datetime import date, timedelta

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

import ev_backtest as eb
from boatrace_sources import STADIUM_NAMES, http_get, iso_jst, target_stadium_ids
from closing_odds import _base
from ev_judge import load_config, scratched_boats
from predict_boatrace_lib import FEATURE_COLS, FEATURE_COLS_LIVE, PARAMS, prepare_features
from race_store import VERIFY_DIR, write_json
from trio_prob import PROB_FLOOR, harville_trio

RACEDAY_CACHE = os.path.join("cache", "raceday_features.csv")
NEW_COLS = ["ex_course", "course_changed", "weight_adjustment",
            "propeller_new", "parts_count", "wind_tail", "wind_cross"]
FEATURES = {"B": FEATURE_COLS, "C": FEATURE_COLS_LIVE,
            "D": FEATURE_COLS_LIVE + NEW_COLS}
METHODS = ["A", "B", "C", "D", "E"]
LABELS = {"A": "A market (closing odds)", "B": "B morning model",
          "C": "C live model", "D": "D live+ model",
          "E": "E market + model D"}
GRID = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5]


# ------------------------------------------------------------
# race-day features from the day files
# ------------------------------------------------------------
def _wind(speed, direction):
    if not speed or direction in (None, 17):
        return 0.0, 0.0
    ang = math.radians((int(direction) - 1) * 22.5)   # 1 = "north"
    # 5 ("east") = tailwind, 13 ("west") = headwind (relative directions)
    return speed * math.sin(ang), speed * math.cos(ang)


def raceday_rows(doc, stadiums):
    out = []
    st = ((doc or {}).get("programs") or {}).get("stadiums") or {}
    for sk, sv in st.items():
        sid = str(sk).zfill(2)
        if sid not in stadiums:
            continue
        for rk, race in ((sv or {}).get("races") or {}).items():
            prev = (race or {}).get("preview") or {}
            racers = prev.get("racers") if isinstance(prev.get("racers"), dict) else {}
            tail, cross = _wind(prev.get("wind_speed"),
                                prev.get("wind_direction_number"))
            for ek, r in racers.items():
                if not isinstance(r, dict):
                    continue
                boat = int(r.get("entry_number") or ek)
                course = r.get("course_number")
                parts = r.get("parts")
                out.append({
                    "race_date": race.get("date"), "stadium_id": sid,
                    "race_number": int(rk), "boat_number": boat,
                    "ex_course": course,
                    "course_changed": (None if course is None
                                       else int(course != boat)),
                    "weight_adjustment": r.get("weight_adjustment"),
                    "propeller_new": (None if "propeller" not in r
                                      else int(r.get("propeller") == "新")),
                    "parts_count": (len(parts) if isinstance(parts, list)
                                    else None),
                    "wind_tail": tail, "wind_cross": cross,
                })
    return out


def load_raceday(start, end, stadiums):
    have = pd.DataFrame()
    if os.path.exists(RACEDAY_CACHE):
        have = pd.read_csv(RACEDAY_CACHE, dtype={"stadium_id": str})
    done = set(have["race_date"].unique()) if not have.empty else set()
    base, rows, d = _base(), [], start
    while d <= end:
        ds = d.isoformat()
        if ds not in done and base:
            resp, _ = http_get(f"{base}/{d.year}/{d.strftime('%Y%m%d')}.json")
            if resp is not None and resp.status_code == 200:
                got = raceday_rows(resp.json(), stadiums)
                rows += got or [{"race_date": ds, "stadium_id": "--"}]
        d += timedelta(days=1)
    if rows:
        have = pd.concat([have, pd.DataFrame(rows)], ignore_index=True)
        os.makedirs("cache", exist_ok=True)
        have.to_csv(RACEDAY_CACHE, index=False)
    have = have[have["stadium_id"] != "--"].copy()
    have["stadium_id"] = have["stadium_id"].astype(str).str.zfill(2)
    return have


# ------------------------------------------------------------
# helpers
# ------------------------------------------------------------
def fit_iso(pairs):
    if len(pairs) < 1000:
        return None
    x, y = zip(*pairs)
    return IsotonicRegression(out_of_bounds="clip", y_min=PROB_FLOOR,
                              y_max=1.0).fit(x, y)


def apply_iso(raw, iso):
    if iso is None:
        return raw
    keys = list(raw)
    v = np.clip(iso.predict([raw[k] for k in keys]), PROB_FLOOR, None)
    v = v / v.sum()
    return dict(zip(keys, v))


def pool(market, model, a, b):
    keys = [k for k in market if k in model]
    v = np.array([max(market[k], PROB_FLOOR) ** a * max(model[k], PROB_FLOOR) ** b
                  for k in keys])
    v = v / v.sum()
    return dict(zip(keys, v))


def fit_pool(races):
    best = (float("inf"), 1.0, 0.0)
    for a in GRID:
        for b in GRID:
            if a == 0 and b == 0:
                continue
            ll = -sum(math.log(max(pool(r["market"], r["cal"]["D"], a, b)
                                   .get(r["actual"], PROB_FLOOR), PROB_FLOOR))
                      for r in races)
            best = min(best, (ll, a, b))
    return best[1], best[2]


def score(races, probs_key, cfg, rng):
    ll, top1, per_race, tickets, er = 0.0, 0, [], 0, 0.0
    for r in races:
        p = r["final"][probs_key]
        ll -= math.log(max(p.get(r["actual"], PROB_FLOOR), PROB_FLOOR))
        top1 += int(max(p, key=p.get) == r["actual"])
        cands = sorted(((k, q, r["odds"].get(k)) for k, q in p.items()),
                       key=lambda t: t[0])
        cands = [(k, q, o, q * o) for k, q, o in cands
                 if o and q >= cfg["prob_min"] and q * o >= cfg["ev_min"]]
        cands.sort(key=lambda t: -t[3])
        cands = cands[:cfg["max_candidates_per_race"]]
        if cands:
            hit = any(k == r["actual"] for k, *_ in cands)
            per_race.append((100 * len(cands),
                             (r["payout"] or 0.0) if hit else 0.0))
            tickets += len(cands)
            er += sum(c[3] for c in cands)
    n = len(races)
    inv = sum(i for i, _ in per_race)
    ret = sum(x for _, x in per_race)
    ci = None
    if len(per_race) >= 30:
        arr = np.array(per_race)
        idx = rng.integers(0, len(arr), size=(2000, len(arr)))
        rois = arr[idx, 1].sum(1) / arr[idx, 0].sum(1) * 100
        ci = [round(float(np.percentile(rois, 2.5)), 1),
              round(float(np.percentile(rois, 97.5)), 1)]
    return {"races": n, "log_loss": round(ll / n, 4) if n else None,
            "top1_hit": round(100 * top1 / n, 1) if n else None,
            "tickets": tickets,
            "roi": round(100 * ret / inv, 1) if inv else None,
            "roi_ci95": ci,
            "mean_expected_return": round(100 * er / tickets, 1) if tickets else None}


# ------------------------------------------------------------
# main
# ------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-01")
    ap.add_argument("--score-from", default="2026-04")
    args = ap.parse_args()
    stadiums = target_stadium_ids()
    cfg = load_config()
    rng = np.random.default_rng(7)

    raw = pd.read_csv("boatrace_results.csv")
    raw["stadium_id"] = raw["stadium_id"].astype(int).astype(str).str.zfill(2)
    raw = raw[raw["stadium_id"].isin(stadiums)].dropna(subset=["boat_number"])
    last_day = date.fromisoformat(raw["race_date"].max())
    first_day = date.fromisoformat(args.start + "-01")

    rd = load_raceday(first_day, last_day, stadiums)
    closing = eb.load_closing(first_day, last_day, stadiums)
    df = prepare_features(raw)
    df["race_date"] = df["race_date"].dt.strftime("%Y-%m-%d")
    df = df.merge(rd, how="left",
                  on=["race_date", "stadium_id", "race_number", "boat_number"])
    for c in NEW_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    print(f"Rows {len(df)}; race-day coverage from {args.start}: "
          f"{df.loc[df['race_date'] >= first_day.isoformat(), 'ex_course'].notna().mean():.1%}")

    months = sorted({d[:7] for d in df["race_date"] if d >= first_day.isoformat()})
    races_all, importance = [], None
    for m in months:
        train = df[(df["race_date"] < m + "-01") & df["place"].notna()]
        test = df[df["race_date"].str.startswith(m)]
        models = {}
        for k, cols in FEATURES.items():
            mdl = lgb.LGBMClassifier(**PARAMS)
            mdl.fit(train[cols], (train["place"] == 1).astype(int))
            models[k] = mdl
        importance = pd.Series(models["D"].booster_.feature_importance("gain"),
                               index=FEATURES["D"])
        for (d, sid, rno), g in test.groupby(["race_date", "stadium_id",
                                               "race_number"]):
            odds = closing.get((d, f"{sid}-{int(rno):02d}"))
            top = g[pd.to_numeric(g["place"], errors="coerce") <= 3]
            if not odds or len(top) != 3 or g["payout_trio"].isna().all():
                continue
            out = set(scratched_boats(odds))
            g = g[~g["boat_number"].astype(int).isin(out)]
            if len(g) < 3:
                continue
            inv = {k: 1 / v for k, v in odds.items() if v}
            tot = sum(inv.values())
            rec = {"date": d, "month": m, "sid": sid,
                   "actual": "-".join(str(int(b)) for b in sorted(top["boat_number"])),
                   "payout": float(g["payout_trio"].dropna().iloc[0]),
                   "odds": odds, "market": {k: v / tot for k, v in inv.items()},
                   "raw": {}}
            for k, mdl in models.items():
                p = mdl.predict_proba(g[FEATURES[k]])[:, 1]
                rec["raw"][k] = harville_trio(g["boat_number"].tolist(),
                                              p / p.sum())
            races_all.append(rec)
        print(f"{m}: trained on {len(train)} rows, "
              f"{sum(r['month'] == m for r in races_all)} races")

    # calibration / pool fitted on earlier months only
    for m in months:
        prev = [r for r in races_all if r["month"] < m]
        cur = [r for r in races_all if r["month"] == m]
        isos = {k: fit_iso([(v, float(c == r["actual"])) for r in prev
                            for c, v in r["raw"][k].items()]) for k in FEATURES}
        for r in prev + cur:
            r.setdefault("cal", {})
        for r in cur:
            r["cal"] = {k: apply_iso(r["raw"][k], isos[k]) for k in FEATURES}
        a, b = fit_pool([r for r in prev if r.get("cal")]) if prev else (1.0, 0.0)
        for r in cur:
            r["final"] = {"A": r["market"], **r["cal"],
                          "E": pool(r["market"], r["cal"]["D"], a, b)}
            r["pool"] = (a, b)

    scored = [r for r in races_all if r["month"] >= args.score_from]
    res = {"generated_at": iso_jst(),
           "scored_period": f"{scored[0]['date']} .. {scored[-1]['date']}",
           "races": len(scored), "methods": LABELS,
           "pool_weights_last": scored[-1]["pool"],
           "overall": {k: score(scored, k, cfg, rng) for k in METHODS},
           "by_stadium": {}, "by_month": {}}
    for sid in sorted({r["sid"] for r in scored}):
        sub = [r for r in scored if r["sid"] == sid]
        res["by_stadium"][sid] = {k: score(sub, k, cfg, rng) for k in METHODS}
    for m in sorted({r["month"] for r in scored}):
        sub = [r for r in scored if r["month"] == m]
        res["by_month"][m] = {k: score(sub, k, cfg, rng)["log_loss"]
                              for k in METHODS}
    imp = (importance / importance.sum() * 100).round(2)
    res["importance_new_features_pct"] = {c: float(imp[c]) for c in NEW_COLS}
    res["importance_top10_pct"] = {k: float(v) for k, v in
                                   imp.sort_values(ascending=False).head(10).items()}

    write_json(os.path.join(VERIFY_DIR, "method_comparison.json"), res)
    with open(os.path.join(VERIFY_DIR, "method_comparison.md"), "w",
              encoding="utf-8") as f:
        f.write(to_markdown(res))
    for k in METHODS:
        o = res["overall"][k]
        print(f"{LABELS[k]:<26} log-loss {o['log_loss']}  top1 {o['top1_hit']}%  "
              f"tickets {o['tickets']}  ROI {o['roi']} {o['roi_ci95']}")


def to_markdown(res):
    def f(v):
        return "—" if v is None else v

    def ci(v):
        return "—" if not v else f"{v[0]}–{v[1]}"
    md = [f"# Method comparison ({res['scored_period']}, {res['races']} races)",
          "", f"Generated: {res['generated_at']}. Monthly walk-forward; "
          + "calibration and pool weights fitted on earlier months only. "
          + "ROI uses closing odds (not known before the deadline).", "",
          "## Overall", "",
          "| Method | Log-loss | Top-1 hit % | Tickets | ROI % | ROI 95% CI "
          + "| Mean exp. return % |", "|---|---|---|---|---|---|---|"]
    for k, o in res["overall"].items():
        md.append(f"| {res['methods'][k]} | {f(o['log_loss'])} | {f(o['top1_hit'])} "
                  + f"| {o['tickets']} | {f(o['roi'])} | {ci(o['roi_ci95'])} "
                  + f"| {f(o['mean_expected_return'])} |")
    md += ["", "Pool weights (market, model) in the last month: "
           + f"{res['pool_weights_last']}", "", "## By stadium (log-loss / ROI %)",
           "", "| Stadium | " + " | ".join(res["methods"][k] for k in res["overall"])
           + " |", "|---" * (len(res["overall"]) + 1) + "|"]
    for sid, v in res["by_stadium"].items():
        md.append(f"| {STADIUM_NAMES.get(sid, sid)} | "
                  + " | ".join(f"{v[k]['log_loss']} / {f(v[k]['roi'])}" for k in v)
                  + " |")
    md += ["", "## By month (log-loss)", "",
           "| Month | " + " | ".join(res["overall"]) + " |",
           "|---" * (len(res["overall"]) + 1) + "|"]
    for m, v in res["by_month"].items():
        md.append(f"| {m} | " + " | ".join(str(v[k]) for k in v) + " |")
    md += ["", "## Model D: share of total gain (last month's model)", "",
           "| Feature | Gain % |", "|---|---|"]
    md += [f"| {k} (new) | {v} |" for k, v in res["importance_new_features_pct"].items()]
    md += ["", "Top 10:", "", "| Feature | Gain % |", "|---|---|"]
    md += [f"| {k} | {v} |" for k, v in res["importance_top10_pct"].items()]
    md += ["", "Lower log-loss is better. Buying at random at market odds "
           + "returns about 75% (trio takeout ~25%)."]
    return "\n".join(md) + "\n"


if __name__ == "__main__":
    main()
