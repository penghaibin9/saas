from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.modules.platform.business_forms.domain_adapters import (
    BusinessFormCommandAdapterRegistry,
    BusinessFormDataAdapterRegistry,
    BusinessFormSubmissionService,
    InternshipSpecialFilingCommandAdapter,
    InternshipSpecialFilingDataAdapter,
)
from app.modules.platform.business_forms.application_service import BusinessFormApplicationService
from app.modules.platform.business_forms.definition_service import BusinessFormDefinitionService
from app.modules.platform.business_forms.models import BusinessFormDefinition, BusinessFormVersion
from app.models.base import Base
from app.modules.platform.business_forms.runtime import BusinessFormRuntimeValidator
from app.modules.platform.business_forms.schema_validator import (
    BusinessFormSchemaValidator,
    MAX_CONDITION_DEPTH,
    MAX_CONDITION_NODES,
    MAX_FIELDS,
    compute_schema_hash,
)
from app.modules.platform.business_forms.schemas import BusinessFormVersionDTO, FormClient


def _version(*, clients=None, fields=None, adapter="INTERNSHIP_SPECIAL_FILING"):
    version = BusinessFormVersionDTO.model_validate({
        "form_code": "INTERNSHIP_SPECIAL_FILING_V1",
        "version_id": 101,
        "version_no": 1,
        "schema_hash": "pending",
        "schema_version": "1.0",
        "supported_clients": clients or {"STAFF_PC", "STUDENT_PC", "STUDENT_MINIAPP"},
        "policy_refs": [],
        "domain_data_adapter": "INTERNSHIP_SPECIAL_FILING_INITIAL",
        "domain_command_adapter": adapter,
        "fields": fields or [
            {
                "code": "filingType", "type": "select", "label": "备案类型", "required": True,
                "options": [
                    {"label": "高风险", "value": "HIGH_RISK"},
                    {"label": "跨省", "value": "CROSS_PROVINCE"},
                ],
            },
            {"code": "triggerReason", "type": "textarea", "label": "触发原因", "required": True, "maxLength": 500},
            {
                "code": "riskDescription", "type": "textarea", "label": "风险说明",
                "visibleWhen": {"op": "eq", "field": "filingType", "value": "HIGH_RISK"},
                "requiredWhen": {"op": "eq", "field": "filingType", "value": "HIGH_RISK"},
            },
            {"code": "fileIds", "type": "file", "label": "依据材料", "required": True, "multiple": True},
            {"code": "studentId", "type": "student-picker", "label": "学生", "required": False},
            {"code": "serverStatus", "type": "text", "label": "状态", "readonly": True},
        ],
        "conditions": [],
    })
    return version.model_copy(update={"schema_hash": compute_schema_hash(version)})


def test_publish_validator_accepts_bounded_schema_and_hash():
    version = _version()
    assert BusinessFormSchemaValidator().validate(version) is version
    assert len(version.schema_hash) == 64


@pytest.mark.parametrize("dangerous", [
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "eval(userInput)",
    "Function(userInput)",
])
def test_publish_rejects_script_html_url_and_eval_payloads(dangerous):
    version = _version()
    fields = [field.model_copy() for field in version.fields]
    fields[0] = fields[0].model_copy(update={"help_text": dangerous})
    tampered = version.model_copy(update={"fields": fields, "schema_hash": "pending"})
    tampered = tampered.model_copy(update={"schema_hash": compute_schema_hash(tampered)})
    with pytest.raises(AppException) as caught:
        BusinessFormSchemaValidator().validate(tampered)
    assert caught.value.code == "FORM_SCHEMA_INVALID"


def test_publish_rejects_prototype_pollution_and_reserved_business_fields():
    with pytest.raises(ValidationError):
        BusinessFormVersionDTO.model_validate({
            **_version().model_dump(mode="json"),
            "fields": [{
                "code": "ok", "type": "text", "label": "x", "__proto__": {"admin": True},
            }],
        })
    reserved = _version(fields=[{"code": "tenantId", "type": "text", "label": "租户"}])
    with pytest.raises(AppException):
        BusinessFormSchemaValidator().validate(reserved, verify_hash=False)


