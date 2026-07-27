"""四端学生本人身份解析安全门面。

所有移动端与学生PC共用的 resolve_student 均优先稳定 studentId 和账号绑定；
迁移期学号/姓名兜底必须显式记日志，禁止静默猜中他人。
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from . import mobile_student_service as _legacy
from . import student_account_link_service as link_service

log = logging.getLogger("app.student_identity")


def _numeric_user_id(user: dict) -> int | None:
    raw = str((user or {}).get("userId") or "").strip()
    for prefix in ("db-", "u_"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    return int(raw) if raw.isdigit() else None


def resolve_student(db, user: dict):
    """稳定解析当前账号对应学生；无法唯一证明时返回 None。"""
    from app.models import StudentProfile

    u = user or {}
    tenant_id = _legacy._tid()
    base = select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False),
    )

    student_id = u.get("studentId")
    if student_id:
        try:
            row = db.scalars(base.where(StudentProfile.id == int(student_id))).first()
        except (TypeError, ValueError):
            row = None
        if row:
            return row
        log.warning(
            "student_identity_stale_token tenant=%s user=%s student_id=%s",
            tenant_id, u.get("userId"), student_id,
        )

    user_id = _numeric_user_id(u)
    login_name = str(u.get("loginName") or u.get("studentNo") or "").strip() or None
    if user_id:
        linked_id = link_service.get_student_id_by_user(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            allow_legacy_fallback=True,
            login_name=login_name,
        )
        if linked_id:
            row = db.scalars(base.where(StudentProfile.id == int(linked_id))).first()
            if row:
                return row
        # 有真实账号ID却无法建立绑定证据时必须停止，不能继续按姓名猜人。
        log.warning(
            "student_identity_unresolved_account tenant=%s user=%s login=%s",
            tenant_id, user_id, login_name,
        )
        return None

    # 仅兼容没有数据库账号ID的旧令牌/历史演示身份；每次命中均记迁移告警。
    student_no = str(u.get("studentNo") or "").strip()
    if student_no:
        rows = db.scalars(base.where(StudentProfile.student_no == student_no)).all()
        if len(rows) == 1:
            log.warning(
                "student_identity_legacy_student_no tenant=%s no=%s student_id=%s",
                tenant_id, student_no, rows[0].id,
            )
            return rows[0]
        if len(rows) > 1:
            log.error("student_identity_ambiguous_student_no tenant=%s no=%s", tenant_id, student_no)
            return None

    name = str(u.get("realName") or "").strip()
    if name:
        rows = db.scalars(base.where(StudentProfile.real_name == name)).all()
        if len(rows) == 1:
            log.warning(
                "student_identity_legacy_name tenant=%s name=%s student_id=%s",
                tenant_id, name, rows[0].id,
            )
            return rows[0]
        if len(rows) > 1:
            log.error("student_identity_ambiguous_name tenant=%s name=%s", tenant_id, name)
    return None


# 原模块中的所有调用点在运行时统一读取这个函数；外部后续 import 也会取得安全实现。
_legacy.resolve_student = resolve_student
