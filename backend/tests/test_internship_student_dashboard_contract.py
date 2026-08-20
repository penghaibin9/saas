"""学生岗位实习工作台字段真值回归。"""
from __future__ import annotations

import inspect


def test_student_dashboard_reads_canonical_enterprise_mentor_field():
    from app.models import InternshipRecord
    from app.modules.internship.services import internship_student_dashboard_service as service

    assert hasattr(InternshipRecord, "enterprise_mentor_name")
    assert not hasattr(InternshipRecord, "mentor_name")

    source = inspect.getsource(service.get_my_dashboard)
    assert "record.enterprise_mentor_name" in source
    assert "record.mentor_name" not in source
