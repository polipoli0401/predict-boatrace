from itertools import combinations

import pytest

from boatrace_sources import parse_trio_odds_html


# Labels and cell texts below are the Japanese strings the source page
# publishes ("odds updated at", "closing odds", "scratched").
def make_odds_html(values, label="オッズ更新時間 14:05"):
    """Synthetic page with the same table layout as the official trio
    odds page: one column group (2nd, 3rd, odds) per first boat."""
    head = "".join(f'<th class="is-boatColor{b}">{b}</th>'
                   f'<th colspan="2">name{b}</th>' for b in range(1, 7))
    blocks = {a: [(b, c) for b, c in combinations(range(a + 1, 7), 2)]
              for a in range(1, 7)}
    # rows: for each first boat a, pairs grouped by second boat
    rows_by_group = {}
    for a, pairs in blocks.items():
        lines = []
        for b in sorted({p[0] for p in pairs}):
            thirds = [c for bb, c in pairs if bb == b]
            for i, c in enumerate(thirds):
                cells = []
                if i == 0:
                    cells.append(f'<td rowspan="{len(thirds)}">{b}</td>')
                key = f"{a}-{b}-{c}"
                cells.append(f"<td>{c}</td>")
                cells.append(f'<td class="oddsPoint ">{values[key]}</td>')
                lines.append(cells)
        rows_by_group[a] = lines
    n = max(len(v) for v in rows_by_group.values())
    body = []
    for r in range(n):
        cells = []
        for a in range(1, 7):
            lines = rows_by_group[a]
            if r < len(lines):
                cells.extend(lines[r])
            else:
                cells.append('<td class="is-disabled"> </td>' * (
                    3 if (r == len(lines) or not lines) else 3))
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<p class="tab4_time">{label}</p><table><thead><tr>{head}</tr>'
            f'</thead><tbody>{"".join(body)}</tbody></table>')


@pytest.fixture
def values():
    return {"-".join(map(str, c)): f"{10 + i * 1.5:.1f}"
            for i, c in enumerate(combinations(range(1, 7), 3))}


def test_parse_all_twenty(values):
    out = parse_trio_odds_html(make_odds_html(values))
    assert len(out["odds"]) == 20
    for k, v in values.items():
        assert out["odds"][k] == float(v)
    assert out["label"] == "オッズ更新時間 14:05"
    assert out["is_final"] is False


def test_closing_label_and_missing_values(values):
    values["1-2-6"] = "欠場"
    out = parse_trio_odds_html(make_odds_html(values, label="締切時オッズ"))
    assert out["is_final"] is True
    assert out["odds"]["1-2-6"] is None   # not 0: "no odds" stays None


def test_unexpected_layout_raises():
    with pytest.raises(ValueError):
        parse_trio_odds_html("<html><body>no table</body></html>")
