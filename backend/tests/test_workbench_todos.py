"""工作台·待办与消息读端真实化回归（services/workbench_todo_service）。

锁住的核心性质（此前 api/v1/todos.py 直接返回静态 MOCK_TODOS，以下性质全部不成立）：
  1. 待办来自真库 t_unified_todo，不是静态样例；
  2. 学院池待办（assignee_id=0）必须按数据范围收敛——辅导员看不到别的班的池待办；
  3. 未配数据范围的教职工 fail-closed：只看得到明确指派给自己的，池待办一律不可见；
  4. 跨租户不可见；
  5. 计数（红点角标）与列表同口径；
  6. 完成待办真实落库且不可重复完成；
  7. 消息按 receiver_id 收敛，别人的消息不可见。
"""
from __future__ import annotations

MAIN = 1000000000000000001
OTHER = 1000000000000000009

# 令牌 userId 用 u_ 前缀：_uid() 剥离后得到数字 ID；避免 db- 前缀触发 validate_token_subject 查库。
CA_UID, CB_UID = 51001, 51002


def _token(user_id, login_name, role="COUNSELOR", user_type="TEACHER", tenant_id=MAIN):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u_{user_id}", "loginName": login_name, "realName": f"姓名{user_id}",
        "userType": user_type, "tid": "demo", "tenantId": str(tenant_id),
        "activeContextId": "ctx", "currentRoleCode": role, "clientType": "PC"})}


def _seed(_db_mode):
    """两个班各一名学生；辅导员A 只带软件2301班，辅导员B 只带机电2301班。
    造 4 条待办：A班池 / B班池 / 指派给A本人 / 他租户池。"""
    from app.db.session import get_sessionmaker
    from app.models import (SchoolClass, StudentProfile, TeacherStudentScope, UnifiedMessage,
                            UnifiedTodo)
    db = get_sessionmaker()()
    try:
        ca = SchoolClass(tenant_id=MAIN, major_id=1, class_name="软件2301班", status="ACTIVE")
        cb = SchoolClass(tenant_id=MAIN, major_id=1, class_name="机电2301班", status="ACTIVE")
        db.add_all([ca, cb])
        db.flush()

        sa = StudentProfile(tenant_id=MAIN, student_no="WB0001", real_name="甲一", grade="2023",
                            class_id=ca.id, current_stage="ON_CAMPUS", student_status="NORMAL",
                            status="ACTIVE")
        sb = StudentProfile(tenant_id=MAIN, student_no="WB0002", real_name="乙二", grade="2023",
                            class_id=cb.id, current_stage="ON_CAMPUS", student_status="NORMAL",
                            status="ACTIVE")
        db.add_all([sa, sb])
        db.flush()

        # 数据范围：按工号（teacher_key）绑定，不依赖姓名
        db.add_all([
            TeacherStudentScope(tenant_id=MAIN, teacher_key="counselorA", teacher_name="辅导员A",
                                role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2301班",
                                status="ACTIVE"),
            TeacherStudentScope(tenant_id=MAIN, teacher_key="counselorB", teacher_name="辅导员B",
                                role_code="COUNSELOR", scope_type="CLASS", ref_value="机电2301班",
                                status="ACTIVE"),
        ])

        todos = [
            UnifiedTodo(tenant_id=MAIN, source_module="student-affairs", source_biz_type="LEAVE",
                        source_biz_id=9001, todo_type="LEAVE_APPROVAL", assignee_id=0,
                        student_id=sa.id, title="A班池待办：甲一请假待审", status="PENDING"),
            UnifiedTodo(tenant_id=MAIN, source_module="student-affairs", source_biz_type="LEAVE",
                        source_biz_id=9002, todo_type="LEAVE_APPROVAL", assignee_id=0,
                        student_id=sb.id, title="B班池待办：乙二请假待审", status="PENDING"),
            UnifiedTodo(tenant_id=MAIN, source_module="student-affairs", source_biz_type="RISK",
                        source_biz_id=9003, todo_type="RISK_HANDLE", assignee_id=CA_UID,
                        student_id=sb.id, title="指派给A本人的风险处置", status="PENDING"),
            UnifiedTodo(tenant_id=OTHER, source_module="student-affairs", source_biz_type="LEAVE",
                        source_biz_id=9004, todo_type="LEAVE_APPROVAL", assignee_id=0,
                        student_id=sa.id, title="他租户池待办", status="PENDING"),
        ]
        db.add_all(todos)
        db.add_all([
            UnifiedMessage(tenant_id=MAIN, receiver_id=CA_UID, title="给A的消息",
                           content="内容A", message_type="SYSTEM", status="UNREAD"),
            UnifiedMessage(tenant_id=MAIN, receiver_id=CB_UID, title="给B的消息",
                           content="内容B", message_type="SYSTEM", status="UNREAD"),
        ])
        db.commit()
        return {"sa": sa.id, "sb": sb.id}
    finally:
        db.close()


