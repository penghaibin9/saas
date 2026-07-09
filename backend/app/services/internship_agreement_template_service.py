"""岗位实习中心 · 实习协议模板库服务（DB_ENABLED=true 走本模块）。

协议模板配置主数据：CRUD + 状态机（DRAFT/ENABLED/DISABLED/ARCHIVED）+ 默认模板（同租户同类型唯一）
+ 适用范围（学院/专业/年级/批次）+ 变量说明 + 正文。
横切：租户隔离 + is_deleted 软删 + 审计到 t_internship_audit_trail(target_type=AGREEMENT_TEMPLATE)。

数据范围：协议模板为校级配置主数据，默认按租户可见；
如需按学院限定（学院实习负责人只看本院模板），在 _scope_filter 处接入 resolve_teacher_scope（预留）。

隔离：本文件不引用实习学生/打卡/周报/毕设等表；仅读写 t_internship_agreement_template + 审计表。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import InternshipAgreementTemplate, InternshipAuditTrail
from app.services.db_service import _iso, _tid, session

STATUS_LABEL = {"DRAFT": "草稿", "ENABLED": "启用中", "DISABLED": "已停用", "ARCHIVED": "已归档"}
STATUS_TONE = {"DRAFT": "default", "ENABLED": "success", "DISABLED": "warning", "ARCHIVED": "default"}

# 标准协议变量字典（供前端「模板变量说明」预置，协议渲染时按 key 占位替换）
VARIABLE_PRESETS = [
    {"key": "studentName", "label": "学生姓名", "example": "张三"},
    {"key": "studentNo", "label": "学号", "example": "2023115001"},
    {"key": "className", "label": "班级", "example": "软件2301"},
    {"key": "collegeName", "label": "学院", "example": "信息工程学院"},
    {"key": "majorName", "label": "专业", "example": "软件技术"},
    {"key": "companyName", "label": "企业名称", "example": "华信智能科技有限公司"},
    {"key": "positionName", "label": "岗位名称", "example": "前端开发实习生"},
    {"key": "mentorName", "label": "企业导师", "example": "李导师"},
    {"key": "teacherName", "label": "指导教师", "example": "王老师"},
    {"key": "internPeriod", "label": "实习时间", "example": "2026-03-01 至 2026-06-30"},
    {"key": "internStartDate", "label": "实习开始日期", "example": "2026-03-01"},
    {"key": "internEndDate", "label": "实习结束日期", "example": "2026-06-30"},
    {"key": "schoolName", "label": "学校名称", "example": "XX职业技术学院"},
    {"key": "signDate", "label": "签订日期", "example": "2026-02-20"},
]

# 状态机允许的动作 → 目标态
_ACTION_TARGET = {"ENABLE": "ENABLED", "DISABLE": "DISABLED", "ARCHIVE": "ARCHIVED"}
# 各动作允许的前置态
_ACTION_FROM = {"ENABLE": {"DRAFT", "DISABLED"}, "DISABLE": {"ENABLED"},
                "ARCHIVE": {"DRAFT", "ENABLED", "DISABLED"}}


def _op_name() -> str:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统"


def _op_id():
    u = get_current_user_ctx() or {}
    return u.get("userId")


def _trail(db, tpl_id: int, action: str, detail: dict | None = None):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=tpl_id, target_type="AGREEMENT_TEMPLATE",
                                action=action, operator_name=_op_name(), detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _row(t: InternshipAgreementTemplate, *, full: bool = False) -> dict:
    base = {
        "id": str(t.id), "name": t.name, "category": t.category or "",
        "version": t.template_version, "status": t.status,
        "statusLabel": STATUS_LABEL.get(t.status, t.status),
        "statusTone": STATUS_TONE.get(t.status, "default"),
        "isDefault": bool(t.is_default),
        "scopeCollegeIds": t.scope_college_ids or [],
        "scopeMajorIds": t.scope_major_ids or [],
        "scopeGrades": t.scope_grades or [],
        "scopeBatchIds": t.scope_batch_ids or [],
        "scopeSummary": _scope_summary(t),
        "remark": t.remark or "",
        "updatedAt": _iso(t.updated_at), "createdAt": _iso(t.created_at),
    }
    if full:
        base.update({
            "body": t.body or "",
            "variables": t.variables or [],
            "enabledAt": _iso(t.enabled_at), "disabledAt": _iso(t.disabled_at),
            "archivedAt": _iso(t.archived_at), "archivedBy": t.archived_by or "",
        })
    return base


def _scope_summary(t: InternshipAgreementTemplate) -> str:
    parts = []
    if t.scope_college_ids:
        parts.append(f"学院×{len(t.scope_college_ids)}")
    if t.scope_major_ids:
        parts.append(f"专业×{len(t.scope_major_ids)}")
    if t.scope_grades:
        parts.append("、".join(str(g) for g in t.scope_grades))
    if t.scope_batch_ids:
        parts.append(f"批次×{len(t.scope_batch_ids)}")
    return " / ".join(parts) if parts else "全校通用"


def _get(db, template_id: str) -> InternshipAgreementTemplate:
    try:
        tid = int(template_id)
    except (TypeError, ValueError):
        raise not_found("协议模板不存在")
    t = db.scalar(select(InternshipAgreementTemplate).where(
        InternshipAgreementTemplate.id == tid,
        InternshipAgreementTemplate.tenant_id == _tid(),
        InternshipAgreementTemplate.is_deleted.is_(False)))
    if not t:
        raise not_found("协议模板不存在")
    return t


def _apply_scope(t, body) -> None:
    """把 create/update body 的适用范围/变量写入模型（None 表示不改）。"""
    if getattr(body, "scopeCollegeIds", None) is not None:
        t.scope_college_ids = body.scopeCollegeIds
    if getattr(body, "scopeMajorIds", None) is not None:
        t.scope_major_ids = body.scopeMajorIds
    if getattr(body, "scopeGrades", None) is not None:
        t.scope_grades = body.scopeGrades
    if getattr(body, "scopeBatchIds", None) is not None:
        t.scope_batch_ids = body.scopeBatchIds
    if getattr(body, "variables", None) is not None:
        t.variables = [v.model_dump() if hasattr(v, "model_dump") else dict(v) for v in body.variables]


# ═══════════ 查询 ═══════════

def list_templates(page: int = 1, page_size: int = 20, *, keyword=None, status=None,
                   category=None, college_id=None, major_id=None, grade=None, batch_id=None) -> tuple:
    with session() as db:
        conds = [InternshipAgreementTemplate.tenant_id == _tid(),
                 InternshipAgreementTemplate.is_deleted.is_(False)]
        if keyword:
            like = f"%{keyword.strip()}%"
            conds.append(or_(InternshipAgreementTemplate.name.like(like),
                             InternshipAgreementTemplate.category.like(like)))
        if status:
            conds.append(InternshipAgreementTemplate.status == status)
        if category:
            conds.append(InternshipAgreementTemplate.category == category)
        total = db.scalar(select(func.count()).select_from(InternshipAgreementTemplate).where(*conds)) or 0
        rows = db.scalars(select(InternshipAgreementTemplate).where(*conds)
                          .order_by(InternshipAgreementTemplate.is_default.desc(),
                                    InternshipAgreementTemplate.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        items = [_row(r) for r in rows]
    # JSON 范围筛选在应用层做（跨方言稳妥；数据量为配置级，规模小）
    if college_id:
        items = [x for x in items if str(college_id) in [str(i) for i in x["scopeCollegeIds"]]]
    if major_id:
        items = [x for x in items if str(major_id) in [str(i) for i in x["scopeMajorIds"]]]
    if grade:
        items = [x for x in items if str(grade) in [str(i) for i in x["scopeGrades"]]]
    if batch_id:
        items = [x for x in items if str(batch_id) in [str(i) for i in x["scopeBatchIds"]]]
    return items, total


def get_template(template_id: str) -> dict:
    with session() as db:
        t = _get(db, template_id)
        data = _row(t, full=True)
        trails = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(),
            InternshipAuditTrail.target_type == "AGREEMENT_TEMPLATE",
            InternshipAuditTrail.target_id == t.id)
            .order_by(InternshipAuditTrail.id.desc()).limit(50)).all()
        data["auditTrail"] = [{"action": a.action, "operator": a.operator_name or "",
                               "detail": a.detail_json or {}, "occurredAt": _iso(a.occurred_at)}
                              for a in trails]
        return data


def template_stats() -> dict:
    with session() as db:
        conds = [InternshipAgreementTemplate.tenant_id == _tid(),
                 InternshipAgreementTemplate.is_deleted.is_(False)]
        rows = db.scalars(select(InternshipAgreementTemplate).where(*conds)).all()
    by_status = {}
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    return {"total": len(rows),
            "byStatus": [{"status": k, "label": STATUS_LABEL.get(k, k), "count": v}
                         for k, v in by_status.items()],
            "defaultCount": sum(1 for r in rows if r.is_default)}


def variable_presets() -> list:
    return VARIABLE_PRESETS


# ═══════════ 写操作 ═══════════

def create_template(body) -> dict:
    with session() as db:
        t = InternshipAgreementTemplate(
            tenant_id=_tid(), name=body.name.strip(), category=(body.category or None),
            template_version=(body.version or "v1.0"), body=body.body or None,
            remark=(body.remark or None), status="DRAFT", is_default=False,
            created_by=_op_id(), updated_by=_op_id())
        _apply_scope(t, body)
        db.add(t)
        db.flush()
        _trail(db, t.id, "CREATE", {"name": t.name, "version": t.template_version})
        db.commit()
        db.refresh(t)
        return _row(t, full=True)


def update_template(template_id: str, body) -> dict:
    with session() as db:
        t = _get(db, template_id)
        if t.status == "ARCHIVED":
            raise AppException("STATUS_CONFLICT", "已归档模板不可编辑")
        if body.name is not None:
            t.name = body.name.strip()
        if body.category is not None:
            t.category = body.category or None
        if body.version is not None:
            t.template_version = body.version
        if body.body is not None:
            t.body = body.body or None
        if body.remark is not None:
            t.remark = body.remark or None
        _apply_scope(t, body)
        t.updated_by = _op_id()
        _trail(db, t.id, "UPDATE", {"name": t.name, "version": t.template_version})
        db.commit()
        db.refresh(t)
        return _row(t, full=True)


def set_status(template_id: str, action: str, reason: str = "") -> dict:
    action = (action or "").upper()
    if action not in _ACTION_TARGET:
        raise AppException("VALIDATION_ERROR", f"未知动作：{action}（支持 ENABLE/DISABLE/ARCHIVE）")
    with session() as db:
        t = _get(db, template_id)
        if t.status not in _ACTION_FROM[action]:
            raise AppException("STATUS_CONFLICT",
                               f"当前状态「{STATUS_LABEL.get(t.status, t.status)}」不允许执行「{action}」")
        now = datetime.utcnow()
        t.status = _ACTION_TARGET[action]
        if action == "ENABLE":
            t.enabled_at = now
        elif action == "DISABLE":
            t.disabled_at = now
            t.is_default = False  # 停用即失去默认资格
        elif action == "ARCHIVE":
            t.archived_at = now
            t.archived_by = _op_name()
            t.is_default = False  # 归档即失去默认资格
        t.updated_by = _op_id()
        _trail(db, t.id, action, {"reason": reason} if reason else {})
        db.commit()
        db.refresh(t)
        return _row(t, full=True)


def set_default(template_id: str, on: bool = True) -> dict:
    """设为/取消默认模板。设为默认要求状态=启用中；同租户同类型仅一个默认。"""
    with session() as db:
        t = _get(db, template_id)
        if on:
            if t.status != "ENABLED":
                raise AppException("STATUS_CONFLICT", "只有「启用中」的模板可设为默认")
            # 清掉同租户同类型的其它默认
            others = db.scalars(select(InternshipAgreementTemplate).where(
                InternshipAgreementTemplate.tenant_id == _tid(),
                InternshipAgreementTemplate.is_deleted.is_(False),
                InternshipAgreementTemplate.is_default.is_(True),
                InternshipAgreementTemplate.id != t.id)).all()
            for o in others:
                if (o.category or "") == (t.category or ""):
                    o.is_default = False
            t.is_default = True
        else:
            t.is_default = False
        t.updated_by = _op_id()
        _trail(db, t.id, "SET_DEFAULT" if on else "UNSET_DEFAULT",
               {"category": t.category or ""})
        db.commit()
        db.refresh(t)
        return _row(t, full=True)
