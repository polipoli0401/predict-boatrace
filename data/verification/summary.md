# Verification (2026-10-19 .. 2026-11-23)

Generated: 2026-11-24T11:33:35+09:00

## By stadium (candidates = last pre-deadline decision, 100 JPY per ticket)

| Stadium | Predicted races | Candidate races | Tickets | Hits | Hit % | Invested | Returned | ROI % | Mean exp. return % | Log-loss (model / market) |
|---|---|---|---|---|---|---|---|---|---|---|
| Tokuyama | 192 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2068 / 2.1128 (n=192) |
| Ashiya | 216 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2556 / 2.1081 (n=216) |
| Omura | 276 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2902 / 2.1897 (n=276) |
| Total | 684 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2559 / 2.1423 (n=684) |

## Rule applied with closing odds (reference)

The decision rule applied after the fact with closing odds. Closing odds are not known at decision time, so this is not the result of actual candidates.

| Stadium | Races | Tickets | Hits | Hit % | ROI % | Mean exp. return % |
|---|---|---|---|---|---|---|
| Tokuyama | 138 | 240 | 10 | 7.2 | 61.5 | 167.1 |
| Ashiya | 170 | 298 | 16 | 9.4 | 69.0 | 177.9 |
| Omura | 200 | 324 | 16 | 8.0 | 77.0 | 174.8 |
| Total | 508 | 862 | 42 | 8.3 | 69.9 | 173.8 |

## Probability calibration (all combinations)

| Probability band | N | Mean predicted | Observed |
|---|---|---|---|
| (0.0, 0.02] | 6250 | 0.010 | 0.007 |
| (0.02, 0.05] | 3249 | 0.034 | 0.026 |
| (0.05, 0.1] | 2041 | 0.074 | 0.068 |
| (0.1, 0.15] | 1062 | 0.127 | 0.139 |
| (0.15, 0.2] | 547 | 0.170 | 0.188 |
| (0.2, 0.3] | 458 | 0.235 | 0.295 |
| (0.3, 0.5] | 72 | 0.334 | 0.417 |
| (0.5, 1.0] | 1 | 0.636 | 0.000 |

Lower log-loss is better. Market = closing odds inverted and normalised. Small samples fluctuate strongly; do not act on them.

## Tracked strategies (new races only, pre-registered)

| Strategy | Since | Races | Tickets | Hits | ROI % | ROI 95% CI | Past (selection / test) |
|---|---|---|---|---|---|---|---|
| Favourite trio, 1 ticket (top win prob 30-40%, gap >= 20%) | 2026-11-20 | 3 | 3 | 0 | 0.0 | — | 145.2% (n=61) / 143.0% (n=64) |
| Top-3 by P(top-3) box, 1 ticket (top win prob 30-40%, gap >= 20%) | 2026-11-20 | 3 | 3 | 0 | 0.0 | — | 131.5% (n=61) / 115.5% (n=64) |
| Omura only: top-3 by P(top-3) box, 1 ticket (top win prob 20-30%) | 2026-11-20 | 3 | 3 | 1 | 73.3 | — | 100.6% (n=65) / 103.5% (n=60) |
| Win bet on the model's top boat when it is not the market favourite | 2026-11-20 | 21 | 21 | 9 | 134.3 | — | 115.7% (n=524) / 125.2% (n=409) |

A strategy counts as confirmed only if its ROI stays above 100% on new races with the lower CI bound above 100% (needs several hundred races).
