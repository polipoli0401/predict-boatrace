"""Race board: all target stadiums merged into one list sorted by the
scheduled deadline (締切予定時刻), rendered as HTML (GitHub Pages) and
Markdown (Actions job summary)."""
import html
import json

from boatrace_sources import STADIUM_NAMES, iso_jst
from ev_judge import (
    DECISION_CANDIDATE,
    DECISION_PASS,
    DECISION_UNDECIDABLE,
    evaluate_race,
    parse_jst,
)

ODDS_STATUS_LABEL = {"success": "取得済", "pending": "未取得",
                     "failed": "取得失敗"}


def fmt_prob(c):
    return f"{c['probability'] * 100:.1f}%"


def fmt_odds(c):
    return "—" if c["odds"] is None else f"{c['odds']:.1f}"


def fmt_ev(c):
    er = c["expected_return"]
    return "—" if er is None else f"{er * 100:.0f}%"


def fmt_req(c):
    r = c.get("required_odds")
    return "確率不足" if r is None else f"{r:.1f}倍〜"


def fmt_combo(c):
    return ("★" if c["candidate"] else "") + c["combination"]


def _hhmm(text):
    dt = parse_jst(text)
    return dt.strftime("%H:%M") if dt else "—"


def build_rows(preds_doc, info_doc, odds_doc, cfg, calibration, now):
    """One row per race from the union of predictions / race info / odds.
    Races without odds or predictions are kept (判定不可)."""
    preds = (preds_doc or {}).get("races", {})
    infos = (info_doc or {}).get("races", {})
    odds = (odds_doc or {}).get("races", {})
    rows = []
    for key in sorted(set(preds) | set(infos) | set(odds)):
        p, i, o = preds.get(key), infos.get(key, {}), odds.get(key)
        sid = (p or i or o)["stadium_id"]
        rno = int((p or i or o)["race_number"])
        closed_at = i.get("closed_at") or (p or {}).get("closed_at")
        ev = evaluate_race(p, o, now, cfg, calibration)
        if o and o.get("status") == "failed" and not o.get("odds"):
            ev["reason"] = "オッズ取得失敗"
        rows.append({
            "key": key, "stadium_id": sid,
            "stadium_name": STADIUM_NAMES.get(sid, sid),
            "race_number": rno, "closed_at": closed_at,
            "closed_hhmm": _hhmm(closed_at),
            "entry_status": i.get("entry_status", "未取得"),
            "entry_note": i.get("entry_note"),
            "exhibition_status": i.get("exhibition_status", "未取得"),
            "finished": bool(i.get("finished")),
            "is_closed": bool(parse_jst(closed_at)
                              and parse_jst(closed_at) <= now),
            "odds_status": (o or {}).get("status", "pending"),
            "odds_at": (o or {}).get("odds_fetched_at"),
            "odds_label": (o or {}).get("official_label"),
            "odds_error": (o or {}).get("last_error"),
            "predicted_at": (p or {}).get("predicted_at"),
            "prediction_kind": (p or {}).get("prediction_kind"),
            **{k: ev[k] for k in ("decision", "reason", "rows", "stale",
                                  "scratched")},
        })
    rows.sort(key=sort_key)
    return rows


def sort_key(row):
    """Deadline ascending, then stadium code, then race number.
    Races without a deadline go last."""
    dt = parse_jst(row.get("closed_at"))
    return (0 if dt else 1, dt.isoformat() if dt else "",
            str(row["stadium_id"]).zfill(2), int(row["race_number"]))


def summary_counts(rows):
    c = {DECISION_CANDIDATE: 0, DECISION_PASS: 0, DECISION_UNDECIDABLE: 0}
    for r in rows:
        if not r["is_closed"]:
            c[r["decision"]] += 1
    return c


