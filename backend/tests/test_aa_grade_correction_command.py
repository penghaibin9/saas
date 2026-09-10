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

import json

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


from app.models import AaGradeTask, AaGradeRecord, AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTeachingClass, User
from app.models.academic_affairs_effective_grade import AaGradeChangeRequest, AaEffectiveGradePolicy
from app.modules.academic_affairs.services import academic_affairs_grade_change_authority_service as authority
from app.modules.academic_affairs.services import academic_affairs_grade_change_component_service as components
from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as classes
from app.modules.academic_affairs.services import academic_affairs_roster_consumer_service as roster

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


def _seed_initial_grade(*, usual=60, final=60):
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
                              gpa_point=round(max(0, (total - 50) / 10), 2) if total >= 60 else 0,
                              gpa_policy_code="DEFAULT", gpa_policy_version=1,
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


def _seed_published_grade(*, usual=60, final=60, dynamic=False):
    _activate()
    ids = _seed_initial_grade(usual=usual, final=final)
    with get_sessionmaker()() as db:
        task=db.get(AaGradeTask,ids['taskId'])
        course=AaCourse(tenant_id=TID,course_code='CS101',course_name='数据结构',credit=4,version=1,status='ENABLED')
        db.add(course);db.flush()
        batch=AaTeachingTaskBatch(tenant_id=TID,term_id=task.term_id,batch_name='正式成绩测试任务',status='APPROVED')
        db.add(batch);db.flush()
        teaching=AaTeachingTask(tenant_id=TID,batch_id=batch.id,course_id=course.id,course_code=course.course_code,course_name=course.course_name,class_id=task.class_id,teacher_key='teacher01',status='READY')
        db.add(teaching);db.flush()
        task.course_id=course.id;task.teaching_task_id=teaching.id
        tc=AaTeachingClass(tenant_id=TID,teaching_task_id=teaching.id,term_id=task.term_id,course_id=course.id,class_code='GC-CLASS',class_name='更正教学班',status='ACTIVE')
        db.add(tc);db.flush()
        classes.create_roster_version(db,tc,[ids['studentId']],source_type='ADMIN_CLASS',source_id=task.class_id)
        db.flush()
        roster.freeze_consumer_snapshot(db,'GRADE_TASK',task.id,teaching.id)
        if not db.query(AaEffectiveGradePolicy).filter_by(tenant_id=TID,status='ACTIVE').first():
            db.add(AaEffectiveGradePolicy(tenant_id=TID,policy_code='GC',policy_version=1,active_scope_key='BASE',attempt_strategy='LATEST_ATTEMPT',status='ACTIVE'))
        # A real ACTIVE teacher account is needed by workflow applicant and file ownership.
        teacher=db.query(User).filter_by(tenant_id=TID,login_name='teacher01').first()
        if teacher is None:
            teacher=User(tenant_id=TID,login_name='teacher01',real_name='教师',password_hash='x',user_type='TEACHER',status='ACTIVE')
            db.add(teacher);db.flush()
        ids.update(teachingClassId=tc.id,courseId=course.id,teacherUserId=teacher.id)
        if dynamic:
            from app.models.academic_affairs_r10 import AaGradeSchemeSnapshot,AaGradeComponentScore
            scheme=[{'code':'USUAL','name':'平时','weight':30},{'code':'FINAL','name':'期末','weight':70}]
            db.add(AaGradeSchemeSnapshot(tenant_id=TID,grade_task_id=task.id,scheme_json=json.dumps(scheme),scheme_version=1,status='LOCKED'))
            for item in scheme:
                db.add(AaGradeComponentScore(tenant_id=TID,grade_task_id=task.id,grade_record_id=ids['recordId'],student_id=ids['studentId'],component_code=item['code'],component_name=item['name'],weight=item['weight'],score=usual if item['code']=='USUAL' else final,weighted_score=(usual if item['code']=='USUAL' else final)*item['weight']/100,scheme_version=1))
        db.commit()
    return ids

