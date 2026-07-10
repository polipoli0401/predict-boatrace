"""Daily prediction runner (morning model).

Trains two LightGBM models (P(win), P(top-3)) on the accumulated
results CSV using morning-available features only, applies the strategy
selected by the backtest, and writes recommended tickets to
prediction_result.txt and prediction_history.csv.

Environment variables (repository secrets):
  API_BASE_URL, TARGET_STADIUM_IDS, STADIUM_PREF_MAP
"""
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score
import datetime
import requests
import os
import json

from predict_boatrace_lib import (
    TARGET_STADIUM_IDS, FEATURE_COLS, PARAMS, STRATEGY_NAMES,
    prepare_features, build_ticket
)

API_BASE = os.environ.get("API_BASE_URL")
if not API_BASE:
    raise RuntimeError("API_BASE_URL is not set.")

TARGET_DATE   = datetime.date.today()
RESULTS_CSV   = "boatrace_results.csv"
HISTORY_CSV   = "prediction_history.csv"
STRATEGY_JSON = "optimal_strategy.json"

output_lines = []


def log(msg):
    print(msg)
    output_lines.append(msg)


def fetch_today_programs(target_date):
    url = (f"{API_BASE}/programs/v2/"
           f"{target_date.year}/{target_date.strftime('%Y%m%d')}.json")
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 404:
            return pd.DataFrame()
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log(f"[ERROR] program fetch failed: {e}")
        return pd.DataFrame()
    records = []
    for race in data.get("programs", []):
        sid = str(race.get("race_stadium_number", "")).zfill(2)
        if sid not in TARGET_STADIUM_IDS:
            continue
        subtitle = str(race.get("race_subtitle") or "")
        boats = race.get("boats", {})
        for boat in (boats.values() if isinstance(boats, dict) else boats):
            records.append({
                "race_date": target_date.isoformat(), "stadium_id": sid,
                "race_number": race.get("race_number"),
                "boat_number": boat.get("racer_boat_number"),
                "racer_number": boat.get("racer_number"),
                "racer_name": boat.get("racer_name"),
                "official_national_win_rate": boat.get("racer_national_top_1_percent", 0),
                "official_national_top2_rate": boat.get("racer_national_top_2_percent", 0),
                "official_national_top3_rate": boat.get("racer_national_top_3_percent", 0),
                "official_local_win_rate": boat.get("racer_local_top_1_percent", 0),
                "official_local_top2_rate": boat.get("racer_local_top_2_percent", 0),
                "official_local_top3_rate": boat.get("racer_local_top_3_percent", 0),
                "official_avg_st": boat.get("racer_average_start_timing", 0),
                "racer_class": boat.get("racer_class_number", 4),
                "flying_count": boat.get("racer_flying_count", 0),
                "late_count": boat.get("racer_late_count", 0),
                "racer_age": boat.get("racer_age", 0),
                "racer_branch": boat.get("racer_branch_number", 0),
                "racer_weight": boat.get("racer_weight", 0),
                "motor_number": boat.get("racer_assigned_motor_number", 0),
                "motor_top2_rate": boat.get("racer_assigned_motor_top_2_percent", 0),
                "motor_top3_rate": boat.get("racer_assigned_motor_top_3_percent", 0),
                "boat_top2_rate": boat.get("racer_assigned_boat_top_2_percent", 0),
                "race_grade": race.get("race_grade_number", 5),
                "is_final": 1 if "優勝" in subtitle and "準優勝" not in subtitle else 0,
                "is_semifinal": 1 if "準優勝" in subtitle else 0,
            })
    return pd.DataFrame(records)


def save_prediction_history(race_date, stadium_id, race_number,
                            tickets, result_df, history_path):
    top3 = result_df.sort_values('p1', ascending=False).head(3)
    trio_main = str(tickets[0]) if tickets else None
    new_row = {
        'race_date': race_date, 'stadium_id': int(stadium_id),
        'race_number': race_number,
        'pred_1st': int(top3.iloc[0]['boat_number']),
        'pred_2nd': int(top3.iloc[1]['boat_number']) if len(top3) > 1 else None,
        'pred_3rd': int(top3.iloc[2]['boat_number']) if len(top3) > 2 else None,
        'pred_trio': trio_main,
        'pred_trio_all': str(tickets),
        'actual_1st': None, 'actual_2nd': None, 'actual_3rd': None,
        'actual_trio': None, 'first_hit': None, 'trio_hit': None,
        'payout_trio': None, 'payout_trifecta': None,
    }
    if os.path.exists(history_path):
        h = pd.read_csv(history_path)
        if 'pred_trio_all' not in h.columns:
            h['pred_trio_all'] = None
        mask = ((h['race_date'] == race_date) &
                (h['stadium_id'].astype(int) == int(stadium_id)) &
                (h['race_number'] == race_number))
        if mask.any():
            for k, v in new_row.items():
                if k.startswith('actual') or k.endswith('hit') \
                        or k.startswith('payout'):
                    continue
                h.loc[mask, k] = v
        else:
            h = pd.concat([h, pd.DataFrame([new_row])], ignore_index=True)
    else:
        h = pd.DataFrame([new_row])
    h.to_csv(history_path, index=False, encoding='utf-8-sig')


# ============================================================
# main
# ============================================================
log(f"=== Prediction run: {TARGET_DATE} ===")

