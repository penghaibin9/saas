"""V2 普通任课教师流程收口静态/合同回归锁。"""
from pathlib import Path
import inspect

from app.modules.academic_affairs.services import academic_affairs_schedule_service as schedule_svc
from app.modules.academic_affairs.services import academic_affairs_org_service as org_svc
from app.modules.academic_affairs.services import academic_affairs_textbook_service as textbook_svc
from app.modules.academic_affairs.services import academic_affairs_program_governance_service as program_governance
from app.modules.academic_affairs.services import academic_affairs_teacher_relation_authority as teacher_authority

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_teacher_relation_scope_is_formal_relation_first_with_legacy_only_when_unprojected():
    source = inspect.getsource(teacher_authority.relation_scope)
    assert "AaTeachingClassTeacher" in source
    assert 'teacher_key.in_(sorted(keys))' in source
    assert 'status == "ACTIVE"' in source
    assert "~exists().where" in source
    assert "AaTeachingClass.teaching_task_id == AaTeachingTask.id" in source


def test_teacher_schedule_and_schedule_query_use_formal_teacher_authority():
    class_source = inspect.getsource(schedule_svc.class_schedule)
    teaching_class_source = inspect.getsource(schedule_svc.teaching_class_schedule)
    teacher_source = inspect.getsource(schedule_svc.teacher_schedule)

    assert 'role == "ACADEMIC_TEACHER"' in class_source
    assert "teacher_authority.relation_scope" in class_source
    assert "正式任课关系涉及的班级课表" in class_source
    assert 'role == "ACADEMIC_TEACHER"' in teaching_class_source
    assert "本人正式任课关系中的教学班课表" in teaching_class_source

    # Public teacher_schedule is intentionally replaced by the repository's
    # canonical week-clipped TeachingClassTeacher guard during service init.
    assert getattr(schedule_svc.teacher_schedule, "_schedule_teacher_relation_guard", False) is True
    assert "TEACHING_CLASS_TEACHER_BY_WEEK" in teacher_source
    assert "_teacher_items" in teacher_source


def test_teacher_class_and_teaching_class_pickers_are_relation_scoped():
    classes = inspect.getsource(org_svc.list_classes)
    teaching_classes = inspect.getsource(org_svc.list_teaching_classes)
    assert 'role == "ACADEMIC_TEACHER"' in classes
    assert 'relation_scope(db, user, term_id=term_id)["classIds"]' in classes
    assert 'role == "ACADEMIC_TEACHER"' in teaching_classes
    assert '["taskIds"]' in teaching_classes
    router = _read("app/modules/academic_affairs/routers/academic_affairs.py")
    assert 'termId: Optional[int] = Query(None, ge=1)' in router
    assert 'term_id=termId' in router
    assert '_ORG_PICKER_VIEW = require_any_permission("academicAffairs.org.view", "academicAffairs.schedule.view")' in router

    # Picker access must not widen the role to the whole organization directory.
    from app.core.permissions import ROLE_PERMISSIONS
    assert "academicAffairs.org.view" not in ROLE_PERMISSIONS["ACADEMIC_TEACHER"]


def test_teacher_resource_booking_ledger_is_self_only():
    resource = _read("app/modules/academic_affairs/services/academic_affairs_resource_service.py")
    assert "def _teacher_booking_keys" in resource
    for name in ("list_bookings", "list_lab_bookings"):
        start = resource.index(f"def {name}")
        end = resource.find("\ndef ", start + 5)
        block = resource[start:end if end > start else len(resource)]
        assert "_teacher_booking_keys(user)" in block
        assert "applicant_key.in_" in block


def test_teacher_task_pickers_explicitly_request_mine_only():
    grade = _read("../frontend/src/modules/academicAffairs/views/AaGradeEntryView.vue")
    textbook = _read("../frontend/src/modules/academicAffairs/views/AaTextbookConsoleView.vue")
    assert 'formalMine: !isAdminRole' in grade
    assert 'formalMine: isAcademicTeacher' in textbook
    assert textbook_svc.__name__.endswith("academic_affairs_textbook_final_facade")


