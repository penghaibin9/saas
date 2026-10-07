"""13B-培养方案二级模块第三轮续工 · 端到端：实践环节 / 方案变更 / 方案归档。

TR1 实践环节：编制态增删改 + 非编制态 409 + 周数<=0 校验失败。
TR2 方案变更：冻结→恢复（无绑定回 PUBLISHED / 有绑定回 ENABLED 两分支）→停用（终态）+
    原因<5字 400 + 终态再变更 409 + 变更记录可查。
TR3 方案归档：DISABLED 与版本链 SUPERSEDED 两类均出现在只读列表，普通 DRAFT 不出现。
TR4 越权：学生令牌对三组新端点一律 403。

显式复用共享 db_mode，在独立 MySQL 测试库串行执行。当前审核依赖已发布角色模板、
真实组织任职与学校商业授权，不能再只建少量业务表并依赖其它用例留下的身份事实。
"""
from __future__ import annotations

import pytest

from tests.support_academic_review_identity import ensure_college_review_scope

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"

@pytest.fixture()
def db_mode_programs(db_mode):
    """本文件显式选用完整测试身份基线；不改动共享夹具或生产守卫。"""
    return db_mode


def _hdr(client, login_name):
    """业务回归直接签发既有 mock 身份，避免全量 shard 的登录限流状态污染本模块。"""
    del client
    from app.core.config import settings
    from app.services import mock_auth_service

    user_type = "STUDENT" if login_name == "student01" else "ADMIN"
    data = mock_auth_service.login(
        settings.DEFAULT_TENANT_CODE,
        login_name,
        user_type,
        "PC",
    )
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _ensure_real_major():
    """固定使用本文件专用学院/专业，避免 shard 顺序影响 Program 的学院审核 scope。"""
    from app.db.session import get_sessionmaker
    from app.models import College, Major

    db = get_sessionmaker()()
    try:
        college = db.query(College).filter(
            College.tenant_id == TID,
            College.code == "AW2TESTCOL",
        ).first()
        if college is None:
            college = College(
                tenant_id=TID,
                college_name="A-W2测试学院",
                code="AW2TESTCOL",
                status="ACTIVE",
            )
            db.add(college)
            db.flush()
        else:
            college.college_name = "A-W2测试学院"
            college.status = "ACTIVE"
            college.is_deleted = False

        major = db.query(Major).filter(
            Major.tenant_id == TID,
            Major.code == "AW2TESTMAJ",
        ).first()
        if major is None:
            major = Major(
                tenant_id=TID,
                college_id=college.id,
                major_name="A-W2测试专业",
                code="AW2TESTMAJ",
                status="ACTIVE",
                enroll_status="ENROLLING",
            )
            db.add(major)
        else:
            major.college_id = college.id
            major.major_name = "A-W2测试专业"
            major.status = "ACTIVE"
            major.enroll_status = "ENROLLING"
            major.is_deleted = False
        db.flush()
        major_id = int(major.id)
        db.commit()
        return major_id
    finally:
        db.close()


def _new_program(client, hdr, name):
    # 正式发布/绑定门禁要求方案必须有稳定且真实存在的专业/年级身份。
    major_id = _ensure_real_major()
    ensure_college_review_scope(major_ids=[major_id])
    r = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": name, "majorId": str(major_id), "gradeYear": "2026"})
    assert r.status_code == 200, r.text
    return r.json()["data"]["programId"]


def _seed_enabled_course(pid, *, name="占位课程", credit=1):
    """直接种一条正式 ENABLED 课程，给最小真库夹具提供稳定 courseId。"""
    from app.db.session import get_sessionmaker
    from app.models import AaCourse
    db = get_sessionmaker()()
    course = AaCourse(
        tenant_id=TID,
        course_code=f"P{int(pid) % 1000000:06d}",
        course_name=name,
        category="MAJOR_CORE",
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


def _make_governance_ready(client, hdr, pid, *, total=1, course_credit=None,
                           module="专业核心", course_name="占位课程"):
    """补齐当前权威发布门禁需要的学分结构、稳定课程身份与结构化毕业要求。"""
    course_credit = total if course_credit is None else course_credit
    r = client.put(f"{BASE}/programs/{pid}", headers=hdr, json={"totalCredits": total})
    assert r.status_code == 200, r.text
    r = client.put(f"{BASE}/programs/{pid}/credit-requirements", headers=hdr, json={
        "items": [{"module": module, "creditTarget": total}]})
    assert r.status_code == 200, r.text
    cid = _seed_enabled_course(pid, name=course_name, credit=course_credit)
    r = client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseId": str(cid), "courseName": course_name, "openTermNo": 1,
        "module": module, "credit": course_credit})
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE}/programs/{pid}/graduation-requirements", headers=hdr, json={
        "category": "ABILITY", "content": "完成培养方案规定课程并达到毕业要求", "sortOrder": 1})
    assert r.status_code == 200, r.text
    return cid


