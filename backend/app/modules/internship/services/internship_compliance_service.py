"""统一合规评估：规则/事实/证据分离；NOT_APPLICABLE 不计缺失。"""
from __future__ import annotations

from datetime import datetime
from contextlib import nullcontext

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.models import (
    InternshipAgreement, InternshipBatch, InternshipComplianceExemption, InternshipConsent,
    InternshipEmergencyPlan, InternshipInsurance, InternshipPosition, InternshipRecord,
    InternshipSafetyCompletion, InternshipSpecialFiling, InternshipIncident,
    StudentProfile, EmpCompany, RiskRecord, InternshipEnterpriseEval,
    InternshipStudentEval, InternshipFinalScore,
)
from app.modules.internship.services.internship_compliance_rules import (
    get_batch_compliance_rules, rule_version_label,
)
from app.modules.internship.services.internship_enterprise_inspection_service import (
    is_enterprise_access_valid,
)
from app.modules.internship.services.internship_position_rights import evaluate_position_publishability
from app.services.db_service import _as_id, _tid, session


def _pick(rows, statuses):
    for row in rows:
        if row.status in statuses:
            valid_until = getattr(row, "valid_until", None)
            if valid_until and valid_until < datetime.utcnow():
                continue
            return row
    return None


def _item(code, cfg, status, reason="", evidence=None, route="", evidence_version=None):
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
        "evidenceVersion": evidence_version,
        "reason": reason,
        "route": route,
    }


def evaluate_internship_compliance(internship_id, operation="ONBOARD", user=None, db=None):
    operation = str(operation or "").upper()
    allowed = {"ONBOARD", "CONTINUE", "ASSESS", "ARCHIVE", "BATCH_CLOSE"}
    if operation not in allowed:
        raise AppException("VALIDATION_ERROR", "operation 必须为 ONBOARD/CONTINUE/ASSESS/ARCHIVE/BATCH_CLOSE")
    with (session() if db is None else nullcontext(db)) as db:
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
                InternshipComplianceExemption.status == "APPROVED",
                InternshipComplianceExemption.is_deleted.is_(False),
            )).first()
            if ex and (not ex.valid_until or ex.valid_until >= datetime.utcnow()):
                return "EXEMPTED", "已获有效豁免", ex.id
            return status, reason, evidence

        base_cfg = {"required": True, "severity": "BLOCK"}
        items.append(_item(
            "eligibility", {**base_cfg, "label": "实习资格"},
            "VALID" if rec.eligibility_status == "QUALIFIED" else "MISSING",
            "" if rec.eligibility_status == "QUALIFIED" else "实习资格未认定合格"))
        items.append(_item(
            "enterprise", {**base_cfg, "label": "实习企业"},
            "VALID" if rec.enterprise_id else "MISSING",
            "" if rec.enterprise_id else "未落实实习企业"))
        items.append(_item(
            "position", {**base_cfg, "label": "实习岗位"},
            "VALID" if rec.position_id else "MISSING",
            "" if rec.position_id else "未分配实习岗位"))

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
            company = db.get(EmpCompany, pos.company_id) if pos else None
            rights = evaluate_position_publishability(
                pos, company, batch, stu, operation=operation, db=db)
            status = "VALID" if rights.get("passed") else "REJECTED"
            reason = "；".join(
                x["reason"] for x in
                (rights.get("blockers") or []) + (rights.get("unknowns") or []))
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

        quantities = None
        if operation in ("ASSESS", "ARCHIVE", "BATCH_CLOSE"):
            from app.modules.internship.services.internship_compliance_facts import (
                material_quantity_facts)
            quantities = material_quantity_facts(db, rec, batch)
            for code, label in (
                ("weekly", "周报要求"), ("checkin", "打卡要求"),
                ("guidance", "指导次数"), ("visit", "巡访次数"),
            ):
                fact = quantities[code]
                items.append(_item(
                    code, {"label": label, "required": True, "severity": "BLOCK"},
                    fact["status"],
                    "" if fact["status"] == "VALID"
                    else f"应有 {fact['expected']}，有效 {fact['actual']}，缺 {fact['missing']}"))
            open_incidents = int(db.scalar(select(func.count()).select_from(InternshipIncident).where(
                InternshipIncident.tenant_id == _tid(),
                InternshipIncident.internship_id == rec.id,
                InternshipIncident.status != "CLOSED",
                InternshipIncident.is_deleted.is_(False))) or 0)
            items.append(_item(
                "openIncident", {"label": "开放事故", "required": True, "severity": "BLOCK"},
                "VALID" if open_incidents == 0 else "MISSING",
                "" if open_incidents == 0 else f"存在 {open_incidents} 个未关闭事故"))
            open_high = int(db.scalar(select(func.count()).select_from(RiskRecord).where(
                RiskRecord.tenant_id == _tid(), RiskRecord.internship_id == rec.id,
                RiskRecord.risk_level == "HIGH",
                RiskRecord.status.in_(("PENDING_HANDLE", "PROCESSING")),
                RiskRecord.is_deleted.is_(False))) or 0)
            items.append(_item(
                "openHighRisk", {"label": "开放高风险", "required": True, "severity": "BLOCK"},
                "VALID" if open_high == 0 else "MISSING",
                "" if open_high == 0 else f"存在 {open_high} 个开放高风险"))
        if operation in ("ARCHIVE", "BATCH_CLOSE"):
            checks = (
                ("enterpriseEval", "企业评价", InternshipEnterpriseEval,
                 InternshipEnterpriseEval.school_review_status == "APPROVED"),
                ("studentEval", "学生自评", InternshipStudentEval,
                 InternshipStudentEval.submit_status == "SUBMITTED"),
                ("score", "实习成绩", InternshipFinalScore,
                 InternshipFinalScore.status == "PUBLISHED"),
            )
            for code, label, model, condition in checks:
                count = int(db.scalar(select(func.count()).select_from(model).where(
                    model.tenant_id == _tid(), model.internship_id == rec.id,
                    condition, model.is_deleted.is_(False))) or 0)
                items.append(_item(
                    code, {"label": label, "required": True, "severity": "BLOCK"},
                    "VALID" if count else "MISSING", "" if count else f"缺少{label}"))

        blockers = [
            x for x in items
            if x["required"] and x["applicable"] and x["severity"] == "BLOCK"
            and x["status"] not in ("VALID", "EXEMPTED", "NOT_APPLICABLE")
        ]
        warnings = [
            x for x in items
            if x["applicable"] and x["status"] not in ("VALID", "EXEMPTED", "NOT_APPLICABLE") and x not in blockers
        ]
        applicable = [x for x in items if x["applicable"] and x["required"]]
        done = [x for x in applicable if x["status"] in ("VALID", "EXEMPTED")]
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
            "quantityFacts": quantities,
        }


