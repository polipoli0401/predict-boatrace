"""Daily data fetcher.

Downloads race results, program (entry list) data and exhibition-run
data for the configured stadiums, maintains an incremental local CSV,
and evaluates pending predictions against confirmed results.

Environment variables (repository secrets):
  API_BASE_URL       : data source base URL
  TARGET_STADIUM_IDS : comma-separated stadium IDs
"""
import requests
import pandas as pd
from datetime import date, timedelta
import time
import os
import json

API_BASE = os.environ.get("API_BASE_URL")
if not API_BASE:
    raise RuntimeError("API_BASE_URL is not set.")

TARGET_STADIUM_IDS = [
    s.strip().zfill(2)
    for s in os.environ.get("TARGET_STADIUM_IDS", "").split(",")
    if s.strip()
]
if not TARGET_STADIUM_IDS:
    raise RuntimeError("TARGET_STADIUM_IDS is not set.")

TARGET_DATE_FROM = date(2024, 1, 1)
TARGET_DATE_TO   = date.today() - timedelta(days=1)
INTERVAL_SEC     = 1.5

# Exhibition backfill is attempted for dates on/after this value.
# If the data source has no exhibition data for older dates, raise this
# to the first covered date to avoid re-attempting them on every run.
PREVIEW_MIN_DATE = "2024-01-01"

RESULTS_CSV = "boatrace_results.csv"
HISTORY_CSV = "prediction_history.csv"

PREVIEW_COLS = ['exhibition_time', 'tilt', 'preview_st',
                'preview_weight', 'race_wind_live', 'race_wave_live']

PROGRAM_COLS = [
    'official_national_win_rate', 'official_national_top2_rate',
    'official_national_top3_rate', 'official_local_win_rate',
    'official_local_top2_rate', 'official_local_top3_rate',
    'official_avg_st', 'racer_class', 'flying_count', 'late_count',
    'racer_age', 'racer_branch', 'racer_weight',
    'motor_number', 'motor_top2_rate', 'motor_top3_rate',
    'boat_top2_rate', 'boat_top3_rate',
    'race_grade', 'is_final', 'is_semifinal',
]


def fetch_json(kind, target_date):
    url = (f"{API_BASE}/{kind}/v2/"
           f"{target_date.year}/{target_date.strftime('%Y%m%d')}.json")
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def parse_results(data):
    results = []
    for race in data.get("results", []):
        sid = str(race.get("race_stadium_number", "")).zfill(2)
        if sid not in TARGET_STADIUM_IDS:
            continue
        payouts = race.get("payouts", {})
        pt, pf = None, None
        if isinstance(payouts, dict):
            td, fd = payouts.get("trio"), payouts.get("trifecta")
            if isinstance(td, list) and td:
                pt = td[0].get("payout") if isinstance(td[0], dict) else td[0]
            if isinstance(fd, list) and fd:
                pf = fd[0].get("payout") if isinstance(fd[0], dict) else fd[0]
        boats = race.get("boats", {})
        for boat in (boats.values() if isinstance(boats, dict) else boats):
            results.append({
                "race_date":       race.get("race_date"),
                "stadium_id":      sid,
                "race_number":     race.get("race_number"),
                "boat_number":     boat.get("racer_boat_number"),
                "course_number":   boat.get("racer_course_number"),
                "racer_number":    boat.get("racer_number"),
                "racer_name":      boat.get("racer_name"),
                "place":           boat.get("racer_place_number"),
                "start_timing":    boat.get("racer_start_timing"),
                "payout_trio":     pt,
                "payout_trifecta": pf,
            })
    return results


