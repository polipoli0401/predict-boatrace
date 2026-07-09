Boat Race Prediction System
===========================

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

Data files (committed by workflows)
-----------------------------------
  boatrace_results.csv     Accumulated race results + program features
                           + exhibition data where available.
  prediction_history.csv   Every prediction with its later outcome
                           (untouched forward test).
  optimal_strategy.json    Strategy selected by the latest backtest.

Setup
-----
1. Create the following repository secrets
   (Settings > Secrets and variables > Actions):

     API_BASE_URL         Base URL of the public data source.
     TARGET_STADIUM_IDS   Comma-separated stadium IDs, e.g. "01,02,03".
     STADIUM_PREF_MAP     Stadium-to-home-branch map, e.g. "01:10,02:20".
                          Used for the "local racer" feature.

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

License / Disclaimer
--------------------
No warranty of any kind. The authors accept no liability for financial
losses incurred by using this software.
