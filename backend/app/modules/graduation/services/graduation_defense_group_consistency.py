"""答辩组编排并发与通知真实性收口。"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    GraduationBatch,
    GraduationDefenseGroup,
    GraduationFinal,
    GraduationStudent,
    MessageEventOutbox,
)
from app.modules.graduation.services.graduation_scope_service import assert_student_access, can_access_student, has_full_scope
from app.services.db_service import _tid, session

_INSTALLED = False


def _locked_group(db, group_id, *, batch_id=None) -> GraduationDefenseGroup:
    row = db.scalars(select(GraduationDefenseGroup).where(
        GraduationDefenseGroup.id == int(group_id),
        GraduationDefenseGroup.tenant_id == _tid(),
        GraduationDefenseGroup.is_deleted.is_(False),
    ).with_for_update()).first()
    if not row:
        raise not_found("答辩组不存在")
    if batch_id not in (None, "") and int(row.batch_id or 0) != int(batch_id):
        raise AppException("DATA_CONFLICT", "当前页面批次与答辩组批次不一致，请刷新")
    return row


def _require_batch(db, batch_id) -> GraduationBatch:
    if batch_id in (None, ""):
        raise AppException("VALIDATION_ERROR", "必须选择毕业设计批次")
    row = db.scalars(select(GraduationBatch).where(
        GraduationBatch.id == int(batch_id), GraduationBatch.tenant_id == _tid(),
        GraduationBatch.is_deleted.is_(False),
    ).with_for_update()).first()
    if not row:
        raise not_found("毕业设计批次不存在")
    if row.status in ("ARCHIVED", "VOIDED"):
        raise AppException("DATA_CONFLICT", "已归档或已作废批次不可修改答辩编排")
    return row


def create_group(group_name, defense_date=None, location=None, chair=None,
                 members=None, secretary=None, batch_id=None,
                 chair_mentor_id=None, secretary_mentor_id=None,
                 member_mentor_ids=None) -> dict:
    from app.modules.graduation.services import graduation_service as svc

    name = str(group_name or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "答辩组名称不能为空")
    with session() as db:
        batch = _require_batch(db, batch_id)
        existed = db.scalars(select(GraduationDefenseGroup).where(
            GraduationDefenseGroup.tenant_id == _tid(),
            GraduationDefenseGroup.batch_id == batch.id,
            GraduationDefenseGroup.group_name == name,
            GraduationDefenseGroup.is_deleted.is_(False),
        ).with_for_update()).first()
        if existed:
            raise AppException("DATA_CONFLICT", "当前批次已存在同名答辩组")
        group = GraduationDefenseGroup(
            tenant_id=_tid(), batch_id=batch.id, group_name=name,
            defense_date=str(defense_date or "").strip() or None,
            location=str(location or "").strip() or None,
            student_count=0, conflict="", published=False,
        )
        svc._apply_defense_people(
            db, group, chair=chair, secretary=secretary, members=members,
            chair_mentor_id=chair_mentor_id, secretary_mentor_id=secretary_mentor_id,
            member_mentor_ids=member_mentor_ids,
        )
        db.add(group)
        try:
            db.flush()
        except IntegrityError as exc:
            raise AppException("DATA_CONFLICT", "当前批次已存在同名答辩组") from exc
        svc._recompute_defense(db, group)
        svc._audit(db, "DEFENSE", group.id, "新建答辩组", f"{group.group_name} batch={batch.id}")
        db.commit()
        return svc.get_defense_group_detail(group.id)


def update_group(group_id, group_name=None, defense_date=None, location=None, chair=None,
                 members=None, secretary=None, chair_mentor_id=None,
                 secretary_mentor_id=None, member_mentor_ids=None,
                 *, batch_id=None) -> dict:
    from app.modules.graduation.services import graduation_service as svc

    with session() as db:
        group = _locked_group(db, group_id, batch_id=batch_id)
        _require_batch(db, group.batch_id)
        if group_name and str(group_name).strip():
            new_name = str(group_name).strip()
            duplicate = db.scalars(select(GraduationDefenseGroup).where(
                GraduationDefenseGroup.tenant_id == _tid(),
                GraduationDefenseGroup.batch_id == group.batch_id,
                GraduationDefenseGroup.group_name == new_name,
                GraduationDefenseGroup.id != group.id,
                GraduationDefenseGroup.is_deleted.is_(False),
            ).with_for_update()).first()
            if duplicate:
                raise AppException("DATA_CONFLICT", "当前批次已存在同名答辩组")
            group.group_name = new_name
        group.defense_date = str(defense_date or "").strip() or None
        group.location = str(location or "").strip() or None
        svc._apply_defense_people(
            db, group, chair=chair, secretary=secretary, members=members,
            chair_mentor_id=chair_mentor_id, secretary_mentor_id=secretary_mentor_id,
            member_mentor_ids=member_mentor_ids, preserve_existing=True,
        )
        was_published = bool(group.published)
        group.published = False
        group.version = int(group.version or 0) + 1
        svc._recompute_defense(db, group)
        svc._audit(db, "DEFENSE", group.id,
                   "编辑答辩组" + ("（撤回已发布，需重新发布）" if was_published else ""),
                   group.group_name)
        db.commit()
        return svc.get_defense_group_detail(group.id)


def assign_students(group_id, student_ids, *, batch_id=None) -> dict:
    from app.modules.graduation.services import graduation_service as svc

    ids = sorted({int(value) for value in (student_ids or [])})
    with session() as db:
        group = _locked_group(db, group_id, batch_id=batch_id)
        _require_batch(db, group.batch_id)
        current_students = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.defense_group_id == group.id,
            GraduationStudent.is_deleted.is_(False),
        ).order_by(GraduationStudent.id).with_for_update()).all()
        current_ids = {row.id for row in current_students}
        targets = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id.in_(ids or [-1]),
            GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE",
        ).order_by(GraduationStudent.id).with_for_update()).all()
        by_id = {row.id: row for row in targets}
        missing = [value for value in ids if value not in by_id]
        if missing:
            raise not_found(f"学生不存在：{','.join(map(str, missing[:10]))}")
        added = 0
        for student_id in ids:
            student = by_id[student_id]
            assert_student_access(db, student, "defense.assign")
            if int(student.batch_id or 0) != int(group.batch_id or 0):
                raise AppException("DATA_CONFLICT", f"学生 {student.name} 与答辩组不在同一批次")
            if student.stage not in ("FINAL_CHECK", "DEFENSE", "COMPLETED"):
                raise AppException("DATA_CONFLICT", f"学生 {student.name} 尚未进入成果检查阶段")
            if student.defense_group_id == group.id:
                continue
            if student.defense_group_id and student.defense_group_id != group.id:
                raise AppException("DATA_CONFLICT", f"学生 {student.name} 已在其他答辩组")
            if len(current_ids) + added + 1 > svc.MAX_DEFENSE_STUDENTS:
                raise AppException("DATA_CONFLICT", f"单个答辩组学生数不得超过 {svc.MAX_DEFENSE_STUDENTS} 人")
            final_ok = db.scalars(select(GraduationFinal).where(
                GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == student.id,
                GraduationFinal.final_type == "定稿", GraduationFinal.status == "APPROVED",
                GraduationFinal.is_deleted.is_(False),
            ).with_for_update()).first()
            if not final_ok:
                raise AppException("DATA_CONFLICT", f"学生 {student.name} 的正式定稿尚未通过")
            student.defense_group_id = group.id
            student.defense_group = group.group_name
            if student.stage == "FINAL_CHECK":
                student.stage = "DEFENSE"
            student.version = int(student.version or 0) + 1
            added += 1
        svc._recompute_defense(db, group)
        group.published = False
        group.version = int(group.version or 0) + 1
        svc._audit(db, "DEFENSE", group.id, "分配学生进答辩组", f"{group.group_name} +{added} 人")
        db.commit()
        return svc.get_defense_group_detail(group.id)


def unassign_students(group_id, student_ids, *, batch_id=None) -> dict:
    from app.modules.graduation.services import graduation_service as svc

    ids = sorted({int(value) for value in (student_ids or [])})
    with session() as db:
        group = _locked_group(db, group_id, batch_id=batch_id)
        students = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id.in_(ids or [-1]),
            GraduationStudent.is_deleted.is_(False),
        ).order_by(GraduationStudent.id).with_for_update()).all()
        removed = 0
        for student in students:
            assert_student_access(db, student, "defense.assign")
            if int(student.batch_id or 0) != int(group.batch_id or 0):
                raise AppException("DATA_CONFLICT", f"学生 {student.name} 与答辩组批次不一致")
            if student.defense_group_id == group.id:
                student.defense_group_id = None
                student.defense_group = None
                student.version = int(student.version or 0) + 1
                removed += 1
        svc._recompute_defense(db, group)
        group.published = False
        group.version = int(group.version or 0) + 1
        svc._audit(db, "DEFENSE", group.id, "移出答辩组学生", f"{group.group_name} -{removed} 人")
        db.commit()
        return svc.get_defense_group_detail(group.id)


def publish_group(group_id, *, batch_id=None) -> dict:
    from app.modules.graduation.services import graduation_service as svc

    with session() as db:
        group = _locked_group(db, group_id, batch_id=batch_id)
        _require_batch(db, group.batch_id)
        svc._recompute_defense(db, group)
        if group.conflict:
            raise AppException("VALIDATION_ERROR", "存在评委与导师冲突，调整后方可发布")
        if not group.chair_mentor_id or not group.secretary_mentor_id:
            raise AppException("VALIDATION_ERROR", "答辩主席和秘书必须绑定稳定导师 ID")
        from app.modules.graduation.services import graduation_identity as identity
        seats = identity.judge_panel_seats(group)
        if not seats or any(not (seat.get("mentorId") or seat.get("expertId")) for seat in seats):
            raise AppException("VALIDATION_ERROR", "所有答辩评委必须绑定稳定校内导师或校外专家 ID")
        if not str(group.location or "").strip() or not str(group.defense_date or "").strip():
            raise AppException("VALIDATION_ERROR", "答辩时间和地点未安排完整")
        if int(group.student_count or 0) <= 0:
            raise AppException("VALIDATION_ERROR", "尚未分配答辩学生")
        group.published = True
        group.version = int(group.version or 0) + 1
        svc._audit(db, "DEFENSE", group.id, "发布答辩安排",
                   f"{group.group_name}（{group.student_count} 人） version={group.version}")
        db.commit()
        return {"id": str(group.id), "published": True, "version": group.version}


def notify_group(group_id, user=None, *, batch_id=None) -> dict:
    from app.modules.graduation.services import graduation_service as svc
    from app.services.message_event_outbox_service import emit_message_event, process_pending_outbox

    with session() as db:
        group = _locked_group(db, group_id, batch_id=batch_id)
        if not svc._can_access_defense_group(db, group):
            raise no_permission("答辩组不在当前数据范围内")
        if not group.published:
            raise AppException("DATA_CONFLICT", "答辩组尚未发布，不能发送通知")
        students = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.defense_group_id == group.id,
            GraduationStudent.is_deleted.is_(False),
        ).order_by(GraduationStudent.id).with_for_update()).all()
        schedule_hash = hashlib.sha256(
            f"{group.version}|{group.defense_date}|{group.location}|{group.chair_mentor_id}".encode("utf-8")
        ).hexdigest()[:16]
        outbox_ids, skipped = [], 0
        for student in students:
            if not can_access_student(db, student) or not student.student_id:
                skipped += 1
                continue
            content = (
                f"同学你好，你的毕业设计答辩组「{group.group_name}」已发布。"
                f"时间：{group.defense_date or '待定'}；地点：{group.location or '待定'}；"
                f"主席：{group.chair or '待指定'}。请按时参加。"
            )
            row = emit_message_event(
                db,
                event_code="GRADUATION_DESIGN.DEFENSE_ARRANGED",
                source_module="graduation",
                source_biz_type="defense_group",
                source_biz_id=int(group.id),
                recipient_refs=[{"studentId": int(student.student_id)}],
                content=content,
                title=f"答辩安排通知：{group.group_name}",
                action_key="graduation.defense.view",
                action_params={"gdStudentId": str(student.id), "batchId": str(group.batch_id)},
                dedup_key=(
                    f"GRADUATION_DESIGN.DEFENSE_ARRANGED:{group.id}:v{group.version}:"
                    f"{schedule_hash}:student:{student.student_id}"
                ),
            )
            outbox_ids.append(int(row.id))
        svc._audit(db, "DEFENSE", group.id, "答辩通知进入发送队列",
                   f"queued={len(outbox_ids)} skipped={skipped} version={group.version}")
        db.commit()

    process_error = None
    try:
        process_pending_outbox(limit=max(50, len(outbox_ids)), worker_id="graduation-inline")
    except Exception as exc:  # 业务已成功写 outbox，投递由调度重试
        process_error = type(exc).__name__

    with session() as db:
        rows = db.scalars(select(MessageEventOutbox).where(
            MessageEventOutbox.tenant_id == _tid(),
            MessageEventOutbox.id.in_(outbox_ids or [-1]),
            MessageEventOutbox.is_deleted.is_(False),
        )).all()
        delivered = sum(1 for row in rows if row.status == "SUCCEEDED")
        failed = sum(1 for row in rows if row.status in ("DEAD", "RETRY_WAIT"))
        pending = len(rows) - delivered - failed
        status = "DELIVERED" if delivered == len(rows) and rows else (
            "PARTIAL" if delivered else "QUEUED"
        )
        message = (
            f"已送达 {delivered} 人" if status == "DELIVERED" else
            f"已进入发送队列 {len(rows)} 人，当前送达 {delivered} 人，待重试 {pending + failed} 人"
        )
        return {
            "groupId": str(group_id), "queued": len(rows), "delivered": delivered,
            "failed": failed, "pending": pending, "skipped": skipped,
            "deliveryStatus": status, "outboxIds": [str(value) for value in outbox_ids],
            "processorError": process_error, "message": message,
            # 旧前端兼容：notified 只代表真实送达，不再代表排队数量。
            "notified": delivered,
        }


def install_defense_group_consistency() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    from app.modules.graduation.services import graduation_service as svc
    svc.create_defense_group = create_group
    svc.update_defense_group = update_group
    svc.assign_defense_students = assign_students
    svc.unassign_defense_students = unassign_students
    svc.publish_defense = publish_group
    svc.notify_defense_group = notify_group
