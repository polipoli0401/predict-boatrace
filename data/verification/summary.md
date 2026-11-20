# Verification (2026-10-19 .. 2026-11-20)

Generated: 2026-11-21T07:20:42+09:00

## By stadium (candidates = last pre-deadline decision, 100 JPY per ticket)

| Stadium | Predicted races | Candidate races | Tickets | Hits | Hit % | Invested | Returned | ROI % | Mean exp. return % | Log-loss (model / market) |
|---|---|---|---|---|---|---|---|---|---|---|
| Tokuyama | 192 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2068 / 2.1128 (n=192) |
| Ashiya | 180 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.224 / 2.0858 (n=180) |
| Omura | 240 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.271 / 2.1854 (n=240) |
| Total | 612 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2371 / 2.1333 (n=612) |

## Rule applied with closing odds (reference)

The decision rule applied after the fact with closing odds. Closing odds are not known at decision time, so this is not the result of actual candidates.

| Stadium | Races | Tickets | Hits | Hit % | ROI % | Mean exp. return % |
|---|---|---|---|---|---|---|
| Tokuyama | 138 | 240 | 10 | 7.2 | 61.5 | 167.1 |
| Ashiya | 140 | 238 | 10 | 7.1 | 52.9 | 176.3 |
| Omura | 172 | 279 | 15 | 8.7 | 86.4 | 171.8 |
| Total | 450 | 757 | 35 | 7.8 | 68.0 | 171.7 |

## Probability calibration (all combinations)

| Probability band | N | Mean predicted | Observed |
|---|---|---|---|
| (0.0, 0.02] | 5630 | 0.010 | 0.007 |
| (0.02, 0.05] | 2873 | 0.034 | 0.026 |
| (0.05, 0.1] | 1824 | 0.074 | 0.068 |
| (0.1, 0.15] | 940 | 0.127 | 0.143 |
| (0.15, 0.2] | 497 | 0.170 | 0.193 |
| (0.2, 0.3] | 407 | 0.235 | 0.290 |
| (0.3, 0.5] | 68 | 0.334 | 0.412 |
| (0.5, 1.0] | 1 | 0.636 | 0.000 |

Lower log-loss is better. Market = closing odds inverted and normalised. Small samples fluctuate strongly; do not act on them.

## Tracked strategies (new races only, pre-registered)

| Strategy | Since | Races | Tickets | Hits | ROI % | ROI 95% CI | Past (selection / test) |
|---|---|---|---|---|---|---|---|
| Favourite trio, 1 ticket (top win prob 30-40%, gap >= 20%) | 2026-11-20 | 0 | 0 | 0 | — | — | 145.2% (n=61) / 143.0% (n=64) |
| Top-3 by P(top-3) box, 1 ticket (top win prob 30-40%, gap >= 20%) | 2026-11-20 | 0 | 0 | 0 | — | — | 131.5% (n=61) / 115.5% (n=64) |
| Omura only: top-3 by P(top-3) box, 1 ticket (top win prob 20-30%) | 2026-11-20 | 1 | 1 | 0 | 0.0 | — | 100.6% (n=65) / 103.5% (n=60) |
| Win bet on the model's top boat when it is not the market favourite | 2026-11-20 | 6 | 6 | 2 | 101.7 | — | 115.7% (n=524) / 125.2% (n=409) |

A strategy counts as confirmed only if its ROI stays above 100% on new races with the lower CI bound above 100% (needs several hundred races).
