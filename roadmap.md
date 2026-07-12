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

### Non-goals
- Betting automation (manual, small-stakes verification only)
- Real-time odds integration (out of scope for this data source)
- Kelly-style stake sizing (edge estimate too uncertain to justify)

## Honest status

Best grid-search cell: ROI 115.4% on 167 races — small sample,
selected post-hoc, treated as optimistic. Unfiltered strategies all
sit at 54–80% ROI against a ~25% takeout. Exhibition data adds +2 to
+10pt ROI across strategies but does not clear break-even. The purpose
of this project is measurement, not profit.
