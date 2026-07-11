"""Walk-forward backtest with morning vs live model comparison.

Trains two model sets daily:
  - morning: features available at 3 AM (no exhibition data)
  - live:    morning features + exhibition-run data (~15 min before race)
Compares every ticket strategy under both models against an
always-[1,2,3] baseline, then stores the best morning configuration.
"""
import pandas as pd
import numpy as np
import lightgbm as lgb
import json

from predict_boatrace_lib import (
    TARGET_STADIUM_IDS, FEATURE_COLS, FEATURE_COLS_LIVE, PARAMS,
    STRATEGY_NAMES, prepare_features, build_ticket
)

RESULTS_CSV = "boatrace_results.csv"
MIN_TRAIN_DAYS = 30

df = pd.read_csv(RESULTS_CSV)
df['stadium_id'] = df['stadium_id'].astype(int).astype(str).str.zfill(2)
df = df[df['stadium_id'].isin(TARGET_STADIUM_IDS)]
df = df.dropna(subset=['place', 'boat_number'])
df['place'] = df['place'].astype(int)

df = prepare_features(df)
df['is_first'] = (df['place'] == 1).astype(int)
df['is_top3']  = (df['place'] <= 3).astype(int)

ex_fill = df['exhibition_time'].notna().mean() * 100 \
    if 'exhibition_time' in df.columns else 0.0
print(f"Exhibition data coverage: {ex_fill:.1f}% of rows")

all_dates = sorted(df['race_date'].unique())
print(f"Backtest input: {len(all_dates)} days / {len(df)} rows")

race_rows = []
for i, D in enumerate(all_dates):
    if i < MIN_TRAIN_DAYS:
        continue
    tr = df[df['race_date'] < D]
    te = df[df['race_date'] == D]
    if tr.empty or te.empty or tr['is_first'].sum() == 0:
        continue

    # morning models (no exhibition features)
    m1 = lgb.LGBMClassifier(**PARAMS)
    m1.fit(tr[FEATURE_COLS], tr['is_first'])
    m3 = lgb.LGBMClassifier(**PARAMS)
    m3.fit(tr[FEATURE_COLS], tr['is_top3'])
    # live models (with exhibition features)
    m1L = lgb.LGBMClassifier(**PARAMS)
    m1L.fit(tr[FEATURE_COLS_LIVE], tr['is_first'])
    m3L = lgb.LGBMClassifier(**PARAMS)
    m3L.fit(tr[FEATURE_COLS_LIVE], tr['is_top3'])

    for (sid, rno), race_df in te.groupby(['stadium_id', 'race_number']):
        if len(race_df) < 6:
            continue
        race_df = race_df.copy()

        p1 = m1.predict_proba(race_df[FEATURE_COLS])[:, 1]
        p3 = m3.predict_proba(race_df[FEATURE_COLS])[:, 1]
        race_df['p1'] = p1 / p1.sum() if p1.sum() > 0 else 1/len(race_df)
        race_df['p3'] = p3

        p1L = m1L.predict_proba(race_df[FEATURE_COLS_LIVE])[:, 1]
        p3L = m3L.predict_proba(race_df[FEATURE_COLS_LIVE])[:, 1]
        race_df['p1L'] = p1L / p1L.sum() if p1L.sum() > 0 else 1/len(race_df)
        race_df['p3L'] = p3L

        actual = race_df.sort_values('place')
        t3 = actual[actual['place'] <= 3]
        if len(t3) < 3:
            continue
        a = sorted(int(t3.iloc[k]['boat_number']) for k in range(3))

        by_p1 = race_df.sort_values('p1', ascending=False)
        has_ex = race_df['exhibition_time'].notna().any() \
            if 'exhibition_time' in race_df.columns else False
        race_rows.append({
            'race_date': pd.Timestamp(D).date().isoformat(),
            'stadium_id': sid, 'race_number': rno,
            'top_prob': by_p1.iloc[0]['p1'],
            'prob_gap': by_p1.iloc[0]['p1'] - by_p1.iloc[1]['p1'],
            'has_exhibition': int(has_ex),
            'boats_json': json.dumps({
                'bn': race_df['boat_number'].astype(int).tolist(),
                'p1': [round(v, 4) for v in race_df['p1'].tolist()],
                'p3': [round(v, 4) for v in race_df['p3'].tolist()],
                'p1L': [round(v, 4) for v in race_df['p1L'].tolist()],
                'p3L': [round(v, 4) for v in race_df['p3L'].tolist()],
            }),
            'actual_trio': json.dumps(a),
            'payout_trio': race_df['payout_trio'].iloc[0],
        })

bt = pd.DataFrame(race_rows)
bt.to_csv("backtest_result.csv", index=False, encoding='utf-8-sig')
n = len(bt)
n_ex = int(bt['has_exhibition'].sum())
print(f"Backtest simulated: {n} races "
      f"({n_ex} with exhibition data)\n")


