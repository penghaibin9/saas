"""统一合规评估：规则/事实/证据分离；NOT_APPLICABLE 不计缺失。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import (
    InternshipAgreement, InternshipBatch, InternshipComplianceExemption, InternshipConsent,
    InternshipEmergencyPlan, InternshipInsurance, InternshipPosition, InternshipRecord,
    InternshipSafetyCompletion, InternshipSpecialFiling, StudentProfile,
)
from app.modules.internship.services.internship_compliance_rules import (
    get_batch_compliance_rules, rule_version_label,
)
from app.modules.internship.services.internship_enterprise_inspection_service import (
    is_enterprise_access_valid,
)
from app.modules.internship.services.internship_position_rights import evaluate_position_compliance
from app.services.db_service import _as_id, _tid, session


def _pick(rows, statuses):
    for row in rows:
        if row.status in statuses:
            valid_until = getattr(row, "valid_until", None)
            if valid_until and valid_until < datetime.utcnow():
                continue
            return row
    return None


def _item(code, cfg, status, reason="", evidence=None, route=""):
    required = bool(cfg.get("required"))
    applicable = status != "NOT_APPLICABLE"
    return {
        "code": code,
        "label": cfg.get("label", code),
        "applicable": applicable,
        "required": required and applicable,
        "severity": cfg.get("severity", "WARN"),
        "status": status,
        "evidenceId": str(evidence) if evidence else None,
        "evidenceVersion": None,
        "reason": reason,
        "route": route,
    }


def evaluate_internship_compliance(internship_id, operation="ONBOARD", user=None):
    with session() as db:
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        rec = assert_internship_record_scope(db, internship_id, user, "合规评估")
        batch = db.get(InternshipBatch, rec.batch_id) if rec.batch_id else None
        rules = get_batch_compliance_rules(db, batch)
        version = rule_version_label(batch)
        stu = db.get(StudentProfile, rec.student_id)
        items = []

        def apply_exemption(code, status, reason, evidence):
            ex = db.scalars(select(InternshipComplianceExemption).where(
                InternshipComplianceExemption.tenant_id == _tid(),
                InternshipComplianceExemption.internship_id == rec.id,
                InternshipComplianceExemption.check_code == code,
                InternshipComplianceExemption.status == "ACTIVE",
                InternshipComplianceExemption.is_deleted.is_(False),
            )).first()
            if ex and (not ex.valid_until or ex.valid_until >= datetime.utcnow()):
                return "VALID", "已获有效豁免", ex.id
            return status, reason, evidence

        # 1 企业准入
        cfg = rules["enterpriseAccess"]
        if not rec.enterprise_id:
            status, reason, evid = ("NOT_APPLICABLE", "尚未落实企业", None) if operation != "ONBOARD" else (
                "MISSING", "尚未落实企业/岗位", None)
        else:
            ok, reason = is_enterprise_access_valid(db, rec.enterprise_id, rules)
            status, reason, evid = (("VALID", "", None) if ok else ("MISSING", reason or "企业准入无效", None))
        status, reason, evid = apply_exemption("enterpriseAccess", status, reason, evid)
        items.append(_item("enterpriseAccess", cfg, status, reason, evid, "/admin/internship/compliance"))

        # 2 学生知情（required 为总开关；requireStudentConsent 仅在 required=True 时细化）
        cfg = rules["studentConsent"]
        if not cfg.get("required"):
            items.append(_item("studentConsent", cfg, "NOT_APPLICABLE", "规则未要求"))
        else:
            rows = db.scalars(select(InternshipConsent).where(
                InternshipConsent.tenant_id == _tid(), InternshipConsent.internship_id == rec.id,
                InternshipConsent.consent_type == "STUDENT", InternshipConsent.is_deleted.is_(False),
            )).all()
            hit = _pick(rows, ("VALID",))
            na = next((x for x in rows if x.status == "NOT_APPLICABLE"), None)
            if na and not cfg.get("required"):
                status, reason, evid = "NOT_APPLICABLE", "不适用", na.id
            elif hit:
                status, reason, evid = "VALID", "", hit.id
            elif any(x.status == "PENDING" for x in rows):
                status, reason, evid = "PENDING", "待确认", None
            else:
                status, reason, evid = "MISSING", "缺少学生知情确认", None
            status, reason, evid = apply_exemption("studentConsent", status, reason, evid)
            items.append(_item("studentConsent", cfg, status, reason, evid))

        # 3 监护人知情
        cfg = rules.get("guardianConsent") or {
            "label": "监护人知情确认", "required": False, "severity": "BLOCK"}
        need_guardian = bool((rules.get("studentConsent") or {}).get("requireGuardianConsentForMinor"))
        birth = getattr(stu, "birth_date", None) if stu else None
        if not need_guardian:
            items.append(_item("guardianConsent", cfg, "NOT_APPLICABLE", "规则未要求监护人确认"))
        elif birth is None:
            # 无可靠出生日期：不自动猜测；待核实时不算 VALID
            gcfg = {**cfg, "required": bool(cfg.get("required") or need_guardian)}
            status, reason, evid = "PENDING", "出生日期待核实，暂无法判定是否需监护人确认", None
            status, reason, evid = apply_exemption("guardianConsent", status, reason, evid)
            items.append(_item("guardianConsent", gcfg, status, reason, evid))
        else:
            # 简化：满 18 不适用；未满适用
            age_years = (datetime.utcnow().date() - birth).days / 365.25 if hasattr(birth, "year") else 99
            if hasattr(birth, "year") is False and isinstance(birth, datetime):
                age_years = (datetime.utcnow() - birth).days / 365.25
            elif isinstance(birth, datetime):
                age_years = (datetime.utcnow() - birth).days / 365.25
            else:
                try:
                    age_years = (datetime.utcnow().date() - birth).days / 365.25
                except Exception:
                    age_years = 99
            gcfg = {**cfg, "required": True}
            if age_years >= 18:
                items.append(_item("guardianConsent", gcfg, "NOT_APPLICABLE", "已成年"))
            else:
                rows = db.scalars(select(InternshipConsent).where(
                    InternshipConsent.tenant_id == _tid(), InternshipConsent.internship_id == rec.id,
                    InternshipConsent.consent_type == "GUARDIAN", InternshipConsent.is_deleted.is_(False),
                )).all()
                hit = _pick(rows, ("VALID",))
                status, reason, evid = (("VALID", "", hit.id) if hit else ("MISSING", "未成年须监护人确认", None))
                status, reason, evid = apply_exemption("guardianConsent", status, reason, evid)
                items.append(_item("guardianConsent", gcfg, status, reason, evid))

        # 4 安全教育
        cfg = rules["safetyEducation"]
        if not cfg.get("required"):
            items.append(_item("safetyEducation", cfg, "NOT_APPLICABLE", "规则未要求"))
        else:
            rows = db.scalars(select(InternshipSafetyCompletion).where(
                InternshipSafetyCompletion.tenant_id == _tid(),
                InternshipSafetyCompletion.internship_id == rec.id,
                InternshipSafetyCompletion.is_deleted.is_(False),
            )).all()
            hit = _pick(rows, ("PASSED",)) or next((x for x in rows if x.passed and x.commitment_confirmed), None)
            if hit:
                status, reason, evid = "VALID", "", hit.id
            elif any(x.status == "PENDING" for x in rows):
                status, reason, evid = "PENDING", "安全教育待完成/待审", None
            else:
                status, reason, evid = "MISSING", "安全教育未通过", None
            status, reason, evid = apply_exemption("safetyEducation", status, reason, evid)
            items.append(_item("safetyEducation", cfg, status, reason, evid))

        # 5 保险
        cfg = rules["insurance"]
        rows = db.scalars(select(InternshipInsurance).where(
            InternshipInsurance.tenant_id == _tid(), InternshipInsurance.internship_id == rec.id,
            InternshipInsurance.is_deleted.is_(False),
        )).all()
        hit = _pick(rows, ("VERIFIED",))
        if not cfg.get("required"):
            items.append(_item("insurance", cfg, "NOT_APPLICABLE" if not hit else "VALID",
                               "" if hit else "规则未强制", getattr(hit, "id", None)))
        else:
            status, reason, evid = (("VALID", "", hit.id) if hit else ("MISSING", "实习保险未核验", None))
            status, reason, evid = apply_exemption("insurance", status, reason, evid)
            items.append(_item("insurance", cfg, status, reason, evid))

        # 6 协议
        cfg = rules["agreement"]
        rows = db.scalars(select(InternshipAgreement).where(
            InternshipAgreement.tenant_id == _tid(), InternshipAgreement.internship_id == rec.id,
            InternshipAgreement.is_deleted.is_(False),
        )).all()
        hit = _pick(rows, ("EFFECTIVE", "ARCHIVED"))
        if not cfg.get("required"):
            items.append(_item("agreement", cfg, "NOT_APPLICABLE" if not hit else "VALID",
                               "" if hit else "规则未强制", getattr(hit, "id", None)))
        else:
            status, reason, evid = (("VALID", "", hit.id) if hit else ("MISSING", "三方协议未生效", None))
            status, reason, evid = apply_exemption("agreement", status, reason, evid)
            items.append(_item("agreement", cfg, status, reason, evid))

        # 7 特殊备案
        cfg = rules["specialFiling"]
        from app.modules.internship.services.internship_special_filing_service import evaluate_triggers
        pos = db.get(InternshipPosition, rec.position_id) if rec.position_id else None
        trigger_tuples = evaluate_triggers(pos, stu, None) if cfg.get("required") else []
        triggers = [t[0] for t in trigger_tuples]
        filings = db.scalars(select(InternshipSpecialFiling).where(
            InternshipSpecialFiling.tenant_id == _tid(),
            InternshipSpecialFiling.internship_id == rec.id,
            InternshipSpecialFiling.is_deleted.is_(False),
        )).all()
        if not cfg.get("required") or not triggers:
            na = next((x for x in filings if x.status in ("NOT_REQUIRED", "NOT_APPLICABLE")), None)
            items.append(_item("specialFiling", cfg, "NOT_APPLICABLE",
                               "无需特殊备案" if not triggers else "规则未要求",
                               getattr(na, "id", None)))
        else:
            hit = _pick(filings, ("APPROVED",))
            if hit:
                status, reason, evid = "VALID", "", hit.id
            elif any(str(x.status).startswith("PENDING") for x in filings):
                status, reason, evid = "PENDING", "特殊备案审批中", None
            else:
                labels = [t[1] for t in trigger_tuples]
                status, reason, evid = "MISSING", "特殊场景须备案：" + ",".join(labels), None
            status, reason, evid = apply_exemption("specialFiling", status, reason, evid)
            items.append(_item("specialFiling", cfg, status, reason, evid))

        # 8 岗位权益
        cfg = rules["workRights"]
        if not cfg.get("required") or not pos:
            items.append(_item("workRights", cfg,
                               "NOT_APPLICABLE" if not pos or not cfg.get("required") else "MISSING",
                               "未分配岗位" if not pos else "规则未要求"))
        else:
            rights = evaluate_position_compliance(pos, stu, rules)
            status = "VALID" if rights.get("passed") else "REJECTED"
            reason = "；".join(rights.get("blockers") or [])
            status, reason, evid = apply_exemption("workRights", status, reason, None)
            items.append(_item("workRights", cfg, status, reason, evid))

        # 9 应急预案
        cfg = rules["emergency"]
        if not cfg.get("required") or not rec.enterprise_id:
            items.append(_item("emergency", cfg, "NOT_APPLICABLE",
                               "规则未要求或未落实企业"))
        else:
            plans = db.scalars(select(InternshipEmergencyPlan).where(
                InternshipEmergencyPlan.tenant_id == _tid(),
                InternshipEmergencyPlan.company_id == rec.enterprise_id,
                InternshipEmergencyPlan.is_deleted.is_(False),
            )).all()
            hit = _pick(plans, ("APPROVED",))
            status, reason, evid = (("VALID", "", hit.id) if hit else ("MISSING", "缺少有效应急预案", None))
            status, reason, evid = apply_exemption("emergency", status, reason, evid)
            items.append(_item("emergency", cfg, status, reason, evid))

        # 10 指导教师
        cfg = rules.get("advisor") or {"label": "校内指导教师", "required": True, "severity": "BLOCK"}
        if not cfg.get("required"):
            items.append(_item("advisor", cfg, "NOT_APPLICABLE", "规则未要求"))
        else:
            ok = bool(rec.advisor_user_id or (rec.advisor_name or "").strip())
            status, reason, evid = (("VALID", "", None) if ok else ("MISSING", "未分配校内指导教师", None))
            status, reason, evid = apply_exemption("advisor", status, reason, evid)
            items.append(_item("advisor", cfg, status, reason, evid))

        blockers = [
            x for x in items
            if x["required"] and x["applicable"] and x["severity"] == "BLOCK"
            and x["status"] not in ("VALID", "NOT_APPLICABLE")
        ]
        warnings = [
            x for x in items
            if x["applicable"] and x["status"] not in ("VALID", "NOT_APPLICABLE") and x not in blockers
        ]
        applicable = [x for x in items if x["applicable"] and x["required"]]
        done = [x for x in applicable if x["status"] == "VALID"]
        return {
            "passed": not blockers,
            "score": None,
            "completeness": {
                "done": len(done),
                "applicable": len(applicable),
                "ratio": round(len(done) / len(applicable), 4) if applicable else 1.0,
            },
            "blockers": blockers,
            "warnings": warnings,
            "items": items,
            "ruleVersion": version,
            "evaluatedAt": datetime.utcnow().isoformat() + "Z",
            "operation": operation,
        }


def grant_exemption(body, user=None):
    b = body or {}
    reason = (b.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "豁免原因不少于 5 字")
    if not b.get("checkCode") or not b.get("internshipId"):
        raise AppException("VALIDATION_ERROR", "缺少 internshipId/checkCode")
    from app.modules.internship.services.internship_version import extract_expected_version
    # expectedVersion on internship record optional for exemption create
    with session() as db:
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        rec = assert_internship_record_scope(db, b["internshipId"], user, "合规豁免")
        if b.get("expectedVersion") is not None:
            extract_expected_version(b)
        from app.models import InternshipComplianceExemption, InternshipAuditTrail
        x = InternshipComplianceExemption(
            tenant_id=_tid(), internship_id=rec.id, batch_id=rec.batch_id,
            check_code=b["checkCode"], reason=reason,
            evidence_file_ids=b.get("evidenceFileIds") or b.get("fileIds"),
            valid_from=datetime.utcnow(),
            valid_until=None,
            status="ACTIVE",
            approved_by_name=(user or {}).get("realName") or "系统",
            approved_at=datetime.utcnow(),
            rule_version=rule_version_label(db.get(InternshipBatch, rec.batch_id) if rec.batch_id else None),
        )
        if b.get("validUntil"):
            raw = b["validUntil"]
            x.valid_until = datetime.fromisoformat(str(raw).replace("Z", "")) if isinstance(raw, str) else raw
        db.add(x)
        db.add(InternshipAuditTrail(
            tenant_id=_tid(), target_id=rec.id, target_type="COMPLIANCE_EXEMPT",
            action="GRANT", operator_name=(user or {}).get("realName") or "系统",
            detail_json={"checkCode": b["checkCode"], "reason": reason},
            occurred_at=datetime.utcnow()))
        db.commit()
        return {"id": str(x.id), "status": x.status, "checkCode": x.check_code, "version": int(x.version or 0)}


def batch_compliance_stats(batch_id, user=None):
    with session() as db:
        rows = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == _as_id(batch_id),
            InternshipRecord.is_deleted.is_(False),
        )).all()
        from app.modules.internship.services.internship_student_service import _current_scope, _rec_in_scope
        scope = _current_scope(user)
        ids = [r.id for r in rows if _rec_in_scope(
            scope, db, r, db.get(StudentProfile, r.student_id))]
    results = [evaluate_internship_compliance(i, "BATCH_CLOSE", user) for i in ids]
    blocked_ids = [str(i) for i, r in zip(ids, results) if not r["passed"]]
    missing = {}
    for r in results:
        for it in r["blockers"]:
            missing[it["code"]] = missing.get(it["code"], 0) + 1
    return {
        "batchId": str(batch_id),
        "total": len(results),
        "canOnboard": sum(1 for x in results if x["passed"]),
        "blocked": len(blocked_ids),
        "blockedInternshipIds": blocked_ids[:100],
        "missingByCode": missing,
        "ruleVersion": results[0]["ruleVersion"] if results else None,
    }


def list_batch_compliance_summary(batch_id, user=None):
    return batch_compliance_stats(batch_id, user)
