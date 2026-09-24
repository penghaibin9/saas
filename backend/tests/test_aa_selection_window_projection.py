from datetime import datetime, timedelta
from types import SimpleNamespace

from app.modules.academic_affairs.services.academic_affairs_selection_core_service import _batch_dto


def test_expired_open_batch_reports_closed_window_without_rewriting_business_status():
    now = datetime.utcnow()
    batch = SimpleNamespace(id=7, term_id=2, batch_name="窗口测试", status="OPEN",
                            select_start_at=now-timedelta(days=2), select_end_at=now-timedelta(days=1),
                            apply_scope_json=None, rule_json=None, remark=None, locked_at=None)
    result = _batch_dto(batch)
    assert result["status"] == "OPEN"
    assert result["windowState"] == "ENDED"
    assert "不能继续选课" in result["windowNotice"]
    batch.status = "LOCKED"
    assert _batch_dto(batch)["windowNotice"] == ""
    batch.status = "OPEN"
    batch.select_start_at = now+timedelta(days=1)
    batch.select_end_at = now+timedelta(days=2)
    assert _batch_dto(batch)["windowState"] == "NOT_STARTED"
