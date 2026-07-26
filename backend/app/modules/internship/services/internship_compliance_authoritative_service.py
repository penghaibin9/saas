"""学校端、归档端和批次端使用的权威合规包装层。

保留既有完整规则计算，只替换已经确认有误的安全教育事实：当前批次全部 ACTIVE
课程均须按当前版本通过且完成承诺。模块加载后把旧公开入口兼容指向本实现，使
历史调用点无需复制重写也不会继续使用错误安全判定。
"""
from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime

from app.models import InternshipRecord
from app.modules.internship.services import internship_compliance_service as base
from app.modules.internship.services.internship_safety_compliance_service import (
    evaluate_required_courses,
)
from app.services.db_service import _as_id, session

_legacy_evaluate = base.evaluate_internship_compliance


def _recompute(result: dict) -> dict:
    items = result.get("items") or []
    blockers = [
        item for item in items
        if item.get("required") and item.get("applicable")
        and item.get("severity") == "BLOCK"
        and item.get("status") not in ("VALID", "EXEMPTED", "NOT_APPLICABLE")
    ]
    warnings = [
        item for item in items
        if item.get("applicable")
        and item.get("status") not in ("VALID", "EXEMPTED", "NOT_APPLICABLE")
        and item not in blockers
    ]
    applicable = [
        item for item in items if item.get("applicable") and item.get("required")
    ]
    done = [
        item for item in applicable
        if item.get("status") in ("VALID", "EXEMPTED")
    ]
    result["blockers"] = blockers
    result["warnings"] = warnings
    result["passed"] = not blockers
    result["completeness"] = {
        "done": len(done),
        "applicable": len(applicable),
        "ratio": round(len(done) / len(applicable), 4) if applicable else 1.0,
    }
    return result


def evaluate_internship_compliance(
    internship_id, operation="ONBOARD", user=None, db=None,
):
    result = _legacy_evaluate(
        internship_id, operation=operation, user=user, db=db)
    with (session() if db is None else nullcontext(db)) as active_db:
        record = active_db.get(InternshipRecord, _as_id(internship_id))
        if not record or not record.batch_id:
            return result
        safety = evaluate_required_courses(
            active_db, batch_id=record.batch_id, internship_id=record.id)
    for item in result.get("items") or []:
        if item.get("code") != "safetyEducation":
            continue
        if item.get("status") == "NOT_APPLICABLE":
            break
        item["status"] = safety["status"]
        item["reason"] = safety["reason"]
        item["evidenceId"] = (
            str(safety["evidenceId"]) if safety.get("evidenceId") else None)
        item["evidenceVersion"] = safety.get("evidenceVersion")
        item["detail"] = {
            "requiredCount": safety["requiredCount"],
            "passedCount": safety["passedCount"],
            "missingCourses": safety["missingCourses"],
        }
        break
    return _recompute(result)


def batch_compliance_stats(batch_id, user=None):
    """保持原PC契约，所有指标和下钻使用权威上岗/归档评估。"""
    from sqlalchemy import select
    from app.models import StudentProfile
    from app.modules.internship.services.internship_scope import (
        apply_internship_record_scope,
    )
    from app.services.db_service import _tid

    with session() as db:
        query = select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == _as_id(batch_id),
            InternshipRecord.is_deleted.is_(False),
        )
        records = db.scalars(apply_internship_record_scope(query, user)).all()
        evaluated_at = datetime.utcnow().isoformat() + "Z"
        entries = []
        by_code = {}
        rule_version = None
        for record in records:
            onboard = evaluate_internship_compliance(
                record.id, "ONBOARD", user=user, db=db)
            archive = evaluate_internship_compliance(
                record.id, "ARCHIVE", user=user, db=db)
            rule_version = rule_version or onboard.get("ruleVersion")
            student = db.get(StudentProfile, record.student_id)
            codes = sorted({item["code"] for item in onboard["blockers"]})
            archive_codes = sorted({item["code"] for item in archive["blockers"]})
            entry = {
                "internshipId": str(record.id),
                "studentId": str(record.student_id),
                "studentNo": student.student_no if student else "",
                "studentName": student.real_name if student else "",
                "classId": str(student.class_id or "") if student else "",
                "advisorName": record.advisor_name or "",
                "recordStatus": record.status,
                "onboardPassed": bool(onboard["passed"]),
                "archivePassed": bool(archive["passed"]),
                "blockerCodes": codes,
                "archiveBlockerCodes": archive_codes,
                "blockers": onboard["blockers"],
                "archiveBlockers": archive["blockers"],
                "route": f"/admin/internship/students/{record.id}",
            }
            entries.append(entry)
            for code in set(codes + archive_codes):
                by_code.setdefault(code, []).append(entry)

        labels = {
            "enterpriseAccess": "缺企业准入",
            "studentConsent": "缺学生知情",
            "guardianConsent": "缺监护人确认",
            "safetyEducation": "缺安全教育",
            "agreement": "缺协议",
            "insurance": "缺保险",
            "specialFiling": "缺特殊备案",
            "workRights": "岗位权益不合规",
            "emergency": "缺应急预案",
            "openIncident": "开放事故",
            "openHighRisk": "开放高风险",
        }
        metrics = [
            {"metricCode": "TOTAL", "metricLabel": "批次总人数",
             "count": len(entries), "drilldownFilter": "ALL"},
            {"metricCode": "ONBOARD_READY", "metricLabel": "可上岗",
             "count": sum(1 for item in entries if item["onboardPassed"]),
             "drilldownFilter": "ONBOARD_READY"},
            {"metricCode": "BLOCKED", "metricLabel": "被阻断",
             "count": sum(1 for item in entries if not item["onboardPassed"]),
             "drilldownFilter": "BLOCKED"},
        ]
        metrics.extend({
            "metricCode": code, "metricLabel": label,
            "count": len(by_code.get(code, [])), "drilldownFilter": code,
        } for code, label in labels.items())
        metrics.extend([
            {"metricCode": "ARCHIVE_READY", "metricLabel": "可归档",
             "count": sum(1 for item in entries if item["archivePassed"]),
             "drilldownFilter": "ARCHIVE_READY"},
            {"metricCode": "ARCHIVE_BLOCKED", "metricLabel": "不可归档",
             "count": sum(1 for item in entries if not item["archivePassed"]),
             "drilldownFilter": "ARCHIVE_BLOCKED"},
        ])
        for metric in metrics:
            metric["ruleVersion"] = rule_version
            metric["evaluatedAt"] = evaluated_at
        drilldowns = {
            "ALL": entries,
            "ONBOARD_READY": [item for item in entries if item["onboardPassed"]],
            "BLOCKED": [item for item in entries if not item["onboardPassed"]],
            "ARCHIVE_READY": [item for item in entries if item["archivePassed"]],
            "ARCHIVE_BLOCKED": [item for item in entries if not item["archivePassed"]],
            **by_code,
        }
        return {
            "batchId": str(batch_id), "total": len(entries),
            "passed": sum(1 for item in entries if item["onboardPassed"]),
            "blocked": sum(1 for item in entries if not item["onboardPassed"]),
            "metrics": metrics, "drilldowns": drilldowns,
            "missingByCode": {
                code: len(values) for code, values in by_code.items()
            },
            "students": entries,
            "ruleVersion": rule_version,
            "evaluatedAt": evaluated_at,
        }


base.evaluate_internship_compliance = evaluate_internship_compliance
base.batch_compliance_stats = batch_compliance_stats
