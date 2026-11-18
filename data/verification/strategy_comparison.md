# Strategy comparison (out of sample)

Generated: 2026-11-19T08:36:29+09:00. Parameters are chosen on the selection period and reported on the later test period. ROI = return / stake; 95% CI by bootstrap over races. Random buying returns about 75% (trio takeout ~25%).

## Part 1 — ticket strategies (selection 2024-02-03 .. 2025-12-31, test 2026-01-01 .. 2026-11-17)

| Strategy | Unfiltered: selection | Unfiltered: test | Chosen filter | Filtered: selection | Filtered: test |
|---|---|---|---|---|---|
| Favorite trio (1 ticket) | 78.5% [75.7–81.2] (n=13035, hit 23.6%) | 74.7% [71.0–78.6] (n=6250, hit 23.2%) | {'prob_min': 0.5, 'prob_max': 0.6, 'gap_min': 0.0} | 80.3% [74.4–86.3] (n=2905, hit 22.2%) | 79.4% [67.8–91.8] (n=744, hit 23.0%) |
| Axis + partners (3 tickets) | 79.3% [77.5–81.2] (n=13035, hit 52.0%) | 76.9% [74.3–79.4] (n=6250, hit 51.5%) | {'prob_min': 0.6, 'prob_max': 0.7, 'gap_min': 0.0} | 80.3% [71.8–89.6] (n=701, hit 51.8%) | 112.3% (n=26, hit 65.4%) |
| Top3-model box (1 ticket) | 77.4% [74.9–80.0] (n=13035, hit 24.6%) | 76.9% [73.2–80.7] (n=6250, hit 24.6%) | {'prob_min': 0.3, 'prob_max': 0.5, 'gap_min': 0.3} | 80.1% [65.8–94.1] (n=513, hit 21.1%) | 74.1% [57.1–89.9] (n=331, hit 19.6%) |
| Drop-the-favorite (4 tickets) | 56.2% [51.9–60.6] (n=13035, hit 9.0%) | 52.7% [46.7–58.8] (n=6250, hit 9.0%) | {'prob_min': 0.3, 'prob_max': 0.4, 'gap_min': 0.0} | 71.4% [63.4–79.9] (n=2970, hit 16.3%) | 53.9% [46.7–62.0] (n=2048, hit 13.5%) |
| Weak-lane1 exclusion box (4 tickets) | 69.6% [62.6–77.2] (n=3311, hit 19.3%) | 55.8% [48.7–62.6] (n=2212, hit 16.7%) | {'prob_min': 0.3, 'prob_max': 0.4, 'gap_min': 0.0} | 71.1% [62.9–79.8] (n=2968, hit 18.5%) | 54.4% [47.0–62.0] (n=2047, hit 15.1%) |
| Top2 fixed + 3rd-slot spread (3 tickets) | 77.0% [75.2–78.8] (n=13035, hit 50.9%) | 74.6% [72.1–77.1] (n=6250, hit 50.4%) | {'prob_min': 0.6, 'prob_max': 0.7, 'gap_min': 0.3} | 85.1% [76.8–93.0] (n=698, hit 52.4%) | 60.9% (n=26, hit 42.3%) |
| Model top-1 trio (1 ticket) | 78.5% [75.6–81.2] (n=13035, hit 23.6%) | 74.4% [70.8–78.2] (n=6250, hit 23.2%) | {'top1_prob_min': 0.25} | 79.2% [76.3–82.2] (n=9988, hit 25.7%) | 75.9% [71.8–80.2] (n=4089, hit 26.6%) |

## Part 2 — with closing odds (selection 2026-01-01 .. 2026-06-30, test 2026-07-01 .. 2026-11-17)

- Market favourite, 1 ticket: selection 74.8% [70.5–79.2] (n=3577, hit 26.3%); test 73.0% [68.0–78.2] (n=2673, hit 25.9%)
- Model top-1 trio, 1 ticket: selection 73.8% [68.8–79.1] (n=3577, hit 23.1%); test 75.3% [69.5–81.2] (n=2673, hit 23.3%)

| Closing-odds band | All combos in band: selection | test | Model top-1 in band: selection | test |
|---|---|---|---|---|
| 1-3 | 74.5% [69.5–79.3] (n=1741, hit 34.3%) | 76.9% [71.1–82.5] (n=1313, hit 35.1%) | 75.0% [69.5–80.8] (n=1350, hit 33.1%) | 76.3% [69.6–83.1] (n=999, hit 32.8%) |
| 3-5 | 72.5% [68.7–76.2] (n=2773, hit 31.0%) | 77.4% [72.8–82.2] (n=2073, hit 32.4%) | 72.4% [65.3–80.3] (n=1501, hit 19.7%) | 73.2% [65.0–81.6] (n=1165, hit 20.0%) |
| 5-10 | 69.4% [65.6–73.5] (n=3318, hit 26.5%) | 77.7% [73.0–82.4] (n=2479, hit 29.0%) | 77.0% [61.9–93.3] (n=632, hit 12.5%) | 77.8% [59.2–96.4] (n=445, hit 13.0%) |
| 10-20 | 73.5% [68.1–79.0] (n=3373, hit 16.8%) | 75.5% [69.1–81.7] (n=2513, hit 17.2%) | 72.2% [15.5–136.1] (n=76, hit 6.6%) | 94.7% [18.9–191.9] (n=53, hit 7.5%) |
| 20-50 | 56.8% [51.1–62.5] (n=3513, hit 9.5%) | 67.9% [60.5–75.4] (n=2623, hit 11.1%) | 0.0% (n=3, hit 0.0%) | 0.0% (n=5, hit 0.0%) |
| 50-100 | 46.5% [37.1–56.1] (n=3506, hit 2.8%) | 45.9% [34.9–56.6] (n=2615, hit 2.8%) | — | — |
| 100- | 29.5% [17.8–42.9] (n=3202, hit 0.9%) | 36.2% [22.6–51.2] (n=2388, hit 1.2%) | — | — |

Many strategies are tested; with this many comparisons a few will exceed 100% on one period by chance. Only results that stay above 100% on the test period with a CI above 100% would be evidence of an edge.
