"""13A-P1 学工首页 + 班级/班干部骨架 · 端到端（真实 DB 模式）。

覆盖：三角色视图差异 + scope 差异；13 模块卡空态；班级列表范围过滤；
班干部任命/列表；辅导员跨班访问 403（越权+自动审计）；重复任命 409。
"""
from __future__ import annotations

TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_classes(db_mode):
    """在 db_mode（DB 已启用）之上补种：2 班 + 5 生 + 辅导员范围限定 A 班。"""
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2102", grade="2021", status="ACTIVE")
    db.add(a); db.add(b); db.flush()
    for i in range(3):
        db.add(StudentProfile(tenant_id=TID, student_no=f"A{i:03d}", real_name=f"甲{i}",
                              class_id=a.id, current_stage="ORIENTATION",
                              student_status="NORMAL", status="ACTIVE"))
    for i in range(2):
        db.add(StudentProfile(tenant_id=TID, student_no=f"B{i:03d}", real_name=f"乙{i}",
                              class_id=b.id, current_stage="ORIENTATION",
                              student_status="NORMAL", status="ACTIVE"))
    # 辅导员 counselor01（王莉）数据范围 = A 班
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2101",
                               status="ACTIVE"))
    db.commit()
    ids = {"A": a.id, "B": b.id}
    db.close()
    return ids


def test_dashboard_three_role_views(client, db_mode):
    _seed_classes(db_mode)
    # 学工处：全校视图 + ADMIN_TENANT
    r = client.get("/api/v1/student-affairs/dashboard", headers=_hdr(client, "school_admin01")).json()
    assert r["code"] == 0
    assert r["data"]["view"] == "SA_ADMIN"
    assert r["data"]["scopeMode"] == "ADMIN_TENANT"
    assert len(r["data"]["moduleCards"]) == 13
    # 首页卡随阶段点亮：P1 class / P2 leave / P3 aid+funding / P4 discipline+risk / P5 talk+family+profile
    # / P6 dorm+archive（psy/activity 未在 13A P1-P8 范围，保持空态）
    _live = {"class", "leave", "aid", "funding", "discipline", "risk", "talk", "family", "profile",
             "dorm", "archive"}
    assert {m["key"] for m in r["data"]["moduleCards"] if m["status"] == "LIVE"} == _live
    assert all(m["empty"] for m in r["data"]["moduleCards"] if m["key"] not in _live)

    # 学院学工：本院视图
    r2 = client.get("/api/v1/student-affairs/dashboard", headers=_hdr(client, "college_admin01")).json()
    assert r2["data"]["view"] == "COLLEGE_SA"

    # 辅导员：本班视图 + SCOPED，学生数=A 班 3 人
    r3 = client.get("/api/v1/student-affairs/dashboard", headers=_hdr(client, "counselor01")).json()
    assert r3["data"]["view"] == "COUNSELOR"
    assert r3["data"]["scopeMode"] == "SCOPED"
    stu = next(c["value"] for c in r3["data"]["summaryCards"] if c["key"] == "studentTotal")
    assert stu == 3


def test_class_scope_filter(client, db_mode):
    ids = _seed_classes(db_mode)
    # 学工处见 2 个班
    r = client.get("/api/v1/student-affairs/classes", headers=_hdr(client, "school_admin01")).json()
    assert r["code"] == 0 and len(r["data"]["items"]) == 2
    # 辅导员只见 A 班
    r2 = client.get("/api/v1/student-affairs/classes", headers=_hdr(client, "counselor01")).json()
    assert len(r2["data"]["items"]) == 1
    assert r2["data"]["items"][0]["classId"] == str(ids["A"])


def test_cadre_appoint_and_list(client, db_mode):
    ids = _seed_classes(db_mode)
    hdr = _hdr(client, "counselor01")
    body = {"studentId": "1", "position": "MONITOR", "termCode": "2026-1"}
    r = client.post(f"/api/v1/student-affairs/classes/{ids['A']}/cadres", json=body, headers=hdr).json()
    assert r["code"] == 0 and r["data"]["position"] == "MONITOR"
    # 历史欠账：任命/列表须带学生姓名+学号（此前只回 studentId 内部主键）。id=1 为基础种子学生赵一凡。
    assert r["data"]["studentName"] == "赵一凡" and r["data"]["studentNo"] == "2023115001"
    # 列表可见 + 带姓名学号
    r2 = client.get(f"/api/v1/student-affairs/classes/{ids['A']}/cadres", headers=hdr).json()
    assert len(r2["data"]["items"]) == 1
    assert r2["data"]["items"][0]["studentName"] == "赵一凡"
    assert r2["data"]["items"][0]["studentNo"] == "2023115001"
    # 同班同职务重复任命 → 409
    r3 = client.post(f"/api/v1/student-affairs/classes/{ids['A']}/cadres", json=body, headers=hdr)
    assert r3.status_code == 409