def _publish(client, hdr, pid):
    """按当前权威治理合同完成 DRAFT -> COLLEGE_REVIEW -> ACADEMIC_REVIEW -> PUBLISHED。"""
    _make_governance_ready(client, hdr, pid)
    r = client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    assert r.status_code == 200, r.text
    r = client.post(
        f"{BASE}/programs/{pid}/review",
        headers=_hdr(client, "college_admin01"),
        json={"action": "APPROVE"},
    )
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "PUBLISHED"


def test_draft_course_formation_update_survives_readback_and_keeps_review_guards(client, db_mode_programs):
    hdr = _hdr(client, "school_admin01")
    pid = _new_program(client, hdr, "草稿编班方式正常编辑")
    _make_governance_ready(client, hdr, pid)
    detail = client.get(f"{BASE}/programs/{pid}", headers=hdr).json()["data"]
    source_id = detail["courses"][0]["programCourseId"]
    assert detail["courses"][0]["formationMode"] is None
    path = f"{BASE}/programs/courses/{source_id}"

    invalid = client.put(path, headers=hdr, json={"formationMode": "MERGED"})
    assert invalid.status_code == 400, invalid.text
    assert invalid.json()["bizCode"] == "VALIDATION_ERROR"
    result = client.put(path, headers=hdr, json={"formationMode": "SELECTABLE"})
    assert result.status_code == 200, result.text
    assert result.json()["data"]["formationMode"] == "SELECTABLE"
    for body in ({"credit": 1}, {"formationMode": None}):
        result = client.put(path, headers=hdr, json=body)
        assert result.status_code == 200, result.text
        assert result.json()["data"]["formationMode"] == "SELECTABLE"
    denied = client.put(path, headers=_hdr(client, "student01"), json={"formationMode": "ADMIN_FIXED"})
    assert denied.status_code == 403, denied.text

    result = client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    assert result.status_code == 200, result.text
    result = client.post(f"{BASE}/programs/{pid}/review", headers=_hdr(client, "college_admin01"), json={"action": "APPROVE"})
    assert result.status_code == 200, result.text
    result = client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    assert result.status_code == 200, result.text
    result = client.put(path, headers=hdr, json={"formationMode": "ADMIN_FIXED"})
    assert result.status_code == 409, result.text
    readback = client.get(f"{BASE}/programs/{pid}", headers=hdr).json()["data"]
    assert readback["status"] == "PUBLISHED"
    assert readback["courses"][0]["formationMode"] == "SELECTABLE"


def test_tr1_practice_segment_crud(client, db_mode_programs):
    hdr = _hdr(client, "school_admin01")
    pid = _new_program(client, hdr, "实践环节CRUD方案")
    r = client.post(f"{BASE}/programs/{pid}/practice-segments", headers=hdr, json={
        "segmentName": "顶岗实习", "segmentType": "POST_INTERNSHIP", "openTermNo": 6,
        "weeks": 16, "credit": 8, "orgMode": "DISTRIBUTED", "location": "合作企业", "assessmentMode": "CHECK"})
    assert r.status_code == 200, r.text
    seg = r.json()["data"]
    sid = seg["segmentId"]
    assert seg["weeks"] == 16 and seg["segmentType"] == "POST_INTERNSHIP" and seg["orgMode"] == "DISTRIBUTED"

    items = client.get(f"{BASE}/programs/{pid}/practice-segments", headers=hdr).json()["data"]["items"]
    assert len(items) == 1 and items[0]["segmentName"] == "顶岗实习"

    r = client.put(f"{BASE}/programs/practice-segments/{sid}", headers=hdr, json={"weeks": 18})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["weeks"] == 18

    r = client.delete(f"{BASE}/programs/practice-segments/{sid}", headers=hdr)
    assert r.status_code == 200, r.text
    items = client.get(f"{BASE}/programs/{pid}/practice-segments", headers=hdr).json()["data"]["items"]
    assert items == []


def test_tr1_practice_segment_rejects_bad_weeks_and_non_draft(client, db_mode_programs):
    hdr = _hdr(client, "school_admin01")
    pid = _new_program(client, hdr, "实践环节校验方案")
    r = client.post(f"{BASE}/programs/{pid}/practice-segments", headers=hdr, json={"segmentName": "军训", "weeks": 0})
    assert r.status_code == 400, r.text

    _publish(client, hdr, pid)
    r = client.post(f"{BASE}/programs/{pid}/practice-segments", headers=hdr, json={"segmentName": "军训", "weeks": 2})
    assert r.status_code == 409, r.text


