"""实习批次参与人：用组织范围选人替代反复导 Excel 名单（阶段 E）。

流程：

    设规则（学院/专业/班级/年级/点名 - 排除项）
      → 预览（现算，学生转班会跟着变）
      → 冻结（名单落库快照 + 幂等建实习记录 + 审计 + 批次转 RUNNING）
      → 之后只能人工增删单个学生，规则不再自动生效

为什么冻结后要快照：实习名单有考核与法律意义。学生冻结后转班、改名，
不能把人从名单里挪走或挪进来；但页面显示的姓名仍以主档为准（双读），
快照只用于"当时属于哪个班"的追溯。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services import student_scope_resolver as scope
from app.services.db_service import _iso, _tid, session

# 只有草稿批次能改规则与冻结；已开跑的批次改名单必须走人工增减并留痕
EDITABLE_BATCH_STATUS = {"DRAFT"}


def _op_name() -> str:
    u = get_current_user_ctx() or {}
    return u.get("realName") or u.get("loginName") or "系统"


def _audit(db, batch_id, action: str, detail=None) -> None:
    """写实习域留痕。该表是 append-only 的 target_id/target_type/detail_json 结构，
    不是通用的 biz_type/detail 文本表——写错字段会在运行时才炸。"""
    from app.models import InternshipAuditTrail
    u = get_current_user_ctx() or {}
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=int(batch_id), target_type="BATCH", action=action,
        operator_name=_op_name(),
        detail_json={"scene": "BATCH_PARTICIPANT", "role": u.get("currentRoleCode") or "",
                     "detail": detail},
        occurred_at=datetime.utcnow()))


def _get_batch(db, batch_id):
    from app.models import InternshipBatch
    b = db.get(InternshipBatch, int(batch_id))
    if not b or b.is_deleted or int(b.tenant_id) != _tid():
        raise not_found("实习批次不存在或不在当前数据范围内")
    return b


def _get_or_create_rule(db, batch_id):
    from app.models import InternshipBatchScopeRule
    row = db.scalars(select(InternshipBatchScopeRule).where(
        InternshipBatchScopeRule.tenant_id == _tid(),
        InternshipBatchScopeRule.batch_id == int(batch_id),
        InternshipBatchScopeRule.is_deleted.is_(False))).first()
    if row is None:
        row = InternshipBatchScopeRule(tenant_id=_tid(), batch_id=int(batch_id), rule_json={})
        db.add(row)
        db.flush()
    return row


# ── 规则与预览 ────────────────────────────────────────────────────────────

def get_rule(batch_id) -> dict:
    with session() as db:
        b = _get_batch(db, batch_id)
        rule = _get_or_create_rule(db, batch_id)
        db.commit()
        return {
            "batchId": str(b.id), "batchName": b.batch_name, "batchStatus": b.status,
            "rule": rule.rule_json or {},
            "frozen": rule.frozen_at is not None,
            "frozenAt": _iso(rule.frozen_at), "frozenBy": rule.frozen_by or "",
            "lastPreviewCount": int(rule.last_preview_count or 0),
            "lastPreviewAt": _iso(rule.last_preview_at),
            "editable": b.status in EDITABLE_BATCH_STATUS and rule.frozen_at is None,
        }


def preview(batch_id, body: dict, user: dict) -> dict:
    """按规则现算名单。不写名单，只记一次预览计数，便于页面显示"上次圈了多少人"。"""
    with session() as db:
        _get_batch(db, batch_id)
        rule_row = _get_or_create_rule(db, batch_id)
        rule = scope.parse_rule(body or {})
        res = scope.resolve(db, _tid(), rule, user=user)

        # 已在本批次名单里的人单独标出来，避免用户以为要重复添加
        existing = _participant_student_ids(db, batch_id)
        rows = scope.preview_rows(db, res.students, _tid())
        for r in rows:
            r["alreadyIn"] = int(r["studentId"]) in existing

        rule_row.rule_json = rule.to_dict()
        rule_row.last_preview_count = res.matched_count
        rule_row.last_preview_at = datetime.utcnow()
        rule_row.version = int(rule_row.version or 0) + 1
        db.commit()
        return {"rule": rule.to_dict(), "rows": rows, "alreadyInCount": sum(1 for r in rows if r["alreadyIn"]),
                **res.summary()}


def _participant_student_ids(db, batch_id) -> set[int]:
    from app.models import InternshipBatchParticipant
    return {int(x) for x in db.scalars(select(InternshipBatchParticipant.student_id).where(
        InternshipBatchParticipant.tenant_id == _tid(),
        InternshipBatchParticipant.batch_id == int(batch_id),
        InternshipBatchParticipant.status == "ACTIVE",
        InternshipBatchParticipant.is_deleted.is_(False))).all()}


# ── 冻结 ──────────────────────────────────────────────────────────────────

def freeze(batch_id, body: dict, user: dict) -> dict:
    """把规则圈到的人固化为正式名单，并幂等创建实习记录。

    幂等的两处：
    - participant 有 (tenant, batch, student) 唯一键，重复冻结不会插第二条；
    - InternshipRecord 有 (tenant, student, batch) 唯一键，已有记录直接复用，
      不会因为多点一次冻结就给学生建两条实习记录。
    """
    from app.models import InternshipBatchParticipant, InternshipRecord

    with session() as db:
        b = _get_batch(db, batch_id)
        rule_row = _get_or_create_rule(db, batch_id)
        if rule_row.frozen_at is not None:
            raise AppException("DATA_CONFLICT", "该批次名单已冻结，如需调整请使用单个增减")
        if b.status not in EDITABLE_BATCH_STATUS:
            raise AppException("DATA_CONFLICT",
                               f"只有草稿状态的批次可以冻结名单（当前 {b.status}）")

        rule = scope.parse_rule(body.get("rule") if body else rule_row.rule_json)
        if rule.is_empty():
            raise AppException("VALIDATION_ERROR", "选人规则为空，请先选择学院/专业/班级或指定学生")
        res = scope.resolve(db, _tid(), rule, user=user, limit=None)
        if not res.students:
            raise AppException("VALIDATION_ERROR", "按当前规则没有圈到任何学生，请调整后重试")

        cache: dict = {}
        existing = _participant_student_ids(db, batch_id)
        created = reused = 0
        for s in res.students:
            if int(s.id) in existing:
                continue
            snap = scope.preview_rows(db, [s], _tid())[0]
            rec = db.scalars(select(InternshipRecord).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.student_id == int(s.id),
                InternshipRecord.batch_id == int(batch_id))).first()
            if rec is None:
                rec = InternshipRecord(tenant_id=_tid(), student_id=int(s.id),
                                       batch_id=int(batch_id), status="PREPARING",
                                       eligibility_status="PENDING", destination_type="NONE")
                db.add(rec)
                db.flush()
                created += 1
            else:
                reused += 1
            db.add(InternshipBatchParticipant(
                tenant_id=_tid(), batch_id=int(batch_id), student_id=int(s.id), source="SCOPE",
                snapshot_student_no=snap["studentNo"], snapshot_name=snap["name"],
                snapshot_class_name=snap["className"], snapshot_college_name=snap["collegeName"],
                internship_id=int(rec.id), status="ACTIVE"))

        rule_row.rule_json = rule.to_dict()
        rule_row.frozen_at = datetime.utcnow()
        rule_row.frozen_by = _op_name()
        rule_row.version = int(rule_row.version or 0) + 1

        total = len(existing) + len(res.students) - len(
            [s for s in res.students if int(s.id) in existing])
        b.planned_count = total
        b.status = "RUNNING"
        b.previous_status = "DRAFT"
        b.last_transition_at = datetime.utcnow()
        b.last_transition_by = _op_name()
        b.transition_reason = "冻结参与人名单"
        b.version = int(b.version or 0) + 1

        _audit(db, batch_id, "冻结参与人名单",
               {"total": total, "createdRecords": created, "reusedRecords": reused,
                "rule": rule.to_dict()})
        db.commit()
        return {"batchId": str(batch_id), "total": total, "createdRecords": created,
                "reusedRecords": reused, "batchStatus": b.status}


# ── 名单读写 ──────────────────────────────────────────────────────────────

def list_participants(batch_id, page: int = 1, page_size: int = 20,
                      keyword: str | None = None, include_removed: bool = False) -> tuple[list, int]:
    """名单列表。姓名/班级走主档双读——改了学籍这里立刻跟着变，快照只在主档缺失时兜底。"""
    from app.models import InternshipBatchParticipant, StudentProfile

    with session() as db:
        _get_batch(db, batch_id)
        conds = [InternshipBatchParticipant.tenant_id == _tid(),
                 InternshipBatchParticipant.batch_id == int(batch_id),
                 InternshipBatchParticipant.is_deleted.is_(False)]
        if not include_removed:
            conds.append(InternshipBatchParticipant.status == "ACTIVE")
        rows = db.scalars(select(InternshipBatchParticipant).where(*conds)
                          .order_by(InternshipBatchParticipant.id)).all()

        profiles = {p.id: p for p in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_([r.student_id for r in rows] or [0]))).all()}
        cache: dict = {}
        items = []
        for r in rows:
            p = profiles.get(int(r.student_id))
            college_name = class_name = ""
            if p is not None:
                college_name, _major, class_name = scope.org_names(db, p, cache)
            items.append({
                "id": str(r.id), "studentId": str(r.student_id),
                "studentNo": (p.student_no if p else None) or r.snapshot_student_no or "",
                "name": (p.real_name if p else None) or r.snapshot_name or "",
                "className": class_name or r.snapshot_class_name or "",
                "collegeName": college_name or r.snapshot_college_name or "",
                "snapshotClassName": r.snapshot_class_name or "",
                "classChanged": bool(class_name and r.snapshot_class_name
                                     and class_name != r.snapshot_class_name),
                "source": r.source, "status": r.status,
                "internshipId": str(r.internship_id or ""),
                "removeReason": r.remove_reason or "",
                "createdAt": _iso(r.created_at), "version": int(r.version or 0),
            })
        if keyword:
            kw = keyword.strip()
            items = [x for x in items if kw in x["name"] or kw in x["studentNo"]]
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def add_participants(batch_id, student_ids, user: dict, reason: str = "") -> dict:
    """人工补录（转专业、休学复学、漏选）。同样幂等，且要求学生在调用者数据范围内。"""
    from app.models import InternshipBatchParticipant, InternshipRecord, StudentProfile

    ids = [int(x) for x in (student_ids or []) if x]
    if not ids:
        raise AppException("VALIDATION_ERROR", "请至少选择一名学生")

    with session() as db:
        _get_batch(db, batch_id)
        # 复用 resolver 的数据范围口径：点名添加也不能越权把别院学生塞进来
        allowed = scope.resolve(db, _tid(), scope.parse_rule({"studentIds": ids}),
                                user=user, limit=None)
        allowed_ids = {int(s.id) for s in allowed.students}
        rejected = [i for i in ids if i not in allowed_ids]

        existing = _participant_student_ids(db, batch_id)
        added = 0
        for s in allowed.students:
            if int(s.id) in existing:
                continue
            snap = scope.preview_rows(db, [s], _tid())[0]
            rec = db.scalars(select(InternshipRecord).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.student_id == int(s.id),
                InternshipRecord.batch_id == int(batch_id))).first()
            if rec is None:
                rec = InternshipRecord(tenant_id=_tid(), student_id=int(s.id),
                                       batch_id=int(batch_id), status="PREPARING",
                                       eligibility_status="PENDING", destination_type="NONE")
                db.add(rec)
                db.flush()
            # 曾被移出的人重新加入：复活原行而不是插重复行（唯一键也不允许）
            revived = db.scalars(select(InternshipBatchParticipant).where(
                InternshipBatchParticipant.tenant_id == _tid(),
                InternshipBatchParticipant.batch_id == int(batch_id),
                InternshipBatchParticipant.student_id == int(s.id))).first()
            if revived is not None:
                revived.status = "ACTIVE"
                revived.remove_reason = None
                revived.internship_id = int(rec.id)
                revived.version = int(revived.version or 0) + 1
            else:
                db.add(InternshipBatchParticipant(
                    tenant_id=_tid(), batch_id=int(batch_id), student_id=int(s.id),
                    source="MANUAL", snapshot_student_no=snap["studentNo"],
                    snapshot_name=snap["name"], snapshot_class_name=snap["className"],
                    snapshot_college_name=snap["collegeName"],
                    internship_id=int(rec.id), status="ACTIVE"))
            added += 1

        _audit(db, batch_id, "补录参与人",
               {"added": added, "studentIds": [int(x.id) for x in allowed.students],
                "reason": reason or ""})
        db.commit()
        return {"added": added, "skippedExisting": len(ids) - len(rejected) - added,
                "rejectedOutOfScope": rejected}


def remove_participant(batch_id, participant_id, reason: str, expected_version) -> dict:
    """移出名单。保留行 + 记原因，便于追溯"这个人当初在不在名单里"。"""
    from app.core.optimistic_lock import require_expected_version
    from app.models import InternshipBatchParticipant

    if not reason or len(reason.strip()) < 2:
        raise AppException("VALIDATION_ERROR", "移出原因必填（不少于 2 字）")
    expected = require_expected_version(expected_version)

    with session() as db:
        _get_batch(db, batch_id)
        row = db.get(InternshipBatchParticipant, int(participant_id))
        if (not row or row.is_deleted or int(row.tenant_id) != _tid()
                or int(row.batch_id) != int(batch_id)):
            raise not_found("参与人记录不存在")
        if int(row.version or 0) != expected:
            raise AppException("APPROVAL_VERSION_CONFLICT", "数据已被他人修改，请刷新后重试")
        if row.status != "ACTIVE":
            raise AppException("DATA_CONFLICT", "该学生已不在名单中")
        row.status = "REMOVED"
        row.remove_reason = reason.strip()
        row.version = int(row.version or 0) + 1
        _audit(db, batch_id, "移出参与人",
               {"studentId": int(row.student_id), "name": row.snapshot_name or "",
                "reason": reason.strip()})
        db.commit()
        return {"id": str(row.id), "status": row.status}


def summary(batch_id) -> dict:
    from app.models import InternshipBatchParticipant

    with session() as db:
        b = _get_batch(db, batch_id)
        rule = _get_or_create_rule(db, batch_id)
        base = [InternshipBatchParticipant.tenant_id == _tid(),
                InternshipBatchParticipant.batch_id == int(batch_id),
                InternshipBatchParticipant.is_deleted.is_(False)]
        active = db.scalar(select(func.count()).select_from(InternshipBatchParticipant)
                           .where(*base, InternshipBatchParticipant.status == "ACTIVE")) or 0
        removed = db.scalar(select(func.count()).select_from(InternshipBatchParticipant)
                            .where(*base, InternshipBatchParticipant.status == "REMOVED")) or 0
        db.commit()
        return {"batchId": str(b.id), "batchName": b.batch_name, "batchStatus": b.status,
                "frozen": rule.frozen_at is not None, "frozenAt": _iso(rule.frozen_at),
                "activeCount": int(active), "removedCount": int(removed),
                "plannedCount": int(b.planned_count or 0)}
