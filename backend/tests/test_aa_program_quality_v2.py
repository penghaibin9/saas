"""V2-01 培养方案质量与开课差异回归。"""
from types import SimpleNamespace


def test_plan_term_number_uses_grade_and_academic_year():
    from app.modules.academic_affairs.services.academic_affairs_program_quality_service import _plan_term_no

    assert _plan_term_no("2026-2027", 1, "2026") == 1
    assert _plan_term_no("2026-2027", 2, "2026") == 2
    assert _plan_term_no("2027-2028", 1, "2026") == 3
    assert _plan_term_no("2027-2028", 2, "2026") == 4
    assert _plan_term_no("bad", 1, "2026") is None
    assert _plan_term_no("2026-2027", 1, None) is None


def test_issue_contract_is_stable_for_frontend_and_submit_gate():
    from app.modules.academic_affairs.services.academic_affairs_program_quality_service import _issue

    issue = _issue(
        "COURSE_ID_REQUIRED",
        "BLOCKER",
        "课程未关联课程库",
        object_id=8,
        field_path="courseId",
        suggestion="重新选择课程",
        fix_route="/admin/academic-affairs/programs/1",
    )
    assert issue == {
        "ruleCode": "COURSE_ID_REQUIRED",
        "level": "BLOCKER",
        "objectId": "8",
        "fieldPath": "courseId",
        "message": "课程未关联课程库",
        "suggestion": "重新选择课程",
        "fixRoute": "/admin/academic-affairs/programs/1",
    }


class _Query:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)


class _QualityDb:
    def __init__(self, program, practices):
        self.program = program
        self.practices = practices

    def query(self, model):
        if model.__name__ == "AaProgram":
            return _Query([self.program])
        if model.__name__ == "AaProgramPracticeSegment":
            return _Query(self.practices)
        return _Query([])


def test_final_validator_counts_practice_credit_in_total(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_program_quality_final_service as service

    base_result = {
        "programId": "1",
        "programName": "软件技术2026级",
        "status": "DRAFT",
        "creditSum": 98.0,
        "totalCredits": 100.0,
        "courseCount": 20,
        "practiceCount": 1,
        "activeBindingCount": 0,
        "counts": {"blocker": 1, "warning": 0, "info": 0},
        "canSubmit": False,
        "conclusion": "存在 1 个阻断项",
        "issues": [{
            "ruleCode": "TOTAL_CREDIT_INSUFFICIENT",
            "level": "BLOCKER",
            "objectId": "1",
            "fieldPath": "totalCredits",
            "message": "旧课程学分口径不足",
            "suggestion": "",
            "fixRoute": "",
        }],
    }
    monkeypatch.setattr(service._base, "validate_program_db", lambda _db, _pid: dict(base_result, issues=list(base_result["issues"])))
    monkeypatch.setattr(service, "_tid", lambda: 1)
    program = SimpleNamespace(id=1, tenant_id=1, is_deleted=False, total_credits=100)
    practice = SimpleNamespace(
        id=9, tenant_id=1, program_id=1, status="ACTIVE", is_deleted=False,
        segment_name="顶岗实习", credit=2,
    )

    result = service.validate_program_db(_QualityDb(program, [practice]), 1)

    assert result["courseCreditSum"] == 98.0
    assert result["practiceCreditSum"] == 2.0
    assert result["creditSum"] == 100.0
    assert not any(item["ruleCode"] == "TOTAL_CREDIT_INSUFFICIENT" for item in result["issues"])


def test_public_program_services_use_final_quality_layers():
    from app.modules.academic_affairs import services

    assert services.academic_affairs_program_service.__name__.endswith(
        "academic_affairs_program_quality_facade"
    )
    assert services.academic_affairs_program_service.submit_program.__module__.endswith(
        "academic_affairs_program_quality_facade"
    )
    assert services.academic_affairs_program_quality_service.__name__.endswith(
        "academic_affairs_program_quality_security_service"
    )
    assert services.academic_affairs_program_quality_service._base.__name__.endswith(
        "academic_affairs_program_quality_final_service"
    )


def test_program_quality_router_exposes_three_read_endpoints():
    from app.modules.academic_affairs.routers.program_quality_router import router

    paths = {route.path for route in router.routes}
    assert "/academic-affairs/programs/{program_id}/validation" in paths
    assert "/academic-affairs/program-governance/summary" in paths
    assert "/academic-affairs/opening-plan/differences" in paths
