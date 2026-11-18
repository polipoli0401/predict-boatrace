"""Data-source access shared by the prediction and race-day scripts.

Sources (all base URLs come from environment variables / secrets):
  API_BASE_URL      : existing secret. v2 per-kind files
                      ({API_BASE_URL}/programs/v2/...) are used as before.
  PROGRAMS_V1_URL   : optional. Base of the consolidated v1 day file
                      (entry list + deadline + exhibition + result).
                      Defaults to {API_BASE_URL}/api/v1.
  ODDS_BASE_URL     : secret. Base of the official race pages that
                      serve the trio (3-renpuku) odds table.
  TARGET_STADIUM_IDS: existing secret (comma-separated stadium IDs).

Nothing in this module logs URLs or secret values.
"""
import os
import re
import time
from datetime import date, datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

import pandas as pd
import requests

JST = ZoneInfo("Asia/Tokyo")

STADIUM_NAMES = {
    "01": "Kiryu", "02": "Toda", "03": "Edogawa", "04": "Heiwajima",
    "05": "Tamagawa", "06": "Hamanako", "07": "Gamagori", "08": "Tokoname",
    "09": "Tsu", "10": "Mikuni", "11": "Biwako", "12": "Suminoe",
    "13": "Amagasaki", "14": "Naruto", "15": "Marugame", "16": "Kojima",
    "17": "Miyajima", "18": "Tokuyama", "19": "Shimonoseki", "20": "Wakamatsu",
    "21": "Ashiya", "22": "Fukuoka", "23": "Karatsu", "24": "Omura",
}

REQUEST_TIMEOUT = 20
USER_AGENT = "predict-boatrace (research; low-frequency polling)"


# ------------------------------------------------------------
# configuration
# ------------------------------------------------------------
def target_stadium_ids():
    ids = [s.strip().zfill(2)
           for s in os.environ.get("TARGET_STADIUM_IDS", "").split(",")
           if s.strip()]
    if not ids:
        raise RuntimeError("TARGET_STADIUM_IDS is not set.")
    return ids


def _api_base():
    base = os.environ.get("API_BASE_URL")
    return base.rstrip("/") if base else None


def _v1_base():
    v1 = os.environ.get("PROGRAMS_V1_URL")
    if v1:
        return v1.rstrip("/")
    base = _api_base()
    return f"{base}/api/v1" if base else None


def _odds_base():
    base = os.environ.get("ODDS_BASE_URL")
    return base.rstrip("/") if base else None


def odds_source_configured():
    return bool(_odds_base())


def now_jst():
    return datetime.now(JST)


def today_jst():
    override = os.environ.get("TARGET_DATE")
    if override:
        return date.fromisoformat(override)
    return now_jst().date()


def iso_jst(dt=None):
    return (dt or now_jst()).astimezone(JST).isoformat(timespec="seconds")


def race_key(stadium_id, race_number):
    return f"{str(stadium_id).zfill(2)}-{int(race_number):02d}"


# ------------------------------------------------------------
# HTTP with retry
# ------------------------------------------------------------
def http_get(url, retries=3, backoff=2.0, session=None):
    """GET with retry. Returns (response or None, error message or None).
    A 404 is returned as-is (not retried): it means 'not published'."""
    sess = session or requests
    last_err = None
    for i in range(retries):
        try:
            resp = sess.get(url, timeout=REQUEST_TIMEOUT,
                            headers={"User-Agent": USER_AGENT})
            if resp.status_code == 404:
                return resp, "not published (404)"
            if resp.status_code >= 500 or resp.status_code == 429:
                last_err = f"HTTP {resp.status_code}"
            else:
                resp.raise_for_status()
                return resp, None
        except requests.RequestException as e:
            last_err = type(e).__name__
        if i < retries - 1:
            time.sleep(backoff * (i + 1))
    return None, last_err or "request failed"


def _get_json(url):
    resp, err = http_get(url)
    if resp is None or resp.status_code != 200:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


# ------------------------------------------------------------
# entry lists (programs)
# ------------------------------------------------------------
def _subtitle_flags(subtitle):
    # Source strings are Japanese: "final" / "semi-final" race titles.
    s = str(subtitle or "")
    return (1 if "優勝" in s and "準優勝" not in s else 0,
            1 if "準優勝" in s else 0)


