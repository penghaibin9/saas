"""请假逾期与资助发放批处理静态回归合同。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_leave_overdue_scan_is_serialized_and_idempotent():
    text = read("backend/app/services/affairs_batch_job_guard.py")
    assert "CsLeave.overdue_pushed_at.is_(None)" in text
    assert "with_for_update(skip_locked=True)" in text
    assert 'todo_type="LEAVE_OVERDUE"' in text
    assert 'event_code="LEAVE.OVERDUE"' in text


def test_disbursement_generation_is_tenant_all_and_batch_locked():
    text = read("backend/app/services/affairs_batch_job_guard.py")
    assert "该批量操作仅限学校/学工处全域管理员" in text
    assert "FundingBatch.id == int(batch_id)" in text
    assert "with_for_update()" in text
    assert "发放台账已由其他请求生成" in text


def test_disbursement_actions_have_versions_inputs_and_side_effects():
    text = read("backend/app/services/affairs_batch_job_guard.py")
    assert '"PENDING": ["ISSUE", "FAIL"]' in text
    assert "银行卡后4位必须为4位数字" in text
    assert "FUNDING_DISBURSED" in text
    assert "资助发放异常" in text
    assert "funding.atomic_claim_version" in text


def test_disbursement_statistics_follow_student_scope():
    text = read("backend/app/services/affairs_batch_job_guard.py")
    assert "_allowed_class_ids" in text
    assert "StudentProfile.class_id.in_(allowed or {-1})" in text
    assert "StudentProfile.tenant_id == _tid()" in text


def test_router_installs_batch_guard_before_stats_and_archive_is_direct_service():
    source = read("backend/app/api/v1/router.py")
    archive = read("backend/app/services/affairs_archive_service.py")
    batch = source.index("install_batch_job_guard()")
    stats = source.index("install_stats_integrity_guard()")
    assert batch < stats
    assert "install_archive_guard()" not in source
    assert "不再由 guard monkey-patch" in archive
    assert "def collect(" in archive and "def advance(" in archive
