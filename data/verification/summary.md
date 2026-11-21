# Verification (2026-10-19 .. 2026-11-21)

Generated: 2026-11-22T06:04:58+09:00

## By stadium (candidates = last pre-deadline decision, 100 JPY per ticket)

| Stadium | Predicted races | Candidate races | Tickets | Hits | Hit % | Invested | Returned | ROI % | Mean exp. return % | Log-loss (model / market) |
|---|---|---|---|---|---|---|---|---|---|---|
| Tokuyama | 192 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2068 / 2.1128 (n=192) |
| Ashiya | 192 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2605 / 2.1156 (n=192) |
| Omura | 252 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2898 / 2.1878 (n=252) |
| Total | 636 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2559 / 2.1433 (n=636) |

## Rule applied with closing odds (reference)

The decision rule applied after the fact with closing odds. Closing odds are not known at decision time, so this is not the result of actual candidates.

| Stadium | Races | Tickets | Hits | Hit % | ROI % | Mean exp. return % |
|---|---|---|---|---|---|---|
| Tokuyama | 138 | 240 | 10 | 7.2 | 61.5 | 167.1 |
| Ashiya | 148 | 255 | 11 | 7.4 | 57.5 | 177.7 |
| Omura | 180 | 294 | 15 | 8.3 | 82.0 | 173.3 |
| Total | 466 | 789 | 36 | 7.7 | 67.8 | 172.9 |

## Probability calibration (all combinations)

| Probability band | N | Mean predicted | Observed |
|---|---|---|---|
| (0.0, 0.02] | 5837 | 0.010 | 0.007 |
| (0.02, 0.05] | 2993 | 0.034 | 0.027 |
| (0.05, 0.1] | 1899 | 0.074 | 0.067 |
| (0.1, 0.15] | 985 | 0.127 | 0.141 |
| (0.15, 0.2] | 513 | 0.170 | 0.189 |
| (0.2, 0.3] | 422 | 0.235 | 0.289 |
| (0.3, 0.5] | 70 | 0.334 | 0.414 |
| (0.5, 1.0] | 1 | 0.636 | 0.000 |

Lower log-loss is better. Market = closing odds inverted and normalised. Small samples fluctuate strongly; do not act on them.

## Tracked strategies (new races only, pre-registered)

| Strategy | Since | Races | Tickets | Hits | ROI % | ROI 95% CI | Past (selection / test) |
|---|---|---|---|---|---|---|---|
| Favourite trio, 1 ticket (top win prob 30-40%, gap >= 20%) | 2026-11-20 | 1 | 1 | 0 | 0.0 | — | 145.2% (n=61) / 143.0% (n=64) |
| Top-3 by P(top-3) box, 1 ticket (top win prob 30-40%, gap >= 20%) | 2026-11-20 | 1 | 1 | 0 | 0.0 | — | 131.5% (n=61) / 115.5% (n=64) |
| Omura only: top-3 by P(top-3) box, 1 ticket (top win prob 20-30%) | 2026-11-20 | 3 | 3 | 1 | 73.3 | — | 100.6% (n=65) / 103.5% (n=60) |
| Win bet on the model's top boat when it is not the market favourite | 2026-11-20 | 11 | 11 | 3 | 76.4 | — | 115.7% (n=524) / 125.2% (n=409) |

A strategy counts as confirmed only if its ROI stays above 100% on new races with the lower CI bound above 100% (needs several hundred races).