def test_teacher_reference_pages_only_expose_formal_programs_and_enabled_courses():
    program_core = _read("app/modules/academic_affairs/services/academic_affairs_program_core_service.py")
    program_summary = _read("app/modules/academic_affairs/services/academic_affairs_program_governance_summary_service.py")
    course = _read("app/modules/academic_affairs/services/academic_affairs_course_service.py")
    assert '_TEACHER_VISIBLE_PROGRAM_STATUSES = {"PUBLISHED", "ENABLED", "FROZEN"}' in program_core
    assert 'teacher_read = role == "ACADEMIC_TEACHER"' in program_summary
    assert "governance._ACTIVE_PROGRAM_STATUSES" in program_summary
    assert 'AaCourse.status == "ENABLED"' in course
    assert "ACADEMIC_TEACHER" in inspect.getsource(program_governance.validate_program)


def test_schedule_change_stop_and_makeup_are_single_occurrence_contracts():
    r3 = _read("app/modules/academic_affairs/services/academic_affairs_schedule_change_r3_service.py")
    legacy = _read("app/modules/academic_affairs/services/academic_affairs_schedule_change_service.py")
    router = _read("app/modules/academic_affairs/routers/academic_affairs.py")
    assert '停课必须明确选择具体教学周' in r3
    assert '补课必须明确选择具体教学周' in r3
    assert '调课必须明确选择具体教学周或周期范围' in r3
    assert '补课一次只能选择一个具体教学周' in r3
    assert '停课一次只能选择一个具体教学周' in r3
    assert 'tsw = tew = int(raw_week)' in r3
    assert 'exclude_id=(origin.id if ct == "ADJUST" else None)' in r3
    assert '冲突预检必须明确目标教学周范围' in legacy
    assert 'exclude_id=(origin.id if ct == "ADJUST" else None)' in legacy
    assert '补课冲突预检一次只能选择一个具体教学周' in legacy
    assert 'changeType: Literal["ADJUST", "MAKEUP"]' in router
    assert 'change.change_type not in {"ADJUST", "STOP"}' in legacy


def test_teacher_today_uses_one_current_term_authoritative_workbench():
    work = _read("app/modules/academic_affairs/services/academic_affairs_teacher_today_work_service.py")
    mobile = _read("app/modules/academic_affairs/services/mobile_academic_affairs_public_service.py")
    assert "def current_term_workbench" in work
    assert '"source": "CURRENT_TERM_FORMAL_TEACHER_FACTS"' in work
    assert 'term_id=result.get("termId")' in mobile
    assert 'term_end_date=str(result.get("termEndDate") or "")' in mobile


def test_pc_attendance_reuses_canonical_attendance_owner():
    router = _read("app/modules/academic_affairs/routers/academic_affairs.py")
    assert '@router.post("/attendance/sessions/open"' in router
    assert "attendance_svc.create_session(user, payload)" in router
    assert "attendance_svc.mark_attendance(sessionId, user, body.model_dump())" in router
    assert "attendance_svc.submit_session(sessionId, user)" in router


def test_textbook_selection_deep_link_has_exact_server_filter():
    router = _read("app/modules/academic_affairs/routers/textbook_core_router.py")
    service = _read("app/modules/academic_affairs/services/academic_affairs_textbook_service.py")
    assert "selectionId: Optional[int] = None" in router
    assert "selection_id=selectionId" in router
    assert "selection_id=None" in service
    assert "AaTextbookSelection.id == int(selection_id)" in service


def test_teacher_today_confirmation_queue_uses_assignment_owner_not_occurrence_week():
    work = _read("app/modules/academic_affairs/services/academic_affairs_teacher_today_work_service.py")
    start = work.index("# Teaching-task confirmation")
    end = work.index("# Grade responsibility", start)
    block = work[start:end]
    assert 'AaTeachingTask.teacher_key.in_(keys or ["__none__"])' in block
    assert 'AaTeachingTask.status.in_(["ASSIGNED", "TEACHER_CONFIRMED", "READY"])' in block
    assert "formal_task_ids" not in block


