"""Read-only compliance providers and federation registry."""
from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
from typing import Callable, Protocol

from sqlalchemy import select

from app.core.exceptions import AppException, not_found

from .schemas import (
    ComplianceItem,
    ComplianceState,
    DomainComplianceAssessment,
    MaterialConstraint,
    MaterialConstraintState,
    PolicyRef,
    PolicyRefBindingMode,
    ProviderMode,
    SubjectRef,
)


class IDomainComplianceProvider(Protocol):
    provider_code: str
    domain_code: str
    mode: ProviderMode

    def evaluate(
        self, *, subject_ref: SubjectRef, operation: str, user: dict,
    ) -> DomainComplianceAssessment: ...


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _internship_state(item: dict) -> ComplianceState:
    status = str(item.get("status") or "").upper()
    if status == "VALID":
        return ComplianceState.PASS
    if status == "NOT_APPLICABLE":
        return ComplianceState.NOT_APPLICABLE
    if status == "EXEMPTED":
        return ComplianceState.EXEMPTED
    if status == "PENDING":
        return ComplianceState.PENDING
    if status in {"MISSING", "REJECTED", "EXPIRED", "CONFIG_ERROR"}:
        is_block = (
            bool(item.get("required"))
            and bool(item.get("applicable", True))
            and str(item.get("severity") or "").upper() == "BLOCK"
        )
        return ComplianceState.BLOCKER if is_block else ComplianceState.WARNING
    return ComplianceState.NOT_EVALUATED


class InternshipComplianceProvider:
    provider_code = "INTERNSHIP_NATIVE"
    domain_code = "INTERNSHIP"
    mode = ProviderMode.NATIVE_ENGINE

    def __init__(self, evaluator: Callable | None = None):
        self._evaluator = evaluator

    def _native_evaluator(self) -> Callable:
        if self._evaluator is not None:
            return self._evaluator
        # Import the installed authority explicitly.  Importing the legacy
        # module here relied on unrelated startup order to monkey-patch it and
        # could otherwise bypass the corrected safety-evidence evaluation.
        from app.modules.internship.services.internship_compliance_authoritative_service import (
            evaluate_internship_compliance,
        )
        return evaluate_internship_compliance

    def evaluate(
        self, *, subject_ref: SubjectRef, operation: str, user: dict,
    ) -> DomainComplianceAssessment:
        native = self._native_evaluator()(subject_ref.subject_id, operation, user)
        policy_version = str(native.get("ruleVersion") or "") or None
        policy_ref = PolicyRef(
            provider_code=self.provider_code,
            authority_type="INTERNSHIP_COMPLIANCE_RULESET",
            authority_ref=policy_version or "ACTIVE_BATCH_RULESET",
            authority_version=policy_version,
            binding_mode=PolicyRefBindingMode.PINNED if policy_version else PolicyRefBindingMode.RESOLVE_ACTIVE,
        )
        items = []
        for source in native.get("items") or []:
            evidence_ref = None
            if source.get("evidenceId") is not None:
                evidence_ref = {
                    "evidenceId": str(source["evidenceId"]),
                    "evidenceVersion": source.get("evidenceVersion"),
                }
            target = {"route": source["route"]} if source.get("route") else None
            state = _internship_state(source)
            items.append(ComplianceItem(
                code=str(source.get("code") or "UNKNOWN"),
                label=str(source.get("label") or source.get("code") or "未命名检查"),
                state=state,
                applicable=state != ComplianceState.NOT_APPLICABLE,
                required=bool(source.get("required")),
                severity=str(source.get("severity") or "WARN").upper(),
                reason=str(source.get("reason") or "") or None,
                policy_ref=policy_ref,
                evidence_ref=evidence_ref,
                target=target,
            ))
        return DomainComplianceAssessment(
            provider_code=self.provider_code,
            provider_mode=self.mode,
            subject_ref=subject_ref,
            operation=str(native.get("operation") or operation).upper(),
            policy_version=policy_version,
            items=items,
            blocking=not bool(native.get("passed")),
            as_of=_utcnow(),
        )


