"""Closing trio odds (締切時オッズ) for past race days, for verification.

Source: a JSON day file that includes odds for the PREVIOUS days only
(published the next morning JST), set by the CLOSING_ODDS_BASE_URL
secret. It cannot be used for pre-deadline decisions; it is used to
  - compare the model with the market (closing-odds implied probability),
  - measure the expected-return rule after the fact with closing odds,
  - check expected vs realised return.

Checked on 2026-11-17 (11 stadiums, 132 races): for 129 races the trio
odds of the winning combination x 100 equalled the trio payout, i.e. the
values are closing odds. (The remaining 3 involved refunds/adjustments.)

For each date that has data/predictions/<date>.json, within the last
LOOKBACK_DAYS days and without closing odds yet, the day file is fetched
once and the target stadiums' trio odds are stored under "closing" in
data/odds/<date>.json. Live odds fields ("odds", "pre_close", status)
are never modified.

Usage: python closing_odds.py
"""
import glob
import os
from datetime import date, timedelta

from boatrace_sources import http_get, iso_jst, race_key, target_stadium_ids, today_jst
from race_store import PRED_DIR, odds_path, read_json, write_json_if_changed

LOOKBACK_DAYS = 14


def _base():
    b = os.environ.get("CLOSING_ODDS_BASE_URL")
    return b.rstrip("/") if b else None


def parse_trio_closing(day_doc, stadiums):
    """{race_key: {"1-2-3": 4.2 or None, ...}} for target stadiums.
    Nested layout: odds.trio[A][B][C] with A < B < C (string keys)."""
    out = {}
    st = ((day_doc or {}).get("programs") or {}).get("stadiums") or {}
    for sk, sv in st.items():
        sid = str(sk).zfill(2)
        if sid not in stadiums:
            continue
        for rk, race in ((sv or {}).get("races") or {}).items():
            trio = ((race or {}).get("odds") or {}).get("trio")
            if not isinstance(trio, dict):
                continue
            combos = {}
            for a, bs in trio.items():
                for b, cs in (bs or {}).items():
                    for c, v in (cs or {}).items():
                        key = "-".join(sorted([a, b, c], key=int))
                        combos[key] = float(v) if isinstance(v, (int, float)) else None
            if combos and any(v is not None for v in combos.values()):
                out[race_key(sid, int(rk))] = combos
    return out


def dates_needing_closing(today):
    since = today - timedelta(days=LOOKBACK_DAYS)
    out = []
    for path in sorted(glob.glob(os.path.join(PRED_DIR, "*.json"))):
        d = date.fromisoformat(os.path.basename(path)[:-5])
        if not (since <= d < today):
            continue
        races = (read_json(path) or {}).get("races", {})
        odds = (read_json(odds_path(d)) or {}).get("races", {})
        if any(not (odds.get(k) or {}).get("closing") for k in races):
            out.append(d)
    return out


def store_closing(day, closing, preds_doc):
    doc = read_json(odds_path(day)) or {"date": day.isoformat(), "races": {}}
    races = doc.setdefault("races", {})
    fetched = iso_jst()
    n = 0
    for key in (preds_doc or {}).get("races", {}):
        combos = closing.get(key)
        if not combos:
            continue
        sid, rno = key.split("-")
        entry = races.setdefault(key, {"stadium_id": sid,
                                       "race_number": int(rno),
                                       "status": "pending", "odds": None,
                                       "odds_fetched_at": None})
        entry["closing"] = {
            "fetched_at": fetched,
            "odds": [{"combination": k, "value": v}
                     for k, v in sorted(combos.items())],
        }
        n += 1
    doc["updated_at"] = fetched
    write_json_if_changed(odds_path(day), doc)
    return n


def main():
    base = _base()
    if not base:
        print("Closing odds: CLOSING_ODDS_BASE_URL not set; skipped")
        return
    stadiums = target_stadium_ids()
    for day in dates_needing_closing(today_jst()):
        resp, err = http_get(f"{base}/{day.year}/{day.strftime('%Y%m%d')}.json")
        if resp is None or resp.status_code != 200:
            print(f"Closing odds {day}: not available ({err})")
            continue
        try:
            closing = parse_trio_closing(resp.json(), stadiums)
        except ValueError:
            print(f"Closing odds {day}: invalid JSON")
            continue
        n = store_closing(day, closing, read_json(os.path.join(
            PRED_DIR, f"{day.isoformat()}.json")))
        print(f"Closing odds {day}: stored for {n} races")


if __name__ == "__main__":
    main()
