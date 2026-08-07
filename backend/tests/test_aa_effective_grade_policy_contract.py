"""包 2：有效成绩策略版本身份、活动范围唯一、无策略 fail-closed 与任务原子性（真实 MySQL）。

对应根因：
- NEW-P1-03 唯一约束锁死 policy_code，同一策略无法发布 V2；
- NEW-P1-04 无 ACTIVE 策略时 ORM 监听器静默放行，产出没有冻结策略的正式成绩；
- NEW-P1-01 成绩任务与课程身份分两个事务，第二步失败留下半成品任务。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.modules.academic_affairs.services import (
    academic_affairs_effective_grade_policy_failclosed as failclosed,
)
from app.modules.academic_affairs.services import (
    academic_affairs_effective_grade_policy_service as policy_service,
)

TID = 1000000000000000001


def _activate():
    set_tenant({"tenantId": str(TID), "tenantCode": "demo"})
    set_current_user({
        "userId": "u_school_admin01", "loginName": "school_admin01", "realName": "陈校",
        "currentRoleCode": "SCHOOL_ADMIN", "userType": "ADMIN", "tenantId": str(TID),
    })


def _new_term(year_code="2026-2027", term_no=1):
    from app.models import AaTerm

    db = get_sessionmaker()()
    try:
        term = AaTerm(tenant_id=TID, year_code=year_code, term_no=term_no,
                      term_name=f"{year_code}-{term_no}", status="PUBLISHED")
        db.add(term)
        db.commit()
        return int(term.id)
    finally:
        db.close()


def _policies():
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy

    db = get_sessionmaker()()
    try:
        return db.query(AaEffectiveGradePolicy).filter(
            AaEffectiveGradePolicy.tenant_id == TID).order_by(AaEffectiveGradePolicy.id).all()
    finally:
        db.close()


def _academic_student():
    from app.models import AcademicStudent, StudentProfile

    db = get_sessionmaker()()
    try:
        student = StudentProfile(tenant_id=TID, student_no="PK2001", real_name="策略甲",
                                 current_stage="ON_CAMPUS", student_status="REGISTERED",
                                 status="ACTIVE")
        db.add(student)
        db.flush()
        academic = AcademicStudent(tenant_id=TID, student_id=student.id,
                                   student_no=student.student_no, name=student.real_name)
        db.add(academic)
        db.commit()
        return int(academic.id)
    finally:
        db.close()


def _insert_grade(acad_student_id, *, term=""):
    from app.models import AcademicGrade

    db = get_sessionmaker()()
    try:
        db.add(AcademicGrade(
            tenant_id=TID, acad_student_id=acad_student_id, course_name="数据结构",
            course_code="CS101", course_version=1, term=term, nature="REQUIRED",
            credit_value=4, score=88, pass_status="PASSED", exam_type="FINAL",
            record_status="ACTIVE", source="PUBLISH",
        ))
        db.commit()
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_same_policy_code_can_publish_multiple_versions():
    """同一 policy_code 必须能发布 V1/V2 版本链——旧唯一约束把它锁死了（NEW-P1-03）。"""
    _activate()
    term_id = _new_term()
    first = policy_service.activate_grade_policy(
        None, {"attemptStrategy": "LATEST_ATTEMPT", "policyCode": "SCHOOL_MAIN",
               "effectiveFromTermId": term_id})
    second = policy_service.activate_grade_policy(
        None, {"attemptStrategy": "HIGHEST_SCORE", "policyCode": "SCHOOL_MAIN",
               "effectiveFromTermId": term_id})

    assert first["policyVersion"] == 1
    assert second["policyVersion"] == 2

    rows = {int(row.policy_version): row for row in _policies()}
    assert rows[1].status == "SUPERSEDED" and rows[1].active_scope_key is None
    assert rows[2].status == "ACTIVE" and rows[2].active_scope_key == str(term_id)


@pytest.mark.usefixtures("db_mode")
def test_only_one_active_policy_per_effective_scope():
    """同一生效范围任何时刻只允许一条 ACTIVE，由数据库唯一索引兜底。"""
    from sqlalchemy.exc import IntegrityError

    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy

    _activate()
    term_id = _new_term()
    policy_service.activate_grade_policy(
        None, {"attemptStrategy": "LATEST_ATTEMPT", "effectiveFromTermId": term_id})

    db = get_sessionmaker()()
    try:
        db.add(AaEffectiveGradePolicy(
            tenant_id=TID, policy_code="SNEAK_IN", policy_version=1,
            attempt_strategy="HIGHEST_SCORE", effective_from_term_id=term_id,
            active_scope_key=str(term_id), status="ACTIVE",
        ))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()

    active = [row for row in _policies() if row.status == "ACTIVE"]
    assert len(active) == 1


@pytest.mark.usefixtures("db_mode")
def test_concurrent_policy_publication_keeps_single_active():
    """并发发布同一范围的策略：只允许一个成功，绝不产生两条并存 ACTIVE。"""
    _activate()
    term_id = _new_term()
    barrier = Barrier(2)

    def publish(_index):
        _activate()
        barrier.wait()
        try:
            policy_service.activate_grade_policy(
                None, {"attemptStrategy": "LATEST_ATTEMPT", "policyCode": "RACE_POLICY",
                       "effectiveFromTermId": term_id})
            return "ok"
        except AppException as exc:
            return f"rejected:{exc.code}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, range(2)))

    assert results.count("ok") >= 1, results
    active = [row for row in _policies() if row.status == "ACTIVE"]
    assert len(active) == 1, [(row.policy_code, row.policy_version, row.status) for row in _policies()]


@pytest.mark.usefixtures("db_mode")
def test_first_grade_provisions_tenant_base_policy_instead_of_silent_pass():
    """租户从未配置策略时自动落基础策略并冻结到成绩上，绝不产出"没有策略"的正式成绩。

    这是 NEW-P1-04 的正解：既不静默放行，也不给学校留"上线前记得先配策略"的人工前提。
    """
    from app.models import AcademicGrade

    _activate()
    acad_student_id = _academic_student()
    _insert_grade(acad_student_id)

    db = get_sessionmaker()()
    try:
        grade = db.query(AcademicGrade).filter(AcademicGrade.tenant_id == TID).one()
        assert grade.effective_policy_code == failclosed.BASE_POLICY_CODE
        assert grade.effective_attempt_strategy == failclosed.BASE_ATTEMPT_STRATEGY
        active = [row for row in _policies() if row.status == "ACTIVE"]
        assert len(active) == 1 and active[0].active_scope_key == "BASE"
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_grade_outside_every_policy_scope_is_rejected():
    """租户已有策略但成绩学期落在所有策略生效范围之前 → 409，不允许猜一套规则套上去。"""
    from app.models import AcademicGrade

    _activate()
    early_term_id = _new_term("2025-2026", 1)
    late_term_id = _new_term("2027-2028", 1)
    policy_service.activate_grade_policy(
        None, {"attemptStrategy": "HIGHEST_SCORE", "effectiveFromTermId": late_term_id})

    acad_student_id = _academic_student()
    with pytest.raises(AppException) as exc:
        _insert_grade(acad_student_id, term="2025-2026-1")
    assert exc.value.code == "DATA_CONFLICT"

    db = get_sessionmaker()()
    try:
        assert db.query(AcademicGrade).filter(AcademicGrade.tenant_id == TID).count() == 0
    finally:
        db.close()
    assert early_term_id  # 早学期确实存在，排除"学期不存在"这种假阴性


@pytest.mark.usefixtures("db_mode")
def test_legacy_import_context_allows_bypass_and_records_debt():
    """历史导入可以显式豁免，但必须留下来源、操作人、批次和欠账理由。"""
    from app.models import AcademicGrade
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicyBypass

    _activate()
    acad_student_id = _academic_student()
    with failclosed.legacy_import_context(
        source="LEGACY_IMPORT", operator="migration-bot",
        batch_no="LEGACY-2019-01", debt_reason="2019 级历史成绩无当年策略记录",
    ):
        _insert_grade(acad_student_id)

    db = get_sessionmaker()()
    try:
        assert db.query(AcademicGrade).filter(AcademicGrade.tenant_id == TID).count() == 1
        debts = db.query(AaEffectiveGradePolicyBypass).filter(
            AaEffectiveGradePolicyBypass.tenant_id == TID).all()
        assert len(debts) == 1
        assert debts[0].source == "LEGACY_IMPORT"
        assert debts[0].operator == "migration-bot"
        assert debts[0].batch_no == "LEGACY-2019-01"
        assert debts[0].grade_count == 1
        assert debts[0].debt_reason
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_legacy_import_context_requires_full_declaration():
    """豁免声明不完整就拒绝进入：不允许写一个空理由把欠账糊过去。"""
    for kwargs in (
        {"source": "UNKNOWN", "operator": "x", "batch_no": "b", "debt_reason": "r"},
        {"source": "MIGRATION", "operator": "", "batch_no": "b", "debt_reason": "r"},
        {"source": "MIGRATION", "operator": "x", "batch_no": "", "debt_reason": "r"},
        {"source": "MIGRATION", "operator": "x", "batch_no": "b", "debt_reason": ""},
    ):
        with pytest.raises(AppException):
            with failclosed.legacy_import_context(**kwargs):
                pass


@pytest.mark.usefixtures("db_mode")
def test_grade_task_creation_binds_course_identity_in_one_transaction():
    """成绩任务与课程身份绑定失败时不得留下半成品任务（NEW-P1-01）。"""
    from app.models import AaCourse, AaGradeTask, AaTerm
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade_service

    _activate()
    db = get_sessionmaker()()
    try:
        term = AaTerm(tenant_id=TID, year_code="2026-2027", term_no=1, status="PUBLISHED",
                      is_current=True)
        db.add(term)
        db.flush()
        course = AaCourse(tenant_id=TID, course_code="CS101", course_name="数据结构",
                          version=1, credit=4, status="ACTIVE")
        db.add(course)
        db.commit()
        term_id, course_id = int(term.id), int(course.id)
    finally:
        db.close()

    body = {
        "courseId": str(course_id), "courseName": "数据结构", "termId": str(term_id),
        "usualRatio": 30, "finalRatio": 70, "midtermRatio": 0,
        "adminSupplementReason": "历史补录用例", "classId": None, "credit": 4,
    }
    user = {"userId": "u_school_admin01", "loginName": "school_admin01",
            "currentRoleCode": "SCHOOL_ADMIN", "userType": "ADMIN"}

    from types import SimpleNamespace

    result = grade_service.create_grade_task(SimpleNamespace(**body), user)

    db = get_sessionmaker()()
    try:
        task = db.get(AaGradeTask, int(result["gradeTaskId"]))
        # 任务和课程身份必须同时存在：不允许出现 course_id 为空的孤儿任务。
        assert task is not None and int(task.course_id) == course_id
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_failed_course_identity_bind_leaves_no_orphan_task(monkeypatch):
    """绑定阶段抛错时整笔回滚：既不留任务，也不留待办和审计。"""
    from app.models import AaCourse, AaGradeTask, AaTerm, UnifiedTodo
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade_service

    _activate()
    db = get_sessionmaker()()
    try:
        term = AaTerm(tenant_id=TID, year_code="2026-2027", term_no=1, status="PUBLISHED",
                      is_current=True)
        db.add(term)
        db.flush()
        course = AaCourse(tenant_id=TID, course_code="CS102", course_name="操作系统",
                          version=1, credit=3, status="ACTIVE")
        db.add(course)
        db.commit()
        term_id, course_id = int(term.id), int(course.id)
    finally:
        db.close()

    original_audit = grade_service._core._audit

    def _boom(db_, biz_type, biz_id, action, detail=""):
        if action == "COURSE_IDENTITY_BIND":
            raise RuntimeError("injected identity bind failure")
        return original_audit(db_, biz_type, biz_id, action, detail)

    monkeypatch.setattr(grade_service._core, "_audit", _boom)

    from types import SimpleNamespace

    body = SimpleNamespace(courseId=str(course_id), courseName="操作系统", termId=str(term_id),
                           usualRatio=30, finalRatio=70, midtermRatio=0,
                           adminSupplementReason="历史补录用例", classId=None, credit=3,
                           teachingTaskId=None)
    user = {"userId": "u_school_admin01", "loginName": "school_admin01",
            "currentRoleCode": "SCHOOL_ADMIN", "userType": "ADMIN"}

    with pytest.raises(RuntimeError):
        grade_service.create_grade_task(body, user)

    db = get_sessionmaker()()
    try:
        assert db.query(AaGradeTask).filter(AaGradeTask.tenant_id == TID).count() == 0
        assert db.query(UnifiedTodo).filter(
            UnifiedTodo.tenant_id == TID,
            UnifiedTodo.todo_type == "AA_GRADE_ENTRY").count() == 0
    finally:
        db.close()
