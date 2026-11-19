# Verification (2026-10-19 .. 2026-11-19)

Generated: 2026-11-20T07:46:05+09:00

## By stadium (candidates = last pre-deadline decision, 100 JPY per ticket)

| Stadium | Predicted races | Candidate races | Tickets | Hits | Hit % | Invested | Returned | ROI % | Mean exp. return % | Log-loss (model / market) |
|---|---|---|---|---|---|---|---|---|---|---|
| Tokuyama | 180 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2213 / 2.1339 (n=180) |
| Ashiya | 168 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.1802 / 2.0456 (n=168) |
| Omura | 228 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2779 / 2.1958 (n=228) |
| Total | 576 | 0 | 0 | 0 | — | 0 | 0 | — | — | 2.2317 / 2.1327 (n=576) |

## Rule applied with closing odds (reference)

The decision rule applied after the fact with closing odds. Closing odds are not known at decision time, so this is not the result of actual candidates.

| Stadium | Races | Tickets | Hits | Hit % | ROI % | Mean exp. return % |
|---|---|---|---|---|---|---|
| Tokuyama | 128 | 220 | 9 | 7.0 | 61.6 | 166.2 |
| Ashiya | 130 | 220 | 9 | 6.9 | 53.9 | 175.0 |
| Omura | 161 | 258 | 15 | 9.3 | 93.4 | 172.3 |
| Total | 419 | 698 | 33 | 7.9 | 70.9 | 171.2 |

## Probability calibration (all combinations)

| Probability band | N | Mean predicted | Observed |
|---|---|---|---|
| (0.0, 0.02] | 5310 | 0.010 | 0.007 |
| (0.02, 0.05] | 2695 | 0.034 | 0.026 |
| (0.05, 0.1] | 1709 | 0.074 | 0.069 |
| (0.1, 0.15] | 883 | 0.127 | 0.143 |
| (0.15, 0.2] | 474 | 0.170 | 0.192 |
| (0.2, 0.3] | 382 | 0.235 | 0.288 |
| (0.3, 0.5] | 66 | 0.334 | 0.409 |
| (0.5, 1.0] | 1 | 0.636 | 0.000 |

Lower log-loss is better. Market = closing odds inverted and normalised. Small samples fluctuate strongly; do not act on them.

## Tracked strategies (new races only, pre-registered)

| Strategy | Since | Races | Tickets | Hits | ROI % | ROI 95% CI | Past (selection / test) |
|---|---|---|---|---|---|---|---|
| Favourite trio, 1 ticket (top win prob 30-40%, gap >= 20%) | 2026-11-20 | 0 | 0 | 0 | — | — | 145.2% (n=61) / 143.0% (n=64) |
| Top-3 by P(top-3) box, 1 ticket (top win prob 30-40%, gap >= 20%) | 2026-11-20 | 0 | 0 | 0 | — | — | 131.5% (n=61) / 115.5% (n=64) |
| Omura only: top-3 by P(top-3) box, 1 ticket (top win prob 20-30%) | 2026-11-20 | 0 | 0 | 0 | — | — | 100.6% (n=65) / 103.5% (n=60) |
| Win bet on the model's top boat when it is not the market favourite | 2026-11-20 | 0 | 0 | 0 | — | — | 115.7% (n=524) / 125.2% (n=409) |

A strategy counts as confirmed only if its ROI stays above 100% on new races with the lower CI bound above 100% (needs several hundred races).