def fetch_v2_programs(day):
    base = _api_base()
    if not base:
        return None
    return _get_json(f"{base}/programs/v2/{day.year}/"
                     f"{day.strftime('%Y%m%d')}.json")


def fetch_v1_day(day):
    base = _v1_base()
    if not base:
        return None
    return _get_json(f"{base}/{day.year}/{day.strftime('%Y%m%d')}.json")


def _records_from_v2(data, day, stadiums):
    """Same columns as the original predict_boatrace.fetch_today_programs."""
    records, meta = [], {}
    for race in (data or {}).get("programs", []):
        sid = str(race.get("race_stadium_number", "")).zfill(2)
        if sid not in stadiums:
            continue
        rno = int(race.get("race_number"))
        is_final, is_semi = _subtitle_flags(race.get("race_subtitle"))
        boats = race.get("boats", {})
        rows = []
        for boat in (boats.values() if isinstance(boats, dict) else boats):
            rows.append({
                "race_date": day.isoformat(), "stadium_id": sid,
                "race_number": rno,
                "boat_number": boat.get("racer_boat_number"),
                "racer_number": boat.get("racer_number"),
                "racer_name": boat.get("racer_name"),
                "official_national_win_rate": boat.get("racer_national_top_1_percent", 0),
                "official_national_top2_rate": boat.get("racer_national_top_2_percent", 0),
                "official_national_top3_rate": boat.get("racer_national_top_3_percent", 0),
                "official_local_win_rate": boat.get("racer_local_top_1_percent", 0),
                "official_local_top2_rate": boat.get("racer_local_top_2_percent", 0),
                "official_local_top3_rate": boat.get("racer_local_top_3_percent", 0),
                "official_avg_st": boat.get("racer_average_start_timing", 0),
                "racer_class": boat.get("racer_class_number", 4),
                "flying_count": boat.get("racer_flying_count", 0),
                "late_count": boat.get("racer_late_count", 0),
                "racer_age": boat.get("racer_age", 0),
                "racer_branch": boat.get("racer_branch_number", 0),
                "racer_weight": boat.get("racer_weight", 0),
                "motor_number": boat.get("racer_assigned_motor_number", 0),
                "motor_top2_rate": boat.get("racer_assigned_motor_top_2_percent", 0),
                "motor_top3_rate": boat.get("racer_assigned_motor_top_3_percent", 0),
                "boat_top2_rate": boat.get("racer_assigned_boat_top_2_percent", 0),
                "race_grade": race.get("race_grade_number", 5),
                "is_final": is_final, "is_semifinal": is_semi,
            })
        if rows:
            records.extend(rows)
            meta[(sid, rno)] = {"closed_at": race.get("race_closed_at"),
                                "source": "v2"}
    return records, meta


def _v1_races(data, stadiums):
    """Yield (sid, rno, race_dict) for target stadiums in a v1 day file."""
    st = ((data or {}).get("programs") or {}).get("stadiums") or {}
    for sk, sv in st.items():
        sid = str(sk).zfill(2)
        if sid not in stadiums:
            continue
        for rk, race in ((sv or {}).get("races") or {}).items():
            if isinstance(race, dict):
                yield sid, int(rk), race


def _records_from_v1(data, day, stadiums):
    """Map the v1 schema onto the existing (v2-derived) column names.
    Verified on 2026-11-18: every populated field matched v2 exactly,
    except an unknown average ST (v2 null / v1 0) -> mapped to None."""
    records, meta = [], {}
    for sid, rno, race in _v1_races(data, stadiums):
        racers = race.get("racers")
        if not race.get("closed_at") or not isinstance(racers, dict):
            continue  # entry list not captured for this race
        is_final, is_semi = _subtitle_flags(race.get("subtitle"))
        rows = []
        for ek, r in racers.items():
            if not isinstance(r, dict) or r.get("number") is None:
                continue
            avg_st = r.get("average_start_timing")
            rows.append({
                "race_date": day.isoformat(), "stadium_id": sid,
                "race_number": rno,
                "boat_number": int(r.get("entry_number") or ek),
                "racer_number": r.get("number"),
                "racer_name": r.get("name"),
                "official_national_win_rate": r.get("national_win_rate"),
                "official_national_top2_rate": r.get("national_top_2_percent"),
                "official_national_top3_rate": r.get("national_top_3_percent"),
                "official_local_win_rate": r.get("local_win_rate"),
                "official_local_top2_rate": r.get("local_top_2_percent"),
                "official_local_top3_rate": r.get("local_top_3_percent"),
                "official_avg_st": avg_st if avg_st else None,
                "racer_class": r.get("rank_number"),
                "flying_count": r.get("flying_count"),
                "late_count": r.get("late_count"),
                "racer_age": r.get("age"),
                "racer_branch": r.get("branch_number"),
                "racer_weight": r.get("weight"),
                "motor_number": r.get("motor_number"),
                "motor_top2_rate": r.get("motor_top_2_percent"),
                "motor_top3_rate": r.get("motor_top_3_percent"),
                "boat_top2_rate": r.get("boat_top_2_percent"),
                "race_grade": race.get("grade_number", 5),
                "is_final": is_final, "is_semifinal": is_semi,
            })
        if len(rows) >= 3:
            records.extend(rows)
            meta[(sid, rno)] = {"closed_at": race.get("closed_at"),
                                "source": "v1"}
    return records, meta


