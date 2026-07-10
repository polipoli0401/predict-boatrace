"""Shared library for predict_boatrace.py and backtest_boatrace.py.

All stadium-specific configuration is injected via environment variables:
  TARGET_STADIUM_IDS : comma-separated stadium IDs (e.g. "01,02,03")
  STADIUM_PREF_MAP   : stadium-to-branch mapping (e.g. "01:10,02:20")
"""
import os
import pandas as pd
import numpy as np
from itertools import combinations

TARGET_STADIUM_IDS = [
    s.strip().zfill(2)
    for s in os.environ.get("TARGET_STADIUM_IDS", "").split(",")
    if s.strip()
]
if not TARGET_STADIUM_IDS:
    raise RuntimeError("TARGET_STADIUM_IDS is not set.")


def _parse_pref_map(raw):
    m = {}
    for pair in raw.split(","):
        if ":" in pair:
            k, v = pair.split(":")
            try:
                m[k.strip().zfill(2)] = int(v)
            except ValueError:
                pass
    return m


STADIUM_PREF = _parse_pref_map(os.environ.get("STADIUM_PREF_MAP", ""))

# ---- feature definitions ----
# Morning model: information available at ~3 AM on race day.
FEATURE_COLS = [
    'stadium_id_num', 'boat_number', 'is_boat1',
    'racer_class', 'racer_age', 'racer_weight',
    'flying_count', 'late_count', 'is_local',
    'official_national_win_rate', 'official_national_top2_rate',
    'official_national_top3_rate',
    'official_local_win_rate', 'official_local_top2_rate',
    'official_local_top3_rate', 'official_avg_st',
    'motor_top2_rate', 'motor_top3_rate', 'boat_top2_rate',
    'race_grade', 'is_final', 'is_semifinal',
    'stadium_course_win_rate', 'racer_course_win_rate', 'racer_course_n',
    'nwr_rank_in_race', 'nwr_diff_from_avg', 'race_top2_gap',
    'setsu_races', 'setsu_win_rate', 'setsu_top3_rate',
    'setsu_avg_place', 'motor_setsu_top3_rate',
]

# Live model: adds exhibition-run features available ~15 min before a race.
LIVE_EXTRA_COLS = [
    'exhibition_time', 'exhibition_rank', 'tilt', 'preview_st',
    'race_wind_live', 'race_wave_live',
]
FEATURE_COLS_LIVE = FEATURE_COLS + LIVE_EXTRA_COLS

PARAMS = dict(n_estimators=300, learning_rate=0.05, num_leaves=31,
              min_child_samples=20, subsample=0.8, colsample_bytree=0.8,
              class_weight='balanced', random_state=42, verbose=-1)

STRATEGY_NAMES = {
    'honmei_1pt':       'Favorite trio (1 ticket)',
    'axis_nagashi':     'Axis + partners (3 tickets)',
    'p3_box':           'Top3-model box (1 ticket)',
    'honmei_hazushi':   'Drop-the-favorite (4 tickets)',
    'weak1_box':        'Weak-lane1 exclusion box (4 tickets)',
    'top2_fix_nagashi': 'Top2 fixed + 3rd-slot spread (3 tickets)',
}


def add_common_features(df):
    """Race-level relative features and static flags."""
    df = df.copy()
    df['stadium_id_num'] = df['stadium_id'].astype(int)
    df['is_boat1'] = (df['boat_number'] == 1).astype(int)
    df['is_local'] = df.apply(
        lambda r: 1 if r.get('racer_branch') ==
        STADIUM_PREF.get(str(r['stadium_id']).zfill(2)) else 0, axis=1)
    grp = [g for g in ['race_date', 'stadium_id', 'race_number']
           if g in df.columns]
    df['nwr_rank_in_race'] = df.groupby(grp)['official_national_win_rate'] \
        .rank(ascending=False, method='min')
    df['nwr_diff_from_avg'] = df['official_national_win_rate'] - \
        df.groupby(grp)['official_national_win_rate'].transform('mean')

    def top2gap(s):
        v = np.sort(s.values)[::-1]
        return v[0] - v[1] if len(v) > 1 else 0
    df['race_top2_gap'] = df.groupby(grp)['official_national_win_rate'] \
        .transform(top2gap)

    # Exhibition rank within the race (NaN-safe; live feature).
    if 'exhibition_time' in df.columns:
        df['exhibition_rank'] = df.groupby(grp)['exhibition_time'] \
            .rank(method='min', ascending=True)
    else:
        df['exhibition_rank'] = np.nan

    for c in FEATURE_COLS_LIVE:
        if c not in df.columns:
            df[c] = np.nan
    return df


