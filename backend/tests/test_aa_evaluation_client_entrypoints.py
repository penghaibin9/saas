"""学生 PC / 小程序评教入口必须统一走稳定身份、正式教学班和匿名幂等实现。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_student_portal_service_uses_evaluation_safety_facade():
    from app.student_portal import services

    assert services.academic_service.__name__.endswith(
        "academic_evaluation_safety_facade"
    )
    assert services.academic_service.evaluation_tasks.__module__.endswith(
        "academic_evaluation_safety_facade"
    )
    assert services.academic_service.evaluation_submit.__module__.endswith(
        "academic_evaluation_safety_facade"
    )


def test_mobile_service_uses_secured_public_facade():
    from app.modules.academic_affairs import services

    mobile = services.mobile_academic_affairs_service
    assert mobile.__name__.endswith("mobile_academic_affairs_public_service")
    assert mobile.evaluation_tasks_my.__module__.endswith(
        "mobile_academic_affairs_public_service"
    )
    assert mobile.evaluation_submit_my.__module__.endswith(
        "mobile_academic_affairs_public_service"
    )


def test_both_clients_read_real_roster_worklist_and_secure_submit():
    portal = _read("app/student_portal/services/academic_evaluation_safety_facade.py")
    mobile = _read(
        "app/modules/academic_affairs/services/mobile_academic_affairs_public_service.py"
    )
    public = _read(
        "app/modules/academic_affairs/services/academic_affairs_evaluation_public_service.py"
    )

    for source in (portal, mobile):
        assert "evaluation.my_student_tasks" in source
        assert "evaluation.submit_evaluation" in source
        assert "0 <= score_value <= 100" in source
    assert "AaTeachingClassMember.student_id == int(profile.id)" in public
    assert "AaTeachingClass.roster_status == \"LOCKED\"" in public
    assert '"submitted": submitted' in public
    assert '"canSubmit": batch.status == _legacy._B_OPEN and not submitted' in public


def test_student_evaluation_router_is_explicitly_registered():
    router = _read(
        "app/modules/academic_affairs/routers/student_evaluation_router.py"
    )
    registration = _read("app/api/v1/route_registration.py")

    assert 'prefix="/academic-affairs/evaluation"' in router
    assert '@router.get("/my-student-tasks"' in router
    assert "student_evaluation_router" in registration
    assert "api_router.include_router(module.router" in registration


def test_existing_pc_and_miniapp_contracts_stay_compatible():
    portal_router = _read("app/student_portal/router.py")
    mobile_router = _read("app/api/v1/mobile.py")
    portal_api = (
        ROOT.parent / "student-portal/src/services/portalApi.js"
    ).read_text(encoding="utf-8")
    mini_api = (
        ROOT.parent / "miniapp/src/services/realApi.js"
    ).read_text(encoding="utf-8")

    assert '@router.get("/evaluation/tasks"' in portal_router
    assert '@router.post("/evaluation/submit"' in portal_router
    assert 'academicEvaluationTasks: () => request(\'/portal/academic/evaluation/tasks\')' in portal_api
    assert "academicEvaluationSubmit" in portal_api
    assert 'realRequest(\'/mobile/academic/evaluation/tasks\')' in mini_api
    assert 'realRequest(\'/mobile/academic/evaluation/submit\'' in mini_api
    assert 'aa.evaluation_tasks_my(user)' in mobile_router
    assert 'aa.evaluation_submit_my(user, body)' in mobile_router
