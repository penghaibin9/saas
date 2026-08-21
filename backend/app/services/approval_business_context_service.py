"""审批业务 Context 解析（V3 施工手册 TP-A06/TP-A07）。

本模块是审批中心与各业务域之间的只读 adapter 层。审批详情必须展示真实源业务事实；
approve/return/reject 时还必须在同一事务以 ``for_update=True`` 锁住源业务行，并用
``sourceVersion`` 校验用户实际看过的快照，避免“看的是 A，批准时已变成 B”。

生产规则：
- ``FULL``：源记录存在且关键事实齐全；动作可在版本匹配时继续。
- ``PARTIAL/MISSING/ERROR``：信息不足、记录失效或读取失败；动作 fail-closed。
- ``UNSUPPORTED``：只允许尚未接入生产 workflow 的未知类型或显式沙箱豁免出现；
  正式审批字典中的生产类型必须全部登记 adapter，并由合同测试锁死覆盖率。
"""
from __future__ import annotations

from typing import Any, Callable

from app.core.exceptions import AppException
from app.services.db_service import _iso, _tid

CONTEXT_VERSION = 1

FULL = "FULL"
PARTIAL = "PARTIAL"
MISSING = "MISSING"
UNSUPPORTED = "UNSUPPORTED"
ERROR = "ERROR"

_MASKED_PLACEHOLDER = "（敏感内容，需单独授权查看）"


def _field(label: str, value: Any, *, masked: bool = False) -> dict:
    if masked:
        return {"label": label, "value": _MASKED_PLACEHOLDER, "masked": True}
    if value in (None, ""):
        text = ""
    elif hasattr(value, "isoformat"):
        text = _iso(value) or ""
    else:
        text = str(value)
    return {"label": label, "value": text, "masked": False}


def _section(title: str, fields: list[dict]) -> dict:
    return {"title": title, "fields": fields}


def _completeness(fields: list[dict], required: list[str]) -> str:
    have = {f["label"] for f in fields if f["value"] and not f["masked"]}
    return FULL if all(r in have for r in required) else PARTIAL


def _source_row(db, model, source_biz_id: Any, *, for_update: bool = False):
    """租户内读取源业务行；动作模式下锁行直到调用方事务提交。"""
    from sqlalchemy import select

    stmt = select(model).where(
        model.id == int(source_biz_id),
        model.tenant_id == _tid(),
        model.is_deleted.is_(False),
    )
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).first()


def _attachments(db, biz_type: str, biz_id: Any) -> list[dict]:
    """学工域通用附件只投影最小元数据；真实预览仍由文件中心 ACL 裁定。"""
    from sqlalchemy import select
    from app.models import AffairsAttachment

    rows = db.scalars(select(AffairsAttachment).where(
        AffairsAttachment.tenant_id == _tid(),
        AffairsAttachment.biz_type == biz_type,
        AffairsAttachment.biz_id == int(biz_id),
        AffairsAttachment.is_deleted.is_(False),
    ).order_by(AffairsAttachment.id.desc())).all()
    return [{
        "fileId": str(r.file_id),
        "fileName": r.file_name or "",
        "bindingId": str(r.binding_id) if r.binding_id else None,
        "sensitivityLevel": r.sensitivity_level,
        "note": r.note or "",
    } for r in rows]


# ── 各业务域 adapter ──────────────────────────────────────
def _leave_context(db, instance, *, for_update: bool = False) -> dict:
    from app.models import CsLeave

    row = _source_row(db, CsLeave, instance.source_biz_id, for_update=for_update)
    if not row:
        return {"completeness": MISSING, "summary": "请假记录不存在或已删除",
                "sections": [], "attachments": [], "sourceVersion": None}
    fields = [
        _field("请假类型", row.leave_type),
        _field("开始时间", row.start_time),
        _field("结束时间", row.end_time),
        _field("天数", row.days),
        _field("事由", row.reason),
        _field("当前状态", row.affairs_status or row.status),
    ]
    if row.return_reason:
        fields.append(_field("上次退回原因", row.return_reason))
    return {
        "completeness": _completeness(fields, ["请假类型", "开始时间", "结束时间", "事由"]),
        "summary": f"{row.leave_type or '请假'} · {row.days or '—'} 天",
        "sections": [_section("请假信息", fields)],
        "attachments": _attachments(db, "LEAVE", row.id),
        "sourceVersion": int(row.version or 0),
    }


