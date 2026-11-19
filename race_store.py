"""File layout and JSON persistence for the race-day pipeline.

  data/predictions/YYYY-MM-DD.json  night prediction (+ morning updates)
  data/raceinfo/YYYY-MM-DD.json     latest deadline / entrants / exhibition
  data/odds/YYYY-MM-DD.json         trio odds per race with fetch status
  models/win.txt, models/top3.txt   LightGBM boosters from the last
  models/meta.json                  training run (+ identification)

Prediction data and odds data are kept in separate files. Racer names
are never written to these files (registration numbers only).
"""
import hashlib
import json
import os
import tempfile

DATA_DIR = "data"
MODEL_DIR = "models"
PRED_DIR = os.path.join(DATA_DIR, "predictions")
ODDS_DIR = os.path.join(DATA_DIR, "odds")
INFO_DIR = os.path.join(DATA_DIR, "raceinfo")
VERIFY_DIR = os.path.join(DATA_DIR, "verification")


def _path(directory, day):
    return os.path.join(directory, f"{day.isoformat()}.json")


def pred_path(day):
    return _path(PRED_DIR, day)


def odds_path(day):
    return _path(ODDS_DIR, day)


def info_path(day):
    return _path(INFO_DIR, day)


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    """Atomic write so a failed run never leaves a truncated file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".",
                               suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")
    os.replace(tmp, path)


def write_json_if_changed(path, obj, ignore=("updated_at",)):
    """Write only when something other than the `ignore` keys changed,
    so scheduled runs without new information create no commit."""
    old = read_json(path)
    if old is not None:
        strip = lambda d: {k: v for k, v in d.items() if k not in ignore}  # noqa: E731
        if strip(old) == strip(json.loads(json.dumps(obj, ensure_ascii=False))):
            return False
    write_json(path, obj)
    return True


# ------------------------------------------------------------
# models
# ------------------------------------------------------------
def _file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()[:12]


def save_models(m_win, m_top3, meta):
    """Persist the two trained LGBMClassifier boosters for inference-only
    re-prediction on race day. Returns the model identification dict."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    pw = os.path.join(MODEL_DIR, "win.txt")
    p3 = os.path.join(MODEL_DIR, "top3.txt")
    m_win.booster_.save_model(pw)
    m_top3.booster_.save_model(p3)
    ident = dict(meta)
    ident["model_id"] = f"{_file_hash(pw)}-{_file_hash(p3)}"
    write_json(os.path.join(MODEL_DIR, "meta.json"), ident)
    return ident


def load_models():
    """Returns (booster_win, booster_top3, meta) or (None, None, None)."""
    pw = os.path.join(MODEL_DIR, "win.txt")
    p3 = os.path.join(MODEL_DIR, "top3.txt")
    meta = read_json(os.path.join(MODEL_DIR, "meta.json"))
    if not (os.path.exists(pw) and os.path.exists(p3) and meta):
        return None, None, None
    import lightgbm as lgb
    return (lgb.Booster(model_file=pw), lgb.Booster(model_file=p3), meta)


# ------------------------------------------------------------
# prediction records
# ------------------------------------------------------------
def build_race_prediction(day, stadium_id, race_number, closed_at,
                          race_df, trio_raw, trio_cal, tickets,
                          predicted_at, model_ident, entry_source,
                          kind="night"):
    """One race's prediction record. race_df has boat_number,
    racer_number, racer_class, p1, p3."""
    from tracked_strategies import tracked_tickets  # lazy: needs env config

    rd = race_df.sort_values("boat_number")
    ranked = sorted(trio_cal.items(), key=lambda kv: -kv[1])
    return {
        "date": day.isoformat(),
        "stadium_id": str(stadium_id).zfill(2),
        "race_number": int(race_number),
        "closed_at": closed_at,
        "entry_source": entry_source,
        "entries": [{"boat": int(r.boat_number),
                     "racer_number": (int(r.racer_number)
                                      if r.racer_number == r.racer_number
                                      else None),
                     "racer_class": (int(r.racer_class)
                                     if r.racer_class == r.racer_class
                                     else None)}
                    for r in rd.itertuples()],
        "boats": [{"boat": int(r.boat_number),
                   "p_win": round(float(r.p1), 5),
                   "p_top3": round(float(r.p3), 5)}
                  for r in rd.itertuples()],
        "predictions": [{"combination": k,
                         "probability": round(v, 5),
                         "raw_probability": round(trio_raw.get(k, 0.0), 5)}
                        for k, v in ranked],
        "strategy_tickets": ["-".join(map(str, sorted(t))) for t in tickets],
        # pre-registered strategies (strategies.json), fixed before the race
        "tracked_tickets": tracked_tickets(stadium_id, rd[["boat_number", "p1", "p3"]]),
        "prediction_kind": kind,
        "predicted_at": predicted_at,
        "model_id": model_ident.get("model_id") if model_ident else None,
    }


def merge_predictions(day, races, model_ident, calibration, generated_at):
    """Insert/replace race records in the day's prediction file,
    keeping races that are not in `races` untouched."""
    path = pred_path(day)
    doc = read_json(path, default=None) or {"date": day.isoformat(),
                                            "races": {}}
    for r in races:
        key = f"{r['stadium_id']}-{r['race_number']:02d}"
        doc["races"][key] = r
    doc["updated_at"] = generated_at
    doc["model"] = {k: model_ident.get(k) for k in
                    ("model_id", "trained_at", "train_rows",
                     "train_last_date", "train_days")} if model_ident else None
    doc["calibration"] = ({"method": calibration.get("method"),
                           "created_at": calibration.get("created_at"),
                           "fit_period": calibration.get("fit_period")}
                          if calibration else None)
    doc["races"] = dict(sorted(doc["races"].items()))
    write_json(path, doc)
    return doc