def add_time_aware_course_stats(df):
    """Stadium-by-lane and racer-by-lane win rates computed strictly from
    rows dated BEFORE each target row (no look-ahead leakage)."""
    df = df.copy()
    df['race_date'] = pd.to_datetime(df['race_date'])
    df = df.sort_values('race_date').reset_index(drop=True)
    base = df.dropna(subset=['course_number', 'place']).copy()
    if base.empty:
        df['stadium_course_win_rate'] = np.nan
        df['racer_course_win_rate'] = np.nan
        df['racer_course_n'] = 0
        return df
    base['is1'] = (base['place'] == 1).astype(int)
    base['ck'] = base['course_number'].astype(int)

    g1 = base.groupby(['race_date', 'stadium_id', 'ck'])['is1'] \
             .agg(['sum', 'size']).reset_index().sort_values('race_date')
    gg = g1.groupby(['stadium_id', 'ck'])
    g1['cw'], g1['cn'] = gg['sum'].cumsum(), gg['size'].cumsum()
    g1['sc_rate'] = g1['cw'] / g1['cn']
    left = df[['race_date', 'stadium_id', 'boat_number']].reset_index()
    left['ck'] = left['boat_number'].astype(int)
    left = left.sort_values('race_date')
    m = pd.merge_asof(left,
                      g1[['race_date', 'stadium_id', 'ck', 'sc_rate']]
                      .sort_values('race_date'),
                      on='race_date', by=['stadium_id', 'ck'],
                      direction='backward', allow_exact_matches=False)
    m = m.sort_values('index')
    df['stadium_course_win_rate'] = m['sc_rate'].values

    g2 = base.groupby(['race_date', 'racer_number', 'ck'])['is1'] \
             .agg(['sum', 'size']).reset_index().sort_values('race_date')
    gg2 = g2.groupby(['racer_number', 'ck'])
    g2['cw'], g2['cn'] = gg2['sum'].cumsum(), gg2['size'].cumsum()
    left2 = df[['race_date', 'racer_number', 'boat_number']].reset_index()
    left2['ck'] = left2['boat_number'].astype(int)
    left2 = left2.sort_values('race_date')
    m2 = pd.merge_asof(left2,
                       g2[['race_date', 'racer_number', 'ck', 'cw', 'cn']]
                       .sort_values('race_date'),
                       on='race_date', by=['racer_number', 'ck'],
                       direction='backward', allow_exact_matches=False)
    m2 = m2.sort_values('index')
    df['racer_course_n'] = m2['cn'].fillna(0).values
    df['racer_course_win_rate'] = np.where(
        m2['cn'].values >= 5, m2['cw'].values / m2['cn'].values, np.nan)
    return df


