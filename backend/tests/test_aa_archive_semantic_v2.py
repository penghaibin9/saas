"""P0-10：十三域语义归档结构化合同。"""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


def _schedule_item(item_id, *, parity="ALL", teacher="T001", class_id=1, room=1,
                   start=1, end=16, batch=1, weekday=1, slot=1):
    return SimpleNamespace(
        id=item_id,
        batch_id=batch,
        weekday=weekday,
        slot_no=slot,
        start_week=start,
        end_week=end,
        week_parity=parity,
        teacher_key=teacher,
        class_id=class_id,
        classroom_id=room,
        classroom_text=None,
    )


def test_hard_conflict_detects_teacher_class_and_room_collision():
    from app.modules.academic_affairs.services.academic_affairs_archive_rule_evaluator import (
        hard_schedule_conflicts,
    )

    conflicts = hard_schedule_conflicts([
        _schedule_item(1),
        _schedule_item(2),
    ])

    assert len(conflicts) == 1
    assert set(conflicts[0]["kinds"]) == {"TEACHER", "CLASS", "CLASSROOM"}
    assert conflicts[0]["itemIds"] == ["1", "2"]


def test_odd_and_even_week_items_do_not_conflict():
    from app.modules.academic_affairs.services.academic_affairs_archive_rule_evaluator import (
        hard_schedule_conflicts,
    )

    conflicts = hard_schedule_conflicts([
        _schedule_item(1, parity="ODD"),
        _schedule_item(2, parity="EVEN"),
    ])

    assert conflicts == []


class _OpeningQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self.rows)


class _OpeningDb:
    def __init__(self, classes, courses):
        self.classes = classes
        self.courses = courses
        self.query_counts = {}

    def query(self, model):
        self.query_counts[model.__name__] = self.query_counts.get(model.__name__, 0) + 1
        if model.__name__ in {"SchoolClass", "StudentProfile"}:
            return _OpeningQuery(self.classes)
        if model.__name__ == "AaProgramCourse":
            return _OpeningQuery(self.courses)
        raise AssertionError(f"unexpected model: {model.__name__}")


def test_historical_opening_projection_uses_one_canonical_program_per_class(monkeypatch):
    from app.core.context import set_tenant
    from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as policy

    cutoff = datetime(2026, 7, 12, 23, 59)
    term = SimpleNamespace(year_code="2025-2026", term_no=2, end_date=cutoff)
    classes = [
        SimpleNamespace(id=1, major_id=10, grade="2024", college_id=2),
        SimpleNamespace(id=2, major_id=10, grade="2024", college_id=2),
    ]
    courses = [SimpleNamespace(id=91, course_id=501)]
    calls = []

    def resolve(_db, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            status="RESOLVED",
            program=SimpleNamespace(id=70),
            rule="MAJOR_GRADE_HISTORICAL_EFFECTIVE",
            message="历史方案已解析",
        )

    monkeypatch.setattr(policy, "resolve_program_for_scope", resolve)
    set_tenant({"tenantId": "1"})
    opening_db = _OpeningDb(classes, courses)
    try:
        expected, structural = policy._expected_opening(
            opening_db, term
        )
    finally:
        set_tenant(None)

    assert structural == []
    assert [row["key"] for row in expected] == [(501, 1), (501, 2)]
    assert [call["class_id"] for call in calls] == [1, 2]
    assert all(call["as_of"] == cutoff for call in calls)
    assert opening_db.query_counts["AaProgramCourse"] == 1


def test_historical_program_coverage_replays_binding_at_term_end(monkeypatch):
    from app.core.context import set_tenant
    from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as policy

    cutoff = datetime(2026, 7, 12, 23, 59)
    student = SimpleNamespace(
        id=1, student_no="2024S0001", major_id=10, class_id=1,
        grade="2024", college_id=2, student_status="REGISTERED",
    )
    classmate = SimpleNamespace(
        id=2, student_no="2024S0002", major_id=10, class_id=1,
        grade="2024", college_id=2, student_status="REGISTERED",
    )
    captured = []

    def resolve(_db, _student, **kwargs):
        captured.append(kwargs)
        return SimpleNamespace(
            status="RESOLVED", program=SimpleNamespace(id=70),
            rule="MAJOR_GRADE_HISTORICAL_EFFECTIVE", message="历史方案已解析",
        )

    monkeypatch.setattr(policy, "resolve_student_program", resolve)
    monkeypatch.setattr(policy, "validate_program_db", lambda _db, _pid: {"issues": []})
    set_tenant({"tenantId": "1"})
    try:
        result = policy.evaluate_program(
            _OpeningDb([student, classmate], []),
            SimpleNamespace(
                id=4, year_code="2025-2026", term_no=2, end_date=cutoff,
            ),
        )
    finally:
        set_tenant(None)

    assert result["result"] == "PASS"
    assert result["recordCount"] == 2
    assert captured == [{"tenant_id": 1, "as_of": cutoff}]