def _application_body(ids, **changes):
    with get_sessionmaker()() as db:
        task=db.get(AaGradeTask,ids['taskId']);record=db.get(AaGradeRecord,ids['recordId'])
        dynamic = command._has_dynamic(db, task.id)
        values=dict(reason='期末卷面登记有误，请核对原卷更正',newUsualScore=None,newMidtermScore=None,newFinalScore=None if dynamic else 90,expectedGradeVersion=record.version_no,expectedCurrentGradeId=record.acad_grade_id,expectedAuthorityHash=authority.digest(authority.source(db,task,record)),attachmentIds=[])
        if dynamic:
            values.update(expectedComponentHash=components.digest(components.source(db,task,record)),newComponentScores={'USUAL':60,'FINAL':90})
        values.update(changes)
        return SimpleNamespace(**values)

def _review_identity(ids):
    from app.models import WorkflowTask
    with get_sessionmaker()() as db:
        req=db.query(AaGradeChangeRequest).filter_by(tenant_id=TID,grade_record_id=ids['recordId'],status='PENDING').one()
        task=db.get(WorkflowTask,req.current_task_id)
        return dict(changeRequestId=req.id,expectedRequestVersion=req.version,currentTaskId=task.id,expectedTaskVersion=task.version)

def _state(ids):
    return _record_state(ids['recordId']),[(g.id,g.score,g.record_status) for g in _grades(ids['acadStudentId'])]

def _apply(ids, *, new_final=90, reason="期末卷面登分错误，需按原卷更正", command_key=None):
    user = _activate("teacher01", "ACADEMIC_TEACHER")
    body = _application_body(ids, reason=reason)
    if getattr(body, "newComponentScores", None) is not None:
        body.newComponentScores["FINAL"] = new_final
    else:
        body.newFinalScore = new_final
    return command.change_request(ids["taskId"], ids["recordId"], user, body, command_key=command_key)


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
    command.change_college_review(ids["recordId"], _ctx("college_admin01", "COLLEGE_ADMIN"), "APPROVE", identity=_review_identity(ids))

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
@pytest.mark.parametrize("dynamic", [False, True])
def test_final_approval_appends_new_version_and_supersedes_original(dynamic):
    """终审通过 = 追加新版本 + 原行 SUPERSEDED，不是原地覆盖。"""
    ids = _seed_published_grade(dynamic=dynamic)
    before = _state(ids)
    _apply(ids, new_final=90)
    assert _state(ids) == before
    _activate("college_admin01", "COLLEGE_ADMIN")
    command.change_college_review(ids["recordId"], _ctx("college_admin01", "COLLEGE_ADMIN"), "APPROVE", identity=_review_identity(ids))
    assert _state(ids) == before
    _activate("school_admin01", "SCHOOL_ADMIN")
    result = command.change_academic_review(ids["recordId"], _ctx("school_admin01", "SCHOOL_ADMIN"),
                                            "APPROVE", identity=_review_identity(ids), command_key="correction-final-key")

    rows = _grades(ids["acadStudentId"])
    assert len(rows) == 2
    original, corrected = rows
    assert original.id == ids["gradeId"] and original.record_status == "SUPERSEDED"
    assert corrected.record_status == "ACTIVE" and corrected.source == "CHANGE"
    assert str(corrected.id) == result["correctedGradeId"]
    # 30% * 60 + 70% * 90 = 81
    assert corrected.score == 81
    assert float(original.gpa_point) == 1.0, '旧60分版本保留已冻结绩点'
    assert float(corrected.gpa_point) == 3.1, '更正81分不得复制旧版本的1.0绩点'

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


    assert isinstance(result["warningScanOk"], bool)
    assert result["warningScanOk"] or result["warningScanError"]
    from app.modules.academic_affairs.services import academic_affairs_grade_command_receipt as receipts
    receipt = receipts.read(_ctx("school_admin01", "SCHOOL_ADMIN"), "GRADE_CHANGE_REVIEW", "correction-final-key")
    assert receipt["state"] == "SUCCESS"
    assert receipt["result"]["correctedGradeId"] == result["correctedGradeId"]

