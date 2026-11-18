"""Trio (3-renpuku) combination probabilities.

The existing models output per-boat probabilities (P(win) normalised to
sum to 1, and P(top-3)). A trio probability is NOT the product of
per-boat top-3 probabilities. Instead we use the Harville (Plackett-Luce)
ordering model on P(win):

  P(i 1st, j 2nd, k 3rd) = p_i * p_j/(1-p_i) * p_k/(1-p_i-p_j)

and sum the 6 orderings of each unordered trio. The 20 trio
probabilities of a 6-boat race sum to exactly 1.

Raw Harville probabilities from these models are over-confident for
favourites (class_weight='balanced' training). A calibration map is fitted
by calibrate_trio.py on walk-forward (out-of-sample) backtest
probabilities and stored in trio_calibration.json. Calibrated values are
re-normalised so each race still sums to 1.
"""
import json
import os
from itertools import combinations, permutations

import numpy as np

CALIBRATION_JSON = "trio_calibration.json"
PROB_FLOOR = 1e-4


def combo_key(boats):
    return "-".join(str(int(b)) for b in sorted(boats))


def harville_trio(boats, p_win):
    """boats: list of boat numbers, p_win: matching win probabilities.
    Returns {"1-2-3": prob, ...} over all 3-boat combinations."""
    boats = [int(b) for b in boats]
    p = np.clip(np.asarray(p_win, dtype=float), 0.0, None)
    if len(boats) < 3 or p.sum() <= 0:
        return {}
    p = p / p.sum()
    out = {combo_key(c): 0.0 for c in combinations(boats, 3)}
    for i, j, k in permutations(range(len(boats)), 3):
        d1 = 1.0 - p[i]
        d2 = 1.0 - p[i] - p[j]
        if d1 <= 0 or d2 <= 0:
            continue
        out[combo_key((boats[i], boats[j], boats[k]))] += \
            p[i] * (p[j] / d1) * (p[k] / d2)
    total = sum(out.values())
    return {k: v / total for k, v in out.items()} if total > 0 else out


def load_calibration(path=CALIBRATION_JSON):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def apply_calibration(raw, calibration):
    """Map raw trio probabilities through the stored isotonic map and
    re-normalise. Returns raw unchanged when no calibration is given."""
    if not raw or not calibration:
        return dict(raw)
    xs = np.asarray(calibration["x"], dtype=float)
    ys = np.asarray(calibration["y"], dtype=float)
    keys = list(raw)
    vals = np.interp([raw[k] for k in keys], xs, ys)
    vals = np.clip(vals, PROB_FLOOR, None)
    vals = vals / vals.sum()
    return dict(zip(keys, (float(v) for v in vals)))


def trio_probabilities(boats, p_win, calibration=None, exclude=()):
    """Calibrated trio probabilities, optionally excluding boats
    (e.g. a scratched boat: its win probability is removed and the rest
    re-normalised, i.e. the conditional distribution)."""
    keep = [(b, p) for b, p in zip(boats, p_win) if int(b) not in set(exclude)]
    raw = harville_trio([b for b, _ in keep], [p for _, p in keep])
    return raw, apply_calibration(raw, calibration)
