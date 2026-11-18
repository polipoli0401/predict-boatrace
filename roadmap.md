# Roadmap

Current phase: **race-day pipeline — verification build-up**
(night prediction + board running; live odds source still open).

Note: Phase 2's freeze window has ended. The 2026-11 changes (JST dates,
v1 entry lists, race-day pipeline) do not change the model or the
strategy logic, but the JST fix changes which day is predicted, so the
forward test is counted again from the first run after the change.

## Timeline

### Phase 1 — Foundation (done)
- [x] Incremental data pipeline (results / programs / exhibition previews)
- [x] Leak-free feature engineering (walk-forward course stats, within-meet form)
- [x] Dual-model architecture: P(win) + P(top-3), LightGBM
- [x] Removal of start-timing leakage (AUC 0.90 → 0.85, honest baseline)
- [x] 6 ticket strategies + probability-band grid search
- [x] Baseline comparison (always-[1,2,3]) and near-miss diagnosis
- [x] Public repo migration: secrets, English comments, MIT license
- [x] Morning vs live model comparison on exhibition-covered races

### Phase 2 — Forward validation (now → mid-Aug 2026)
- [ ] Run daily predictor untouched; strategy file stays frozen
- [ ] Weekly health check: confirm daily auto-commits exist
- [ ] Accumulate ~600 new races (~30 days) as out-of-sample data

**Rule: no code or feature changes during this window.**
Any change invalidates the forward test and restarts the clock.

### Phase 3 — Re-validation (mid-Aug 2026)
- [ ] Re-run backtest including the new month of data
- [ ] Key question: does the selected configuration
      (Top3-box, p[40–50%), gap ≥ 30%) survive on data it was not
      selected on? Grid-search winners are optimistic by construction;
      out-of-time survival is the real test.
- [ ] Add live-model grid search (exhibition features × filters)
      to test whether any live configuration clears ROI 100%

### Phase 4 — Conditional extensions (only if Phase 3 justifies them)
- [ ] `live_predict.py`: manual pre-race prediction using saved models
      + exhibition data (build only if live grid search shows value)
- [ ] Stadium-level strategy filters (needs more per-stadium samples)
- [ ] Recent-ST form features (mean / variance of last ~10 starts)
- [ ] Race-slot context features (class gaps, race number, lineup design)

### Phase 5 — Race-day pipeline (2026-11 →)

Spec: night prediction, race-day odds, one board for the target
stadiums sorted by deadline, expected return and decision, per-stadium
verification. Automatic betting is out of scope.

#### 5-1 Built (2026-11-19)
- [x] Current-state survey: data sources, workflows, runtimes
      (training + prediction ~20 s; the old ~30 min fetch re-requested
      ~900 non-race (date, stadium) pairs every run → now remembered,
      fetch ~1 min)
- [x] JST dates in fetch / predict (the UTC date predicted the previous
      JST day)
- [x] Night prediction at 00:37 JST from the v1 day file, v2 fallback;
      v1 → v2 field mapping checked on the same day
- [x] Saved models (`models/`) and re-prediction without retraining
      for missing / changed races (~4 s)
- [x] Trio probabilities for all 20 combinations (Harville on P(win)),
      isotonic calibration from walk-forward backtest probabilities,
      time-split check stored in `trio_calibration.json`
- [x] Prediction / race info / odds stored separately per day (JSON)
- [x] Odds status success / pending / failed with JST times; previous
      success kept on failure; null ≠ 0; pre-deadline decision snapshot
- [x] Board: deadline → stadium code → race number; races without odds
      kept; candidate / pass / undecidable; break-even odds; stale-odds
      warning at viewing time; GitHub Pages + job summary
- [x] Closing odds of past days (next-day JSON) for verification
- [x] Verification per stadium: candidates, closing-odds rule check,
      model vs market log-loss, calibration table
- [x] Tests (pytest) for probabilities, odds parsing, decisions, board
      order, odds status handling, source mapping, verification rules
- [x] Backfill of past days from walk-forward backtest probabilities
      (manual workflow). First result, 2026-10-19..11-17, 552 races:
      market log-loss lower than the model at all 3 stadiums; rule with
      closing odds: 671 tickets, mean expected return 171%, realised
      ROI 74%

#### 5-2 Odds source (open)
- [x] Official site: blocked for scripted clients (403) → not used
- [x] Free JSON with odds found, but previous days only → verification
- [ ] Ask the paid boat-race DB API vendor: live trio odds?
      update interval? automated use / terms? price for this use?