def _status_change_context(db, instance, *, for_update: bool = False) -> dict:
    from app.models import AaStatusChange

    row = _source_row(db, AaStatusChange, instance.source_biz_id, for_update=for_update)
    if not row:
        return {"completeness": MISSING, "summary": "学籍异动记录不存在或已删除",
                "sections": [], "attachments": [], "sourceVersion": None}
    fields = [
        _field("异动类型", row.change_type),
        _field("原学籍状态", row.from_status),
        _field("目标学籍状态", row.to_status),
        _field("异动原因", row.reason),
        _field("生效日期", row.effective_date),
        _field("当前状态", row.status),
    ]
    return {
        "completeness": _completeness(fields, ["异动类型", "目标学籍状态"]),
        "summary": f"学籍异动 · {row.change_type or '—'}",
        "sections": [_section("异动信息", fields)],
        "attachments": _attachments(db, "AA_STATUS_CHANGE", row.id),
        "sourceVersion": int(row.version or 0),
    }


def _aid_context(db, instance, *, for_update: bool = False) -> dict:
    from app.models import AidApply

    row = _source_row(db, AidApply, instance.source_biz_id, for_update=for_update)
    if not row:
        return {"completeness": MISSING, "summary": "困难认定申请不存在或已删除",
                "sections": [], "attachments": [], "sourceVersion": None}
    fields = [
        _field("申请等级", row.apply_level),
        _field("辅导员建议等级", row.suggest_level),
        _field("班级评议得分", row.class_review_score),
        _field("班级评议排名", row.class_review_rank),
        _field("困难情况说明", row.statement, masked=True),
        _field("当前状态", row.status),
    ]
    return {
        "completeness": _completeness(fields, ["申请等级"]),
        "summary": f"困难认定 · 申请等级 {row.apply_level or '—'}",
        "sections": [_section("认定信息", fields)],
        "attachments": _attachments(db, "AID", row.id),
        "sourceVersion": int(row.version or 0),
    }


def _funding_context(db, instance, *, for_update: bool = False) -> dict:
    """奖助评定申请。资格明细快照可能含敏感跨域信息，不在通用 Context 展开原文。"""
    from app.models import FundingApplication

    row = _source_row(db, FundingApplication, instance.source_biz_id, for_update=for_update)
    if not row:
        return {"completeness": MISSING, "summary": "奖助申请不存在或已删除",
                "sections": [], "attachments": [], "sourceVersion": None}
    amount = getattr(row, "requested_amount", None)
    if amount is None:
        amount = getattr(row, "amount", None)
    fields = [
        _field("资助类型", row.project_type),
        _field("申请来源", row.apply_source),
        _field("申请金额", amount),
        _field("申请理由", row.statement),
        _field("资格校验快照", getattr(row, "check_snapshot_json", None), masked=True),
        _field("当前状态", row.status),
    ]
    return {
        "completeness": _completeness(fields, ["资助类型", "当前状态"]),
        "summary": f"奖助评定 · {row.project_type or '—'}",
        "sections": [_section("奖助申请", fields)],
        "attachments": _attachments(db, "FUNDING", row.id),
        "sourceVersion": int(row.version or 0),
    }


def _discipline_context(db, instance, *, for_update: bool = False) -> dict:
    from app.models import DisciplineCase

    row = _source_row(db, DisciplineCase, instance.source_biz_id, for_update=for_update)
    if not row:
        return {"completeness": MISSING, "summary": "违纪记录不存在或已删除",
                "sections": [], "attachments": [], "sourceVersion": None}
    fields = [
        _field("处分类型", row.disc_type),
        _field("违纪事实", row.reason),
        _field("决定书文号", row.doc_no),
        _field("拟决定日期", row.decide_date),
        _field("当前状态", row.status),
    ]
    return {
        "completeness": _completeness(fields, ["处分类型", "违纪事实"]),
        "summary": f"违纪认定 · {row.disc_type or '—'}",
        "sections": [_section("违纪信息", fields)],
        "attachments": _attachments(db, "DISCIPLINE", row.id),
        "sourceVersion": int(row.version or 0),
    }


