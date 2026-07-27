"""教务归档十三域唯一语义规则入口。

本模块是纯规则编排：不修改其它模块函数、不依赖导入顺序、不创建第二套归档事实。
归档批次、归档明细、确认封存、解冻和导出仍由 ``academic_affairs_archive_core_service`` 承担。
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time

from sqlalchemy import or_

from app.services.db_service import _tid

from . import academic_affairs_archive_core_service as _core
from . import academic_affairs_archive_rule_evaluator as _semantic
from .academic_affairs_effective_grade_policy_service import policy_snapshot_debt

DOMAINS = [
    ("STUDENT_STATUS", "学籍"),
    ("REGISTRATION", "注册"),
    ("STATUS_CHANGE", "异动"),
    ("PROGRAM", "培养方案"),
    ("TEACHING_TASK", "教学任务"),
    ("SCHEDULE", "课表"),
    ("SELECTION", "选课名单"),
    ("EXAM", "考务"),
    ("GRADE", "成绩"),
    ("MAKEUP", "补考重修免修"),
    ("EVALUATION", "学生评教"),
    ("TEXTBOOK", "教材征订发放费用"),
    ("GRADUATION", "毕业资格"),
]

ROUTES = {
    "STUDENT_STATUS": "/admin/academic-affairs/roster",
    "REGISTRATION": "/admin/academic-affairs/registration",
    "STATUS_CHANGE": "/admin/academic-affairs/status-changes",
    "PROGRAM": "/admin/academic-affairs/programs",
    "TEACHING_TASK": "/admin/academic-affairs/teaching-tasks",
    "SCHEDULE": "/admin/academic-affairs/scheduling",
    "SELECTION": "/admin/academic-affairs/selection/archive",
    "EXAM": "/admin/academic-affairs/exam",
    "GRADE": "/admin/academic-affairs/grade-tasks",
    "MAKEUP": "/admin/academic-affairs/makeup",
    "EVALUATION": "/admin/academic-affairs/evaluation",
    "TEXTBOOK": "/admin/academic-affairs/textbooks",
    "GRADUATION": "/admin/academic-affairs/graduation-audit",
}

_ACTIVE_STATUS_CHANGE = {"DRAFT", "SUBMITTED", "IN_REVIEW"}
_ORDER_TERMINAL = {"ARRIVED", "RECEIVED", "ARCHIVED", "CANCELLED"}
_FEE_TERMINAL = {"PAID", "WAIVED"}


def _day_start(value):
    if value is None:
        return None
    return value if isinstance(value, datetime) else datetime.combine(value, time.min)


def _day_end(value):
    if value is None:
        return None
    return value if isinstance(value, datetime) else datetime.combine(value, time.max)


def _legacy_result(count, passed, remark):
    return _core._result(int(count or 0), bool(passed), str(remark or ""))


def _safe(code, fn):
    try:
        return fn()
    except Exception as exc:
        return _legacy_result(0, False, f"该域语义检查失败：{type(exc).__name__}")


def evaluate_status_change(db, term_id, term_code):
    """只阻断能归属到本学期的真实在途异动；退回、驳回和已生效均为终态。"""
    from app.models import AaStatusChange, AaTerm

    term = None
    if term_id:
        term = db.query(AaTerm).filter(
            AaTerm.id == int(term_id),
            AaTerm.tenant_id == _tid(),
            AaTerm.is_deleted.is_(False),
        ).first()
    start_at = _day_start(getattr(term, "start_date", None)) if term else None
    end_at = _day_end(getattr(term, "end_date", None)) if term else None

    rows = db.query(AaStatusChange).filter(
        AaStatusChange.tenant_id == _tid(),
        AaStatusChange.is_deleted.is_(False),
    ).all()
    scoped = []
    unresolved = 0
    for row in rows:
        row_term = str(getattr(row, "term_code", None) or "").strip()
        if term_code and row_term:
            if row_term == term_code:
                scoped.append(row)
            continue
        occurred_at = (
            getattr(row, "effective_date", None)
            or getattr(row, "created_at", None)
            or getattr(row, "updated_at", None)
        )
        if start_at and end_at and occurred_at:
            if start_at <= occurred_at <= end_at:
                scoped.append(row)
        elif not row_term:
            unresolved += 1

    active = [
        row for row in scoped
        if str(getattr(row, "status", None) or "").upper() in _ACTIVE_STATUS_CHANGE
    ]
    passed = not active
    remark = "本学期无在途学籍异动" if passed else f"本学期仍有 {len(active)} 条学籍异动处于草稿/审批中"
    if unresolved:
        remark += f"；另有 {unresolved} 条历史异动缺少学期与可用日期，待迁移补齐"
    return _legacy_result(len(scoped), passed, remark)


def evaluate_graduation(db, term_id):
    """毕业审核批次没有term_id时只按学期日期窗口核验，禁止用全校历史阻断当前学期。"""
    from app.models import AaGraduationAuditBatch, AaTerm

    if not term_id:
        return _legacy_result(0, True, "未指定学期；毕业审核批次暂无term_id，本次不跨学期阻断")
    term = db.query(AaTerm).filter(
        AaTerm.id == int(term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        return _legacy_result(0, False, "学期不存在，无法核验毕业审核范围")
    start_at = _day_start(getattr(term, "start_date", None))
    end_at = _day_end(getattr(term, "end_date", None))
    if not start_at or not end_at:
        return _legacy_result(0, True, "学期起止日期不完整；已停止使用全校历史毕业批次作阻断")

    rows = []
    for row in db.query(AaGraduationAuditBatch).filter(
        AaGraduationAuditBatch.tenant_id == _tid(),
        AaGraduationAuditBatch.is_deleted.is_(False),
    ).all():
        occurred_at = getattr(row, "generate_at", None) or getattr(row, "created_at", None)
        if occurred_at and start_at <= occurred_at <= end_at:
            rows.append(row)
    if not rows:
        return _legacy_result(0, True, "本学期未发现可按时间归属的毕业审核批次（非毕业学期不阻断）")
    unfinished = [row for row in rows if str(row.status or "").upper() != "ARCHIVED"]
    return _legacy_result(
        len(rows),
        not unfinished,
        "本学期毕业审核批次均已归档" if not unfinished else f"本学期仍有 {len(unfinished)} 个毕业审核批次未归档",
    )


def _active_round_count(rounds) -> int:
    count = 0
    for row in rounds or []:
        status = str(getattr(row, "status", None) or "").upper()
        mode = str(getattr(row, "mode", None) or "FCFS").upper()
        if status in {"DRAFT", "OPEN"} or (status == "CLOSED" and mode == "LOTTERY"):
            count += 1
    return count


def evaluate_selection(db, term_id):
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord, AaSelectionRound

    query = db.query(AaSelectionBatch).filter(
        AaSelectionBatch.tenant_id == _tid(),
        AaSelectionBatch.is_deleted.is_(False),
    )
    if term_id:
        query = query.filter(AaSelectionBatch.term_id == int(term_id))
    batches = query.all()
    if not batches:
        return _legacy_result(0, True, "本学期未启用选课批次，不作为归档阻断")
    batch_ids = [int(row.id) for row in batches]
    unfinished = [
        row for row in batches
        if str(row.status or "").upper() not in {"LOCKED", "ARCHIVED"}
    ]
    rounds = db.query(AaSelectionRound).filter(
        AaSelectionRound.tenant_id == _tid(),
        AaSelectionRound.batch_id.in_(batch_ids),
        AaSelectionRound.is_deleted.is_(False),
    ).all()
    active_rounds = _active_round_count(rounds)
    pending_records = db.query(AaSelectionRecord).filter(
        AaSelectionRecord.tenant_id == _tid(),
        AaSelectionRecord.batch_id.in_(batch_ids),
        AaSelectionRecord.status.in_(["SELECTED", "PENDING_LOTTERY"]),
        AaSelectionRecord.is_deleted.is_(False),
    ).count()
    courses = db.query(AaSelectionCourse).filter(
        AaSelectionCourse.tenant_id == _tid(),
        AaSelectionCourse.batch_id.in_(batch_ids),
        AaSelectionCourse.status == "OPEN",
        AaSelectionCourse.is_deleted.is_(False),
    ).all()
    missing_tasks = sum(1 for course in courses if not course.teaching_task_id)
    batch_by_id = {int(row.id): row for row in batches}
    count_mismatches = 0
    for course in courses:
        batch = batch_by_id.get(int(course.batch_id))
        if not batch or str(batch.status or "").upper() not in {"LOCKED", "ARCHIVED"}:
            continue
        locked = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _tid(),
            AaSelectionRecord.selection_course_id == course.id,
            AaSelectionRecord.status == "LOCKED",
            AaSelectionRecord.is_deleted.is_(False),
        ).count()
        if int(course.selected_count or 0) != int(locked or 0):
            count_mismatches += 1
    blockers = []
    if unfinished:
        blockers.append(f"未锁定/未归档选课批次 {len(unfinished)} 个")
    if active_rounds:
        blockers.append(f"仍有未终结选课轮次 {active_rounds} 个")
    if pending_records:
        blockers.append(f"仍有未转正式名单记录 {int(pending_records)} 条")
    if count_mismatches:
        blockers.append(f"课程人数计数与LOCKED名单不一致 {count_mismatches} 门")
    if missing_tasks:
        blockers.append(f"未关联教学任务的有效课程 {missing_tasks} 门")
    return _legacy_result(
        len(batches), not blockers,
        "选课批次和正式教学名单均已锁定" if not blockers else "；".join(blockers),
    )


def evaluate_makeup(db, term_id, term_code):
    from app.models import AaExemption, AaMakeupBatch, AaRetakeApply

    if not term_id and not term_code:
        return _legacy_result(0, False, "未指定学期，无法核验补考重修免修")
    conditions = []
    if term_id:
        conditions.append(AaMakeupBatch.term_id == int(term_id))
    if term_code:
        conditions.append(AaMakeupBatch.term_code == term_code)
    batches = db.query(AaMakeupBatch).filter(
        AaMakeupBatch.tenant_id == _tid(),
        or_(*conditions),
        AaMakeupBatch.is_deleted.is_(False),
    ).all()
    unfinished = [row for row in batches if str(row.status or "").upper() != "FINISHED"]
    active_retakes = db.query(AaRetakeApply).filter(
        AaRetakeApply.tenant_id == _tid(),
        AaRetakeApply.term_code == term_code,
        AaRetakeApply.status.in_(["SUBMITTED", "ACADEMIC_REVIEW", "APPROVED"]),
        AaRetakeApply.is_deleted.is_(False),
    ).count() if term_code else 0
    active_exemptions = db.query(AaExemption).filter(
        AaExemption.tenant_id == _tid(),
        AaExemption.term_code == term_code,
        AaExemption.status.notin_(["APPROVED", "REJECTED", "CANCELLED"]),
        AaExemption.is_deleted.is_(False),
    ).count() if term_code else 0
    blockers = []
    if unfinished:
        blockers.append(f"未结束补考/清考批次 {len(unfinished)} 个")
    if active_retakes:
        blockers.append(f"仍有在途重修申请 {int(active_retakes)} 条")
    if active_exemptions:
        blockers.append(f"仍有在途免修申请 {int(active_exemptions)} 条")
    return _legacy_result(
        len(batches) + int(active_retakes or 0) + int(active_exemptions or 0),
        not blockers,
        "补考、清考、重修和免修均已收口" if not blockers else "；".join(blockers),
    )


def evaluate_evaluation(db, term_id):
    from app.models import AaEvaluationAppeal, AaEvaluationBatch, AaEvaluationResult, AaEvaluationTask

    if not term_id:
        return _legacy_result(0, False, "未指定学期，无法核验学生评教")
    batches = db.query(AaEvaluationBatch).filter(
        AaEvaluationBatch.tenant_id == _tid(),
        AaEvaluationBatch.term_id == int(term_id),
        AaEvaluationBatch.is_deleted.is_(False),
    ).all()
    if not batches:
        return _legacy_result(0, True, "本学期未启用学生评教，不作为归档阻断")
    batch_ids = [int(row.id) for row in batches]
    unfinished = [
        row for row in batches
        if str(row.status or "").upper() not in {"RESULT_READY", "ARCHIVED"}
    ]
    tasks = db.query(AaEvaluationTask).filter(
        AaEvaluationTask.tenant_id == _tid(),
        AaEvaluationTask.batch_id.in_(batch_ids),
        AaEvaluationTask.is_deleted.is_(False),
    ).all()
    results = db.query(AaEvaluationResult).filter(
        AaEvaluationResult.tenant_id == _tid(),
        AaEvaluationResult.batch_id.in_(batch_ids),
        AaEvaluationResult.is_deleted.is_(False),
    ).all()
    result_keys = {
        (int(row.batch_id), int(row.teaching_task_id))
        for row in results if row.batch_id and row.teaching_task_id
    }
    missing_results = sum(
        1 for task in tasks
        if int(task.submitted_count or 0) > 0
        and (not task.teaching_task_id or (int(task.batch_id), int(task.teaching_task_id)) not in result_keys)
    )
    result_ids = [int(row.id) for row in results]
    active_appeals = db.query(AaEvaluationAppeal).filter(
        AaEvaluationAppeal.tenant_id == _tid(),
        AaEvaluationAppeal.result_id.in_(result_ids),
        AaEvaluationAppeal.status.in_(["SUBMITTED", "COLLEGE_REVIEW"]),
        AaEvaluationAppeal.is_deleted.is_(False),
    ).count() if result_ids else 0
    blockers = []
    if unfinished:
        blockers.append(f"未形成最终结果的评教批次 {len(unfinished)} 个")
    if missing_results:
        blockers.append(f"有提交但未生成结果的评教任务 {missing_results} 个")
    if active_appeals:
        blockers.append(f"仍有在途评教申诉 {int(active_appeals)} 条")
    return _legacy_result(
        len(batches), not blockers,
        "评教窗口、结果和申诉均已收口" if not blockers else "；".join(blockers),
    )


def evaluate_textbook(db, term_id):
    from app.models import (
        AaTextbookDistributionBatch, AaTextbookDistributionRecord,
        AaTextbookFeeLedger, AaTextbookOrderBatch, AaTextbookOrderItem,
    )

    if not term_id:
        return _legacy_result(0, False, "未指定学期，无法核验教材业务")
    orders = db.query(AaTextbookOrderBatch).filter(
        AaTextbookOrderBatch.tenant_id == _tid(),
        AaTextbookOrderBatch.term_id == int(term_id),
        AaTextbookOrderBatch.is_deleted.is_(False),
    ).all()
    if not orders:
        return _legacy_result(0, True, "本学期未启用教材征订，不作为归档阻断")
    order_ids = [int(row.id) for row in orders]
    unfinished_orders = [
        row for row in orders if str(row.status or "").upper() not in _ORDER_TERMINAL
    ]
    items = db.query(AaTextbookOrderItem).filter(
        AaTextbookOrderItem.tenant_id == _tid(),
        AaTextbookOrderItem.order_batch_id.in_(order_ids),
        AaTextbookOrderItem.is_deleted.is_(False),
    ).all()
    ordered_qty = defaultdict(int)
    for item in items:
        ordered_qty[int(item.order_batch_id)] += int(item.order_qty or 0)
    distributions = db.query(AaTextbookDistributionBatch).filter(
        AaTextbookDistributionBatch.tenant_id == _tid(),
        AaTextbookDistributionBatch.order_batch_id.in_(order_ids),
        AaTextbookDistributionBatch.is_deleted.is_(False),
    ).all()
    distribution_order_ids = {int(row.order_batch_id) for row in distributions}
    missing_distribution = sum(
        1 for order in orders
        if str(order.status or "").upper() in {"ARRIVED", "RECEIVED", "ARCHIVED"}
        and ordered_qty.get(int(order.id), 0) > 0
        and int(order.id) not in distribution_order_ids
    )
    unfinished_distributions = sum(
        1 for row in distributions if str(row.status or "").upper() != "COMPLETED"
    )
    distribution_ids = [int(row.id) for row in distributions]
    records = db.query(AaTextbookDistributionRecord).filter(
        AaTextbookDistributionRecord.tenant_id == _tid(),
        AaTextbookDistributionRecord.batch_id.in_(distribution_ids),
        AaTextbookDistributionRecord.is_deleted.is_(False),
    ).all() if distribution_ids else []
    pending_records = sum(1 for row in records if str(row.status or "").upper() == "PENDING")
    chargeable = [
        row for row in records
        if str(row.status or "").upper() in {"RECEIVED", "RETURNED", "EXCHANGED"}
    ]
    chargeable_ids = [int(row.id) for row in chargeable]
    fees = db.query(AaTextbookFeeLedger).filter(
        AaTextbookFeeLedger.tenant_id == _tid(),
        AaTextbookFeeLedger.distribution_record_id.in_(chargeable_ids),
        AaTextbookFeeLedger.is_deleted.is_(False),
    ).all() if chargeable_ids else []
    fee_record_ids = {int(row.distribution_record_id) for row in fees}
    missing_fees = sum(1 for row in chargeable if int(row.id) not in fee_record_ids)
    unsettled = sum(1 for row in fees if str(row.status or "").upper() not in _FEE_TERMINAL)
    blockers = []
    if unfinished_orders:
        blockers.append(f"未到货/未取消征订批次 {len(unfinished_orders)} 个")
    if missing_distribution:
        blockers.append(f"已到货但未形成发放批次的征订 {missing_distribution} 个")
    if unfinished_distributions:
        blockers.append(f"未完成教材发放批次 {unfinished_distributions} 个")
    if pending_records:
        blockers.append(f"仍有待处理教材发放记录 {pending_records} 条")
    if missing_fees:
        blockers.append(f"已签收/退领但缺少费用台账 {missing_fees} 条")
    if unsettled:
        blockers.append(f"未结清教材费用 {unsettled} 条")
    return _legacy_result(
        len(orders) + unfinished_distributions + pending_records + missing_fees + unsettled,
        not blockers,
        "教材征订、发放和费用均已收口" if not blockers else "；".join(blockers),
    )


def apply_effective_grade_policy_debt(db, term_code, result):
    debt = policy_snapshot_debt(db, term=term_code)
    blockers = int(debt.get("missingPolicySnapshot") or 0) + int(debt.get("legacyNameKey") or 0)
    evidence = list(result.get("evidence") or [])
    evidence.append({
        "type": "EFFECTIVE_GRADE_POLICY" if not blockers else "EFFECTIVE_GRADE_POLICY_DEBT",
        "policyCode": "LATEST_FORMAL_SOURCE_V1",
        "totalGrades": int(debt.get("total") or 0),
        "missingPolicySnapshot": int(debt.get("missingPolicySnapshot") or 0),
        "legacyNameKey": int(debt.get("legacyNameKey") or 0),
        "sampleGradeIds": list(debt.get("sampleGradeIds") or []),
    })
    result["evidence"] = evidence
    if not blockers:
        return result
    result.update({
        "present": False,
        "result": "BLOCKED",
        "blockingCount": int(result.get("blockingCount") or 0) + blockers,
        "ruleCode": "GRADE_EFFECTIVE_POLICY_DEBT",
        "summary": (
            f"有效成绩策略欠账{blockers}项：缺少策略快照{debt.get('missingPolicySnapshot', 0)}条，"
            f"LEGACY_NAME_KEY {debt.get('legacyNameKey', 0)}条；禁止归档"
        ),
        "route": "/admin/academic-affairs/grade-identity-debt",
    })
    result["remark"] = result["summary"]
    return result


def evaluate_domains(db, term_id, term_code, college_ids=None) -> dict[str, dict]:
    """十三域唯一编排；任一规则异常都明确阻断，不伪装为无数据或成功。"""
    base = _core._evaluate_domains(db, term_id, term_code, college_ids)
    base["STATUS_CHANGE"] = _safe("STATUS_CHANGE", lambda: evaluate_status_change(db, term_id, term_code))
    base["GRADUATION"] = _safe("GRADUATION", lambda: evaluate_graduation(db, term_id))
    results = _semantic.evaluate_first_batch(
        db, term_id, term_code, base, college_ids=college_ids,
    )
    results["GRADE"] = _safe(
        "GRADE", lambda: apply_effective_grade_policy_debt(db, term_code, results["GRADE"]),
    )
    results["SELECTION"] = _safe("SELECTION", lambda: evaluate_selection(db, term_id))
    results["MAKEUP"] = _safe("MAKEUP", lambda: evaluate_makeup(db, term_id, term_code))
    results["EVALUATION"] = _safe("EVALUATION", lambda: evaluate_evaluation(db, term_id))
    results["TEXTBOOK"] = _safe("TEXTBOOK", lambda: evaluate_textbook(db, term_id))

    output = {}
    for code, _label in DOMAINS:
        normalized = _semantic.normalize_legacy_result(code, results.get(code) or _legacy_result(0, False, "规则未返回结果"))
        normalized["route"] = normalized.get("route") or ROUTES[code]
        normalized["summary"] = normalized.get("summary") or normalized.get("remark") or ""
        normalized["remark"] = normalized["summary"]
        normalized["evidence"] = list(normalized.get("evidence") or [])
        output[code] = normalized
    return output
