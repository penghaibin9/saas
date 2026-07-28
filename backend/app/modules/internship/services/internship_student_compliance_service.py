"""学生本人岗位实习合规事实源。

学生小程序与学生 PC 门户必须渲染本服务返回的结果，禁止各端自行拼装
“是否可上岗”。该服务不复用教师数据范围，而是严格解析当前登录学生本人
唯一实习记录；返回内容仅包含学生可见的状态、原因和下一步，不暴露监护人
令牌、内部审批意见或敏感企业材料。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException
from app.models import (
    EmpCompany,
    InternshipAgreement,
    InternshipBatch,
    InternshipComplianceExemption,
    InternshipConsent,
    InternshipEmergencyPlan,
    InternshipInsurance,
    InternshipPosition,
    InternshipSafetyCompletion,
    InternshipSafetyCourse,
    InternshipSpecialFiling,
)
from app.modules.internship.services.internship_compliance_rules import (
    get_batch_compliance_rules,
    rule_version_label,
)
from app.modules.internship.services.internship_enterprise_inspection_service import (
    is_enterprise_access_valid,
)
from app.modules.internship.services.internship_position_rights import (
    evaluate_position_publishability,
)
from app.modules.internship.services.internship_record_resolver import (
    resolve_student_internship_context,
)
from app.services.db_service import _tid, session

_ALLOWED_OPERATIONS = {"ONBOARD", "CONTINUE"}
_STATUS_LABEL = {
    "VALID": "已完成",
    "EXEMPTED": "已豁免",
    "NOT_APPLICABLE": "不适用",
    "PENDING": "办理中",
    "MISSING": "待完成",
    "REJECTED": "未通过",
    "CONFIG_ERROR": "学校待配置",
}


def _item(code, label, *, required, severity="BLOCK", status="MISSING", reason="", route="", detail=None):
    applicable = status != "NOT_APPLICABLE"
    return {
        "code": code,
        "label": label,
        "required": bool(required and applicable),
        "applicable": applicable,
        "severity": severity,
        "status": status,
        "statusLabel": _STATUS_LABEL.get(status, status),
        "reason": reason,
        "route": route,
        "detail": detail or {},
    }


def _latest(rows):
    return sorted(rows, key=lambda x: int(getattr(x, "id", 0) or 0), reverse=True)


def _valid_row(rows, statuses):
    now = datetime.utcnow()
    for row in _latest(rows):
        if getattr(row, "status", None) not in statuses:
            continue
        valid_until = getattr(row, "valid_until", None)
        if valid_until and valid_until < now:
            continue
        return row
    return None


def _completion_for_course(completions, course_id):
    rows = [x for x in completions if int(x.course_id) == int(course_id)]
    return _latest(rows)[0] if rows else None


def summarize_required_safety_courses(courses, completions, *, required: bool) -> dict:
    """按当前批次全部 ACTIVE 课程与同版本完成记录判定安全教育。

    这是跨端共同规则：任意一门通过不能代表全部通过；旧课程版本、缺少承诺、
    教师审核未通过或课程未配置都不能返回 VALID。
    """
    if not required:
        return {
            "status": "NOT_APPLICABLE", "reason": "当前批次规则未要求安全教育",
            "courses": [], "requiredCount": 0, "passedCount": 0,
        }
    active = [x for x in courses if getattr(x, "status", None) == "ACTIVE"
              and not bool(getattr(x, "is_deleted", False))]
    if not active:
        return {
            "status": "CONFIG_ERROR",
            "reason": "学校已要求安全教育，但当前批次尚未配置有效课程",
            "courses": [], "requiredCount": 0, "passedCount": 0,
        }
    details = []
    passed_count = 0
    has_pending = False
    for course in sorted(active, key=lambda x: int(getattr(x, "id", 0) or 0)):
        completion = _completion_for_course(completions, course.id)
        current_version = bool(
            completion and str(getattr(completion, "course_version", "") or "")
            == str(getattr(course, "course_version", "") or "")
        )
        commitment_ok = bool(
            not bool(getattr(course, "require_commitment", False))
            or (completion and bool(getattr(completion, "commitment_confirmed", False)))
        )
        passed = bool(
            completion
            and getattr(completion, "status", None) == "PASSED"
            and bool(getattr(completion, "passed", False))
            and current_version
            and commitment_ok
        )
        cstatus = getattr(completion, "status", None) if completion else "NOT_STARTED"
        if cstatus in ("IN_PROGRESS", "PENDING_REVIEW", "NOT_STARTED"):
            has_pending = True
        if passed:
            passed_count += 1
        reason = ""
        if not completion:
            reason = "尚未开始"
        elif not current_version:
            reason = "课程版本已更新，需重新学习"
        elif not commitment_ok:
            reason = "尚未确认安全承诺"
        elif cstatus == "PENDING_REVIEW":
            reason = "已提交，待教师审核"
        elif cstatus == "FAILED":
            reason = "审核未通过，需重新学习"
        elif not passed:
            reason = "尚未通过"
        details.append({
            "courseId": str(course.id),
            "title": getattr(course, "title", "安全教育课程"),
            "courseVersion": getattr(course, "course_version", ""),
            "completionId": str(completion.id) if completion else "",
            "completionVersion": int(getattr(completion, "version", 0) or 0) if completion else 0,
            "completionStatus": cstatus,
            "passed": passed,
            "currentVersion": current_version,
            "commitmentConfirmed": bool(completion and getattr(completion, "commitment_confirmed", False)),
            "reason": reason,
        })
    all_passed = passed_count == len(active)
    return {
        "status": "VALID" if all_passed else ("PENDING" if has_pending else "MISSING"),
        "reason": "" if all_passed else f"应完成 {len(active)} 门，已通过 {passed_count} 门",
        "courses": details,
        "requiredCount": len(active),
        "passedCount": passed_count,
    }


def _age_years(birth):
    if not birth:
        return None
    if isinstance(birth, str):
        try:
            birth = datetime.fromisoformat(birth[:10]).date()
        except ValueError:
            return None
    if isinstance(birth, datetime):
        birth = birth.date()
    try:
        today = datetime.utcnow().date()
        return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    except Exception:
        return None


def _apply_exemption(db, rec, code, status, reason):
    row = db.scalars(select(InternshipComplianceExemption).where(
        InternshipComplianceExemption.tenant_id == _tid(),
        InternshipComplianceExemption.internship_id == rec.id,
        InternshipComplianceExemption.check_code == code,
        InternshipComplianceExemption.status == "APPROVED",
        InternshipComplianceExemption.is_deleted.is_(False),
    ).order_by(InternshipComplianceExemption.id.desc())).first()
    if row and (not row.valid_until or row.valid_until >= datetime.utcnow()):
        return "EXEMPTED", "学校已批准有效豁免"
    return status, reason


def _resolve_my_context(db, user, batch_id=None):
    from app.services.mobile_student_service import _require_student, resolve_student
    student = resolve_student(db, _require_student(user))
    if not student:
        raise AppException("NO_PERMISSION", "无法解析当前登录学生身份")
    return resolve_student_internship_context(
        db, student=student, batch_id=batch_id, for_write=False)


def evaluate_my(user: dict, operation="ONBOARD", batch_id=None) -> dict:
    operation = str(operation or "ONBOARD").upper()
    if operation not in _ALLOWED_OPERATIONS:
        raise AppException("VALIDATION_ERROR", "operation 仅支持 ONBOARD/CONTINUE")
    with session() as db:
        ctx = _resolve_my_context(db, user, batch_id=batch_id)
        if ctx.mode == "need_select":
            return {
                "hasData": False, "needSelect": True, "candidates": ctx.candidates,
                "message": ctx.message, "operation": operation,
            }
        rec, student, batch = ctx.record, ctx.student, ctx.batch
        if not rec:
            return {
                "hasData": False, "needSelect": False, "message": ctx.message or "你暂无实习记录",
                "operation": operation,
            }
        if batch is None and rec.batch_id:
            batch = db.get(InternshipBatch, rec.batch_id)
        rules = get_batch_compliance_rules(db, batch)
        items = []

        items.append(_item(
            "eligibility", "实习资格", required=True,
            status="VALID" if rec.eligibility_status == "QUALIFIED" else "MISSING",
            reason="" if rec.eligibility_status == "QUALIFIED" else "学校尚未认定实习资格合格",
        ))
        items.append(_item(
            "enterprise", "实习企业", required=True,
            status="VALID" if rec.enterprise_id else "MISSING",
            reason="" if rec.enterprise_id else "尚未落实实习企业",
            route="/pages/student/internship/enterprises/index",
        ))
        items.append(_item(
            "position", "实习岗位", required=True,
            status="VALID" if rec.position_id else "MISSING",
            reason="" if rec.position_id else "尚未落实实习岗位",
            route="/pages/student/internship/application/index",
        ))
        items.append(_item(
            "advisor", "校内指导教师", required=bool(rules.get("advisor", {}).get("required", True)),
            severity=rules.get("advisor", {}).get("severity", "BLOCK"),
            status="VALID" if (rec.advisor_user_id or (rec.advisor_name or "").strip()) else "MISSING",
            reason="" if (rec.advisor_user_id or (rec.advisor_name or "").strip()) else "学校尚未分配校内指导教师",
        ))

        cfg = rules["enterpriseAccess"]
        if not cfg.get("required"):
            status, reason = "NOT_APPLICABLE", "当前批次规则未要求企业准入考察"
        elif not rec.enterprise_id:
            status, reason = "MISSING", "尚未落实企业，无法完成准入考察"
        else:
            ok, access_reason = is_enterprise_access_valid(db, rec.enterprise_id, rules)
            status, reason = ("VALID", "") if ok else ("MISSING", access_reason or "企业准入考察未通过")
        status, reason = _apply_exemption(db, rec, "enterpriseAccess", status, reason)
        items.append(_item(
            "enterpriseAccess", cfg.get("label", "企业准入考察"),
            required=bool(cfg.get("required")), severity=cfg.get("severity", "BLOCK"),
            status=status, reason=reason,
        ))

        consents = db.scalars(select(InternshipConsent).where(
            InternshipConsent.tenant_id == _tid(),
            InternshipConsent.internship_id == rec.id,
            InternshipConsent.is_deleted.is_(False),
        )).all()
        cfg = rules["studentConsent"]
        student_rows = [x for x in consents if x.consent_type == "STUDENT"]
        if not cfg.get("required"):
            status, reason = "NOT_APPLICABLE", "当前批次规则未要求学生知情确认"
        elif _valid_row(student_rows, {"VALID"}):
            status, reason = "VALID", ""
        elif any(x.status == "PENDING" for x in student_rows):
            status, reason = "PENDING", "知情书待本人阅读确认"
        elif any(x.status == "REJECTED" for x in student_rows):
            status, reason = "REJECTED", "本人已拒绝当前知情书，请联系指导教师"
        else:
            status, reason = "MISSING", "学校尚未下发知情确认任务"
        status, reason = _apply_exemption(db, rec, "studentConsent", status, reason)
        items.append(_item(
            "studentConsent", cfg.get("label", "学生知情确认"),
            required=bool(cfg.get("required")), severity=cfg.get("severity", "BLOCK"),
            status=status, reason=reason, route="/pages/student/internship/consent/index",
        ))

        gcfg = rules.get("guardianConsent") or {"label": "监护人知情确认", "required": False, "severity": "BLOCK"}
        need_guardian = bool(cfg.get("required") and cfg.get("requireGuardianConsentForMinor"))
        age = _age_years(getattr(student, "birth_date", None))
        guardian_rows = [x for x in consents if x.consent_type == "GUARDIAN"]
        if not need_guardian:
            status, reason, required = "NOT_APPLICABLE", "当前规则不要求监护人确认", False
        elif age is None:
            status, reason, required = "PENDING", "出生日期待学校核实，暂无法判断是否需要监护人确认", True
        elif age >= 18:
            status, reason, required = "NOT_APPLICABLE", "当前已成年", False
        elif _valid_row(guardian_rows, {"VALID"}):
            status, reason, required = "VALID", "", True
        elif any(x.status == "PENDING" for x in guardian_rows):
            status, reason, required = "PENDING", "等待已绑定监护人确认", True
        elif any(x.status == "REJECTED" for x in guardian_rows):
            status, reason, required = "REJECTED", "监护人已拒绝当前知情书，请联系学校", True
        else:
            status, reason, required = "MISSING", "未成年学生尚未完成监护人确认", True
        status, reason = _apply_exemption(db, rec, "guardianConsent", status, reason)
        items.append(_item(
            "guardianConsent", gcfg.get("label", "监护人知情确认"),
            required=required, severity=gcfg.get("severity", "BLOCK"),
            status=status, reason=reason, route="/pages/student/internship/consent/index",
        ))

        courses = db.scalars(select(InternshipSafetyCourse).where(
            InternshipSafetyCourse.tenant_id == _tid(),
            InternshipSafetyCourse.batch_id == rec.batch_id,
            InternshipSafetyCourse.is_deleted.is_(False),
        )).all()
        completions = db.scalars(select(InternshipSafetyCompletion).where(
            InternshipSafetyCompletion.tenant_id == _tid(),
            InternshipSafetyCompletion.internship_id == rec.id,
            InternshipSafetyCompletion.is_deleted.is_(False),
        )).all()
        scfg = rules["safetyEducation"]
        safety = summarize_required_safety_courses(
            courses, completions, required=bool(scfg.get("required")))
        status, reason = _apply_exemption(db, rec, "safetyEducation", safety["status"], safety["reason"])
        items.append(_item(
            "safetyEducation", scfg.get("label", "岗前安全教育"),
            required=bool(scfg.get("required")), severity=scfg.get("severity", "BLOCK"),
            status=status, reason=reason, route="/pages/student/internship/safety/index",
            detail={
                "requiredCount": safety["requiredCount"],
                "passedCount": safety["passedCount"],
                "courses": safety["courses"],
            },
        ))

        icfg = rules["insurance"]
        insurance_rows = db.scalars(select(InternshipInsurance).where(
            InternshipInsurance.tenant_id == _tid(),
            InternshipInsurance.internship_id == rec.id,
            InternshipInsurance.is_deleted.is_(False),
        )).all()
        insurance = _valid_row(insurance_rows, {"VERIFIED", "APPROVED", "EFFECTIVE", "VALID"})
        if not icfg.get("required"):
            status, reason = ("VALID", "") if insurance else ("NOT_APPLICABLE", "当前批次规则未强制保险")
        elif insurance:
            status, reason = "VALID", ""
        elif any(x.status in ("PENDING", "PENDING_VERIFY") for x in insurance_rows):
            status, reason = "PENDING", "保险材料已提交，待学校核验"
        else:
            status, reason = "MISSING", "请提交覆盖实习期的保险材料"
        status, reason = _apply_exemption(db, rec, "insurance", status, reason)
        items.append(_item(
            "insurance", icfg.get("label", "实习保险"),
            required=bool(icfg.get("required")), severity=icfg.get("severity", "BLOCK"),
            status=status, reason=reason, route="/pages/student/internship/insurance/index",
        ))

        acfg = rules["agreement"]
        agreements = db.scalars(select(InternshipAgreement).where(
            InternshipAgreement.tenant_id == _tid(),
            InternshipAgreement.internship_id == rec.id,
            InternshipAgreement.is_deleted.is_(False),
        )).all()
        agreement = _valid_row(agreements, {"EFFECTIVE", "ARCHIVED"})
        if not acfg.get("required"):
            status, reason = ("VALID", "") if agreement else ("NOT_APPLICABLE", "当前批次规则未强制三方协议")
        elif agreement:
            status, reason = "VALID", ""
        elif any(x.status in ("PENDING_STUDENT", "PENDING_ENTERPRISE", "PENDING_SCHOOL") for x in agreements):
            status, reason = "PENDING", "三方协议仍在确认流程中"
        elif any(x.status == "REJECTED" for x in agreements):
            status, reason = "REJECTED", "三方协议已被驳回，请修改后重新办理"
        else:
            status, reason = "MISSING", "三方协议尚未生成或下发"
        status, reason = _apply_exemption(db, rec, "agreement", status, reason)
        items.append(_item(
            "agreement", acfg.get("label", "三方协议"),
            required=bool(acfg.get("required")), severity=acfg.get("severity", "BLOCK"),
            status=status, reason=reason, route="/pages/student/internship/agreement/index",
        ))

        fcfg = rules["specialFiling"]
        position = db.get(InternshipPosition, rec.position_id) if rec.position_id else None
        from app.modules.internship.services.internship_special_filing_service import evaluate_triggers
        triggers = evaluate_triggers(position, student, None) if fcfg.get("required") else []
        filings = db.scalars(select(InternshipSpecialFiling).where(
            InternshipSpecialFiling.tenant_id == _tid(),
            InternshipSpecialFiling.internship_id == rec.id,
            InternshipSpecialFiling.is_deleted.is_(False),
        )).all()
        if not fcfg.get("required") or not triggers:
            status, reason = "NOT_APPLICABLE", "当前岗位无需特殊备案"
        elif _valid_row(filings, {"APPROVED"}):
            status, reason = "VALID", ""
        elif any(str(x.status).startswith("PENDING") for x in filings):
            status, reason = "PENDING", "特殊实习备案审批中"
        else:
            status, reason = "MISSING", "当前岗位触发特殊备案，学校尚未完成审批"
        status, reason = _apply_exemption(db, rec, "specialFiling", status, reason)
        items.append(_item(
            "specialFiling", fcfg.get("label", "特殊实习备案"),
            required=bool(fcfg.get("required") and triggers), severity=fcfg.get("severity", "BLOCK"),
            status=status, reason=reason,
        ))

        wcfg = rules["workRights"]
        if not wcfg.get("required"):
            status, reason = "NOT_APPLICABLE", "当前批次规则未启用岗位权益门禁"
        elif not position:
            status, reason = "MISSING", "尚未落实岗位，无法核验岗位权益"
        else:
            company = db.get(EmpCompany, position.company_id) if position.company_id else None
            rights = evaluate_position_publishability(
                position, company, batch, student, operation=operation, db=db)
            status = "VALID" if rights.get("passed") else "REJECTED"
            reason = "；".join(
                x.get("reason", "") for x in
                (rights.get("blockers") or []) + (rights.get("unknowns") or [])
                if x.get("reason"))
        status, reason = _apply_exemption(db, rec, "workRights", status, reason)
        items.append(_item(
            "workRights", wcfg.get("label", "岗位劳动权益"),
            required=bool(wcfg.get("required")), severity=wcfg.get("severity", "BLOCK"),
            status=status, reason=reason,
        ))

        ecfg = rules["emergency"]
        if not ecfg.get("required"):
            status, reason = "NOT_APPLICABLE", "当前批次规则未要求应急预案"
        elif not rec.enterprise_id:
            status, reason = "MISSING", "尚未落实企业，无法匹配应急预案"
        else:
            plans = db.scalars(select(InternshipEmergencyPlan).where(
                InternshipEmergencyPlan.tenant_id == _tid(),
                InternshipEmergencyPlan.company_id == rec.enterprise_id,
                InternshipEmergencyPlan.is_deleted.is_(False),
            )).all()
            status, reason = ("VALID", "") if _valid_row(plans, {"APPROVED"}) else ("MISSING", "实习企业尚无有效应急预案")
        status, reason = _apply_exemption(db, rec, "emergency", status, reason)
        items.append(_item(
            "emergency", ecfg.get("label", "应急预案"),
            required=bool(ecfg.get("required")), severity=ecfg.get("severity", "BLOCK"),
            status=status, reason=reason,
        ))

        blockers = [
            x for x in items
            if x["required"] and x["severity"] == "BLOCK"
            and x["status"] not in ("VALID", "EXEMPTED", "NOT_APPLICABLE")
        ]
        warnings = [
            x for x in items
            if x["applicable"] and x["status"] not in ("VALID", "EXEMPTED", "NOT_APPLICABLE")
            and x not in blockers
        ]
        required_items = [x for x in items if x["required"]]
        done = [x for x in required_items if x["status"] in ("VALID", "EXEMPTED")]
        current = blockers[0] if blockers else (warnings[0] if warnings else None)
        timeline = [{
            "id": x["code"],
            "title": x["label"],
            "status": "COMPLETED" if x["status"] in ("VALID", "EXEMPTED", "NOT_APPLICABLE")
            else ("PROCESSING" if x is current else "NOT_STARTED"),
            "current": x is current,
            "reason": x["reason"],
            "route": x["route"],
        } for x in items if x["required"] or x["status"] != "NOT_APPLICABLE"]
        return {
            "hasData": True,
            "needSelect": False,
            "historyMode": ctx.mode == "history",
            "recordId": str(rec.id),
            "batchId": str(rec.batch_id or ""),
            "batchName": getattr(batch, "batch_name", "") or "",
            "recordStatus": rec.status,
            "operation": operation,
            "passed": not blockers,
            "items": items,
            "blockers": blockers,
            "warnings": warnings,
            "currentTask": current,
            "nextAction": ({
                "label": f"去处理：{current['label']}",
                "route": current["route"],
                "code": current["code"],
            } if current and current.get("route") else None),
            "timeline": timeline,
            "completeness": {
                "done": len(done),
                "required": len(required_items),
                "ratio": round(len(done) / len(required_items), 4) if required_items else 1.0,
            },
            "ruleVersion": rule_version_label(batch),
            "evaluatedAt": datetime.utcnow().isoformat() + "Z",
        }
