"""第五版：批次开课责任与毕业校院节点分离的行为回归。"""
from types import SimpleNamespace

import pytest
from sqlalchemy import select


def test_task_batch_responsibility_ignores_student_college(db_mode, monkeypatch):
    from app.core.context import set_tenant
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch
    from app.modules.academic_affairs.services import academic_affairs_task_service as service
    from app.modules.academic_affairs.services import academic_affairs_task_generation_service as generation

    tid = 1000000000000000001
    set_tenant(tid)
    with get_sessionmaker()() as db:
        course = AaCourse(tenant_id=tid, course_code="V5-CROSS", course_name="跨院课程", owner_college_id=11)
        a = AaTeachingTaskBatch(tenant_id=tid, term_id=202601, batch_name="学院甲", college_id=11)
        b = AaTeachingTaskBatch(tenant_id=tid, term_id=202601, batch_name="学院乙", college_id=22)
        foreign = AaTeachingTaskBatch(tenant_id=tid + 1, term_id=202601, batch_name="另一学校", college_id=11)
        db.add_all([course, a, b, foreign])
        db.flush()
        owned = AaTeachingTask(tenant_id=tid, batch_id=a.id, course_id=course.id, class_id=None, formation_mode="SELECTABLE")
        borrowed_class = AaTeachingTask(tenant_id=tid, batch_id=b.id, course_id=course.id, class_id=100)
        cross_tenant = AaTeachingTask(tenant_id=tid, batch_id=foreign.id, course_id=course.id, class_id=100)
        db.add_all([owned, borrowed_class, cross_tenant])
        db.flush()
        scope = service.TaskManageScope(college_ids={11}, class_ids={100}, role="COLLEGE_ADMIN")
        monkeypatch.setattr(service, "_scope", lambda user, session: scope)
        ids = set(db.scalars(select(AaTeachingTask.id).where(
            AaTeachingTask.tenant_id == tid, *service._visible_task_conditions(scope, AaTeachingTask),
        )).all())
        assert ids == {owned.id}
        assert service._ensure_task_visible(db, owned.id, {})[0].id == owned.id
        with pytest.raises(AppException) as denied:
            service._ensure_task_visible(db, borrowed_class.id, {})
        assert denied.value.code == "NO_DATA_SCOPE"
        assert not db.scalars(generation._college_editable_batch_integrity_statement(a)).all()

        from app.models import AaGradeTask
        from app.modules.academic_affairs.services import academic_affairs_grade_correction_command as correction
        from app.modules.academic_affairs.services import academic_affairs_grade_task_read_service as grades
        from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as schedule
        from app.modules.academic_affairs.services import academic_affairs_schedule_policy as policy
        from app.services import platform_service
        a.status = b.status = "APPROVED"
        owned.status = borrowed_class.status = "READY"
        course.category = "PUBLIC_BASIC"
        grade = AaGradeTask(tenant_id=tid, teaching_task_id=borrowed_class.id, course_id=course.id,
                            class_id=100, status="SUBMITTED")
        db.add(grade)
        db.flush()
        assert correction._task_college_id(db, grade) == 11
        assert correction._task_college_id(db, SimpleNamespace(task_id=borrowed_class.id, class_id=100)) == 11
        assert correction._task_college_id(db, SimpleNamespace(class_id=100)) is None
        assert db.scalars(select(AaGradeTask.id).where(grades.college_scope_condition({11}))).all() == [grade.id]
        assert not db.scalars(select(AaGradeTask.id).where(grades.college_scope_condition({22}))).all()
        schedule_batch = SimpleNamespace(college_id=11, term_id=202601)
        config = SimpleNamespace(enabled=True, config_json={"mode": "HYBRID"})
        monkeypatch.setattr(platform_service, "_get_cfg", lambda *args: config)
        assert schedule._resolve_task(db, schedule_batch, {"taskId": borrowed_class.id}).id == borrowed_class.id
        config.config_json["mode"] = "OFFERING_UNIT"
        assert schedule._resolve_task(db, schedule_batch, {"taskId": owned.id}).id == owned.id
        config.config_json["mode"] = "SCHOOL_CENTRALIZED"
        assert borrowed_class.id in db.scalars(select(AaTeachingTask.id).where(
            policy.task_scope_condition(db, schedule_batch, include_centralized_public=True),
        )).all()
        with pytest.raises(AppException):
            schedule._resolve_task(db, schedule_batch, {"taskId": borrowed_class.id})
        assert schedule._resolve_task(db, SimpleNamespace(college_id=None, term_id=202601),
                                      {"taskId": borrowed_class.id}).id == borrowed_class.id
        course.category = "MAJOR_CORE"
        db.flush()
        assert not db.scalars(select(AaTeachingTask.id).where(
            policy.task_scope_condition(db, SimpleNamespace(college_id=None)),
        )).all()
        assert schedule._resolve_task(db, schedule_batch, {"taskId": borrowed_class.id}).id == borrowed_class.id
        with pytest.raises(AppException):
            schedule._resolve_task(db, SimpleNamespace(college_id=22, term_id=202601), {"taskId": owned.id})
        config.config_json["mode"] = "INVALID"
        with pytest.raises(AppException):
            policy.task_scope_condition(db, schedule_batch)


