"""Out-of-sample test of the expected-return rule with closing odds.

Uses the walk-forward probabilities in backtest_result.csv (models for day
D trained only on days before D) for a date range, the trio calibration
refitted ONLY on races before the range, and the closing trio odds of
each day (CLOSING_ODDS_BASE_URL). Reports, per stadium / month / total:
  - model vs market log-loss (market = closing odds inverted, normalised)
  - the decision rule (ev_config.json) applied with closing odds:
    tickets, hit rate, ROI with a 95% bootstrap interval, mean expected
    return
  - sensitivity to the expected-return threshold
  - probability calibration
Closing odds are not known before the deadline, so this measures the
rule and the probabilities, not achievable betting results.

Closing odds are cached in cache/closing_trio.csv (not committed).
Writes data/verification/ev_backtest.json and ev_backtest.md.

--live uses the "live" model probabilities instead (morning features +
exhibition time / rank, tilt, exhibition start timing, wind and wave),
restricted to races with exhibition data; the calibration is fitted on
earlier live-model races. Output: ev_backtest_live.{json,md}.

Usage: python ev_backtest.py --from 2026-01-01 --to 2026-11-17 [--live]
"""
import argparse
import json
import math
import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

from boatrace_sources import STADIUM_NAMES, http_get, iso_jst, target_stadium_ids
from calibrate_trio import BACKTEST_CSV, BINS, fit_map, race_samples
from closing_odds import _base, parse_trio_closing
from ev_judge import load_config
from race_store import VERIFY_DIR, write_json
from trio_prob import PROB_FLOOR, apply_calibration, harville_trio

CACHE = os.path.join("cache", "closing_trio.csv")
THRESHOLDS = [1.0, 1.2, 1.5, 2.0, 3.0]
BOOT = 2000


def load_closing(start, end, stadiums):
    """{(date, race_key): {combo: odds}} using / extending the cache."""
    have = pd.DataFrame(columns=["date", "key", "combo", "odds"])
    if os.path.exists(CACHE):
        have = pd.read_csv(CACHE, dtype={"key": str})
    done = set(have["date"].unique())
    rows = []
    base = _base()
    d = start
    while d <= end:
        ds = d.isoformat()
        if ds not in done and base:
            resp, _ = http_get(f"{base}/{d.year}/{d.strftime('%Y%m%d')}.json")
            if resp is not None and resp.status_code == 200:
                for key, combos in parse_trio_closing(resp.json(),
                                                      stadiums).items():
                    rows += [(ds, key, k, v) for k, v in combos.items()]
                rows.append((ds, "-", "-", None))   # mark date as fetched
        d += timedelta(days=1)
    if rows:
        have = pd.concat([have, pd.DataFrame(rows, columns=have.columns)],
                         ignore_index=True)
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        have.to_csv(CACHE, index=False)
    out = {}
    for r in have[have["key"] != "-"].itertuples():
        out.setdefault((r.date, r.key), {})[r.combo] = (
            None if pd.isna(r.odds) else float(r.odds))
    return out


def race_records(bt, calibration, closing, pkey="p1"):
    recs = []
    for r in bt.itertuples():
        sid = str(r.stadium_id).zfill(2)
        key = f"{sid}-{int(r.race_number):02d}"
        odds = closing.get((r.race_date, key))
        if not odds:
            continue
        d = json.loads(r.boats_json)
        probs = apply_calibration(harville_trio(d["bn"], d[pkey]), calibration)
        actual = "-".join(str(b) for b in sorted(json.loads(r.actual_trio)))
        inv = {k: 1 / v for k, v in odds.items() if v}
        tot = sum(inv.values())
        recs.append({"date": r.race_date, "sid": sid, "probs": probs,
                     "odds": odds, "actual": actual,
                     "payout": (None if pd.isna(r.payout_trio)
                                else float(r.payout_trio)),
                     "market": {k: v / tot for k, v in inv.items()}})
    return recs


