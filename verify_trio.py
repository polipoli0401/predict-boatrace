"""Verification of the race-day pipeline against confirmed results.

For every date that has data/predictions/<date>.json and results in
boatrace_results.csv:
  - calibration: predicted trio probability vs observed hit frequency
  - candidates: the last pre-close decision stored in data/odds/<date>.json
    (100 JPY per candidate combination) -> hit rate, ROI, and the mean
    expected return at decision time (expected vs realised)
  - market comparison: log-loss of the model vs the closing-odds implied
    probabilities (closing odds from closing_odds.py, or closing odds
    captured by race_day.py after the deadline)
  - closing-odds rule check: the same decision rule (ev_config.json)
    applied after the fact with CLOSING odds. Closing odds are not known
    at decision time, so this is a reference for the rule and the
    probabilities, not the result of actual decisions.
Everything is reported per stadium and in total.

Writes data/verification/summary.json and summary.md.
"""
import glob
import math
import os
from collections import defaultdict
from datetime import date

import pandas as pd

from boatrace_sources import STADIUM_NAMES, iso_jst
from ev_judge import load_config
from race_store import VERIFY_DIR, odds_path, read_json, write_json

RESULTS_CSV = "boatrace_results.csv"
BINS = [0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 1.0]
FLOOR = 1e-4


def actual_results(results_csv=RESULTS_CSV):
    """{(date, sid, rno): (combo, payout_trio)} for races with three
    finishers in places 1-3."""
    df = pd.read_csv(results_csv, usecols=["race_date", "stadium_id",
                                           "race_number", "boat_number",
                                           "place", "payout_trio"])
    df["stadium_id"] = df["stadium_id"].astype(int).astype(str).str.zfill(2)
    out = {}
    for (d, s, r), g in df.groupby(["race_date", "stadium_id", "race_number"]):
        top = g[pd.to_numeric(g["place"], errors="coerce") <= 3]
        if len(top) != 3:
            continue
        combo = "-".join(str(int(b)) for b in sorted(top["boat_number"]))
        pay = top["payout_trio"].iloc[0]
        out[(d, s, int(r))] = (combo, None if pd.isna(pay) else float(pay))
    return out


def _blank():
    return {"races": 0, "candidate_races": 0, "tickets": 0, "hits": 0,
            "invest": 0, "return": 0.0, "er_sum": 0.0,
            "ll_model": 0.0, "ll_market": 0.0, "n_market": 0,
            "c_races": 0, "c_tickets": 0, "c_hits": 0, "c_return": 0.0,
            "c_er_sum": 0.0}


def closing_odds_of(entry):
    """{combo: odds} at the deadline, or None."""
    src = (entry.get("closing") or {}).get("odds")
    if not src and entry.get("is_final"):
        src = entry.get("odds")
    if not src:
        return None
    return {o["combination"]: o["value"] for o in src}


def rule_candidates(probs, odds, cfg):
    """Combinations the decision rule would pick with these odds."""
    rows = [(k, p, odds.get(k)) for k, p in probs.items()]
    rows = [(k, p, o, p * o) for k, p, o in rows
            if o and p >= cfg["prob_min"] and p * o >= cfg["ev_min"]]
    rows.sort(key=lambda r: -r[3])
    return rows[:cfg["max_candidates_per_race"]]


def verify(pred_files, results, cfg=None):
    cfg = cfg or load_config()
    by = defaultdict(_blank)
    calib = []
    dates = []
    for path in sorted(pred_files):
        doc = read_json(path) or {}
        d = doc.get("date")
        if not d:
            continue
        odds_doc = read_json(odds_path(date.fromisoformat(d))) or {}
        any_result = False
        for key, race in (doc.get("races") or {}).items():
            res = results.get((d, race["stadium_id"], int(race["race_number"])))
            if not res:
                continue
            any_result = True
            actual, payout = res
            probs = {p["combination"]: p["probability"]
                     for p in race.get("predictions", [])}
            for k, v in probs.items():
                calib.append((v, 1.0 if k == actual else 0.0))
            for s in (race["stadium_id"], "all"):
                b = by[s]
                b["races"] += 1
                b["ll_model_all"] = b.get("ll_model_all", 0.0) - \
                    math.log(max(probs.get(actual, FLOOR), FLOOR))

            entry = (odds_doc.get("races") or {}).get(key) or {}
            pre = entry.get("pre_close") or {}
            cands = pre.get("candidates") or []
            final = closing_odds_of(entry)
            rule = rule_candidates(probs, final, cfg) if final else []
            for s in (race["stadium_id"], "all"):
                b = by[s]
                if cands:
                    b["candidate_races"] += 1
                    b["tickets"] += len(cands)
                    b["invest"] += 100 * len(cands)
                    b["er_sum"] += sum(c["expected_return"] for c in cands)
                    hit = [c for c in cands if c["combination"] == actual]
                    if hit:
                        b["hits"] += 1
                        b["return"] += payout or 0.0
                if rule:
                    b["c_races"] += 1
                    b["c_tickets"] += len(rule)
                    b["c_er_sum"] += sum(r[3] for r in rule)
                    if any(r[0] == actual for r in rule):
                        b["c_hits"] += 1
                        b["c_return"] += payout or 0.0
                if final:
                    inv = {k: 1 / v for k, v in final.items() if v}
                    tot = sum(inv.values())
                    if tot > 0 and actual in inv:
                        b["n_market"] += 1
                        b["ll_market"] -= math.log(max(inv[actual] / tot, FLOOR))
                        b["ll_model"] -= math.log(max(probs.get(actual, FLOOR),
                                                      FLOOR))
        if any_result:
            dates.append(d)
    return by, calib, dates


