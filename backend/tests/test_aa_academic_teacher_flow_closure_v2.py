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
    assert ':query="{ mine: !isAdminRole }"' in grade
    assert 'mine: isAcademicTeacher' in textbook
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
    assert '停课必须明确选择具体教学周' in r3
    assert '补课必须明确选择具体教学周' in r3
    assert 'tsw = tew = int(raw_week)' in r3
    assert 'exclude_id=(origin.id if ct == "ADJUST" else None)' in r3
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