def add_setsu_features(df):
    """Within-meet form features. A meet is a block of consecutive race
    days at one stadium (a gap > 2 days starts a new meet). Cumulative
    stats exclude the current day (no leakage)."""
    df = df.copy()
    df['race_date'] = pd.to_datetime(df['race_date'])
    df = df.sort_values(['stadium_id', 'race_date']).reset_index(drop=True)

    day_map = df[['stadium_id', 'race_date']].drop_duplicates() \
        .sort_values(['stadium_id', 'race_date'])
    day_map['gap'] = day_map.groupby('stadium_id')['race_date'].diff().dt.days
    day_map['new_setsu'] = (day_map['gap'].isna()) | (day_map['gap'] > 2)
    day_map['setsu_id'] = day_map.groupby('stadium_id')['new_setsu'].cumsum()
    day_map['setsu_id'] = day_map['stadium_id'].astype(str) + "_" + \
        day_map['setsu_id'].astype(str)
    df = df.merge(day_map[['stadium_id', 'race_date', 'setsu_id']],
                  on=['stadium_id', 'race_date'], how='left')

    base = df.dropna(subset=['place']).copy()
    if base.empty:
        for c in ['setsu_races', 'setsu_win_rate', 'setsu_top3_rate',
                  'setsu_avg_place', 'motor_setsu_top3_rate']:
            df[c] = np.nan
        return df
    base['is1'] = (base['place'] == 1).astype(int)
    base['is3'] = (base['place'] <= 3).astype(int)
    d = base.groupby(['setsu_id', 'racer_number', 'race_date']) \
            .agg(n=('place', 'size'), w=('is1', 'sum'),
                 t3=('is3', 'sum'), sp=('place', 'sum')).reset_index() \
            .sort_values('race_date')
    g = d.groupby(['setsu_id', 'racer_number'])
    d['cn'] = g['n'].cumsum() - d['n']
    d['cw'] = g['w'].cumsum() - d['w']
    d['ct3'] = g['t3'].cumsum() - d['t3']
    d['csp'] = g['sp'].cumsum() - d['sp']

    df = df.merge(d[['setsu_id', 'racer_number', 'race_date',
                     'cn', 'cw', 'ct3', 'csp']],
                  on=['setsu_id', 'racer_number', 'race_date'], how='left')
    df['setsu_races'] = df['cn'].fillna(0)
    df['setsu_win_rate'] = np.where(df['cn'] > 0, df['cw'] / df['cn'], np.nan)
    df['setsu_top3_rate'] = np.where(df['cn'] > 0, df['ct3'] / df['cn'], np.nan)
    df['setsu_avg_place'] = np.where(df['cn'] > 0, df['csp'] / df['cn'], np.nan)
    df = df.drop(columns=['cn', 'cw', 'ct3', 'csp'])

    if 'motor_number' in df.columns:
        mb = base.dropna(subset=['motor_number'])
        if not mb.empty:
            md = mb.groupby(['setsu_id', 'stadium_id', 'motor_number',
                             'race_date']) \
                   .agg(n=('place', 'size'), t3=('is3', 'sum')).reset_index() \
                   .sort_values('race_date')
            mg = md.groupby(['setsu_id', 'stadium_id', 'motor_number'])
            md['cn'] = mg['n'].cumsum() - md['n']
            md['ct3'] = mg['t3'].cumsum() - md['t3']
            df = df.merge(md[['setsu_id', 'stadium_id', 'motor_number',
                              'race_date', 'cn', 'ct3']],
                          on=['setsu_id', 'stadium_id', 'motor_number',
                              'race_date'], how='left')
            df['motor_setsu_top3_rate'] = np.where(
                df['cn'] > 0, df['ct3'] / df['cn'], np.nan)
            df = df.drop(columns=['cn', 'ct3'])
        else:
            df['motor_setsu_top3_rate'] = np.nan
    else:
        df['motor_setsu_top3_rate'] = np.nan
    return df


def prepare_features(df):
    """Attach all features. Rows without `place` (today's races) are fine."""
    df = add_time_aware_course_stats(df)
    df = add_setsu_features(df)
    df = add_common_features(df)
    return df


def build_ticket(strategy, race_df):
    """Return a list of trio (3-boat combination) tickets.
    race_df must contain boat_number, p1 (win prob), p3 (top-3 prob)."""
    by_p1 = race_df.sort_values('p1', ascending=False)
    by_p3 = race_df.sort_values('p3', ascending=False)
    b1 = by_p1['boat_number'].astype(int).tolist()
    b3 = by_p3['boat_number'].astype(int).tolist()

    if strategy == 'honmei_1pt':
        return [sorted(b1[:3])]
    if strategy == 'axis_nagashi':
        axis = b1[0]
        partners = [b for b in b3 if b != axis][:3]
        return [sorted([axis, x, y]) for x, y in combinations(partners, 2)]
    if strategy == 'p3_box':
        return [sorted(b3[:3])]
    if strategy == 'honmei_hazushi':
        axis = b1[0]
        rest = [b for b in b3 if b != axis][:4]
        return [sorted(c) for c in combinations(rest, 3)]
    if strategy == 'weak1_box':
        p1b1 = race_df.loc[race_df['boat_number'] == 1, 'p1']
        if len(p1b1) and p1b1.iloc[0] < 0.40:
            rest = [b for b in b3 if b != 1][:4]
            return [sorted(c) for c in combinations(rest, 3)]
        return []
    if strategy == 'top2_fix_nagashi':
        # Fix the two strongest boats by win probability, then spread the
        # third slot across the next three candidates by top-3 probability.
        fixed = b1[:2]
        third_candidates = [b for b in b3 if b not in fixed][:3]
        return [sorted(fixed + [t]) for t in third_candidates]
    return []