strategy, strat_filter = 'honmei_1pt', {}
if os.path.exists(STRATEGY_JSON):
    with open(STRATEGY_JSON) as f:
        sj = json.load(f)
    strategy = sj.get('strategy', 'honmei_1pt')
    strat_filter = sj.get('filter', {})
    log(f"Strategy: {STRATEGY_NAMES.get(strategy, strategy)}")
    log(f"Filter: {strat_filter} "
        f"(backtest ROI {sj.get('roi', '?')}%, n={sj.get('n_races', '?')})")
else:
    log("Strategy: default (favorite trio, no filter)")

# forward-test summary so far
if os.path.exists(HISTORY_CSV):
    ev = pd.read_csv(HISTORY_CSV).dropna(subset=['actual_1st'])
    if not ev.empty:
        def n_tickets(s):
            try:
                return len(json.loads(str(s).replace("'", '"')))
            except Exception:
                return 0
        ev['nt'] = ev['pred_trio_all'].apply(n_tickets) \
            if 'pred_trio_all' in ev.columns else 1
        bet = ev[ev['nt'] > 0]
        if len(bet) > 0:
            inv = bet['nt'].sum() * 100
            ret = bet[bet['trio_hit'] == 1]['payout_trio'].sum()
            log(f"Forward test: {len(bet)} bet races, "
                f"hit {bet['trio_hit'].mean()*100:.1f}%, "
                f"ROI {ret/inv*100:.1f}%")

raw = pd.read_csv(RESULTS_CSV)
raw['stadium_id'] = raw['stadium_id'].astype(int).astype(str).str.zfill(2)
raw = raw[raw['stadium_id'].isin(TARGET_STADIUM_IDS)]
raw = raw.dropna(subset=['place', 'boat_number'])
raw['place'] = raw['place'].astype(int)
log(f"Training data: {len(raw)} rows ({raw['race_date'].nunique()} days)")

programs_df = fetch_today_programs(TARGET_DATE)

# Combine so today's rows inherit course stats and within-meet form.
if not programs_df.empty:
    prog = programs_df.copy()
    prog['place'] = np.nan
    prog['course_number'] = np.nan
    combined = pd.concat([raw, prog], ignore_index=True)
else:
    combined = raw.copy()

combined = prepare_features(combined)

train_df = combined[combined['place'].notna()].copy()
train_df['is_first'] = (train_df['place'] == 1).astype(int)
train_df['is_top3'] = (train_df['place'] <= 3).astype(int)

X = train_df[FEATURE_COLS]
m1 = lgb.LGBMClassifier(**PARAMS)
m1.fit(X, train_df['is_first'])
m3 = lgb.LGBMClassifier(**PARAMS)
m3.fit(X, train_df['is_top3'])

for name, ycol in [("win", 'is_first'), ("top3", 'is_top3')]:
    aucs, y = [], train_df[ycol]
    for tr, va in TimeSeriesSplit(n_splits=3).split(X):
        if y.iloc[va].nunique() < 2:
            continue
        mm = lgb.LGBMClassifier(**PARAMS)
        mm.fit(X.iloc[tr], y.iloc[tr])
        aucs.append(roc_auc_score(y.iloc[va],
                                  mm.predict_proba(X.iloc[va])[:, 1]))
    if aucs:
        log(f"{name} model AUC: {np.mean(aucs):.3f}")

if programs_df.empty:
    log("No races today at target stadiums (or programs not published).")
else:
    today_df = combined[combined['race_date'] ==
                        pd.Timestamp(TARGET_DATE)].copy()
    bet_summary, skip_count = [], 0

    for sid in TARGET_STADIUM_IDS:
        s_df = today_df[today_df['stadium_id'] == sid]
        if s_df.empty:
            continue
        log(f"\n--- Stadium {sid} ---")
        for rno in sorted(s_df['race_number'].unique()):
            race_df = s_df[s_df['race_number'] == rno].copy()
            Xr = race_df[FEATURE_COLS]
            p1 = m1.predict_proba(Xr)[:, 1]
            p3 = m3.predict_proba(Xr)[:, 1]
            race_df['p1'] = p1 / p1.sum() if p1.sum() > 0 else 1/len(race_df)
            race_df['p3'] = p3
            result = race_df.sort_values('p1', ascending=False)

            top_prob = result.iloc[0]['p1']
            gap = top_prob - (result.iloc[1]['p1'] if len(result) > 1 else 0)

            ok = True
            if 'prob_min' in strat_filter:
                ok &= strat_filter['prob_min'] <= top_prob
            if 'prob_max' in strat_filter:
                ok &= top_prob < strat_filter['prob_max']
            if 'gap_min' in strat_filter:
                ok &= strat_filter['gap_min'] <= gap

            tickets = build_ticket(strategy, race_df) if ok else []

            if tickets:
                bet_summary.append((sid, rno, tickets))
                log(f"R{rno}: BET {len(tickets)} tickets "
                    f"(p={top_prob:.1%}, gap={gap:.1%}) -> {tickets}")
            else:
                skip_count += 1

            save_prediction_history(TARGET_DATE.isoformat(), sid, rno,
                                    tickets, race_df, HISTORY_CSV)

    log(f"\n=== Summary ===")
    if bet_summary:
        total = sum(len(t) for _, _, t in bet_summary)
        log(f"Recommended: {len(bet_summary)} races, {total} tickets "
            f"({total*100} JPY) / skipped: {skip_count}")
        for sid, rno, tickets in bet_summary:
            log(f"  Stadium {sid} R{rno}: {tickets}")
    else:
        log(f"No recommended races today (skipped {skip_count})")

with open('prediction_result.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output_lines))