def _titles(resp):
    return [x["title"] for x in resp["data"]["items"]]


def test_pool_todo_converges_by_class_scope(client, db_mode):
    """辅导员A 只应看到本班池待办 + 指派给本人的；B 班池待办不可见。"""
    _seed(db_mode)
    r = client.get("/api/v1/admin/todos", headers=_token(CA_UID, "counselorA")).json()
    assert r["code"] == 0, r
    titles = _titles(r)
    assert "A班池待办：甲一请假待审" in titles
    assert "指派给A本人的风险处置" in titles
    assert "B班池待办：乙二请假待审" not in titles, "跨班级池待办泄漏"


def test_other_counselor_sees_only_own_class(client, db_mode):
    """辅导员B 只看到本班池待办，看不到 A 班的，也看不到指派给 A 的。"""
    _seed(db_mode)
    r = client.get("/api/v1/admin/todos", headers=_token(CB_UID, "counselorB")).json()
    assert r["code"] == 0, r
    titles = _titles(r)
    assert "B班池待办：乙二请假待审" in titles
    assert "A班池待办：甲一请假待审" not in titles
    assert "指派给A本人的风险处置" not in titles, "他人指派待办泄漏"


def test_cross_tenant_todo_invisible(client, db_mode):
    """他租户的池待办在任何角色下都不可见。"""
    _seed(db_mode)
    for uid, key in ((CA_UID, "counselorA"), (CB_UID, "counselorB")):
        r = client.get("/api/v1/admin/todos", headers=_token(uid, key)).json()
        assert "他租户池待办" not in _titles(r), "跨租户待办泄漏"


def test_unscoped_teacher_fail_closed(client, db_mode):
    """未配数据范围的教职工：池待办一律不可见（只可能看到明确指派给自己的）。"""
    _seed(db_mode)
    r = client.get("/api/v1/admin/todos", headers=_token(59999, "no_scope_teacher")).json()
    assert r["code"] == 0, r
    titles = _titles(r)
    assert "A班池待办：甲一请假待审" not in titles
    assert "B班池待办：乙二请假待审" not in titles


def test_count_matches_list(client, db_mode):
    """红点角标与列表同口径：count.total == PENDING 列表条数。"""
    _seed(db_mode)
    h = _token(CA_UID, "counselorA")
    lst = client.get("/api/v1/admin/todos", headers=h, params={"status": "PENDING"}).json()
    cnt = client.get("/api/v1/admin/todos/count", headers=h).json()
    assert cnt["code"] == 0, cnt
    assert cnt["data"]["total"] == lst["data"]["total"], (cnt["data"], lst["data"]["total"])
    assert sum(cnt["data"]["byType"].values()) == cnt["data"]["total"]


