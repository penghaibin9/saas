"""移动教师聚合安全门面。

原聚合实现保留在 ``_mobile_teacher_service_impl``；本门面在所有既有调用入口前统一施加：
- 学校教职工 userType 白名单；
- SECURITY_AUDITOR 不得自动获得业务全校范围；
- classId 必须与本人辅导员/班主任关系取交集；
- 范围/聚合故障不得静默伪装为空列表或 0。

这样既保留大量既有移动业务接口，又把共享安全不变量集中在单一入口，避免漏修某个 Router。
"""
from __future__ import annotations

import logging

from sqlalchemy import func, or_, select

from app.core.exceptions import AppException
from app.core.security import MOBILE_STAFF_USER_TYPES
from app.services import _mobile_teacher_service_impl as _impl

_LOG = logging.getLogger(__name__)


def is_teacher_user(user: dict | None) -> bool:
    u = user or {}
    return bool(u.get("userId")) and (u.get("userType") or "").strip().upper() in MOBILE_STAFF_USER_TYPES


def _require_teacher(user: dict | None):
    """移动教师端统一白名单；空类型、未知类型、学生、家长和平台身份全部拒绝。"""
    u = user or {}
    if not is_teacher_user(u):
        raise AppException("NO_PERMISSION", "该接口仅学校教职工移动端可用", http_status=403)
    return u


def _strict_real_name_is_ambiguous(real_name: str) -> bool:
    """姓名仅作历史兼容；无法证明唯一时按歧义处理，禁止 fail-open。"""
    name = (real_name or "").strip()
    if not name:
        return True
    try:
        with _impl._session() as db:
            from app.models import User
            rows = db.scalars(select(User.id).where(
                User.tenant_id == _impl._tid(),
                User.real_name == name,
                User.is_deleted.is_(False),
            ).limit(2)).all()
        return len(rows) != 1
    except Exception:  # noqa: BLE001
        _LOG.exception("mobile_teacher_identity_uniqueness_unavailable")
        return True


def resolve_teacher_scope(user: dict) -> dict:
    """复用既有范围解析，但校级审计角色不能被当成业务全校管理员。"""
    u = _require_teacher(user)
    return _impl._original_resolve_teacher_scope(u)


def _parse_class_id(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "classId 必须为正整数", http_status=400)
    if parsed <= 0:
        raise AppException("VALIDATION_ERROR", "classId 必须为正整数", http_status=400)
    return parsed


def _authorize_requested_class(scope_mode: str, requested: int | None,
                               allowed_class_ids: set[int]) -> int | None:
    """纯函数门禁：非全校管理员传入的 classId 必须属于本人关系集合。"""
    if scope_mode == "ADMIN_TENANT":
        return requested
    if requested is not None and requested not in allowed_class_ids:
        raise AppException("NO_DATA_SCOPE", "该班级不在你的负责范围内", http_status=403)
    return requested


def my_students(user: dict, class_id=None) -> dict:
    """我的学生：先求 allowed_class_ids，再接受客户端 classId，禁止跨班枚举。"""
    u = _require_teacher(user)
    if not _impl.db_enabled():
        return {"hasData": False, "items": [], "total": 0, "note": "演示模式"}
    scope = resolve_teacher_scope(u)
    requested = _parse_class_id(class_id)
    tid = _impl._tid()
    with _impl._session() as db:
        from app.models import SchoolClass, StudentProfile

        allowed_class_ids: set[int] = set()
        if scope["mode"] != "ADMIN_TENANT":
            numeric_uid = _impl._teacher_numeric_id(u)
            if numeric_uid is None:
                return {"hasData": False, "items": [], "total": 0,
                        "note": "未识别到教师身份，无法匹配班级"}
            allowed_class_ids = set(db.scalars(select(SchoolClass.id).where(
                SchoolClass.tenant_id == tid,
                SchoolClass.is_deleted.is_(False),
                or_(SchoolClass.counselor_id == numeric_uid,
                    SchoolClass.head_teacher_id == numeric_uid),
            )).all())

        _authorize_requested_class(scope["mode"], requested, allowed_class_ids)
        conds = [StudentProfile.tenant_id == tid, StudentProfile.is_deleted.is_(False)]
        if requested is not None:
            conds.append(StudentProfile.class_id == requested)
        elif scope["mode"] != "ADMIN_TENANT":
            if not allowed_class_ids:
                return {"hasData": False, "items": [], "total": 0, "note": "暂无负责班级"}
            conds.append(StudentProfile.class_id.in_(allowed_class_ids))

        total = db.scalar(select(func.count()).select_from(StudentProfile).where(*conds)) or 0
        rows = db.scalars(select(StudentProfile).where(*conds)
                          .order_by(StudentProfile.id.desc()).limit(200)).all()
        class_ids = {row.class_id for row in rows if row.class_id}
        class_map = {}
        if class_ids:
            class_map = {row.id: row.class_name for row in db.scalars(select(SchoolClass).where(
                SchoolClass.tenant_id == tid,
                SchoolClass.is_deleted.is_(False),
                SchoolClass.id.in_(class_ids),
            )).all()}
        items = [{
            "studentId": str(row.id),
            "studentNo": row.student_no,
            "name": row.real_name,
            "className": class_map.get(row.class_id, ""),
            "gender": row.gender or "",
            "stage": row.current_stage,
            "status": row.student_status,
        } for row in rows]
        return {"hasData": bool(items), "items": items, "total": int(total)}


def _metric_unavailable(kind: str, fn, exc: Exception):
    name = getattr(fn, "__qualname__", getattr(fn, "__name__", repr(fn)))
    _LOG.exception("mobile_teacher_aggregate_unavailable kind=%s source=%s", kind, name,
                   exc_info=exc)
    raise AppException(
        "METRIC_UNAVAILABLE",
        "移动工作台数据暂不可用，请稍后重试",
        http_status=503,
    ) from exc


def _total(fn, **kw):
    try:
        _, total = fn(1, 1, **kw)
        return total
    except AppException:
        raise
    except Exception as exc:  # noqa: BLE001
        _metric_unavailable("total", fn, exc)


def _safe_list(fn, page, ps, **kw):
    try:
        return fn(page, ps, **kw)
    except AppException:
        raise
    except Exception as exc:  # noqa: BLE001
        _metric_unavailable("list", fn, exc)


# 保存原范围函数，随后把内部实现使用到的共享符号全部替换成安全版本。
_impl._original_resolve_teacher_scope = _impl.resolve_teacher_scope
_impl._ADMIN_ROLES = set(_impl._ADMIN_ROLES) - {"SECURITY_AUDITOR"}
_impl.is_teacher_user = is_teacher_user
_impl._require_teacher = _require_teacher
_impl._real_name_is_ambiguous = _strict_real_name_is_ambiguous
_impl.resolve_teacher_scope = resolve_teacher_scope
_impl.my_students = my_students
_impl._total = _total
_impl._safe_list = _safe_list

# 保持原模块的全部公开/私有属性兼容，既有 Router 和测试无需改 import。
for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)


def __getattr__(name: str):
    return getattr(_impl, name)


__all__ = [name for name in dir(_impl) if not name.startswith("__")]