- [ ] If no permitted live source: decide between (a) manual decisions
      with break-even odds (current state) and (b) a small manual odds
      input (e.g. a JSON/CSV the user edits, or a form on the board)
- [ ] When a source is chosen: add a fetcher behind the existing odds
      interface (`fetch_trio_odds` → same status / storage) and set its
      secret; check request volume (≤ 40 requests per run by default)

#### 5-3 Operation checks after merge
- [ ] Enable GitHub Pages (Source: GitHub Actions)
- [ ] First manual run of "BoatRace Predictor" (creates `models/` and
      the first prediction file); confirm it finishes before ~08:45 JST
      on scheduled days despite start delays
- [ ] Confirm the race-day workflow commits only when data changed
- [ ] Confirm CI (ruff with `ruff.toml`, pytest) passes on GitHub
- [ ] Run "BoatRace Backtest" once and confirm `calibrate_trio.py`
      refits `trio_calibration.json`

#### 5-4 Verification build-up (needs data, ~1-3 months)
- [ ] Accumulate closing odds + results: aim for ≥ 1,000 races per
      stadium before reading per-stadium numbers
- [ ] Track calibration (predicted vs observed per probability band)
      on post-change data; refit if it drifts
- [ ] Compare model vs market log-loss; the EV rule only makes sense
      where the model adds information the market does not price in
- [ ] Back-test the EV rule on 2026 data with closing odds from the
      next-day JSON (calibration fitted only on earlier data to avoid
      look-ahead), per stadium; adjust `ev_config.json` only from
      out-of-sample results

#### Result of the long-range test (2026-11-19)
`ev_backtest.py`, 2026-01-01..11-17, 6,250 races, closing odds,
calibration fitted only on earlier races:
- Market log-loss lower than the model at every stadium and in every
  month (2.24 vs 2.36).
- Rule (EV ≥ 1.2, p ≥ 0.05): 8,100 tickets, ROI 70% (95% CI 62–78%),
  mean expected return 177%. Higher thresholds are worse.
- Conclusion: the current model has no edge over the market; the EV rule
  is not usable for betting. Paying for live odds is not justified yet.
- Live model (exhibition, tilt, exhibition ST, wind, wave) on the same
  5,010 races: log-loss 2.361 → 2.348 vs market 2.246; ROI 74% → 76%.
  Race-day information closes only ~10% of the gap to the market.

Next steps implied by this result:
- [ ] Market-anchored probabilities: start from closing-odds implied
      probabilities and test whether the model adds information
      (e.g. a blend or a residual model), out of sample
- [ ] Fix the calibration bias: low-probability trios over-estimated,
      high-probability trios under-estimated
- [x] Race-day features not used before (exhibition entry course,
      parts / propeller changes, weight adjustment, wind components):
      tested in `method_comparison.py` → no gain (D 2.349 vs C 2.348)
- [x] Method comparison, same races 2026-04..11 (4,275): market 2.249 <
      live 2.348 ≈ live+ 2.349 < morning 2.365; market + model pool
      2.249 (= market). No method beats the closing odds.
- [x] Strategy comparison out of sample (strategy_comparison.py): no
      strategy above ~77% on 2026; longshots worst (favourite-longshot
      bias); selected filters regress on the test period
- [ ] Track the current optimal_strategy.json cell on new races only
      (145% / 143% on 61 / 64 races, chosen post hoc; needs several
      hundred new races before it means anything)
- [ ] Re-run the comparison in Actions with the real STADIUM_PREF_MAP
      and again after more 2026 race-day data has accumulated
- [ ] Re-run `ev_backtest.py` after each change; only a CI above 100%
      on held-out months would justify live odds

#### 5-5 Later (only if 5-4 justifies it)
- [ ] Direct trio-probability model (instead of Harville from P(win)),
      validated against the current method
- [ ] Exhibition-based (live) update in the race-day run — still
      evaluation-only, see Phase 3/4
- [ ] Use market-implied probabilities as a feature or as a prior

### Non-goals
- Betting automation (manual, small-stakes verification only)
- Kelly-style stake sizing (edge estimate too uncertain to justify)

## Honest status

Best grid-search cell: ROI 115.4% on 167 races — small sample,
selected post-hoc, treated as optimistic. Unfiltered strategies all
sit at 54–80% ROI against a ~25% takeout. Exhibition data adds +2 to
+10pt ROI across strategies but does not clear break-even. The purpose
of this project is measurement, not profit.
