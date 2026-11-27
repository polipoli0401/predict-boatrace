# Verification (2026-10-19 .. 2026-11-27)

Generated: 2026-11-28T08:43:05+09:00

## By stadium (candidates = last pre-deadline decision, 100 JPY per ticket)

| Stadium | Predicted races | Candidate races | Tickets | Hits | Hit % | Invested | Returned | ROI % | Mean exp. return % | Log-loss (model / market) |
|---|---|---|---|---|---|---|---|---|---|---|
| Tokuyama | 240 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2429 / 2.1539 (n=240) |
| Ashiya | 240 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.307 / 2.1695 (n=240) |
| Omura | 309 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2949 / 2.1783 (n=309) |
| Total | 789 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2827 / 2.1682 (n=789) |

## Rule applied with closing odds (reference)

The decision rule applied after the fact with closing odds. Closing odds are not known at decision time, so this is not the result of actual candidates.

| Stadium | Races | Tickets | Hits | Hit % | ROI % | Mean exp. return % |
|---|---|---|---|---|---|---|
| Tokuyama | 176 | 311 | 16 | 9.1 | 84.7 | 174.5 |
| Ashiya | 190 | 342 | 20 | 10.5 | 84.7 | 178.4 |
| Omura | 226 | 378 | 20 | 8.8 | 80.3 | 176.7 |
| Total | 592 | 1031 | 56 | 9.5 | 83.1 | 176.6 |

## Probability calibration (all combinations)

| Probability band | N | Mean predicted | Observed |
|---|---|---|---|
| (0.0, 0.02] | 7177 | 0.010 | 0.007 |
| (0.02, 0.05] | 3752 | 0.034 | 0.027 |
| (0.05, 0.1] | 2376 | 0.074 | 0.071 |
| (0.1, 0.15] | 1231 | 0.127 | 0.132 |
| (0.15, 0.2] | 643 | 0.170 | 0.196 |
| (0.2, 0.3] | 524 | 0.235 | 0.281 |
| (0.3, 0.5] | 76 | 0.334 | 0.395 |
| (0.5, 1.0] | 1 | 0.636 | 0.000 |

Lower log-loss is better. Market = closing odds inverted and normalised. Small samples fluctuate strongly; do not act on them.

## Tracked strategies (new races only, pre-registered)

| Strategy | Since | Races | Tickets | Hits | ROI % | ROI 95% CI | Past (selection / test) |
|---|---|---|---|---|---|---|---|
| Favourite trio, 1 ticket (top win prob 30-40%, gap >= 20%) | 2026-11-20 | 4 | 4 | 1 | 117.5 | — | 145.2% (n=61) / 143.0% (n=64) |
| Top-3 by P(top-3) box, 1 ticket (top win prob 30-40%, gap >= 20%) | 2026-11-20 | 4 | 4 | 0 | 0.0 | — | 131.5% (n=61) / 115.5% (n=64) |
| Omura only: top-3 by P(top-3) box, 1 ticket (top win prob 20-30%) | 2026-11-20 | 4 | 4 | 1 | 55.0 | — | 100.6% (n=65) / 103.5% (n=60) |
| Win bet on the model's top boat when it is not the market favourite | 2026-11-20 | 45 | 45 | 16 | 113.8 | 63.1–173.6 | 115.7% (n=524) / 125.2% (n=409) |

A strategy counts as confirmed only if its ROI stays above 100% on new races with the lower CI bound above 100% (needs several hundred races).
