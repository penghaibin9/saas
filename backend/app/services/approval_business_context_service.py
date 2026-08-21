"""审批业务 Context 解析（V3 施工手册 TP-A06）。

问题
────────────────────────────────────────────────────────────
`approval_runtime_service.get_task()` 之前把 `attachments` 与 `diff` 硬编码成空
数组，审批详情里唯一的业务信息就是一句 "业务记录 {sourceBizId}"。老师在审批
请假、学籍异动、困难认定、违纪时，看不到任何足以支撑判断的事实，却要点通过。

定位
────────────────────────────────────────────────────────────
本模块是 **adapter 层**：按 `WorkflowInstance.source_biz_type` 找到对应业务域的
真实记录，把它投影成审批端能读的 Context。**不复制业务状态、不做判定、不写任何
数据**；业务域仍是自己的权威。

诚实原则（与 SP-D03 同一条）
────────────────────────────────────────────────────────────
- ``FULL``        找到业务记录且关键字段齐全。
- ``PARTIAL``     找到记录但关键字段缺失，不足以支撑完整判断。
- ``MISSING``     业务记录查不到（可能已被删除/软删）——审批对象已经不在了。
- ``UNSUPPORTED`` 该业务类型尚未接入 adapter。**明确说明"还没接"**，而不是返回
                  一个空 Context 让人以为"这条申请本来就没有内容"。
- ``ERROR``       读取业务域时真的出错。与 MISSING/UNSUPPORTED 严格区分。

敏感字段
────────────────────────────────────────────────────────────
困难认定的家庭情况说明等属于强敏感内容（模型注释已标注）。本模块默认只给出
`masked=True` 的占位，不把原文带进审批详情——明文查看必须走独立的授权与审计
通道，不能因为"老师在审批"就默认放行。
"""
from __future__ import annotations

from typing import Any, Callable

from app.services.db_service import _iso, _tid

CONTEXT_VERSION = 1

FULL = "FULL"
PARTIAL = "PARTIAL"
MISSING = "MISSING"
UNSUPPORTED = "UNSUPPORTED"
ERROR = "ERROR"

#: 强敏感字段的统一占位，不返回原文。
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


def _attachments(db, biz_type: str, biz_id: Any) -> list[dict]:
    """读取学工域通用附件表的真实附件。

    只投影展示所需的最小信息；是否可预览由公共文件中心的 ACL 决定，本模块不
    发放任何访问权限。
    """
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
# 只登记仓库里**真实会创建 WorkflowInstance** 的 source_biz_type。
# 手册点名的 COMPANY_CHANGE 目前全仓没有任何地方以该值建实例，为它写 adapter
# 等于为不存在的业务造代码，因此不登记——一旦将来真的接入 workflow，这里返回
# UNSUPPORTED 会明确提示需要补 adapter，而不是静默空白。
#
# EMPLOYMENT_DESTINATION（SP-E02/E04）已经是真实业务：
# employment_destination_submission_service.submit() 会创建
# WorkflowInstance(source_biz_type="EMPLOYMENT_DESTINATION")，第 5 个 adapter。

def _leave_context(db, instance) -> dict:
    from app.models import CsLeave

    row = db.get(CsLeave, int(instance.source_biz_id))
    if not row or row.is_deleted or int(row.tenant_id) != _tid():
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


def _status_change_context(db, instance) -> dict:
    from app.models import AaStatusChange

    row = db.get(AaStatusChange, int(instance.source_biz_id))
    if not row or row.is_deleted or int(row.tenant_id) != _tid():
        return {"completeness": MISSING, "summary": "学籍异动记录不存在或已删除",
                "sections": [], "attachments": [], "sourceVersion": None}
    fields = [
        _field("异动类型", row.change_type),
        _field("原学籍状态", row.from_status),
        _field("目标学籍状态", row.to_status),
    ]
    return {
        "completeness": _completeness(fields, ["异动类型", "目标学籍状态"]),
        "summary": f"学籍异动 · {row.change_type or '—'}",
        "sections": [_section("异动信息", fields)],
        "attachments": _attachments(db, "AA_STATUS_CHANGE", row.id),
        "sourceVersion": int(row.version or 0),
    }


def _aid_context(db, instance) -> dict:
    from app.models import AidApply

    row = db.get(AidApply, int(instance.source_biz_id))
    if not row or row.is_deleted or int(row.tenant_id) != _tid():
        return {"completeness": MISSING, "summary": "困难认定申请不存在或已删除",
                "sections": [], "attachments": [], "sourceVersion": None}
    fields = [
        _field("申请等级", row.apply_level),
        _field("辅导员建议等级", row.suggest_level),
        _field("班级评议得分", row.class_review_score),
        _field("班级评议排名", row.class_review_rank),
        # statement 在模型上被标注为「强敏感」，审批详情一律不带原文。
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


def _discipline_context(db, instance) -> dict:
    from app.models import DisciplineCase

    row = db.get(DisciplineCase, int(instance.source_biz_id))
    if not row or row.is_deleted or int(row.tenant_id) != _tid():
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


def _employment_destination_context(db, instance) -> dict:
    from app.models import EmpDestinationSubmission
    from app.modules.employment.services.employment_service import L_DEST

    row = db.get(EmpDestinationSubmission, int(instance.source_biz_id))
    if not row or row.is_deleted or int(row.tenant_id) != _tid():
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
        # 本域提交流程不收附件（city/contact 等字段是结构化文本，不是文件材料）；
        # 就业材料的正式证据由 EMPLOYMENT_MATERIAL FileBinding 单独承载（T5），
        # 不在这条提交记录上，如实返回空而不是伪造附件列表。
        "attachments": [],
        "sourceVersion": int(row.version or 0),
    }


_ADAPTERS: dict[str, Callable] = {
    "LEAVE": _leave_context,
    "AA_STATUS_CHANGE": _status_change_context,
    "AID": _aid_context,
    "DISCIPLINE": _discipline_context,
    "EMPLOYMENT_DESTINATION": _employment_destination_context,
}


def supported_biz_types() -> list[str]:
    return sorted(_ADAPTERS)


def resolve_context(db, instance) -> dict:
    """把一条 WorkflowInstance 解析成审批端可读的业务 Context。"""
    biz_type = str(getattr(instance, "source_biz_type", "") or "").upper()
    base = {
        "contextVersion": CONTEXT_VERSION,
        "sourceBizType": biz_type,
        "sourceBizId": str(getattr(instance, "source_biz_id", "") or ""),
        "sourceVersion": None,
        "completeness": UNSUPPORTED,
        "summary": "",
        "sections": [],
        "attachments": [],
        "note": "",
    }
    adapter = _ADAPTERS.get(biz_type)
    if not adapter:
        base["note"] = (
            f"业务类型 {biz_type or '（空）'} 尚未接入审批业务上下文，"
            "详情页无法展示原始业务事实；这不代表该申请没有内容。"
        )
        return base
    try:
        result = adapter(db, instance)
    except Exception as exc:  # noqa: BLE001 —— 单域故障不得拖垮整个审批详情
        base["completeness"] = ERROR
        base["note"] = f"业务信息读取失败（{type(exc).__name__}），请稍后重试"
        return base
    base.update(result)
    return base
