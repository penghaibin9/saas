"""R10 教务统计不可变快照。

实时 overview 继续作为当前态；本服务只冻结某次真实聚合的范围、筛选、口径结果和哈希，
不反向修改业务表，也不允许更新历史快照。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import is_super_admin
from app.services.db_service import _tid, session

from . import academic_affairs_stats_facade as _stats

_SCHOOL_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}


def _ctx() -> dict:
    return get_current_user_ctx() or {}


def _operator() -> str:
    ctx = _ctx()
    return str(ctx.get("userId") or ctx.get("loginName") or ctx.get("realName") or "")


def _role(user=None) -> str:
    return str((user or _ctx()).get("currentRoleCode") or "").upper()


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def payload_hash(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _parse_as_of(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _audit(db, snapshot_id, action, detail=""):
    from app.models import AffairsAuditTrail

    ctx = _ctx()
    db.add(AffairsAuditTrail(
        tenant_id=_tid(),
        biz_type="AA_STATS_SNAPSHOT",
        biz_id=int(snapshot_id) if snapshot_id else None,
        action=action,
        operator=_operator(),
        role_name=str(ctx.get("currentRoleCode") or ""),
        detail=str(detail or "")[:990],
        occurred_at=datetime.utcnow(),
    ))


def create_snapshot(user, *, term_id=None, college_id=None, major_id=None,
                    snapshot_type="OVERVIEW", reason="") -> dict:
    """先按当前用户真实数据范围计算，再冻结完整结果；原因用于审计而非口径。"""
    reason_text = str(reason or "").strip()
    if len(reason_text) < 5:
        raise AppException("VALIDATION_ERROR", "生成统计快照须填写不少于5字的用途说明")
    kind = str(snapshot_type or "OVERVIEW").strip().upper()
    if kind != "OVERVIEW":
        raise AppException("VALIDATION_ERROR", "当前仅支持OVERVIEW教务总览快照")

    with session() as scope_db:
        scope = _snapshot_scope(scope_db, user, write=True)
        _require_filter_in_scope(scope, college_id)

    data = _stats.overview(
        user,
        term_id=int(term_id) if term_id else None,
        college_id=int(college_id) if college_id else None,
        major_id=int(major_id) if major_id else None,
    )
    frozen = {
        "snapshotType": kind,
        "scope": data.get("scope") or {},
        "filters": data.get("filters") or {},
        "indicators": data.get("indicators") or [],
        "sourceAsOf": data.get("asOf"),
        "schemaVersion": 1,
    }
    digest = payload_hash(frozen)

    from app.models.academic_affairs_r10 import AaStatsSnapshot
    with session() as db:
        row = AaStatsSnapshot(
            tenant_id=_tid(),
            snapshot_type=kind,
            term_id=int(term_id) if term_id else None,
            college_id=int(college_id) if college_id else None,
            major_id=int(major_id) if major_id else None,
            scope_json=canonical_json(frozen["scope"]),
            filters_json=canonical_json(frozen["filters"]),
            payload_json=canonical_json(frozen),
            payload_hash=digest,
            source_as_of=_parse_as_of(data.get("asOf")),
            generated_at=datetime.utcnow(),
            generated_by=_operator(),
            status="FROZEN",
        )
        db.add(row)
        db.flush()
        _audit(
            db,
            row.id,
            "STATS_SNAPSHOT_CREATE",
            (
                f"type={kind};termId={term_id or '-'};collegeId={college_id or '-'};"
                f"majorId={major_id or '-'};hash={digest};reason={reason_text}"
            ),
        )
        db.commit()
        db.refresh(row)
        return _row(row, include_payload=True)


def _snapshot_scope(db, user, *, write=False):
    """统计快照使用独立数据范围；普通任课教师默认无权读取或创建。"""
    from app.core.affairs_security import build_affairs_context

    role = _role(user)
    if is_super_admin(user) or role in _SCHOOL_ROLES:
        return {"all": True, "collegeIds": set()}
    context = build_affairs_context(user or {}, db)
    college_ids = {int(value) for value in (context.college_ids or set())}
    if role in {"COLLEGE_ADMIN", "COLLEGE_SA"} and college_ids:
        return {"all": False, "collegeIds": college_ids}
    action = "创建" if write else "查看"
    raise no_permission(f"当前身份无权{action}教务统计冻结快照")


def _require_filter_in_scope(scope, college_id):
    if scope["all"]:
        return
    if not college_id or int(college_id) not in scope["collegeIds"]:
        raise no_permission("统计快照学院范围不在当前授权内")


def _loads(raw, fallback):
    try:
        return json.loads(raw or "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _row(row, *, include_payload=False) -> dict:
    result = {
        "snapshotId": str(row.id),
        "snapshotType": row.snapshot_type,
        "termId": str(row.term_id) if row.term_id else None,
        "collegeId": str(row.college_id) if row.college_id else None,
        "majorId": str(row.major_id) if row.major_id else None,
        "scope": _loads(row.scope_json, {}),
        "filters": _loads(row.filters_json, {}),
        "payloadHash": row.payload_hash,
        "sourceAsOf": row.source_as_of.isoformat() if row.source_as_of else None,
        "generatedAt": row.generated_at.isoformat() if row.generated_at else None,
        "generatedBy": row.generated_by or "",
        "status": row.status,
        "immutable": True,
    }
    if include_payload:
        result["payload"] = _loads(row.payload_json, {})
    return result


def list_snapshots(user, *, term_id=None, snapshot_type=None, page=1, page_size=50) -> tuple[list[dict], int]:
    from app.models.academic_affairs_r10 import AaStatsSnapshot

    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 50)))
    with session() as db:
        scope = _snapshot_scope(db, user)
        query = db.query(AaStatsSnapshot).filter(
            AaStatsSnapshot.tenant_id == _tid(),
            AaStatsSnapshot.status == "FROZEN",
            AaStatsSnapshot.is_deleted.is_(False),
        )
        if not scope["all"]:
            query = query.filter(AaStatsSnapshot.college_id.in_(sorted(scope["collegeIds"])))
        if term_id:
            query = query.filter(AaStatsSnapshot.term_id == int(term_id))
        if snapshot_type:
            query = query.filter(AaStatsSnapshot.snapshot_type == str(snapshot_type).upper())
        total = query.count()
        rows = query.order_by(AaStatsSnapshot.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return [_row(row) for row in rows], total


def get_snapshot(user, snapshot_id) -> dict:
    from app.models.academic_affairs_r10 import AaStatsSnapshot

    with session() as db:
        scope = _snapshot_scope(db, user)
        row = db.query(AaStatsSnapshot).filter(
            AaStatsSnapshot.id == int(snapshot_id),
            AaStatsSnapshot.tenant_id == _tid(),
            AaStatsSnapshot.status == "FROZEN",
            AaStatsSnapshot.is_deleted.is_(False),
        ).first()
        if not row:
            raise not_found("统计快照不存在")
        if not scope["all"] and (not row.college_id or int(row.college_id) not in scope["collegeIds"]):
            _audit(db, row.id, "STATS_SNAPSHOT_ACCESS_DENIED", "scope mismatch")
            db.commit()
            raise no_permission("该统计快照不在当前可见范围")
        parsed = _loads(row.payload_json, {})
        if payload_hash(parsed) != row.payload_hash:
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "统计快照内容哈希校验失败，禁止作为正式统计依据",
                details={"snapshotId": str(row.id)},
                http_status=409,
            )
        _audit(db, row.id, "STATS_SNAPSHOT_READ", f"hash={row.payload_hash}")
        db.commit()
        return _row(row, include_payload=True)