def test_teacher_v3_today_projects_action_and_waiting_from_current_term_facts():
    source = _read("app/modules/academic_affairs/services/academic_affairs_teacher_today_work_service.py")
    assert '"TEACHING_TASK_WAITING"' in source
    assert '"GRADE_SETUP"' in source
    assert '"TEXTBOOK_SETUP"' not in source
    assert 'status in {"SUBMITTED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW"}' in source
    assert '"CURRENT_TERM_FORMAL_TEACHER_FACTS"' in source
    assert '/grade-entry?teachingTaskId=' in source
    assert '/textbooks?tab=selection&action=create&taskId=' not in source


def test_teacher_v3_grade_and_textbook_lists_accept_current_term_filter():
    grade = _read("app/modules/academic_affairs/services/academic_affairs_grade_task_read_service.py")
    grade_router = _read("app/modules/academic_affairs/routers/grade_core_router.py")
    textbook = _read("app/modules/academic_affairs/services/academic_affairs_textbook_service.py")
    textbook_router = _read("app/modules/academic_affairs/routers/textbook_core_router.py")
    assert "term_id=None" in grade
    assert "AaGradeTask.term_id == int(term_id)" in grade
    assert "termId: Optional[int] = None" in grade_router
    assert "term_id=termId" in grade_router
    assert "term_id=None" in textbook
    assert "AaTeachingTaskBatch.term_id == int(term_id)" in textbook
    assert "termId: Optional[int] = None" in textbook_router
    assert "term_id=termId" in textbook_router


def test_teacher_v3_exact_setup_links_revalidate_teacher_task():
    router = _read("app/modules/academic_affairs/routers/course_program_task_router.py")
    assert "taskId: Optional[int] = None" in router
    assert "task_id=taskId" in router


def test_teacher_v3_textbook_term_filter_imports_its_join_models():
    source = _read("app/modules/academic_affairs/services/academic_affairs_textbook_service.py")
    assert "AaTeachingTask, AaTeachingTaskBatch, AaTextbookSelection" in source


def test_teacher_v3_non_occurrence_scope_uses_clamped_formal_teacher_authority():
    authority = _read("app/modules/academic_affairs/services/academic_affairs_teacher_relation_authority.py")
    work = _read("app/modules/academic_affairs/services/academic_affairs_teacher_today_work_service.py")
    grade = _read("app/modules/academic_affairs/services/academic_affairs_grade_task_read_service.py")
    task_service = _read("app/modules/academic_affairs/services/academic_affairs_task_service.py")
    assert "active_week_only" not in authority
    assert "class_authority_weeks" in authority
    assert "relation_covers_week(relation, authority_weeks.get" in authority
    assert "relation_scope(db, user, term_id=int(term_id))" in work
    assert "class_authority_weeks" in grade
    assert '"authorityWeek": week' in grade
    assert "formal_mine=False" in task_service
    assert 'mine 与 formalMine 不可同时使用' in task_service


def test_teacher_v3_grade_today_surfaces_deadline_blockers_instead_of_hiding_them():
    source = _read("app/modules/academic_affairs/services/academic_affairs_teacher_today_work_service.py")
    assert "deadline_projection_map" in source
    assert 'overdue = deadline.get("isOverdue") is True' in source
    assert "已超过提交截止时间；可继续完善，提交需学院或教务延长截止时间" in source
    assert '"blocked": bool(overdue)' in source
    assert '"action": action' in source


def test_teacher_v3_rejected_teaching_task_stays_visible_until_college_reassigns():
    source = _read("app/modules/academic_affairs/services/academic_affairs_teacher_today_work_service.py")
    assert '"REJECTED_BY_TEACHER"' in source
    assert '"TEACHING_TASK_REJECTED_WAITING"' in source
    assert "等待学院调整并重新分配" in source


def test_teacher_v3_duplicate_grade_task_conflict_exposes_recoverable_existing_id():
    source = _read("app/modules/academic_affairs/services/academic_affairs_grade_core_service.py")
    assert '"existingGradeTaskId": str(exist.id)' in source
    assert '"existingStatus": str(exist.status or "")' in source