class GraduationMaterialComplianceProvider:
    provider_code = "GRADUATION_MATERIAL"
    domain_code = "GRADUATION"
    mode = ProviderMode.MATERIAL_POLICY

    def __init__(self, session_factory: Callable | None = None):
        self._session_factory = session_factory

    def evaluate(
        self, *, subject_ref: SubjectRef, operation: str, user: dict,
    ) -> DomainComplianceAssessment:
        from app.core.tenant_scoped import tenant_get
        from app.models import FileObject, FileVersion, GraduationStudent
        from app.models.graduation_material import GraduationStudentMaterial
        from app.modules.graduation.materials.query_service import SAFE_SCAN
        from app.modules.graduation.materials.rule_service import active_rule, rule_items
        from app.modules.graduation.services.graduation_scope_service import assert_student_access
        from app.services.db_service import _tid, session

        cm = self._session_factory() if self._session_factory else session()
        with cm if hasattr(cm, "__enter__") else nullcontext(cm) as db:
            student = db.scalars(select(GraduationStudent).where(
                GraduationStudent.tenant_id == _tid(),
                GraduationStudent.id == int(subject_ref.subject_id),
                GraduationStudent.is_deleted.is_(False),
            )).first()
            if not student:
                raise not_found("毕业设计学生不存在")
            assert_student_access(db, student, "platform.compliance.evaluate")
            rule = active_rule(db, int(student.batch_id))
            definitions = rule_items(db, int(rule.id))
            actuals = list(db.scalars(select(GraduationStudentMaterial).where(
                GraduationStudentMaterial.tenant_id == _tid(),
                GraduationStudentMaterial.gd_student_id == int(student.id),
                GraduationStudentMaterial.is_deleted.is_(False),
            )).all())
            by_code = {str(row.material_code).upper(): row for row in actuals}
            policy_version = str(int(rule.rule_version or 1))
            policy_ref = PolicyRef(
                provider_code=self.provider_code,
                authority_type="GRADUATION_MATERIAL_RULE",
                authority_ref=str(rule.id),
                authority_version=policy_version,
                binding_mode=PolicyRefBindingMode.PINNED,
            )
            items: list[ComplianceItem] = []
            for definition in definitions:
                actual = by_code.get(str(definition.material_code).upper())
                major_mismatch = bool(
                    definition.applicable_major_id
                    and str(definition.applicable_major_id) != str(student.major_id or "")
                )
                topic_type = str(getattr(student, "topic_type", "") or "")
                topic_mismatch = bool(
                    definition.applicable_topic_type
                    and str(definition.applicable_topic_type) != topic_type
                )
                required = bool(definition.required)
                reason = None
                evidence_ref = None
                if major_mismatch or topic_mismatch:
                    state = ComplianceState.NOT_APPLICABLE
                    reason = "当前专业或课题类型不适用"
                elif actual and str(actual.required_status).upper() == "NOT_APPLICABLE":
                    state = ComplianceState.NOT_APPLICABLE
                    reason = "业务材料目录标记为不适用"
                elif actual and str(actual.required_status).upper() == "EXEMPTED":
                    state = ComplianceState.EXEMPTED
                    reason = "业务材料目录已豁免"
                elif not actual or not actual.current_version_id:
                    state = ComplianceState.BLOCKER if required else ComplianceState.NOT_APPLICABLE
                    reason = "缺少必需材料" if required else "可选材料未提交"
                else:
                    version = tenant_get(db, FileVersion, actual.current_version_id)
                    file_obj = tenant_get(db, FileObject, version.file_object_id) if version else None
                    evidence_ref = {
                        "materialId": str(actual.id),
                        "fileVersionId": str(actual.current_version_id),
                        "fileObjectId": str(file_obj.id) if file_obj else None,
                    }
                    business_status = str(actual.business_status or "").upper()
                    review_status = str(actual.review_status or "").upper()
                    ready = bool(
                        file_obj
                        and str(file_obj.status or "").upper() == "AVAILABLE"
                        and str(file_obj.scan_status or "").upper() in SAFE_SCAN
                    )
                    if business_status in {"RETURNED"} or review_status == "RETURNED":
                        state = ComplianceState.BLOCKER if required else ComplianceState.WARNING
                        reason = actual.reject_reason or "材料已退回"
                    elif not ready or business_status in {"UPLOADING", "SCANNING", "SUBMITTED"} or review_status == "PENDING":
                        state = ComplianceState.PENDING
                        reason = "文件安全状态或业务审核尚未完成"
                    elif business_status in {"APPROVED", "ARCHIVED"} or review_status in {"APPROVED", "NOT_REQUIRED"}:
                        state = ComplianceState.PASS
                    else:
                        state = ComplianceState.NOT_EVALUATED
                        reason = f"未识别的业务材料状态：{business_status or 'UNKNOWN'}"
                constraints = {
                    "allowedExtensions": MaterialConstraint(
                        state=MaterialConstraintState.ENFORCED,
                        value=list(definition.allowed_ext_json or []),
                    ),
                    "maxFiles": MaterialConstraint(
                        state=MaterialConstraintState.ENFORCED,
                        value=int(definition.max_files or 1),
                    ),
                    "maxSizeBytes": MaterialConstraint(
                        state=MaterialConstraintState.ENFORCED,
                        value=int(definition.max_size_bytes or 0),
                    ),
                }
                items.append(ComplianceItem(
                    code=str(definition.material_code),
                    label=str(definition.material_name),
                    state=state,
                    applicable=state != ComplianceState.NOT_APPLICABLE,
                    required=required,
                    severity="BLOCK" if required else "WARN",
                    reason=reason,
                    policy_ref=policy_ref,
                    evidence_ref=evidence_ref,
                    target={"route": f"/graduation/materials/{student.id}"},
                    constraints=constraints,
                ))
            blocking = any(item.state == ComplianceState.BLOCKER for item in items)
            return DomainComplianceAssessment(
                provider_code=self.provider_code,
                provider_mode=self.mode,
                subject_ref=subject_ref,
                operation=str(operation or "SUBMIT").upper(),
                policy_version=policy_version,
                items=items,
                blocking=blocking,
                as_of=_utcnow(),
            )