def test_counselor_cross_class_403(client, db_mode):
    ids = _seed_classes(db_mode)
    hdr = _hdr(client, "counselor01")
    # 辅导员访问不在范围的 B 班班干部 → 403（NO_DATA_SCOPE + 自动审计）
    r = client.get(f"/api/v1/student-affairs/classes/{ids['B']}/cadres", headers=hdr)
    assert r.status_code == 403
    assert r.json()["bizCode"] == "NO_DATA_SCOPE"
    # 越权任命同样被拒
    r2 = client.post(f"/api/v1/student-affairs/classes/{ids['B']}/cadres",
                     json={"studentId": "1", "position": "MONITOR"}, headers=hdr)
    assert r2.status_code == 403


def test_school_admin_any_class(client, db_mode):
    ids = _seed_classes(db_mode)
    hdr = _hdr(client, "school_admin01")
    # 学工处可对任意班任命
    r = client.post(f"/api/v1/student-affairs/classes/{ids['B']}/cadres",
                    json={"studentId": "9", "position": "STUDY"}, headers=hdr)
    assert r.json()["code"] == 0


def test_dashboard_todo_scoped_to_assignee(client, db_mode):
    """辅导员待办按统一待办可见性：仅本班池待办 + 本人指派；看不到他班池待办与他人指派。

    mock 令牌 userId=u_<数字>，与 workbench_todo_service._uid 解析一致。
    """
    ids = _seed_classes(db_mode)
    from app.core.security import create_access_token
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile, UnifiedTodo
    CA_UID, OTHER_UID = 61001, 61002
    db = get_sessionmaker()()
    sa = db.query(StudentProfile).filter_by(class_id=ids["A"]).first()
    sb = db.query(StudentProfile).filter_by(class_id=ids["B"]).first()
    assert sa and sb
    db.add(UnifiedTodo(
        tenant_id=TID, source_module="student-affairs", source_biz_type="LEAVE",
        source_biz_id=9101, todo_type="LEAVE_APPROVAL", assignee_id=0,
        student_id=sa.id, title="本班池待办", status="PENDING"))
    db.add(UnifiedTodo(
        tenant_id=TID, source_module="student-affairs", source_biz_type="LEAVE",
        source_biz_id=9102, todo_type="LEAVE_APPROVAL", assignee_id=0,
        student_id=sb.id, title="他班池待办", status="PENDING"))
    db.add(UnifiedTodo(
        tenant_id=TID, source_module="student-affairs", source_biz_type="LEAVE",
        source_biz_id=9103, todo_type="LEAVE_APPROVAL", assignee_id=OTHER_UID,
        student_id=sa.id, title="他人指派待办", status="PENDING"))
    db.add(UnifiedTodo(
        tenant_id=TID, source_module="student-affairs", source_biz_type="RISK",
        source_biz_id=9104, todo_type="RISK_HANDLE", assignee_id=CA_UID,
        student_id=sb.id, title="本人指派待办", status="PENDING"))
    db.commit()
    db.close()

    token = create_access_token({
        "userId": f"u_{CA_UID}", "loginName": "counselor01", "realName": "王莉",
        "userType": "TEACHER", "tid": "demo", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "COUNSELOR", "clientType": "PC"})
    hdr = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/student-affairs/dashboard", headers=hdr).json()
    assert r["code"] == 0
    todo = next(c["value"] for c in r["data"]["summaryCards"] if c["key"] == "pendingTodo")
    # 本班池 1 + 本人指派 1；他班池与他人指派不可见
    assert todo == 2
    assert r["data"]["scopeLabel"] in ("本人负责范围", "全校", "本院", "无数据范围")
    keys = {c["key"] for c in r["data"]["summaryCards"]}
    assert "dormException" not in keys
    assert "overdueLeave" in keys
    card = next(c for c in r["data"]["summaryCards"] if c["key"] == "pendingLeave")
    assert card.get("drillPath") == "/admin/campus-service/leave"


def test_dashboard_admin_scope_label_schoolwide(client, db_mode):
    _seed_classes(db_mode)
    r = client.get("/api/v1/student-affairs/dashboard", headers=_hdr(client, "school_admin01")).json()
    assert r["data"]["scopeLabel"] == "全校"
    assert r["data"]["scopeMode"] == "ADMIN_TENANT"
    # 学工管理员可见全校池待办口径：conftest 种子里无 assignee_id=0 的 PENDING，
    # 另有 assignee_id=1 的个人待办——mock 管理员 uid 不可解析时只计池待办，不得回退全量 PENDING
    todo = next(c["value"] for c in r["data"]["summaryCards"] if c["key"] == "pendingTodo")
    assert todo == 0
