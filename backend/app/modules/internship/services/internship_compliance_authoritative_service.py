"""学校端、归档端和批次端使用的权威合规包装层。

保留既有完整规则计算，只替换已经确认有误的安全教育事实：当前批次全部 ACTIVE
课程均须按当前版本通过且完成承诺。模块加载后把旧公开入口兼容指向本实现，使
历史调用点无需复制重写也不会继续使用错误安全判定。
"""
from __future__ import annotations

from contextlib import nullcontext

from app.models import InternshipRecord
from app.modules.internship.services import internship_compliance_service as base
from app.modules.internship.services.internship_safety_compliance_service import (
    evaluate_required_courses,
)
from app.services.db_service import _as_id, session

# 保存原始实现，避免兼容回挂后递归调用自身。
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
    """批次统计逐学生使用权威评估器，避免旧统计与学生端不一致。"""
    from app.models import InternshipRecord, StudentProfile
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    from app.services.db_service import _tid
    from sqlalchemy import select

    with session() as db:
        batch = resolve_batch(db, batch_id)
        records = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
        ).order_by(InternshipRecord.id.asc())).all()
        scope = _current_scope(user)
        rows = []
        by_code = {}
        passed = 0
        for record in records:
            student = db.get(StudentProfile, record.student_id)
            if not student or not _rec_in_scope(scope, db, record, student):
                continue
            result = evaluate_internship_compliance(
                record.id, operation="ONBOARD", user=user, db=db)
            if result.get("passed"):
                passed += 1
            blockers = result.get("blockers") or []
            for item in blockers:
                by_code[item["code"]] = by_code.get(item["code"], 0) + 1
            rows.append({
                "internshipId": str(record.id),
                "studentId": str(record.student_id),
                "studentNo": student.student_no,
                "studentName": student.real_name,
                "advisorName": record.advisor_name or "",
                "passed": bool(result.get("passed")),
                "blockers": blockers,
                "warnings": result.get("warnings") or [],
                "ruleVersion": result.get("ruleVersion"),
            })
        total = len(rows)
        return {
            "batchId": str(batch.id), "batchName": batch.batch_name,
            "total": total, "passed": passed, "blocked": total - passed,
            "missingByCode": by_code, "students": rows,
            "ruleVersion": rows[0].get("ruleVersion") if rows else "",
        }


# 兼容历史调用点：应用启动加载本模块后，旧模块公开函数统一落到权威实现。
# 旧模块内部 grant/review_exemption 等其它能力不受影响。
base.evaluate_internship_compliance = evaluate_internship_compliance
base.batch_compliance_stats = batch_compliance_stats
