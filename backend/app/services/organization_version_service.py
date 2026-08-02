"""SYS-04 组织变更版本与教职工任职。

组织仍由 ``t_college`` / ``t_major`` / ``t_class`` 承载，本服务提供两件现在缺失的能力：

1. **未来生效的组织调整**：变更先进版本草稿，激活时才落到实体表，并留下 before 快照供回滚。
   草稿和排期状态对当前查询零影响——这不是靠代码克制，而是因为变更根本没写进实体表。
2. **真实任职**：既有 ``counselor_id`` / ``head_teacher_id`` / ``secretary_id`` 只是三个字段，
   没有起止时间，"任职到期"无从谈起。这里补上带有效期的任职表，并按"定时任务 + 读取时校验"
   双保险失效，避免定时任务没跑到时过期任职仍然生效。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.organization_version import (ASSIGNMENT_SOURCE_MANUAL,
                                             ASSIGNMENT_STATUS_ACTIVE,
                                             ASSIGNMENT_STATUS_EXPIRED,
                                             ASSIGNMENT_STATUS_REVOKED,
                                             ASSIGNMENT_TYPES,
                                             ORG_CHANGE_CREATE,
                                             ORG_CHANGE_DISABLE,
                                             ORG_CHANGE_ENABLE,
                                             ORG_CHANGE_MOVE,
                                             ORG_CHANGE_RENAME,
                                             ORG_CHANGE_TYPES,
                                             ORG_TYPE_CLASS, ORG_TYPE_COLLEGE,
                                             ORG_TYPE_MAJOR, ORG_TYPES,
                                             ORG_VERSION_ACTIVATED,
                                             ORG_VERSION_DRAFT,
                                             ORG_VERSION_ROLLED_BACK,
                                             ORG_VERSION_SCHEDULED,
                                             ORG_VERSION_VALIDATED,
                                             OrgVersion, OrgVersionItem,
                                             StaffAssignment)

ALLOWED_VERSION_TRANSITIONS: dict[str, frozenset[str]] = {
    ORG_VERSION_DRAFT: frozenset({ORG_VERSION_VALIDATED}),
    ORG_VERSION_VALIDATED: frozenset({ORG_VERSION_DRAFT, ORG_VERSION_SCHEDULED, ORG_VERSION_ACTIVATED}),
    ORG_VERSION_SCHEDULED: frozenset({ORG_VERSION_VALIDATED, ORG_VERSION_ACTIVATED}),
    ORG_VERSION_ACTIVATED: frozenset({ORG_VERSION_ROLLED_BACK}),
    ORG_VERSION_ROLLED_BACK: frozenset(),
}


def _floor_seconds(value: datetime | None) -> datetime | None:
    """截断到秒。MySQL DATETIME 会把微秒四舍五入（.9 进位到下一秒），
    否则"立即任命"的任职其 effective_at 会比当前时间晚，读取时被判为尚未生效。"""
    return value.replace(microsecond=0) if value else value


def _now() -> datetime:
    return _floor_seconds(datetime.utcnow())


def _tenant_id(value: int | None = None) -> int:
    tenant_id = int(value or current_tenant_id() or 0)
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    return tenant_id


def _actor_id() -> int | None:
    user = get_current_user_ctx() or {}
    raw = user.get("userId") or user.get("id")
    try:
        return int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _session():
    return get_sessionmaker()()


def _models():
    from app.models import College, Major, SchoolClass

    return {ORG_TYPE_COLLEGE: College, ORG_TYPE_MAJOR: Major, ORG_TYPE_CLASS: SchoolClass}


def _name_field(org_type: str) -> str:
    return {
        ORG_TYPE_COLLEGE: "college_name",
        ORG_TYPE_MAJOR: "major_name",
        ORG_TYPE_CLASS: "class_name",
    }[org_type]


def _parent_field(org_type: str) -> str | None:
    return {ORG_TYPE_COLLEGE: None, ORG_TYPE_MAJOR: "college_id", ORG_TYPE_CLASS: "major_id"}[org_type]


def _load_node(db, tenant_id: int, org_type: str, node_id: int):
    """按租户加载组织节点。跨租户 id 一律当作不存在，不泄露其他学校数据是否存在。"""
    model = _models()[org_type]
    node = db.scalars(
        select(model).where(model.tenant_id == tenant_id, model.id == int(node_id), model.is_deleted.is_(False))
    ).first()
    if not node:
        raise not_found(f"组织节点不存在（{org_type}:{node_id}）")
    return node


# ── 影响面计算 ──────────────────────────────────────────────────────────────
def compute_impact(org_type: str, node_id: int, *, tenant_id: int | None = None) -> dict:
    """移动/停用一个节点会牵动谁。页面在激活前必须展示这个。"""
    tid = _tenant_id(tenant_id)
    from app.models import Major, SchoolClass, StudentProfile

    with _session() as db:
        _load_node(db, tid, org_type, node_id)
        majors = classes = students = 0
        if org_type == ORG_TYPE_COLLEGE:
            major_ids = [
                r[0]
                for r in db.execute(
                    select(Major.id).where(
                        Major.tenant_id == tid, Major.college_id == int(node_id), Major.is_deleted.is_(False)
                    )
                )
            ]
            majors = len(major_ids)
            class_ids = (
                [
                    r[0]
                    for r in db.execute(
                        select(SchoolClass.id).where(
                            SchoolClass.tenant_id == tid,
                            SchoolClass.major_id.in_(major_ids),
                            SchoolClass.is_deleted.is_(False),
                        )
                    )
                ]
                if major_ids
                else []
            )
            classes = len(class_ids)
        elif org_type == ORG_TYPE_MAJOR:
            class_ids = [
                r[0]
                for r in db.execute(
                    select(SchoolClass.id).where(
                        SchoolClass.tenant_id == tid,
                        SchoolClass.major_id == int(node_id),
                        SchoolClass.is_deleted.is_(False),
                    )
                )
            ]
            classes = len(class_ids)
        else:
            class_ids = [int(node_id)]

        if class_ids:
            students = int(
                db.scalar(
                    select(func.count())
                    .select_from(StudentProfile)
                    .where(
                        StudentProfile.tenant_id == tid,
                        StudentProfile.class_id.in_(class_ids),
                        StudentProfile.is_deleted.is_(False),
                    )
                )
                or 0
            )

        assignments = int(
            db.scalar(
                select(func.count())
                .select_from(StaffAssignment)
                .where(
                    StaffAssignment.tenant_id == tid,
                    StaffAssignment.org_type == org_type,
                    StaffAssignment.org_node_id == int(node_id),
                    StaffAssignment.status == ASSIGNMENT_STATUS_ACTIVE,
                    StaffAssignment.is_deleted.is_(False),
                )
            )
            or 0
        )
        return {
            "orgType": org_type,
            "orgNodeId": str(node_id),
            "affectedMajors": majors,
            "affectedClasses": classes,
            "affectedStudents": students,
            "affectedAssignments": assignments,
        }


# ── 版本 ────────────────────────────────────────────────────────────────────
def _version_row(version: OrgVersion, items: list[OrgVersionItem] | None = None) -> dict:
    payload = {
        "versionId": str(version.id),
        "versionCode": version.version_code,
        "versionName": version.version_name,
        "status": version.status,
        "effectiveAt": version.effective_at.isoformat() if version.effective_at else None,
        "activatedAt": version.activated_at.isoformat() if version.activated_at else None,
        "rolledBackAt": version.rolled_back_at.isoformat() if version.rolled_back_at else None,
        "reason": version.reason,
        "impact": version.impact_json or {},
        "version": int(version.version or 0),
        "allowedTransitions": sorted(ALLOWED_VERSION_TRANSITIONS.get(version.status, frozenset())),
    }
    if items is not None:
        payload["items"] = [
            {
                "itemId": str(i.id),
                "changeType": i.change_type,
                "orgType": i.org_type,
                "orgNodeId": str(i.org_node_id) if i.org_node_id else None,
                "payload": i.payload_json or {},
                "before": i.before_json or {},
                "appliedAt": i.applied_at.isoformat() if i.applied_at else None,
            }
            for i in items
        ]
    return payload


def create_version(*, version_name: str, reason: str, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        version = OrgVersion(
            tenant_id=tid,
            version_code=f"ORGV-{uuid.uuid4().hex[:10].upper()}",
            version_name=version_name or "组织调整",
            status=ORG_VERSION_DRAFT,
            reason=reason,
            created_by=_actor_id(),
            updated_by=_actor_id(),
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        return _version_row(version, [])


def add_change(
    version_id: int,
    *,
    change_type: str,
    org_type: str,
    payload: dict,
    org_node_id: int | None = None,
    tenant_id: int | None = None,
) -> dict:
    tid = _tenant_id(tenant_id)
    ctype = str(change_type or "").upper()
    otype = str(org_type or "").upper()
    if ctype not in ORG_CHANGE_TYPES:
        raise AppException("VALIDATION_ERROR", f"未知变更类型：{ctype}", details={"allowed": list(ORG_CHANGE_TYPES)})
    if otype not in ORG_TYPES:
        raise AppException("VALIDATION_ERROR", f"未知组织类型：{otype}", details={"allowed": list(ORG_TYPES)})

    with _session() as db:
        version = _load_version(db, tid, version_id)
        if version.status != ORG_VERSION_DRAFT:
            raise AppException("ORG_VERSION_LOCKED", "只有草稿状态的版本可以调整变更项", http_status=409)

        if ctype == ORG_CHANGE_CREATE:
            if not str(payload.get("name") or "").strip():
                raise AppException("VALIDATION_ERROR", "新建组织必须提供名称")
            parent_field = _parent_field(otype)
            if parent_field:
                parent_id = payload.get("parentId")
                if not parent_id:
                    raise AppException("VALIDATION_ERROR", "该组织类型必须指定上级")
                parent_type = ORG_TYPE_COLLEGE if otype == ORG_TYPE_MAJOR else ORG_TYPE_MAJOR
                _load_node(db, tid, parent_type, int(parent_id))  # 跨租户上级会 404
        else:
            if not org_node_id:
                raise AppException("VALIDATION_ERROR", "该变更类型必须指定组织节点")
            _load_node(db, tid, otype, int(org_node_id))
            if ctype == ORG_CHANGE_MOVE:
                new_parent = payload.get("parentId")
                parent_field = _parent_field(otype)
                if not parent_field:
                    raise AppException("VALIDATION_ERROR", "学院没有上级，无法移动")
                if not new_parent:
                    raise AppException("VALIDATION_ERROR", "移动必须指定新的上级")
                parent_type = ORG_TYPE_COLLEGE if otype == ORG_TYPE_MAJOR else ORG_TYPE_MAJOR
                _load_node(db, tid, parent_type, int(new_parent))
            if ctype == ORG_CHANGE_RENAME and not str(payload.get("name") or "").strip():
                raise AppException("VALIDATION_ERROR", "改名必须提供新名称")

        item = OrgVersionItem(
            tenant_id=tid,
            version_id=int(version.id),
            change_type=ctype,
            org_type=otype,
            org_node_id=int(org_node_id) if org_node_id else None,
            payload_json=payload or {},
            created_by=_actor_id(),
            updated_by=_actor_id(),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return {
            "itemId": str(item.id),
            "changeType": item.change_type,
            "orgType": item.org_type,
            "orgNodeId": str(item.org_node_id) if item.org_node_id else None,
            "payload": item.payload_json,
        }


def _load_version(db, tenant_id: int, version_id: int, *, lock: bool = False) -> OrgVersion:
    stmt = select(OrgVersion).where(
        OrgVersion.tenant_id == tenant_id,
        OrgVersion.id == int(version_id),
        OrgVersion.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    version = db.scalars(stmt).first()
    if not version:
        raise not_found("组织版本不存在")
    return version


def _load_items(db, tenant_id: int, version_id: int) -> list[OrgVersionItem]:
    return list(
        db.scalars(
            select(OrgVersionItem)
            .where(
                OrgVersionItem.tenant_id == tenant_id,
                OrgVersionItem.version_id == int(version_id),
                OrgVersionItem.is_deleted.is_(False),
            )
            .order_by(OrgVersionItem.id)
        ).all()
    )


def get_version(version_id: int, *, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        version = _load_version(db, tid, version_id)
        return _version_row(version, _load_items(db, tid, version_id))


def list_versions(*, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        versions = db.scalars(
            select(OrgVersion)
            .where(OrgVersion.tenant_id == tid, OrgVersion.is_deleted.is_(False))
            .order_by(OrgVersion.id.desc())
        ).all()
        return {"items": [_version_row(v) for v in versions]}


def transition_version(
    version_id: int,
    target_status: str,
    *,
    reason: str,
    expected_version: int,
    effective_at: datetime | None = None,
    tenant_id: int | None = None,
) -> dict:
    tid = _tenant_id(tenant_id)
    target = str(target_status or "").upper()
    with _session() as db:
        version = _load_version(db, tid, version_id, lock=True)
        if int(version.version or 0) != int(expected_version):
            raise AppException(
                "VERSION_CONFLICT", "该组织版本已被其他人修改，请刷新后重试", http_status=409,
                details={"currentVersion": int(version.version or 0)},
            )
        current = version.status
        if target == current:
            return _version_row(version, _load_items(db, tid, version_id))
        if target not in ALLOWED_VERSION_TRANSITIONS.get(current, frozenset()):
            raise AppException(
                "STATE_TRANSITION_DENIED", f"不允许从 {current} 变更为 {target}", http_status=409,
                details={"allowed": sorted(ALLOWED_VERSION_TRANSITIONS.get(current, frozenset()))},
            )

        items = _load_items(db, tid, version_id)
        if target in (ORG_VERSION_VALIDATED, ORG_VERSION_ACTIVATED) and not items:
            raise AppException("VALIDATION_ERROR", "空版本没有可执行的变更")

        if target == ORG_VERSION_VALIDATED:
            impacts = [
                compute_impact(i.org_type, i.org_node_id, tenant_id=tid)
                for i in items
                if i.org_node_id and i.change_type in (ORG_CHANGE_MOVE, ORG_CHANGE_DISABLE)
            ]
            version.impact_json = {"items": impacts}
        if target == ORG_VERSION_SCHEDULED:
            effective_at = _floor_seconds(effective_at)
            if not effective_at:
                raise AppException("VALIDATION_ERROR", "排期必须提供生效时间")
            if effective_at <= _now():
                raise AppException("VALIDATION_ERROR", "生效时间必须晚于当前时间")
            version.effective_at = effective_at
        if target == ORG_VERSION_ACTIVATED:
            _apply_items(db, tid, items)
            version.activated_at = _now()
        if target == ORG_VERSION_ROLLED_BACK:
            _revert_items(db, tid, items)
            version.rolled_back_at = _now()

        version.status = target
        version.reason = reason or version.reason
        version.updated_by = _actor_id()
        version.version = int(version.version or 0) + 1
        db.commit()
        db.refresh(version)
        _audit(target, version.id, reason)
        return _version_row(version, _load_items(db, tid, version_id))


def _apply_items(db, tenant_id: int, items: list[OrgVersionItem]) -> None:
    """把变更真正写进实体表，同时保存 before 快照供回滚。"""
    models = _models()
    for item in items:
        name_field = _name_field(item.org_type)
        parent_field = _parent_field(item.org_type)
        payload = item.payload_json or {}

        if item.change_type == ORG_CHANGE_CREATE:
            model = models[item.org_type]
            row = model(tenant_id=tenant_id, status="ACTIVE", created_by=_actor_id(), updated_by=_actor_id())
            setattr(row, name_field, str(payload.get("name")))
            if parent_field:
                setattr(row, parent_field, int(payload.get("parentId")))
            if payload.get("code"):
                row.code = str(payload["code"])
            db.add(row)
            db.flush()
            item.org_node_id = int(row.id)
            item.before_json = {"created": True}
        else:
            node = _load_node(db, tenant_id, item.org_type, item.org_node_id)
            before: dict[str, Any] = {"status": node.status, name_field: getattr(node, name_field)}
            if parent_field:
                before[parent_field] = getattr(node, parent_field)
            item.before_json = before

            if item.change_type == ORG_CHANGE_RENAME:
                setattr(node, name_field, str(payload.get("name")))
            elif item.change_type == ORG_CHANGE_MOVE:
                setattr(node, parent_field, int(payload.get("parentId")))
            elif item.change_type == ORG_CHANGE_DISABLE:
                node.status = "INACTIVE"
            elif item.change_type == ORG_CHANGE_ENABLE:
                node.status = "ACTIVE"
            node.updated_by = _actor_id()
        item.applied_at = _now()


def _revert_items(db, tenant_id: int, items: list[OrgVersionItem]) -> None:
    """按 before 快照回滚。新建的节点停用而不是物理删除，避免下游引用悬空。"""
    for item in reversed(items):
        before = item.before_json or {}
        if not before or not item.org_node_id:
            continue
        node = _load_node(db, tenant_id, item.org_type, item.org_node_id)
        if before.get("created"):
            node.status = "INACTIVE"
        else:
            for field, value in before.items():
                if hasattr(node, field):
                    setattr(node, field, value)
        node.updated_by = _actor_id()
        item.applied_at = None


def activate_due_versions(*, now: datetime | None = None) -> dict:
    """激活到期的排期版本。幂等：已激活的不会再次应用。"""
    moment = now or _now()
    activated: list[dict] = []
    skipped: list[dict] = []
    with _session() as db:
        due = db.scalars(
            select(OrgVersion).where(
                OrgVersion.status == ORG_VERSION_SCHEDULED,
                OrgVersion.effective_at.is_not(None),
                OrgVersion.effective_at <= moment,
                OrgVersion.is_deleted.is_(False),
            )
        ).all()
        targets = [(v.tenant_id, v.id, int(v.version or 0)) for v in due]

    for tenant_id, version_id, ver in targets:
        try:
            transition_version(
                version_id, ORG_VERSION_ACTIVATED, reason="排期到点自动激活",
                expected_version=ver, tenant_id=tenant_id,
            )
            activated.append({"tenantId": str(tenant_id), "versionId": str(version_id)})
        except AppException as exc:
            skipped.append({"tenantId": str(tenant_id), "versionId": str(version_id), "reason": exc.code})
    return {"activated": activated, "skipped": skipped, "checkedAt": moment.isoformat()}


# ── 任职 ────────────────────────────────────────────────────────────────────
def _assignment_row(row: StaffAssignment, *, at: datetime | None = None) -> dict:
    moment = at or _now()
    effective_now = (
        row.status == ASSIGNMENT_STATUS_ACTIVE
        and row.effective_at <= moment
        and (row.expires_at is None or row.expires_at > moment)
    )
    return {
        "assignmentId": str(row.id),
        "userId": str(row.user_id),
        "orgType": row.org_type,
        "orgNodeId": str(row.org_node_id),
        "assignmentType": row.assignment_type,
        "isPrimary": bool(row.is_primary),
        "sourceType": row.source_type,
        "sourceId": row.source_id,
        "effectiveAt": row.effective_at.isoformat() if row.effective_at else None,
        "expiresAt": row.expires_at.isoformat() if row.expires_at else None,
        "status": row.status,
        "effectiveNow": effective_now,
        "reason": row.reason,
        "version": int(row.version or 0),
    }


def create_assignment(
    *,
    user_id: int,
    org_type: str,
    org_node_id: int,
    assignment_type: str,
    effective_at: datetime | None = None,
    expires_at: datetime | None = None,
    is_primary: bool = False,
    reason: str = "",
    tenant_id: int | None = None,
) -> dict:
    tid = _tenant_id(tenant_id)
    otype = str(org_type or "").upper()
    atype = str(assignment_type or "").upper()
    if otype not in ORG_TYPES:
        raise AppException("VALIDATION_ERROR", f"未知组织类型：{otype}")
    if atype not in ASSIGNMENT_TYPES:
        raise AppException("VALIDATION_ERROR", f"未知任职类型：{atype}", details={"allowed": list(ASSIGNMENT_TYPES)})
    start = _floor_seconds(effective_at) or _now()
    expires_at = _floor_seconds(expires_at)
    if expires_at and expires_at <= start:
        raise AppException("VALIDATION_ERROR", "任职结束时间必须晚于开始时间")

    with _session() as db:
        _load_node(db, tid, otype, int(org_node_id))  # 跨租户组织节点 404
        if is_primary:
            # 一个人同一时间只应有一个主任职
            db.query(StaffAssignment).filter(
                StaffAssignment.tenant_id == tid,
                StaffAssignment.user_id == int(user_id),
                StaffAssignment.is_primary.is_(True),
                StaffAssignment.status == ASSIGNMENT_STATUS_ACTIVE,
            ).update({"is_primary": False}, synchronize_session=False)
        row = StaffAssignment(
            tenant_id=tid,
            user_id=int(user_id),
            org_type=otype,
            org_node_id=int(org_node_id),
            assignment_type=atype,
            is_primary=bool(is_primary),
            source_type=ASSIGNMENT_SOURCE_MANUAL,
            effective_at=start,
            expires_at=expires_at,
            status=ASSIGNMENT_STATUS_ACTIVE,
            reason=reason,
            created_by=_actor_id(),
            updated_by=_actor_id(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _assignment_row(row)


def revoke_assignment(assignment_id: int, *, reason: str, expected_version: int, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        row = db.scalars(
            select(StaffAssignment).where(
                StaffAssignment.tenant_id == tid,
                StaffAssignment.id == int(assignment_id),
                StaffAssignment.is_deleted.is_(False),
            )
        ).first()
        if not row:
            raise not_found("任职记录不存在")
        if int(row.version or 0) != int(expected_version):
            raise AppException("VERSION_CONFLICT", "该任职已被其他人修改，请刷新后重试", http_status=409)
        row.status = ASSIGNMENT_STATUS_REVOKED
        row.expires_at = _now()
        row.reason = reason or row.reason
        row.is_primary = False
        row.updated_by = _actor_id()
        row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        return _assignment_row(row)


def list_assignments(
    *, user_id: int | None = None, org_type: str | None = None, org_node_id: int | None = None,
    include_expired: bool = False, at: datetime | None = None, tenant_id: int | None = None,
) -> dict:
    tid = _tenant_id(tenant_id)
    moment = at or _now()
    with _session() as db:
        stmt = select(StaffAssignment).where(
            StaffAssignment.tenant_id == tid, StaffAssignment.is_deleted.is_(False)
        )
        if user_id:
            stmt = stmt.where(StaffAssignment.user_id == int(user_id))
        if org_type:
            stmt = stmt.where(StaffAssignment.org_type == str(org_type).upper())
        if org_node_id:
            stmt = stmt.where(StaffAssignment.org_node_id == int(org_node_id))
        rows = db.scalars(stmt.order_by(StaffAssignment.id.desc())).all()
        items = [_assignment_row(r, at=moment) for r in rows]
        if not include_expired:
            # 读取时校验：即使定时任务还没把状态刷成 EXPIRED，过期任职也不会被当作有效
            items = [i for i in items if i["effectiveNow"]]
        return {"items": items, "total": len(items), "resolvedAt": moment.isoformat()}


def effective_assignments(user_id: int, *, at: datetime | None = None, tenant_id: int | None = None) -> list[dict]:
    """给鉴权/业务用的唯一读取入口：某人此刻真实生效的任职。"""
    return list_assignments(user_id=user_id, at=at, tenant_id=tenant_id)["items"]


def expire_due_assignments(*, now: datetime | None = None) -> dict:
    """定时把到期任职刷成 EXPIRED。与读取时校验构成双保险。"""
    moment = now or _now()
    with _session() as db:
        rows = db.scalars(
            select(StaffAssignment).where(
                StaffAssignment.status == ASSIGNMENT_STATUS_ACTIVE,
                StaffAssignment.expires_at.is_not(None),
                StaffAssignment.expires_at <= moment,
                StaffAssignment.is_deleted.is_(False),
            )
        ).all()
        for row in rows:
            row.status = ASSIGNMENT_STATUS_EXPIRED
            row.is_primary = False
            row.version = int(row.version or 0) + 1
        db.commit()
        return {"expired": len(rows), "checkedAt": moment.isoformat()}


def _audit(action: str, version_id: int, reason: str) -> None:
    try:
        from app.services import audit_log

        audit_log.record(
            "ORG_VERSION_TRANSITION", f"orgVersion:{version_id}", detail={"toStatus": action, "reason": reason}
        )
    except Exception:  # noqa: BLE001 - 审计失败不影响主流程
        pass