def grant_exemption(body, user=None):
    b = body or {}
    reason = (b.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "豁免原因不少于 5 字")
    if not b.get("checkCode") or not b.get("internshipId"):
        raise AppException("VALIDATION_ERROR", "缺少 internshipId/checkCode")
    from app.modules.internship.services.internship_version import extract_expected_version
    if not b.get("validUntil"):
        raise AppException("VALIDATION_ERROR", "豁免必须设置有效期")
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
            valid_until=None, status="PENDING_REVIEW",
            requested_by_name=(user or {}).get("realName") or "系统",
            requested_by_user_id=str((user or {}).get("userId") or ""),
            rule_version=rule_version_label(db.get(InternshipBatch, rec.batch_id) if rec.batch_id else None),
        )
        if b.get("validUntil"):
            raw = b["validUntil"]
            x.valid_until = datetime.fromisoformat(str(raw).replace("Z", "")) if isinstance(raw, str) else raw
        db.add(x)
        if x.valid_until <= datetime.utcnow():
            raise AppException("VALIDATION_ERROR", "豁免有效期必须晚于当前时间")
        db.add(InternshipAuditTrail(
            tenant_id=_tid(), target_id=rec.id, target_type="COMPLIANCE_EXEMPT",
            action="REQUEST", operator_name=(user or {}).get("realName") or "系统",
            detail_json={"checkCode": b["checkCode"], "reason": reason},
            occurred_at=datetime.utcnow()))
        db.commit()
        return {"id": str(x.id), "status": x.status, "checkCode": x.check_code, "version": int(x.version or 0)}