@pytest.mark.parametrize("scope_type", ["TENANT_ALL", "SELF", "NONE"])
def test_graduation_college_review_rejects_non_college_scope(monkeypatch, scope_type):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_graduation_scope_guard as guard

    monkeypatch.setattr(guard, "build_affairs_context", lambda user, db: SimpleNamespace(scope_type=scope_type, college_ids={11}))
    with pytest.raises(AppException) as denied:
        guard.assert_college_review_authority(None, {"currentRoleCode": "ACADEMIC_ADMIN"}, SimpleNamespace(student_id=1))
    assert denied.value.code == "NO_DATA_SCOPE"


def test_graduation_college_review_requires_current_assignee(monkeypatch):
    from app.core.context import set_tenant
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_graduation_scope_guard as guard
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as responsibility

    set_tenant(1000000000000000001)
    context = SimpleNamespace(scope_type="COLLEGE", college_ids={11}, permission_codes={"academicAffairs.graduation.collegeReview"})
    monkeypatch.setattr(guard, "build_affairs_context", lambda user, db: context)
    db = SimpleNamespace(scalar=lambda statement: SimpleNamespace(college_id=11),
                         get=lambda model, key: SimpleNamespace(tenant_id=1000000000000000001, is_deleted=False, status="ACTIVE"))
    projection = {"resolved": True, "assigneeUserIds": ["101"]}
    monkeypatch.setattr(responsibility, "resolve_organization", lambda *args, **kwargs: projection)
    assert guard.assert_college_review_authority(db, {"userId": "db-101"}, SimpleNamespace(student_id=1)) == projection
    with pytest.raises(AppException):
        guard.assert_college_review_authority(db, {"userId": "db-102"}, SimpleNamespace(student_id=1))
    context.permission_codes = set()
    with pytest.raises(AppException):
        guard.assert_college_review_authority(db, {"userId": "db-101"}, SimpleNamespace(student_id=1))
    context.permission_codes = {"academicAffairs.graduation.collegeReview"}
    projection["resolved"] = False
    with pytest.raises(AppException):
        guard.assert_college_review_authority(db, {"userId": "db-101"}, SimpleNamespace(student_id=1))


@pytest.mark.parametrize("status,permissions,expected", [
    ("INPUTTING", {"academicAffairs.grade.input"}, {"VIEW", "INPUT", "IMPORT"}),
    ("INPUTTING", {"academicAffairs.grade.submit"}, {"VIEW", "SUBMIT"}),
    ("PUBLISHED", {"academicAffairs.gradeChange.apply"}, {"VIEW", "REQUEST_CHANGE"}),
    ("PUBLISHED", {"academicAffairs.grade.input"}, {"VIEW"}),
])
def test_grade_teacher_buttons_match_command_permissions(status, permissions, expected):
    from app.modules.academic_affairs.services import academic_affairs_grade_task_read_service as read
    ctx = SimpleNamespace(scope_type="COURSE", permission_codes=permissions)
    assert set(read._allowed_actions(SimpleNamespace(status=status), {}, True, context=ctx)) == expected
    assert read._allowed_actions(SimpleNamespace(status=status), {}, False, context=ctx) == ["VIEW"]