def _discipline_remove_context(db, instance, *, for_update: bool = False) -> dict:
    from app.models import DisciplineCase, DisciplineRemoveApply

    row = _source_row(db, DisciplineRemoveApply, instance.source_biz_id, for_update=for_update)
    if not row:
        return {"completeness": MISSING, "summary": "处分解除申请不存在或已删除",
                "sections": [], "attachments": [], "sourceVersion": None}
    case = _source_row(db, DisciplineCase, row.case_id, for_update=False) if row.case_id else None
    fields = [
        _field("处分单ID", row.case_id),
        _field("原处分类型", getattr(case, "disc_type", None)),
        _field("原处分文号", getattr(case, "doc_no", None)),
        _field("解除理由", row.apply_reason),
        _field("最短期限校验", "通过" if row.min_months_check else "未通过"),
        _field("当前节点", row.current_node),
        _field("当前状态", row.status),
    ]
    return {
        "completeness": _completeness(fields, ["处分单ID", "解除理由", "当前状态"]),
        "summary": f"处分解除 · {getattr(case, 'disc_type', '') or row.case_id}",
        "sections": [_section("解除申请", fields)],
        "attachments": _attachments(db, "DISCIPLINE_REMOVE", row.id),
        "sourceVersion": int(row.version or 0),
    }


def _grade_task_context(db, instance, *, for_update: bool = False) -> dict:
    """成绩任务审批展示任务规则和真实录入汇总；不把大量逐生成绩塞进通用详情。"""
    from sqlalchemy import func, select
    from app.models import AaGradeRecord, AaGradeTask

    row = _source_row(db, AaGradeTask, instance.source_biz_id, for_update=for_update)
    if not row:
        return {"completeness": MISSING, "summary": "成绩任务不存在或已删除",
                "sections": [], "attachments": [], "sourceVersion": None}
    aggregate = db.execute(select(
        func.count(AaGradeRecord.id),
        func.sum(func.if_(AaGradeRecord.total_score.is_not(None), 1, 0)),
        func.sum(func.if_(AaGradeRecord.pass_status == "PASSED", 1, 0)),
        func.sum(func.if_(AaGradeRecord.pass_status == "FAILED", 1, 0)),
    ).where(
        AaGradeRecord.tenant_id == _tid(),
        AaGradeRecord.task_id == row.id,
        AaGradeRecord.is_deleted.is_(False),
    )).first()
    total_rows = int((aggregate[0] if aggregate else 0) or 0)
    completed_rows = int((aggregate[1] if aggregate else 0) or 0)
    passed_rows = int((aggregate[2] if aggregate else 0) or 0)
    failed_rows = int((aggregate[3] if aggregate else 0) or 0)
    fields = [
        _field("课程", row.course_name),
        _field("学期", row.term_code),
        _field("任课教师", row.teacher_key),
        _field("平时占比", f"{row.usual_ratio}%"),
        _field("期中占比", f"{getattr(row, 'midterm_ratio', 0) or 0}%"),
        _field("期末占比", f"{row.final_ratio}%"),
        _field("及格线", row.pass_line),
        _field("成绩明细数", total_rows),
        _field("已录完整", completed_rows),
        _field("及格人数", passed_rows),
        _field("不及格人数", failed_rows),
        _field("当前状态", row.status),
    ]
    return {
        "completeness": _completeness(fields, ["课程", "当前状态"]),
        "summary": f"成绩审核 · {row.course_name or '课程'} · {completed_rows}/{total_rows} 已录完整",
        "sections": [_section("成绩任务", fields)],
        "attachments": [],
        "sourceVersion": int(row.version or 0),
    }