@pytest.mark.usefixtures("db_mode")
def test_consecutive_corrections_form_a_to_b_to_c_chain():
    """连续两次更正必须形成 A→B→C 完整链，只有最后一条是 ACTIVE。"""
    ids = _seed_published_grade()
    for score in (90, 75):
        _apply(ids, new_final=score)
        _activate("college_admin01", "COLLEGE_ADMIN")
        command.change_college_review(ids["recordId"], _ctx("college_admin01", "COLLEGE_ADMIN"), "APPROVE", identity=_review_identity(ids))
        _activate("school_admin01", "SCHOOL_ADMIN")
        command.change_academic_review(ids["recordId"], _ctx("school_admin01", "SCHOOL_ADMIN"), "APPROVE", identity=_review_identity(ids))

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
                                  "REJECT", "卷面复核后确认原分数无误", identity=_review_identity(ids))

    assert _record_state(ids["recordId"]) == before_record
    assert [(row.id, row.score, row.record_status) for row in _grades(ids["acadStudentId"])] == before_grades


@pytest.mark.usefixtures("db_mode")
def test_failed_final_approval_rolls_back_everything(monkeypatch):
    """C06：终审任一步失败，正式成绩、工作流、审计和消息全部回滚。"""
    from app.models import AffairsAuditTrail, MessageEventOutbox
    from app.models.academic_affairs_effective_grade import AaGradeChangeRequest

    ids = _seed_published_grade(dynamic=True)
    _apply(ids)
    _activate("college_admin01", "COLLEGE_ADMIN")
    command.change_college_review(ids["recordId"], _ctx("college_admin01", "COLLEGE_ADMIN"), "APPROVE", identity=_review_identity(ids))

    before_record = _record_state(ids["recordId"])
    before_grades = [(row.id, row.score, row.record_status) for row in _grades(ids["acadStudentId"])]

    with get_sessionmaker()() as snapshot_db:
        before_components = components.source(snapshot_db, snapshot_db.get(AaGradeTask, ids["taskId"]), snapshot_db.get(AaGradeRecord, ids["recordId"]))

    def _boom(*_args, **_kwargs):
        raise RuntimeError("injected outbox failure")

    monkeypatch.setattr(
        "app.services.message_event_outbox_service.emit_receiver_notice", _boom)

    _activate("school_admin01", "SCHOOL_ADMIN")
    with pytest.raises(RuntimeError):
        command.change_academic_review(ids["recordId"], _ctx("school_admin01", "SCHOOL_ADMIN"), "APPROVE", identity=_review_identity(ids), command_key="rollback-final-key")

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


    from app.models.idempotency import IdempotencyRecord
    with get_sessionmaker()() as db:
        assert components.source(db, db.get(AaGradeTask, ids["taskId"]), db.get(AaGradeRecord, ids["recordId"])) == before_components
        assert db.query(IdempotencyRecord).filter(IdempotencyRecord.tenant_id == TID).count() == 0

@pytest.mark.usefixtures("db_mode")
def test_two_concurrent_final_approvals_only_one_wins():
    """两人并发终审只有一个成功，正式成绩只追加一条新版本。"""
    ids = _seed_published_grade()
    _apply(ids)
    _activate("college_admin01", "COLLEGE_ADMIN")
    command.change_college_review(ids["recordId"], _ctx("college_admin01", "COLLEGE_ADMIN"), "APPROVE", identity=_review_identity(ids))

    frozen_identity = _review_identity(ids)
    barrier = Barrier(2)

    def approve(_index):
        _activate("school_admin01", "SCHOOL_ADMIN")
        barrier.wait()
        try:
            command.change_academic_review(ids["recordId"], _ctx("school_admin01", "SCHOOL_ADMIN"),
                                           "APPROVE", identity=frozen_identity, command_key=f"concurrent-final-{_index}")
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
                                      "APPROVE", identity=_review_identity(ids))


def _college(ids):
    user=_activate('college_admin01','COLLEGE_ADMIN')
    return command.change_college_review(ids['recordId'],user,'APPROVE',identity=_review_identity(ids))

def _final(ids,**kwargs):
    user=_activate('school_admin01','SCHOOL_ADMIN')
    return command.change_academic_review(ids['recordId'],user,'APPROVE',identity=_review_identity(ids),**kwargs)


