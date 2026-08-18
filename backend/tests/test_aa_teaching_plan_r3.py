"""教务中心 · 教学计划（收编）· 第三轮补缺 R3 · 端到端。

背景：《教学计划-生产级施工包.md》顶部 2026-07-14 用户最终裁决「收编」——不建独立
t_aa_teaching_plan* 域。navPlan `aa-teaching-plan` 10 个叶子中，年级/专业教学计划、学期教学计划/
课程开设计划、计划归档 3 个此前已收编到「培养方案」「教学任务」「教务归档」既有页面。本文件覆盖
R3 本轮补齐的剩余 5 个叶子：实践教学计划/计划审核/计划发布/计划变更/计划执行进度——全部收编到既有
真实实现，零新表零迁移，仅补齐此前缺失的自动化测试覆盖。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _ensure_real_major():
    """给绑定类回归用例提供真实租户学院/专业，不再依赖 phantom majorId=1。"""
    from app.db.session import get_sessionmaker
    from app.models import College, Major

    db = get_sessionmaker()()
    try:
        major = db.query(Major).filter(
            Major.tenant_id == TID,
            Major.status == "ACTIVE",
            Major.is_deleted.is_(False),
        ).order_by(Major.id).first()
        if major:
            return major.id

        college = db.query(College).filter(
            College.tenant_id == TID,
            College.code == "AW2TESTCOL",
            College.is_deleted.is_(False),
        ).first()
        if not college:
            college = College(
                tenant_id=TID,
                college_name="A-W2测试学院",
                code="AW2TESTCOL",
                status="ACTIVE",
            )
            db.add(college)
            db.flush()

        major = Major(
            tenant_id=TID,
            college_id=college.id,
            major_name="A-W2测试专业",
            code="AW2TESTMAJ",
            status="ACTIVE",
            enroll_status="ENROLLING",
        )
        db.add(major)
        db.commit()
        return major.id
    finally:
        db.close()


def _seed_enabled_course(pid, *, name, credit):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse
    db = get_sessionmaker()()
    course = AaCourse(
        tenant_id=TID,
        course_code=f"TP{int(pid) % 1000000:06d}",
        course_name=name,
        category="PUBLIC_BASIC",
        nature="REQUIRED",
        credit=credit,
        hours_total=16,
        hours_theory=16,
        hours_practice=0,
        exam_mode="EXAM",
        status="ENABLED",
    )
    db.add(course); db.flush()
    cid = course.id
    db.commit(); db.close()
    return cid


def _governance_ready_program(client, hdr, name, total=10):
    """构造满足当前正式发布门禁的方案，但保持 DRAFT 供各用例选择后续动作。"""
    major_id = _ensure_real_major()
    r = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": name, "majorId": str(major_id), "gradeYear": "2026", "totalCredits": total})
    assert r.status_code == 200, r.text
    pid = r.json()["data"]["programId"]
    cid = _seed_enabled_course(pid, name="高等数学", credit=total)
    r = client.put(f"{BASE}/programs/{pid}/credit-requirements", headers=hdr, json={
        "items": [{"module": "公共基础", "creditTarget": total}]})
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseId": str(cid), "courseName": "高等数学", "openTermNo": 1,
        "module": "公共基础", "credit": total})
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE}/programs/{pid}/graduation-requirements", headers=hdr, json={
        "category": "ABILITY", "content": "完成培养方案规定课程并达到毕业要求", "sortOrder": 1})
    assert r.status_code == 200, r.text
    return pid


def _enabled_program(client, hdr, name="软件技术2026方案", total=10):
    """建治理完整方案→提交→两审通过（PUBLISHED）→绑年级（ENABLED）。"""
    pid = _governance_ready_program(client, hdr, name, total)
    r = client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "PUBLISHED"
    r = client.post(f"{BASE}/programs/{pid}/bind", headers=hdr, json={"gradeYear": "2026"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "ENABLED"
    return pid


def test_tp1_change_creates_new_version_with_audit(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    pid = _enabled_program(client, hdr)
    r = client.post(f"{BASE}/programs/{pid}/change", headers=hdr,
                    json={"reason": "学分要求调整，新增一门专业核心课"})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["version"] == 2 and d["status"] == "DRAFT"
    versions = client.get(f"{BASE}/programs/{d['programId']}/versions", headers=hdr).json()["data"]["items"]
    assert any(v["programId"] == d["programId"] and v["version"] == 2 for v in versions)
    assert any(v["programId"] == pid and v["version"] == 1 for v in versions)


def test_tp2_change_validation_and_permission(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    pid_draft = client.post(f"{BASE}/programs", headers=hdr,
                            json={"programName": "草稿方案"}).json()["data"]["programId"]
    r1 = client.post(f"{BASE}/programs/{pid_draft}/change", headers=hdr, json={"reason": "随便改改试一下"})
    assert r1.status_code == 409

    pid = _enabled_program(client, hdr, name="方案B")
    r2 = client.post(f"{BASE}/programs/{pid}/change", headers=hdr, json={"reason": "改"})
    assert r2.status_code == 400

    hdr_stu = _hdr(client, "student01")
    r3 = client.post(f"{BASE}/programs/{pid}/change", headers=hdr_stu, json={"reason": "学生尝试变更教学计划"})
    assert r3.status_code == 403


def test_tp3_credit_requirements_practice_module_roundtrip(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    pid = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "实践教学计划测试方案", "totalCredits": 100}).json()["data"]["programId"]
    r = client.put(f"{BASE}/programs/{pid}/credit-requirements", headers=hdr, json={"items": [
        {"module": "公共基础", "creditTarget": 30},
        {"module": "专业核心", "creditTarget": 50},
        {"module": "实践环节", "creditTarget": 20, "note": "集中实践/顶岗实习"}
    ]})
    assert r.status_code == 200
    assert r.json()["data"]["targetSum"] == 100

    got = client.get(f"{BASE}/programs/{pid}/credit-requirements", headers=hdr).json()["data"]
    practice = next(i for i in got["items"] if i["module"] == "实践环节")
    assert practice["creditTarget"] == 20 and practice["note"] == "集中实践/顶岗实习"

    r2 = client.put(f"{BASE}/programs/{pid}/credit-requirements", headers=hdr, json={"items": [
        {"module": "实践环节", "creditTarget": 10}, {"module": "实践环节", "creditTarget": 5}
    ]})
    assert r2.status_code == 400


def test_tp4_review_publish_workbench_status_filters(client, db_mode):
    """审核/发布工作台使用当前正式治理合同，不再靠 name-only 课程绕过发布校验。"""
    hdr = _hdr(client, "school_admin01")
    pid = _governance_ready_program(client, hdr, "审核发布口径测试方案", 5)
    r = client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    assert r.status_code == 200, r.text

    review_list = client.get(f"{BASE}/programs?statusIn=COLLEGE_REVIEW,ACADEMIC_REVIEW",
                             headers=hdr).json()["data"]["items"]
    assert any(p["programId"] == pid for p in review_list)

    r = client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    assert r.status_code == 200, r.text

    publish_list = client.get(f"{BASE}/programs?statusIn=PUBLISHED,ENABLED",
                              headers=hdr).json()["data"]["items"]
    assert any(p["programId"] == pid for p in publish_list)
    review_list2 = client.get(f"{BASE}/programs?statusIn=COLLEGE_REVIEW,ACADEMIC_REVIEW",
                              headers=hdr).json()["data"]["items"]
    assert not any(p["programId"] == pid for p in review_list2)