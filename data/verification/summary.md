# Verification (2026-10-19 .. 2026-11-26)

Generated: 2026-11-27T08:59:41+09:00

## By stadium (candidates = last pre-deadline decision, 100 JPY per ticket)

| Stadium | Predicted races | Candidate races | Tickets | Hits | Hit % | Invested | Returned | ROI % | Mean exp. return % | Log-loss (model / market) |
|---|---|---|---|---|---|---|---|---|---|---|
| Tokuyama | 228 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.228 / 2.1437 (n=228) |
| Ashiya | 240 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.307 / 2.1695 (n=240) |
| Omura | 297 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.3005 / 2.1868 (n=297) |
| Total | 765 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2809 / 2.1685 (n=765) |

## Rule applied with closing odds (reference)

The decision rule applied after the fact with closing odds. Closing odds are not known at decision time, so this is not the result of actual candidates.

| Stadium | Races | Tickets | Hits | Hit % | ROI % | Mean exp. return % |
|---|---|---|---|---|---|---|
| Tokuyama | 166 | 291 | 16 | 9.6 | 90.5 | 173.4 |
| Ashiya | 190 | 342 | 20 | 10.5 | 84.7 | 178.4 |
| Omura | 217 | 359 | 18 | 8.3 | 73.5 | 176.9 |
| Total | 573 | 992 | 54 | 9.4 | 82.3 | 176.4 |

## Probability calibration (all combinations)

| Probability band | N | Mean predicted | Observed |
|---|---|---|---|
| (0.0, 0.02] | 6959 | 0.010 | 0.007 |
| (0.02, 0.05] | 3650 | 0.034 | 0.027 |
| (0.05, 0.1] | 2290 | 0.074 | 0.070 |
| (0.1, 0.15] | 1191 | 0.127 | 0.134 |
| (0.15, 0.2] | 627 | 0.170 | 0.196 |
| (0.2, 0.3] | 507 | 0.234 | 0.280 |
| (0.3, 0.5] | 75 | 0.333 | 0.400 |
| (0.5, 1.0] | 1 | 0.636 | 0.000 |

Lower log-loss is better. Market = closing odds inverted and normalised. Small samples fluctuate strongly; do not act on them.

## Tracked strategies (new races only, pre-registered)

| Strategy | Since | Races | Tickets | Hits | ROI % | ROI 95% CI | Past (selection / test) |
|---|---|---|---|---|---|---|---|
| Favourite trio, 1 ticket (top win prob 30-40%, gap >= 20%) | 2026-11-20 | 3 | 3 | 0 | 0.0 | — | 145.2% (n=61) / 143.0% (n=64) |
| Top-3 by P(top-3) box, 1 ticket (top win prob 30-40%, gap >= 20%) | 2026-11-20 | 3 | 3 | 0 | 0.0 | — | 131.5% (n=61) / 115.5% (n=64) |
| Omura only: top-3 by P(top-3) box, 1 ticket (top win prob 20-30%) | 2026-11-20 | 3 | 3 | 1 | 73.3 | — | 100.6% (n=65) / 103.5% (n=60) |
| Win bet on the model's top boat when it is not the market favourite | 2026-11-20 | 39 | 39 | 15 | 126.4 | 69.7–196.9 | 115.7% (n=524) / 125.2% (n=409) |

A strategy counts as confirmed only if its ROI stays above 100% on new races with the lower CI bound above 100% (needs several hundred races).
