from app.services import mobile_agenda_projection_service as agenda


def test_same_timestamp_cross_kind_cursor_matches_render_sort_order():
    """同一时刻跨页时，cursor 必须与 EXAM→DEADLINE→COURSE 的真实排序完全同序。"""
    rows = [
        {"startAt": "2026-08-20T09:00:00", "kind": "COURSE", "eventId": "m-course"},
        {"startAt": "2026-08-20T09:00:00", "kind": "EXAM", "eventId": "z-exam"},
        {"startAt": "2026-08-20T09:00:00", "kind": "DEADLINE", "eventId": "a-deadline"},
    ]
    ordered = sorted(rows, key=agenda._sort_key)
    assert [row["kind"] for row in ordered] == ["EXAM", "DEADLINE", "COURSE"]

    cursors = [agenda._cursor_of(row) for row in ordered]
    assert cursors == sorted(cursors), "cursor 顺序必须与完整渲染排序键一致"

    first_cursor = cursors[0]
    after_first = [row for row in ordered if agenda._cursor_of(row) > first_cursor]
    assert [row["kind"] for row in after_first] == ["DEADLINE", "COURSE"]

    second_cursor = cursors[1]
    after_second = [row for row in ordered if agenda._cursor_of(row) > second_cursor]
    assert [row["kind"] for row in after_second] == ["COURSE"]
