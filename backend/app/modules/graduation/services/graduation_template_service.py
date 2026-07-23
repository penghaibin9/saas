"""毕业设计中心 · 材料模板中心服务（材料/任务书/开题模板统一底座）。
状态机 DRAFT→ENABLED↔DISABLED→ARCHIVED；同租户同类型默认模板唯一；启用中方可设默认。
隔离说明：仅依赖毕设域模型与公共 db_service，不引用其它业务域。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import GraduationAuditTrail, GraduationTemplate
from app.services.db_service import _iso, _tid, session

TYPES = {"MATERIAL": "材料模板", "TASKBOOK": "任务书模板", "PROPOSAL": "开题模板"}
STATUS_LABEL = {"DRAFT": "草稿", "ENABLED": "启用中", "DISABLED": "已停用", "ARCHIVED": "已归档"}
# 各类型预置可用占位变量
DEFAULT_VARS = {
    "MATERIAL": ["学生姓名", "学号", "班级", "课题名称", "指导教师", "提交日期"],
    "TASKBOOK": ["学生姓名", "课题名称", "指导教师", "任务目标", "进度安排", "下达日期"],
    "PROPOSAL": ["学生姓名", "课题名称", "选题背景", "研究方案", "预期成果", "指导教师"],
}


def _op():
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("currentRoleCode") or ""


def _audit(db, bid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type="TEMPLATE", biz_id=str(bid), action=action,
                                operator=n, role_name=r, detail=detail, before_val=before,
                                after_val=after, occurred_at=datetime.now(timezone.utc)))


def _row(t: GraduationTemplate) -> dict:
    return {"id": str(t.id), "templateType": t.template_type,
            "templateTypeLabel": TYPES.get(t.template_type, t.template_type),
            "name": t.name, "version": t.template_version or "", "status": t.status,
            "statusLabel": STATUS_LABEL.get(t.status, t.status), "isDefault": t.is_default,
            "applicableNote": t.applicable_note or "", "remark": t.remark or "",
            "updateTime": _iso(t.updated_at)}


def _detail(t: GraduationTemplate) -> dict:
    r = _row(t)
    r.update({"content": t.content or "", "variables": t.variables_json or []})
    return r


def _get(db, tid) -> GraduationTemplate:
    t = db.get(GraduationTemplate, int(tid))
    if not t or t.is_deleted or t.tenant_id != _tid():
        raise not_found("模板不存在")
    return t


def variable_dict() -> dict:
    return {k: DEFAULT_VARS[k] for k in DEFAULT_VARS}


def list_templates(page, ps, template_type=None, status=None, keyword=None):
    with session() as db:
        q = select(GraduationTemplate).where(GraduationTemplate.tenant_id == _tid(),
                                             GraduationTemplate.is_deleted.is_(False))
        if template_type:
            q = q.where(GraduationTemplate.template_type == template_type)
        if status:
            q = q.where(GraduationTemplate.status == status)
        rows = db.scalars(q.order_by(GraduationTemplate.is_default.desc(),
                                     GraduationTemplate.id.desc())).all()
        items = [_row(t) for t in rows]
        if keyword:
            kw = keyword.strip()
            items = [i for i in items if kw in i["name"]]
        total = len(items)
        start = (max(1, page) - 1) * ps
        return items[start:start + ps], total


def get_template(tid) -> dict:
    with session() as db:
        return _detail(_get(db, tid))


def create_template(template_type, name, content=None, variables=None, applicable_note=None,
                    version=None, remark=None) -> dict:
    if template_type not in TYPES:
        raise AppException("VALIDATION_ERROR", "模板类型必须是 材料/任务书/开题")
    if not (name and name.strip()):
        raise AppException("VALIDATION_ERROR", "模板名称不能为空")
    with session() as db:
        t = GraduationTemplate(
            tenant_id=_tid(), template_type=template_type, name=name.strip(),
            template_version=(version or "v1").strip(), content=(content or "").strip() or None,
            variables_json=variables if variables is not None else DEFAULT_VARS.get(template_type, []),
            applicable_note=(applicable_note or "").strip() or None, status="DRAFT",
            is_default=False, remark=(remark or "").strip() or None)
        db.add(t)
        db.flush()
        _audit(db, t.id, "新建模板", f"{TYPES[template_type]}·{t.name}")
        db.commit()
        return _detail(t)


def update_template(tid, name=None, content=None, variables=None, applicable_note=None,
                   version=None, remark=None) -> dict:
    with session() as db:
        t = _get(db, tid)
        if t.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档模板不可编辑")
        if name and name.strip():
            t.name = name.strip()
        if content is not None:
            t.content = content.strip() or None
        if variables is not None:
            t.variables_json = variables
        if applicable_note is not None:
            t.applicable_note = applicable_note.strip() or None
        if version and version.strip():
            t.template_version = version.strip()
        if remark is not None:
            t.remark = remark.strip() or None
        _audit(db, t.id, "编辑模板", t.name)
        db.commit()
        return _detail(t)


_TRANSITIONS = {"ENABLE": ("ENABLED", ("DRAFT", "DISABLED")),
                "DISABLE": ("DISABLED", ("ENABLED",)),
                "ARCHIVE": ("ARCHIVED", ("DRAFT", "DISABLED"))}


def set_status(tid, action) -> dict:
    if action not in _TRANSITIONS:
        raise AppException("VALIDATION_ERROR", "非法操作")
    target, allowed = _TRANSITIONS[action]
    with session() as db:
        t = _get(db, tid)
        if t.status not in allowed:
            raise AppException("DATA_CONFLICT", f"当前状态「{STATUS_LABEL.get(t.status)}」不可执行该操作")
        before = t.status
        t.status = target
        if target in ("DISABLED", "ARCHIVED") and t.is_default:
            t.is_default = False  # 停用/归档自动失默认
        _audit(db, t.id, {"ENABLE": "启用模板", "DISABLE": "停用模板", "ARCHIVE": "归档模板"}[action],
               t.name, before, target)
        db.commit()
        return _detail(t)


def set_default(tid) -> dict:
    with session() as db:
        t = _get(db, tid)
        if t.status != "ENABLED":
            raise AppException("DATA_CONFLICT", "只有启用中的模板可设为默认")
        # 同类型其它默认失效
        for other in db.scalars(select(GraduationTemplate).where(
                GraduationTemplate.tenant_id == _tid(),
                GraduationTemplate.template_type == t.template_type,
                GraduationTemplate.is_default.is_(True),
                GraduationTemplate.is_deleted.is_(False))).all():
            if other.id != t.id:
                other.is_default = False
        t.is_default = True
        _audit(db, t.id, "设为默认模板", f"{TYPES[t.template_type]}·{t.name}")
        db.commit()
        return _detail(t)


def stats(template_type=None) -> dict:
    with session() as db:
        base = [GraduationTemplate.tenant_id == _tid(), GraduationTemplate.is_deleted.is_(False)]
        if template_type:
            base.append(GraduationTemplate.template_type == template_type)
        total = int(db.scalar(select(func.count()).select_from(GraduationTemplate).where(*base)) or 0)
        by_status = [{"status": s, "label": STATUS_LABEL[s],
                     "count": int(db.scalar(select(func.count()).select_from(GraduationTemplate).where(
                         *base, GraduationTemplate.status == s)) or 0)} for s in STATUS_LABEL]
        return {"total": total, "byStatus": by_status}