def parse_programs(data):
    pmap = {}
    for race in data.get("programs", []):
        sid = str(race.get("race_stadium_number", "")).zfill(2)
        if sid not in TARGET_STADIUM_IDS:
            continue
        rno      = race.get("race_number")
        grade    = race.get("race_grade_number", 5)
        subtitle = str(race.get("race_subtitle") or "")
        boats = race.get("boats", {})
        for boat in (boats.values() if isinstance(boats, dict) else boats):
            bn = boat.get("racer_boat_number")
            pmap[(sid, rno, bn)] = {
                "official_national_win_rate":  boat.get("racer_national_top_1_percent", 0),
                "official_national_top2_rate": boat.get("racer_national_top_2_percent", 0),
                "official_national_top3_rate": boat.get("racer_national_top_3_percent", 0),
                "official_local_win_rate":     boat.get("racer_local_top_1_percent", 0),
                "official_local_top2_rate":    boat.get("racer_local_top_2_percent", 0),
                "official_local_top3_rate":    boat.get("racer_local_top_3_percent", 0),
                "official_avg_st":             boat.get("racer_average_start_timing", 0),
                "racer_class":                 boat.get("racer_class_number", 4),
                "flying_count":                boat.get("racer_flying_count", 0),
                "late_count":                  boat.get("racer_late_count", 0),
                "racer_age":                   boat.get("racer_age", 0),
                "racer_branch":                boat.get("racer_branch_number", 0),
                "racer_weight":                boat.get("racer_weight", 0),
                "motor_number":                boat.get("racer_assigned_motor_number", 0),
                "motor_top2_rate":             boat.get("racer_assigned_motor_top_2_percent", 0),
                "motor_top3_rate":             boat.get("racer_assigned_motor_top_3_percent", 0),
                "boat_top2_rate":              boat.get("racer_assigned_boat_top_2_percent", 0),
                "boat_top3_rate":              boat.get("racer_assigned_boat_top_3_percent", 0),
                "race_grade":                  grade,
                "is_final":  1 if "優勝" in subtitle and "準優勝" not in subtitle else 0,
                "is_semifinal": 1 if "準優勝" in subtitle else 0,
            }
    return pmap


def parse_previews(data):
    """Exhibition-run data, published ~15 minutes before each race.
    Availability for historical dates depends on the data source."""
    vmap = {}
    for race in data.get("previews", []):
        sid = str(race.get("race_stadium_number", "")).zfill(2)
        if sid not in TARGET_STADIUM_IDS:
            continue
        rno  = race.get("race_number")
        wind = race.get("race_wind")
        wave = race.get("race_wave")
        boats = race.get("boats", {})
        items = boats.items() if isinstance(boats, dict) else enumerate(boats)
        for _, boat in items:
            bn = boat.get("racer_boat_number")
            vmap[(sid, rno, bn)] = {
                "exhibition_time": boat.get("racer_exhibition_time"),
                "tilt":            boat.get("racer_tilt_adjustment"),
                "preview_st":      boat.get("racer_start_timing"),
                "preview_weight":  boat.get("racer_weight"),
                "race_wind_live":  wind,
                "race_wave_live":  wave,
            }
    return vmap


def evaluate_predictions(results_df, history_path):
    """Fill actual results into pending prediction rows and report totals."""
    if not os.path.exists(history_path):
        return
    h = pd.read_csv(history_path)
    if 'stadium_id' not in h.columns:
        return
    une = h[h['actual_1st'].isna()]
    if une.empty:
        print("Evaluation: no pending predictions")
        return
    rdf = results_df.copy()
    rdf['stadium_id'] = rdf['stadium_id'].astype(int)
    updated = 0
    for idx, row in une.iterrows():
        rr = rdf[(rdf['race_date'] == row['race_date']) &
                 (rdf['stadium_id'] == int(row['stadium_id'])) &
                 (rdf['race_number'] == int(row['race_number']))].sort_values('place')
        t3 = rr[rr['place'] <= 3]
        if len(t3) < 3:
            continue
        a = [int(t3.iloc[k]['boat_number']) for k in range(3)]

        # tickets: prefer the multi-ticket column, fall back to the single trio
        tickets = []
        try:
            tickets = json.loads(str(row.get('pred_trio_all', '[]'))
                                 .replace("'", '"'))
        except Exception:
            tickets = []
        if not tickets and pd.notna(row.get('pred_trio')):
            try:
                tickets = [json.loads(str(row['pred_trio']).replace("'", '"'))]
            except Exception:
                tickets = []

        trio_hit = 1 if any(sorted(t) == sorted(a) for t in tickets) else 0
        h.at[idx, 'actual_1st'], h.at[idx, 'actual_2nd'], \
            h.at[idx, 'actual_3rd'] = a
        h.at[idx, 'actual_trio']     = str(sorted(a))
        h.at[idx, 'first_hit']       = 1 if pd.notna(row['pred_1st']) and \
            int(row['pred_1st']) == a[0] else 0
        h.at[idx, 'trio_hit']        = trio_hit
        h.at[idx, 'payout_trio']     = rr.iloc[0].get('payout_trio')
        h.at[idx, 'payout_trifecta'] = rr.iloc[0].get('payout_trifecta')
        updated += 1
    h.to_csv(history_path, index=False, encoding='utf-8-sig')

    ev = h.dropna(subset=['actual_1st'])
    if not ev.empty:
        def n_tickets(s):
            try:
                return len(json.loads(str(s).replace("'", '"')))
            except Exception:
                return 0
        ev = ev.copy()
        ev['nt'] = ev['pred_trio_all'].apply(n_tickets) \
            if 'pred_trio_all' in ev.columns else 1
        bet = ev[ev['nt'] > 0]
        print(f"Evaluation: {updated} races updated")
        if len(bet) > 0:
            inv = bet['nt'].sum() * 100
            ret = bet[bet['trio_hit'] == 1]['payout_trio'].sum()
            print(f"Cumulative (bet races only): {len(bet)} races, "
                  f"hit {bet['trio_hit'].mean()*100:.1f}%, "
                  f"ROI {ret/inv*100:.1f}%")


