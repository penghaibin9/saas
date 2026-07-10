"""教务中心·成绩录入闭环（13B-P5）测试：配比校验 + 平时/期末合成 + 未录全拦截发布 +
发布投影 t_acad_grade + 发布后禁改/禁重复发布 + 读侧成绩单/挂科清单/分析 + fail-list 无 N+1。

academic_affairs 域此前零测试覆盖；本文件补齐最高风险的成绩状态机闭环（SQLite 隔离库可跑）。
"""
from __future__ import annotations

MAIN_TID = 1000000000000000001


def _seed_students(names):
    """按姓名建 StudentProfile，返回 [(id, name), ...]。"""
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    out = []
    try:
        for i, nm in enumerate(names):
            s = StudentProfile(tenant_id=MAIN_TID, student_no=f"2023700{i:03d}", real_name=nm,
                               class_id=9001, current_stage="IN_SCHOOL", student_status="NORMAL",
                               status="ACTIVE")
            db.add(s)
            db.flush()
            out.append((s.id, nm))
        db.commit()
        return out
    finally:
        db.close()


def _mk_task(client, auth_headers, course="高等数学", credit=4):
    r = client.post("/api/v1/academic-affairs/grade-tasks", headers=auth_headers,
                    json={"courseName": course, "termCode": "2025-2026-2", "credit": credit,
                          "usualRatio": 30, "finalRatio": 70, "passLine": 60}).json()
    assert r["code"] == 0, r
    assert r["data"]["status"] == "DRAFT"
    return r["data"]["gradeTaskId"]


def test_grade_ratio_validation(client, auth_headers, db_mode):
    """平时占比+期末占比必须=100，否则 422。"""
    r = client.post("/api/v1/academic-affairs/grade-tasks", headers=auth_headers,
                    json={"courseName": "大学英语", "usualRatio": 40, "finalRatio": 70}).json()
    assert r["code"] == 422001, r


def test_grade_full_closed_loop(client, auth_headers, db_mode):
    stus = _seed_students(["成绩甲", "成绩乙"])
    (sid_a, _), (sid_b, _) = stus
    tid = _mk_task(client, auth_headers)

    # 甲：平时90/期末90 → 合成 90 PASSED
    ra = client.post(f"/api/v1/academic-affairs/grade-tasks/{tid}/scores", headers=auth_headers,
                     json={"studentId": str(sid_a), "usualScore": 90, "finalScore": 90}).json()
    assert ra["code"] == 0 and ra["data"]["totalScore"] == 90 and ra["data"]["passStatus"] == "PASSED"

    # 乙：仅录平时分 → 总评未合成（None）→ 不可发布
    rb = client.post(f"/api/v1/academic-affairs/grade-tasks/{tid}/scores", headers=auth_headers,
                     json={"studentId": str(sid_b), "usualScore": 50}).json()
    assert rb["code"] == 0 and rb["data"]["totalScore"] is None

    blocked = client.post(f"/api/v1/academic-affairs/grade-tasks/{tid}/publish", headers=auth_headers).json()
    assert blocked["code"] == 409001, blocked  # 仍有 1 名学生成绩未录全

    # 乙补齐 50/50 → 合成 50 FAIL
    rb2 = client.post(f"/api/v1/academic-affairs/grade-tasks/{tid}/scores", headers=auth_headers,
                      json={"studentId": str(sid_b), "usualScore": 50, "finalScore": 50}).json()
    assert rb2["code"] == 0 and rb2["data"]["totalScore"] == 50 and rb2["data"]["passStatus"] == "FAIL"

    pub = client.post(f"/api/v1/academic-affairs/grade-tasks/{tid}/publish", headers=auth_headers).json()
    assert pub["code"] == 0 and pub["data"]["status"] == "PUBLISHED" and pub["data"]["projected"] == 2

    # 发布后禁止再录入
    reenter = client.post(f"/api/v1/academic-affairs/grade-tasks/{tid}/scores", headers=auth_headers,
                          json={"studentId": str(sid_a), "usualScore": 100, "finalScore": 100}).json()
    assert reenter["code"] == 409001, reenter
    # 发布后禁止重复发布
    repub = client.post(f"/api/v1/academic-affairs/grade-tasks/{tid}/publish", headers=auth_headers).json()
    assert repub["code"] == 409001, repub

    # 读侧：甲成绩单得 4 学分、无挂科；乙 0 学分、挂科 1
    ta = client.get(f"/api/v1/academic-affairs/students/{sid_a}/transcript", headers=auth_headers).json()
    assert ta["code"] == 0 and ta["data"]["earnedCredits"] == 4 and ta["data"]["failCount"] == 0
    assert any(it["courseName"] == "高等数学" for it in ta["data"]["items"])
    tb = client.get(f"/api/v1/academic-affairs/students/{sid_b}/transcript", headers=auth_headers).json()
    assert tb["code"] == 0 and tb["data"]["earnedCredits"] == 0 and tb["data"]["failCount"] == 1

    # 挂科清单含乙
    fl = client.get("/api/v1/academic-affairs/grade-views/fail-list", headers=auth_headers).json()
    assert fl["code"] == 0 and fl["data"]["total"] >= 1
    assert any(row["studentName"] == "成绩乙" and row["score"] == 50 for row in fl["data"]["items"])

    # 成绩分析：分数段 + 及格率
    an = client.get("/api/v1/academic-affairs/grade-views/analysis", headers=auth_headers).json()
    assert an["code"] == 0 and an["data"]["total"] >= 2
    dist = {d["range"]: d["count"] for d in an["data"]["distribution"]}
    assert dist["90-100"] >= 1 and dist["0-59"] >= 1


