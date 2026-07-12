"""毕业设计中心 · 选题轮次/志愿服务（轮次制互选 + 贪心匹配）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.models import (GraduationAuditTrail, GraduationBatch, GraduationStudent, GraduationTopic,
                        GraduationTopicChoice, GraduationTopicRound)
from app.services.db_service import _iso, _tid, session
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
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type="TOPIC_ROUND", biz_id=str(biz_id),
                                action=action, operator="系统", detail=detail, occurred_at=datetime.utcnow()))


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
    real_name = (user.get("realName") or "").strip()
    topic = db.get(GraduationTopic, choice.topic_id)
    if (role == "GD_MENTOR" and real_name and topic and not topic.is_deleted
            and topic.tenant_id == _tid() and (topic.advisor_name or "").strip() == real_name):
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
            GraduationTopicChoice.is_deleted.is_(False))
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


def submit_choices(round_id, gd_student_id, choices: list[dict], *, admin_import: bool = False) -> dict:
    if not choices:
        raise AppException("VALIDATION_ERROR", "请至少选择一个志愿")
    with session() as db:
        r = _get_round(db, round_id)
        allowed = ("OPEN",) if not admin_import else ("OPEN", "CLOSED")
        if r.status not in allowed:
            raise AppException("DATA_CONFLICT", "仅进行中的轮次可提交志愿" if not admin_import else "仅进行中或已关闭轮次可导入志愿")
        if len(choices) > int(r.max_choices or 3):
            raise AppException("VALIDATION_ERROR", f"最多 {r.max_choices} 个志愿")
        stu = db.get(GraduationStudent, int(gd_student_id))
        if not stu or stu.is_deleted or stu.tenant_id != _tid():
            raise not_found("毕设学生不存在")
        assert_student_access(db, stu, "topic.choice.submit")
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
        existing = db.scalars(select(GraduationTopicChoice).where(
            GraduationTopicChoice.tenant_id == _tid(), GraduationTopicChoice.round_id == int(round_id),
            GraduationTopicChoice.gd_student_id == int(gd_student_id),
            GraduationTopicChoice.is_deleted.is_(False))).all()
        for ex in existing:
            ex.is_deleted = True
        for ch in choices:
            db.add(GraduationTopicChoice(
                tenant_id=_tid(), round_id=int(round_id), gd_student_id=int(gd_student_id),
                topic_id=int(ch.get("topicId") or ch.get("topic_id")),
                choice_order=int(ch.get("choiceOrder") or ch.get("choice_order")),
                status="PENDING"))
        _audit(db, round_id, "SUBMIT_CHOICES", f"学生 {stu.name} 提交 {len(choices)} 个志愿")
        db.commit()
        return {"submitted": len(choices)}


def get_choice_detail(choice_id) -> dict:
    """志愿详情（含关联题目导师姓名，供教师端范围校验）。"""
    with session() as db:
        c = db.get(GraduationTopicChoice, int(choice_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("志愿不存在")
        stu = db.get(GraduationStudent, c.gd_student_id)
        assert_student_access(db, stu, "topic.choice.detail")
        topic = db.get(GraduationTopic, c.topic_id)
        return _choice_row(c, stu, topic)


def list_pending_choices_for_advisor(advisor_name: str) -> list[dict]:
    """教师端·本人指导题目下待确认的志愿（PENDING）。"""
    if not advisor_name:
        return []
    if not has_full_scope():
        user = get_current_user_ctx() or {}
        role = (user.get("currentRoleCode") or user.get("userType") or "").strip().upper()
        real_name = (user.get("realName") or "").strip()
        if role != "GD_MENTOR" or not real_name or real_name != advisor_name.strip():
            raise no_permission("Cannot query pending choices for another advisor")
    with session() as db:
        topic_ids = [t.id for t in db.scalars(select(GraduationTopic).where(
            GraduationTopic.tenant_id == _tid(), GraduationTopic.is_deleted.is_(False),
            GraduationTopic.advisor_name == advisor_name)).all()]
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
        if r.status not in ("OPEN", "CLOSED"):
            raise AppException("DATA_CONFLICT", "仅进行中或已关闭轮次可执行匹配")
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
        errors: list[str] = []
        for w in winners:
            try:
                gd_stu_svc.assign_topic_in_session(
                    db, str(w["gd_student_id"]), str(w["topic_id"]), relationship_authorized=True
                )
                matched += 1
                success_ids.add(int(w["id"]))
            except AppException as e:
                errors.append(str(e.message if hasattr(e, "message") else e))
            except Exception as e:
                errors.append(str(e))
        for c in pending:
            c.status = "MATCHED" if int(c.id) in success_ids else "UNMATCHED"
        r.status = "MATCHED"
        _audit(db, round_id, "MATCH", f"匹配成功 {matched} 人")
        db.commit()
        return {"matched": matched, "totalChoices": len(payload), "errors": errors}


# ═══════════ 退选重选 / 容量冲突复核 / 统计 / 归档（Batch 3） ═══════════

def withdraw_choices(round_id, gd_student_id) -> dict:
    """学生退选：撤回本轮全部待处理志愿（仅进行中轮次；已确认/已匹配的须走变更流程，不可自助退选）。
    退选后学生可重新提交志愿（submit_choices 覆盖语义）。"""
    with session() as db:
        r = _get_round(db, round_id)
        if r.status != "OPEN":
            raise AppException("DATA_CONFLICT", "仅进行中的轮次可退选")
        stu = db.get(GraduationStudent, int(gd_student_id))
        assert_student_access(db, stu, "topic.choice.withdraw")
        chs = db.scalars(select(GraduationTopicChoice).where(
            GraduationTopicChoice.tenant_id == _tid(), GraduationTopicChoice.round_id == int(round_id),
            GraduationTopicChoice.gd_student_id == int(gd_student_id),
            GraduationTopicChoice.is_deleted.is_(False))).all()
        if not chs:
            raise not_found("当前没有可退选的志愿")
        if any(c.status in ("CONFIRMED", "MATCHED") for c in chs):
            raise AppException("DATA_CONFLICT", "已被确认/匹配的选题不可自助退选，请走「课题变更」流程")
        for c in chs:
            c.is_deleted = True
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


def export_rounds_xlsx(batch_id=None, status=None) -> dict:
    from app.core.context import get_current_user_ctx
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
        persist_rows=lambda rows: _persist_choice_import(round_id, rows),
        permission_key="graduationDesign.topicRound.import",
        audit_action="导入选题志愿",
    )


def choice_import_template_bytes(round_id: str) -> bytes:
    from app.services import excel
    return excel.build_template(_choice_import_spec(round_id))


def choice_import_read(round_id: str, content: bytes) -> list[dict]:
    from app.services import excel
    return excel.read_upload(_choice_import_spec(round_id), content)


def choice_import_dry_run(round_id: str, rows: list[dict]) -> dict:
    from app.services import excel
    return excel.pre_validate(_choice_import_spec(round_id), rows)


def choice_import_errors_pack(round_id: str, rows: list[dict], errors: list[dict]) -> dict:
    from app.services import excel
    return excel.build_error_rows(_choice_import_spec(round_id), rows, errors)


def choice_import_confirm(round_id: str, rows: list[dict]) -> dict:
    from app.services import excel
    spec = _choice_import_spec(round_id)
    pre = excel.pre_validate(spec, rows)
    result = excel.confirm_import(spec, rows)
    excel.job_service.record_import(spec.module_key, spec.biz_type, pre=pre,
                                    result=result, status="IMPORTED",
                                    remark=f"roundId={round_id}")
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
