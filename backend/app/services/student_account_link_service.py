"""学生主档 ↔ 登录账号绑定的唯一读写口（学生主档统一整改 阶段 C）。

所有「这个账号是哪个学生」「这个学生的账号是谁」的问题都必须问本模块，
不得再各处写 `User.login_name == StudentProfile.student_no`——那条隐式约定正是
学号一更正就登录不到、收不到消息的根因。

迁移期口径：链接表由 alembic 回填，但可能存在回填不到的学生（账号后建、学号改过等）。
因此读取提供 `allow_legacy_fallback`：找不到链接时可临时退回登录名匹配并**记指标**，
让迁移期不炸；写入路径一律要求真实链接，不接受兜底。
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select

from app.models.student_account_link import (LINK_ACTIVE, LINK_REVOKED, LINK_SUSPENDED,
                                             StudentAccountLink)

log = logging.getLogger("app.student_account_link")


def _safe_query(fn, what: str):
    """读取绑定失败时降级为「查不到」，绝不让它把登录/发消息整条链路带崩。

    典型场景：代码已升级但迁移尚未执行，t_student_account_link 不存在。
    此时若把异常抛出去，全体学生将无法登录——远比「暂时退回按学号匹配」严重。
    失败一律记 warning，便于运维发现「该跑迁移了」。
    """
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - 读取侧降级，不掩盖写入错误
        log.warning("student_account_link_unavailable op=%s err=%s", what, type(exc).__name__)
        return None


def _active(db, tenant_id: int, **where):
    stmt = select(StudentAccountLink).where(
        StudentAccountLink.tenant_id == int(tenant_id),
        StudentAccountLink.link_status == LINK_ACTIVE,
        StudentAccountLink.is_deleted.is_(False))
    for col, val in where.items():
        stmt = stmt.where(getattr(StudentAccountLink, col) == val)
    return db.scalars(stmt).first()


def get_student_id_by_user(db, *, tenant_id: int, user_id, allow_legacy_fallback: bool = False,
                           login_name: str | None = None) -> int | None:
    """账号 → 学生主档 id。"""
    if not user_id:
        return None
    row = _safe_query(lambda: _active(db, tenant_id, user_id=int(user_id)),
                      "get_student_id_by_user")
    if row is not None:
        return int(row.student_id)
    if not allow_legacy_fallback or not login_name:
        return None
    return _legacy_student_id_by_login_name(db, tenant_id=tenant_id, login_name=login_name,
                                            user_id=user_id)


def get_user_id_by_student(db, *, tenant_id: int, student_id) -> int | None:
    """学生主档 id → 账号。无绑定返回 None（调用方据此统计 ACCOUNT_UNLINKED）。"""
    if not student_id:
        return None
    row = _safe_query(lambda: _active(db, tenant_id, student_id=int(student_id)),
                      "get_user_id_by_student")
    return int(row.user_id) if row is not None else None


def _legacy_student_id_by_login_name(db, *, tenant_id: int, login_name: str,
                                     user_id=None) -> int | None:
    """迁移期兜底：按历史约定 login_name == student_no 找学生，并记指标。

    命中说明该账号尚未回填链接——属于需要修的数据，不是正常路径，因此打 warning
    而不是静默通过；等指标归零即可删除本函数。
    """
    from app.models import StudentProfile

    s = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == int(tenant_id),
        StudentProfile.student_no == str(login_name),
        StudentProfile.is_deleted.is_(False))).first()
    if s is None:
        return None
    log.warning("student_account_link_missing tenant=%s user=%s login_name=%s student_id=%s",
                tenant_id, user_id, login_name, s.id)
    return int(s.id)


def bind_in_session(db, *, tenant_id: int, student_id: int, user_id: int,
                    source: str = "MANUAL", login_name: str | None = None,
                    student_no: str | None = None, remark: str | None = None) -> StudentAccountLink:
    """建立绑定（调用方事务内，不 commit）。

    幂等：同一 (student, user) 已 ACTIVE 时直接返回；学生或账号已绑到别处则报错，
    换绑必须先显式解绑，避免一个账号悄悄从一个学生转到另一个学生。
    """
    from app.core.exceptions import AppException

    exist = _active(db, tenant_id, student_id=int(student_id))
    if exist is not None:
        if int(exist.user_id) == int(user_id):
            return exist
        raise AppException("DATA_CONFLICT",
                           f"该学生已绑定其它登录账号（user_id={exist.user_id}），"
                           "请先解绑再重新绑定", http_status=409)
    taken = _active(db, tenant_id, user_id=int(user_id))
    if taken is not None:
        raise AppException("DATA_CONFLICT",
                           f"该登录账号已绑定其它学生（student_id={taken.student_id}），"
                           "请先解绑再重新绑定", http_status=409)

    row = StudentAccountLink(
        tenant_id=int(tenant_id), student_id=int(student_id), user_id=int(user_id),
        link_status=LINK_ACTIVE, source=source, bound_login_name=login_name,
        bound_student_no=student_no, bound_at=datetime.utcnow(), remark=remark)
    db.add(row)
    db.flush()
    return row


def suspend_by_student_in_session(db, *, tenant_id: int, student_id: int,
                                  remark: str | None = None) -> int:
    """学生作废/回收时暂停绑定（不解绑、不动账号本身）。

    只改链接状态：账号是否停用、是否强制改密属于账号管理职责，
    在这里顺手关账号会让「恢复学籍」与「恢复登录」被绑死。
    """
    row = _active(db, tenant_id, student_id=int(student_id))
    if row is None:
        return 0
    row.link_status = LINK_SUSPENDED
    row.unbound_at = datetime.utcnow()
    if remark:
        row.remark = remark
    row.version = int(row.version or 0) + 1
    return 1


def reactivate_by_student_in_session(db, *, tenant_id: int, student_id: int,
                                     remark: str | None = None) -> int:
    """学生恢复时重新启用被暂停的绑定；账号状态仍不动。"""
    row = db.scalars(select(StudentAccountLink).where(
        StudentAccountLink.tenant_id == int(tenant_id),
        StudentAccountLink.student_id == int(student_id),
        StudentAccountLink.link_status == LINK_SUSPENDED,
        StudentAccountLink.is_deleted.is_(False))).first()
    if row is None:
        return 0
    # 恢复前确认该账号没有在此期间被绑给别人
    taken = _active(db, tenant_id, user_id=int(row.user_id))
    if taken is not None:
        return 0
    row.link_status = LINK_ACTIVE
    row.unbound_at = None
    if remark:
        row.remark = remark
    row.version = int(row.version or 0) + 1
    return 1


def revoke_in_session(db, *, tenant_id: int, student_id: int, remark: str | None = None) -> int:
    """人工解绑（换账号、误绑纠正）。历史行保留，便于追溯。"""
    row = _active(db, tenant_id, student_id=int(student_id))
    if row is None:
        return 0
    row.link_status = LINK_REVOKED
    row.unbound_at = datetime.utcnow()
    if remark:
        row.remark = remark
    row.version = int(row.version or 0) + 1
    return 1


def resolve_user_id_for_student(db, *, tenant_id: int, student_id, student_no: str | None = None,
                                require_active_account: bool = True) -> int | None:
    """给某个学生发消息时找他的账号：先查绑定，绑定缺失时按学号兜底并记指标。

    面向「已知学生 → 要给他发通知」的场景（调课变更、实习催交、消息 outbox 等）。
    这些地方以前各写一遍 `login_name == student_no`，学号一改就发错人或发不出去。
    """
    from app.models import User

    uid = get_user_id_by_student(db, tenant_id=tenant_id, student_id=student_id)
    if uid:
        if not require_active_account:
            return uid
        ok = db.scalar(select(User.id).where(
            User.id == uid, User.tenant_id == int(tenant_id),
            User.is_deleted.is_(False), User.status == "ACTIVE"))
        return int(ok) if ok else None

    if not student_no:
        return None
    conds = [User.tenant_id == int(tenant_id), User.login_name == str(student_no),
             User.user_type == "STUDENT", User.is_deleted.is_(False)]
    if require_active_account:
        conds.append(User.status == "ACTIVE")
    got = db.scalar(select(User.id).where(*conds))
    if got:
        log.warning("student_account_link_missing_on_notify tenant=%s student_id=%s no=%s",
                    tenant_id, student_id, student_no)
        return int(got)
    return None


def active_user_ids_for_students(db, *, tenant_id: int, student_ids) -> dict:
    """批量：学生 id → 账号 id（消息受众用，避免逐个查）。"""
    ids = [int(x) for x in (student_ids or []) if x]
    if not ids:
        return {}
    rows = _safe_query(lambda: db.scalars(select(StudentAccountLink).where(
        StudentAccountLink.tenant_id == int(tenant_id),
        StudentAccountLink.student_id.in_(ids),
        StudentAccountLink.link_status == LINK_ACTIVE,
        StudentAccountLink.is_deleted.is_(False))).all(), "active_user_ids_for_students")
    return {int(r.student_id): int(r.user_id) for r in (rows or [])}
