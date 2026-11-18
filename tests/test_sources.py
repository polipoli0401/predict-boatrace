from datetime import date

from boatrace_sources import load_day_programs, race_status_from_v1

DAY = date(2026, 11, 19)


def v1_racer(e, number, avg_st=0.17):
    return {"entry_number": e, "name": "x", "number": number,
            "rank_number": 2, "branch_number": 40, "age": 30, "weight": 52.0,
            "flying_count": 0, "late_count": 0,
            "average_start_timing": avg_st, "national_win_rate": 5.5,
            "national_top_2_percent": 30, "national_top_3_percent": 50,
            "local_win_rate": 5.0, "local_top_2_percent": 25,
            "local_top_3_percent": 45, "motor_number": 10,
            "motor_top_2_percent": 33, "motor_top_3_percent": 50,
            "boat_number": 20, "boat_top_2_percent": 30,
            "boat_top_3_percent": 45}


def v1_doc():
    full = {"closed_at": "2026-11-19 08:47:00", "grade_number": 5,
            "subtitle": "予選",
            "racers": {str(e): v1_racer(e, 4000 + e, avg_st=0 if e == 6 else 0.17)
                       for e in range(1, 7)},
            "preview": {"racers": {str(e): {"exhibition_time": 6.8}
                                   for e in range(1, 6)}},
            "result": {"racers": {}}}
    missing = {"closed_at": None, "racers": None}
    return {"programs": {"stadiums": {
        "18": {"races": {"1": full, "2": missing}},
        "5": {"races": {"1": full}}}}}


def v2_doc():
    boats = [{"racer_boat_number": b, "racer_number": 5000 + b,
              "racer_national_top_1_percent": 6.0} for b in range(1, 7)]
    return {"programs": [{"race_stadium_number": 18, "race_number": 2,
                          "race_closed_at": "2026-11-19 09:13:00",
                          "race_grade_number": 5, "race_subtitle": "",
                          "boats": boats}]}


def test_v1_first_v2_fills_missing_race():
    df, meta = load_day_programs(DAY, ["18"], v1_doc(), v2_doc())
    assert meta[("18", 1)]["source"] == "v1"
    assert meta[("18", 2)] == {"closed_at": "2026-11-19 09:13:00",
                               "source": "v2"}
    assert ("05", 1) not in meta                      # not a target stadium
    r1 = df[(df.race_number == 1) & (df.boat_number == 1)].iloc[0]
    assert r1.official_national_win_rate == 5.5
    assert r1.racer_class == 2
    assert r1.official_avg_st == 0.17
    r6 = df[(df.race_number == 1) & (df.boat_number == 6)].iloc[0]
    assert r6.official_avg_st != r6.official_avg_st    # 0 = unknown -> NaN
    assert len(df[df.race_number == 2]) == 6


def test_race_status_from_v1():
    st = race_status_from_v1(v1_doc(), ["18"])
    assert st["18-01"]["entrants"]["1"] == 4001
    assert st["18-01"]["exhibition_boats"] == [1, 2, 3, 4, 5]
    assert st["18-01"]["finished"] is False
    assert st["18-02"]["closed_at"] is None
