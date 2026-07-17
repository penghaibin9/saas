"""学生主档目录 /students 数据范围收敛专项测试（真实 MySQL）。

对应总闸门欠账「学生选择器的数据范围提示与后端不符」（2026-07-16 登记）：
前端 AppStudentPicker 提示「仅显示你数据范围内的学生」，此前后端 /students 仅
require_staff + 租户过滤，辅导员可搜全校学生。本组测试锁定 SEC 收敛口径：

- 辅导员(CLASS)：仅本班学生；未配 scope → fail-closed 空；跨班详情/写 403002。
- 学院管理员(COLLEGE)：仅本院学生；跨院 403002。
- 心理教师(PSY_STUDENT)：仅授权学生。
- 学工处/校管理员(TENANT_ALL)：全租户不受影响（防误伤回归）。
- 其他域角色（毕设/实习/就业等）目录语义本轮不收敛，不在此测试范围。
"""
from __future__ import annotations

TID = 1000000000000000001


def _hdr(client, login):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _base(db_mode, counselor_scope=True):
    """两院/两班/三生：软件2101(A001) 软件学院、机械2101(C001,C002) 机械学院。"""
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    try:
        col1 = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
        col2 = College(tenant_id=TID, college_name="机械学院", status="ACTIVE")
        db.add_all([col1, col2]); db.flush()
        m1 = Major(tenant_id=TID, college_id=col1.id, major_name="软件技术", status="ACTIVE")
        m2 = Major(tenant_id=TID, college_id=col2.id, major_name="机械制造", status="ACTIVE")
        db.add_all([m1, m2]); db.flush()
        cA = SchoolClass(tenant_id=TID, major_id=m1.id, class_name="软件2101", grade="2021", status="ACTIVE")
        cC = SchoolClass(tenant_id=TID, major_id=m2.id, class_name="机械2101", grade="2021", status="ACTIVE")
        db.add_all([cA, cC]); db.flush()
        sids = {}
        for key, no, name, cls, col in [("A", "A001", "甲一", cA, col1),
                                        ("C", "C001", "丙一", cC, col2),
                                        ("C2", "C002", "丙二", cC, col2)]:
            s = StudentProfile(tenant_id=TID, student_no=no, real_name=name, class_id=cls.id,
                               college_id=col.id, major_id=cls.major_id, gender="男",
                               current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
            db.add(s); db.flush(); sids[key] = s.id
        rows = [TeacherStudentScope(tenant_id=TID, teacher_key="psych01", teacher_name="心理·孙",
                                    role_code="PSYCHOLOGY_TEACHER", scope_type="PSY_STUDENT",
                                    ref_value="A001", status="ACTIVE"),
                TeacherStudentScope(tenant_id=TID, teacher_key="college_admin01", teacher_name="张晓明",
                                    role_code="COLLEGE_ADMIN", scope_type="COLLEGE",
                                    ref_value="软件学院", status="ACTIVE")]
        if counselor_scope:
            rows.append(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                                            role_code="COUNSELOR", scope_type="CLASS",
                                            ref_value="软件2101", status="ACTIVE"))
        db.add_all(rows)
        db.commit()
        return sids
    finally:
        db.close()


def _list_nos(client, hdr, **params):
    r = client.get("/api/v1/students", headers=hdr, params={"pageSize": 100, **params}).json()
    assert r["code"] == 0
    return {x["studentNo"] for x in r["data"]["items"]}


def test_counselor_list_only_own_class(client, db_mode):
    """辅导员列表/搜索仅见本班；跨班关键词搜索必须搜不到。"""
    _base(db_mode)
    hdr = _hdr(client, "counselor01")
    assert _list_nos(client, hdr) == {"A001"}
    assert _list_nos(client, hdr, keyword="丙一") == set(), "辅导员不得搜到跨班学生"


def test_counselor_cross_class_detail_and_write_403(client, db_mode):
    ids = _base(db_mode)
    hdr = _hdr(client, "counselor01")
    ok = client.get(f"/api/v1/students/{ids['A']}", headers=hdr)
    assert ok.json()["code"] == 0
    for path in (f"/api/v1/students/{ids['C']}",
                 f"/api/v1/students/{ids['C']}/timeline",
                 f"/api/v1/students/{ids['C']}/risk-summary"):
        r = client.get(path, headers=hdr)
        assert r.status_code == 403 and r.json()["bizCode"] == "NO_DATA_SCOPE", path
    w = client.put(f"/api/v1/students/{ids['C']}", headers=hdr, json={"realName": "改名"})
    assert w.status_code == 403 and w.json()["bizCode"] == "NO_DATA_SCOPE"
    v = client.post(f"/api/v1/students/{ids['C']}/void", headers=hdr, json={"reason": "越权作废尝试"})
    assert v.status_code == 403 and v.json()["bizCode"] == "NO_DATA_SCOPE"


def test_counselor_unconfigured_fail_closed(client, db_mode):
    """未配 scope 的辅导员绝不回退全租户：列表空、详情 403002。"""
    ids = _base(db_mode, counselor_scope=False)
    hdr = _hdr(client, "counselor01")
    assert _list_nos(client, hdr) == set()
    r = client.get(f"/api/v1/students/{ids['A']}", headers=hdr)
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_DATA_SCOPE"


def test_college_admin_only_own_college(client, db_mode):
    ids = _base(db_mode)
    hdr = _hdr(client, "college_admin01")
    assert _list_nos(client, hdr) == {"A001"}
    r = client.get(f"/api/v1/students/{ids['C']}", headers=hdr)
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_DATA_SCOPE"


def test_psych_teacher_only_authorized_students(client, db_mode):
    ids = _base(db_mode)
    hdr = _hdr(client, "psych01")
    assert _list_nos(client, hdr) == {"A001"}
    r = client.get(f"/api/v1/students/{ids['C']}", headers=hdr)
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_DATA_SCOPE"


def test_counselor_export_scoped(client, db_mode):
    """学生主档导出与目录同口径：辅导员只能导出本班（堵导出旁路）。"""
    _base(db_mode)
    hdr = _hdr(client, "counselor01")
    t = client.post("/api/v1/export/students", headers=hdr,
                    json={"purpose": "本班学生名单核对"}).json()
    assert t["code"] == 0 and t["data"]["rowCount"] == 1, t


def test_tenant_all_roles_unaffected(client, db_mode):
    """学工处/校管理员照旧全租户；防收敛误伤回归。"""
    ids = _base(db_mode)
    for login in ("school_admin01", "sa_admin01"):
        hdr = _hdr(client, login)
        nos = _list_nos(client, hdr)
        # 应用启动可能播沙箱种子学生，故断言包含而非全等：跨院三生全部可见即未误伤
        assert {"A001", "C001", "C002"} <= nos, f"{login} 全租户角色被误收敛: {nos}"
        assert client.get(f"/api/v1/students/{ids['C']}", headers=hdr).json()["code"] == 0, login
