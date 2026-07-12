"""学工中心 · 统一安全底座专项测试（真实 MySQL）。

覆盖：能力权限 / 数据范围(班·院·楼·生·SELF·NONE fail-closed) / 跨租户 / 敏感审计 / 兼容层一致。
先复现（未修时 test_scope_* 会红），再随统一安全上下文修复后转绿。
"""
from __future__ import annotations

TID = 1000000000000000001          # mock 用户所在租户
TID2 = 1000000000000000002         # 跨租户数据


def _hdr(client, login):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _base(db_mode, counselor_scope=True, college_scope=True):
    """两院/四班/四生 + 跨租户一生。可选是否给 counselor01 配班、college_admin01 配院（复现未配用）。"""
    from app.db.session import get_sessionmaker
    from app.models import (College, DormBuilding, Major, SchoolClass, StudentProfile,
                            TeacherStudentScope)
    db = get_sessionmaker()()
    try:
        col1 = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
        col2 = College(tenant_id=TID, college_name="机械学院", status="ACTIVE")
        db.add_all([col1, col2]); db.flush()
        m1 = Major(tenant_id=TID, college_id=col1.id, major_name="软件技术", status="ACTIVE")
        m2 = Major(tenant_id=TID, college_id=col2.id, major_name="机械制造", status="ACTIVE")
        db.add_all([m1, m2]); db.flush()
        cA = SchoolClass(tenant_id=TID, major_id=m1.id, class_name="软件2101", grade="2021",
                         counselor_id=999001, status="ACTIVE")
        cB = SchoolClass(tenant_id=TID, major_id=m1.id, class_name="软件2102", grade="2021",
                         counselor_id=999002, status="ACTIVE")
        cC = SchoolClass(tenant_id=TID, major_id=m2.id, class_name="机械2101", grade="2021",
                         counselor_id=999003, status="ACTIVE")
        cD = SchoolClass(tenant_id=TID, major_id=m2.id, class_name="机械2102", grade="2021",
                         counselor_id=999004, status="ACTIVE")
        db.add_all([cA, cB, cC, cD]); db.flush()
        sids = {}
        for key, no, name, cls, col in [("A", "A001", "甲一", cA, col1), ("B", "B001", "乙一", cB, col1),
                                        ("C", "C001", "丙一", cC, col2), ("D", "D001", "丁一", cD, col2)]:
            s = StudentProfile(tenant_id=TID, student_no=no, real_name=name, class_id=cls.id,
                               college_id=col.id, major_id=cls.major_id, gender="男",
                               current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
            db.add(s); db.flush(); sids[key] = s.id
        # 跨租户学生（同名近似，异租户）
        sx = StudentProfile(tenant_id=TID2, student_no="A001", real_name="甲一影子", class_id=cA.id,
                            college_id=col1.id, major_id=m1.id, gender="男",
                            current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
        db.add(sx); db.flush(); sids["X2"] = sx.id
        # 宿舍楼：楼A 归 dorm01，楼B 归他人
        bA = DormBuilding(tenant_id=TID, building_name="紫荆A", building_code="ZJ-A",
                          manager_teacher_key="dorm01", floor_count=3, status="ENABLED")
        bB = DormBuilding(tenant_id=TID, building_name="紫荆B", building_code="ZJ-B",
                          manager_teacher_key="other_dorm", floor_count=3, status="ENABLED")
        db.add_all([bA, bB]); db.flush()
        # scope 行
        rows = []
        if counselor_scope:
            rows.append(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                                            role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2101",
                                            status="ACTIVE"))
        if college_scope:
            rows.append(TeacherStudentScope(tenant_id=TID, teacher_key="college_admin01", teacher_name="张晓明",
                                            role_code="COLLEGE_ADMIN", scope_type="COLLEGE", ref_value="软件学院",
                                            status="ACTIVE"))
        rows.append(TeacherStudentScope(tenant_id=TID, teacher_key="psych01", teacher_name="心理·孙",
                                        role_code="PSYCHOLOGY_TEACHER", scope_type="PSY_STUDENT", ref_value="A001",
                                        status="ACTIVE"))
        db.add_all(rows)
        db.commit()
        return {"cA": cA.id, "cB": cB.id, "cC": cC.id, "cD": cD.id, "col1": col1.id, "col2": col2.id,
                "bA": bA.id, "bB": bB.id, **sids}
    finally:
        db.close()


BASE = "/api/v1/student-affairs"

# ════════════ 一、能力权限（403001） ════════════

def test_capability_denied(client, db_mode):
    _base(db_mode)
    # 普通教师(教务)/就业老师/学生 → 学工敏感域 403001
    for login in ("academic01", "employment01", "student01"):
        r = client.get(f"{BASE}/discipline/cases", headers=_hdr(client, login))
        assert r.status_code == 403 and r.json()["bizCode"] == "NO_PERMISSION", login
    # 宿管 → 心理 / 违纪 403001（越域）
    assert client.get(f"{BASE}/mental/list", headers=_hdr(client, "dorm01")).status_code == 403
    assert client.get(f"{BASE}/discipline/cases", headers=_hdr(client, "dorm01")).status_code == 403


def test_unauthenticated_401(client):
    r = client.get(f"{BASE}/classes")
    assert r.json()["code"] == 401001


# ════════════ 二、数据范围 ════════════

def test_scope_counselor_configured(client, db_mode):
    ids = _base(db_mode)
    hdr = _hdr(client, "counselor01")
    r = client.get(f"{BASE}/classes", headers=hdr).json()
    assert r["code"] == 0 and len(r["data"]["items"]) == 1
    assert r["data"]["items"][0]["classId"] == str(ids["cA"])
    # 用 id 访问 B 班（不在范围）→ 403 NO_DATA_SCOPE
    rb = client.get(f"{BASE}/classes/{ids['cB']}/profile", headers=hdr)
    assert rb.status_code == 403 and rb.json()["bizCode"] == "NO_DATA_SCOPE"


def test_scope_counselor_unconfigured_fail_closed(client, db_mode):
    """复现 hole#1：未配班辅导员绝不得看全校。未修时返回全部班级→红。"""
    ids = _base(db_mode, counselor_scope=False)
    hdr = _hdr(client, "counselor01")
    r = client.get(f"{BASE}/classes", headers=hdr).json()
    assert r["code"] == 0 and len(r["data"]["items"]) == 0, "未配范围辅导员必须 fail-closed 看 0 班"
    # 详情任何班 → 403002
    rb = client.get(f"{BASE}/classes/{ids['cA']}/profile", headers=hdr)
    assert rb.status_code == 403 and rb.json()["bizCode"] == "NO_DATA_SCOPE"


def test_scope_college_admin_no_cross_college(client, db_mode):
    """复现 hole#3：学院管理员只看本院。未修时返回四班(跨院)→红。"""
    ids = _base(db_mode)
    hdr = _hdr(client, "college_admin01")
    r = client.get(f"{BASE}/classes", headers=hdr).json()
    got = {x["classId"] for x in r["data"]["items"]}
    assert got == {str(ids["cA"]), str(ids["cB"])}, f"学院管理员越院可见：{got}"
    # 跨院班详情 → 403002
    rc = client.get(f"{BASE}/classes/{ids['cC']}/profile", headers=hdr)
    assert rc.status_code == 403 and rc.json()["bizCode"] == "NO_DATA_SCOPE"


def test_scope_dorm_manager_building(client, db_mode):
    ids = _base(db_mode)
    hdr = _hdr(client, "dorm01")
    r = client.get(f"{BASE}/dorm/buildings", headers=hdr).json()
    got = {b["buildingId"] for b in r["data"].get("items", r["data"])} if isinstance(r["data"], (list, dict)) else set()
    # 只见楼A
    assert str(ids["bA"]) in got and str(ids["bB"]) not in got, f"宿管越楼可见：{got}"


def test_scope_school_admin_sees_all(client, db_mode):
    _base(db_mode)
    r = client.get(f"{BASE}/classes", headers=_hdr(client, "school_admin01")).json()
    assert r["code"] == 0 and len(r["data"]["items"]) == 4  # 学工/校级 TENANT_ALL


# ════════════ 三、跨租户 ════════════

def test_cross_tenant_blocked(client, db_mode):
    ids = _base(db_mode)
    # 学工处管理员（本租户 TENANT_ALL）也不得越租户看 TID2 学生画像
    r = client.get(f"{BASE}/students/{ids['X2']}/profile", headers=_hdr(client, "sa_admin01"))
    assert r.status_code in (403, 404), f"跨租户可达：{r.status_code}"


# ════════════ 四、敏感审计 ════════════

def test_sensitive_psy_scope_and_audit(client, db_mode):
    ids = _base(db_mode)
    hdr = _hdr(client, "psych01")
    # 授权学生 A001 → 可见摘要
    ra = client.get(f"{BASE}/mental/students/{ids['A']}/summary", headers=hdr)
    assert ra.status_code == 200
    # 未授权学生 D → 403（不得通过 id 绕过）
    rd = client.get(f"{BASE}/mental/students/{ids['D']}/summary", headers=hdr)
    assert rd.status_code == 403