def test_persisted_rule_summary_fits_existing_varchar_300_and_round_trips():
    from app.modules.academic_affairs.services import academic_affairs_archive_service as service

    encoded = service._persisted_remark("GRADE", {
        "recordCount": 326,
        "present": False,
        "result": "BLOCKED",
        "ruleCode": "GRADE_TASK_UNPUBLISHED",
        "summary": "未发布成绩任务" * 100,
        "blockingCount": 8,
        "route": "/admin/academic-affairs/grade-tasks?filter=pending",
        "evidence": [{"taskId": str(i)} for i in range(100)],
    })
    parsed = service.parse_persisted_remark(
        "GRADE", encoded, present=False, record_count=326,
    )

    assert len(encoded) <= 300
    assert parsed["result"] == "BLOCKED"
    assert parsed["ruleCode"] == "GRADE_TASK_UNPUBLISHED"
    assert parsed["blockingCount"] == 8
    assert parsed["recordCount"] == 326
    assert parsed["evidence"] == []


def test_public_archive_service_is_single_explicit_entry():
    from app.modules.academic_affairs.services import academic_affairs_archive_service as service

    assert service.__name__.endswith("academic_affairs_archive_service")
    assert len(service._DOMAINS) == 13
    assert {code for code, _label in service._DOMAINS} == {
        "STUDENT_STATUS", "REGISTRATION", "STATUS_CHANGE", "PROGRAM",
        "TEACHING_TASK", "SCHEDULE", "SELECTION", "EXAM", "GRADE",
        "MAKEUP", "EVALUATION", "TEXTBOOK", "GRADUATION",
    }
    assert callable(service._evaluate_domains)
    assert callable(service.run_check)
    assert callable(service.precheck)


def test_archive_precheck_page_shows_semantic_status_and_drill_route():
    root = Path(__file__).resolve().parents[2]
    source = (
        root / "frontend/src/modules/academicAffairs/views/ArchivePrecheckView.vue"
    ).read_text(encoding="utf-8")

    for field in ("blockingCount", "blockedDomains", "ruleCode", "evidence", "domain.route"):
        assert field in source
    assert "当前仍有业务阻断，暂不可归档" in source
    assert "去处理" in source
    assert "“已阻断”表示存在明确业务阻断，“待治理”表示证据不足；两者都不能放行" in source


def test_global_force_button_is_not_reintroduced():
    root = Path(__file__).resolve().parents[2]
    core = (
        root / "backend/app/modules/academic_affairs/services/academic_affairs_archive_core_service.py"
    ).read_text(encoding="utf-8")

    assert "整体强制归档已停用" in core
    assert "仅语义完整性检查通过（READY）的批次可确认归档" in core