def eval_strategy(bt, strategy, prob_min=0.0, prob_max=1.0,
                  gap_min=0.0, use_live=False, require_exhibition=False):
    """Simulate a strategy. use_live switches to the live model's
    probabilities. require_exhibition restricts to races where
    exhibition data exists (fair comparison subset)."""
    invest, ret, hit_races, n_races, n_tickets = 0, 0.0, 0, 0, 0
    pk1 = 'p1L' if use_live else 'p1'
    pk3 = 'p3L' if use_live else 'p3'
    for _, row in bt.iterrows():
        if require_exhibition and row['has_exhibition'] == 0:
            continue
        if not (prob_min <= row['top_prob'] < prob_max):
            continue
        if row['prob_gap'] < gap_min:
            continue
        d = json.loads(row['boats_json'])
        rdf = pd.DataFrame({'boat_number': d['bn'],
                            'p1': d[pk1], 'p3': d[pk3]})
        tickets = build_ticket(strategy, rdf)
        if not tickets:
            continue
        n_races += 1
        n_tickets += len(tickets)
        invest += len(tickets) * 100
        actual = sorted(json.loads(row['actual_trio']))
        if any(sorted(t) == actual for t in tickets):
            hit_races += 1
            if pd.notna(row['payout_trio']):
                ret += row['payout_trio']
    roi = ret / invest * 100 if invest > 0 else 0
    hr = hit_races / n_races * 100 if n_races > 0 else 0
    return n_races, n_tickets, hr, roi


# ---- baseline ----
bl_hit = bt['actual_trio'].apply(lambda s: json.loads(s) == [1, 2, 3])
bl_ret = bt.loc[bl_hit & bt['payout_trio'].notna(), 'payout_trio'].sum()
print("Baseline [1,2,3]: "
      f"hit {bl_hit.mean()*100:.1f}%, ROI {bl_ret/(n*100)*100:.1f}%\n")

# ---- diagnostic: near-miss rate ----
def partial_hit_stats(bt):
    n2, n3, n01 = 0, 0, 0
    for _, row in bt.iterrows():
        d = json.loads(row['boats_json'])
        rdf = pd.DataFrame({'boat_number': d['bn'], 'p1': d['p1']})
        pred = set(rdf.sort_values('p1', ascending=False)
                   .head(3)['boat_number'].astype(int))
        actual = set(json.loads(row['actual_trio']))
        k = len(pred & actual)
        if k == 3:
            n3 += 1
        elif k == 2:
            n2 += 1
        else:
            n01 += 1
    total = len(bt)
    print("Partial-hit diagnosis (morning favorite trio):")
    print(f"  3/3 correct: {n3/total*100:5.1f}%")
    print(f"  2/3 correct: {n2/total*100:5.1f}%  <- near-miss zone")
    print(f"  0-1 correct: {n01/total*100:5.1f}%\n")

partial_hit_stats(bt)

# ---- morning vs live, restricted to races that HAVE exhibition data ----
print("Strategy results — morning vs live "
      "(exhibition-covered races only):")
for st in STRATEGY_NAMES:
    nr, nt, hr, roi = eval_strategy(bt, st, use_live=False,
                                    require_exhibition=True)
    nrL, ntL, hrL, roiL = eval_strategy(bt, st, use_live=True,
                                        require_exhibition=True)
    print(f"  {STRATEGY_NAMES[st]:<40}: "
          f"AM {nr}R hit {hr:5.1f}% ROI {roi:6.1f}%  |  "
          f"LIVE {nrL}R hit {hrL:5.1f}% ROI {roiL:6.1f}%")

# ---- full-sample morning results (continuity with previous runs) ----
print("\nStrategy results — morning model, all races:")
for st in STRATEGY_NAMES:
    nr, nt, hr, roi = eval_strategy(bt, st)
    print(f"  {STRATEGY_NAMES[st]:<40}: {nr}R {nt}t "
          f"hit {hr:5.1f}%  ROI {roi:6.1f}%")

# ---- grid search (morning model only; strategy selection stays AM) ----
rows = []
edges = np.arange(0.30, 0.80, 0.10)
for st in STRATEGY_NAMES:
    for lo_i in range(len(edges) - 1):
        for hi_i in range(lo_i + 1, len(edges)):
            for g in [0.0, 0.10, 0.20, 0.30]:
                nr, nt, hr, roi = eval_strategy(
                    bt, st, edges[lo_i], edges[hi_i], g)
                if nr < 100:
                    continue
                rows.append({'strategy': st,
                             'prob_min': round(float(edges[lo_i]), 2),
                             'prob_max': round(float(edges[hi_i]), 2),
                             'gap_min': round(float(g), 2),
                             'n_races': nr, 'n_tickets': nt,
                             'hit_rate': round(hr, 1),
                             'roi': round(roi, 1)})
res = pd.DataFrame(rows)
if not res.empty:
    res.sort_values('roi', ascending=False) \
       .to_csv("strategy_scan.csv", index=False, encoding='utf-8-sig')

    print("\nTop 10 by ROI (morning model, n>=100):")
    for _, r in res.sort_values('roi', ascending=False).head(10).iterrows():
        print(f"  {STRATEGY_NAMES[r['strategy']]:<40} "
              f"p[{r['prob_min']:.0%},{r['prob_max']:.0%}) "
              f"gap>={r['gap_min']:.0%} : {int(r['n_races'])}R "
              f"hit {r['hit_rate']}%  ROI {r['roi']}%")

    best = res.sort_values('roi', ascending=False).iloc[0]
    with open('optimal_strategy.json', 'w') as f:
        json.dump({
            'strategy': best['strategy'],
            'filter': {'prob_min': float(best['prob_min']),
                       'prob_max': float(best['prob_max']),
                       'gap_min': float(best['gap_min'])},
            'roi': float(best['roi']),
            'hit_rate': float(best['hit_rate']),
            'n_races': int(best['n_races']),
            'n_tickets': int(best['n_tickets']),
        }, f, indent=2)
    print("\nSaved: optimal_strategy.json / strategy_scan.csv")
    print("Note: grid-search selection carries multiple-comparison bias; "
          "treat the top ROI as optimistic.")
else:
    print("No configuration met the n>=100 requirement.")