def test_fail_list_no_n_plus_one(client, auth_headers, db_mode):
    """挂科清单读侧：触及 t_acad_student 的查询次数与挂科行数无关（JOIN 批量，非逐行 db.get）。"""
    from sqlalchemy import event
    from app.db.session import get_engine
    stus = _seed_students([f"挂科生{i:02d}" for i in range(6)])
    tid = _mk_task(client, auth_headers, course="线性代数", credit=3)
    for sid, _ in stus:
        client.post(f"/api/v1/academic-affairs/grade-tasks/{tid}/scores", headers=auth_headers,
                    json={"studentId": str(sid), "usualScore": 30, "finalScore": 30})
    pub = client.post(f"/api/v1/academic-affairs/grade-tasks/{tid}/publish", headers=auth_headers).json()
    assert pub["code"] == 0 and pub["data"]["projected"] == 6

    hits = []
    engine = get_engine()

    def _rec(conn, cursor, statement, parameters, context, executemany):
        if "t_acad_student" in statement:
            hits.append(statement)

    event.listen(engine, "before_cursor_execute", _rec)
    try:
        fl = client.get("/api/v1/academic-affairs/grade-views/fail-list?pageSize=50", headers=auth_headers).json()
    finally:
        event.remove(engine, "before_cursor_execute", _rec)
    assert fl["code"] == 0 and fl["data"]["total"] >= 6
    assert len(hits) <= 2, f"疑似 N+1：命中 t_acad_student {len(hits)} 次 → {hits}"


def test_grade_endpoints_forbid_student_token(client, auth_headers, db_mode):
    """成绩录入/发布 PC 端点拒绝学生令牌（academic_affairs 已 require_staff）。"""
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "student01", "password": "any"}).json()["data"]
    sh = {"Authorization": f"Bearer {data['accessToken']}"}
    r1 = client.post("/api/v1/academic-affairs/grade-tasks", headers=sh,
                     json={"courseName": "x", "usualRatio": 30, "finalRatio": 70}).json()
    assert r1["code"] == 403001, r1
    r2 = client.get("/api/v1/academic-affairs/grade-views/fail-list", headers=sh).json()
    assert r2["code"] == 403001, r2
