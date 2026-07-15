"""13B-P2 学籍异动全链路 · 端到端（真实 DB 模式）。

SC1 休学全链→SUSPENDED+到期日；SC2 复学→REGISTERED；SC3 转专业迁院系班(状态不变)；
SC4 在途重复409；SC5 终态学生禁发起422；SC6 复学前置非休学409；SC7 驳回。
SC9+（Tier1 R1 补强）：辅导员/学院教务数据范围收敛 + 越权 403 + 异动统计端点。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=2, class_name="网络2101", grade="2021", status="ACTIVE")
    db.add(a); db.add(b); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="AA001", real_name="学籍甲", class_id=a.id,
                       college_id=10, major_id=1, current_stage="ON_CAMPUS",
                       student_status="NORMAL", status="ACTIVE")
    db.add(s); db.flush()
    ids = {"a": a.id, "b": b.id, "s": s.id}
    db.commit()
    db.close()
    return ids


def _submit(client, hdr, sid, ct, **extra):
    return client.post(f"{BASE}/status-changes", headers=hdr,
                       json={"studentId": str(sid), "changeType": ct, "reason": f"{ct}原因说明足够长", **extra})


def _approve(client, hdr, cid, times):
    r = None
    for _ in range(times):
        r = client.post(f"{BASE}/status-changes/{cid}/review", headers=hdr, json={"action": "APPROVE"})
    return r.json()


def _status(client, sid, hdr):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    st = db.get(StudentProfile, sid).student_status
    db.close()
    return st


def test_sc1_suspend_full_flow(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _submit(client, hdr, ids["s"], "SUSPEND").json()["data"]["changeId"]
    r = _approve(client, hdr, cid, 3)  # 辅导员→学院→教务处
    assert r["data"]["status"] == "EFFECTIVE" and r["data"]["toStatus"] == "SUSPENDED"
    assert r["data"]["expireDate"]  # 休学到期日已设(真实补充)
    assert _status(client, ids["s"], hdr) == "SUSPENDED"


def test_sc2_resume_after_suspend(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    c1 = _submit(client, hdr, ids["s"], "SUSPEND").json()["data"]["changeId"]
    _approve(client, hdr, c1, 3)
    c2 = _submit(client, hdr, ids["s"], "RESUME", toClassId=str(ids["a"])).json()["data"]["changeId"]
    r = _approve(client, hdr, c2, 3)
    assert r["data"]["toStatus"] == "REGISTERED"
    assert _status(client, ids["s"], hdr) == "REGISTERED"


def test_sc3_transfer_major_moves_org(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _submit(client, hdr, ids["s"], "TRANSFER_MAJOR",
                  toMajorId="2", toClassId=str(ids["b"]), toCollegeId="20").json()["data"]["changeId"]
    r = _approve(client, hdr, cid, 4)  # 辅导员→转出院→接收院→教务处
    assert r["data"]["status"] == "EFFECTIVE"
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    s = db.get(StudentProfile, ids["s"])
    # 转专业不改学籍状态字面，但迁移了院系班
    assert s.student_status == "REGISTERED" and s.class_id == ids["b"] and s.major_id == 2
    db.close()


def test_sc4_duplicate_active_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    _submit(client, hdr, ids["s"], "SUSPEND")
    assert _submit(client, hdr, ids["s"], "WITHDRAW").status_code == 409


def test_sc5_terminal_student_422(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _submit(client, hdr, ids["s"], "WITHDRAW").json()["data"]["changeId"]
    _approve(client, hdr, cid, 3)  # → WITHDRAWN(终态)
    assert _status(client, ids["s"], hdr) == "WITHDRAWN"
    # 终态学生再发起异动 → 422
    r = _submit(client, hdr, ids["s"], "SUSPEND")
    assert r.status_code == 400  # VALIDATION_ERROR→400


def test_sc6_resume_requires_suspended_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    # NORMAL 学生直接复学 → 409
    assert _submit(client, hdr, ids["s"], "RESUME").status_code == 409


def test_sc7_reject(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _submit(client, hdr, ids["s"], "SUSPEND").json()["data"]["changeId"]
    r = client.post(f"{BASE}/status-changes/{cid}/review", headers=hdr,
                    json={"action": "REJECT", "reason": "材料不齐，不予批准"}).json()
    assert r["data"]["status"] == "REJECTED"
    assert _status(client, ids["s"], hdr) == "NORMAL"  # 未生效，主档不变


def test_sc8_student_forbidden_403(client, db_mode):
    """越权红线（13B-FE-W2 学籍写侧接入波补齐）：学生令牌打异动/注册/名册端点一律 403（require_staff）。"""
    hdr = _hdr(client, "student01")
    assert client.post(f"{BASE}/status-changes", headers=hdr,
                       json={"studentId": "1", "changeType": "SUSPEND"}).status_code == 403
    assert client.get(f"{BASE}/status-changes", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/registration-batches", headers=hdr,
                       json={"batchName": "x"}).status_code == 403
    assert client.get(f"{BASE}/roster", headers=hdr).status_code == 403


# ═══════════ SC9+：Tier1 R1 数据范围收敛（辅导员限本班 / 学院教务限本院）═══════════

def _seed_scoped(db_mode):
    """在 SC1-8 基础上补：College/Major 实体（COLLEGE 范围解析链 Major.college_id→SchoolClass.major_id 依赖）
    + 辅导员(软件2101)/学院教务(软件学院) 的 TeacherStudentScope，另建一名"网络学院"学生供越权对照。"""
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    college_sw = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    college_wl = College(tenant_id=TID, college_name="网络学院", status="ACTIVE")
    db.add(college_sw); db.add(college_wl); db.flush()
    major_sw = Major(tenant_id=TID, college_id=college_sw.id, major_name="软件技术", status="ACTIVE")
    major_wl = Major(tenant_id=TID, college_id=college_wl.id, major_name="网络技术", status="ACTIVE")
    db.add(major_sw); db.add(major_wl); db.flush()
    a = SchoolClass(tenant_id=TID, major_id=major_sw.id, class_name="软件2101", grade="2021", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=major_wl.id, class_name="网络2101", grade="2021", status="ACTIVE")
    db.add(a); db.add(b); db.flush()
    s_in = StudentProfile(tenant_id=TID, student_no="AA010", real_name="范围甲", class_id=a.id,
                          college_id=college_sw.id, major_id=major_sw.id, current_stage="ON_CAMPUS",
                          student_status="NORMAL", status="ACTIVE")
    s_out = StudentProfile(tenant_id=TID, student_no="AA011", real_name="范围乙", class_id=b.id,
                           college_id=college_wl.id, major_id=major_wl.id, current_stage="ON_CAMPUS",
                           student_status="NORMAL", status="ACTIVE")
    db.add(s_in); db.add(s_out); db.flush()
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2101", status="ACTIVE"))
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="college_admin01", teacher_name="张晓明",
                               role_code="COLLEGE_ADMIN", scope_type="COLLEGE", ref_value="软件学院", status="ACTIVE"))
    db.commit()
    ids = {"collegeSw": college_sw.id, "collegeWl": college_wl.id, "classA": a.id, "classB": b.id,
           "sIn": s_in.id, "sOut": s_out.id}
    db.close()
    return ids


def test_sc9_counselor_reviews_own_class_only(client, db_mode):
    """辅导员对本班学生的休学申请可审（首节点 COUNSELOR_REVIEW）；对越权班学生的申请 403。"""
    ids = _seed_scoped(db_mode)
    admin_hdr = _hdr(client, "school_admin01")
    coun_hdr = _hdr(client, "counselor01")
    cid_in = _submit(client, admin_hdr, ids["sIn"], "SUSPEND").json()["data"]["changeId"]
    cid_out = _submit(client, admin_hdr, ids["sOut"], "SUSPEND").json()["data"]["changeId"]
    r = client.post(f"{BASE}/status-changes/{cid_in}/review", headers=coun_hdr, json={"action": "APPROVE"})
    assert r.status_code == 200 and r.json()["data"]["currentNode"] == "COLLEGE_REVIEW"
    r2 = client.post(f"{BASE}/status-changes/{cid_out}/review", headers=coun_hdr, json={"action": "APPROVE"})
    assert r2.status_code == 403


def test_sc10_college_admin_list_scoped_to_own_college(client, db_mode):
    """学院教务的异动列表只见本院（from/to 学院双向），越院学生的异动不出现。"""
    ids = _seed_scoped(db_mode)
    admin_hdr = _hdr(client, "school_admin01")
    _submit(client, admin_hdr, ids["sIn"], "SUSPEND")
    _submit(client, admin_hdr, ids["sOut"], "SUSPEND")
    college_hdr = _hdr(client, "college_admin01")
    r = client.get(f"{BASE}/status-changes", headers=college_hdr, params={"changeType": "SUSPEND"})
    assert r.status_code == 200
    names = {row["realName"] for row in r.json()["data"]["items"]}
    assert "范围甲" in names and "范围乙" not in names


def test_sc11_college_admin_submit_scoped_403(client, db_mode):
    """学院教务代录异动仅限本院学生；对越院学生发起 403002。"""
    ids = _seed_scoped(db_mode)
    college_hdr = _hdr(client, "college_admin01")
    r_ok = _submit(client, college_hdr, ids["sIn"], "WITHDRAW")
    assert r_ok.status_code == 200
    r_bad = _submit(client, college_hdr, ids["sOut"], "WITHDRAW")
    assert r_bad.status_code == 403


def test_sc12_office_final_requires_tenant_all(client, db_mode):
    """教务处终审节点(AA_OFFICE_FINAL)仅 TENANT_ALL 角色可处理；学院教务在终审节点越权 403。"""
    ids = _seed_scoped(db_mode)
    admin_hdr = _hdr(client, "school_admin01")
    coun_hdr = _hdr(client, "counselor01")
    college_hdr = _hdr(client, "college_admin01")
    cid = _submit(client, admin_hdr, ids["sIn"], "SUSPEND").json()["data"]["changeId"]
    r1 = client.post(f"{BASE}/status-changes/{cid}/review", headers=coun_hdr, json={"action": "APPROVE"})
    assert r1.status_code == 200  # COUNSELOR_REVIEW → COLLEGE_REVIEW
    r2 = client.post(f"{BASE}/status-changes/{cid}/review", headers=college_hdr, json={"action": "APPROVE"})
    assert r2.status_code == 200  # COLLEGE_REVIEW → AA_OFFICE_FINAL
    r3 = client.post(f"{BASE}/status-changes/{cid}/review", headers=college_hdr, json={"action": "APPROVE"})
    assert r3.status_code == 403  # 学院教务无权处理教务处终审节点


def test_sc13_stats_endpoint_scoped(client, db_mode):
    """异动统计端点：教务处全校聚合；学院教务仅见本院数据（范围与 list 一致）。"""
    ids = _seed_scoped(db_mode)
    admin_hdr = _hdr(client, "school_admin01")
    _submit(client, admin_hdr, ids["sIn"], "SUSPEND")
    _submit(client, admin_hdr, ids["sOut"], "WITHDRAW")
    r_admin = client.get(f"{BASE}/status-changes/stats", headers=admin_hdr)
    assert r_admin.status_code == 200
    d = r_admin.json()["data"]
    assert d["total"] >= 2
    types_admin = {g["key"] for g in d["byType"]}
    assert "SUSPEND" in types_admin and "WITHDRAW" in types_admin

    college_hdr = _hdr(client, "college_admin01")
    r_college = client.get(f"{BASE}/status-changes/stats", headers=college_hdr)
    assert r_college.status_code == 200
    d2 = r_college.json()["data"]
    types_college = {g["key"] for g in d2["byType"]}
    assert "SUSPEND" in types_college and "WITHDRAW" not in types_college


def test_sc14_counselor_no_apply_permission(client, db_mode):
    """辅导员未被授予发起权限（仅审核节点权限），POST /status-changes → 403。"""
    ids = _seed_scoped(db_mode)
    coun_hdr = _hdr(client, "counselor01")
    r = _submit(client, coun_hdr, ids["sIn"], "SUSPEND")
    assert r.status_code == 403


# ═══════════ SC15+（学籍异动三级模块续工·第三轮补缺）：转班(TRANSFER_CLASS) + 留级(RETAIN)申请入口 ═══════════

def _seed_transfer_class(db_mode):
    """转班测试专用种子：同专业两班（软件2101当前班 / 软件2102目标班）+ 另一专业一班（网络2101，跨专业对照）。"""
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE", class_status="NORMAL")
    a2 = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2102", grade="2021", status="ACTIVE", class_status="NORMAL")
    b = SchoolClass(tenant_id=TID, major_id=2, class_name="网络2101", grade="2021", status="ACTIVE", class_status="NORMAL")
    db.add(a); db.add(a2); db.add(b); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="AA020", real_name="转班甲", class_id=a.id,
                       college_id=10, major_id=1, current_stage="ON_CAMPUS",
                       student_status="NORMAL", status="ACTIVE")
    db.add(s); db.flush()
    ids = {"a": a.id, "a2": a2.id, "b": b.id, "s": s.id}
    db.commit()
    db.close()
    return ids


def test_sc15_transfer_class_same_major_flow(client, db_mode):
    """转班全链路：同专业换班，三节点(辅导员→学院→教务处)审批后生效；class_id 变、major/college 不变。"""
    ids = _seed_transfer_class(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _submit(client, hdr, ids["s"], "TRANSFER_CLASS", toClassId=str(ids["a2"])).json()["data"]["changeId"]
    r = _approve(client, hdr, cid, 3)
    assert r["data"]["status"] == "EFFECTIVE" and r["data"]["toStatus"] == "REGISTERED"
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    s = db.get(StudentProfile, ids["s"])
    assert s.class_id == ids["a2"] and s.major_id == 1 and s.college_id == 10
    db.close()


def test_sc16_transfer_class_cross_major_rejected(client, db_mode):
    """转班校验：目标班跨专业 → 拒绝（应引导改用「转专业申请」）。"""
    ids = _seed_transfer_class(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = _submit(client, hdr, ids["s"], "TRANSFER_CLASS", toClassId=str(ids["b"]))
    assert r.status_code == 400  # VALIDATION_ERROR→400


def test_sc17_transfer_class_same_class_conflict_409(client, db_mode):
    """转班校验：目标班=当前班 → 409。"""
    ids = _seed_transfer_class(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = _submit(client, hdr, ids["s"], "TRANSFER_CLASS", toClassId=str(ids["a"]))
    assert r.status_code == 409


def test_sc18_transfer_class_missing_target_rejected(client, db_mode):
    """转班校验：不填目标班级 → 拒绝。"""
    ids = _seed_transfer_class(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = _submit(client, hdr, ids["s"], "TRANSFER_CLASS")
    assert r.status_code == 400


def test_sc19_retain_full_flow(client, db_mode):
    """留级(RETAIN，「保留学籍申请」分类入口底层类型)全链路首次端到端覆盖：两节点(学院→教务处)。
    NORMAL→RETAINED 不在 change_student_status() 合法转移白名单内（真实业务：留级认定针对已注册在读
    学生，非入学未注册状态），故本测试起点造 REGISTERED 学生，不复用别测试的 NORMAL 起点种子。"""
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    db.add(a); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="AA021", real_name="留级甲", class_id=a.id,
                       college_id=10, major_id=1, current_stage="ON_CAMPUS",
                       student_status="REGISTERED", status="ACTIVE")
    db.add(s); db.flush()
    sid = s.id
    db.commit()
    db.close()
    hdr = _hdr(client, "school_admin01")
    cid = _submit(client, hdr, sid, "RETAIN").json()["data"]["changeId"]
    r = _approve(client, hdr, cid, 2)  # 学院→教务处
    assert r["data"]["status"] == "EFFECTIVE" and r["data"]["toStatus"] == "RETAINED"
    assert _status(client, sid, hdr) == "RETAINED"
