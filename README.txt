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
Added 2026-11. Goal: combine the night prediction with odds, show
expected-return based candidates for the target stadiums on one list
sorted by deadline, and verify the result per stadium. The existing
models, backtest and forward test (prediction_history.csv) are kept.

  Daily flow (JST)
    00:37  BoatRace Predictor
           fetch results -> train (~20 s) -> save models -> predict the
           day's races (trio probabilities) -> closing odds of past days
           -> verification -> board (no odds yet)
    06:41  BoatRace Race Day (morning update)
    08:07-21:37 every 30 min  BoatRace Race Day
           entrants / deadlines / exhibition -> re-predict only races
           that were missing or changed (saved models, ~4 s, no
           training) -> odds (if a source is configured) -> expected
           return -> decision -> board
    GitHub Actions start times are not guaranteed: delays of several
    hours were observed for the former 03:00 JST schedule. Runs are
    therefore early and frequent, at off-peak minutes, and the board
    always shows when odds were fetched.

  Modules
  boatrace_sources.py      Data-source access. Entry lists, deadlines,
                           exhibition status and results come from the
                           consolidated v1 day file (first published
                           around 00:15 JST on race day, then updated
                           about every 10 min). The v2 programs file
                           fills races missing in v1 (on 2026-11-18,
                           v1 lacked 2 of 12 races at one stadium).
                           v1 -> existing column mapping was checked
                           against v2 for the same day: all populated
                           values matched (unknown average ST: v2 null,
                           v1 0 -> stored as missing).
                           Also: optional live trio-odds page parser
                           (ODDS_BASE_URL) and http retry helper.

  trio_prob.py             Probabilities for all 20 trio combinations.
                           Harville ordering model on P(win):
                             P(i,j,k in order) = p_i * p_j/(1-p_i)
                                                 * p_k/(1-p_i-p_j)
                           summed over the 6 orders of a trio. This is
                           NOT the product of per-boat top-3
                           probabilities; the 20 values sum to 1.
                           A scratched boat is removed and the rest
                           re-normalised (conditional distribution).

  calibrate_trio.py        Raw Harville probabilities are over-confident
                           for favourites (the models are trained with
                           class_weight='balanced'). An isotonic map is
                           fitted on the walk-forward probabilities in
                           backtest_result.csv and stored in
                           trio_calibration.json together with a
                           time-split check (oldest 80% fit, newest 20%
                           test). Result at creation (test period
                           2026-05-02 .. 2026-11-17, 3,857 races):
                             log-loss 2.400 -> 2.376
                             predicted 0.37 -> observed 0.29 (raw)
                             predicted 0.33 -> observed 0.36 (calibrated)
                           Refitted by the backtest workflow.

  race_day.py              Light race-day update (see flow above).
                           Re-predictions are NOT written to
                           prediction_history.csv, so the forward test
                           keeps the night prediction only.

  ev_judge.py              expected return = calibrated probability x
                           odds (1.20 = 120%). Decision rule below.
  board.py                 Board: one list for all target stadiums,
                           sorted by deadline, then stadium code, then
                           race number; races without odds stay listed.
                           HTML for GitHub Pages (phone layout as cards,
                           light/dark) and Markdown for the job summary.

  closing_odds.py          Closing odds of past race days
                           from a day file that is published the next
                           morning (CLOSING_ODDS_BASE_URL). Verification
                           only: it cannot be used before the deadline.
                           Checked on 2026-11-17: for 129 of 132 races
                           the winning trio's odds x 100 equalled the
                           trio payout, i.e. these are closing odds.

  verify_trio.py           data/verification/summary.{json,md}, per
                           stadium and total:
                           - candidates (last pre-deadline decision):
                             hit rate, ROI, mean expected return
                           - closing-odds rule check (reference only):
                             the same rule applied with closing odds
                           - model vs market log-loss (market = closing
                             odds, inverted and normalised)
                           - probability calibration table

  backfill_verification.py Fills past race days for verification without
                           training: walk-forward probabilities from
                           backtest_result.csv -> prediction files
                           (marked "backfill", not in
                           prediction_history.csv) + closing odds ->
                           verification. The calibration used is refitted
                           only on races before the range. Manual
                           workflow: "BoatRace Backfill Verification".

  ev_backtest.py           Out-of-sample test of the decision rule over a
                           long range (default from 2026-01-01) with
                           closing odds; calibration fitted only on
                           earlier races; per stadium / month /
                           threshold, bootstrap 95% CI for ROI. Writes
                           data/verification/ev_backtest.{json,md}.

  method_comparison.py     Same-race comparison of methods, monthly
                           walk-forward from 2026-01 (scored from
                           2026-04): A market, B morning model, C live
                           model, D live + unused race-day items
                           (exhibition entry course, parts / propeller
                           changes, weight adjustment, head/tail and
                           cross wind), E market + model pool. Writes
                           data/verification/method_comparison.{json,md}.

  Decision (ev_config.json; all thresholds are configurable)
    Candidate     at least one combination with expected
                  return >= ev_min (1.2) AND probability >=
                  prob_min (0.05), odds fetched within
                  stale_minutes (15) at decision time; at most
                  max_candidates_per_race (3) combinations
    Pass          otherwise
    Undecidable   no prediction, no odds, or odds too old
    A high expected return alone never makes a candidate (prob_min).
    Break-even odds = ev_min / probability is shown for
    every combination with probability >= prob_min, so the rule can be
    applied by hand with the odds shown in a betting app.
    The page also warns when the odds shown are older than
    stale_minutes at viewing time. No automatic betting.

  Odds status (data/odds/<date>.json, per race)
    success   last fetch succeeded (odds_fetched_at, JST)
    pending   not fetched yet (or no odds source configured)
    failed    last attempt failed (last_failure_at, last_error); the
              previous successful odds are kept and shown with their
              own fetch time, never as current odds
    Missing odds are null, never 0. pre_close keeps the last decision
    made with odds fetched before the deadline; closing keeps the
    closing odds from closing_odds.py.