def test_mysql_program_checks_term_archived_graduates_without_widening_scope(db_mode):
    """已有毕业归档事实作为范围前置；方案解析和质量校验使用真实 MySQL。"""
    import json
    from app.core.context import get_tenant, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import (
        AaTerm, AaProgram, AaProgramBinding, AaProgramCourse, AaCourse, Major,
        AaProgramGraduationRequirement, StudentProfile, AaGraduationAuditBatch,
        AaGraduationAuditResult, GraduationEvaluationRun, GraduationDecisionFact,
    )
    from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as policy

    tenant = 1000000000000000001
    previous = get_tenant()
    set_tenant(tenant)
    try:
        with get_sessionmaker()() as db:
            # 仅隔离测试库：排除公共夹具中不属于本故事的默认学生。
            db.query(StudentProfile).filter_by(tenant_id=tenant).update({"is_deleted": True})
            term = AaTerm(tenant_id=tenant, year_code="2025-2026", term_no=2,
                          start_date=datetime(2026, 2, 1), end_date=datetime(2026, 7, 12), status="PUBLISHED")
            old = AaTerm(tenant_id=tenant, year_code="2024-2025", term_no=2, status="PUBLISHED")
            major = Major(tenant_id=tenant, college_id=1, major_name="归档方案测试专业", status="ACTIVE")
            db.add_all([term, old, major]); db.flush()
            program = AaProgram(tenant_id=tenant, program_name="本期毕业方案", major_id=major.id,
                                grade_year="2023", total_credits=1, status="ENABLED",
                                requirement_json=json.dumps({"creditStructure": [{"module": "专业核心", "creditTarget": 1}]}))
            course = AaCourse(tenant_id=tenant, course_code="ARCHIVEGRAD", course_name="毕业课程",
                              credit=1, hours_total=16, status="ENABLED")
            db.add_all([program, course]); db.flush()
            binding = AaProgramBinding(tenant_id=tenant, program_id=program.id, major_id=major.id,
                                       grade_year="2023", bound_at=datetime(2026, 2, 1), status="ACTIVE")
            db.add_all([
                binding,
                AaProgramCourse(tenant_id=tenant, program_id=program.id, course_id=course.id,
                                course_name=course.course_name, credit_snapshot=1, module="专业核心", open_term_no=6),
                AaProgramGraduationRequirement(tenant_id=tenant, program_id=program.id,
                                               category="ABILITY", content="达到毕业能力要求", status="ACTIVE"),
            ])
            def graduate(number, *, college=1, tid=tenant, source_term=None, decision=True, status="GRADUATED"):
                student = StudentProfile(tenant_id=tid, student_no=f"ARCHGR{number}", real_name="虚构归档学生",
                                         major_id=major.id, college_id=college, grade="2023",
                                         student_status=status, status="ACTIVE", created_at=datetime(2026, 2, 1))
                db.add(student); db.flush()
                batch = AaGraduationAuditBatch(tenant_id=tid, batch_name=f"归档来源{number}",
                                               term_id=(source_term or term).id, status="ARCHIVED")
                db.add(batch); db.flush()
                result = AaGraduationAuditResult(tenant_id=tid, batch_id=batch.id, student_id=student.id,
                                                 status="ARCHIVED", conclusion="GRADUATED", overall="SYSTEM_PASSED")
                db.add(result); db.flush()
                run = GraduationEvaluationRun(tenant_id=tid, batch_id=batch.id, result_id=result.id,
                                               student_id=student.id, run_no=1, program_id=program.id,
                                               input_snapshot_json="{}", input_hash="a" * 64,
                                               item_results_json="[]", overall="SYSTEM_PASSED")
                db.add(run); db.flush()
                if decision:
                    db.add(GraduationDecisionFact(tenant_id=tid, batch_id=batch.id, result_id=result.id,
                                                  student_id=student.id, evaluation_run_id=run.id,
                                                  conclusion="GRADUATED", decision_at=datetime.utcnow()))
                return student

            graduate(1)
            graduate(2, college=2)
            graduate(3, source_term=old)
            graduate(4, decision=False)
            graduate(5, tid=tenant + 1)
            graduate(6, status="WITHDRAWN")
            db.commit()
            result = policy.evaluate_program(db, term)
            assert result["result"] == "PASS", result
            assert result["recordCount"] == 2
            assert result["evidence"][0]["coveragePercent"] == 100
            assert result["evidence"][0]["archivedGraduates"] == 2
            assert policy.evaluate_program(db, term, college_ids={1})["recordCount"] == 1
            assert policy.evaluate_program(db, term, college_ids={2})["recordCount"] == 1
            assert policy.evaluate_program(db, term, college_ids={3})["ruleCode"] == "PROGRAM_NO_ENROLLED_STUDENT"
            assert policy.evaluate_program(db, None)["ruleCode"] == "PROGRAM_NO_ENROLLED_STUDENT"
            # 当前学期没有这些毕业事实，不能用历史毕业生凑覆盖率。
            future = AaTerm(tenant_id=tenant, year_code="2026-2027", term_no=1, status="PUBLISHED")
            db.add(future); db.flush()
            assert policy.evaluate_program(db, future)["ruleCode"] == "PROGRAM_NO_ENROLLED_STUDENT"
            binding.bound_at = datetime(2026, 8, 1)
            db.commit()
            missing = policy.evaluate_program(db, term)
            assert missing["result"] == "BLOCKED"
            assert missing["evidence"][0]["coveragePercent"] == 0
            binding.bound_at = datetime(2026, 2, 1)
            program.total_credits = 2
            db.commit()
            assert policy.evaluate_program(db, term)["result"] == "BLOCKED"
    finally:
        set_tenant(previous)
