"""Verification of the race-day pipeline against confirmed results.

For every date that has data/predictions/<date>.json and results in
boatrace_results.csv:
  - calibration: predicted trio probability vs observed hit frequency
  - candidates: the last pre-close decision stored in data/odds/<date>.json
    (100 JPY per candidate combination) -> hit rate, ROI, and the mean
    expected return at decision time (expected vs realised)
  - market comparison: log-loss of the model vs the closing-odds implied
    probabilities (when closing odds were captured)
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
            "ll_model": 0.0, "ll_market": 0.0, "n_market": 0}


def verify(pred_files, results):
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
            final = entry.get("odds") if entry.get("is_final") else None
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
                if final:
                    inv = {o["combination"]: 1 / o["value"] for o in final
                           if o["value"]}
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
    lines = [f"# 検証結果（{s['period'] or 'データなし'}）", "",
             f"生成: {s['generated_at']}", "",
             "## 場別（購入候補 = 締切前の最後の判定、1点100円換算）", "",
             "| 場 | 予測レース | 候補レース | 点数 | 的中 | 的中率% | 投資 | 払戻 "
             "| 回収率% | 平均期待回収率% | 対数損失(モデル/市場) |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for sid, v in s["by_stadium"].items():
        name = "合計" if sid == "all" else STADIUM_NAMES.get(sid, sid)
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
    lines += ["", "## 予測確率の校正（全組合せ）", "",
              "| 予測確率帯 | 件数 | 予測平均 | 実際の的中率 |", "|---|---|---|---|"]
    for c in s["calibration"]:
        lines.append(f"| {c['bin']} | {c['n']} | {c['predicted']:.3f} "
                     f"| {c['observed']:.3f} |")
    lines += ["", "対数損失は小さいほど良い。市場は締切時オッズの逆数を正規化した確率。"
              "件数が少ない間は数値が大きくぶれるため、判断材料にしないこと。"]
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
