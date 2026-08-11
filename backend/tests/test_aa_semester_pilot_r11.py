"""R11 真实学校完整学期试点门禁回归。"""
from pathlib import Path
from types import SimpleNamespace
import importlib


def test_r11_models_keep_term_uniqueness_and_checkpoint_history():
    from app.models.academic_affairs_r11 import AaSemesterPilot, AaSemesterPilotCheckpoint

    pilot_fields = set(AaSemesterPilot.__mapper__.attrs.keys())
    checkpoint_fields = set(AaSemesterPilotCheckpoint.__mapper__.attrs.keys())
    assert {
        "term_id", "term_code", "status", "real_data_confirmed", "check_run_no",
        "passed_stage_count", "blocker_count", "latest_evidence_hash",
        "latest_checked_at", "completed_at", "completed_by",
    } <= pilot_fields
    assert {
        "pilot_id", "run_no", "stage_code", "passed", "blocker_count",
        "warning_count", "evidence_json", "evidence_hash", "checked_at",
    } <= checkpoint_fields
    pilot_unique = {value.name for value in AaSemesterPilot.__table__.constraints if value.name}
    checkpoint_unique = {value.name for value in AaSemesterPilotCheckpoint.__table__.constraints if value.name}
    assert "uk_aa_semester_pilot_term" in pilot_unique
    assert "uk_aa_semester_pilot_checkpoint" in checkpoint_unique


def test_r11_migration_is_additive_and_never_seeds_completed_status():
    root = Path(__file__).resolve().parents[1]
    migration = (
        root / "alembic/versions/0131_aa_real_semester_pilot.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "0131_aa_real_semester_pilot"' in migration
    assert 'down_revision = "0130_aa_dynamic_grade_stats_snapshot"' in migration
    assert "t_aa_semester_pilot" in migration
    assert "t_aa_semester_pilot_checkpoint" in migration
    assert 'server_default="PREPARING"' in migration
    assert "insert(" not in migration
    assert "COMPLETED" not in migration


def test_stage_payload_hash_changes_when_evidence_changes():
    from app.modules.academic_affairs.services.academic_affairs_semester_pilot_service import _stage

    first = _stage(
        "BASELINE", "基础数据",
        evidence={"studentCount": 100}, blockers=[], warnings=[],
    )
    second = _stage(
        "BASELINE", "基础数据",
        evidence={"studentCount": 101}, blockers=[], warnings=[],
    )
    blocked = _stage(
        "BASELINE", "基础数据",
        evidence={"studentCount": 100}, blockers=["没有真实学生"], warnings=[],
    )
    assert first["passed"] is True
    assert blocked["passed"] is False
    assert first["evidenceHash"] != second["evidenceHash"]
    assert first["evidenceHash"] != blocked["evidenceHash"]


def test_r11_has_exact_six_ordered_real_stages():
    from app.modules.academic_affairs.services.academic_affairs_semester_pilot_service import _STAGE_ORDER

    assert [code for code, _name in _STAGE_ORDER] == [
        "BASELINE", "PRE_TERM", "IN_TERM", "EXAM", "GRADE", "ARCHIVE",
    ]


def test_completion_source_blocks_nonproduction_mock_and_partial_evidence():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_semester_pilot_service.py"
    ).read_text(encoding="utf-8")

    assert "eligibleForRealCompletion" in source
    assert "MOCK_LOGIN_ENABLED" in source
    assert "CONFIRM_REAL_SEMESTER_COMPLETED" in source
    assert 'pilot.status != "READY_TO_COMPLETE"' in source
    assert "passed_stage_count" in source
    assert "latest_evidence_hash" in source
    assert "最新检查证据不完整或已有变化" in source
    assert "试点总证据哈希校验失败" in source
    assert "本服务不生成学生、课程、任务、考勤、考试或成绩数据" in source


def test_r11_checks_real_cross_domain_facts_not_test_results():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_semester_pilot_service.py"
    ).read_text(encoding="utf-8")

    for fact in (
        "StudentProfile", "AaProgramBinding", "AaTeachingTask", "AaTeachingClass",
        "AaScheduleBatch", "AaAttendanceSession", "AaExamBatch", "AaExamCourse",
        "AaGradeTask", "AcademicGrade", "AaArchiveBatch", "AaStatsSnapshot",
        "AaRosterConsumerSnapshot",
    ):
        assert fact in source
    assert "pytest" not in source
    assert "mockRequest" not in source
    assert "seed" not in source.lower()


def test_r11_routes_are_registered_and_require_explicit_complete_action():
    # 主应用注册的是 bundle 的最终聚合结果；基础 academic_affairs.router 只是历史大 Router，
    # 扩展 Router（含 R11）在 bundle.build_router() 中按确定性顺序装配。
    from app.modules.academic_affairs.routers import academic_affairs_bundle

    signatures = {
        (route.path, tuple(sorted(route.methods or set())))
        for route in academic_affairs_bundle.build_router().routes
    }
    for signature in (
        ("/academic-affairs/semester-pilots", ("POST",)),
        ("/academic-affairs/semester-pilots", ("GET",)),
        ("/academic-affairs/semester-pilots/{pilot_id}", ("GET",)),
        ("/academic-affairs/semester-pilots/{pilot_id}/check", ("POST",)),
        ("/academic-affairs/semester-pilots/{pilot_id}/complete", ("POST",)),
        ("/academic-affairs/semester-pilots/{pilot_id}/cancel", ("POST",)),
    ):
        assert signature in signatures


def test_public_services_load_r11_without_replacing_existing_domain_services():
    from app.modules.academic_affairs import services

    archive_before = services.academic_affairs_archive_service
    mobile_before = services.mobile_academic_affairs_service
    pilot = importlib.import_module(
        "app.modules.academic_affairs.services.academic_affairs_semester_pilot_service"
    )

    assert pilot.__name__.endswith("academic_affairs_semester_pilot_service")
    # 加载 R11 只能增加自己的服务能力，不能通过 import side effect 抢占既有公开入口。
    assert services.academic_affairs_archive_service is archive_before
    assert services.mobile_academic_affairs_service is mobile_before
    assert services.academic_affairs_archive_service.__name__.endswith("academic_affairs_archive_service")
    assert services.mobile_academic_affairs_service.__name__.endswith("mobile_academic_affairs_public_service")