def rule_tickets(rec, cfg, ev_min):
    rows = [(k, p, rec["odds"].get(k)) for k, p in rec["probs"].items()]
    rows = [(k, p, o, p * o) for k, p, o in rows
            if o and p >= cfg["prob_min"] and p * o >= ev_min]
    rows.sort(key=lambda x: -x[3])
    return rows[:cfg["max_candidates_per_race"]]


def evaluate(recs, cfg, ev_min, rng=None):
    per_race = []   # (invest, return)
    tickets = hits = 0
    er = 0.0
    ll_model = ll_market = 0.0
    for rec in recs:
        ll_model -= math.log(max(rec["probs"].get(rec["actual"], PROB_FLOOR),
                                 PROB_FLOOR))
        ll_market -= math.log(max(rec["market"].get(rec["actual"], PROB_FLOOR),
                                  PROB_FLOOR))
        t = rule_tickets(rec, cfg, ev_min)
        if not t:
            continue
        hit = any(k == rec["actual"] for k, *_ in t)
        ret = (rec["payout"] or 0.0) if hit else 0.0
        per_race.append((100 * len(t), ret))
        tickets += len(t)
        hits += int(hit)
        er += sum(x[3] for x in t)
    n = len(recs)
    inv = sum(i for i, _ in per_race)
    ret = sum(r for _, r in per_race)
    out = {"races": n, "candidate_races": len(per_race), "tickets": tickets,
           "hits": hits,
           "hit_rate": round(100 * hits / len(per_race), 1) if per_race else None,
           "roi": round(100 * ret / inv, 1) if inv else None,
           "mean_expected_return": round(100 * er / tickets, 1) if tickets else None,
           "log_loss_model": round(ll_model / n, 4) if n else None,
           "log_loss_market": round(ll_market / n, 4) if n else None,
           "roi_ci95": None}
    if rng is not None and len(per_race) >= 30:
        arr = np.array(per_race)
        idx = rng.integers(0, len(arr), size=(BOOT, len(arr)))
        rois = arr[idx, 1].sum(1) / arr[idx, 0].sum(1) * 100
        out["roi_ci95"] = [round(float(np.percentile(rois, 2.5)), 1),
                           round(float(np.percentile(rois, 97.5)), 1)]
    return out


def calibration_table(recs):
    rows = [(p, 1.0 if k == r["actual"] else 0.0)
            for r in recs for k, p in r["probs"].items()]
    df = pd.DataFrame(rows, columns=["p", "hit"])
    df["bin"] = pd.cut(df["p"], BINS)
    return [{"bin": str(b), "n": int(len(g)),
             "predicted": round(float(g["p"].mean()), 4),
             "observed": round(float(g["hit"].mean()), 4)}
            for b, g in df.groupby("bin", observed=True)]


