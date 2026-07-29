"""学生评教批次从生成任务到开放提交必须始终启用匿名模式。"""
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_non_anonymous_student_batch_is_rejected():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    with pytest.raises(AppException) as exc:
        service._require_anonymous_student_batch(SimpleNamespace(anonymous=False))

    assert exc.value.http_status == 409
    assert "必须启用匿名模式" in exc.value.message


def test_anonymous_batch_and_role_only_batch_are_allowed():
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    service._require_anonymous_student_batch(SimpleNamespace(anonymous=True))
    service._require_anonymous_student_batch(
        SimpleNamespace(anonymous=False),
        has_student_tasks=False,
    )


def test_public_service_guards_generation_publish_open_and_submit():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_evaluation_public_service.py"
    ).read_text(encoding="utf-8")

    for function in ("generate_tasks", "publish_batch", "open_batch", "submit_evaluation"):
        assert f"def {function}(" in source
    assert source.count("_require_anonymous_student_batch(") >= 5
    assert "_batch_has_student_tasks" in source
    assert "AaEvaluationBatch.anonymous.is_(True)" in source
