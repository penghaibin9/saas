from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AppException
from app.modules.internship.services import internship_formal_document_service as svc


def _snapshot(document_type="INTERNSHIP_CERTIFICATE"):
    return {
        "schemaVersion": 1,
        "documentType": document_type,
        "school": {"tenantId": "1", "schoolName": "益阳职业技术学院"},
        "student": {
            "id": "7", "studentNo": "20260001", "realName": "测试学生",
            "grade": "2024", "collegeName": "机电工程学院",
            "majorName": "机电一体化技术", "className": "机电2401",
        },
        "internship": {
            "id": "11", "batchId": "2", "status": "ASSESSING",
            "enterpriseName": "测试企业", "positionName": "设备运维",
            "advisorName": "指导教师", "enterpriseMentorName": "企业导师",
            "startDate": "2026-03-01T00:00:00", "endDate": "2026-08-31T00:00:00",
        },
        "completion": {
            "status": "ASSESSING", "enterpriseName": "测试企业",
            "positionName": "设备运维",
            "startDate": "2026-03-01T00:00:00", "endDate": "2026-08-31T00:00:00",
        },
    }


def test_g17_supports_four_formal_document_types():
    assert set(svc.SUPPORTED_DOCUMENTS) == {
        "ENTERPRISE_EVALUATION",
        "INTERNSHIP_CERTIFICATE",
        "FINAL_ASSESSMENT",
        "SUMMARY_REPORT",
    }


def test_g17_source_hash_is_stable_and_fact_sensitive():
    first = _snapshot()
    second = _snapshot()
    assert svc.source_hash(first) == svc.source_hash(second)
    second["internship"]["positionName"] = "智能制造"
    assert svc.source_hash(first) != svc.source_hash(second)


def test_g17_certificate_pdf_is_real_pdf():
    data = svc.render_formal_pdf(
        "INTERNSHIP_CERTIFICATE", _snapshot(), document_version=2,
    )
    assert data.startswith(b"%PDF")
    assert len(data) > 1000


def test_g17_invalid_document_type_is_rejected():
    with pytest.raises(AppException):
        svc.normalize_document_type("UNKNOWN")


def test_g17_certificate_requires_completed_formal_facts():
    record = type("Record", (), {
        "status": "ONBOARD",
        "enterprise_name": "测试企业",
        "position_name": "设备运维",
        "intern_start_date": datetime.utcnow() - timedelta(days=10),
        "intern_end_date": datetime.utcnow() + timedelta(days=10),
    })()
    with pytest.raises(AppException):
        svc._certificate_fact(None, record)

    record.status = "ASSESSING"
    with pytest.raises(AppException):
        svc._certificate_fact(record)


def test_g17_staff_routes_are_exposed():
    from app.modules.internship.routers.internship_formal_document import router
    paths = {route.path for route in router.routes}
    assert "/internship/formal-documents/by-internship/{internship_id}" in paths
    assert "/internship/formal-documents/generate" in paths
    assert "/internship/formal-documents/{document_id}/download" in paths