def review_exemption(exemption_id, body, user=None):
    from app.core.permissions import enforce_permission, is_super_admin
    from app.models import InternshipAuditTrail
    enforce_permission(user or {}, "internship.compliance.exempt.approve")
    role = ((user or {}).get("currentRoleCode") or "").upper()
    if role != "SCHOOL_ADMIN" and not is_super_admin(user or {}):
        from app.core.exceptions import no_permission
        raise no_permission("仅学校管理员可批准合规豁免")
    b = body or {}
    action = (b.get("action") or "").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须为 APPROVE/REJECT")
    with session() as db:
        x = db.scalar(select(InternshipComplianceExemption).where(
            InternshipComplianceExemption.id == _as_id(exemption_id),
            InternshipComplianceExemption.tenant_id == _tid(),
            InternshipComplianceExemption.is_deleted.is_(False)).with_for_update())
        if not x:
            raise not_found("合规豁免不存在")
        if b.get("expectedVersion") is None or int(b["expectedVersion"]) != int(x.version or 0):
            raise AppException("DATA_CONFLICT", "豁免申请版本已变化")
        if x.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅待审核豁免可处理")
        if action == "APPROVE":
            if not x.valid_until or x.valid_until <= datetime.utcnow():
                raise AppException("DATA_CONFLICT", "豁免有效期无效")
            if not x.evidence_file_ids:
                raise AppException("VALIDATION_ERROR", "BLOCK级豁免批准必须绑定依据文件")
            x.status = "APPROVED"
            x.approved_by_name = (user or {}).get("realName") or "系统"
            x.approved_at = datetime.utcnow()
        else:
            x.status = "REJECTED"
        x.reviewed_by_name = (user or {}).get("realName") or "系统"
        x.reviewed_at = datetime.utcnow()
        x.version = int(x.version or 0) + 1
        db.add(InternshipAuditTrail(
            tenant_id=_tid(), target_id=x.internship_id, target_type="COMPLIANCE_EXEMPT",
            action=action, operator_name=x.reviewed_by_name,
            detail_json={"exemptionId": str(x.id), "checkCode": x.check_code,
                         "comment": b.get("comment") or ""},
            occurred_at=datetime.utcnow()))
        db.commit()
        return {"id": str(x.id), "status": x.status, "version": x.version}


def batch_compliance_stats(batch_id, user=None):
    with session() as db:
        from app.modules.internship.services.internship_scope import apply_internship_record_scope
        query = select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == _as_id(batch_id),
            InternshipRecord.is_deleted.is_(False),
        )
        rows = db.scalars(apply_internship_record_scope(query, user)).all()
        evaluated_at = datetime.utcnow().isoformat() + "Z"
        entries, by_code = [], {}
        for rec in rows:
            onboard = evaluate_internship_compliance(rec.id, "ONBOARD", user=user, db=db)
            archive = evaluate_internship_compliance(rec.id, "ARCHIVE", user=user, db=db)
            stu = db.get(StudentProfile, rec.student_id)
            codes = sorted({x["code"] for x in onboard["blockers"]})
            archive_codes = sorted({x["code"] for x in archive["blockers"]})
            entry = {
                "internshipId": str(rec.id), "studentId": str(rec.student_id),
                "studentNo": stu.student_no if stu else "", "studentName": stu.real_name if stu else "",
                "classId": str(stu.class_id or "") if stu else "",
                "advisorName": rec.advisor_name or "", "recordStatus": rec.status,
                "onboardPassed": onboard["passed"], "archivePassed": archive["passed"],
                "blockerCodes": codes, "archiveBlockerCodes": archive_codes,
                "blockers": onboard["blockers"], "route": f"/admin/internship/students/{rec.id}",
            }
            entries.append(entry)
            for code in set(codes + archive_codes):
                by_code.setdefault(code, []).append(entry)
        labels = {
            "enterpriseAccess": "缺企业准入", "studentConsent": "缺学生知情",
            "guardianConsent": "缺监护人确认", "safetyEducation": "缺安全教育",
            "agreement": "缺协议", "insurance": "缺保险",
            "specialFiling": "缺特殊备案", "workRights": "岗位权益不合规",
            "emergency": "缺应急预案", "openIncident": "开放事故",
            "openHighRisk": "开放高风险",
        }
        metrics = [
            {"metricCode": "TOTAL", "metricLabel": "批次总人数", "count": len(entries),
             "drilldownFilter": "ALL"},
            {"metricCode": "ONBOARD_READY", "metricLabel": "可上岗",
             "count": sum(1 for x in entries if x["onboardPassed"]),
             "drilldownFilter": "ONBOARD_READY"},
            {"metricCode": "BLOCKED", "metricLabel": "被阻断",
             "count": sum(1 for x in entries if not x["onboardPassed"]),
             "drilldownFilter": "BLOCKED"},
        ]
        metrics.extend({
            "metricCode": code, "metricLabel": label, "count": len(by_code.get(code, [])),
            "drilldownFilter": code,
        } for code, label in labels.items())
        metrics.extend([
            {"metricCode": "ARCHIVE_READY", "metricLabel": "可归档",
             "count": sum(1 for x in entries if x["archivePassed"]),
             "drilldownFilter": "ARCHIVE_READY"},
            {"metricCode": "ARCHIVE_BLOCKED", "metricLabel": "不可归档",
             "count": sum(1 for x in entries if not x["archivePassed"]),
             "drilldownFilter": "ARCHIVE_BLOCKED"},
        ])
        version = (evaluate_internship_compliance(
            rows[0].id, "ONBOARD", user=user, db=db)["ruleVersion"] if rows else None)
        for metric in metrics:
            metric["ruleVersion"] = version
            metric["evaluatedAt"] = evaluated_at
        drilldowns = {
            "ALL": entries,
            "ONBOARD_READY": [x for x in entries if x["onboardPassed"]],
            "BLOCKED": [x for x in entries if not x["onboardPassed"]],
            "ARCHIVE_READY": [x for x in entries if x["archivePassed"]],
            "ARCHIVE_BLOCKED": [x for x in entries if not x["archivePassed"]],
            **by_code,
        }
        return {
            "batchId": str(batch_id), "total": len(entries),
            "metrics": metrics, "drilldowns": drilldowns,
            "missingByCode": {code: len(values) for code, values in by_code.items()},
            "ruleVersion": version, "evaluatedAt": evaluated_at,
        }


