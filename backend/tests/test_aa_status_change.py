"""13B-P2 学籍异动全链路 · 端到端（真实 DB 模式）。

SC1 休学全链→SUSPENDED+到期日；SC2 复学→REGISTERED；SC3 转专业迁院系班(状态不变)；
SC4 在途重复409；SC5 终态学生禁发起422；SC6 复学前置非休学409；SC7 驳回。
SC9+（Tier1 R1 补强）：辅导员/学院教务数据范围收敛 + 越权 403 + 异动统计端点。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


import pytest

_TOKEN_CACHE: dict[str, dict] = {}


@pytest.fixture(autouse=True)
def _reset_token_cache():
    """db_mode 每个用例重建 schema，上一用例的令牌随 token_store 一起失效，必须逐例清空。"""
    _TOKEN_CACHE.clear()
    yield
    _TOKEN_CACHE.clear()


def _hdr(client, login_name):
    """同一用例内复用令牌：逐节点审批会多次取头，反复调登录会撞上登录频次/锁定阈值。"""
    cached = _TOKEN_CACHE.get(login_name)
    if cached:
        return cached
    body = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()
    data = body.get("data")
    assert data, f"mock-login {login_name} failed: {body}"
    header = {"Authorization": f"Bearer {data['accessToken']}"}
    _TOKEN_CACHE[login_name] = header
    return header


_COLLEGE_NAME = "软件学院"

# 包 5 收口后，审批任务有明确受理人：每个节点只能由它真实的受理人办理，
# 校管理员不再能一个人把三级审批全点完（职责分离）。
_NODE_LOGIN = {
    "COUNSELOR_REVIEW": "counselor01",
    "COLLEGE_REVIEW": "college_admin01",
    "OUT_COLLEGE_REVIEW": "college_admin01",
    "IN_COLLEGE_REVIEW": "college_admin01",
    "COLLEGE_ASSIGN_CLASS": "college_admin01",
    "AA_OFFICE_FINAL": "school_admin01",
}


def _seed_reviewers(db, *, class_ids, college_ids):
    """当前学期 + 真实审批账号 + 辅导员/学院教务的数据范围，缺一不可（全部 fail-closed）。"""
    from app.models import College, SchoolClass, TeacherStudentScope
    from tests.support_status_change_identity import seed_status_change_identity

    seed_status_change_identity(db, class_ids=class_ids, college_ids=college_ids)
    for class_id in class_ids:
        row = db.get(SchoolClass, int(class_id))
        if row is not None:
            db.add(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                                       role_code="COUNSELOR", scope_type="CLASS",
                                       ref_value=row.class_name, status="ACTIVE"))
    for college_id in college_ids:
        row = db.get(College, int(college_id))
        if row is not None:
            db.add(TeacherStudentScope(tenant_id=TID, teacher_key="college_admin01",
                                       teacher_name="张晓明", role_code="COLLEGE_ADMIN",
                                       scope_type="COLLEGE", ref_value=row.college_name,
                                       status="ACTIVE"))
    db.flush()


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass, StudentProfile
    db = get_sessionmaker()()
    college_sw = College(tenant_id=TID, college_name=_COLLEGE_NAME, status="ACTIVE")
    college_net = College(tenant_id=TID, college_name="网络学院", status="ACTIVE")
    db.add(college_sw); db.add(college_net); db.flush()
    major_sw = Major(tenant_id=TID, college_id=college_sw.id, major_name="软件技术", status="ACTIVE")
    major_net = Major(tenant_id=TID, college_id=college_net.id, major_name="网络技术", status="ACTIVE")
    db.add(major_sw); db.add(major_net); db.flush()
    a = SchoolClass(tenant_id=TID, major_id=major_sw.id, class_name="软件2101", grade="2021", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=major_net.id, class_name="网络2101", grade="2021", status="ACTIVE")
    db.add(a); db.add(b); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="AA001", real_name="学籍甲", class_id=a.id,
                       college_id=college_sw.id, major_id=major_sw.id, current_stage="ON_CAMPUS",
                       student_status="NORMAL", status="ACTIVE")
    db.add(s); db.flush()
    _seed_reviewers(db, class_ids=(a.id, b.id), college_ids=(college_sw.id, college_net.id))
    ids = {"a": a.id, "b": b.id, "s": s.id,
           "college": college_sw.id, "collegeNet": college_net.id,
           "majorSw": major_sw.id, "majorNet": major_net.id}
    db.commit()
    db.close()
    return ids


def _submit(client, hdr, sid, ct, **extra):
    return client.post(f"{BASE}/status-changes", headers=hdr,
                       json={"studentId": str(sid), "changeType": ct, "reason": f"{ct}原因说明足够长", **extra})


def _current_node(client, cid):
    hdr = _hdr(client, "school_admin01")
    return client.get(f"{BASE}/status-changes/{cid}", headers=hdr).json()["data"]["currentNode"]


def _approve(client, hdr, cid, times):
    """按节点真实受理人逐级通过。hdr 只用于读取详情，写操作一律用该节点的受理人身份。"""
    r = None
    for _ in range(times):
        node = _current_node(client, cid)
        node_hdr = _hdr(client, _NODE_LOGIN[node])
        r = client.post(f"{BASE}/status-changes/{cid}/review", headers=node_hdr, json={"action": "APPROVE"})
        assert r.status_code == 200, f"node={node} -> {r.text}"
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
                  toMajorId=str(ids["majorNet"]), toClassId=str(ids["b"]),
                  toCollegeId=str(ids["collegeNet"])).json()["data"]["changeId"]
    r = _approve(client, hdr, cid, 4)  # 辅导员→转出院→接收院→教务处
    assert r["data"]["status"] == "EFFECTIVE"
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    s = db.get(StudentProfile, ids["s"])
    # 转专业不改学籍状态字面，但迁移了院系班
    assert (s.student_status == "REGISTERED" and s.class_id == ids["b"]
            and s.major_id == ids["majorNet"] and s.college_id == ids["collegeNet"])
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
    # 首节点是辅导员初审，任务已明确分配给辅导员本人：驳回也必须由受理人做，不能由校管理员代劳。
    coun_hdr = _hdr(client, "counselor01")
    r = client.post(f"{BASE}/status-changes/{cid}/review", headers=coun_hdr,
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
    # 两个班都挂同一个辅导员账号：越权断言靠 TeacherStudentScope 的班级范围裁决，
    # 不靠"任务无人认领"这种假阴性通过。
    from tests.support_status_change_identity import seed_status_change_identity
    seed_status_change_identity(db, class_ids=(a.id, b.id),
                                college_ids=(college_sw.id, college_wl.id))
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
    from app.models import College, SchoolClass, StudentProfile
    db = get_sessionmaker()()
    college = College(tenant_id=TID, college_name=_COLLEGE_NAME, status="ACTIVE")
    db.add(college); db.flush()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE", class_status="NORMAL")
    a2 = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2102", grade="2021", status="ACTIVE", class_status="NORMAL")
    b = SchoolClass(tenant_id=TID, major_id=2, class_name="网络2101", grade="2021", status="ACTIVE", class_status="NORMAL")
    db.add(a); db.add(a2); db.add(b); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="AA020", real_name="转班甲", class_id=a.id,
                       college_id=college.id, major_id=1, current_stage="ON_CAMPUS",
                       student_status="NORMAL", status="ACTIVE")
    db.add(s); db.flush()
    _seed_reviewers(db, class_ids=(a.id, a2.id, b.id), college_ids=(college.id,))
    ids = {"a": a.id, "a2": a2.id, "b": b.id, "s": s.id, "college": college.id}
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
    assert s.class_id == ids["a2"] and s.major_id == 1 and s.college_id == ids["college"]
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
    """留级(RETAIN)全链路端到端覆盖：两节点(学院→教务处)。
    NORMAL→RETAINED 不在 change_student_status() 合法转移白名单内（真实业务：留级认定针对已注册在读
    学生，非入学未注册状态），故本测试起点造 REGISTERED 学生，不复用别测试的 NORMAL 起点种子。
    注意：留级(RETAINED)与保留学籍(PRESERVED)是两个语义相反的独立类型，后者见 sc20/sc21/sc22。"""
    from app.db.session import get_sessionmaker
    from app.models import College, SchoolClass, StudentProfile
    db = get_sessionmaker()()
    college = College(tenant_id=TID, college_name=_COLLEGE_NAME, status="ACTIVE")
    db.add(college); db.flush()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    db.add(a); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="AA021", real_name="留级甲", class_id=a.id,
                       college_id=college.id, major_id=1, current_stage="ON_CAMPUS",
                       student_status="REGISTERED", status="ACTIVE")
    db.add(s); db.flush()
    _seed_reviewers(db, class_ids=(a.id,), college_ids=(college.id,))
    sid = s.id
    db.commit()
    db.close()
    hdr = _hdr(client, "school_admin01")
    cid = _submit(client, hdr, sid, "RETAIN").json()["data"]["changeId"]
    r = _approve(client, hdr, cid, 2)  # 学院→教务处
    assert r["data"]["status"] == "EFFECTIVE" and r["data"]["toStatus"] == "RETAINED"
    assert _status(client, sid, hdr) == "RETAINED"


# ═══════════ 保留学籍（PRESERVE，R3 法规核验后从「留级」拆出的独立异动类型）═══════════
# 依据：教育部令41号第二十七条（应征入伍保留学籍至退役后2年、跨校联合培养期间保留）、
# 第二十八条（保留学籍期间"不享受在校学习学生待遇"→不计在籍）、第三十条(二)（休学、保留学籍
# 期满未复学可退学）。与留级(RETAIN/RETAINED，第十五条授权学校自定的学业处理)语义相反，勿混。


def _seed_registered(db_mode, student_no, real_name):
    """造一个 REGISTERED 在读学生（保留学籍/留级都要求发起时在籍）。"""
    from app.db.session import get_sessionmaker
    from app.models import College, SchoolClass, StudentProfile
    db = get_sessionmaker()()
    college = College(tenant_id=TID, college_name=_COLLEGE_NAME, status="ACTIVE")
    db.add(college); db.flush()
    c = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2102", grade="2021", status="ACTIVE")
    db.add(c); db.flush()
    s = StudentProfile(tenant_id=TID, student_no=student_no, real_name=real_name, class_id=c.id,
                       college_id=college.id, major_id=1, current_stage="ON_CAMPUS",
                       student_status="REGISTERED", status="ACTIVE")
    db.add(s); db.flush()
    _seed_reviewers(db, class_ids=(c.id,), college_ids=(college.id,))
    sid = s.id
    db.commit()
    db.close()
    return sid


def test_sc20_preserve_full_flow_and_not_enrolled(client, db_mode):
    """保留学籍全链路：三节点(辅导员→学院→教务处)生效为 PRESERVED；且 PRESERVED 不计在籍
    （41号令第二十八条"不享受在校学习学生待遇"；若误算在籍会虚增对教育主管部门报送的在册数）。"""
    from app.modules.academic_affairs.services.academic_affairs_status_service import is_enrolled
    sid = _seed_registered(db_mode, "AA030", "入伍甲")
    hdr = _hdr(client, "school_admin01")
    cid = _submit(client, hdr, sid, "PRESERVE").json()["data"]["changeId"]
    r = _approve(client, hdr, cid, 3)
    assert r["data"]["status"] == "EFFECTIVE" and r["data"]["toStatus"] == "PRESERVED"
    assert _status(client, sid, hdr) == "PRESERVED"
    # 关键断言：保留学籍不在籍，留级在籍——两者语义相反
    assert is_enrolled("PRESERVED") is False
    assert is_enrolled("RETAINED") is True


def test_sc21_preserve_then_resume(client, db_mode):
    """保留学籍期满复学：PRESERVED→复学→REGISTERED（41号令第三十条(二)把休学与保留学籍并列，
    两者都经复学回到在籍）。保留学籍不设 expire_date（退役日期提交时不可知），故不触发超期拦截。"""
    sid = _seed_registered(db_mode, "AA031", "入伍乙")
    hdr = _hdr(client, "school_admin01")
    cid = _submit(client, hdr, sid, "PRESERVE").json()["data"]["changeId"]
    _approve(client, hdr, cid, 3)
    assert _status(client, sid, hdr) == "PRESERVED"
    cid2 = _submit(client, hdr, sid, "RESUME").json()["data"]["changeId"]
    r = _approve(client, hdr, cid2, 3)
    assert r["data"]["status"] == "EFFECTIVE"
    assert _status(client, sid, hdr) == "REGISTERED"


def test_sc22_preserve_not_enrolled_student_409(client, db_mode):
    """非在籍学生不可发起保留学籍：先休学，再发起保留学籍 → 409（仅在籍学生可发起该异动）。"""
    sid = _seed_registered(db_mode, "AA032", "休学丙")
    hdr = _hdr(client, "school_admin01")
    cid = _submit(client, hdr, sid, "SUSPEND").json()["data"]["changeId"]
    _approve(client, hdr, cid, 3)
    assert _status(client, sid, hdr) == "SUSPENDED"
    r = _submit(client, hdr, sid, "PRESERVE")
    assert r.status_code == 409, r.text
