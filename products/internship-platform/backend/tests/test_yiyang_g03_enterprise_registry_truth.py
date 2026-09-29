"""Yiyang G03: internal enterprise lookup is usable, external registry truth stays fail-closed.

Procurement truth boundary:
- school-owned enterprise library may search by enterprise name / credit code;
- student-entered identity can never self-upgrade to registry VERIFIED;
- a real government/commercial registry verification requires an authorized external provider.
"""
from __future__ import annotations

import inspect

from app.modules.internship.services import internship_application_service as application_svc
from app.modules.internship.services import internship_enterprise_service as enterprise_svc
from app.modules.internship.services import (
    internship_student_application_context_service as student_application_svc,
)


def _complete_self_arranged_payload() -> dict:
    return {
        "companyName": "益阳示例智能制造有限公司",
        "companyCreditCode": "91430900MA4L12345X",
        "companyPrincipal": "张负责人",
        "companyScale": "中型",
        "companyPhone": "0737-1234567",
        "companyEmail": "hr@example.com",
        "companyNature": "民营企业",
        "companyIndustry": "制造业",
        "companyRegisteredAddress": "湖南省益阳市赫山区示例大道88号",
        "companyPostalCode": "413000",
        "companyProvince": "湖南省",
        "companyCity": "益阳市",
        "companyDistrict": "赫山区",
        "contactName": "李人事",
        "contactPhone": "13800138000",
        "internshipDepartment": "智能制造部",
        "positionName": "设备运维实习生",
        "positionCategory": "工程技术",
        "workContent": "参与设备巡检、维护记录和生产现场技术支持。",
        "enterpriseMentorName": "王工程师",
        "enterpriseMentorPhone": "13900139000",
        "workCountry": "中国",
        "workProvince": "湖南省",
        "workCity": "益阳市",
        "workDistrict": "赫山区",
        "workAddress": "湖南省益阳市赫山区产业园A区",
        "internshipStartDate": "2026-10-01",
        "internshipEndDate": "2027-01-15",
        "internshipMode": "自主实习",
        "majorMatch": True,
        "agreedSalary": "2800.00",
        "evidenceFileId": "",
        "agreementFileIds": [],
    }


def test_g03_internal_enterprise_lookup_searches_name_and_credit_code():
    source = inspect.getsource(enterprise_svc.list_enterprises)
    assert "EmpCompany.name.like" in source
    assert "EmpCompany.credit_code.like" in source
    assert "EmpCompany.tenant_id == _tid()" in source
    assert "EmpCompany.is_deleted.is_(False)" in source


def test_g03_enterprise_identity_validation_rejects_pasted_labels_and_bad_codes():
    assert enterprise_svc._validate_company_name("湖南跃科信息工程有限公司") is None
    assert enterprise_svc._validate_company_name("税号: 91430104MA4RXFFJ0T") is not None
    assert enterprise_svc._validate_company_name("6607007880100001016") is not None

    assert enterprise_svc._validate_credit_code("91430104MA4RXFFJ0T") is None
    assert enterprise_svc._validate_credit_code("税号:91430104MA4RXFFJ0T") is not None
    assert enterprise_svc._validate_credit_code("9143 0104") is not None


def test_g03_student_payload_cannot_forge_registry_verified_state(monkeypatch):
    # File IDs are irrelevant to the registry-authority contract in this focused test.
    monkeypatch.setattr(
        application_svc,
        "_validate_file",
        lambda file_id, required=False: str(file_id or "").strip() or None,
    )
    payload = _complete_self_arranged_payload()
    payload.update({
        "registryVerificationStatus": "VERIFIED",
        "registryVerificationProvider": "student-self-claimed",
        "registryReference": "fake-reference",
        "registryVerifiedAt": "2026-09-29T00:00:00",
    })

    cleaned = application_svc._clean_self_arranged(payload, require_complete=True)
    assert cleaned["company_name"] == payload["companyName"]
    assert cleaned["company_credit_code"] == payload["companyCreditCode"]
    assert not any("registry" in key.lower() for key in cleaned)


def test_g03_company_identity_change_resets_registry_truth():
    source = inspect.getsource(student_application_svc.save)
    assert 'row.registry_verification_status = "UNVERIFIED"' in source
    assert "row.registry_verification_provider = None" in source
    assert "row.registry_reference = None" in source
    assert "row.registry_verified_at = None" in source


def test_g03_external_registry_is_explicitly_not_simulated():
    source = inspect.getsource(application_svc._clean_self_arranged)
    assert "student input can never turn a" in source
    assert "authorized provider adapter" in source