# ============================================================
# main
# ============================================================
existing_df = pd.DataFrame()
if os.path.exists(RESULTS_CSV):
    existing_df = pd.read_csv(RESULTS_CSV)
    existing_df['stadium_id'] = existing_df['stadium_id'] \
        .astype(int).astype(str).str.zfill(2)
    for col in PROGRAM_COLS + PREVIEW_COLS:
        if col not in existing_df.columns:
            existing_df[col] = None

existing_keys = set()
if not existing_df.empty:
    existing_keys = set(zip(existing_df['race_date'],
                            existing_df['stadium_id']))

new_rows = []
program_filled, preview_filled = 0, 0
current = TARGET_DATE_FROM

while current <= TARGET_DATE_TO:
    ds = current.isoformat()
    missing = [s for s in TARGET_STADIUM_IDS if (ds, s) not in existing_keys]

    # decide which backfills are needed for already-stored dates
    need_preview_fill, need_program_fill = False, False
    if not existing_df.empty and not missing:
        day_rows = existing_df[existing_df['race_date'] == ds]
        if len(day_rows) > 0:
            if ds >= PREVIEW_MIN_DATE and \
                    day_rows['exhibition_time'].isna().all():
                need_preview_fill = True
            if day_rows['race_grade'].isna().all() \
                    or day_rows['racer_age'].isna().all():
                need_program_fill = True

    if not missing and not need_preview_fill and not need_program_fill:
        current += timedelta(days=1)
        continue

    # fetch only what this date actually needs
    r_data = fetch_json("results", current) if missing else None
    if missing and r_data is None:
        current += timedelta(days=1)
        time.sleep(0.3)
        continue

    v_data = fetch_json("previews", current) \
        if (missing or need_preview_fill) else None
    vmap = parse_previews(v_data) if v_data else {}

    p_data = fetch_json("programs", current) \
        if (missing or need_program_fill) else None
    pmap = parse_programs(p_data) if p_data else {}

    if need_preview_fill and vmap:
        day_rows = existing_df[existing_df['race_date'] == ds]
        for i, row in day_rows.iterrows():
            key = (row['stadium_id'], row['race_number'], row['boat_number'])
            if key in vmap:
                for c, v in vmap[key].items():
                    existing_df.at[i, c] = v
        preview_filled += 1

    if need_program_fill and pmap:
        day_rows = existing_df[existing_df['race_date'] == ds]
        for i, row in day_rows.iterrows():
            key = (row['stadium_id'], row['race_number'], row['boat_number'])
            if key in pmap:
                for c, v in pmap[key].items():
                    existing_df.at[i, c] = v
        program_filled += 1

    if missing and r_data:
        day_results = [r for r in parse_results(r_data)
                       if r['stadium_id'] in missing]
        for rec in day_results:
            key = (rec['stadium_id'], rec['race_number'], rec['boat_number'])
            rec.update(pmap.get(key, {c: None for c in PROGRAM_COLS}))
            rec.update(vmap.get(key, {c: None for c in PREVIEW_COLS}))
        new_rows.extend(day_results)

    current += timedelta(days=1)
    time.sleep(INTERVAL_SEC)

combined = pd.concat([existing_df, pd.DataFrame(new_rows)],
                     ignore_index=True) if new_rows else existing_df

if not combined.empty:
    combined['stadium_id'] = combined['stadium_id'] \
        .astype(int).astype(str).str.zfill(2)
    combined = (combined
                .drop_duplicates(subset=['race_date', 'stadium_id',
                                         'race_number', 'boat_number'])
                .sort_values(['race_date', 'stadium_id',
                              'race_number', 'boat_number'])
                .reset_index(drop=True))
    combined.to_csv(RESULTS_CSV, index=False, encoding='utf-8-sig')

    ex_cov = combined['exhibition_time'].notna().mean() * 100
    print(f"Fetch done: +{len(new_rows)} new rows, "
          f"backfilled {program_filled} program-days / "
          f"{preview_filled} exhibition-days")
    print(f"Total: {len(combined)} rows "
          f"({combined['race_date'].nunique()} days), "
          f"exhibition coverage {ex_cov:.1f}%")
    evaluate_predictions(combined, HISTORY_CSV)
else:
    print("Fetch done: no data")