# ------------------------------------------------------------
# Markdown (job summary)
# ------------------------------------------------------------
def render_markdown(rows, day, now, cfg):
    out = [f"## {day.isoformat()} レース一覧（締切予定時刻順・JST）",
           f"生成: {iso_jst(now)} / 判定基準: 期待回収率 ≥ "
           f"{cfg['ev_min']*100:.0f}% かつ 確率 ≥ {cfg['prob_min']*100:.0f}%"
           f"、オッズ取得から {cfg['stale_minutes']} 分以内", "",
           "| 締切 | 場・R | 出走 | 展示 | オッズ取得 | 状況 | 買い目 "
           "| 確率 | 必要オッズ | オッズ | 期待回収率 | 判定 |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        combos = r["rows"][:3]

        def cell(f, combos=combos):
            return "<br>".join(f(c) for c in combos) or "—"
        decision = r["decision"] + (f"（{r['reason']}）" if r["reason"] else "")
        if r["is_closed"]:
            decision = "締切済 / " + decision
        out.append(
            f"| {r['closed_hhmm']} | {r['stadium_name']} {r['race_number']}R "
            f"| {r['entry_status']} | {r['exhibition_status']} "
            f"| {_hhmm(r['odds_at'])} "
            f"| {ODDS_STATUS_LABEL.get(r['odds_status'], r['odds_status'])} "
            f"| {cell(fmt_combo)} | {cell(fmt_prob)} | {cell(fmt_req)} "
            f"| {cell(fmt_odds)} | {cell(fmt_ev)} "
            f"| {decision} |")
    out += ["", "★ = 購入候補の組合せ。予測は研究目的の参考値で、"
            "的中や利益を保証しません。最終判断は利用者が行ってください。"]
    return "\n".join(out)


# ------------------------------------------------------------
# HTML (GitHub Pages)
# ------------------------------------------------------------
_CSS = """
:root{--bg:#f7f7f5;--fg:#1d1d1f;--muted:#6b6b70;--card:#fff;--line:#e3e3e0;
--cand:#0a7a3d;--cand-bg:#e6f4ec;--pass:#6b6b70;--na:#a15c00;--na-bg:#fdf1e0;
--warn:#b42318;--closed:#9a9a9f;--accent:#1f5fbf}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#141416;
--fg:#ececee;--muted:#a0a0a8;--card:#1d1d20;--line:#2e2e33;--cand:#5cd08f;
--cand-bg:#173325;--pass:#a0a0a8;--na:#f0b45c;--na-bg:#3a2a12;--warn:#ff8a7a;
--closed:#6c6c72;--accent:#7fb0ff}}
:root[data-theme=dark]{--bg:#141416;--fg:#ececee;--muted:#a0a0a8;--card:#1d1d20;
--line:#2e2e33;--cand:#5cd08f;--cand-bg:#173325;--pass:#a0a0a8;--na:#f0b45c;
--na-bg:#3a2a12;--warn:#ff8a7a;--closed:#6c6c72;--accent:#7fb0ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,
"Hiragino Sans","Noto Sans JP",system-ui,sans-serif}
main{max-width:1200px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:0 0 4px}
.meta{color:var(--muted);font-size:12px;margin:0 0 12px}
.counts{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px}
.chip{padding:4px 10px;border-radius:999px;background:var(--card);
border:1px solid var(--line);font-size:13px}
.chip b{font-variant-numeric:tabular-nums}
.filters{margin:0 0 12px;font-size:13px;color:var(--muted)}
table{width:100%;border-collapse:collapse;background:var(--card);
border:1px solid var(--line);border-radius:8px;overflow:hidden}
th,td{padding:8px;border-bottom:1px solid var(--line);text-align:left;
vertical-align:top;font-variant-numeric:tabular-nums}
th{font-size:12px;color:var(--muted);font-weight:600;background:var(--card);
position:sticky;top:0}
td.num{text-align:right}
.combo{display:block;white-space:nowrap}
.combo.cand{color:var(--cand);font-weight:700}
.dec{font-weight:700;white-space:nowrap}
.dec.c{color:var(--cand)} .dec.p{color:var(--pass)} .dec.n{color:var(--na)}
tr.cand td{background:var(--cand-bg)}
tr.closed td{color:var(--closed)}
tr.closed .dec{color:var(--closed)}
.reason{display:block;font-size:12px;font-weight:400;color:var(--muted)}
.warn{color:var(--warn);font-size:12px;display:block}
.st-failed{color:var(--warn)} .st-pending{color:var(--muted)}
footer{color:var(--muted);font-size:12px;margin-top:16px}
footer table{margin-top:8px}
@media (max-width:760px){
 main{padding:12px 16px}
 table.board,table.board tbody,table.board tr,table.board td{display:block;width:100%}
 table.board thead{display:none}
 table.board{border:none;background:none}
 table.board tr{background:var(--card);border:1px solid var(--line);
  border-radius:8px;margin:0 0 10px;padding:6px 0}
 table.board td{border:none;padding:2px 12px;text-align:left}
 table.board td::before{content:attr(data-label);display:inline-block;
  min-width:6.5em;color:var(--muted);font-size:12px}
 table.board td.combos::before{display:block}
 table.board td.num{text-align:left}
}
"""

_JS = """
(function(){
  var stale = %d;
  var now = Date.now();
  document.querySelectorAll('[data-odds-at]').forEach(function(el){
    var t = Date.parse(el.getAttribute('data-odds-at'));
    if (!t) return;
    var mins = Math.floor((now - t) / 60000);
    if (mins > stale && !el.closest('tr.closed')) {
      var w = document.createElement('span');
      w.className = 'warn';
      w.textContent = '取得から' + mins + '分経過（古いオッズ）';
      el.appendChild(w);
    }
  });
  var cb = document.getElementById('hide-closed');
  function apply(){ document.querySelectorAll('tr.closed').forEach(function(r){
    r.style.display = cb.checked ? 'none' : ''; }); }
  try { cb.checked = localStorage.getItem('hideClosed') === '1'; } catch(e) {}
  cb.addEventListener('change', function(){
    try { localStorage.setItem('hideClosed', cb.checked ? '1' : '0'); } catch(e) {}
    apply(); });
  apply();
})();
"""


def _esc(v):
    return html.escape("" if v is None else str(v))


def render_html(rows, day, now, cfg, verification=None):
    counts = summary_counts(rows)
    body = []
    for r in rows:
        cls = []
        if r["is_closed"]:
            cls.append("closed")
        elif r["decision"] == DECISION_CANDIDATE:
            cls.append("cand")
        dec_cls = {DECISION_CANDIDATE: "c", DECISION_PASS: "p"}.get(
            r["decision"], "n")
        combos = r["rows"][:max(3, sum(c["candidate"] for c in r["rows"]))]

        def col(fmt, combos=combos):
            return "".join(
                f'<span class="combo{" cand" if c["candidate"] else ""}">'
                f'{fmt(c)}</span>' for c in combos) or "—"
        odds_at = r["odds_at"]
        odds_cell = (f'<span data-odds-at="{_esc(odds_at)}">'
                     f'{_esc(_hhmm(odds_at))}'
                     + (f'<span class="reason">{_esc(r["odds_label"])}</span>'
                        if r["odds_label"] else "") + "</span>"
                     if odds_at else "—")
        status = ODDS_STATUS_LABEL.get(r["odds_status"], r["odds_status"])
        if r["odds_status"] == "failed" and r["odds_error"]:
            status += f'<span class="reason">{_esc(r["odds_error"])}</span>'
        decision = (f'<span class="dec {dec_cls}">'
                    f'{"締切済・" if r["is_closed"] else ""}'
                    f'{_esc(r["decision"])}'
                    + (f'<span class="reason">{_esc(r["reason"])}</span>'
                       if r["reason"] else "") + "</span>")
        entry = _esc(r["entry_status"]) + (
            f'<span class="reason">{_esc(r["entry_note"])}</span>'
            if r.get("entry_note") else "")
        body.append(
            f'<tr class="{" ".join(cls)}">'
            f'<td data-label="締切予定"><b>{_esc(r["closed_hhmm"])}</b></td>'
            f'<td data-label="場・R">{_esc(r["stadium_name"])} '
            f'{r["race_number"]}R</td>'
            f'<td data-label="出走情報">{entry}</td>'
            f'<td data-label="展示情報">{_esc(r["exhibition_status"])}</td>'
            f'<td data-label="オッズ取得">{odds_cell}</td>'
            f'<td data-label="取得状況" class="st-{_esc(r["odds_status"])}">'
            f'{status}</td>'
            f'<td data-label="予測買い目" class="combos">'
            f'{col(lambda c: _esc(fmt_combo(c)))}</td>'
            f'<td data-label="予測確率" class="num combos">{col(fmt_prob)}</td>'
            f'<td data-label="必要オッズ" class="num combos">{col(fmt_req)}</td>'
            f'<td data-label="オッズ" class="num combos">{col(fmt_odds)}</td>'
            f'<td data-label="期待回収率" class="num combos">{col(fmt_ev)}</td>'
            f'<td data-label="判定">{decision}</td></tr>')

    verify_html = ""
    if verification and verification.get("by_stadium"):
        vrows = "".join(
            f"<tr><td>{_esc(STADIUM_NAMES.get(s, s) if s != 'all' else '合計')}</td>"
            f"<td class=num>{v['candidate_races']}</td>"
            f"<td class=num>{v['tickets']}</td>"
            f"<td class=num>{v['hit_rate']}</td>"
            f"<td class=num>{v['roi']}</td>"
            f"<td class=num>{v['mean_expected_return']}</td>"
            f"<td class=num>{(v.get('closing_rule') or {}).get('roi')}</td></tr>"
            for s, v in verification["by_stadium"].items())
        verify_html = (
            "<h2 style='font-size:15px;margin:20px 0 0'>検証（購入候補の実績・"
            f"{_esc(verification.get('period'))}）</h2>"
            "<table><thead><tr><th>場</th><th>候補レース</th><th>点数</th>"
            "<th>的中率%</th><th>回収率%</th><th>平均期待回収率%</th>"
            "<th>締切時オッズでの回収率%（参考）</th>"
            f"</tr></thead><tbody>{vrows}</tbody></table>")

    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>レース一覧 {day.isoformat()}</title>
<style>{_CSS}</style></head><body><main>
<h1>{day.isoformat()} レース一覧</h1>
<p class="meta">締切予定時刻順（JST）・生成 {_esc(iso_jst(now))} ・
判定基準：期待回収率 {cfg['ev_min']*100:.0f}%以上 かつ 予測確率
{cfg['prob_min']*100:.0f}%以上、オッズ取得から{cfg['stale_minutes']}分以内</p>
<div class="counts">
<span class="chip">購入候補 <b>{counts[DECISION_CANDIDATE]}</b></span>
<span class="chip">見送り <b>{counts[DECISION_PASS]}</b></span>
<span class="chip">判定不可 <b>{counts[DECISION_UNDECIDABLE]}</b></span>
<span class="chip">（締切前のレースのみ集計）</span></div>
<p class="filters"><label><input type="checkbox" id="hide-closed">
締切済みのレースを隠す</label></p>
<table class="board"><thead><tr><th>締切予定</th><th>場・R</th><th>出走情報</th>
<th>展示情報</th><th>オッズ取得</th><th>取得状況</th><th>予測買い目</th>
<th>予測確率</th><th>必要オッズ</th><th>オッズ</th><th>期待回収率</th><th>判定</th></tr></thead>
<tbody>{"".join(body) or '<tr><td colspan="12">対象レースがありません</td></tr>'}</tbody></table>
{verify_html}
<footer>★ = 購入候補の組合せ（期待回収率の高い順）。必要オッズ = 実際のオッズがこの値以上なら
期待回収率が基準（{cfg['ev_min']*100:.0f}%）に届く目安（予測確率が基準未満の組合せは「確率不足」）。予測確率は過去のバックテストで補正した参考値で、
的中や利益を保証しません。オッズは取得時点の値で、締切までに変動します。自動購入は行いません。
最終的な購入判断は利用者が行ってください。</footer>
</main><script>{_JS % cfg['stale_minutes']}</script></body></html>
"""


def load_verification(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