def load_day_programs(day, stadiums=None, v1_data=None, v2_data=None):
    """Entry lists for `day`: v1 first, v2 fills races v1 is missing.
    Returns (DataFrame, meta) where meta[(sid, rno)] = {closed_at, source}."""
    stadiums = stadiums or target_stadium_ids()
    if v1_data is None:
        v1_data = fetch_v1_day(day)
    rec1, meta1 = _records_from_v1(v1_data, day, stadiums)
    if v2_data is None:
        v2_data = fetch_v2_programs(day)
    rec2, meta2 = _records_from_v2(v2_data, day, stadiums)
    records = list(rec1)
    meta = dict(meta1)
    for key, m in meta2.items():
        if key not in meta:
            records.extend(r for r in rec2
                           if (r["stadium_id"], r["race_number"]) == key)
            meta[key] = m
    return pd.DataFrame(records), meta


def race_status_from_v1(data, stadiums):
    """Light per-race status from the v1 day file: deadline, entrants,
    exhibition availability and whether the race has a result."""
    out = {}
    for sid, rno, race in _v1_races(data, stadiums):
        racers = race.get("racers") if isinstance(race.get("racers"), dict) else {}
        entrants = {}
        for ek, r in racers.items():
            if isinstance(r, dict) and r.get("number") is not None:
                entrants[str(int(r.get("entry_number") or ek))] = int(r["number"])
        prev = race.get("preview") or {}
        prev_racers = prev.get("racers") if isinstance(prev.get("racers"), dict) else {}
        ex_boats = sorted(int(k) for k, r in prev_racers.items()
                          if isinstance(r, dict)
                          and r.get("exhibition_time") is not None)
        res = race.get("result") or {}
        res_racers = res.get("racers") if isinstance(res.get("racers"), dict) else {}
        places = [r.get("place_number") for r in res_racers.values()
                  if isinstance(r, dict)]
        finished = any(p is not None for p in places)
        out[race_key(sid, rno)] = {
            "stadium_id": sid, "race_number": rno,
            "closed_at": race.get("closed_at"),
            "entrants": entrants,
            "exhibition_boats": ex_boats,
            "finished": finished,
        }
    return out


