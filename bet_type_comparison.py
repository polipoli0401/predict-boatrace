"""Which bet type works best with the model? And does any stadium stand out?

Part 1 — bet types, 2026 (day files with payouts and closing odds of all
bet types, CLOSING_ODDS_BASE_URL; cached in cache/). For every race the
model's single most likely ticket of each type is bought (1 ticket, 100
JPY), using the walk-forward morning P(win) in backtest_result.csv and
the Harville ordering model:
  win (単勝), place (複勝, top 2), exacta (2連単), quinella (2連複),
  quinella_place (拡連複, both in top 3), trifecta (3連単), trio (3連複)
Reference: the market favourite of each type (lowest closing odds) and
the payout rate implied by the closing odds (1 / sum(1/odds)) for the
single-winner types.

Part 2 — stadiums, 2024-02 .. latest (results CSV payouts): the model's
top trio and top trifecta, 1 ticket, per stadium and per half-period
(selection 2024-02..2025-12 / test 2026), with bootstrap 95% CIs.

Writes data/verification/bet_type_comparison.{json,md}.
"""
import gzip
import json
import os
from datetime import date, timedelta
from itertools import combinations, permutations

import numpy as np
import pandas as pd

from boatrace_sources import STADIUM_NAMES, http_get, iso_jst, target_stadium_ids
from closing_odds import _base
from race_store import VERIFY_DIR, write_json

CACHE = os.path.join("cache", "bettypes_2026.json.gz")
TYPES = ["win", "place", "exacta", "quinella", "quinella_place", "trifecta", "trio"]
LABELS = {"win": "Win (単勝)", "place": "Place (複勝)", "exacta": "Exacta (2連単)",
          "quinella": "Quinella (2連複)", "quinella_place": "Wide (拡連複)",
          "trifecta": "Trifecta (3連単)", "trio": "Trio (3連複)"}
rng = np.random.default_rng(3)


# ------------------------------------------------------------
# data
# ------------------------------------------------------------
def _flat(node, depth, prefix=()):
    """Flatten nested odds {a: {b: {c: x}}} to {(a, b, c): x}."""
    out = {}
    if depth == 1:
        for k, v in (node or {}).items():
            out[prefix + (k,)] = v
        return out
    for k, v in (node or {}).items():
        out.update(_flat(v, depth - 1, prefix + (k,)))
    return out


def race_entry(race):
    odds = race.get("odds") or {}
    res = race.get("result") or {}
    pays = {}
    for t in TYPES:
        pays[t] = [(p.get("combination"), p.get("amount"))
                   for p in (res.get("payouts") or {}).get(t) or []
                   if p.get("amount")]
    o = {}
    for t, depth, sep in [("win", 1, ""), ("exacta", 2, "-"), ("quinella", 2, "="),
                          ("trifecta", 3, "-"), ("trio", 3, "=")]:
        flat = _flat(odds.get(t), depth)
        o[t] = {sep.join(k): v for k, v in flat.items()
                if isinstance(v, (int, float)) and v > 0}
    return {"pays": pays, "odds": o}


def load_2026(start, end, stadiums):
    data = {}
    if os.path.exists(CACHE):
        with gzip.open(CACHE, "rt", encoding="utf-8") as f:
            data = json.load(f)
    base, d, changed = _base(), start, False
    while d <= end:
        ds = d.isoformat()
        if ds not in data and base:
            resp, _ = http_get(f"{base}/{d.year}/{d.strftime('%Y%m%d')}.json")
            if resp is not None and resp.status_code == 200:
                day = {}
                st = (resp.json().get("programs") or {}).get("stadiums") or {}
                for sk, sv in st.items():
                    sid = str(sk).zfill(2)
                    if sid not in stadiums:
                        continue
                    for rk, race in ((sv or {}).get("races") or {}).items():
                        day[f"{sid}-{int(rk):02d}"] = race_entry(race or {})
                data[ds] = day
                changed = True
        d += timedelta(days=1)
    if changed:
        os.makedirs("cache", exist_ok=True)
        with gzip.open(CACHE, "wt", encoding="utf-8") as f:
            json.dump(data, f)
    return data


