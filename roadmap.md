# Roadmap

Current phase: **forward validation** (strategy frozen, data accumulating).

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

### Race-day pipeline (added 2026-11)
- [x] Night prediction at 00:37 JST from the v1 day file (v2 fallback)
- [x] Saved models; race-day re-prediction without retraining
- [x] Calibrated trio probabilities (Harville + isotonic, time-split check)
- [x] Odds status model (success / pending / failed), JST timestamps,
      previous success kept on failure
- [x] Merged 3-stadium board sorted by deadline; expected return; decision
- [x] Per-stadium verification (hit rate, ROI, expected vs realised)
- [ ] Odds source with terms that allow automated access (the official
      site currently returns 403 to scripted clients)
- [ ] Live (exhibition) model in the race-day update — still
      evaluation-only, see Phase 3/4

### Non-goals
- Betting automation (manual, small-stakes verification only)
- Kelly-style stake sizing (edge estimate too uncertain to justify)

## Honest status

Best grid-search cell: ROI 115.4% on 167 races — small sample,
selected post-hoc, treated as optimistic. Unfiltered strategies all
sit at 54–80% ROI against a ~25% takeout. Exhibition data adds +2 to
+10pt ROI across strategies but does not clear break-even. The purpose
of this project is measurement, not profit.