def test_complete_todo_persists_and_is_idempotent(client, db_mode):
    """完成待办真实落库；重复完成返回冲突而不是静默成功。"""
    _seed(db_mode)
    h = _token(CA_UID, "counselorA")
    lst = client.get("/api/v1/admin/todos", headers=h, params={"status": "PENDING"}).json()
    tid = next(x["todoId"] for x in lst["data"]["items"] if x["title"].startswith("A班池待办"))

    ok = client.post(f"/api/v1/admin/todos/{tid}/complete", headers=h, json={}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "DONE", ok

    again = client.post(f"/api/v1/admin/todos/{tid}/complete", headers=h, json={}).json()
    assert again["code"] != 0, "重复完成必须冲突"

    after = client.get("/api/v1/admin/todos", headers=h, params={"status": "PENDING"}).json()
    assert tid not in [x["todoId"] for x in after["data"]["items"]], "完成后仍出现在待处理列表"


def test_todo_detail_cross_scope_is_not_found(client, db_mode):
    """越范围取详情返回 404（不泄漏该待办是否存在）。"""
    _seed(db_mode)
    ha = _token(CA_UID, "counselorA")
    hb = _token(CB_UID, "counselorB")
    lst = client.get("/api/v1/admin/todos", headers=ha).json()
    tid = next(x["todoId"] for x in lst["data"]["items"] if x["title"].startswith("A班池待办"))
    r = client.get(f"/api/v1/admin/todos/{tid}", headers=hb).json()
    assert r["code"] != 0, "他人范围内的待办详情不应可读"


def test_summary_converges_by_scope(client, db_mode):
    """/api/v1/todos/summary（前端角标）必须按人收敛，不能返回全校待办数。

    修复前 db_service.todo_summary() 只过滤 tenant_id：本用例中辅导员A 可见 2 条，
    但全租户 PENDING 有 3 条（含 B 班池待办），旧口径会把 3 报给 A。
    """
    _seed(db_mode)
    a = client.get("/api/v1/todos/summary", headers=_token(CA_UID, "counselorA")).json()
    b = client.get("/api/v1/todos/summary", headers=_token(CB_UID, "counselorB")).json()
    assert a["code"] == 0 and b["code"] == 0, (a, b)
    lst_a = client.get("/api/v1/admin/todos", headers=_token(CA_UID, "counselorA"),
                       params={"status": "PENDING"}).json()
    assert a["data"]["pending"] == lst_a["data"]["total"], (a["data"], lst_a["data"]["total"])
    # A 与 B 可见集合不同 → 汇总数不应相同（旧的全校口径会让两者相等）
    assert a["data"]["pending"] != b["data"]["pending"] or a["data"]["pending"] == 0


def test_cannot_complete_others_todo_via_simple_endpoint(client, db_mode):
    """/api/v1/todos/{id}/done 必须做归属校验。

    修复前 db_service.todo_done() 只按 id+tenant 更新状态，任意教职工凭 ID 即可完成他人待办。
    """
    _seed(db_mode)
    ha = _token(CA_UID, "counselorA")
    hb = _token(CB_UID, "counselorB")
    lst = client.get("/api/v1/admin/todos", headers=ha, params={"status": "PENDING"}).json()
    tid = next(x["todoId"] for x in lst["data"]["items"] if x["title"].startswith("A班池待办"))

    deny = client.post(f"/api/v1/todos/{tid}/done", headers=hb).json()
    assert deny["code"] != 0, "B 不应能完成 A 范围内的待办"

    still = client.get("/api/v1/admin/todos", headers=ha, params={"status": "PENDING"}).json()
    assert tid in [x["todoId"] for x in still["data"]["items"]], "越权调用后待办状态被改动"


def test_messages_converge_by_receiver(client, db_mode):
    """消息按 receiver_id 收敛：A 只看到给 A 的。"""
    _seed(db_mode)
    r = client.get("/api/v1/admin/messages", headers=_token(CA_UID, "counselorA")).json()
    assert r["code"] == 0, r
    titles = [x["title"] for x in r["data"]["items"]]
    assert "给A的消息" in titles
    assert "给B的消息" not in titles, "他人消息泄漏"
    cnt = client.get("/api/v1/admin/messages/count", headers=_token(CA_UID, "counselorA")).json()
    assert cnt["data"]["unread"] >= 1
