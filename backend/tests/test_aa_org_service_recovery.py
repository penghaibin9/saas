"""Regression guard for the organization services restored from the integration gap."""
from types import SimpleNamespace


def test_organization_service_dependencies_are_importable():
    from app.services import org_class_lifecycle_service, org_reference_check_service

    assert callable(org_class_lifecycle_service.read_class_references)
    assert callable(org_reference_check_service.check_org_references)


def test_class_lifecycle_counts_only_live_students_and_open_tasks():
    from app.services.org_class_lifecycle_service import (
        EXITED_STUDENT_STATUSES,
        closing_blockers,
        task_blocks_closure,
    )

    assert "GRADUATED" in EXITED_STUDENT_STATUSES
    assert task_blocks_closure(
        SimpleNamespace(status="READY"),
        SimpleNamespace(is_deleted=False),
        SimpleNamespace(is_deleted=False, status="PUBLISHED"),
    )
    assert not task_blocks_closure(
        SimpleNamespace(status="READY"),
        SimpleNamespace(is_deleted=False),
        SimpleNamespace(is_deleted=False, status="ARCHIVED"),
    )
    assert closing_blockers(2, 1) == [
        "仍有 2 名在籍学生，请先处理转班或离校学籍手续",
        "仍有 1 条未归档教学任务，请先处理教学任务或完成所属学期的教务归档",
    ]