def _grade_change_context(db, instance, *, for_update: bool = False) -> dict:
    from app.models import AaGradeChangeRequest

    row = _source_row(db, AaGradeChangeRequest, instance.source_biz_id, for_update=for_update)
    if not row:
        return {"completeness": MISSING, "summary": "成绩更正申请不存在或已删除",
                "sections": [], "attachments": [], "sourceVersion": None}
    fields = [
        _field("学生ID", row.student_id),
        _field("更正理由", row.reason),
        _field("更正前平时分", row.before_usual_score),
        _field("更正前期中分", row.before_midterm_score),
        _field("更正前期末分", row.before_final_score),
        _field("更正前总评", row.before_total_score),
        _field("拟改平时分", row.proposed_usual_score),
        _field("拟改期中分", row.proposed_midterm_score),
        _field("拟改期末分", row.proposed_final_score),
        _field("拟改总评", row.proposed_total_score),
        _field("拟改及格状态", row.proposed_pass_status),
        _field("当前状态", row.status),
    ]
    return {
        "completeness": _completeness(fields, ["学生ID", "更正理由", "当前状态"]),
        "summary": f"成绩更正 · 学生 {row.student_id}",
        "sections": [_section("成绩更正", fields)],
        "attachments": [],
        "sourceVersion": int(row.version or 0),
    }


def _schedule_change_context(db, instance, *, for_update: bool = False) -> dict:
    from app.models import AaScheduleChange

    row = _source_row(db, AaScheduleChange, instance.source_biz_id, for_update=for_update)
    if not row:
        return {"completeness": MISSING, "summary": "调停课申请不存在或已删除",
                "sections": [], "attachments": [], "sourceVersion": None}
    fields = [
        _field("变更类型", row.change_type),
        _field("课程", row.course_name),
        _field("班级", row.class_name),
        _field("教师", row.teacher_name or row.teacher_key),
        _field("原星期", row.origin_weekday),
        _field("原节次", row.origin_slot_no),
        _field("原教室", row.origin_classroom),
        _field("目标星期", row.target_weekday),
        _field("目标节次", row.target_slot_no),
        _field("目标教室", row.target_classroom),
        _field("变更原因", row.reason),
        _field("补课安排", row.makeup_plan),
        _field("当前状态", row.status),
    ]
    return {
        "completeness": _completeness(fields, ["变更类型", "课程", "变更原因", "当前状态"]),
        "summary": f"{row.change_type or '调停课'} · {row.course_name or '课程'}",
        "sections": [_section("调停课申请", fields)],
        "attachments": [],
        "sourceVersion": int(row.version or 0),
    }


def _message_campaign_context(db, instance, *, for_update: bool = False) -> dict:
    from app.models import MessageCampaign

    row = _source_row(db, MessageCampaign, instance.source_biz_id, for_update=for_update)
    if not row:
        return {"completeness": MISSING, "summary": "消息发布单不存在或已删除",
                "sections": [], "attachments": [], "sourceVersion": None}
    fields = [
        _field("标题", row.title),
        _field("摘要", row.summary),
        _field("分类", row.category),
        _field("优先级", row.priority),
        _field("紧急消息", "是" if row.emergency else "否"),
        _field("需要确认回执", "是" if row.require_ack else "否"),
        _field("发布模式", row.publish_mode),
        _field("定时发布时间", row.scheduled_at),
        _field("过期时间", row.expire_at),
        _field("预计接收人数", row.recipient_count),
        _field("发布人", row.sender_name_snapshot),
        _field("当前状态", row.status),
    ]
    return {
        "completeness": _completeness(fields, ["标题", "当前状态"]),
        "summary": f"消息审核 · {row.title or '未命名消息'}",
        "sections": [_section("发布单", fields)],
        "attachments": [],
        "sourceVersion": int(row.version or 0),
    }


def _employment_destination_context(db, instance, *, for_update: bool = False) -> dict:
    from app.models import EmpDestinationSubmission
    from app.modules.employment.services.employment_service import L_DEST

    row = _source_row(db, EmpDestinationSubmission, instance.source_biz_id, for_update=for_update)
    if not row:
        return {"completeness": MISSING, "summary": "就业去向登记提交不存在或已删除",
                "sections": [], "attachments": [], "sourceVersion": None}
    dest_label = L_DEST.get(row.destination_type, row.destination_type)
    fields = [
        _field("去向类型", dest_label),
        _field("单位/去向", row.company_name),
        _field("岗位", row.job_title),
        _field("城市", row.city),
        _field("联系方式", row.contact),
        _field("说明", row.remark),
        _field("当前状态", row.status),
    ]
    return {
        "completeness": _completeness(fields, ["去向类型"]),
        "summary": f"就业去向登记 · {dest_label}",
        "sections": [_section("登记信息", fields)],
        "attachments": [],
        "sourceVersion": int(row.version or 0),
    }