def test_publish_rejects_field_and_condition_budgets():
    too_many = _version(fields=[{"code": f"field{i}", "type": "text", "label": str(i)} for i in range(MAX_FIELDS + 1)])
    with pytest.raises(AppException):
        BusinessFormSchemaValidator().validate(too_many, verify_hash=False)

    condition = {"op": "eq", "field": "filingType", "value": "HIGH_RISK"}
    for _ in range(MAX_CONDITION_DEPTH):
        condition = {"op": "all", "conditions": [condition]}
    version = _version()
    fields = [field.model_copy() for field in version.fields]
    fields[0] = fields[0].model_copy(update={"visible_when": condition})
    too_deep = version.model_copy(update={"fields": fields})
    with pytest.raises(AppException):
        BusinessFormSchemaValidator().validate(too_deep, verify_hash=False)

    leaves = [
        {"op": "eq", "field": "controller", "value": str(index)}
        for index in range(MAX_CONDITION_NODES // 2)
    ]
    over_budget = _version(fields=[
        {"code": "controller", "type": "text", "label": "控制字段"},
        {
            "code": "first", "type": "text", "label": "第一字段",
            "visibleWhen": {"op": "any", "conditions": leaves},
        },
        {
            "code": "second", "type": "text", "label": "第二字段",
            "visibleWhen": {"op": "any", "conditions": leaves},
        },
    ])
    with pytest.raises(AppException) as caught:
        BusinessFormSchemaValidator().validate(over_budget, verify_hash=False)
    assert caught.value.code == "FORM_SCHEMA_INVALID"


def test_runtime_rejects_stale_version_hash_hidden_readonly_and_unknown_fields():
    version = _version()
    runtime = BusinessFormRuntimeValidator(
        file_authorizer=lambda *_: True, student_authorizer=lambda *_: True,
    )
    base = {
        "filingType": "CROSS_PROVINCE", "triggerReason": "跨省实习需要备案",
        "fileIds": ["11"],
    }
    with pytest.raises(AppException) as caught:
        runtime.validate_submission(
            version=version, submitted_values=base, client="STUDENT_PC",
            schema_hash=version.schema_hash, version_id=999, context={}, user={},
        )
    assert caught.value.code == "FORM_VERSION_STALE"

    with pytest.raises(AppException) as caught:
        runtime.validate_submission(
            version=version, submitted_values=base, client="STUDENT_PC",
            schema_hash="0" * 64, version_id=101, context={}, user={},
        )
    assert caught.value.code == "FORM_SCHEMA_HASH_MISMATCH"

    cases = [
        ({**base, "riskDescription": "隐藏字段注入"}, "FORM_HIDDEN_FIELD_INJECTION"),
        ({**base, "serverStatus": "APPROVED"}, "FORM_READONLY_FIELD_INJECTION"),
        ({**base, "tenantId": "attacker"}, "FORM_FIELD_INJECTION"),
    ]
    for values, code in cases:
        with pytest.raises(AppException) as caught:
            runtime.validate_submission(
                version=version, submitted_values=values, client="STUDENT_PC",
                schema_hash=version.schema_hash, version_id=101, context={}, user={},
            )
        assert caught.value.code == code


def test_runtime_rechecks_required_client_student_and_file_authorization():
    version = _version()
    denied_student = BusinessFormRuntimeValidator(
        file_authorizer=lambda file_id, *_: str(file_id) == "11",
        student_authorizer=lambda student_id, *_: str(student_id) == "22",
    )
    required_values = {
        "filingType": "HIGH_RISK", "triggerReason": "高风险岗位触发备案", "fileIds": ["11"],
    }
    with pytest.raises(AppException) as caught:
        denied_student.validate_submission(
            version=version, submitted_values=required_values, client="STUDENT_PC",
            schema_hash=version.schema_hash, version_id=101, context={}, user={},
        )
    assert caught.value.code == "FORM_REQUIRED"

    with pytest.raises(AppException) as caught:
        denied_student.validate_submission(
            version=version,
            submitted_values={**required_values, "riskDescription": "风险说明完整", "studentId": "999"},
            client="STUDENT_PC", schema_hash=version.schema_hash, version_id=101, context={}, user={},
        )
    assert caught.value.code == "NO_DATA_SCOPE"

    with pytest.raises(AppException) as caught:
        denied_student.validate_submission(
            version=version,
            submitted_values={**required_values, "riskDescription": "风险说明完整", "fileIds": ["999"]},
            client="STUDENT_PC", schema_hash=version.schema_hash, version_id=101, context={}, user={},
        )
    assert caught.value.code == "NO_PERMISSION"

    with pytest.raises(AppException) as caught:
        denied_student.validate_submission(
            version=version,
            submitted_values={**required_values, "riskDescription": "风险说明完整"},
            client="TEACHER_MINIAPP", schema_hash=version.schema_hash, version_id=101, context={}, user={},
        )
    assert caught.value.code == "FORM_CLIENT_UNSUPPORTED"

    with pytest.raises(AppException) as caught:
        denied_student.validate_submission(
            version=version,
            submitted_values={**required_values, "riskDescription": "风险说明完整"},
            client="ATTACKER_CLIENT", schema_hash=version.schema_hash,
            version_id=101, context={}, user={},
        )
    assert caught.value.code == "FORM_CLIENT_UNSUPPORTED"


def test_runtime_rebuilds_conditions_from_authoritative_initial_data():
    version = _version(fields=[
        {"code": "serverStatus", "type": "text", "label": "服务端状态", "readonly": True},
        {
            "code": "reason", "type": "textarea", "label": "原因",
            "visibleWhen": {"op": "eq", "field": "serverStatus", "value": "PENDING"},
            "requiredWhen": {"op": "eq", "field": "serverStatus", "value": "PENDING"},
        },
    ])
    runtime = BusinessFormRuntimeValidator()
    sanitized = runtime.validate_submission(
        version=version,
        submitted_values={"reason": "由服务端状态触发"},
        authoritative_values={"serverStatus": "PENDING", "tenantId": "must-be-filtered"},
        client="STUDENT_PC",
        schema_hash=version.schema_hash,
        version_id=version.version_id,
        context={},
        user={},
    )
    assert sanitized == {"reason": "由服务端状态触发"}

    with pytest.raises(AppException) as caught:
        runtime.validate_submission(
            version=version,
            submitted_values={"reason": "隐藏字段不得提交"},
            authoritative_values={"serverStatus": "APPROVED"},
            client="STUDENT_PC",
            schema_hash=version.schema_hash,
            version_id=version.version_id,
            context={},
            user={},
        )
    assert caught.value.code == "FORM_HIDDEN_FIELD_INJECTION"


@pytest.mark.parametrize("invalid_number", [float("nan"), float("inf"), float("-inf")])
def test_runtime_rejects_non_finite_numbers_and_boolean_file_ids(invalid_number):
    version = _version(fields=[
        {"code": "amount", "type": "number", "label": "数值"},
        {"code": "fileIds", "type": "file", "label": "文件", "multiple": True},
    ])
    runtime = BusinessFormRuntimeValidator(file_authorizer=lambda *_: True)
    with pytest.raises(AppException) as caught:
        runtime.validate_submission(
            version=version,
            submitted_values={"amount": invalid_number},
            client="STUDENT_PC",
            schema_hash=version.schema_hash,
            version_id=version.version_id,
            context={},
            user={},
        )
    assert caught.value.code == "FORM_VALUE_INVALID"

    with pytest.raises(AppException) as caught:
        runtime.validate_submission(
            version=version,
            submitted_values={"fileIds": [True]},
            client="STUDENT_PC",
            schema_hash=version.schema_hash,
            version_id=version.version_id,
            context={},
            user={},
        )
    assert caught.value.code == "FORM_VALUE_INVALID"


def test_special_filing_adapter_calls_canonical_commands_and_expected_version():
    calls = []

    def create(body, user):
        calls.append(("create", deepcopy(body), user))
        return {"id": "77", "status": "DRAFT", "version": 0}

    def submit(filing_id, *, user, expected_version):
        calls.append(("submit", filing_id, user, expected_version))
        return {"id": filing_id, "status": "PENDING_COLLEGE", "version": 1}

    adapter = InternshipSpecialFilingCommandAdapter(create_command=create, submit_command=submit)
    version = _version(fields=[
        {"code": "triggerReason", "type": "textarea", "label": "原因", "required": True},
        {"code": "fileIds", "type": "file", "label": "文件", "required": True, "multiple": True},
    ])
    runtime = BusinessFormRuntimeValidator(file_authorizer=lambda *_: True)
    service = BusinessFormSubmissionService(
        runtime, BusinessFormCommandAdapterRegistry([adapter]),
    )
    result = service.submit(
        version=version,
        values={"triggerReason": "夜班岗位需要备案", "fileIds": ["5"]},
        client=FormClient.STUDENT_PC,
        schema_hash=version.schema_hash,
        version_id=version.version_id,
        context={"action": "CREATE", "internshipId": "19"},
        expected_business_version=None,
        user={"userId": "u1"},
    )
    assert result.record_id == "77"
    assert calls[0] == (
        "create",
        {"triggerReason": "夜班岗位需要备案", "fileIds": ["5"], "internshipId": "19"},
        {"userId": "u1"},
    )

    with pytest.raises(AppException) as caught:
        adapter.submit(
            context={"action": "SUBMIT", "filingId": "77"}, values={}, form_version=version,
            expected_business_version=None, user={},
        )
    assert caught.value.code == "FORM_EXPECTED_VERSION_REQUIRED"
    submitted = adapter.submit(
        context={"action": "SUBMIT", "filingId": "77"}, values={}, form_version=version,
        expected_business_version=0, user={"userId": "u1"},
    )
    assert submitted.status == "PENDING_COLLEGE"
    assert calls[-1] == ("submit", "77", {"userId": "u1"}, 0)


def test_unknown_adapter_fails_closed_and_no_generic_submission_model_exists():
    with pytest.raises(AppException):
        BusinessFormCommandAdapterRegistry([]).get("UNKNOWN")
    model_source = (
        __import__("pathlib").Path("app/modules/platform/business_forms/models.py")
        .read_text(encoding="utf-8")
    )
    assert "class GenericFormSubmission" not in model_source
    assert "class GenericApproval" not in model_source
    assert "class GenericBusinessRecord" not in model_source
    assert "__tablename__ = \"t_business_form_definition\"" in model_source
    assert "__tablename__ = \"t_business_form_version\"" in model_source


def test_data_adapter_uses_canonical_compliance_scope_and_never_derives_rules():
    calls = []

    def canonical(internship_id, operation, *, user):
        calls.append((internship_id, operation, user))
        return {
            "items": [
                {"code": "specialFiling", "status": "PENDING", "reason": "canonical"},
            ],
        }

    adapter = InternshipSpecialFilingDataAdapter(compliance_evaluator=canonical)
    assert adapter.load_initial(
        context={"internshipId": "19"}, user={"userId": "u1"},
    ) == {"serverStatus": "PENDING"}
    assert calls == [("19", "ONBOARD", {"userId": "u1"})]
    with pytest.raises(AppException) as caught:
        adapter.load_initial(context={}, user={})
    assert caught.value.code == "FORM_CONTEXT_INVALID"


def test_definition_versions_publish_immutably_and_new_changes_create_a_new_version():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        BusinessFormDefinition.__table__, BusinessFormVersion.__table__,
    ])
    with Session(engine) as db:
        service = BusinessFormDefinitionService(db, tenant_id=7, actor_id=9)
        definition = service.create_definition(
            form_code="internship_special_filing_v1",
            form_name="实习特殊备案",
            domain_code="internship",
        )
        payload = {
            "schemaVersion": "1.0",
            "supportedClients": ["STAFF_PC", "STUDENT_PC"],
            "domainDataAdapter": "INTERNSHIP_SPECIAL_FILING_INITIAL",
            "domainCommandAdapter": "INTERNSHIP_SPECIAL_FILING",
            "fields": [{"code": "triggerReason", "type": "textarea", "label": "触发原因", "required": True}],
        }
        first = service.create_draft_version(definition.id, payload)
        assert first.version_no == 1
        service.publish_version(first.id, expected_version=0)
        assert first.status == "PUBLISHED"
        assert definition.active_version_id == first.id

        changed = {
            **payload,
            "supportedClients": ["STAFF_PC", "STUDENT_PC", "STUDENT_MINIAPP"],
            "fields": payload["fields"] + [{"code": "fileIds", "type": "file", "label": "依据", "multiple": True}],
        }
        second = service.create_draft_version(definition.id, changed)
        assert second.version_no == 2
        impact = service.impact_analysis(second.id)
        assert impact["addedFields"] == ["fileIds"]
        assert impact["addedClients"] == ["STUDENT_MINIAPP"]
        service.publish_version(second.id, expected_version=0)
        assert first.status == "DISABLED"
        assert second.status == "PUBLISHED"
        assert definition.active_version_id == second.id

        second.schema_json = {"fields": [], "conditions": []}
        with pytest.raises(Exception) as caught:
            db.flush()
        assert "published business form version is immutable" in str(caught.value)