def to_markdown(res):
    def fmt(v):
        return "—" if v is None else v

    def ci(v):
        return "—" if not v else f"{v[0]}–{v[1]}"
    head = ("| | Races | Candidate races | Tickets | Hits | Hit % | ROI % "
            + "| ROI 95% CI | Mean exp. return % | Log-loss model / market |")
    sep = "|---|---|---|---|---|---|---|---|---|---|"

    def line(name, v):
        return (f"| {name} | {v['races']} | {v['candidate_races']} "
                + f"| {v['tickets']} | {v['hits']} | {fmt(v['hit_rate'])} "
                + f"| {fmt(v['roi'])} | {ci(v['roi_ci95'])} "
                + f"| {fmt(v['mean_expected_return'])} "
                + f"| {fmt(v['log_loss_model'])} / {fmt(v['log_loss_market'])} |")
    md = [f"# Expected-return rule with closing odds ({res['period']})", "",
          f"Model: {res['model']}.", "",
          f"Generated: {res['generated_at']}. Probabilities: walk-forward "
          + "backtest; calibration fitted only on races "
          + f"{res['calibration_fit'][0]} .. {res['calibration_fit'][1]}. "
          + f"Rule: expected return ≥ {res['ev_min']}, probability ≥ "
          + f"{res['prob_min']}, at most {res['max_candidates']} per race. "
          + "Closing odds are not known before the deadline: this measures "
          + "the rule and the probabilities, not achievable results.", "",
          "## By stadium", "", head, sep]
    for sid, v in res["by_stadium"].items():
        md.append(line("Total" if sid == "all" else STADIUM_NAMES.get(sid, sid), v))
    md += ["", "## By month", "", head, sep]
    for m, v in res["by_month"].items():
        md.append(line(m, v))
    md += ["", "## Expected-return threshold (all stadiums)", "", head, sep]
    for t, v in res["thresholds"].items():
        md.append(line(f"≥ {t}", v))
    md += ["", "## Probability calibration", "",
           "| Probability band | N | Mean predicted | Observed |",
           "|---|---|---|---|"]
    md += [f"| {c['bin']} | {c['n']} | {c['predicted']:.3f} | {c['observed']:.3f} |"
           for c in res["calibration"]]
    md += ["", "Reference: buying at random at market odds returns about "
           + "75% on average (trio takeout ~25%). Lower log-loss is better."]
    return "\n".join(md) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="2026-01-01")
    ap.add_argument("--to", dest="end")
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    pkey = "p1L" if args.live else "p1"
    suffix = "_live" if args.live else ""
    stadiums = target_stadium_ids()
    cfg = load_config()

    bt = pd.read_csv(BACKTEST_CSV).sort_values("race_date")
    bt = bt[bt["stadium_id"].astype(int).astype(str).str.zfill(2).isin(stadiums)]
    if args.live:
        bt = bt[bt["has_exhibition"] == 1]
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end or bt["race_date"].max())

    samples = list(race_samples(bt[bt["race_date"] < start.isoformat()], pkey))
    calibration = fit_map(samples)
    period = bt[(bt["race_date"] >= start.isoformat())
                & (bt["race_date"] <= end.isoformat())]
    closing = load_closing(start, end, stadiums)
    recs = race_records(period, calibration, closing, pkey)
    print(f"{len(recs)} races with closing odds ({start} .. {end}); "
          f"calibration fitted on {len(samples)} earlier races")

    rng = np.random.default_rng(42)
    res = {"generated_at": iso_jst(), "period": f"{start} .. {end}",
           "model": "live (with exhibition / wind / wave)" if args.live
           else "morning (no race-day information)",
           "calibration_fit": [samples[0][0], samples[-1][0]],
           "ev_min": cfg["ev_min"], "prob_min": cfg["prob_min"],
           "max_candidates": cfg["max_candidates_per_race"],
           "by_stadium": {}, "by_month": {}, "thresholds": {}}
    for sid in sorted({r["sid"] for r in recs}) + ["all"]:
        sub = [r for r in recs if sid == "all" or r["sid"] == sid]
        res["by_stadium"][sid] = evaluate(sub, cfg, cfg["ev_min"], rng)
    for m in sorted({r["date"][:7] for r in recs}):
        res["by_month"][m] = evaluate([r for r in recs if r["date"][:7] == m],
                                      cfg, cfg["ev_min"], rng)
    for t in THRESHOLDS:
        res["thresholds"][str(t)] = evaluate(recs, cfg, t, rng)
    res["calibration"] = calibration_table(recs)

    write_json(os.path.join(VERIFY_DIR, f"ev_backtest{suffix}.json"), res)
    with open(os.path.join(VERIFY_DIR, f"ev_backtest{suffix}.md"), "w",
              encoding="utf-8") as f:
        f.write(to_markdown(res))
    a = res["by_stadium"]["all"]
    print(f"Total: {a['tickets']} tickets, ROI {a['roi']}% "
          f"(95% CI {a['roi_ci95']}), mean expected return "
          f"{a['mean_expected_return']}%, log-loss model "
          f"{a['log_loss_model']} vs market {a['log_loss_market']}")


if __name__ == "__main__":
    main()
