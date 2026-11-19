"""Out-of-sample comparison of ticket strategies (how to buy).

Avoids the main weakness of the original grid search (choosing the best
filter on the same data it is reported on): every strategy's parameters
are chosen on a SELECTION period and reported on a later TEST period,
with bootstrap 95% CIs (resampling races).

Part 1 — payout-only strategies, walk-forward morning probabilities from
backtest_result.csv (2024-02 .. latest). Selection 2024-02..2025-12,
test 2026-01..:
  - the 6 existing ticket strategies (predict_boatrace_lib.build_ticket)
    with the original probability-band / gap filter grid
  - model top-1 trio (Harville on P(win)), 1 ticket, with a minimum
    top-1 trio probability chosen on the selection period
Part 2 — odds-dependent, 2026 with closing odds (CLOSING_ODDS_BASE_URL,
cached). Selection 2026-01..06, test 2026-07..:
  - buy every combination in a closing-odds band (market structure:
    favourite-longshot bias)
  - market favourite (lowest-odds trio), 1 ticket
  - model top-1 trio restricted to a closing-odds band
Closing odds are not known before the deadline; Part 2 measures the
market and the model, not achievable betting results.

Writes data/verification/strategy_comparison.{json,md}.
"""
import json
import os
from datetime import date

import numpy as np
import pandas as pd

import ev_backtest as eb
from boatrace_sources import iso_jst, target_stadium_ids
from predict_boatrace_lib import STRATEGY_NAMES, build_ticket
from race_store import VERIFY_DIR, write_json
from trio_prob import harville_trio

SEL_END = "2025-12-31"          # Part 1 selection period ends
P2_SEL_END = "2026-06-30"       # Part 2 selection period ends
MIN_RACES = 100
BANDS = [(1, 3), (3, 5), (5, 10), (10, 20), (20, 50), (50, 100), (100, 1e9)]
TOP1_MIN = [0.0, 0.10, 0.15, 0.20, 0.25, 0.30]
rng = np.random.default_rng(11)