class EvidenceOnlyProvider:
    """Fail-closed placeholder where no source-backed policy exists yet."""

    def __init__(self, provider_code: str, domain_code: str, domain_label: str):
        self.provider_code = provider_code
        self.domain_code = str(domain_code).upper()
        self.domain_label = domain_label
        self.mode = ProviderMode.EVIDENCE_ONLY

    def evaluate(
        self, *, subject_ref: SubjectRef, operation: str, user: dict,
    ) -> DomainComplianceAssessment:
        del user
        item = ComplianceItem(
            code="POLICY_NOT_SUPPORTED",
            label=f"{self.domain_label}合规策略",
            state=ComplianceState.NOT_EVALUATED,
            applicable=True,
            required=True,
            severity="BLOCK",
            reason="当前域仅有证据读取能力，尚无可联邦的来源规则；未执行不等于通过",
        )
        return DomainComplianceAssessment(
            provider_code=self.provider_code,
            provider_mode=self.mode,
            subject_ref=subject_ref,
            operation=str(operation or "READ").upper(),
            policy_version=None,
            items=[item],
            blocking=True,
            as_of=_utcnow(),
        )


class ComplianceFederation:
    def __init__(self, providers: list[IDomainComplianceProvider]):
        self._providers = {}
        for provider in providers:
            code = str(provider.provider_code or "").strip().upper()
            domain = str(provider.domain_code or "").strip().upper()
            if not code or not domain or code in self._providers:
                raise AppException(
                    "COMPLIANCE_PROVIDER_INVALID",
                    "合规 provider code/domain 为空或 provider code 重复",
                )
            self._providers[code] = provider

    @property
    def provider_codes(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))

    def evaluate(
        self, *, provider_code: str, subject_ref: SubjectRef, operation: str, user: dict,
    ) -> DomainComplianceAssessment:
        code = str(provider_code or "").strip().upper()
        provider = self._providers.get(code)
        if not provider:
            raise AppException("COMPLIANCE_PROVIDER_NOT_FOUND", "未知合规 provider", http_status=404)
        if str(subject_ref.domain or "").upper() != str(provider.domain_code or "").strip().upper():
            raise AppException(
                "COMPLIANCE_SUBJECT_DOMAIN_MISMATCH",
                "合规 provider 与 subject domain 不匹配",
                http_status=403,
            )
        try:
            return provider.evaluate(subject_ref=subject_ref, operation=operation, user=user)
        except AppException:
            raise
        except Exception:
            return DomainComplianceAssessment(
                provider_code=code,
                provider_mode=provider.mode,
                subject_ref=subject_ref,
                operation=str(operation or "READ").upper(),
                policy_version=None,
                items=[ComplianceItem(
                    code="PROVIDER_EVALUATION_FAILED",
                    label="来源合规评估不可用",
                    state=ComplianceState.NOT_EVALUATED,
                    applicable=True,
                    required=True,
                    severity="BLOCK",
                    reason="来源域评估失败；系统按未评估且阻断处理",
                )],
                blocking=True,
                as_of=_utcnow(),
            )


def default_federation() -> ComplianceFederation:
    return ComplianceFederation([
        InternshipComplianceProvider(),
        GraduationMaterialComplianceProvider(),
        EvidenceOnlyProvider("AFFAIRS_EVIDENCE", "STUDENT_AFFAIRS", "学生事务"),
        EvidenceOnlyProvider("ACADEMIC_EVIDENCE", "ACADEMIC", "教务"),
    ])