def test_tr2_change_status_freeze_resume_disable(client, db_mode_programs):
    hdr = _hdr(client, "school_admin01")
    pid = _new_program(client, hdr, "方案变更生命周期")
    _publish(client, hdr, pid)

    r = client.post(f"{BASE}/programs/{pid}/change-status", headers=hdr, json={"action": "FREEZE", "reason": "短"})
    assert r.status_code == 400, r.text

    r = client.post(f"{BASE}/programs/{pid}/change-status", headers=hdr, json={"action": "FREEZE", "reason": "专业停招临时冻结"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "FROZEN"

    r = client.post(f"{BASE}/programs/{pid}/change-status", headers=hdr, json={"action": "RESUME", "reason": "专业恢复招生启用"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "PUBLISHED"

    r = client.post(f"{BASE}/programs/{pid}/change-status", headers=hdr, json={"action": "DISABLE", "reason": "方案编制有误停用"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "DISABLED"

    r = client.post(f"{BASE}/programs/{pid}/change-status", headers=hdr, json={"action": "FREEZE", "reason": "再次尝试冻结应失败"})
    assert r.status_code == 409, r.text

    log = client.get(f"{BASE}/programs/{pid}/change-log", headers=hdr).json()["data"]["items"]
    actions = [x["action"] for x in log]
    assert "LIFECYCLE_FREEZE" in actions
    assert "LIFECYCLE_RESUME" in actions
    assert "LIFECYCLE_DISABLE" in actions


def test_tr2_resume_to_enabled_when_active_binding(client, db_mode_programs):
    hdr = _hdr(client, "school_admin01")
    pid = _new_program(client, hdr, "方案变更绑定恢复")
    _publish(client, hdr, pid)
    r = client.post(f"{BASE}/programs/{pid}/bind", headers=hdr, json={"gradeYear": "2027"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "ENABLED"

    r = client.post(f"{BASE}/programs/{pid}/change-status", headers=hdr, json={"action": "FREEZE", "reason": "临时冻结待复核"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "FROZEN"

    r = client.post(f"{BASE}/programs/{pid}/change-status", headers=hdr, json={"action": "RESUME", "reason": "复核通过恢复启用"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "ENABLED"


def test_tr3_archive_lists_disabled_and_superseded_not_plain_draft(client, db_mode_programs):
    hdr = _hdr(client, "school_admin01")
    pid1 = _new_program(client, hdr, "归档-已停用方案")
    _publish(client, hdr, pid1)
    r = client.post(f"{BASE}/programs/{pid1}/change-status", headers=hdr, json={"action": "DISABLE", "reason": "停用测试用例数据"})
    assert r.status_code == 200, r.text

    pid2 = _new_program(client, hdr, "归档-历史版本方案")
    _publish(client, hdr, pid2)
    r = client.post(f"{BASE}/programs/{pid2}/new-version", headers=hdr)
    assert r.status_code == 200, r.text
    new_pid = r.json()["data"]["programId"]

    pid3 = _new_program(client, hdr, "归档-普通草稿不应出现")

    items = client.get(f"{BASE}/program-archive", headers=hdr, params={"pageSize": 200}).json()["data"]["items"]
    by_id = {x["programId"]: x for x in items}
    assert pid1 in by_id and "DISABLED" in by_id[pid1]["archiveReasons"]
    assert pid2 in by_id and "SUPERSEDED" in by_id[pid2]["archiveReasons"]
    assert by_id[pid2]["supersededByProgramId"] == new_pid
    assert pid3 not in by_id


def test_submit_rejects_when_total_credits_unset_or_course_sum_short(client, db_mode_programs):
    """发布治理回归：缺正式总学分或课程学分不足必须由 PROGRAM_VALIDATION_BLOCKED fail-closed。"""
    hdr = _hdr(client, "school_admin01")
    pid = _new_program(client, hdr, "总学分未设置不可提交")
    r = client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    assert r.status_code == 409, r.text
    assert "PROGRAM_VALIDATION_BLOCKED" in r.text
    assert "总学分" in r.text

    # 构造其它发布治理项均完整、仅课程/实践学分合计不足的精确场景。
    _make_governance_ready(client, hdr, pid, total=10, course_credit=4, course_name="学分不足课程")
    r = client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    assert r.status_code == 409, r.text
    assert "PROGRAM_VALIDATION_BLOCKED" in r.text
    assert "课程与实践学分合计" in r.text
    assert "毕业总学分" in r.text


def test_tr4_student_403_on_new_endpoints(client, db_mode_programs):
    hdr = _hdr(client, "school_admin01")
    pid = _new_program(client, hdr, "越权测试方案")
    stu = _hdr(client, "student01")
    assert client.get(f"{BASE}/programs/{pid}/practice-segments", headers=stu).status_code == 403
    assert client.post(f"{BASE}/programs/{pid}/practice-segments", headers=stu,
                       json={"segmentName": "X", "weeks": 1}).status_code == 403
    assert client.post(f"{BASE}/programs/{pid}/change-status", headers=stu,
                       json={"action": "FREEZE", "reason": "越权尝试冻结"}).status_code == 403
    assert client.get(f"{BASE}/programs/{pid}/change-log", headers=stu).status_code == 403
    assert client.get(f"{BASE}/program-archive", headers=stu).status_code == 403
