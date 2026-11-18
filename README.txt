Boat Race Prediction System
===========================

This repository was built as a personal research / verification project
to study whether machine learning can extract predictive value from
publicly available boat race data. It is published for portfolio and
educational purposes.

An automated machine-learning pipeline that fetches public boat race
data daily, trains gradient-boosting models, and outputs recommended
trio (3-boat combination) tickets based on a backtested strategy.

This project is for educational and research purposes. It analyses a
pari-mutuel betting market with a ~25% takeout rate; no profit is
guaranteed and past backtest performance does not predict future
results. Bet responsibly and only with money you can afford to lose.

Architecture
------------
  fetch_boatrace.py        Daily incremental data fetcher.
                           Downloads confirmed results, program data and
                           exhibition-run data, appends to
                           boatrace_results.csv, and fills actual
                           outcomes into pending predictions.

  predict_boatrace.py      Daily prediction runner ("morning model").
                           Trains two LightGBM models (P(win), P(top-3))
                           using only information available on the
                           morning of race day, applies the strategy in
                           optimal_strategy.json, and logs tickets to
                           prediction_history.csv.

  predict_boatrace_lib.py  Shared feature engineering and ticket logic.
                           Defines two feature sets:
                             FEATURE_COLS       morning (no exhibition)
                             FEATURE_COLS_LIVE  + exhibition-run data
                           All features are computed strictly from
                           information available before each race
                           (no look-ahead leakage).

  backtest_boatrace.py     Walk-forward backtest. Retrains both model
                           sets daily, compares 6 ticket strategies
                           under morning vs live features against an
                           always-[1,2,3] baseline, and stores the best
                           morning configuration.

Race-day pipeline (night prediction -> odds -> board)
-----------------------------------------------------
  boatrace_sources.py      Data-source access. Entry lists, deadlines,
                           exhibition status and results come from the
                           consolidated v1 day file (published around
                           00:15 JST on race day, updated ~10 min);
                           the v2 programs file fills any race v1 lacks.
                           Optional trio-odds fetcher (ODDS_BASE_URL).

  trio_prob.py             Trio probabilities for all 20 combinations
                           (Harville ordering model on P(win); NOT the
                           product of per-boat top-3 probabilities),
                           calibrated with trio_calibration.json.

  calibrate_trio.py        Fits that calibration from the walk-forward
                           probabilities in backtest_result.csv (time
                           split check: oldest 80% fit / newest 20% test).

  race_day.py              Light race-day update, no training: entry
                           changes, deadlines, exhibition status,
                           re-prediction with saved models where needed,
                           odds (if configured), expected return,
                           decision, race board (site/index.html and
                           the Actions job summary).

  ev_judge.py / board.py   Expected return = probability x odds.
                           Decision rules and thresholds: ev_config.json.

  verify_trio.py           Per-stadium verification: candidate hit rate
                           and ROI, expected vs realised return,
                           probability calibration, model vs closing-odds
                           market log-loss.

  Workflows
    BoatRace Predictor   00:37 JST  results -> training -> prediction ->
                                    verification -> board (no odds)
    BoatRace Race Day    06:41 JST and every 30 min 08:07-21:37 JST
    Scheduled start times are not guaranteed (multi-hour delays observed);
    the board always shows when odds were fetched.

  Decision (ev_config.json)
    購入候補  expected return >= ev_min (1.2) AND probability >= prob_min
              (0.05), odds fetched within stale_minutes (15)
    見送り    otherwise
    判定不可  no prediction / no odds / odds too old
    The board also shows the break-even ("必要オッズ") per combination,
    so the rule can be applied by hand when no odds source is configured.
    No automatic betting. Final decisions are the user's.

Data files (committed by workflows)
-----------------------------------
  boatrace_results.csv     Accumulated race results + program features
                           + exhibition data where available.
  prediction_history.csv   Every prediction with its later outcome
                           (untouched forward test).
  optimal_strategy.json    Strategy selected by the latest backtest.
  trio_calibration.json    Trio-probability calibration + its check.
  data/predictions/        Per-day trio predictions (JSON, per race).
  data/raceinfo/           Latest deadline / entrants / exhibition.
  data/odds/               Trio odds with status (success / pending /
                           failed), last success / failure time (JST);
                           a failed fetch never deletes earlier odds.
  data/verification/       summary.json / summary.md.
  data/backfill_attempts.json  Dates whose backfill returned no data
                           (not retried every run).
  models/                  Boosters of the last training run (+ id).

Setup
-----
1. Create the following repository secrets
   (Settings > Secrets and variables > Actions):

     API_BASE_URL         Base URL of the public data source.
     TARGET_STADIUM_IDS   Comma-separated stadium IDs, e.g. "01,02,03".
     STADIUM_PREF_MAP     Stadium-to-home-branch map, e.g. "01:10,02:20".
                          Used for the "local racer" feature.

   Optional:
     ODDS_BASE_URL        Base URL of a trio-odds page source. Leave
                          unset unless the source's terms allow
                          automated access; without it no odds are
                          fetched and every race shows "未取得".
     PROGRAMS_V1_URL      Override for the v1 day-file base
                          (default: {API_BASE_URL}/api/v1).

   For the race board page: Settings > Pages > Source = "GitHub Actions".

2. Enable write access for workflows
   (Settings > Actions > General > Workflow permissions
    > "Read and write permissions").

3. Run the "BoatRace Predictor" workflow manually once.
   The first run downloads the full history and may take ~40 minutes;
   exhibition-data backfill can extend this further.

4. Run the "BoatRace Backtest" workflow to generate
   optimal_strategy.json. Training four model sets per day in
   walk-forward mode takes roughly 3-4 hours.

5. The daily schedule then runs automatically. Recommended tickets
   appear in the workflow artifact (prediction_result.txt).

Method notes
------------
- The production ("morning") model uses only entry lists, official
  racer/motor statistics, lane statistics and within-meet form.
  Actual start timings are intentionally excluded (leakage).
- A parallel "live" feature set adds exhibition-run data to measure,
  via backtest, whether pre-race exhibition information carries value
  beyond what the market already prices in. It is evaluation-only
  until proven useful.
- Models are validated with time-series splits; the backtest is fully
  walk-forward (train on days < D, predict day D).
- Strategy selection is a grid search and therefore optimistic;
  prediction_history.csv provides an untouched forward test.

Acknowledgements
----------------
Developed with AI assistance (Claude by Anthropic).
Design decisions, verification and operation by the repository owner.

License / Disclaimer
--------------------
Released under the MIT License (see LICENSE).
No warranty of any kind. The authors accept no liability for financial
losses incurred by using this software.
