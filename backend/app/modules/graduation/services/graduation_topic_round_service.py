"""毕业设计中心 · 选题轮次/志愿服务（轮次制互选 + 贪心匹配）。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import enforce_permission
from app.models import (GraduationAuditTrail, GraduationBatch, GraduationStudent, GraduationTopic,
                        GraduationTopicChoice, GraduationTopicRound)
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_export_security import sanitize_xlsx_export
from app.modules.graduation.services.graduation_command_service import _conflict_guard
from app.modules.graduation.services import graduation_student_service as gd_stu_svc
from app.modules.graduation.services.graduation_scope_service import (
    accessible_student_ids, assert_student_access, has_full_scope,
)

ROUND_LABEL = {"DRAFT": "草稿", "OPEN": "进行中", "CLOSED": "已关闭", "MATCHED": "已匹配",
               "ARCHIVED": "已归档"}
ROUND_TONE = {"DRAFT": "default", "OPEN": "processing", "CLOSED": "warning", "MATCHED": "success",
              "ARCHIVED": "info"}
CHOICE_LABEL = {"PENDING": "待匹配", "MATCHED": "已匹配", "UNMATCHED": "未匹配", "CONFIRMED": "已确认", "REJECTED": "已驳回"}


def plan_topic_matches(choices: list[dict], remaining_by_topic: dict[int, int]) -> list[dict]:
    """纯函数：按志愿序贪心匹配（一人最多一题、不超容量）。"""
    remain = dict(remaining_by_topic)
    ordered = sorted(choices, key=lambda c: (c["choice_order"], c["id"]))
    assigned: set[int] = set()
    winners: list[dict] = []
    for c in ordered:
        sid = c["gd_student_id"]
        tid = c["topic_id"]
        if sid in assigned:
            continue
        if remain.get(tid, 0) <= 0:
            continue
        remain[tid] -= 1
        assigned.add(sid)
        winners.append(c)
    return winners


def _audit(db, biz_id, action, detail=""):
    user = get_current_user_ctx() or {}
    operator = user.get("realName") or user.get("loginName")
    role = user.get("currentRoleCode") or user.get("userType")
    if not operator:
        raise AppException("AUDIT_CONTEXT_MISSING", "关键动作缺少操作者上下文")
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type="TOPIC_ROUND", biz_id=str(biz_id),
                                action=action, operator=operator, role_name=role,
                                detail=detail, occurred_at=datetime.now(timezone.utc)))


def _get_round(db, rid) -> GraduationTopicRound:
    r = db.get(GraduationTopicRound, int(rid))
    if not r or r.is_deleted or r.tenant_id != _tid():
        raise not_found("选题轮次不存在")
    return r


def _assert_choice_decision_access(db, choice: GraduationTopicChoice, action: str) -> None:
    """Limit a decision to graduation managers or the advisor owning the topic."""
    if has_full_scope():
        return
    user = get_current_user_ctx() or {}
    role = (user.get("currentRoleCode") or user.get("userType") or "").strip().upper()
    topic = db.get(GraduationTopic, choice.topic_id)
    from app.modules.graduation.services import graduation_identity as gid
    me = gid.current_user_mentor(db)
    if (role == "GD_MENTOR" and me and topic and not topic.is_deleted
            and topic.tenant_id == _tid()
            and getattr(topic, "advisor_mentor_id", None)
            and int(topic.advisor_mentor_id) == int(me.id)):
        return
    raise no_permission(f"Choice is outside the current graduation-design scope ({action})")


def _row_round(r: GraduationTopicRound, batch: GraduationBatch | None = None, *, choice_count: int = 0) -> dict:
    return {
        "id": str(r.id), "batchId": str(r.batch_id) if r.batch_id else "",
        "batchName": batch.batch_name if batch else "",
        "roundName": r.round_name, "roundNo": r.round_no,
        "maxChoices": r.max_choices, "status": r.status,
        "statusLabel": ROUND_LABEL.get(r.status, r.status),
        "statusTone": ROUND_TONE.get(r.status, "default"),
        "startAt": _iso(r.start_at) if r.start_at else "",
        "endAt": _iso(r.end_at) if r.end_at else "",
        "collegeScope": r.college_scope or "", "remark": r.remark or "",
        "choiceCount": choice_count, "updatedAt": _iso(r.updated_at),
    }


def list_rounds(page: int, page_size: int, batch_id=None, status=None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(GraduationTopicRound).where(GraduationTopicRound.tenant_id == _tid(),
                                               GraduationTopicRound.is_deleted.is_(False))
        if batch_id:
            q = q.where(GraduationTopicRound.batch_id == int(batch_id))
        if status:
            q = q.where(GraduationTopicRound.status == status)
        rows = db.scalars(q.order_by(GraduationTopicRound.id.desc())).all()
        batches = {b.id: b for b in db.scalars(select(GraduationBatch).where(
            GraduationBatch.tenant_id == _tid(), GraduationBatch.is_deleted.is_(False))).all()}
        counts: dict[int, int] = {}
        if rows:
            rids = [r.id for r in rows]
            for rid, cnt in db.execute(
                select(GraduationTopicChoice.round_id, func.count()).where(
                    GraduationTopicChoice.tenant_id == _tid(),
                    GraduationTopicChoice.round_id.in_(rids),
                    GraduationTopicChoice.is_deleted.is_(False)).group_by(GraduationTopicChoice.round_id)
            ):
                counts[int(rid)] = int(cnt)
        items = [_row_round(r, batches.get(r.batch_id), choice_count=counts.get(int(r.id), 0)) for r in rows]
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def create_round(body) -> dict:
    data = body.model_dump() if hasattr(body, "model_dump") else dict(body)
    with session() as db:
        batch_id = int(data["batchId"]) if data.get("batchId") else None
        if batch_id:
            b = db.get(GraduationBatch, batch_id)
            if not b or b.is_deleted or b.tenant_id != _tid():
                raise not_found("毕设批次不存在")
        r = GraduationTopicRound(
            tenant_id=_tid(), batch_id=batch_id, round_name=data["roundName"].strip(),
            round_no=int(data.get("roundNo") or 1), max_choices=int(data.get("maxChoices") or 3),
            status="DRAFT", college_scope=(data.get("collegeScope") or "").strip() or None,
            remark=(data.get("remark") or "").strip() or None)
        if data.get("startAt"):
            r.start_at = datetime.fromisoformat(str(data["startAt"]).replace("Z", "+00:00").split("+")[0])
        if data.get("endAt"):
            r.end_at = datetime.fromisoformat(str(data["endAt"]).replace("Z", "+00:00").split("+")[0])
        db.add(r)
        db.flush()
        _audit(db, r.id, "CREATE", r.round_name)
        db.commit()
        batch = db.get(GraduationBatch, r.batch_id) if r.batch_id else None
        return _row_round(r, batch if batch and not batch.is_deleted else None)
def open_round(rid) -> dict:
    with session() as db:
        r = _get_round(db, rid)
        if r.status not in ("DRAFT", "CLOSED"):
            raise AppException("DATA_CONFLICT", "仅草稿或已关闭轮次可开启")
        r.status = "OPEN"
        _audit(db, r.id, "OPEN", "开启选题轮次")
        db.commit()
        return _row_round(r)


def close_round(rid) -> dict:
    with session() as db:
        r = _get_round(db, rid)
        if r.status != "OPEN":
            raise AppException("DATA_CONFLICT", "仅进行中的轮次可关闭")
        r.status = "CLOSED"
        _audit(db, r.id, "CLOSE", "关闭选题轮次")
        db.commit()
        return _row_round(r)


def _choice_row(c: GraduationTopicChoice, stu: GraduationStudent | None, topic: GraduationTopic | None) -> dict:
    return {
        "id": str(c.id), "roundId": str(c.round_id), "gdStudentId": str(c.gd_student_id),
        "studentName": stu.name if stu else "", "studentNo": stu.student_no if stu else "",
        "topicId": str(c.topic_id), "topicTitle": topic.title if topic else "",
        "advisorName": topic.advisor_name if topic else "",
        "choiceOrder": c.choice_order, "status": c.status,
        "statusLabel": CHOICE_LABEL.get(c.status, c.status),
    }


def list_choices(round_id, gd_student_id=None) -> list[dict]:
    with session() as db:
        _get_round(db, round_id)
        q = select(GraduationTopicChoice).where(
            GraduationTopicChoice.tenant_id == _tid(), GraduationTopicChoice.round_id == int(round_id),
            GraduationTopicChoice.is_deleted.is_(False),
            GraduationTopicChoice.status != "WITHDRAWN")
        scope_ids = accessible_student_ids(db, _tid())
        q = q.where(GraduationTopicChoice.gd_student_id.in_(scope_ids or [-1]))
        if gd_student_id:
            q = q.where(GraduationTopicChoice.gd_student_id == int(gd_student_id))
        choices = db.scalars(q.order_by(GraduationTopicChoice.gd_student_id, GraduationTopicChoice.choice_order)).all()
        stu_map = {s.id: s for s in db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False))).all()}
        topic_map = {t.id: t for t in db.scalars(select(GraduationTopic).where(
            GraduationTopic.tenant_id == _tid(), GraduationTopic.is_deleted.is_(False))).all()}
        return [_choice_row(c, stu_map.get(c.gd_student_id), topic_map.get(c.topic_id)) for c in choices]


@_conflict_guard
def submit_choices(round_id, gd_student_id, choices: list[dict], *, admin_import: bool = False) -> dict:
    if not choices:
        raise AppException("VALIDATION_ERROR", "请至少选择一个志愿")
    with session() as db:
        r = db.scalars(select(GraduationTopicRound).where(
            GraduationTopicRound.id == int(round_id),
            GraduationTopicRound.tenant_id == _tid(),
            GraduationTopicRound.is_deleted.is_(False),
        ).with_for_update()).first()
        if not r:
            raise not_found("选题轮次不存在")
        if r.status != "OPEN":
            raise AppException("DATA_CONFLICT", "仅进行中的轮次可提交或导入志愿")
        if len(choices) > int(r.max_choices or 3):
            raise AppException("VALIDATION_ERROR", f"最多 {r.max_choices} 个志愿")
        stu = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(gd_student_id),
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        if not stu or stu.is_deleted or stu.tenant_id != _tid():
            raise not_found("毕设学生不存在")
        assert_student_access(db, stu, "topic.choice.submit")
        if not admin_import:
            elig = getattr(stu, "eligibility_status", None) or "PENDING"
            if elig != "QUALIFIED":
                from app.modules.graduation.services.graduation_student_service import ELIG_LABEL
                raise AppException(
                    "DATA_CONFLICT",
                    f"仅「资格合格」学生可填报志愿（当前：{ELIG_LABEL.get(elig, elig)}）",
                )
        orders = set()
        for ch in choices:
            order = int(ch.get("choiceOrder") or ch.get("choice_order") or 0)
            if order < 1 or order in orders:
                raise AppException("VALIDATION_ERROR", "志愿序号须从1开始且不重复")
            orders.add(order)
            tid = int(ch.get("topicId") or ch.get("topic_id"))
            t = db.get(GraduationTopic, tid)
            if not t or t.is_deleted or t.tenant_id != _tid():
                raise not_found(f"题目 {tid} 不存在")
            if t.review_status != "APPROVED" or t.status != "CONFIRMED":
                raise AppException("DATA_CONFLICT", f"题目「{t.title}」未入池，不可选")
            if r.batch_id and t.batch_id and int(t.batch_id) != int(r.batch_id):
                raise AppException("DATA_CONFLICT", f"题目「{t.title}」不属于本轮次所在批次，不可选")
            if (r.batch_id or t.batch_id) and int(r.batch_id or 0) != int(t.batch_id or 0):
                raise AppException("DATA_CONFLICT", f"题目「{t.title}」与轮次批次不一致，不可选")
            if r.batch_id and stu.batch_id and int(stu.batch_id) != int(r.batch_id):
                raise AppException("DATA_CONFLICT", "学生批次与选题轮次不一致，不可填报志愿")
            if (r.batch_id or stu.batch_id) and int(r.batch_id or 0) != int(stu.batch_id or 0):
                raise AppException("DATA_CONFLICT", "学生批次与选题轮次不一致，不可填报志愿")
        existing = db.scalars(select(GraduationTopicChoice).where(
            GraduationTopicChoice.tenant_id == _tid(), GraduationTopicChoice.round_id == int(round_id),
            GraduationTopicChoice.gd_student_id == int(gd_student_id))
            .with_for_update()).all()
        by_order = {int(ex.choice_order): ex for ex in existing}
        requested_orders = set()
        for ch in choices:
            order = int(ch.get("choiceOrder") or ch.get("choice_order"))
            requested_orders.add(order)
            ex = by_order.get(order)
            if ex:
                ex.topic_id = int(ch.get("topicId") or ch.get("topic_id"))
                ex.status = "PENDING"
                ex.is_deleted = False
                ex.submission_version = int(ex.submission_version or 0) + 1
            else:
                db.add(GraduationTopicChoice(
                    tenant_id=_tid(), round_id=int(round_id), gd_student_id=int(gd_student_id),
                    topic_id=int(ch.get("topicId") or ch.get("topic_id")),
                    choice_order=order, status="PENDING"))
        for order, ex in by_order.items():
            if order not in requested_orders:
                ex.status = "WITHDRAWN"
                ex.is_deleted = False
        _audit(db, round_id, "SUBMIT_CHOICES", f"学生 {stu.name} 提交 {len(choices)} 个志愿")
        db.commit()
        return {"submitted": len(choices)}


def get_choice_detail(choice_id) -> dict:
    """志愿详情（含关联题目导师姓名，供教师端范围校验）。
    确认志愿前学生尚未形成导师关系，因此按「管理员或题目归属导师」裁决，
    不得要求 student.advisor_name 已经等于当前教师。"""
    with session() as db:
        c = db.get(GraduationTopicChoice, int(choice_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("志愿不存在")
        _assert_choice_decision_access(db, c, "topic.choice.detail")
        stu = db.get(GraduationStudent, c.gd_student_id)
        topic = db.get(GraduationTopic, c.topic_id)
        return _choice_row(c, stu, topic)


def list_pending_choices_for_advisor(advisor_name: str) -> list[dict]:
    """教师端·本人指导题目下待确认的志愿（PENDING）。"""
    if not advisor_name:
        return []
    if not has_full_scope():
        user = get_current_user_ctx() or {}
        role = (user.get("currentRoleCode") or user.get("userType") or "").strip().upper()
        if role != "GD_MENTOR":
            raise no_permission("Cannot query pending choices for another advisor")
    with session() as db:
        from app.modules.graduation.services import graduation_identity as gid
        me = gid.current_user_mentor(db)
        if not has_full_scope() and not me:
            raise no_permission("当前账号未绑定毕设导师台账")
        owner_filter = (GraduationTopic.advisor_mentor_id == int(me.id)) if me else (
            GraduationTopic.advisor_name == advisor_name)
        topic_ids = [t.id for t in db.scalars(select(GraduationTopic).where(
            GraduationTopic.tenant_id == _tid(), GraduationTopic.is_deleted.is_(False),
            owner_filter)).all()]
        if not topic_ids:
            return []
        choices = db.scalars(select(GraduationTopicChoice).where(
            GraduationTopicChoice.tenant_id == _tid(), GraduationTopicChoice.is_deleted.is_(False),
            GraduationTopicChoice.status == "PENDING",
            GraduationTopicChoice.topic_id.in_(topic_ids))
            .order_by(GraduationTopicChoice.choice_order, GraduationTopicChoice.id)).all()
        stu_map = {s.id: s for s in db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False))).all()}
        topic_map = {t.id: t for t in db.scalars(select(GraduationTopic).where(
            GraduationTopic.id.in_(topic_ids))).all()}
        return [_choice_row(c, stu_map.get(c.gd_student_id), topic_map.get(c.topic_id)) for c in choices]


@_conflict_guard
def confirm_choice(choice_id, operator_name: str = "") -> dict:
    """教师/管理员·确认志愿：录入该学生到题目（复用 assign_topic 校验+容量），
    并把该生在同一轮次内其余 PENDING 志愿自动关闭为 REJECTED（一人一题，避免重复处理）。"""
    with session() as db:
        c = db.scalars(select(GraduationTopicChoice).where(
            GraduationTopicChoice.id == int(choice_id),
            GraduationTopicChoice.tenant_id == _tid(),
            GraduationTopicChoice.is_deleted.is_(False),
        ).with_for_update()).first()
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("志愿不存在")
        _assert_choice_decision_access(db, c, "topic.choice.confirm")
        if c.status != "PENDING":
            raise AppException("DATA_CONFLICT",
                               f"仅待确认志愿可确认（当前：{CHOICE_LABEL.get(c.status, c.status)}）")
        gd_student_id, topic_id, round_id = c.gd_student_id, c.topic_id, c.round_id
        gd_stu_svc.assign_topic_in_session(
            db, str(gd_student_id), str(topic_id), relationship_authorized=True
        )
        c.status = "CONFIRMED"
        others = db.scalars(select(GraduationTopicChoice).where(
            GraduationTopicChoice.tenant_id == _tid(), GraduationTopicChoice.round_id == round_id,
            GraduationTopicChoice.gd_student_id == gd_student_id, GraduationTopicChoice.id != c.id,
            GraduationTopicChoice.is_deleted.is_(False), GraduationTopicChoice.status == "PENDING")
            .with_for_update()).all()
        for o in others:
            o.status = "REJECTED"
        _audit(db, round_id, "CONFIRM_CHOICE",
              f"{operator_name or '教师'} 确认志愿 choiceId={choice_id}，自动关闭其余待处理志愿 {len(others)} 条")
        db.commit()
        stu = db.get(GraduationStudent, gd_student_id)
        topic = db.get(GraduationTopic, topic_id)
        return _choice_row(c, stu, topic)


def reject_choice(choice_id, reason: str = "", operator_name: str = "") -> dict:
    """教师/管理员·驳回志愿：不落定分配，学生可等待其余志愿或重新提交。"""
    with session() as db:
        c = db.scalars(select(GraduationTopicChoice).where(
            GraduationTopicChoice.id == int(choice_id),
            GraduationTopicChoice.tenant_id == _tid(),
            GraduationTopicChoice.is_deleted.is_(False),
        ).with_for_update()).first()
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("志愿不存在")
        _assert_choice_decision_access(db, c, "topic.choice.reject")
        if c.status != "PENDING":
            raise AppException("DATA_CONFLICT",
                               f"仅待确认志愿可驳回（当前：{CHOICE_LABEL.get(c.status, c.status)}）")
        c.status = "REJECTED"
        _audit(db, c.round_id, "REJECT_CHOICE",
              f"{operator_name or '教师'} 驳回志愿 choiceId={choice_id}：{reason or '未说明理由'}")
        db.commit()
        stu = db.get(GraduationStudent, c.gd_student_id)
        topic = db.get(GraduationTopic, c.topic_id)
        return _choice_row(c, stu, topic)


def match_round(round_id) -> dict:
    if not has_full_scope():
        raise no_permission("Only graduation managers can execute automatic topic matching")
    with session() as db:
        r = db.scalars(select(GraduationTopicRound).where(
            GraduationTopicRound.id == int(round_id),
            GraduationTopicRound.tenant_id == _tid(),
            GraduationTopicRound.is_deleted.is_(False),
        ).with_for_update()).first()
        if not r:
            raise not_found("选题轮次不存在")
        if r.status != "CLOSED":
            raise AppException("DATA_CONFLICT", "仅已关闭轮次可执行匹配")
        pending = db.scalars(select(GraduationTopicChoice).where(
            GraduationTopicChoice.tenant_id == _tid(), GraduationTopicChoice.round_id == int(round_id),
            GraduationTopicChoice.is_deleted.is_(False), GraduationTopicChoice.status == "PENDING")
            .with_for_update()).all()
        if not pending:
            raise AppException("DATA_CONFLICT", "暂无待匹配志愿")
        topic_ids = {c.topic_id for c in pending}
        topics = {t.id: t for t in db.scalars(select(GraduationTopic).where(
            GraduationTopic.tenant_id == _tid(), GraduationTopic.id.in_(topic_ids))
            .order_by(GraduationTopic.id).with_for_update()).all()}
        remaining = {tid: max(0, int(topics[tid].capacity) - int(topics[tid].selected or 0))
                     for tid in topic_ids if tid in topics}
        payload = [{"id": c.id, "gd_student_id": int(c.gd_student_id), "topic_id": int(c.topic_id),
                    "choice_order": int(c.choice_order)} for c in pending]
        winners = plan_topic_matches(payload, remaining)
        matched = 0
        success_ids: set[int] = set()
        for w in winners:
            gd_stu_svc.assign_topic_in_session(
                db, str(w["gd_student_id"]), str(w["topic_id"]), relationship_authorized=True
            )
            matched += 1
            success_ids.add(int(w["id"]))
        for c in pending:
            c.status = "MATCHED" if int(c.id) in success_ids else "UNMATCHED"
        r.status = "MATCHED"
        _audit(db, round_id, "MATCH", f"匹配成功 {matched} 人")
        db.commit()
        return {"matched": matched, "totalChoices": len(payload), "errors": []}


# ═══════════ 退选重选 / 容量冲突复核 / 统计 / 归档（Batch 3） ═══════════

def withdraw_choices(round_id, gd_student_id) -> dict:
    """学生退选：撤回本轮全部待处理志愿（仅进行中轮次；已确认/已匹配的须走变更流程，不可自助退选）。
    退选后学生可重新提交志愿（submit_choices 覆盖语义）。"""
    with session() as db:
        r = db.scalars(select(GraduationTopicRound).where(
            GraduationTopicRound.id == int(round_id),
            GraduationTopicRound.tenant_id == _tid(),
            GraduationTopicRound.is_deleted.is_(False),
        ).with_for_update()).first()
        if r.status != "OPEN":
            raise AppException("DATA_CONFLICT", "仅进行中的轮次可退选")
        stu = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(gd_student_id),
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        assert_student_access(db, stu, "topic.choice.withdraw")
        chs = db.scalars(select(GraduationTopicChoice).where(
            GraduationTopicChoice.tenant_id == _tid(), GraduationTopicChoice.round_id == int(round_id),
            GraduationTopicChoice.gd_student_id == int(gd_student_id),
            GraduationTopicChoice.is_deleted.is_(False),
            GraduationTopicChoice.status != "WITHDRAWN").with_for_update()).all()
        if not chs:
            raise not_found("当前没有可退选的志愿")
        if any(c.status in ("CONFIRMED", "MATCHED") for c in chs):
            raise AppException("DATA_CONFLICT", "已被确认/匹配的选题不可自助退选，请走「课题变更」流程")
        for c in chs:
            c.status = "WITHDRAWN"
            c.is_deleted = True
            c.submission_version = int(c.submission_version or 0) + 1
        _audit(db, round_id, "WITHDRAW_CHOICES", f"学生 {stu.name if stu else gd_student_id} 退选 {len(chs)} 个志愿")
        db.commit()
        return {"withdrawn": len(chs)}


def list_capacity_conflicts(round_id) -> list[dict]:
    """容量冲突人工复核：列出本轮「待处理志愿数 > 剩余容量」的过热题目及竞争学生，供管理员人工确认/驳回。"""
    with session() as db:
        _get_round(db, round_id)
        chs = db.scalars(select(GraduationTopicChoice).where(
            GraduationTopicChoice.tenant_id == _tid(), GraduationTopicChoice.round_id == int(round_id),
            GraduationTopicChoice.is_deleted.is_(False),
            GraduationTopicChoice.status == "PENDING")).all()
        by_topic: dict[int, list] = {}
        for c in chs:
            by_topic.setdefault(int(c.topic_id), []).append(c)
        out = []
        for tid, group in by_topic.items():
            t = db.get(GraduationTopic, tid)
            if not t or t.is_deleted:
                continue
            remaining = max(0, int(t.capacity or 0) - int(t.selected or 0))
            if len(group) <= remaining:
                continue  # 不过热
            students = []
            for c in sorted(group, key=lambda x: x.choice_order):
                s = db.get(GraduationStudent, int(c.gd_student_id))
                students.append({"choiceId": str(c.id), "gdStudentId": str(c.gd_student_id),
                                 "studentName": s.name if s else "", "className": s.class_name if s else "",
                                 "choiceOrder": c.choice_order, "advisorName": t.advisor_name or ""})
            out.append({"topicId": str(tid), "title": t.title, "capacity": int(t.capacity or 0),
                        "remaining": remaining, "pendingCount": len(group),
                        "overBy": len(group) - remaining, "students": students})
        return sorted(out, key=lambda x: -x["overBy"])


def round_stats(round_id) -> dict:
    """选题统计：本轮志愿状态分布、参与学生数、过热题目数、匹配/确认数。"""
    with session() as db:
        r = _get_round(db, round_id)
        chs = db.scalars(select(GraduationTopicChoice).where(
            GraduationTopicChoice.tenant_id == _tid(), GraduationTopicChoice.round_id == int(round_id),
            GraduationTopicChoice.is_deleted.is_(False))).all()
        status_count: dict[str, int] = {}
        students = set()
        topic_pending: dict[int, int] = {}
        for c in chs:
            status_count[c.status] = status_count.get(c.status, 0) + 1
            students.add(int(c.gd_student_id))
            if c.status == "PENDING":
                topic_pending[int(c.topic_id)] = topic_pending.get(int(c.topic_id), 0) + 1
        over = 0
        for tid, cnt in topic_pending.items():
            t = db.get(GraduationTopic, tid)
            if t and cnt > max(0, int(t.capacity or 0) - int(t.selected or 0)):
                over += 1
        by_status = [{"status": s, "label": CHOICE_LABEL.get(s, s), "count": status_count.get(s, 0)}
                     for s in ("PENDING", "CONFIRMED", "MATCHED", "REJECTED", "UNMATCHED")]
        return {"roundId": str(r.id), "roundName": r.round_name, "status": r.status,
                "statusLabel": ROUND_LABEL.get(r.status, r.status), "totalChoices": len(chs),
                "studentCount": len(students), "byStatus": by_status,
                "confirmedCount": status_count.get("CONFIRMED", 0) + status_count.get("MATCHED", 0),
                "conflictTopicCount": over}


def archive_round(rid) -> dict:
    """选题归档：已关闭/已匹配的轮次归档（终态，不再参与进行中列表）。"""
    with session() as db:
        r = _get_round(db, rid)
        if r.status not in ("CLOSED", "MATCHED"):
            raise AppException("DATA_CONFLICT", "仅已关闭/已匹配的轮次可归档")
        r.status = "ARCHIVED"
        _audit(db, rid, "ARCHIVE_ROUND", f"归档轮次 {r.round_name}")
        db.commit()
        return {"id": str(r.id), "status": "ARCHIVED"}


# ═══════════ Excel 导入/导出 ═══════════

def build_round_export_spec():
    from app.services import excel
    C = excel.ColumnSpec
    return excel.ExportSpec(
        module_key="graduationDesign", biz_type="gd-topic-round", sheet_title="选题轮次台账",
        file_name="选题轮次台账.xlsx",
        columns=[
            C("roundName", "轮次名称"),
            C("batchName", "毕设批次"),
            C("roundNo", "轮次序号"),
            C("maxChoices", "最多志愿数"),
            C("statusLabel", "状态"),
            C("startAt", "开始时间"),
            C("endAt", "结束时间"),
            C("choiceCount", "志愿数"),
            C("updatedAt", "更新时间"),
        ],
    )


@sanitize_xlsx_export
def export_rounds_xlsx(batch_id=None, status=None) -> dict:
    enforce_permission(get_current_user_ctx() or {}, "graduationDesign.topic.export")
    if not batch_id:
        raise AppException("VALIDATION_ERROR", "导出前必须选择毕业设计批次")
    from app.services import excel
    items, _ = list_rounds(1, 100000, batch_id=batch_id, status=status)
    user = get_current_user_ctx() or {}
    return excel.build_export(build_round_export_spec(), items, operator_name=user.get("realName") or "系统")


def build_choice_export_spec():
    from app.services import excel
    C = excel.ColumnSpec
    return excel.ExportSpec(
        module_key="graduationDesign", biz_type="gd-topic-choice", sheet_title="选题志愿台账",
        file_name="选题志愿台账.xlsx",
        columns=[
            C("studentNo", "学号"),
            C("studentName", "姓名"),
            C("topicTitle", "志愿题目"),
            C("advisorName", "指导教师"),
            C("choiceOrder", "志愿序号"),
            C("statusLabel", "状态"),
        ],
    )


@sanitize_xlsx_export
def export_choices_xlsx(round_id, *, matched_only=False) -> dict:
    from app.core.context import get_current_user_ctx
    from app.services import excel
    items = list_choices(round_id)
    if matched_only:
        items = [x for x in items if x["status"] in ("MATCHED", "UNMATCHED")]
    user = get_current_user_ctx() or {}
    return excel.build_export(build_choice_export_spec(), items, operator_name=user.get("realName") or "系统")


def _choice_import_business_validate(round_id: str, row: dict, row_no: int) -> str | None:
    no = (row.get("studentNo") or "").strip()
    tno = (row.get("topicNo") or "").strip()
    ttitle = (row.get("topicTitle") or row.get("title") or "").strip()
    if not tno and not ttitle:
        return "题目编号或名称至少填一项"
    order = row.get("choiceOrder") or row.get("choice_order")
    try:
        o = int(order)
        if o < 1:
            return "志愿序号须为正整数"
        row["choiceOrder"] = o
    except (TypeError, ValueError):
        return "志愿序号须为正整数"
    with session() as db:
        _get_round(db, round_id)
        if no:
            stu = db.scalars(select(GraduationStudent).where(
                GraduationStudent.tenant_id == _tid(), GraduationStudent.student_no == no,
                GraduationStudent.is_deleted.is_(False))).first()
            if not stu:
                return f"学号 {no} 未在毕设学生名单"
        topic = None
        if tno:
            topic = db.scalars(select(GraduationTopic).where(
                GraduationTopic.tenant_id == _tid(), GraduationTopic.topic_no == tno,
                GraduationTopic.is_deleted.is_(False))).first()
        elif ttitle:
            topic = db.scalars(select(GraduationTopic).where(
                GraduationTopic.tenant_id == _tid(), GraduationTopic.title == ttitle,
                GraduationTopic.is_deleted.is_(False))).first()
        if not topic:
            return "题目编号或名称无法匹配已入池题目"
        if topic.review_status != "APPROVED" or topic.status != "CONFIRMED":
            return f"题目「{topic.title}」未入池"
        row["_topicId"] = str(topic.id)
    return None


def _persist_choice_import(round_id: str, rows: list[dict]) -> dict:
    with session() as db:
        r = _get_round(db, round_id)
        if r.status not in ("OPEN", "CLOSED"):
            raise AppException("DATA_CONFLICT", "仅进行中或已关闭轮次可导入志愿")
        stu_map = {s.student_no: int(s.id) for s in db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False))).all()}
        topics = db.scalars(select(GraduationTopic).where(
            GraduationTopic.tenant_id == _tid(), GraduationTopic.is_deleted.is_(False))).all()
        by_no = {(t.topic_no or "").strip(): t for t in topics if (t.topic_no or "").strip()}
        by_title = {t.title.strip(): t for t in topics}
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        gid = stu_map.get((row.get("studentNo") or "").strip())
        tno = (row.get("topicNo") or "").strip()
        ttitle = (row.get("topicTitle") or row.get("title") or "").strip()
        topic = by_no.get(tno) if tno else (by_title.get(ttitle) if ttitle else None)
        if not gid or not topic:
            continue
        order = row.get("choiceOrder") or row.get("choice_order")
        grouped.setdefault(gid, []).append({"topicId": str(topic.id), "choiceOrder": int(order)})
    submitted = 0
    for gid, chs in grouped.items():
        submit_choices(round_id, str(gid), chs, admin_import=True)
        submitted += 1
    return {"created": submitted, "students": submitted}


def _persist_choice_import_atomic(round_id: str, rows: list[dict]) -> dict:
    """Persist all imported choices and their evidence in one transaction."""
    with session() as db:
        round_row = _get_round(db, round_id)
        if round_row.status != "OPEN":
            raise AppException("DATA_CONFLICT", "Only an open topic round can accept imported choices")
        students = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).all()
        student_by_no = {student.student_no: student for student in students}
        topics = db.scalars(select(GraduationTopic).where(
            GraduationTopic.tenant_id == _tid(),
            GraduationTopic.is_deleted.is_(False),
        ).with_for_update()).all()
        topic_by_no = {
            (topic.topic_no or "").strip(): topic
            for topic in topics if (topic.topic_no or "").strip()
        }
        topic_by_title = {topic.title.strip(): topic for topic in topics}
        grouped: dict[int, list[tuple[int, GraduationTopic]]] = {}
        for row in rows:
            student = student_by_no.get((row.get("studentNo") or "").strip())
            topic_no = (row.get("topicNo") or "").strip()
            topic_title = (row.get("topicTitle") or row.get("title") or "").strip()
            topic = topic_by_no.get(topic_no) if topic_no else topic_by_title.get(topic_title)
            if not student or not topic:
                raise AppException("DATA_CONFLICT", "Import master data changed; run dry-run again")
            grouped.setdefault(int(student.id), []).append((
                int(row.get("choiceOrder") or row.get("choice_order")),
                topic,
            ))

        student_by_id = {int(student.id): student for student in students}
        for student_id, choices in grouped.items():
            student = student_by_id[student_id]
            assert_student_access(db, student, "topic.choice.submit")
            if len(choices) > int(round_row.max_choices or 3):
                raise AppException("VALIDATION_ERROR", "Imported choices exceed the round limit")
            if round_row.batch_id and int(student.batch_id or 0) != int(round_row.batch_id):
                raise AppException("DATA_CONFLICT", "Student and topic round batches do not match")
            orders = [order for order, _ in choices]
            if any(order < 1 for order in orders) or len(orders) != len(set(orders)):
                raise AppException("VALIDATION_ERROR", "Choice order must be positive and unique")
            for _, topic in choices:
                if topic.review_status != "APPROVED" or topic.status != "CONFIRMED":
                    raise AppException("DATA_CONFLICT", "Imported topic is no longer available")
                if round_row.batch_id and int(topic.batch_id or 0) != int(round_row.batch_id):
                    raise AppException("DATA_CONFLICT", "Topic and topic round batches do not match")

            existing = db.scalars(select(GraduationTopicChoice).where(
                GraduationTopicChoice.tenant_id == _tid(),
                GraduationTopicChoice.round_id == int(round_id),
                GraduationTopicChoice.gd_student_id == student_id,
            ).with_for_update()).all()
            by_order = {int(choice.choice_order): choice for choice in existing}
            requested = set(orders)
            for order, topic in choices:
                choice = by_order.get(order)
                if choice:
                    choice.topic_id = int(topic.id)
                    choice.status = "PENDING"
                    choice.is_deleted = False
                    choice.submission_version = int(choice.submission_version or 0) + 1
                else:
                    db.add(GraduationTopicChoice(
                        tenant_id=_tid(), round_id=int(round_id),
                        gd_student_id=student_id, topic_id=int(topic.id),
                        choice_order=order, status="PENDING",
                    ))
            for order, choice in by_order.items():
                if order not in requested:
                    choice.status = "WITHDRAWN"
                    choice.is_deleted = False
            _audit(
                db, round_id, "IMPORT_CHOICES",
                f"studentId={student_id}, choices={len(choices)}",
            )

        from app.services import excel
        job = excel.job_service.add_import_job(
            db, "graduationDesign", "gd-topic-choice", created=len(grouped),
        )
        db.commit()
        return {"created": len(grouped), "students": len(grouped), **job}


def _choice_import_spec(round_id: str):
    from app.services import excel
    C = excel.ColumnSpec

    return excel.ImportSpec(
        module_key="graduationDesign", biz_type="gd-topic-choice", template_name="选题志愿导入",
        columns=[
            C("studentNo", "学号", required=True, example="2022001001"),
            C("topicNo", "题目编号", example="T-2026-001", help_text="与题目编号或名称二选一"),
            C("topicTitle", "题目名称", example="智慧校园系统设计"),
            C("choiceOrder", "志愿序号", required=True, type="int", example="1"),
        ],
        notes=[
            "1. 同一学号多行表示多个志愿，志愿序号不可重复。",
            "2. 题目须已审核入池；学号须在毕设学生名单。",
            "3. 导入会覆盖该学生在当前轮次的已有志愿。",
            "4. 轮次须为「进行中」或「已关闭」状态。",
        ],
        business_validate=lambda row, row_no: _choice_import_business_validate(round_id, row, row_no),
        persist_rows=lambda rows: _persist_choice_import_atomic(round_id, rows),
        permission_key="graduationDesign.topic.create",
        audit_action="导入选题志愿",
    )


def choice_import_template_bytes(round_id: str) -> bytes:
    from app.services import excel
    return excel.build_template(_choice_import_spec(round_id))


def choice_import_read(round_id: str, content: bytes) -> list[dict]:
    from app.services import excel
    return excel.read_upload(_choice_import_spec(round_id), content)


def choice_import_dry_run(
    round_id: str, rows: list[dict], evidence: dict | None = None,
) -> dict:
    from app.services import excel
    return excel.pre_validate(_choice_import_spec(round_id), rows, evidence)


def choice_import_errors_pack(round_id: str, rows: list[dict], errors: list[dict]) -> dict:
    from app.services import excel
    return excel.build_error_rows(_choice_import_spec(round_id), rows, errors)


def choice_import_confirm(round_id: str, rows: list[dict], preview_token: str | None = None) -> dict:
    from app.services import excel
    spec = _choice_import_spec(round_id)
    result = excel.confirm_import(spec, rows, preview_token)
    return result


def active_round(batch_id=None) -> dict | None:
    """当前开放轮次（供前端展示）。"""
    with session() as db:
        q = select(GraduationTopicRound).where(
            GraduationTopicRound.tenant_id == _tid(), GraduationTopicRound.is_deleted.is_(False),
            GraduationTopicRound.status == "OPEN")
        if batch_id:
            q = q.where(GraduationTopicRound.batch_id == int(batch_id))
        r = db.scalars(q.order_by(GraduationTopicRound.id.desc())).first()
        if not r:
            return None
        batch = db.get(GraduationBatch, r.batch_id) if r.batch_id else None
        return _row_round(r, batch if batch and not batch.is_deleted else None)


# 正式 Service 在定义完基础导入契约后静态绑定安全版本。
from app.modules.graduation.services.graduation_command_service import withdraw_choices

_base_choice_import_business_validate = _choice_import_business_validate
_base_choice_import_spec = _choice_import_spec


def _choice_import_business_validate(round_id: str, row: dict, row_no: int):
    from app.modules.graduation.services.graduation_topic_import_consistency import (
        validate_open_round,
    )
    return validate_open_round(
        round_id, row, row_no, base_validate=_base_choice_import_business_validate,
    )


def _choice_import_spec(round_id: str):
    from app.modules.graduation.services.graduation_topic_import_consistency import (
        open_only_spec,
    )
    return open_only_spec(
        round_id,
        base_spec=_base_choice_import_spec,
        base_validate=_base_choice_import_business_validate,
    )