def test_grade_overdue_recipients_require_matching_scope_and_permission(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_grade_deadline_scheduler_service as scheduler
    rows = [(SimpleNamespace(id=i, login_name=str(i), user_type="TEACHER"),
             SimpleNamespace(id=i, role_code="CUSTOM")) for i in range(1, 5)]
    contexts = {
        "1": SimpleNamespace(scope_type="TENANT_ALL", permission_codes={"academicAffairs.grade.collegeReview"}, college_ids=set()),
        "2": SimpleNamespace(scope_type="COLLEGE", permission_codes={"academicAffairs.grade.publish"}, college_ids={11}),
        "3": SimpleNamespace(scope_type="TENANT_ALL", permission_codes={"academicAffairs.grade.publish"}, college_ids=set()),
        "4": SimpleNamespace(scope_type="COLLEGE", permission_codes={"academicAffairs.grade.collegeReview"}, college_ids={11}),
    }
    monkeypatch.setattr(scheduler, "build_affairs_context", lambda user, db: contexts[user["userId"]])
    db = SimpleNamespace(execute=lambda statement: SimpleNamespace(all=lambda: rows))
    assert scheduler._admin_scopes(db) == {3: None, 4: {11}}


def test_centralized_public_and_college_professional_schedules_publish_independently(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaProgram, AaProgramCourse, AaTeachingTask, AaTeachingTaskBatch, AaScheduleBatch
    from app.services import platform_service
    from app.modules.academic_affairs.services import academic_affairs_schedule_truth_service as truth
    from tests.test_aa_schedule import _hdr, _term, _seed_single_publishable_task, _item, BASE, TID

    headers = _hdr(client, "school_admin01")
    term_id = _term(client, headers)
    class_id = _seed_single_publishable_task(term_id)
    # 只替换已有配置中心的参数读值，所有命令、完整性/资源门禁与MySQL写入保持真实。
    original_cfg = platform_service._get_cfg
    monkeypatch.setattr(platform_service, "_get_cfg", lambda db, tid, group, key:
        SimpleNamespace(enabled=True, config_json={"mode": "SCHOOL_CENTRALIZED"})
        if group == "ACAD_RULE" and key == "PUBLIC_SCHEDULE_MODE" else original_cfg(db, tid, group, key))
    with get_sessionmaker()() as db:
        batch = db.query(AaTeachingTaskBatch).filter(
            AaTeachingTaskBatch.tenant_id == TID, AaTeachingTaskBatch.term_id == int(term_id),
        ).one()
        public_task = db.query(AaTeachingTask).filter(AaTeachingTask.batch_id == batch.id).one()
        public_course = db.get(AaCourse, public_task.course_id)
        public_course.category = "PUBLIC_BASIC"
        college_id = batch.college_id
        professional = AaCourse(tenant_id=TID, course_code="V5-PROFESSIONAL", course_name="专业课程",
                                category="MAJOR_CORE", owner_college_id=college_id, credit=2)
        db.add(professional); db.flush()
        public_plan = db.get(AaProgramCourse, public_task.source_program_course_id)
        db.get(AaProgram, public_plan.program_id).total_credits = 6
        professional_plan = AaProgramCourse(tenant_id=TID, program_id=public_plan.program_id,
            course_id=professional.id, course_name=professional.course_name, open_term_no=public_plan.open_term_no, credit_snapshot=2)
        db.add(professional_plan); db.flush()
        professional_task = AaTeachingTask(
            tenant_id=TID, batch_id=batch.id, course_id=professional.id, course_name="专业课程",
            class_id=class_id, teaching_class_name="发布测试班", teacher_key="T1", teacher_name="王老师",
            source_program_course_id=professional_plan.id, formation_mode="ADMIN_FIXED",
            status="READY", weekly_hours=1, start_week=1, end_week=18,
        )
        db.add(professional_task); db.flush()
        task_ids = [public_task.id, professional_task.id]
        db.commit()
    headers = _hdr(client, "school_admin01")
    schedule_ids = []
    for index, owner in enumerate((None, college_id)):
        created = client.post(f"{BASE}/schedule-batches", headers=headers, json={
            "termId": term_id, "collegeId": str(owner) if owner else None, "batchName": f"分级排课{index}",
        })
        assert created.status_code == 200, created.text
        batch_id = created.json()["data"]["batchId"]
        schedule_ids.append(int(batch_id))
        added = _item(client, headers, batch_id, taskId=str(task_ids[index]), classId=str(class_id),
                      courseName="高数" if index == 0 else "专业课程", weekday=index + 1)
        assert added.status_code == 200, added.text
        prepared = client.post(f"{BASE}/schedule-batches/{batch_id}/pre-publish", headers=headers)
        assert prepared.status_code == 200, prepared.text
        if index == 0:
            premature = client.post(f"{BASE}/schedule-batches/{batch_id}/publish", headers=headers)
            assert premature.status_code == 409, premature.text
            with get_sessionmaker()() as db:
                assert db.get(AaScheduleBatch, int(batch_id)).status == "PRE_PUBLISHED"
    # 公共课和专业课都完成预发布后，由真实校级发布人逐份正式发布。
    for batch_id in schedule_ids:
        published = client.post(f"{BASE}/schedule-batches/{batch_id}/publish", headers=headers)
        assert published.status_code == 200, published.text
    with get_sessionmaker()() as db:
        from app.core.context import set_tenant
        set_tenant(TID)
        assert set(truth.active_batch_ids(db, [int(term_id)])) == set(schedule_ids)
        assert all(db.get(AaScheduleBatch, value).status == "PUBLISHED" for value in schedule_ids)


def test_graduation_actual_college_then_school_command_boundary(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College, StudentProfile, Role, RolePermission
    from tests.support_grade_review_identity import seed_grade_review_identity, _ensure_permission
    from tests.test_aa_graduation_d_w0_contract import _seed_formal_result, _decision_rows, _result_status, BASE, TID
    from tests.test_aa_grade_review_flow import _hdr

    with get_sessionmaker()() as db:
        college = College(tenant_id=TID, college_name="毕业责任学院", status="ACTIVE")
        foreign = College(tenant_id=TID, college_name="另一毕业学院", status="ACTIVE")
        db.add_all([college, foreign]); db.flush()
        ids = (college.id, foreign.id)
        seed_grade_review_identity(db, college_ids=[college.id])
        for login, permission in (
            ("college_admin01", "academicAffairs.graduation.collegeReview"),
            ("school_admin01", "academicAffairs.graduation.final"),
        ):
            role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == f"TEST_GRADE_{login.upper()}").one()
            grant = _ensure_permission(db, permission)
            db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=grant.id, status="ACTIVE"))
        db.commit()
    student_id, result_id, run_id = _seed_formal_result(
        suffix="V5OWN", overall="SYSTEM_PASSED", review_note="", result_status="SYSTEM_PASSED", college_id=ids[0],
    )
    foreign_student, foreign_result, _ = _seed_formal_result(
        suffix="V5OTHER", overall="SYSTEM_PASSED", review_note="", result_status="SYSTEM_PASSED", college_id=ids[1],
    )
    school = _hdr(client, "school_admin01")
    college_headers = _hdr(client, "college_admin01")
    payload = {"action": "APPROVE", "note": "学院核对全部正式证据"}
    assert client.post(f"{BASE}/graduation-results/{result_id}/college-review", headers=school, json=payload).status_code == 403
    assert client.post(f"{BASE}/graduation-results/{foreign_result}/college-review", headers=college_headers, json=payload).status_code == 403
    assert _result_status(result_id) == _result_status(foreign_result) == "SYSTEM_PASSED"
    reviewed = client.post(f"{BASE}/graduation-results/{result_id}/college-review", headers=college_headers, json=payload)
    assert reviewed.status_code == 200, reviewed.text
    assert _result_status(result_id) == "ACADEMIC_REVIEW"
    final_payload = {"conclusion": "GRADUATED", "confirm": True}
    assert client.post(f"{BASE}/graduation-results/{result_id}/final", headers=college_headers, json=final_payload).status_code == 403
    completed = client.post(f"{BASE}/graduation-results/{result_id}/final", headers=school, json=final_payload)
    assert completed.status_code == 200, completed.text
    assert _result_status(result_id) == "GRADUATED"
    decisions = _decision_rows(result_id)
    assert len(decisions) == 1 and decisions[0].evaluation_run_id == run_id