# ------------------------------------------------------------
# official trio odds page
# ------------------------------------------------------------
class _TableParser(HTMLParser):
    """Collects every table as rows of cells (text, class, rowspan,
    colspan, is_header). Nested tables are kept separate."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self._stack, self._cell = [], [], None
        self.tab4_time = None
        self._in_tab4 = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self._stack.append({"rows": []})
        elif tag == "tr" and self._stack:
            self._stack[-1]["rows"].append([])
        elif tag in ("td", "th") and self._stack and self._stack[-1]["rows"]:
            self._cell = {"text": "", "cls": a.get("class") or "",
                          "rowspan": int(a.get("rowspan") or 1),
                          "colspan": int(a.get("colspan") or 1),
                          "th": tag == "th"}
        elif tag == "p" and "tab4_time" in (a.get("class") or ""):
            self._in_tab4 = True
            self.tab4_time = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._stack:
            self._cell["text"] = self._cell["text"].strip()
            self._stack[-1]["rows"][-1].append(self._cell)
            self._cell = None
        elif tag == "table" and self._stack:
            self.tables.append(self._stack.pop())
        elif tag == "p" and self._in_tab4:
            self._in_tab4 = False

    def handle_data(self, data):
        if self._cell is not None:
            self._cell["text"] += data
        if self._in_tab4:
            self.tab4_time += data


def _expand(rows):
    """Expand rowspan/colspan into a rectangular grid of cells."""
    grid, carry = [], {}
    for row in rows:
        line, col, queue = {}, 0, list(row)
        while queue or any(c >= col for c in carry):
            if col in carry:
                left, cell = carry[col]
                line[col] = cell
                if left <= 1:
                    del carry[col]
                else:
                    carry[col] = (left - 1, cell)
                col += 1
                continue
            if not queue:
                col += 1
                if col > 200:
                    break
                continue
            cell = queue.pop(0)
            for _ in range(cell["colspan"]):
                line[col] = cell
                if cell["rowspan"] > 1:
                    carry[col] = (cell["rowspan"] - 1, cell)
                col += 1
        grid.append([line.get(i) for i in range(max(line) + 1)] if line else [])
    return grid


def _to_float(text):
    t = (text or "").replace(",", "").strip()
    return float(t) if re.fullmatch(r"\d+(\.\d+)?", t) else None


def parse_trio_odds_html(html):
    """Parse the official trio odds table.
    Returns dict(odds={'1-2-3': 15.2 or None, ...}, label=str|None,
    is_final=bool) or raises ValueError on an unexpected layout."""
    p = _TableParser()
    p.feed(html)
    table = next((t for t in p.tables
                  if any("oddsPoint" in c["cls"]
                         for r in t["rows"] for c in r)), None)
    if table is None:
        raise ValueError("odds table not found")
    head = [r for r in table["rows"] if r and all(c["th"] for c in r)]
    body = [r for r in table["rows"] if r and not all(c["th"] for c in r)]
    if not head:
        raise ValueError("odds header not found")
    hline = _expand([head[0]])[0]
    groups = len(hline) // 3
    firsts = []
    for g in range(groups):
        cell = hline[3 * g]
        firsts.append(int(cell["text"]) if cell and cell["text"].isdigit() else None)
    odds = {}
    for line in _expand(body):
        for g in range(groups):
            if 3 * g + 2 >= len(line):
                continue
            c2, c3, co = line[3 * g], line[3 * g + 1], line[3 * g + 2]
            if not co or "oddsPoint" not in co["cls"]:
                continue
            try:
                combo = sorted([firsts[g], int(c2["text"]), int(c3["text"])])
            except (TypeError, ValueError, KeyError):
                raise ValueError("unexpected odds cell layout")
            odds["-".join(map(str, combo))] = _to_float(co["text"])
    if len(odds) != 20:
        raise ValueError(f"expected 20 trio combinations, got {len(odds)}")
    label = (p.tab4_time or "").strip() or None
    return {"odds": odds, "label": label,
            # the source labels closing odds with the Japanese word for
            # "deadline"
            "is_final": bool(label and "締切" in label)}


def fetch_trio_odds(day, stadium_id, race_number, session=None):
    """Fetch one race's trio odds.
    Returns dict(ok=bool, odds=dict|None, label, is_final, error)."""
    base = _odds_base()
    if not base:
        return {"ok": False, "odds": None, "label": None,
                "is_final": False, "error": "ODDS_BASE_URL is not set"}
    url = (f"{base}/odds3f?rno={int(race_number)}"
           f"&jcd={str(stadium_id).zfill(2)}&hd={day.strftime('%Y%m%d')}")
    resp, err = http_get(url, session=session)
    if resp is None or resp.status_code != 200:
        return {"ok": False, "odds": None, "label": None,
                "is_final": False, "error": err or "HTTP error"}
    resp.encoding = resp.encoding or "utf-8"
    try:
        parsed = parse_trio_odds_html(resp.text)
    except ValueError as e:
        return {"ok": False, "odds": None, "label": None,
                "is_final": False, "error": f"parse: {e}"}
    if not any(v is not None for v in parsed["odds"].values()):
        return {"ok": False, "odds": None, "label": parsed["label"],
                "is_final": False, "error": "no odds published yet"}
    return {"ok": True, "error": None, **parsed}