@pytest.mark.usefixtures("db_mode")
@pytest.mark.parametrize("mutation", ["roster", "policy", "component", "material", "version"])
def test_source_change_blocks_final_and_preserves_formal(mutation):
    dynamic=mutation=='component'
    ids=_seed_published_grade(dynamic=dynamic)
    _apply(ids);_college(ids)
    with get_sessionmaker()() as db:
        if mutation=='roster':
            tc=db.get(AaTeachingClass,ids['teachingClassId'])
            classes.create_roster_version(db,tc,[ids['studentId']],source_type='MANUAL',source_id=tc.id,reason='明确名单来源换版测试')
        elif mutation=='policy':
            policy=db.query(AaEffectiveGradePolicy).filter_by(tenant_id=TID,status='ACTIVE').first();policy.makeup_cap=55
        elif mutation=='component':
            from app.models.academic_affairs_r10 import AaGradeComponentScore
            row=db.query(AaGradeComponentScore).filter_by(tenant_id=TID,grade_task_id=ids['taskId']).first();row.version+=1
        elif mutation=='material':
            # Frozen empty manifest integrity is a real invalid-evidence case; no file mocks.
            req=db.query(AaGradeChangeRequest).filter_by(tenant_id=TID,grade_record_id=ids['recordId']).one();req.evidence_manifest_hash='0'*64
        elif mutation=='version':
            db.get(AaGradeRecord,ids['recordId']).version_no+=1
        db.commit()
    before=_state(ids)
    with pytest.raises(AppException) as failure:_final(ids,command_key='candidate-blocked-final')
    assert failure.value.http_status==409
    assert _state(ids)==before
    with get_sessionmaker()() as db:
        req=db.query(AaGradeChangeRequest).filter_by(tenant_id=TID,grade_record_id=ids['recordId']).one()
        assert req.status=='PENDING'
        from app.models.idempotency import IdempotencyRecord
        assert db.query(IdempotencyRecord).filter(IdempotencyRecord.tenant_id==TID).count()==0


@pytest.mark.usefixtures("db_mode")
def test_actual_bound_file_quarantined_blocks_final():
    from app.models.file import FileObject,FileBinding
    from app.core.context import set_current_user
    ids=_seed_published_grade()
    with get_sessionmaker()() as db:
        file=FileObject(tenant_id=TID,file_key='candidate-grade-evidence',file_name='原卷.pdf',sha256='a'*64,status='AVAILABLE',scan_status='CLEAN',owner_user_id=ids['teacherUserId'],visibility='PRIVATE',biz_type='TEMP_PRIVATE')
        db.add(file);db.commit();fid=file.id
    user=_activate('teacher01','ACADEMIC_TEACHER');user['userId']=str(ids['teacherUserId']);set_current_user(user)
    command.change_request(ids['taskId'],ids['recordId'],user,_application_body(ids,attachmentIds=[str(fid)]))
    _college(ids)
    with get_sessionmaker()() as db:
        assert db.query(FileBinding).filter_by(tenant_id=TID,file_id=fid,status='ACTIVE').count()==1
        file=db.get(FileObject,fid);file.status='QUARANTINED';file.scan_status='INFECTED';db.commit()
    before=_state(ids)
    with pytest.raises(AppException) as failure:_final(ids)
    assert failure.value.http_status==409 and _state(ids)==before


@pytest.mark.usefixtures("db_mode")
def test_real_warning_scan_failure_keeps_committed_grade_and_honest_receipt(monkeypatch):
    from app.modules.academic_affairs.services import academic_grade_effect_service as effects
    ids=_seed_published_grade();_apply(ids);_college(ids)
    def fail(*args,**kwargs):raise RuntimeError('injected warning scan failure')
    # Fail only the post-commit effect runner. Grade, workflow and durable command are real MySQL.
    monkeypatch.setattr(effects,'run_effect',fail)
    result=_final(ids,command_key='scan-failure-final')
    assert result['warningScanOk'] is False and result['warningScanError']
    assert result['warningScanState']=='UNKNOWN'
    assert [g[2] for g in _state(ids)[1]]==['SUPERSEDED','ACTIVE']
    from app.modules.academic_affairs.services import academic_affairs_grade_command_receipt as receipts
    persisted=receipts.read(_ctx('school_admin01','SCHOOL_ADMIN'),'GRADE_CHANGE_REVIEW','scan-failure-final')
    assert persisted['state']=='SUCCESS'
    assert persisted['result']['correctedGradeId']==result['correctedGradeId']
    assert persisted['result']['warningScanOk'] is False
