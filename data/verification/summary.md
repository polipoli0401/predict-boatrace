# Verification (2026-10-19 .. 2026-11-17)

Generated: 2026-11-19T08:11:40+09:00

## By stadium (candidates = last pre-deadline decision, 100 JPY per ticket)

| Stadium | Predicted races | Candidate races | Tickets | Hits | Hit % | Invested | Returned | ROI % | Mean exp. return % | Log-loss (model / market) |
|---|---|---|---|---|---|---|---|---|---|---|
| Tokuyama | 168 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2264 / 2.1395 (n=168) |
| Ashiya | 168 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.1802 / 2.0456 (n=168) |
| Omura | 216 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2893 / 2.21 (n=216) |
| Total | 552 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2369 / 2.1385 (n=552) |

## Rule applied with closing odds (reference)

The decision rule applied after the fact with closing odds. Closing odds are not known at decision time, so this is not the result of actual candidates.

| Stadium | Races | Tickets | Hits | Hit % | ROI % | Mean exp. return % |
|---|---|---|---|---|---|---|
| Tokuyama | 118 | 204 | 9 | 7.6 | 66.5 | 164.0 |
| Ashiya | 130 | 220 | 9 | 6.9 | 53.9 | 175.0 |
| Omura | 154 | 247 | 15 | 9.7 | 97.6 | 172.7 |
| Total | 402 | 671 | 33 | 8.2 | 73.8 | 170.8 |

## Probability calibration (all combinations)

| Probability band | N | Mean predicted | Observed |
|---|---|---|---|
| (0.0, 0.02] | 5084 | 0.010 | 0.007 |
| (0.02, 0.05] | 2581 | 0.034 | 0.026 |
| (0.05, 0.1] | 1647 | 0.074 | 0.066 |
| (0.1, 0.15] | 849 | 0.127 | 0.145 |
| (0.15, 0.2] | 450 | 0.170 | 0.189 |
| (0.2, 0.3] | 364 | 0.235 | 0.288 |
| (0.3, 0.5] | 64 | 0.335 | 0.422 |
| (0.5, 1.0] | 1 | 0.636 | 0.000 |

Lower log-loss is better. Market = closing odds inverted and normalised. Small samples fluctuate strongly; do not act on them.