_ADAPTERS: dict[str, Callable] = {
    "LEAVE": _leave_context,
    "AA_STATUS_CHANGE": _status_change_context,
    "AID": _aid_context,
    "FUNDING": _funding_context,
    "DISCIPLINE": _discipline_context,
    "DISCIPLINE_REMOVE": _discipline_remove_context,
    "AA_GRADE_TASK": _grade_task_context,
    "AA_GRADE_CHANGE": _grade_change_context,
    "AA_SCHEDULE_CHANGE": _schedule_change_context,
    "MESSAGE_CAMPAIGN": _message_campaign_context,
    "EMPLOYMENT_DESTINATION": _employment_destination_context,
}

# PROFILE_CORRECTION 只由 sandbox_service / demo seed 创建，仓库无生产 command 创建点。
# 不能为了让覆盖率数字好看而给不存在的正式业务造 adapter；但豁免必须显式、带理由，
# 并进入 coverage contract，未来一旦生产化就必须删除豁免并补正式 adapter。
_NON_PRODUCTION_CONTEXT_EXEMPTIONS: dict[str, str] = {
    "PROFILE_CORRECTION": "仅体验沙箱/演示学校种子创建，不存在生产业务 command",
}


def supported_biz_types() -> list[str]:
    return sorted(_ADAPTERS)


def non_production_exemptions() -> dict[str, str]:
    return dict(_NON_PRODUCTION_CONTEXT_EXEMPTIONS)


def context_coverage_snapshot() -> dict:
    return {
        "supported": supported_biz_types(),
        "nonProductionExemptions": non_production_exemptions(),
    }


def assert_action_context(context: dict, expected_source_version) -> None:
    """supported Context 必须完整且携带用户实际看过的 sourceVersion。"""
    context = context or {}
    biz_type = str(context.get("sourceBizType") or "").upper()
    if biz_type not in _ADAPTERS:
        return
    completeness = context.get("completeness")
    if completeness != FULL:
        raise AppException(
            "APPROVAL_CONTEXT_INCOMPLETE",
            f"业务记录不完整或无法读取（{completeness}），暂不能执行审批动作，请刷新后重试",
            http_status=409,
        )
    if expected_source_version is None:
        raise AppException(
            "APPROVAL_CONTEXT_VERSION_REQUIRED",
            "当前审批需要业务版本快照，请刷新审批详情后重试",
            http_status=409,
        )
    actual = context.get("sourceVersion")
    if actual is None or int(expected_source_version) != int(actual):
        raise AppException(
            "APPROVAL_CONTEXT_VERSION_CONFLICT",
            "业务记录内容已发生变化，请刷新后重试",
            http_status=409,
        )


def resolve_context(db, instance, *, for_update: bool = False) -> dict:
    """把 WorkflowInstance 解析成审批端 Context；动作事务可锁源业务行。"""
    biz_type = str(getattr(instance, "source_biz_type", "") or "").upper()
    base = {
        "contextVersion": CONTEXT_VERSION,
        "sourceBizType": biz_type,
        "sourceBizId": str(getattr(instance, "source_biz_id", "") or ""),
        "sourceVersion": None,
        "versionGuardRequired": biz_type in _ADAPTERS,
        "completeness": UNSUPPORTED,
        "summary": "",
        "sections": [],
        "attachments": [],
        "note": "",
    }
    adapter = _ADAPTERS.get(biz_type)
    if not adapter:
        if biz_type in _NON_PRODUCTION_CONTEXT_EXEMPTIONS:
            base["note"] = (
                f"业务类型 {biz_type} 为非生产审批类型："
                f"{_NON_PRODUCTION_CONTEXT_EXEMPTIONS[biz_type]}"
            )
        else:
            base["note"] = (
                f"业务类型 {biz_type or '（空）'} 尚未接入审批业务上下文，"
                "详情页无法展示原始业务事实；这不代表该申请没有内容。"
            )
        return base
    try:
        result = adapter(db, instance, for_update=for_update)
    except Exception as exc:  # noqa: BLE001 —— 单域故障不得拖垮整个审批详情
        base["completeness"] = ERROR
        base["note"] = f"业务信息读取失败（{type(exc).__name__}），请稍后重试"
        return base
    base.update(result)
    return base
