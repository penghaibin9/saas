"""消息受众解析：按规则展开为 user_id 列表，并生成预览指纹。

V1 优先支持：CLASS（行政班）、COLLEGE、ALL_STUDENT、ALL_STAFF、ALL_USERS、PERSON。
权限与数据范围在此裁定；调用方不得自行传入人员列表。
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission
from app.core.permissions import has_permission
from app.services.db_service import _tid, session

# 预览令牌内存缓存（单进程开发/测试）；生产多 worker 应以指纹重算为准，令牌仅辅助。
_PREVIEW_CACHE: dict[str, dict] = {}
_PREVIEW_TTL_SEC = 15 * 60


def _uid(user: dict | None) -> int:
    from app.services.message_identity import resolve_message_user_id
    return resolve_message_user_id(user)


def _normalize_rules(audiences: list[dict]) -> list[dict]:
    out = []
    for a in audiences or []:
        out.append({
            "type": str(a.get("type") or a.get("audienceType") or "").upper(),
            "includeOrExclude": str(a.get("includeOrExclude") or "INCLUDE").upper(),
            "targetIds": [int(x) for x in (a.get("targetIds") or []) if x is not None],
            "targetCodes": [str(x) for x in (a.get("targetCodes") or []) if x],
            "includeChildren": bool(a.get("includeChildren", True)),
        })
    return out


def _require_publish_scope(user: dict, rules: list[dict]) -> None:
    """按受众类型检查发布权限；无权限直接 403。"""
    types = {r["type"] for r in rules if r["includeOrExclude"] == "INCLUDE"}
    if not types:
        raise AppException("VALIDATION_ERROR", "请至少选择一个接收范围",
                           details={"reason": "AUDIENCE_EMPTY"}, http_status=422)

    if types & {"ALL_USERS", "ALL_STUDENT", "ALL_STAFF"}:
        if types & {"ALL_USERS"} and not has_permission(user, "workbench.message.schoolAll.publish"):
            raise no_permission("无全校师生发布权限")
        if "ALL_STUDENT" in types and not (
            has_permission(user, "workbench.message.schoolStudent.publish")
            or has_permission(user, "workbench.message.schoolAll.publish")
        ):
            raise no_permission("无全校学生发布权限")
        if "ALL_STAFF" in types and not (
            has_permission(user, "workbench.message.schoolStaff.publish")
            or has_permission(user, "workbench.message.schoolAll.publish")
        ):
            raise no_permission("无全校教职工发布权限")

    if types & {"COLLEGE", "MAJOR", "GRADE"}:
        if not (
            has_permission(user, "workbench.message.college.publish")
            or has_permission(user, "workbench.message.schoolAll.publish")
            or has_permission(user, "workbench.message.schoolStudent.publish")
        ):
            raise no_permission("无学院范围发布权限")

    if types & {"CLASS", "ADMIN_CLASS", "TEACHING_CLASS"}:
        if not (
            has_permission(user, "workbench.message.class.publish")
            or has_permission(user, "workbench.message.college.publish")
            or has_permission(user, "workbench.message.schoolStudent.publish")
            or has_permission(user, "workbench.message.schoolAll.publish")
        ):
            raise no_permission("无班级范围发布权限")

    if not has_permission(user, "workbench.message.publish"):
        # 入口码兜底：有具体 publish 码即可
        if not any(has_permission(user, c) for c in (
            "workbench.message.class.publish",
            "workbench.message.college.publish",
            "workbench.message.schoolStudent.publish",
            "workbench.message.schoolStaff.publish",
            "workbench.message.schoolAll.publish",
        )):
            raise no_permission("无消息发布权限")


def _allowed_class_ids(db, user: dict) -> set[int] | None:
    """None=全租户；空集=fail-closed。"""
    from app.core.affairs_security import build_affairs_context
    ctx = build_affairs_context(user, db)
    return ctx.allowed_class_ids(db)


# 绑定表是否已建（部署未跑迁移时为 False）。表建好后不会消失，故进程级缓存一次即可。
_LINK_TABLE_READY: bool | None = None


def link_table_ready(db) -> bool:
    """检测 t_student_account_link 是否存在。

    存在意义：代码升级但迁移未执行时，直接 JOIN 不存在的表会让**全校消息发不出去**。
    检测到表缺失就整体退回历史 JOIN（login_name == student_no），
    功能可用但不解决改号问题——由运维看到 warning 后补跑迁移。
    """
    global _LINK_TABLE_READY
    if _LINK_TABLE_READY is None:
        try:
            from sqlalchemy import inspect as sa_inspect
            _LINK_TABLE_READY = "t_student_account_link" in sa_inspect(db.get_bind()).get_table_names()
        except Exception:  # noqa: BLE001
            _LINK_TABLE_READY = False
        if not _LINK_TABLE_READY:
            import logging
            logging.getLogger("app.message_audience").warning(
                "student_account_link_table_missing 消息受众退回学号匹配，请执行数据库迁移")
    return _LINK_TABLE_READY


def _link_join():
    """学生 → 账号绑定（阶段 C）。返回 (target, onclause) 供 outerjoin 展开。

    **必须用 outerjoin**：INNER 会把尚未回填绑定的学生整批过滤掉，
    _user_join 里的迁移期兜底分支就再也命中不到。
    """
    from sqlalchemy import and_

    from app.models import StudentProfile
    from app.models.student_account_link import LINK_ACTIVE, StudentAccountLink
    return StudentAccountLink, and_(
        StudentAccountLink.tenant_id == StudentProfile.tenant_id,
        StudentAccountLink.student_id == StudentProfile.id,
        StudentAccountLink.link_status == LINK_ACTIVE,
        StudentAccountLink.is_deleted.is_(False),
    )


def _user_join(active_only: bool = False):
    """账号连接：优先按绑定的 user_id，绑定缺失时退回历史约定 login_name == student_no。

    两个分支互斥（后者要求 link 行为 NULL），不会把同一学生匹配成两行。
    兜底只为迁移期存在：账号链接回填完成、指标归零后删除 or_ 的第二个分支，
    届时未绑定学生会如实计入 ACCOUNT_UNLINKED 而不是靠学号蒙对。
    """
    from sqlalchemy import and_, or_

    from app.models import StudentProfile, User
    from app.models.student_account_link import StudentAccountLink
    conds = [
        User.tenant_id == StudentProfile.tenant_id,
        User.is_deleted.is_(False),
        or_(
            User.id == StudentAccountLink.user_id,
            # 兜底按学号猜账号时必须确认是学生账号：学号与教师工号撞号会把
            # 面向学生的消息误发给教师（既有隐患，随本次改造一并收紧）。
            and_(StudentAccountLink.id.is_(None),
                 User.login_name == StudentProfile.student_no,
                 User.user_type == "STUDENT"),
        ),
    ]
    if active_only:
        conds.append(User.status == "ACTIVE")
    return User, and_(*conds)


def apply_student_account_joins(q, db, *, active_only: bool = False, inner_user: bool = False):
    """给「学生 → 账号」的查询挂上正确的 JOIN。

    绑定表就绪时：LEFT JOIN 绑定 + JOIN 账号（绑定优先，缺失按学号兜底）；
    表尚未建立（部署未跑迁移）时：整体退回历史 JOIN，保证消息还发得出去。
    四处受众查询都经本函数，避免各写一遍分支写歪。
    """
    from sqlalchemy import and_

    from app.models import StudentProfile, User
    if link_table_ready(db):
        q = q.outerjoin(*_link_join())
        target, onclause = _user_join(active_only=active_only)
        return q.join(target, onclause) if inner_user else q.outerjoin(target, onclause)

    conds = [
        User.tenant_id == StudentProfile.tenant_id,
        User.login_name == StudentProfile.student_no,
        User.user_type == "STUDENT",
        User.is_deleted.is_(False),
    ]
    if active_only:
        conds.append(User.status == "ACTIVE")
    return q.join(User, and_(*conds)) if inner_user else q.outerjoin(User, and_(*conds))


def _student_user_ids_by_classes(db, class_ids: set[int]) -> tuple[set[int], dict[str, int]]:
    """行政班 → 已开通账号的学生 user_id（student_no = User.login_name）。"""
    from app.models import StudentProfile, User
    from sqlalchemy import and_
    if not class_ids:
        return set(), {}
    q = select(User.id, StudentProfile.student_status, StudentProfile.status).select_from(StudentProfile)
    q = apply_student_account_joins(q, db)
    rows = db.execute(
        q.where(
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
            StudentProfile.class_id.in_(list(class_ids)),
        )
    ).all()
    user_ids: set[int] = set()
    excluded = {"ACCOUNT_UNLINKED": 0, "STUDENT_STATUS_EXCLUDED": 0, "ACCOUNT_DISABLED": 0}
    for uid, student_status, profile_status in rows:
        st = str(student_status or "").upper()
        ps = str(profile_status or "").upper()
        if st in ("GRADUATED", "WITHDRAWN", "SUSPENDED", "MERGED", "RECYCLED") or ps in ("DISABLED", "DELETED"):
            excluded["STUDENT_STATUS_EXCLUDED"] += 1
            continue
        if not uid:
            excluded["ACCOUNT_UNLINKED"] += 1
            continue
        user_ids.add(int(uid))
    return user_ids, excluded


def _student_user_ids_by_colleges(
    db, college_ids: set[int], allowed_classes: set[int] | None
) -> tuple[set[int], dict[str, int], set[int]]:
    from app.models import StudentProfile, User
    from sqlalchemy import and_
    if not college_ids:
        return set(), {}, set()
    conds = [
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
        StudentProfile.college_id.in_(list(college_ids)),
    ]
    if allowed_classes is not None:
        if not allowed_classes:
            return set(), {}, set()
        conds.append(StudentProfile.class_id.in_(list(allowed_classes)))
    q = select(User.id, StudentProfile.student_status, StudentProfile.status,
               StudentProfile.class_id).select_from(StudentProfile)
    q = apply_student_account_joins(q, db)
    rows = db.execute(q.where(*conds)).all()
    user_ids: set[int] = set()
    excluded = {"ACCOUNT_UNLINKED": 0, "STUDENT_STATUS_EXCLUDED": 0}
    class_set: set[int] = set()
    for uid, student_status, profile_status, class_id in rows:
        st = str(student_status or "").upper()
        ps = str(profile_status or "").upper()
        if st in ("GRADUATED", "WITHDRAWN", "SUSPENDED", "MERGED", "RECYCLED") or ps in ("DISABLED", "DELETED"):
            excluded["STUDENT_STATUS_EXCLUDED"] += 1
            continue
        if class_id:
            class_set.add(int(class_id))
        if not uid:
            excluded["ACCOUNT_UNLINKED"] += 1
            continue
        user_ids.add(int(uid))
    return user_ids, excluded, class_set


def _all_student_user_ids(db, allowed_classes: set[int] | None) -> tuple[set[int], dict[str, int]]:
    from app.models import StudentProfile, User
    from sqlalchemy import and_
    conds = [
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    ]
    if allowed_classes is not None:
        if not allowed_classes:
            return set(), {}
        conds.append(StudentProfile.class_id.in_(list(allowed_classes)))
    rows_q = (
        select(User.id)
        .select_from(StudentProfile)
    )
    # 本查询语义是「只要已开通账号的学生」，故 User 用 INNER；
    # 绑定表始终 LEFT（INNER 会把尚未回填的学生整批漏掉）。
    rows = db.execute(
        apply_student_account_joins(rows_q, db, active_only=True, inner_user=True)
        .where(*conds)
    ).all()
    unlinked_q = select(StudentProfile.id).select_from(StudentProfile)
    unlinked = db.execute(
        apply_student_account_joins(unlinked_q, db).where(*conds, User.id.is_(None))
    ).all()
    return {int(r[0]) for r in rows}, {"ACCOUNT_UNLINKED": len(unlinked)}


def _staff_user_ids(db) -> set[int]:
    from app.models import User
    rows = db.scalars(select(User.id).where(
        User.tenant_id == _tid(),
        User.is_deleted.is_(False),
        User.status == "ACTIVE",
        User.user_type.in_(("TEACHER", "STAFF", "SCHOOL_ADMIN", "ADMIN")),
    )).all()
    return {int(x) for x in rows if x}


def resolve_audience(user: dict, audiences: list[dict],
                     recipient_types: list[str] | None = None) -> dict[str, Any]:
    """解析受众，返回 user_ids / breakdown / excluded / fingerprint。"""
    rules = _normalize_rules(audiences)
    _require_publish_scope(user, rules)
    rtypes = {str(x).upper() for x in (recipient_types or ["STUDENT"])}

    with session() as db:
        allowed = _allowed_class_ids(db, user)
        include: set[int] = set()
        exclude: set[int] = set()
        excluded_counts: dict[str, int] = {}
        class_set: set[int] = set()
        college_set: set[int] = set()

        for rule in rules:
            t = rule["type"]
            ids = set(rule["targetIds"])
            bucket = include if rule["includeOrExclude"] == "INCLUDE" else exclude

            if t in ("CLASS", "ADMIN_CLASS"):
                if allowed is not None:
                    illegal = ids - set(allowed)
                    if illegal:
                        raise no_permission("不可向范围外班级发布")
                    ids = ids & set(allowed) if ids else set(allowed)
                if not ids and allowed is not None:
                    ids = set(allowed)
                if not ids and allowed is None:
                    raise AppException("VALIDATION_ERROR", "请指定班级",
                                       details={"reason": "CLASS_REQUIRED"}, http_status=422)
                class_set |= ids
                uids, exc = _student_user_ids_by_classes(db, ids)
                bucket |= uids
                for k, v in exc.items():
                    excluded_counts[k] = excluded_counts.get(k, 0) + v

            elif t == "COLLEGE":
                if not ids:
                    raise AppException("VALIDATION_ERROR", "请选择学院",
                                       details={"reason": "COLLEGE_REQUIRED"}, http_status=422)
                college_set |= ids
                uids, exc, cids = _student_user_ids_by_colleges(db, ids, allowed)
                class_set |= cids
                bucket |= uids
                for k, v in exc.items():
                    excluded_counts[k] = excluded_counts.get(k, 0) + v

            elif t == "ALL_STUDENT":
                uids, exc = _all_student_user_ids(db, allowed)
                bucket |= uids
                for k, v in exc.items():
                    excluded_counts[k] = excluded_counts.get(k, 0) + v

            elif t == "ALL_STAFF":
                bucket |= _staff_user_ids(db)

            elif t == "ALL_USERS":
                uids, exc = _all_student_user_ids(db, None if has_permission(user, "workbench.message.schoolAll.publish") else allowed)
                bucket |= uids
                bucket |= _staff_user_ids(db)
                for k, v in exc.items():
                    excluded_counts[k] = excluded_counts.get(k, 0) + v

            elif t == "PERSON":
                bucket |= ids

            else:
                raise AppException("VALIDATION_ERROR", f"暂不支持的受众类型：{t}",
                                   details={"reason": "AUDIENCE_TYPE_UNSUPPORTED"}, http_status=422)

        final = include - exclude
        # recipient_types 过滤（V1：PERSON/ALL_* 已按类型写入；CLASS 默认学生）
        if rtypes == {"STAFF"}:
            staff = _staff_user_ids(db)
            final &= staff

        fingerprint = "sha256:" + hashlib.sha256(
            json.dumps({
                "rules": rules,
                "rtypes": sorted(rtypes),
                "users": sorted(final),
                "tenant": _tid(),
            }, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

        return {
            "userIds": sorted(final),
            "recipientCount": len(final),
            "breakdown": {
                "student": len(final) if "STAFF" not in rtypes or "STUDENT" in rtypes else 0,
                "staff": 0,
                "college": len(college_set),
                "class": len(class_set),
            },
            "excluded": [{"reasonCode": k, "count": v} for k, v in excluded_counts.items() if v],
            "audienceFingerprint": fingerprint,
            "rules": rules,
        }


def preview_audience(user: dict, audiences: list[dict],
                     recipient_types: list[str] | None = None) -> dict:
    resolved = resolve_audience(user, audiences, recipient_types)
    token = uuid.uuid4().hex
    expires = datetime.utcnow() + timedelta(seconds=_PREVIEW_TTL_SEC)
    _PREVIEW_CACHE[token] = {
        "userId": _uid(user),
        "tenantId": _tid(),
        "fingerprint": resolved["audienceFingerprint"],
        "userIds": resolved["userIds"],
        "rules": resolved["rules"],
        "expiresAt": expires,
    }
    # 清理过期
    now = datetime.utcnow()
    dead = [k for k, v in _PREVIEW_CACHE.items() if v["expiresAt"] < now]
    for k in dead:
        _PREVIEW_CACHE.pop(k, None)

    return {
        "previewToken": token,
        "audienceFingerprint": resolved["audienceFingerprint"],
        "expiresAt": expires.isoformat() + "Z",
        "recipientCount": resolved["recipientCount"],
        "breakdown": resolved["breakdown"],
        "excluded": resolved["excluded"],
    }


def consume_preview(user: dict, preview_token: str, audience_fingerprint: str) -> list[int]:
    """校验预览令牌与指纹，返回 user_id 列表；失效或不匹配则抛错。"""
    item = _PREVIEW_CACHE.get(preview_token)
    if not item:
        raise AppException("DATA_CONFLICT", "受众预览已失效，请重新预览",
                           details={"reason": "MESSAGE_AUDIENCE_CHANGED"})
    if item["expiresAt"] < datetime.utcnow():
        _PREVIEW_CACHE.pop(preview_token, None)
        raise AppException("DATA_CONFLICT", "受众预览已过期，请重新预览",
                           details={"reason": "MESSAGE_AUDIENCE_CHANGED"})
    if item["userId"] != _uid(user) or item["tenantId"] != _tid():
        raise no_permission("受众预览不属于当前用户")
    if item["fingerprint"] != audience_fingerprint:
        raise AppException("DATA_CONFLICT", "受众已变化，请重新确认人数",
                           details={"reason": "MESSAGE_AUDIENCE_CHANGED"})
    return list(item["userIds"])


def resolve_for_publish(
    user: dict,
    *,
    preview_token: str,
    audience_fingerprint: str,
    audiences: list[dict] | None = None,
    recipient_types: list[str] | None = None,
) -> list[int]:
    """发布时解析接收人：优先消费预览令牌；令牌因进程重启/过期丢失时，按已落库规则重算并校验指纹。

    这样「预览人数 > 0 → 确认发布」不会因内存预览缓存丢失而整单失败，发布记录也能落到库。
    """
    try:
        return consume_preview(user, preview_token, audience_fingerprint)
    except AppException as exc:
        details = getattr(exc, "details", None) or {}
        if details.get("reason") != "MESSAGE_AUDIENCE_CHANGED":
            raise
        if not audiences:
            raise
        resolved = resolve_audience(user, audiences, recipient_types or ["STUDENT", "STAFF"])
        if resolved["audienceFingerprint"] != audience_fingerprint:
            raise AppException(
                "DATA_CONFLICT",
                "受众已变化，请返回上一步重新预览后再发布",
                details={"reason": "MESSAGE_AUDIENCE_CHANGED"},
            )
        return list(resolved["userIds"])


def list_audience_options(user: dict, audience_type: str, keyword: str | None = None,
                         page_size: int = 100) -> dict:
    """发布页选择器数据：严格按权限与数据范围返回。"""
    at = str(audience_type or "").upper()
    kw = (keyword or "").strip().lower()
    if at == "CLASS":
        if not (
            has_permission(user, "workbench.message.class.publish")
            or has_permission(user, "workbench.message.college.publish")
            or has_permission(user, "workbench.message.schoolStudent.publish")
            or has_permission(user, "workbench.message.schoolAll.publish")
            or has_permission(user, "workbench.message.publish")
        ):
            raise no_permission("无班级发布权限")
        from app.models import SchoolClass
        with session() as db:
            allowed = _allowed_class_ids(db, user)
            q = select(SchoolClass).where(
                SchoolClass.tenant_id == _tid(),
                SchoolClass.is_deleted.is_(False),
                SchoolClass.status == "ACTIVE",
            )
            if allowed is not None:
                if not allowed:
                    return {"items": []}
                q = q.where(SchoolClass.id.in_(list(allowed)))
            rows = db.scalars(q.order_by(SchoolClass.class_name.asc()).limit(500)).all()
            items = []
            for c in rows:
                name = c.class_name or f"班级#{c.id}"
                if kw and kw not in name.lower() and kw not in str(c.id):
                    continue
                items.append({
                    "id": int(c.id),
                    "name": name,
                    "desc": (c.grade or "") + (f" · {c.class_code}" if getattr(c, "class_code", None) else ""),
                })
                if len(items) >= page_size:
                    break
            return {"items": items}

    if at == "COLLEGE":
        if not (
            has_permission(user, "workbench.message.college.publish")
            or has_permission(user, "workbench.message.schoolStudent.publish")
            or has_permission(user, "workbench.message.schoolAll.publish")
        ):
            raise no_permission("无学院发布权限")
        from app.models import College, StudentProfile
        with session() as db:
            allowed = _allowed_class_ids(db, user)
            if allowed is not None:
                if not allowed:
                    return {"items": []}
                college_ids = {
                    int(x) for x in db.scalars(select(StudentProfile.college_id).where(
                        StudentProfile.tenant_id == _tid(),
                        StudentProfile.is_deleted.is_(False),
                        StudentProfile.class_id.in_(list(allowed)),
                        StudentProfile.college_id.is_not(None),
                    )).all() if x
                }
            else:
                college_ids = {
                    int(x) for x in db.scalars(select(College.id).where(
                        College.tenant_id == _tid(),
                        College.is_deleted.is_(False),
                        College.status == "ACTIVE",
                    )).all() if x
                }
            if not college_ids:
                return {"items": []}
            rows = db.scalars(select(College).where(
                College.tenant_id == _tid(),
                College.id.in_(list(college_ids)),
                College.is_deleted.is_(False),
            ).order_by(College.college_name.asc())).all()
            items = []
            for c in rows:
                name = c.college_name or f"学院#{c.id}"
                if kw and kw not in name.lower():
                    continue
                items.append({"id": int(c.id), "name": name, "desc": c.code or ""})
                if len(items) >= page_size:
                    break
            return {"items": items}

    raise AppException("VALIDATION_ERROR", f"不支持的选项类型：{at}", http_status=422)


def audiences_from_campaign_rules(db, campaign_id: int) -> list[dict]:
    """从已落库的受众规则还原预览请求格式。"""
    from app.models import MessageAudience
    rows = db.scalars(select(MessageAudience).where(
        MessageAudience.tenant_id == _tid(),
        MessageAudience.campaign_id == int(campaign_id),
        MessageAudience.is_deleted.is_(False),
    )).all()
    out = []
    for r in rows:
        if r.rule_json and isinstance(r.rule_json, dict):
            out.append(r.rule_json)
            continue
        tids = [int(r.target_id)] if r.target_id else []
        out.append({
            "type": r.audience_type,
            "includeOrExclude": r.include_or_exclude or "INCLUDE",
            "targetIds": tids,
        })
    return out