# ------------------------------------------------------------
# model picks (Harville on P(win))
# ------------------------------------------------------------
def picks(boats, p):
    p = np.asarray(p, float)
    p = p / p.sum()
    idx = range(len(boats))
    win = boats[int(np.argmax(p))]
    top2 = {boats[i]: p[i] + sum(p[j] * p[i] / (1 - p[j]) for j in idx if j != i)
            for i in idx}
    exacta = {(boats[i], boats[j]): p[i] * p[j] / (1 - p[i])
              for i, j in permutations(idx, 2)}
    tri = {(boats[i], boats[j], boats[k]):
           p[i] * p[j] / (1 - p[i]) * p[k] / (1 - p[i] - p[j])
           for i, j, k in permutations(idx, 3)}
    quin = {}
    for (a, b), v in exacta.items():
        quin[tuple(sorted((a, b)))] = quin.get(tuple(sorted((a, b))), 0) + v
    trio = {}
    for k, v in tri.items():
        trio[tuple(sorted(k))] = trio.get(tuple(sorted(k)), 0) + v
    wide = {pair: sum(v for t, v in trio.items() if set(pair) <= set(t))
            for pair in combinations(sorted(boats), 2)}
    best = lambda d: max(d, key=d.get)  # noqa: E731
    e, q, w, tf, tr = best(exacta), best(quin), best(wide), best(tri), best(trio)
    return {"win": str(win), "place": str(best(top2)),
            "exacta": f"{e[0]}-{e[1]}", "quinella": f"{q[0]}={q[1]}",
            "quinella_place": f"{w[0]}={w[1]}",
            "trifecta": f"{tf[0]}-{tf[1]}-{tf[2]}",
            "trio": "=".join(map(str, tr))}


def _same(a, b, ordered):
    if ordered:
        return a == b
    return sorted(a.replace("=", "-").split("-")) == sorted(b.replace("=", "-").split("-"))


def ret_of(ticket, pays, ordered):
    return sum(amt for comb, amt in pays if comb and _same(ticket, comb, ordered))


def stats(per_race):
    if not per_race:
        return {"races": 0, "hit_rate": None, "roi": None, "roi_ci95": None}
    arr = np.array(per_race, float)
    out = {"races": len(arr), "hit_rate": round(100 * float((arr[:, 1] > 0).mean()), 1),
           "roi": round(100 * arr[:, 1].sum() / arr[:, 0].sum(), 1), "roi_ci95": None}
    if len(arr) >= 30:
        ix = rng.integers(0, len(arr), size=(2000, len(arr)))
        r = arr[ix, 1].sum(1) / arr[ix, 0].sum(1) * 100
        out["roi_ci95"] = [round(float(np.percentile(r, 2.5)), 1),
                           round(float(np.percentile(r, 97.5)), 1)]
    return out


ORDERED = {"win": True, "place": True, "exacta": True, "quinella": False,
           "quinella_place": False, "trifecta": True, "trio": False}


# ------------------------------------------------------------
def main():
    stadiums = target_stadium_ids()
    bt = pd.read_csv("backtest_result.csv").sort_values("race_date")
    bt["sid"] = bt["stadium_id"].astype(int).astype(str).str.zfill(2)
    bt = bt[bt["sid"].isin(stadiums)]
    bt["key"] = bt["sid"] + "-" + bt["race_number"].astype(int).map("{:02d}".format)

    # Part 1
    b26 = bt[bt["race_date"] >= "2026-01-01"]
    data = load_2026(date(2026, 1, 1), date.fromisoformat(b26["race_date"].max()),
                     stadiums)
    model = {t: [] for t in TYPES}
    model_sid = {s: {t: [] for t in TYPES} for s in stadiums}
    fav = {t: [] for t in ["win", "exacta", "quinella", "trifecta", "trio"]}
    rate = {t: [] for t in fav}
    for r in b26.itertuples():
        e = (data.get(r.race_date) or {}).get(r.key)
        if not e or not e["pays"].get("trio"):
            continue
        d = json.loads(r.boats_json)
        pk = picks(d["bn"], d["p1"])
        for t in TYPES:
            rt = ret_of(pk[t], e["pays"][t], ORDERED[t])
            model[t].append((100, rt))
            model_sid[r.sid][t].append((100, rt))
        for t in fav:
            o = e["odds"].get(t) or {}
            if not o:
                continue
            rate[t].append(1 / sum(1 / v for v in o.values()))
            f = min(o, key=o.get)
            fav[t].append((100, ret_of(f, e["pays"][t], ORDERED[t])))
    part1 = {"period": f"2026-01-01 .. {b26['race_date'].max()}",
             "model_top1": {t: stats(v) for t, v in model.items()},
             "market_favourite": {t: stats(v) for t, v in fav.items()},
             "implied_payout_rate": {t: round(100 * float(np.median(v)), 1)
                                     for t, v in rate.items() if v},
             "model_top1_by_stadium": {s: {t: stats(v) for t, v in m.items()}
                                       for s, m in model_sid.items()}}

    # Part 2 (trio / trifecta payouts from the results CSV, back to 2024)
    res = pd.read_csv("boatrace_results.csv",
                      usecols=["race_date", "stadium_id", "race_number",
                               "boat_number", "place", "payout_trifecta"])
    res["sid"] = res["stadium_id"].astype(int).astype(str).str.zfill(2)
    order = {}
    for (dd, s, rn), g in res.groupby(["race_date", "sid", "race_number"]):
        g = g[pd.to_numeric(g["place"], errors="coerce").between(1, 3)]
        if len(g) == 3:
            g = g.sort_values("place")
            order[(dd, s, int(rn))] = ("-".join(str(int(b)) for b in g["boat_number"]),
                                       g["payout_trifecta"].iloc[0])
    part2 = {}
    for s in stadiums + ["all"]:
        sub = bt if s == "all" else bt[bt["sid"] == s]
        out = {}
        for period, lo, hi in [("selection", "0000", "2025-12-31"),
                               ("test", "2026-01-01", "9999")]:
            ps = sub[(sub["race_date"] >= lo) & (sub["race_date"] <= hi)]
            trio_r, tf_r = [], []
            for r in ps.itertuples():
                d = json.loads(r.boats_json)
                pk = picks(d["bn"], d["p1"])
                act = sorted(json.loads(r.actual_trio))
                pay = 0.0 if pd.isna(r.payout_trio) else r.payout_trio
                trio_r.append((100, pay if sorted(int(x) for x in pk["trio"].split("="))
                               == act else 0.0))
                o = order.get((r.race_date, r.sid, int(r.race_number)))
                if o and not pd.isna(o[1]):
                    tf_r.append((100, o[1] if pk["trifecta"] == o[0] else 0.0))
            out[period] = {"trio": stats(trio_r), "trifecta": stats(tf_r)}
        part2[s] = out
    res_doc = {"generated_at": iso_jst(), "part1": part1, "part2": part2}
    write_json(os.path.join(VERIFY_DIR, "bet_type_comparison.json"), res_doc)
    md = to_markdown(res_doc)
    with open(os.path.join(VERIFY_DIR, "bet_type_comparison.md"), "w",
              encoding="utf-8") as f:
        f.write(md)
    print(md)