def test_disabled_published_version_remains_permanently_immutable():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        BusinessFormDefinition.__table__, BusinessFormVersion.__table__,
    ])
    with Session(engine) as db:
        service = BusinessFormDefinitionService(db, tenant_id=7, actor_id=9)
        definition = service.create_definition(
            form_code="immutable_after_disable", form_name="不可变", domain_code="internship",
        )
        row = service.create_draft_version(definition.id, {
            "supportedClients": ["STAFF_PC"],
            "domainDataAdapter": "INTERNSHIP_SPECIAL_FILING_INITIAL",
            "domainCommandAdapter": "INTERNSHIP_SPECIAL_FILING",
            "fields": [{"code": "reason", "type": "text", "label": "原因"}],
        })
        service.publish_version(row.id, expected_version=0)
        service.disable_version(row.id, expected_version=1)
        db.flush()
        row.schema_json = {"fields": [], "conditions": []}
        with pytest.raises(Exception) as caught:
            db.flush()
        assert "published business form version is immutable" in str(caught.value)


def test_resolve_active_policy_requires_explicit_impact_ack_before_publish():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        BusinessFormDefinition.__table__, BusinessFormVersion.__table__,
    ])
    with Session(engine) as db:
        service = BusinessFormDefinitionService(db, tenant_id=7, actor_id=9)
        definition = service.create_definition(
            form_code="resolve_active_ack", form_name="动态策略", domain_code="graduation",
        )
        row = service.create_draft_version(definition.id, {
            "supportedClients": ["STAFF_PC"],
            "domainDataAdapter": "GRADUATION_INITIAL",
            "domainCommandAdapter": "GRADUATION_COMMAND",
            "policyRefs": [{
                "provider_code": "GRADUATION_MATERIAL",
                "authority_type": "GRADUATION_MATERIAL_RULE",
                "authority_ref": "ACTIVE",
                "binding_mode": "RESOLVE_ACTIVE",
            }],
            "fields": [{"code": "reason", "type": "text", "label": "原因"}],
        })
        impact = service.impact_analysis(row.id)
        assert len(impact["resolveActivePolicyRefs"]) == 1
        with pytest.raises(AppException) as caught:
            service.publish_version(row.id, expected_version=0)
        assert caught.value.code == "FORM_POLICY_IMPACT_ACK_REQUIRED"
        service.publish_version(
            row.id, expected_version=0, resolve_active_impact_ack=True,
        )
        assert row.status == "PUBLISHED"


