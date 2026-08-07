"""包 1：正式成绩更正统一命令（真实 MySQL）。

不变量：
1. 发起更正不得改动任何正式事实（C05）——审批期间成绩单读到的还是原分数；
2. 终审通过是追加式版本：新 AcademicGrade 为 ACTIVE、原行 SUPERSEDED，连续两次更正
   形成 A→B→C 完整链；
3. 终审、工作流、审计、outbox 同一事务（C06）——任一步失败全部回滚；
4. 两人并发终审只有一个成功；
5. 驳回不改变任何正式事实；
6. 工作流任务永远有真实受理人，解析不到就不允许发起（NEW-P1-02）。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.modules.academic_affairs.services import (
    academic_affairs_grade_correction_command as command,
)

TID = 1000000000000000001
REVIEW_PERM = "academicAffairs.gradeChange.review"
COLLEGE_NAME = "更正学院"


def _ctx(login_name, role_code):
    return {
        "userId": f"u_{login_name}", "loginName": login_name, "realName": login_name,
        "currentRoleCode": role_code, "userType": "ADMIN", "tenantId": str(TID),
    }


def _activate(login_name="school_admin01", role_code="SCHOOL_ADMIN"):
    set_tenant({"tenantId": str(TID), "tenantCode": "demo"})
    user = _ctx(login_name, role_code)
    set_current_user(user)
    return user


def _grant(db, login_name, real_name):
    """建启用账号并通过专属角色授予成绩更正审批权限。"""
    from app.models import Permission, Role, RolePermission, User, UserRole

    user = db.query(User).filter(User.tenant_id == TID, User.login_name == login_name).first()
    if user is None:
        user = User(tenant_id=TID, login_name=login_name, real_name=real_name,
                    password_hash="x", user_type="SCHOOL_ADMIN", status="ACTIVE")
        db.add(user)
        db.flush()
    permission = db.query(Permission).filter(Permission.permission_code == REVIEW_PERM).first()
    if permission is None:
        permission = Permission(permission_code=REVIEW_PERM, permission_name=REVIEW_PERM,
                                module_code="academicAffairs", action="REVIEW")
        db.add(permission)
        db.flush()
    role_code = f"TEST_{login_name.upper()}"
    role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == role_code).first()
    if role is None:
        role = Role(tenant_id=TID, role_code=role_code, role_name=role_code, status="ACTIVE")
        db.add(role)
        db.flush()
    if db.query(UserRole).filter(UserRole.tenant_id == TID, UserRole.user_id == user.id,
                                 UserRole.role_id == role.id).first() is None:
        db.add(UserRole(tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE"))
    if db.query(RolePermission).filter(RolePermission.tenant_id == TID,
                                       RolePermission.role_id == role.id,
                                       RolePermission.permission_id == permission.id).first() is None:
        db.add(RolePermission(tenant_id=TID, role_id=role.id,
                              permission_id=permission.id, status="ACTIVE"))
    db.flush()
    return user


def _seed_published_grade(*, usual=60, final=60):
    """造一条已发布成绩：任务 + 明细 + 正式 AcademicGrade，并配好两个节点的受理人。"""
    from app.models import (
        AaGradeRecord, AaGradeTask, AaTerm, AcademicGrade, AcademicStudent, College, Major,
        SchoolClass, StudentProfile,
    )

    db = get_sessionmaker()()
    try:
        term = AaTerm(tenant_id=TID, year_code="2026-2027", term_no=1, term_name="2026-2027-1",
                      status="PUBLISHED", is_current=True)
        db.add(term)
        db.flush()
        college = College(tenant_id=TID, college_name=COLLEGE_NAME, status="ACTIVE")
        db.add(college)
        db.flush()
        major = Major(tenant_id=TID, college_id=college.id, major_name="软件技术", status="ACTIVE")
        db.add(major)
        db.flush()
        klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="更正2101",
                            grade="2021", status="ACTIVE")
        db.add(klass)
        db.flush()
        student = StudentProfile(tenant_id=TID, student_no="GC001", real_name="更正甲",
                                 class_id=klass.id, college_id=college.id, major_id=major.id,
                                 current_stage="ON_CAMPUS", student_status="REGISTERED",
                                 status="ACTIVE")
        db.add(student)
        db.flush()
        academic = AcademicStudent(tenant_id=TID, student_id=student.id,
                                   student_no=student.student_no, name=student.real_name)
        db.add(academic)
        db.flush()

        college_user = _grant(db, "college_admin01", "张晓明")
        office_user = _grant(db, "school_admin01", "陈校")
        college.secretary_id = int(college_user.id)

        # 学院教务只能审本院任务：数据范围同样要真实配置，不能靠"没人拦"通过。
        from app.models import TeacherStudentScope

        db.add(TeacherStudentScope(tenant_id=TID, teacher_key="college_admin01",
                                   teacher_name="张晓明", role_code="COLLEGE_ADMIN",
                                   scope_type="COLLEGE", ref_value=COLLEGE_NAME, status="ACTIVE"))

        task = AaGradeTask(tenant_id=TID, term_id=term.id, term_code="2026-2027-1",
                           course_name="数据结构", class_id=klass.id, teacher_key="teacher01",
                           credit=4, usual_ratio=30, midterm_ratio=0, final_ratio=70,
                           pass_line=60, status="PUBLISHED")
        db.add(task)
        db.flush()
        total = round(usual * 0.3 + final * 0.7)
        record = AaGradeRecord(tenant_id=TID, task_id=task.id, student_id=student.id,
                               usual_score=usual, final_score=final, total_score=total,
                               pass_status="PASSED" if total >= 60 else "FAILED",
                               source="PUBLISH", version_no=1)
        db.add(record)
        db.flush()
        grade = AcademicGrade(tenant_id=TID, acad_student_id=academic.id, course_name="数据结构",
                              course_code="CS101", course_version=1, attempt_no=1,
                              grade_task_id=task.id, grade_record_id=record.id,
                              term="2026-2027-1", nature="REQUIRED", credit_value=4,
                              score=total, pass_status=record.pass_status, exam_type="FINAL",
                              record_status="ACTIVE", source="PUBLISH")
        db.add(grade)
        db.flush()
        record.acad_grade_id = grade.id
        db.commit()
        return {
            "taskId": int(task.id), "recordId": int(record.id), "gradeId": int(grade.id),
            "studentId": int(student.id), "acadStudentId": int(academic.id),
            "collegeUserId": int(college_user.id), "officeUserId": int(office_user.id),
        }
    finally:
        db.close()


def _change_tasks(db):
    """只看成绩更正工作流的任务；db_mode 的最小种子里另有一条无关待办任务。"""
    from app.models import WorkflowInstance, WorkflowTask

    instance_ids = [
        int(value) for (value,) in db.query(WorkflowInstance.id).filter(
            WorkflowInstance.tenant_id == TID,
            WorkflowInstance.source_biz_type == "AA_GRADE_CHANGE",
        ).all()
    ]
    return db.query(WorkflowTask).filter(
        WorkflowTask.tenant_id == TID,
        WorkflowTask.instance_id.in_(instance_ids or [0]),
    ).order_by(WorkflowTask.id).all()


def _record_state(record_id):
    from app.models import AaGradeRecord

    db = get_sessionmaker()()
    try:
        row = db.get(AaGradeRecord, int(record_id))
        return {
            "usual": row.usual_score, "final": row.final_score, "total": row.total_score,
            "pass": row.pass_status, "source": row.source, "version": int(row.version_no or 1),
            "acadGradeId": int(row.acad_grade_id or 0),
        }
    finally:
        db.close()


def _grades(acad_student_id):
    from app.models import AcademicGrade

    db = get_sessionmaker()()
    try:
        return db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == TID,
            AcademicGrade.acad_student_id == acad_student_id,
        ).order_by(AcademicGrade.id).all()
    finally:
        db.close()


def _apply(ids, *, new_final=90, reason="期末卷面登分错误，需按原卷更正"):
    _activate("teacher01", "ACADEMIC_TEACHER")
    body = SimpleNamespace(reason=reason, newUsualScore=None, newMidtermScore=None,
                           newFinalScore=new_final)
    return command.change_request(ids["taskId"], ids["recordId"],
                                 _ctx("teacher01", "ACADEMIC_TEACHER"), body)


@pytest.mark.usefixtures("db_mode")
def test_change_request_does_not_touch_formal_grade():
    """C05：发起更正不得改动正式成绩明细或正式成绩行。"""
    ids = _seed_published_grade()
    before_record = _record_state(ids["recordId"])
    before_grades = [(row.id, row.score, row.record_status) for row in _grades(ids["acadStudentId"])]

    result = _apply(ids)
    assert result["status"] == "CHANGE_REVIEW"
    assert int(result["assigneeId"]) == ids["collegeUserId"]
    assert result["proposedTotalScore"] != result["currentTotalScore"]

    assert _record_state(ids["recordId"]) == before_record
    assert [(row.id, row.score, row.record_status) for row in _grades(ids["acadStudentId"])] == before_grades


@pytest.mark.usefixtures("db_mode")
def test_workflow_tasks_always_have_a_real_assignee():
    """NEW-P1-02：两个节点的待审任务都必须落到真实受理人，不允许 assignee_id=0。"""
    from app.models import WorkflowTask

    ids = _seed_published_grade()
    _apply(ids)

    _activate("college_admin01", "COLLEGE_ADMIN")
    command.change_college_review(ids["recordId"], _ctx("college_admin01", "COLLEGE_ADMIN"), "APPROVE")

    db = get_sessionmaker()()
    try:
        tasks = _change_tasks(db)
        assert tasks
        assert all(int(row.assignee_id or 0) > 0 for row in tasks)
        pending = [row for row in tasks if row.status == "PENDING"]
        assert len(pending) == 1
        assert pending[0].node_code == "ACADEMIC_REVIEW"
        assert int(pending[0].assignee_id) == ids["officeUserId"]
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_final_approval_appends_new_version_and_supersedes_original():
    """终审通过 = 追加新版本 + 原行 SUPERSEDED，不是原地覆盖。"""
    ids = _seed_published_grade()
    _apply(ids, new_final=90)
    _activate("college_admin01", "COLLEGE_ADMIN")
    command.change_college_review(ids["recordId"], _ctx("college_admin01", "COLLEGE_ADMIN"), "APPROVE")
    _activate("school_admin01", "SCHOOL_ADMIN")
    result = command.change_academic_review(ids["recordId"], _ctx("school_admin01", "SCHOOL_ADMIN"),
                                            "APPROVE")

    rows = _grades(ids["acadStudentId"])
    assert len(rows) == 2
    original, corrected = rows
    assert original.id == ids["gradeId"] and original.record_status == "SUPERSEDED"
    assert corrected.record_status == "ACTIVE" and corrected.source == "CHANGE"
    assert str(corrected.id) == result["correctedGradeId"]
    # 30% * 60 + 70% * 90 = 81
    assert corrected.score == 81

    state = _record_state(ids["recordId"])
    assert state["total"] == 81 and state["acadGradeId"] == corrected.id
    assert state["version"] == 2

    from app.models.academic_affairs_effective_grade import AaGradeCorrection

    db = get_sessionmaker()()
    try:
        link = db.query(AaGradeCorrection).filter(AaGradeCorrection.tenant_id == TID).one()
        assert link.source_type == "CHANGE_REQUEST"
        assert link.original_grade_id == original.id and link.corrected_grade_id == corrected.id
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_consecutive_corrections_form_a_to_b_to_c_chain():
    """连续两次更正必须形成 A→B→C 完整链，只有最后一条是 ACTIVE。"""
    ids = _seed_published_grade()
    for score in (90, 75):
        _apply(ids, new_final=score)
        _activate("college_admin01", "COLLEGE_ADMIN")
        command.change_college_review(ids["recordId"], _ctx("college_admin01", "COLLEGE_ADMIN"), "APPROVE")
        _activate("school_admin01", "SCHOOL_ADMIN")
        command.change_academic_review(ids["recordId"], _ctx("school_admin01", "SCHOOL_ADMIN"), "APPROVE")

    rows = _grades(ids["acadStudentId"])
    assert len(rows) == 3
    assert [row.record_status for row in rows] == ["SUPERSEDED", "SUPERSEDED", "ACTIVE"]
    assert [row.score for row in rows] == [60, 81, 70]  # 30%*60+70%*75 = 70.5 → 70


@pytest.mark.usefixtures("db_mode")
def test_reject_changes_no_formal_fact():
    """驳回不改变任何正式事实。"""
    ids = _seed_published_grade()
    before_record = _record_state(ids["recordId"])
    before_grades = [(row.id, row.score, row.record_status) for row in _grades(ids["acadStudentId"])]

    _apply(ids)
    _activate("college_admin01", "COLLEGE_ADMIN")
    command.change_college_review(ids["recordId"], _ctx("college_admin01", "COLLEGE_ADMIN"),
                                  "REJECT", "卷面复核后确认原分数无误")

    assert _record_state(ids["recordId"]) == before_record
    assert [(row.id, row.score, row.record_status) for row in _grades(ids["acadStudentId"])] == before_grades


@pytest.mark.usefixtures("db_mode")
def test_failed_final_approval_rolls_back_everything(monkeypatch):
    """C06：终审任一步失败，正式成绩、工作流、审计和消息全部回滚。"""
    from app.models import AffairsAuditTrail, MessageEventOutbox
    from app.models.academic_affairs_effective_grade import AaGradeChangeRequest

    ids = _seed_published_grade()
    _apply(ids)
    _activate("college_admin01", "COLLEGE_ADMIN")
    command.change_college_review(ids["recordId"], _ctx("college_admin01", "COLLEGE_ADMIN"), "APPROVE")

    before_record = _record_state(ids["recordId"])
    before_grades = [(row.id, row.score, row.record_status) for row in _grades(ids["acadStudentId"])]

    def _boom(*_args, **_kwargs):
        raise RuntimeError("injected outbox failure")

    monkeypatch.setattr(
        "app.services.message_event_outbox_service.emit_receiver_notice", _boom)

    _activate("school_admin01", "SCHOOL_ADMIN")
    with pytest.raises(RuntimeError):
        command.change_academic_review(ids["recordId"], _ctx("school_admin01", "SCHOOL_ADMIN"), "APPROVE")

    assert _record_state(ids["recordId"]) == before_record
    assert [(row.id, row.score, row.record_status) for row in _grades(ids["acadStudentId"])] == before_grades

    db = get_sessionmaker()()
    try:
        request = db.query(AaGradeChangeRequest).filter(AaGradeChangeRequest.tenant_id == TID).one()
        assert request.status == "PENDING"
        pending = [row for row in _change_tasks(db) if row.status == "PENDING"]
        assert len(pending) == 1 and pending[0].node_code == "ACADEMIC_REVIEW"
        assert db.query(AffairsAuditTrail).filter(
            AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.action == "CHANGE_APPROVE").count() == 0
        assert db.query(MessageEventOutbox).filter(
            MessageEventOutbox.tenant_id == TID,
            MessageEventOutbox.event_code == "GRADE.CORRECTED").count() == 0
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_two_concurrent_final_approvals_only_one_wins():
    """两人并发终审只有一个成功，正式成绩只追加一条新版本。"""
    ids = _seed_published_grade()
    _apply(ids)
    _activate("college_admin01", "COLLEGE_ADMIN")
    command.change_college_review(ids["recordId"], _ctx("college_admin01", "COLLEGE_ADMIN"), "APPROVE")

    barrier = Barrier(2)

    def approve(_index):
        _activate("school_admin01", "SCHOOL_ADMIN")
        barrier.wait()
        try:
            command.change_academic_review(ids["recordId"], _ctx("school_admin01", "SCHOOL_ADMIN"),
                                           "APPROVE")
            return "ok"
        except AppException as exc:
            return f"rejected:{exc.code}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(approve, range(2)))

    assert results.count("ok") == 1, results
    assert results.count("rejected:APPROVAL_VERSION_CONFLICT") == 1, results
    rows = _grades(ids["acadStudentId"])
    assert len(rows) == 2
    assert sum(1 for row in rows if row.record_status == "ACTIVE") == 1


@pytest.mark.usefixtures("db_mode")
def test_duplicate_pending_request_is_rejected():
    """同一成绩只允许一条在途更正申请。"""
    ids = _seed_published_grade()
    _apply(ids)
    with pytest.raises(AppException) as exc:
        _apply(ids, new_final=95)
    assert exc.value.code == "DATA_CONFLICT"


@pytest.mark.usefixtures("db_mode")
def test_apply_without_resolvable_assignee_is_blocked():
    """解析不到唯一真实受理人时禁止发起，绝不落 assignee_id=0 的无人任务。"""
    from app.models import College
    from app.models.academic_affairs_effective_grade import AaGradeChangeRequest

    ids = _seed_published_grade()
    db = get_sessionmaker()()
    try:
        college = db.query(College).filter(College.tenant_id == TID,
                                           College.college_name == COLLEGE_NAME).one()
        college.secretary_id = None
        db.commit()
    finally:
        db.close()

    with pytest.raises(AppException) as exc:
        _apply(ids)
    assert exc.value.code == "DATA_CONFLICT"

    db = get_sessionmaker()()
    try:
        assert db.query(AaGradeChangeRequest).filter(
            AaGradeChangeRequest.tenant_id == TID).count() == 0
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_reviewer_must_be_the_assigned_person():
    """任务已明确分配给学院受理人时，别人不能抢办。"""
    ids = _seed_published_grade()
    _apply(ids)
    _activate("school_admin01", "SCHOOL_ADMIN")
    with pytest.raises(AppException):
        command.change_college_review(ids["recordId"], _ctx("school_admin01", "SCHOOL_ADMIN"),
                                      "APPROVE")
