from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
QUERY_SOURCE = (BACKEND / "app/services/approval_mobile_query_service.py").read_text(encoding="utf-8")
ROUTER_SOURCE = (BACKEND / "app/api/v1/approval_mobile.py").read_text(encoding="utf-8")
REG_SOURCE = (BACKEND / "app/api/v1/route_registration.py").read_text(encoding="utf-8")


def test_stage_b_mobile_approval_queue_is_real_db_only():
    assert "APPROVAL_BACKEND_UNAVAILABLE" in QUERY_SOURCE
    assert 'normalized not in {"pending", "done", "mine"}' in QUERY_SOURCE
    assert "WorkflowTask" in QUERY_SOURCE
    assert "WorkflowInstance" in QUERY_SOURCE
    assert "StudentAccountLink" in QUERY_SOURCE
    assert "StudentProfile.real_name.like(like)" in QUERY_SOURCE
    assert "StudentProfile.student_no.like(like)" in QUERY_SOURCE
    assert "WorkflowInstance.source_biz_id == int(kw)" in QUERY_SOURCE
    assert "mock" not in QUERY_SOURCE.lower()


def test_stage_b_queue_filters_and_counts_before_pagination():
    count_pos = QUERY_SOURCE.index("total = int(db.scalar")
    offset_pos = QUERY_SOURCE.index(".offset((page - 1) * page_size)", count_pos)
    assert count_pos < offset_pos
    assert "WorkflowInstance.applicant_id == actor" in QUERY_SOURCE
    assert "WorkflowTask.assignee_id == actor" in QUERY_SOURCE
    assert 'statuses = ["PENDING"] if normalized == "pending"' in QUERY_SOURCE
    assert "即使拥有 approval.manage 也不扩大为全租户列表" in QUERY_SOURCE


def test_stage_b_mobile_queue_endpoint_is_registered():
    assert 'APIRouter(prefix="/approvals/mobile"' in ROUTER_SOURCE
    assert '@router.get("/queue"' in ROUTER_SOURCE
    assert 'pattern="^(pending|done|mine)$"' in ROUTER_SOURCE
    assert "api_router.include_router(approval_mobile.router)" in REG_SOURCE