def fs(s):
    if not s or not s["races"]:
        return "—"
    ci = f" [{s['roi_ci95'][0]}–{s['roi_ci95'][1]}]" if s["roi_ci95"] else ""
    return f"{s['roi']}%{ci}, hit {s['hit_rate']}%"


def to_markdown(r):
    p1, p2 = r["part1"], r["part2"]
    md = ["# Bet types and stadiums", "", f"Generated: {r['generated_at']}. "
          + "1 ticket (100 JPY) per race: the model's single most likely ticket "
          + "of each type (walk-forward P(win), Harville). ROI with bootstrap "
          + "95% CI.", "", f"## Bet types ({p1['period']})", "",
          "| Bet type | Model top ticket | Market favourite | Implied payout rate |",
          "|---|---|---|---|"]
    for t in TYPES:
        md.append(f"| {LABELS[t]} | {fs(p1['model_top1'][t])} "
                  + f"| {fs(p1['market_favourite'].get(t))} "
                  + f"| {p1['implied_payout_rate'].get(t, '—')}"
                  + ("%" if t in p1["implied_payout_rate"] else "") + " |")
    md += ["", "## Bet types by stadium (model top ticket, 2026)", "",
           "| Bet type | " + " | ".join(STADIUM_NAMES.get(s, s)
                                        for s in p1["model_top1_by_stadium"]) + " |",
           "|---" * (len(p1["model_top1_by_stadium"]) + 1) + "|"]
    for t in TYPES:
        md.append(f"| {LABELS[t]} | " + " | ".join(
            fs(m[t]) for m in p1["model_top1_by_stadium"].values()) + " |")
    md += ["", "## Stadiums over the full period (model top ticket)", "",
           "| Stadium | Trio 2024-25 | Trio 2026 | Trifecta 2024-25 | Trifecta 2026 |",
           "|---|---|---|---|---|"]
    for s, v in p2.items():
        name = "Total" if s == "all" else STADIUM_NAMES.get(s, s)
        md.append(f"| {name} | {fs(v['selection']['trio'])} | {fs(v['test']['trio'])} "
                  + f"| {fs(v['selection']['trifecta'])} | {fs(v['test']['trifecta'])} |")
    md += ["", "Implied payout rate = median over races of 1 / sum(1/odds) for "
           + "single-winner bet types (closing odds). Place and wide have "
           + "several winning tickets, so no simple implied rate is shown."]
    return "\n".join(md) + "\n"


if __name__ == "__main__":
    main()
