"""教务中心·课表三重冲突检测（13B-P4）测试：手工排课教师/班级/教室冲突 + 单双周相容 +
导入逐行冲突清单 + 批次状态机（草稿→预发布→发布→作废重发）。

academic_affairs 域此前零测试；本文件锁定最高风险的排课冲突检测器行为（SQLite 隔离库可跑）。
"""
from __future__ import annotations


def _new_batch(client, auth_headers, term_id="9001"):
    r = client.post("/api/v1/academic-affairs/schedule-batches", headers=auth_headers,
                    json={"termId": term_id, "batchName": "测试课表"}).json()
    assert r["code"] == 0, r
    assert r["data"]["status"] == "DRAFT"
    return r["data"]["batchId"]


def _add(client, auth_headers, bid, weekday, slot, teacher, class_id, room,
         parity="ALL", start=1, end=18, course="课程X"):
    return client.post(f"/api/v1/academic-affairs/schedule-batches/{bid}/items", headers=auth_headers,
                       json={"weekday": weekday, "slotNo": slot, "teacherKey": teacher, "classId": class_id,
                             "classroom": room, "weekParity": parity, "startWeek": start, "endWeek": end,
                             "courseName": course}).json()


def test_schedule_triple_conflict_detection(client, auth_headers, db_mode):
    bid = _new_batch(client, auth_headers)
    # 基准课：周2第3节，教师 T1 / 班级 101 / 教室 A101
    base = _add(client, auth_headers, bid, 2, 3, "T1", "101", "A101")
    assert base["code"] == 0 and base["data"]["status"] == "EFFECTIVE"

    # 同槽 + 同教师（其余不同）→ 教师冲突 409
    r_t = _add(client, auth_headers, bid, 2, 3, "T1", "999", "Z9")
    assert r_t["code"] == 409001 and "TEACHER" in r_t["message"], r_t
    # 同槽 + 同班级（教师不同）→ 班级冲突 409
    r_c = _add(client, auth_headers, bid, 2, 3, "T2", "101", "Z9")
    assert r_c["code"] == 409001 and "CLASS" in r_c["message"], r_c
    # 同槽 + 同教室（教师/班级不同）→ 教室冲突 409
    r_r = _add(client, auth_headers, bid, 2, 3, "T2", "999", "A101")
    assert r_r["code"] == 409001 and "CLASSROOM" in r_r["message"], r_r

    # 同教师但不同节次 → 不冲突
    r_ok = _add(client, auth_headers, bid, 2, 5, "T1", "101", "A101")
    assert r_ok["code"] == 0, r_ok


def test_schedule_week_parity(client, auth_headers, db_mode):
    """单双周相容：同教师同槽，单周 + 双周不冲突；再排单周与已存单周冲突。"""
    bid = _new_batch(client, auth_headers)
    odd = _add(client, auth_headers, bid, 4, 4, "TP", "201", "B201", parity="ODD")
    assert odd["code"] == 0, odd
    even = _add(client, auth_headers, bid, 4, 4, "TP", "201", "B201", parity="EVEN")
    assert even["code"] == 0, even  # ODD 与 EVEN 不冲突
    odd2 = _add(client, auth_headers, bid, 4, 4, "TP", "201", "B201", parity="ODD")
    assert odd2["code"] == 409001, odd2  # 与已存单周冲突


def test_schedule_import_conflict_rows(client, auth_headers, db_mode):
    """导入通道走同一检测器，逐行落库，返回冲突行清单（不整批回滚）。"""
    bid = _new_batch(client, auth_headers)
    _add(client, auth_headers, bid, 2, 3, "T1", "101", "A101")  # 占位，用于制造导入冲突
    payload = {"items": [
        {"weekday": 2, "slotNo": 6, "teacherKey": "T5", "classId": "105", "classroom": "A105"},  # ok
        {"weekday": 2, "slotNo": 3, "teacherKey": "T1", "classId": "888", "classroom": "Z8"},     # 教师冲突
    ]}
    r = client.post(f"/api/v1/academic-affairs/schedule-batches/{bid}/import", headers=auth_headers,
                    json=payload).json()
    assert r["code"] == 0, r
    assert r["data"]["imported"] == 1 and len(r["data"]["conflicts"]) == 1
    assert r["data"]["conflicts"][0]["row"] == 2 and r["data"]["conflicts"][0]["type"] == "TEACHER"


def test_schedule_state_machine(client, auth_headers, db_mode):
    bid = _new_batch(client, auth_headers)
    _add(client, auth_headers, bid, 1, 1, "TS", "301", "C301")
    # 预发布仅限草稿
    pre = client.post(f"/api/v1/academic-affairs/schedule-batches/{bid}/pre-publish", headers=auth_headers).json()
    assert pre["code"] == 0 and pre["data"]["status"] == "PRE_PUBLISHED"
    # 发布
    pub = client.post(f"/api/v1/academic-affairs/schedule-batches/{bid}/publish", headers=auth_headers).json()
    assert pub["code"] == 0 and pub["data"]["status"] == "PUBLISHED"
    # 发布后禁止直接排课
    after = _add(client, auth_headers, bid, 1, 2, "TS", "301", "C301")
    assert after["code"] == 409001, after
    # 作废重发需原因≥5字
    bad = client.post(f"/api/v1/academic-affairs/schedule-batches/{bid}/void-reissue", headers=auth_headers,
                      json={"reason": "改"}).json()
    assert bad["code"] == 422001, bad
    ok = client.post(f"/api/v1/academic-affairs/schedule-batches/{bid}/void-reissue", headers=auth_headers,
                     json={"reason": "教师临时调课需重排"}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "ARCHIVED"


def test_schedule_class_view_after_publish(client, auth_headers, db_mode):
    bid = _new_batch(client, auth_headers)
    _add(client, auth_headers, bid, 3, 2, "TV", "401", "D401", course="数据结构")
    client.post(f"/api/v1/academic-affairs/schedule-batches/{bid}/publish", headers=auth_headers)
    cv = client.get(f"/api/v1/academic-affairs/schedule-batches/{bid}/class-view?classId=401",
                    headers=auth_headers).json()
    assert cv["code"] == 0 and len(cv["data"]["items"]) == 1
    assert cv["data"]["items"][0]["courseName"] == "数据结构" and cv["data"]["items"][0]["weekday"] == 3
