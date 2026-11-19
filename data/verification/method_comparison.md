# Method comparison (2026-04-01 .. 2026-11-18, 4275 races)

Generated: 2026-11-19T08:33:31+09:00. Monthly walk-forward; calibration and pool weights fitted on earlier months only. ROI uses closing odds (not known before the deadline).

## Overall

| Method | Log-loss | Top-1 hit % | Tickets | ROI % | ROI 95% CI | Mean exp. return % |
|---|---|---|---|---|---|---|
| A market (closing odds) | 2.249 | 26.2 | 0 | — | — | — |
| B morning model | 2.3645 | 24.0 | 5316 | 77.1 | 68.3–86.2 | 175.3 |
| C live model | 2.348 | 24.8 | 5285 | 77.8 | 68.5–87.3 | 175.5 |
| D live+ model | 2.3491 | 24.4 | 5514 | 77.1 | 67.6–86.9 | 176.1 |
| E market + model D | 2.2493 | 26.2 | 8 | 0.0 | — | 126.1 |

Pool weights (market, model) in the last month: (0.75, 0.25)

## By stadium (log-loss / ROI %)

| Stadium | A market (closing odds) | B morning model | C live model | D live+ model | E market + model D |
|---|---|---|---|---|---|
| Tokuyama | 2.2144 / — | 2.3352 / 80.3 | 2.3082 / 78.2 | 2.3067 / 82.2 | 2.2114 / 0.0 |
| Ashiya | 2.297 / — | 2.4081 / 79.6 | 2.4048 / 89.2 | 2.4058 / 74.6 | 2.3016 / 0.0 |
| Omura | 2.2384 / — | 2.3523 / 70.5 | 2.334 / 65.7 | 2.3382 / 73.8 | 2.2379 / 0.0 |

## By month (log-loss)

| Month | A | B | C | D | E |
|---|---|---|---|---|---|
| 2026-04 | 2.2138 | 2.3246 | 2.3131 | 2.3252 | 2.2143 |
| 2026-05 | 2.2493 | 2.365 | 2.3596 | 2.3518 | 2.2505 |
| 2026-06 | 2.2703 | 2.3673 | 2.3504 | 2.335 | 2.2614 |
| 2026-07 | 2.258 | 2.3811 | 2.3643 | 2.368 | 2.2603 |
| 2026-08 | 2.3021 | 2.4726 | 2.4404 | 2.464 | 2.3149 |
| 2026-09 | 2.2761 | 2.3602 | 2.3499 | 2.3365 | 2.2689 |
| 2026-10 | 2.2099 | 2.3327 | 2.3195 | 2.3167 | 2.2128 |
| 2026-11 | 2.1878 | 2.2579 | 2.2263 | 2.2283 | 2.178 |

## Model D: share of total gain (last month's model)

| Feature | Gain % |
|---|---|
| ex_course (new) | 0.49 |
| course_changed (new) | 0.14 |
| weight_adjustment (new) | 0.03 |
| propeller_new (new) | 0.0 |
| parts_count (new) | 0.02 |
| wind_tail (new) | 0.37 |
| wind_cross (new) | 0.29 |

Top 10:

| Feature | Gain % |
|---|---|
| boat_number | 55.09 |
| nwr_diff_from_avg | 11.38 |
| stadium_course_win_rate | 7.15 |
| racer_course_win_rate | 2.86 |
| is_boat1 | 2.52 |
| nwr_rank_in_race | 2.36 |
| exhibition_rank | 1.36 |
| official_national_top2_rate | 1.35 |
| setsu_avg_place | 1.32 |
| race_top2_gap | 1.12 |

Lower log-loss is better. Buying at random at market odds returns about 75% (trio takeout ~25%).
