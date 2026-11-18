from itertools import combinations

import pytest

from trio_prob import apply_calibration, harville_trio, trio_probabilities

BOATS = [1, 2, 3, 4, 5, 6]
P_WIN = [0.45, 0.2, 0.12, 0.1, 0.08, 0.05]


def test_twenty_combinations_sum_to_one():
    t = harville_trio(BOATS, P_WIN)
    assert len(t) == 20
    assert set(t) == {"-".join(map(str, c)) for c in combinations(BOATS, 3)}
    assert sum(t.values()) == pytest.approx(1.0)


def test_not_simple_product_of_top3_probabilities():
    # a naive product of per-boat probabilities does not sum to 1
    naive = {k: P_WIN[a - 1] * P_WIN[b - 1] * P_WIN[c - 1]
             for k, (a, b, c) in
             (("-".join(map(str, c)), c) for c in combinations(BOATS, 3))}
    assert sum(naive.values()) != pytest.approx(1.0)
    t = harville_trio(BOATS, P_WIN)
    assert t["1-2-3"] > t["4-5-6"]


def test_uniform_win_probabilities_give_uniform_trios():
    t = harville_trio(BOATS, [1 / 6] * 6)
    for v in t.values():
        assert v == pytest.approx(1 / 20)


def test_calibration_renormalises():
    raw = harville_trio(BOATS, P_WIN)
    cal = {"x": [0.0, 0.1, 1.0], "y": [0.01, 0.08, 0.5]}
    out = apply_calibration(raw, cal)
    assert sum(out.values()) == pytest.approx(1.0)
    assert apply_calibration(raw, None) == raw


def test_exclude_scratched_boat():
    raw, cal = trio_probabilities(BOATS, P_WIN, None, exclude=[6])
    assert len(raw) == 10
    assert all("6" not in k.split("-") for k in raw)
    assert sum(cal.values()) == pytest.approx(1.0)
