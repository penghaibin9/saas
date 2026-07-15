"""补考重修缓考免修 · 统计分析(三级施工卡10) + 材料归档(三级施工卡11) 端点测试（Tier1 R2 续工）。

覆盖：四条线统计聚合正常/course维度下钻/学院数据范围(本院可见+越权403)/导出用途校验(<5字400)/
学生越权403；补考安排表打印页正常/未发布409/学院越权403；免修材料归档标记非终态409/成功/幂等，
归档列表查询与筛选，非授权角色403。

SQLite 自测（本轮禁止连接共享 MySQL 测试库，运行前需设置 TEST_DATABASE_URL=sqlite:///...）。
口径核对三级施工卡 §7/§9/§10/§12。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _college_admin_token(login_name):
    """合成任意学院教务员 token（越权对照组，mock-login 花名册未预置的学院用此构造）。"""
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{login_name}", "loginName": login_name, "realName": login_name,
        "userType": "ADMIN", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "COLLEGE_ADMIN", "clientType": "PC"})}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (AaDeferredExam, AaExemption, AaMakeupBatch, AaRetakeApply,
                            AcademicMakeup, AcademicStudent, College, Major, StudentProfile,
                            TeacherStudentScope)
    db = get_sessionmaker()()
    soft = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    mech = College(tenant_id=TID, college_name="机械学院", status="ACTIVE")
    db.add_all([soft, mech]); db.flush()
    major = Major(tenant_id=TID, college_id=soft.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="AR2401", real_name="归甲", college_id=soft.id,
                        major_id=major.id, grade="2024", student_status="NORMAL", status="ACTIVE")
    db.add(s1); db.flush()
    a1 = AcademicStudent(tenant_id=TID, student_id=s1.id, student_no="AR2401", name="归甲",
                         class_name="软件2401", college_name="软件学院")
    db.add(a1); db.flush()
    # 补考批次（PUBLISHED，含 1 条已录分名单，供统计 + 打印用）
    b = AaMakeupBatch(tenant_id=TID, batch_name="2024秋补考", term_code="2024-2", status="PUBLISHED")
    db.add(b); db.flush()
    db.add(AcademicMakeup(tenant_id=TID, acad_student_id=a1.id, course_name="高等数学", batch_id=b.id,
                          status="SCORED", final_score=72, record_status="ACTIVE"))
    # 重修申请（APPROVED=通过，计入分母）
    db.add(AaRetakeApply(tenant_id=TID, student_id=s1.id, student_no="AR2401", student_name="归甲",
                         course_name="数据结构", term_code="2024-2", retake_count=1, status="APPROVED"))
    # 免修申请：1 条终态(APPROVED，可归档) + 1 条在途(SUBMITTED，不可归档)
    e_approved = AaExemption(tenant_id=TID, student_id=s1.id, student_no="AR2401", student_name="归甲",
                             course_name="线性代数", term_code="2024-2", college_id=soft.id, status="APPROVED")
    e_pending = AaExemption(tenant_id=TID, student_id=s1.id, student_no="AR2401", student_name="归甲",
                            course_name="概率论", term_code="2024-2", college_id=soft.id, status="SUBMITTED")
    db.add_all([e_approved, e_pending]); db.flush()
    # 缓考记录（APPROVED）
    db.add(AaDeferredExam(tenant_id=TID, student_id=s1.id, student_no="AR2401", student_name="归甲",
                          exam_course_id=1, course_name="大学物理", status="APPROVED"))
    # college_admin01（mock-login 预置）→ 软件学院 数据范围
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="college_admin01", role_code="COLLEGE_ADMIN",
                              scope_type="COLLEGE", ref_value="软件学院", status="ACTIVE"))
    db.commit()
    ids = {"soft": soft.id, "mech": mech.id, "batch": b.id,
          "exemptionApproved": e_approved.id, "exemptionPending": e_pending.id}
    db.close()
    return ids


# ══════════ 统计分析（三级施工卡 10） ══════════

def test_s1_stats_aggregate_normal(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/makeup/stats", headers=admin).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["makeup"]["count"] == 1 and d["makeup"]["passRate"] == 1.0
    assert d["retake"]["count"] == 1 and d["retake"]["passRate"] == 1.0
    assert d["exemption"]["count"] == 2 and d["exemption"]["passRate"] == 1.0  # 分母只算终态(1条)
    assert d["deferred"]["count"] == 1 and d["deferred"]["passRate"] == 1.0


def test_s2_stats_dimension_course_groups(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/makeup/stats", headers=admin, params={"dimension": "course"}).json()
    assert r["code"] == 0
    assert any(g["key"] == "高等数学" and g["count"] == 1 for g in r["data"]["groups"]["makeup"])


def test_s3_stats_detail_drilldown(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/makeup/stats/detail", headers=admin, params={"line": "exemption"}).json()
    assert r["code"] == 0 and r["data"]["total"] == 2


def test_s4_stats_college_scope_own_visible_cross_forbidden(client, db_mode):
    ids = _seed(db_mode)
    college_admin = _hdr(client, "college_admin01")
    # 本院范围（软件学院）：可见本院数据
    r = client.get(f"{BASE}/makeup/stats", headers=college_admin).json()
    assert r["code"] == 0 and r["data"]["makeup"]["count"] == 1
    # 越权传机械学院 collegeId → 403
    assert client.get(f"{BASE}/makeup/stats", headers=college_admin,
                      params={"collegeId": str(ids["mech"])}).status_code == 403


def test_s5_stats_export_purpose_validation_and_success(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bad = client.post(f"{BASE}/makeup/stats/export", headers=admin, json={"purpose": "短"})
    assert bad.status_code == 400
    ok = client.post(f"{BASE}/makeup/stats/export", headers=admin, json={"purpose": "月度教学质量分析核对"})
    assert ok.status_code == 200
    assert "spreadsheetml" in ok.headers["content-type"]


def test_s6_stats_student_forbidden_403(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("归甲", "AR2401")
    assert client.get(f"{BASE}/makeup/stats", headers=stu).status_code == 403


# ══════════ 材料归档（三级施工卡 11） ══════════

def test_p1_print_data_normal(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/makeup/batches/{ids['batch']}/print-data", headers=admin).json()
    assert r["code"] == 0
    assert r["data"]["batchName"] == "2024秋补考"
    assert any(s["studentName"] == "归甲" and s["courseName"] == "高等数学" for s in r["data"]["students"])


def test_p2_print_batch_not_published_409(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaMakeupBatch
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    db = get_sessionmaker()()
    draft = AaMakeupBatch(tenant_id=TID, batch_name="草稿批次", status="DRAFT")
    db.add(draft); db.commit(); db.refresh(draft)
    bid = draft.id
    db.close()
    assert client.get(f"{BASE}/makeup/batches/{bid}/print-data", headers=admin).status_code == 409


def test_p3_print_cross_college_scope_403(client, db_mode):
    ids = _seed(db_mode)
    from app.db.session import get_sessionmaker
    from app.models import TeacherStudentScope
    db = get_sessionmaker()()
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="mech_admin01", role_code="COLLEGE_ADMIN",
                              scope_type="COLLEGE", ref_value="机械学院", status="ACTIVE"))
    db.commit(); db.close()
    mech_admin = _college_admin_token("mech_admin01")
    assert client.get(f"{BASE}/makeup/batches/{ids['batch']}/print-data", headers=mech_admin).status_code == 403


def test_a1_archive_non_terminal_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    assert client.post(f"{BASE}/exemption/{ids['exemptionPending']}/archive", headers=admin).status_code == 409


def test_a2_archive_success_and_idempotent(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    r1 = client.post(f"{BASE}/exemption/{ids['exemptionApproved']}/archive", headers=admin).json()
    assert r1["code"] == 0 and r1["data"]["archiveStatus"] == "ARCHIVED"
    # 幂等：已归档再次调用不报错，状态不变
    r2 = client.post(f"{BASE}/exemption/{ids['exemptionApproved']}/archive", headers=admin).json()
    assert r2["code"] == 0 and r2["data"]["archiveStatus"] == "ARCHIVED"


def test_a3_archive_list_query_and_filter(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/exemption/archive-list", headers=admin).json()
    assert r["code"] == 0 and r["data"]["total"] == 2
    client.post(f"{BASE}/exemption/{ids['exemptionApproved']}/archive", headers=admin)
    filtered = client.get(f"{BASE}/exemption/archive-list", headers=admin,
                          params={"status": "ARCHIVED"}).json()
    assert filtered["data"]["total"] == 1
    assert filtered["data"]["items"][0]["exemptionId"] == str(ids["exemptionApproved"])


def test_a4_archive_student_forbidden_403(client, db_mode):
    ids = _seed(db_mode)
    stu = _stu_token("归甲", "AR2401")
    assert client.post(f"{BASE}/exemption/{ids['exemptionApproved']}/archive", headers=stu).status_code == 403
    assert client.get(f"{BASE}/exemption/archive-list", headers=stu).status_code == 403