def test_application_service_loads_exact_active_version_before_real_command():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        BusinessFormDefinition.__table__, BusinessFormVersion.__table__,
    ])
    calls = []

    def canonical_read(internship_id, operation, *, user):
        calls.append(("read", internship_id, operation, user))
        return {"items": [{"code": "specialFiling", "status": "NOT_APPLICABLE"}]}

    def canonical_create(body, user):
        calls.append(("create", deepcopy(body), user))
        return {"id": "88", "status": "DRAFT", "version": 0}

    with Session(engine) as db:
        definitions = BusinessFormDefinitionService(db, tenant_id=7, actor_id=9)
        definition = definitions.create_definition(
            form_code="internship_special_filing_v1",
            form_name="特殊备案",
            domain_code="internship",
        )
        row = definitions.create_draft_version(definition.id, {
            "supportedClients": ["STUDENT_PC"],
            "domainDataAdapter": "INTERNSHIP_SPECIAL_FILING_INITIAL",
            "domainCommandAdapter": "INTERNSHIP_SPECIAL_FILING",
            "fields": [
                {"code": "serverStatus", "type": "text", "label": "状态", "readonly": True},
                {
                    "code": "triggerReason", "type": "textarea", "label": "原因",
                    "visibleWhen": {"op": "eq", "field": "serverStatus", "value": "NOT_APPLICABLE"},
                    "requiredWhen": {"op": "eq", "field": "serverStatus", "value": "NOT_APPLICABLE"},
                },
                {"code": "fileIds", "type": "file", "label": "材料", "required": True, "multiple": True},
            ],
        })
        definitions.publish_version(row.id, expected_version=0)
        runtime = BusinessFormRuntimeValidator(file_authorizer=lambda *_: True)
        app = BusinessFormApplicationService(
            db,
            tenant_id=7,
            runtime=runtime,
            command_adapters=BusinessFormCommandAdapterRegistry([
                InternshipSpecialFilingCommandAdapter(create_command=canonical_create),
            ]),
            data_adapters=BusinessFormDataAdapterRegistry([
                InternshipSpecialFilingDataAdapter(compliance_evaluator=canonical_read),
            ]),
        )
        loaded = app.load_form(
            form_code="INTERNSHIP_SPECIAL_FILING_V1",
            version_id=row.id,
            client="STUDENT_PC",
            context={"internshipId": "19"},
            user={"userId": "u1"},
        )
        assert loaded["initialData"] == {"serverStatus": "NOT_APPLICABLE"}
        result = app.submit(
            form_code="INTERNSHIP_SPECIAL_FILING_V1",
            version_id=row.id,
            schema_hash=row.schema_hash,
            client="STUDENT_PC",
            values={"triggerReason": "跨省岗位需要备案", "fileIds": ["5"]},
            context={"action": "CREATE", "internshipId": "19"},
            expected_business_version=None,
            user={"userId": "u1"},
        )
        assert result.record_id == "88"
        assert [call[0] for call in calls] == ["read", "read", "create"]
        assert calls[-1] == (
            "create",
            {"triggerReason": "跨省岗位需要备案", "fileIds": ["5"], "internshipId": "19"},
            {"userId": "u1"},
        )
        definitions.disable_version(row.id, expected_version=1)
        with pytest.raises(AppException):
            app.submit(
                form_code="INTERNSHIP_SPECIAL_FILING_V1",
                version_id=row.id,
                schema_hash=row.schema_hash,
                client="STUDENT_PC",
                values={"triggerReason": "不得到达命令", "fileIds": ["5"]},
                context={"action": "CREATE", "internshipId": "19"},
                expected_business_version=None,
                user={"userId": "u1"},
            )
