"""O4 server-side orientation qualification and payment truth.

The browser and mini-program only render this verdict.  All blockers are derived
from stable identity, frozen flow, formal files, payment/green-channel facts,
canonical dorm facts and open exceptions.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import false, func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (
    DormBed,
    DormStay,
    GreenChannelApplication,
    OrientationBatch,
    OrientationException,
    OrientationFlowStep,
    OrientationMaterial,
    OrientationMaterialRequirement,
    OrientationPaymentAccount,
    OrientationQualificationDecision,
    OrientationStudent,
    OrientationStudentStep,
    StudentAccountLink,
    StudentProfile,
)
from app.models.file import FileBinding, FileObject, FileVersion
from app.services.db_service import _iso, _tid, session
from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED

RULE_VERSION = "O4.1"
PRECHECK_STEPS = {"ACTIVATE", "INFO", "MATERIAL", "PAYMENT", "DORM"}
TERMINAL_STEP = {"DONE", "WAIVED", "NOT_REQUIRED"}
PAYMENT_PASS = {"PAID", "WAIVED", "DEFERRED"}
BLOCKING_EXCEPTION = {"OPEN", "PROCESSING", "ESCALATED"}
CHECKIN_HARD_BLOCKER_CODES = {
    "FLOW_CONFIGURATION_MISSING",
    "IDENTITY_NOT_LINKED",
    "ACCOUNT_NOT_LINKED",
    "OPEN_EXCEPTION_IDENTITY",
}


def _actor_id(user=None) -> int | None:
    value = str((user or get_current_user_ctx() or {}).get("userId") or "")
    if value.startswith("db-"):
        value = value[3:]
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _money(value) -> str:
    return f"{Decimal(str(value or 0)):.2f}"


def _block(code: str, step: str, message: str, *, review: bool = False) -> dict:
    return {
        "code": code,
        "step": step,
        "message": message,
        "kind": "MANUAL_REVIEW" if review else "BLOCKING",
    }


def _blocks_on_site_checkin(item: dict) -> bool:
    """Only identity and the student's own information confirmation stop arrival.

    Materials, payment, dorm allocation and their operational exceptions remain
    visible follow-ups for the school.  They still prevent the final college
    confirmation through the strict ``verdict`` below, but do not make a student
    wait outside the check-in desk for work that belongs to back-office teams.
    """
    code = str(item.get("code") or "")
    step = str(item.get("step") or "")
    if code in CHECKIN_HARD_BLOCKER_CODES:
        return True
    if code in {"REQUIRED_STEP_INCOMPLETE", "STEP_BLOCKED"}:
        return step in {"ACTIVATE", "INFO"}
    return False


def _flow_context(db, student):
    batch = db.get(OrientationBatch, int(student.batch_id))
    if not batch or batch.is_deleted or int(batch.tenant_id) != int(student.tenant_id):
        return None, [], []
    definitions = list(db.scalars(select(OrientationFlowStep).where(
        OrientationFlowStep.tenant_id == student.tenant_id,
        OrientationFlowStep.flow_version_id == batch.flow_version_id,
        OrientationFlowStep.is_deleted.is_(False),
    ).order_by(OrientationFlowStep.sort_order, OrientationFlowStep.id)).all())
    states = list(db.scalars(select(OrientationStudentStep).where(
        OrientationStudentStep.tenant_id == student.tenant_id,
        OrientationStudentStep.orientation_student_id == student.id,
        OrientationStudentStep.is_deleted.is_(False),
    )).all())
    return batch, definitions, states


def _material_fact(db, student, requirement) -> tuple[dict, dict | None]:
    material = db.scalars(select(OrientationMaterial).where(
        OrientationMaterial.tenant_id == student.tenant_id,
        OrientationMaterial.ori_student_id == student.id,
        OrientationMaterial.student_id == student.student_id,
        OrientationMaterial.material_type == requirement.material_type,
        OrientationMaterial.is_current.is_(True),
        OrientationMaterial.is_deleted.is_(False),
    ).order_by(OrientationMaterial.id.desc())).first()
    base = {
        "materialType": requirement.material_type,
        "required": bool(requirement.required),
        "status": material.status if material else "MISSING",
        "evidenceReady": False,
    }
    if not material:
        return base, _block(
            "MATERIAL_MISSING", "MATERIAL", f"缺少必交材料：{requirement.material_name}"
        )
    version = db.get(FileVersion, int(material.file_version_id or 0)) if material.file_version_id else None
    file_obj = db.get(FileObject, int(version.file_object_id)) if version else None
    binding = db.scalars(select(FileBinding).where(
        FileBinding.tenant_id == student.tenant_id,
        FileBinding.biz_type == "ORIENTATION_MATERIAL",
        FileBinding.biz_id == str(material.id),
        FileBinding.version_id == material.file_version_id,
        FileBinding.student_id == student.student_id,
        FileBinding.is_current.is_(True),
        FileBinding.status == "ACTIVE",
        FileBinding.is_deleted.is_(False),
    )).first()
    scan = str(getattr(file_obj, "scan_status", None) or SCAN_NOT_REQUIRED).upper()
    base.update({
        "fileVersionStatus": getattr(version, "status", None) or "MISSING",
        "scanStatus": scan,
        "bindingActive": bool(binding),
    })
    ready = (
        material.status == "APPROVED"
        and version is not None and version.status == "APPROVED" and bool(version.is_current)
        and file_obj is not None and file_obj.status == "AVAILABLE"
        and binding is not None
        and (not requirement.requires_scan_clean or scan in READY_SCAN_STATES)
    )
    base["evidenceReady"] = ready
    if not ready:
        return base, _block(
            "MATERIAL_EVIDENCE_NOT_READY", "MATERIAL",
            f"{requirement.material_name}尚未形成审核通过且安全可用的正式文件证据",
        )
    return base, None


def _sync_fact_steps(db, student, state_by_key: dict, facts: dict) -> None:
    """Only a persisted recalculation may move canonical steps from real facts."""
    from app.services.orientation_flow_service import set_student_step_status

    derived = {
        "ACTIVATE": bool(facts["identity"].get("accountLinked")),
        "MATERIAL": bool(facts["materials"].get("satisfied")),
        "PAYMENT": bool(facts["payment"].get("satisfied")),
        "DORM": bool(facts["dorm"].get("satisfied")),
    }
    for key, satisfied in derived.items():
        row = state_by_key.get(key)
        if satisfied and row and row.status not in TERMINAL_STEP:
            set_student_step_status(
                db, student, key, "DONE", status_source="PROCESS_FACT",
                source_biz_id=f"qualification:{student.id}:{key.lower()}",
            )


def evaluate(db, student: OrientationStudent, *, persist: bool = False, actor_id=None) -> dict:
    blockers: list[dict] = []
    batch, definitions, states = _flow_context(db, student)
    if not batch or not definitions:
        blockers.append(_block(
            "FLOW_CONFIGURATION_MISSING", "FLOW", "冻结流程配置缺失，须人工核查", review=True
        ))
    state_by_key = {row.step_key: row for row in states}
    definition_by_key = {row.step_key: row for row in definitions if row.enabled}

    account_linked = False
    if student.student_id and student.identity_status == "LINKED":
        account_linked = bool(db.scalars(select(StudentAccountLink.id).where(
            StudentAccountLink.tenant_id == student.tenant_id,
            StudentAccountLink.student_id == student.student_id,
            StudentAccountLink.link_status == "ACTIVE",
            StudentAccountLink.is_deleted.is_(False),
        )).first())
    identity = {
        "profileLinked": bool(student.student_id and student.identity_status == "LINKED"),
        "accountLinked": account_linked,
    }
    if not identity["profileLinked"]:
        blockers.append(_block("IDENTITY_NOT_LINKED", "ACTIVATE", "迎新记录尚未绑定稳定学生主档"))
    elif not account_linked:
        blockers.append(_block("ACCOUNT_NOT_LINKED", "ACTIVATE", "学生主档尚未绑定有效登录账号"))

    required_materials = []
    material_blockers = []
    material_step = definition_by_key.get("MATERIAL")
    if material_step and material_step.required:
        if not batch:
            requirements = []
        else:
            requirements = list(db.scalars(select(OrientationMaterialRequirement).where(
                OrientationMaterialRequirement.tenant_id == student.tenant_id,
                OrientationMaterialRequirement.flow_version_id == batch.flow_version_id,
                OrientationMaterialRequirement.required.is_(True),
                OrientationMaterialRequirement.is_deleted.is_(False),
            ).order_by(OrientationMaterialRequirement.sort_order, OrientationMaterialRequirement.id)).all())
        if not requirements:
            material_blockers.append(_block(
                "MATERIAL_REQUIREMENTS_MISSING", "MATERIAL", "必交材料规则未配置，须人工核查", review=True
            ))
        for requirement in requirements:
            fact, blocker = _material_fact(db, student, requirement)
            required_materials.append(fact)
            if blocker:
                material_blockers.append(blocker)
    blockers.extend(material_blockers)
    material_satisfied = not material_blockers

    payment = db.scalars(select(OrientationPaymentAccount).where(
        OrientationPaymentAccount.tenant_id == student.tenant_id,
        OrientationPaymentAccount.orientation_student_id == student.id,
        OrientationPaymentAccount.is_deleted.is_(False),
    )).first()
    green = db.scalars(select(GreenChannelApplication).where(
        GreenChannelApplication.tenant_id == student.tenant_id,
        GreenChannelApplication.ori_student_id == student.id,
        GreenChannelApplication.status == "APPROVED",
        GreenChannelApplication.is_deleted.is_(False),
    ).order_by(GreenChannelApplication.id.desc())).first()
    payment_fact = {
        "status": payment.status if payment else "MISSING",
        "payableAmount": _money(payment.payable_amount if payment else 0),
        "paidAmount": _money(payment.paid_amount if payment else 0),
        "greenChannelApproved": bool(green),
    }
    payment_fact["satisfied"] = bool(
        green or (payment and payment.status in PAYMENT_PASS)
    )
    payment_step = definition_by_key.get("PAYMENT")
    if payment_step and payment_step.required:
        if not payment:
            blockers.append(_block(
                "PAYMENT_FACT_MISSING", "PAYMENT", "缴费事实未同步，须人工核查", review=True
            ))
        elif not payment_fact["satisfied"]:
            blockers.append(_block("PAYMENT_INCOMPLETE", "PAYMENT", "尚未缴清且绿色通道未通过"))

    dorm_fact = {"status": "NOT_REQUIRED", "satisfied": True}
    dorm_step = definition_by_key.get("DORM")
    dorm_state = state_by_key.get("DORM")
    if dorm_step and dorm_step.required and not (dorm_state and dorm_state.status == "WAIVED"):
        stay = db.scalars(select(DormStay).where(
            DormStay.tenant_id == student.tenant_id,
            DormStay.student_id == student.student_id,
            DormStay.status.in_(["RESERVED", "ACTIVE"]),
            DormStay.is_deleted.is_(False),
        ).order_by(DormStay.id.desc())).first() if student.student_id else None
        bed = db.get(DormBed, int(stay.bed_id)) if stay else None
        consistent = bool(
            stay and bed and int(bed.tenant_id) == int(student.tenant_id)
            and ((stay.status == "ACTIVE" and bed.status == "OCCUPIED" and bed.student_id == student.student_id)
                 or stay.status == "RESERVED")
        )
        dorm_fact = {
            "status": stay.status if stay else "MISSING",
            "satisfied": consistent,
            "bedId": str(stay.bed_id) if stay else "",
        }
        if not consistent:
            blockers.append(_block("DORM_NOT_CONFIRMED", "DORM", "必办住宿尚未形成有效预留或入住事实"))

    open_exceptions = list(db.scalars(select(OrientationException).where(
        OrientationException.tenant_id == student.tenant_id,
        OrientationException.ori_student_id == student.id,
        OrientationException.status.in_(BLOCKING_EXCEPTION),
        OrientationException.is_deleted.is_(False),
    )).all())
    for item in open_exceptions:
        blockers.append(_block(
            f"OPEN_EXCEPTION_{item.exception_type}", item.exception_type,
            "存在未关闭的迎新异常事项",
        ))

    facts = {
        "identity": identity,
        "materials": {"required": required_materials, "satisfied": material_satisfied},
        "payment": payment_fact,
        "dorm": dorm_fact,
        "openExceptionCount": len(open_exceptions),
        "requiredSteps": {},
    }
    if persist:
        _sync_fact_steps(db, student, state_by_key, facts)
        states = list(db.scalars(select(OrientationStudentStep).where(
            OrientationStudentStep.tenant_id == student.tenant_id,
            OrientationStudentStep.orientation_student_id == student.id,
            OrientationStudentStep.is_deleted.is_(False),
        )).all())
        state_by_key = {row.step_key: row for row in states}

    for key, definition in definition_by_key.items():
        if not definition.required or key not in PRECHECK_STEPS:
            continue
        row = state_by_key.get(key)
        status = row.status if row else "MISSING"
        facts["requiredSteps"][key] = status
        if key in {"ACTIVATE", "MATERIAL", "PAYMENT", "DORM"}:
            # These steps are verified above against their canonical process fact.
            continue
        if status not in TERMINAL_STEP:
            blockers.append(_block("REQUIRED_STEP_INCOMPLETE", key, f"必办环节“{definition.step_name}”尚未完成"))

    # A manually blocked step remains visible even if its underlying fact later changed.
    for row in states:
        if row.status == "BLOCKED" and row.step_key in PRECHECK_STEPS:
            blockers.append(_block(
                "STEP_BLOCKED", row.step_key, row.blocked_reason or "必办环节存在人工卡点"
            ))

    deduped = []
    seen = set()
    for item in blockers:
        key = (item["code"], item["step"], item["message"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    blockers = deduped
    checkin_blockers = [item for item in blockers if _blocks_on_site_checkin(item)]
    checkin_follow_ups = [item for item in blockers if not _blocks_on_site_checkin(item)]
    if any(item["kind"] == "MANUAL_REVIEW" for item in blockers):
        verdict = "MANUAL_REVIEW"
    elif blockers:
        verdict = "NOT_QUALIFIED"
    else:
        verdict = "QUALIFIED"

    digest_input = {
        "studentId": str(student.id), "ruleVersion": RULE_VERSION,
        "facts": facts, "blockers": blockers,
    }
    digest = hashlib.sha256(
        json.dumps(digest_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    result = {
        "studentId": str(student.id), "profileStudentId": str(student.student_id or ""),
        "verdict": verdict,
        "verdictLabel": {
            "QUALIFIED": "具备报到资格", "NOT_QUALIFIED": "暂不具备报到资格",
            "MANUAL_REVIEW": "需人工核查",
        }[verdict],
        "blockers": blockers, "facts": facts, "ruleVersion": RULE_VERSION,
        "inputHash": digest,
        "checkinEligibility": {
            "eligible": not checkin_blockers,
            "blockers": checkin_blockers,
            "followUps": checkin_follow_ups,
        },
    }
    if persist:
        decision = db.scalars(select(OrientationQualificationDecision).where(
            OrientationQualificationDecision.tenant_id == student.tenant_id,
            OrientationQualificationDecision.orientation_student_id == student.id,
            OrientationQualificationDecision.is_deleted.is_(False),
        ).with_for_update()).first()
        now = datetime.utcnow()
        if not decision:
            decision = OrientationQualificationDecision(
                tenant_id=student.tenant_id, orientation_student_id=student.id,
                student_id=student.student_id, verdict=verdict, blockers_json=blockers,
                facts_json=facts, rule_version=RULE_VERSION, input_hash=digest,
                evaluated_at=now, evaluated_by=actor_id,
            )
            db.add(decision)
        else:
            decision.student_id = student.student_id
            decision.verdict = verdict
            decision.blockers_json = blockers
            decision.facts_json = facts
            decision.rule_version = RULE_VERSION
            decision.input_hash = digest
            decision.evaluated_at = now
            decision.evaluated_by = actor_id
            decision.version = int(decision.version or 0) + 1
        db.flush()
        result.update({"decisionId": str(decision.id), "evaluatedAt": _iso(now)})
    return result


def _scope_query(q, user):
    from app.core.affairs_security import student_directory_scope
    class_ids, student_ids = student_directory_scope(user or get_current_user_ctx() or {})
    if student_ids is not None:
        return q.where(OrientationStudent.student_id.in_(student_ids) if student_ids else false())
    if class_ids is not None:
        if not class_ids:
            return q.where(false())
        return q.where(OrientationStudent.student_id.in_(select(StudentProfile.id).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
            StudentProfile.class_id.in_(class_ids),
        )))
    return q


def list_qualifications(page: int, page_size: int, *, keyword=None, verdict=None, user=None):
    with session() as db:
        q = select(OrientationStudent).where(
            OrientationStudent.tenant_id == _tid(),
            OrientationStudent.is_deleted.is_(False),
            OrientationStudent.record_status == "ACTIVE",
        )
        q = _scope_query(q, user)
        if keyword:
            value = f"%{str(keyword).strip()}%"
            q = q.where(
                (OrientationStudent.name.like(value)) | (OrientationStudent.admission_no.like(value))
            )
        rows = list(db.scalars(q.order_by(OrientationStudent.id)).all())
        items = []
        for row in rows:
            decision = evaluate(db, row)
            if verdict and decision["verdict"] != str(verdict).upper():
                continue
            profile = db.get(StudentProfile, int(row.student_id)) if row.student_id else None
            items.append({
                "id": str(row.id), "name": row.name, "admissionNo": row.admission_no,
                "className": row.class_name or "", "reportStatus": row.report_status,
                "stage": row.stage, "version": int(row.version or 0),
                "profileStudentId": str(row.student_id or ""),
                "studentNo": profile.student_no if profile else (row.student_no or ""),
                "canFinalize": decision["verdict"] == "QUALIFIED" and row.report_status == "CHECKED_IN",
                **decision,
            })
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def qualification_detail(student_id, *, user=None, recalculate=False):
    from app.services.orientation_service import assert_orientation_student_scope
    with session() as db:
        student = db.get(OrientationStudent, int(student_id))
        if not student or student.is_deleted or int(student.tenant_id) != int(_tid()):
            raise not_found("新生记录不存在")
        assert_orientation_student_scope(db, student, user)
        result = evaluate(db, student, persist=bool(recalculate), actor_id=_actor_id(user))
        if recalculate:
            db.commit()
        return result


def sync_payment(student_id, body: dict, *, user=None) -> dict:
    from app.services.orientation_service import _audit, assert_orientation_student_scope
    status = str((body or {}).get("status") or "").upper()
    if status not in {"UNPAID", "PARTIAL", "PAID", "WAIVED", "DEFERRED"}:
        raise AppException("VALIDATION_ERROR", "缴费状态不合法")
    try:
        payable = Decimal(str((body or {}).get("payableAmount", 0)))
        paid = Decimal(str((body or {}).get("paidAmount", 0)))
        expected = int((body or {}).get("expectedVersion"))
    except (TypeError, ValueError, ArithmeticError):
        raise AppException("VALIDATION_ERROR", "金额或 expectedVersion 不合法")
    if payable < 0 or paid < 0 or (status == "PAID" and paid < payable):
        raise AppException("VALIDATION_ERROR", "缴费金额与状态不一致")
    source_type = str((body or {}).get("sourceType") or "MANUAL_VERIFIED").upper()
    if source_type not in {"FINANCE_SYNC", "MANUAL_VERIFIED"}:
        raise AppException("VALIDATION_ERROR", "缴费来源不合法")
    source_biz_id = str((body or {}).get("sourceBizId") or "").strip()
    if len(source_biz_id) < 3:
        raise AppException("VALIDATION_ERROR", "sourceBizId 必填")
    with session() as db:
        student = db.scalars(select(OrientationStudent).where(
            OrientationStudent.tenant_id == _tid(), OrientationStudent.id == int(student_id),
            OrientationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        if not student:
            raise not_found("新生记录不存在")
        assert_orientation_student_scope(db, student, user)
        account = db.scalars(select(OrientationPaymentAccount).where(
            OrientationPaymentAccount.tenant_id == _tid(),
            OrientationPaymentAccount.orientation_student_id == student.id,
            OrientationPaymentAccount.is_deleted.is_(False),
        ).with_for_update()).first()
        if not account:
            raise AppException("DATA_CONFLICT", "缴费 Authority 缺失，禁止回退写 OrientationStudent")
        if int(account.version or 0) != expected:
            raise AppException("APPROVAL_VERSION_CONFLICT", "缴费数据已变化，请刷新后重试")
        duplicate = db.scalars(select(OrientationPaymentAccount.id).where(
            OrientationPaymentAccount.tenant_id == _tid(),
            OrientationPaymentAccount.source_type == source_type,
            OrientationPaymentAccount.source_biz_id == source_biz_id,
            OrientationPaymentAccount.id != account.id,
        )).first()
        if duplicate:
            raise AppException("IDEMPOTENCY_CONFLICT", "该缴费来源流水已用于其他新生")
        before = account.status
        account.payable_amount = payable
        account.paid_amount = paid
        account.status = status
        account.source_type = source_type
        account.source_biz_id = source_biz_id
        account.synced_at = datetime.utcnow()
        account.verified_by = _actor_id(user)
        account.version = expected + 1
        student.payable_amount = payable
        student.paid_amount = paid
        student.payment_status = status
        student.version = int(student.version or 0) + 1
        decision = evaluate(db, student, persist=True, actor_id=_actor_id(user))
        _audit(db, "PAYMENT", student.id, "同步缴费事实", source_biz_id, before, status)
        db.commit()
        return {
            "id": str(account.id), "studentId": str(student.id), "status": status,
            "payableAmount": _money(payable), "paidAmount": _money(paid),
            "version": account.version, "qualification": decision,
        }
