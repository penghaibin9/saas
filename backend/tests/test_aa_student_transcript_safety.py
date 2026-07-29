"""P0-02：学生PC成绩出件只能是个人查询件，禁止冒充正式成绩单。"""
from types import SimpleNamespace

import pytest


def test_query_copy_rejects_missing_purpose(monkeypatch):
    from app.core.exceptions import AppException
    from app.student_portal.services import academic_service as service

    monkeypatch.setattr(service._legacy, "transcript", lambda _user: {"items": []})
    with pytest.raises(AppException) as exc:
        service.transcript_print({"userType": "STUDENT"}, {"reason": "查询"})

    assert "不少于5个字" in exc.value.message


def test_query_copy_is_explicitly_non_official_and_non_verifiable(monkeypatch):
    from app.student_portal.services import academic_service as service

    monkeypatch.setattr(
        service._legacy,
        "transcript",
        lambda _user: {"items": [{"courseName": "<script>alert(1)</script>", "score": 88}]},
    )
    monkeypatch.setattr(
        service.common,
        "print_log",
        lambda _user, payload: {
            "watermark": "仅供本人查询",
            "loggedAt": "2026-07-27T10:00:00",
            "auditPayload": payload,
        },
    )

    result = service.transcript_print(
        {"userType": "STUDENT", "studentId": "1"},
        {"reason": "用于个人成绩核对"},
    )

    assert result["docName"] == "个人成绩查询件"
    assert result["documentType"] == "PERSONAL_GRADE_QUERY_COPY"
    assert result["official"] is False
    assert result["verifiable"] is False
    assert result["verificationCode"] is None
    assert result["renderPolicy"] == "TEXT_ONLY"
    assert "不等同于" in result["notice"]
    assert result["auditPayload"]["bizType"] == "GRADE_QUERY_COPY"
    assert result["auditPayload"]["docName"] == "个人成绩查询件"
    # 原始业务文本可以保留给前端；前端必须按TEXT_ONLY用textContent渲染，不能innerHTML拼接。
    assert result["document"]["items"][0]["courseName"] == "<script>alert(1)</script>"


def test_portal_package_exports_transcript_safety_facade():
    from app.student_portal.services import academic_service as service

    assert service.__name__.endswith("academic_transcript_safety_facade")