Odds sources (status 2026-11-19)
--------------------------------
  Live (pre-deadline) trio odds: NOT available yet.
  - Official site: no API. Its trio odds page answered 403 (Access
    Denied, bot protection) to scripted requests; the pipeline does
    not try to work around that. ODDS_BASE_URL is therefore unset and
    every race shows odds as pending.
  - Paid boat-race database API (from 3,300 JPY / month for
    personal use): the product page does not mention odds; to be
    confirmed with the vendor (odds, trio, pre-deadline, automated use).
  - Free JSON day file with odds: previous days only, published
    the next morning -> used for verification (closing odds), not for
    decisions.
  Until a permitted live source exists, decisions are manual using the
  board's break-even odds.

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
  data/backfill_attempts.json  Downloads that returned no data:
                           non-race (date, stadium) pairs and empty
                           backfill dates (not retried every run).
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
     ODDS_BASE_URL        Base URL of a live trio-odds page source.
                          Leave unset unless the source's terms allow
                          automated access; without it no odds are
                          fetched and every race shows odds as pending.
     CLOSING_ODDS_BASE_URL  Base of the next-day JSON with closing odds
                          (verification only). Unset -> step skipped.
     PROGRAMS_V1_URL      Override for the v1 day-file base
                          (default: {API_BASE_URL}/api/v1).

   For the race board page: Settings > Pages > Source = "GitHub Actions".

2. Enable write access for workflows
   (Settings > Actions > General > Workflow permissions
    > "Read and write permissions").

3. Run the "BoatRace Predictor" workflow manually once.
   The first run downloads the full history and may take ~40 minutes;
   exhibition-data backfill can extend this further. Non-race
   (date, stadium) pairs and backfill dates that return no data are
   recorded in data/backfill_attempts.json and are not requested again
   (except the last 14 days), so later runs fetch in about a minute.

4. Run the "BoatRace Backtest" workflow to generate
   optimal_strategy.json. Training four model sets per day in
   walk-forward mode takes roughly 3-4 hours.

5. The daily schedule then runs automatically. Recommended tickets
   appear in the workflow artifact (prediction_result.txt). The race
   board (all target stadiums by deadline, expected return, decision)
   is published to GitHub Pages and shown in each run's job summary.

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
- Dates are Japan time (JST). Until 2026-11 the scripts used the
  runner's UTC date, so the 03:00 JST run predicted the previous JST
  day (races already finished). Forward-test rows before and after the
  fix are not strictly comparable.
- The target stadiums do not race every day. Until 2026-11 every
  (date, stadium) pair without races (~900 since 2024) counted as
  "missing" and was re-requested on every run with a 1.5 s pause, which
  made the fetch step take ~30 min. Such pairs, and backfill dates that
  returned no data, are now recorded in data/backfill_attempts.json and
  skipped (the last 14 days are still retried). The fetch step now takes
  about 1 minute; training plus prediction about 20 seconds.
- The race-day expected return is only as good as the probabilities.
  Out-of-sample test 2026-01-01..11-17 (ev_backtest.py, 6,250 races,
  closing odds): the market had a lower log-loss than the model at all
  3 stadiums and in all 11 months (2.24 vs 2.36). The rule picked 8,100
  tickets in 75% of races with a mean expected return of 177% and
  realised 70% ROI (95% CI 62-78%), i.e. no better than buying at
  random at market odds (~75%). Raising the threshold made it worse
  (>= 2.0: 65%, >= 3.0: 38%). Large expected returns from this model
  mark its disagreements with the market, i.e. model error, not value.
  Do not bet on the rule as it stands.
  Race-day information does not close the gap: on the same 5,010 races
  with exhibition data, the live model (morning features + exhibition
  time / rank, tilt, exhibition ST, wind, wave) improved log-loss only
  from 2.361 to 2.348 against the market's 2.246, and the rule's ROI
  from 74% to 76% (`ev_backtest.py --live`). Still missing even from the
  live model: parts / propeller changes, the exhibition entry course,
  wind direction, weight adjustment.
  Method comparison 2026-04..11-18 (4,275 races, method_comparison.py):
  log-loss A market 2.249, B 2.365, C 2.348, D 2.349, E 2.249; EV-rule
  ROI B/C/D 77-78% (CIs ~68-87%). The newly added race-day items did not
  help (together <1.5% of model D's gain). Pooling with the market gave
  the model a weight of 0.25 but no overall gain (E = A), i.e. no
  information beyond the closing odds was detected. Note: race-day
  items exist only from 2026-01, and the local run had no
  STADIUM_PREF_MAP ("local racer" feature empty for B-D). Treat candidates as
  research output until verification over many races says otherwise.

Acknowledgements
----------------
Developed with AI assistance (Claude by Anthropic).
Design decisions, verification and operation by the repository owner.

License / Disclaimer
--------------------
Released under the MIT License (see LICENSE).
No warranty of any kind. The authors accept no liability for financial
losses incurred by using this software.