def summarise(by, calib, dates):
    out = {"generated_at": iso_jst(),
           "period": f"{dates[0]} .. {dates[-1]}" if dates else None,
           "by_stadium": {}, "calibration": []}
    order = sorted(k for k in by if k != "all") + (["all"] if "all" in by else [])
    for s in order:
        b = by[s]
        out["by_stadium"][s] = {
            "races": b["races"],
            "model_log_loss": round(b.get("ll_model_all", 0.0) / b["races"], 4)
            if b["races"] else None,
            "candidate_races": b["candidate_races"],
            "tickets": b["tickets"],
            "hits": b["hits"],
            "hit_rate": round(100 * b["hits"] / b["candidate_races"], 1)
            if b["candidate_races"] else None,
            "invest": b["invest"],
            "return": round(b["return"]),
            "roi": round(100 * b["return"] / b["invest"], 1)
            if b["invest"] else None,
            "mean_expected_return": round(100 * b["er_sum"] / b["tickets"], 1)
            if b["tickets"] else None,
            "closing_rule": {
                "candidate_races": b["c_races"],
                "tickets": b["c_tickets"],
                "hits": b["c_hits"],
                "hit_rate": round(100 * b["c_hits"] / b["c_races"], 1)
                if b["c_races"] else None,
                "roi": round(100 * b["c_return"] / (100 * b["c_tickets"]), 1)
                if b["c_tickets"] else None,
                "mean_expected_return": round(
                    100 * b["c_er_sum"] / b["c_tickets"], 1)
                if b["c_tickets"] else None,
            },
            "market_compared_races": b["n_market"],
            "log_loss_model_vs_market": [
                round(b["ll_model"] / b["n_market"], 4),
                round(b["ll_market"] / b["n_market"], 4)]
            if b["n_market"] else None,
        }
    if calib:
        df = pd.DataFrame(calib, columns=["p", "hit"])
        df["bin"] = pd.cut(df["p"], BINS)
        for b, g in df.groupby("bin", observed=True):
            out["calibration"].append({
                "bin": str(b), "n": int(len(g)),
                "predicted": round(float(g["p"].mean()), 4),
                "observed": round(float(g["hit"].mean()), 4)})
    return out


def to_markdown(s):
    lines = [f"# Verification ({s['period'] or 'no data'})", "",
             f"Generated: {s['generated_at']}", "",
             "## By stadium (candidates = last pre-deadline decision, "
             + "100 JPY per ticket)", "",
             "| Stadium | Predicted races | Candidate races | Tickets | Hits "
             + "| Hit % | Invested | Returned | ROI % | Mean exp. return % "
             + "| Log-loss (model / market) |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for sid, v in s["by_stadium"].items():
        name = "Total" if sid == "all" else STADIUM_NAMES.get(sid, sid)
        ll = (f"{v['log_loss_model_vs_market'][0]} / "
              f"{v['log_loss_model_vs_market'][1]} "
              f"(n={v['market_compared_races']})"
              if v["log_loss_model_vs_market"] else "—")
        lines.append(
            f"| {name} | {v['races']} | {v['candidate_races']} | {v['tickets']} "
            f"| {v['hits']} | {v['hit_rate'] if v['hit_rate'] is not None else '—'} "
            f"| {v['invest']} | {v['return']} "
            f"| {v['roi'] if v['roi'] is not None else '—'} "
            f"| {v['mean_expected_return'] if v['mean_expected_return'] is not None else '—'} "
            f"| {ll} |")
    lines += ["", "## Rule applied with closing odds (reference)", "",
              "The decision rule applied after the fact with closing odds. "
              + "Closing odds are not known at decision time, so this is not "
              + "the result of actual candidates.", "",
              "| Stadium | Races | Tickets | Hits | Hit % | ROI % "
              + "| Mean exp. return % |",
              "|---|---|---|---|---|---|---|"]
    for sid, v in s["by_stadium"].items():
        name = "Total" if sid == "all" else STADIUM_NAMES.get(sid, sid)
        c = v["closing_rule"]
        dash = lambda x: "—" if x is None else x  # noqa: E731
        lines.append(f"| {name} | {c['candidate_races']} | {c['tickets']} "
                     f"| {c['hits']} | {dash(c['hit_rate'])} | {dash(c['roi'])} "
                     f"| {dash(c['mean_expected_return'])} |")
    lines += ["", "## Probability calibration (all combinations)", "",
              "| Probability band | N | Mean predicted | Observed |",
              "|---|---|---|---|"]
    for c in s["calibration"]:
        lines.append(f"| {c['bin']} | {c['n']} | {c['predicted']:.3f} "
                     f"| {c['observed']:.3f} |")
    lines += ["", "Lower log-loss is better. Market = closing odds inverted and "
              + "normalised. Small samples fluctuate strongly; do not act on "
              + "them."]
    return "\n".join(lines) + "\n"


def main():
    files = glob.glob(os.path.join("data", "predictions", "*.json"))
    if not files:
        print("Verification: no prediction files yet")
        return
    by, calib, dates = verify(files, actual_results())
    s = summarise(by, calib, dates)
    write_json(os.path.join(VERIFY_DIR, "summary.json"), s)
    with open(os.path.join(VERIFY_DIR, "summary.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(s))
    a = s["by_stadium"].get("all")
    if a:
        print(f"Verification {s['period']}: {a['races']} races, "
              f"{a['candidate_races']} candidate races, ROI {a['roi']}%")


if __name__ == "__main__":
    main()