def _workflow_counts(batch_id, scoped_ids, user=None):
    ids = scoped_ids or [0]
    with session() as db:
        return {
            "studentConsentPending": int(db.scalar(select(func.count()).select_from(
                InternshipConsent).where(
                InternshipConsent.tenant_id == _tid(),
                InternshipConsent.internship_id.in_(ids),
                InternshipConsent.consent_type == "STUDENT",
                InternshipConsent.status == "PENDING",
                InternshipConsent.is_deleted.is_(False))) or 0),
            "guardianConsentPending": int(db.scalar(select(func.count()).select_from(
                InternshipConsent).where(
                InternshipConsent.tenant_id == _tid(),
                InternshipConsent.internship_id.in_(ids),
                InternshipConsent.consent_type == "GUARDIAN",
                InternshipConsent.status == "PENDING",
                InternshipConsent.is_deleted.is_(False))) or 0),
            "safetyPending": int(db.scalar(select(func.count()).select_from(
                InternshipSafetyCompletion).where(
                InternshipSafetyCompletion.tenant_id == _tid(),
                InternshipSafetyCompletion.internship_id.in_(ids),
                InternshipSafetyCompletion.status.in_(("NOT_STARTED", "IN_PROGRESS", "PENDING_REVIEW", "FAILED")),
                InternshipSafetyCompletion.is_deleted.is_(False))) or 0),
            "exemptionPending": int(db.scalar(select(func.count()).select_from(
                InternshipComplianceExemption).where(
                InternshipComplianceExemption.tenant_id == _tid(),
                InternshipComplianceExemption.internship_id.in_(ids),
                InternshipComplianceExemption.status == "PENDING_REVIEW",
                InternshipComplianceExemption.is_deleted.is_(False))) or 0),
            "incidentPending": int(db.scalar(select(func.count()).select_from(
                InternshipIncident).where(
                InternshipIncident.tenant_id == _tid(),
                InternshipIncident.internship_id.in_(ids),
                InternshipIncident.status != "CLOSED",
                InternshipIncident.is_deleted.is_(False))) or 0),
        }


def list_batch_compliance_summary(batch_id, user=None):
    return batch_compliance_stats(batch_id, user)