def stats(per_race):
    """per_race: list of (invest, return) for races with a bet."""
    if not per_race:
        return {"races": 0, "tickets": 0, "hit_rate": None, "roi": None,
                "roi_ci95": None}
    arr = np.array(per_race, dtype=float)
    inv, ret = arr[:, 0].sum(), arr[:, 1].sum()
    out = {"races": len(arr), "tickets": int(inv // 100),
           "hit_rate": round(100 * float((arr[:, 1] > 0).mean()), 1),
           "roi": round(100 * ret / inv, 1), "roi_ci95": None}
    if len(arr) >= 30:
        idx = rng.integers(0, len(arr), size=(2000, len(arr)))
        rois = arr[idx, 1].sum(1) / arr[idx, 0].sum(1) * 100
        out["roi_ci95"] = [round(float(np.percentile(rois, 2.5)), 1),
                           round(float(np.percentile(rois, 97.5)), 1)]
    return out


def play(races, pick):
    """pick(race) -> list of combo strings (100 JPY each)."""
    out = []
    for r in races:
        t = pick(r)
        if t:
            hit = r["actual"] in t
            out.append((100 * len(t), (r["payout"] or 0.0) if hit else 0.0))
    return out


# ------------------------------------------------------------
# Part 1
# ------------------------------------------------------------
def load_backtest(stadiums):
    bt = pd.read_csv("backtest_result.csv").sort_values("race_date")
    bt = bt[bt["stadium_id"].astype(int).astype(str).str.zfill(2).isin(stadiums)]
    races = []
    for r in bt.itertuples():
        d = json.loads(r.boats_json)
        raw = harville_trio(d["bn"], d["p1"])
        top = max(raw, key=raw.get)
        races.append({
            "date": r.race_date, "sid": str(r.stadium_id).zfill(2),
            "actual": "-".join(str(b) for b in sorted(json.loads(r.actual_trio))),
            "payout": None if pd.isna(r.payout_trio) else float(r.payout_trio),
            "top_prob": r.top_prob, "gap": r.prob_gap,
            "df": pd.DataFrame({"boat_number": d["bn"], "p1": d["p1"],
                                "p3": d["p3"]}),
            "top1": top, "top1_p": raw[top]})
    return races


def ticket_pick(strategy, lo, hi, gap):
    def pick(r):
        if not (lo <= r["top_prob"] < hi) or r["gap"] < gap:
            return []
        return ["-".join(map(str, sorted(t)))
                for t in build_ticket(strategy, r["df"])]
    return pick


def part1(races):
    sel = [r for r in races if r["date"] <= SEL_END]
    test = [r for r in races if r["date"] > SEL_END]
    edges = np.arange(0.30, 0.80, 0.10)
    rows = []
    for st in STRATEGY_NAMES:
        unf = ticket_pick(st, 0, 1.01, 0)
        best = None
        for i in range(len(edges) - 1):
            for j in range(i + 1, len(edges)):
                for g in [0.0, 0.10, 0.20, 0.30]:
                    s = stats(play(sel, ticket_pick(st, edges[i], edges[j], g)))
                    if s["races"] >= MIN_RACES and (best is None
                                                    or s["roi"] > best[0]["roi"]):
                        best = (s, (round(float(edges[i]), 2),
                                    round(float(edges[j]), 2), g))
        row = {"strategy": STRATEGY_NAMES[st],
               "unfiltered_selection": stats(play(sel, unf)),
               "unfiltered_test": stats(play(test, unf))}
        if best:
            lo, hi, g = best[1]
            row["chosen_filter"] = {"prob_min": lo, "prob_max": hi, "gap_min": g}
            row["filtered_selection"] = best[0]
            row["filtered_test"] = stats(play(test, ticket_pick(st, lo, hi, g)))
        rows.append(row)

    best_t, best_s = None, None
    for t in TOP1_MIN:
        s = stats(play(sel, lambda r, t=t: [r["top1"]] if r["top1_p"] >= t else []))
        if s["races"] >= MIN_RACES and (best_s is None or s["roi"] > best_s["roi"]):
            best_t, best_s = t, s
    rows.append({"strategy": "Model top-1 trio (1 ticket)",
                 "unfiltered_selection": stats(play(sel, lambda r: [r["top1"]])),
                 "unfiltered_test": stats(play(test, lambda r: [r["top1"]])),
                 "chosen_filter": {"top1_prob_min": best_t},
                 "filtered_selection": best_s,
                 "filtered_test": stats(play(test, lambda r: [r["top1"]]
                                             if r["top1_p"] >= best_t else []))})
    return {"selection": f"{sel[0]['date']} .. {sel[-1]['date']}",
            "test": f"{test[0]['date']} .. {test[-1]['date']}", "rows": rows}


# ------------------------------------------------------------
# Part 2
# ------------------------------------------------------------
def part2(races, stadiums):
    p2 = [r for r in races if r["date"] >= "2026-01-01"]
    closing = eb.load_closing(date.fromisoformat(p2[0]["date"]),
                              date.fromisoformat(p2[-1]["date"]), stadiums)
    for r in p2:
        r["odds"] = closing.get((r["date"], f"{r['sid']}-{int(r.get('rno', 0)):02d}"))
    return p2


def part2_eval(p2):
    p2 = [r for r in p2 if r.get("odds")]
    sel = [r for r in p2 if r["date"] <= P2_SEL_END]
    test = [r for r in p2 if r["date"] > P2_SEL_END]

    def band_pick(lo, hi):
        return lambda r: [k for k, v in r["odds"].items() if v and lo <= v < hi]

    def fav(r):
        ok = {k: v for k, v in r["odds"].items() if v}
        return [min(ok, key=ok.get)] if ok else []

    def top1_band(lo, hi):
        return lambda r: ([r["top1"]] if r["odds"].get(r["top1"])
                          and lo <= r["odds"][r["top1"]] < hi else [])
    bands = []
    for lo, hi in BANDS:
        name = f"{lo}-{'' if hi > 1e8 else hi}"
        bands.append({"band": name,
                      "all_in_band_selection": stats(play(sel, band_pick(lo, hi))),
                      "all_in_band_test": stats(play(test, band_pick(lo, hi))),
                      "model_top1_selection": stats(play(sel, top1_band(lo, hi))),
                      "model_top1_test": stats(play(test, top1_band(lo, hi)))})
    return {"selection": f"{sel[0]['date']} .. {sel[-1]['date']}",
            "test": f"{test[0]['date']} .. {test[-1]['date']}",
            "market_favourite_selection": stats(play(sel, fav)),
            "market_favourite_test": stats(play(test, fav)),
            "model_top1_selection": stats(play(sel, lambda r: [r["top1"]])),
            "model_top1_test": stats(play(test, lambda r: [r["top1"]])),
            "bands": bands}


def fmt(s):
    if not s or not s.get("races"):
        return "—"
    ci = f" [{s['roi_ci95'][0]}–{s['roi_ci95'][1]}]" if s["roi_ci95"] else ""
    return f"{s['roi']}%{ci} (n={s['races']}, hit {s['hit_rate']}%)"


def to_markdown(res):
    p1, p2 = res["part1"], res["part2"]
    md = ["# Strategy comparison (out of sample)", "",
          f"Generated: {res['generated_at']}. Parameters are chosen on the "
          + "selection period and reported on the later test period. "
          + "ROI = return / stake; 95% CI by bootstrap over races. "
          + "Random buying returns about 75% (trio takeout ~25%).", "",
          f"## Part 1 — ticket strategies (selection {p1['selection']}, "
          + f"test {p1['test']})", "",
          "| Strategy | Unfiltered: selection | Unfiltered: test "
          + "| Chosen filter | Filtered: selection | Filtered: test |",
          "|---|---|---|---|---|---|"]
    for r in p1["rows"]:
        md.append(f"| {r['strategy']} | {fmt(r['unfiltered_selection'])} "
                  + f"| {fmt(r['unfiltered_test'])} | {r.get('chosen_filter', '—')} "
                  + f"| {fmt(r.get('filtered_selection'))} "
                  + f"| {fmt(r.get('filtered_test'))} |")
    md += ["", f"## Part 2 — with closing odds (selection {p2['selection']}, "
           + f"test {p2['test']})", "",
           "- Market favourite, 1 ticket: selection "
           + f"{fmt(p2['market_favourite_selection'])}; test "
           + f"{fmt(p2['market_favourite_test'])}",
           "- Model top-1 trio, 1 ticket: selection "
           + f"{fmt(p2['model_top1_selection'])}; test "
           + f"{fmt(p2['model_top1_test'])}", "",
           "| Closing-odds band | All combos in band: selection | test "
           + "| Model top-1 in band: selection | test |",
           "|---|---|---|---|---|"]
    for b in p2["bands"]:
        md.append(f"| {b['band']} | {fmt(b['all_in_band_selection'])} "
                  + f"| {fmt(b['all_in_band_test'])} "
                  + f"| {fmt(b['model_top1_selection'])} "
                  + f"| {fmt(b['model_top1_test'])} |")
    md += ["", "Many strategies are tested; with this many comparisons a few "
           + "will exceed 100% on one period by chance. Only results that "
           + "stay above 100% on the test period with a CI above 100% would "
           + "be evidence of an edge."]
    return "\n".join(md) + "\n"


def main():
    stadiums = target_stadium_ids()
    bt = pd.read_csv("backtest_result.csv").sort_values("race_date")
    bt = bt[bt["stadium_id"].astype(int).astype(str).str.zfill(2).isin(stadiums)]
    races = load_backtest(stadiums)
    for r, rno in zip(races, bt["race_number"].tolist()):
        r["rno"] = rno
    res = {"generated_at": iso_jst(), "part1": part1(races)}
    res["part2"] = part2_eval(part2(races, stadiums))
    for r in races:
        r.pop("df", None)
    write_json(os.path.join(VERIFY_DIR, "strategy_comparison.json"), res)
    with open(os.path.join(VERIFY_DIR, "strategy_comparison.md"), "w",
              encoding="utf-8") as f:
        f.write(to_markdown(res))
    print(to_markdown(res))


if __name__ == "__main__":
    main()
