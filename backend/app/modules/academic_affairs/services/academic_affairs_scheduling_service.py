"""13B 排课管理 service（SM-07 增强层）。

在既有课表批次/条目/冲突检测（academic_affairs_schedule_service）之上叠加：
- 排课规则中心（教师可用时间要求/教室类型/周学时约束等，规则键值）
- 教师可用时间采集（教师提交 → 学院采纳/驳回）
- 全量冲突报告（批次内两两检测，收集全部冲突并 HARD/SOFT 分级；既有 _detect_conflict 只返首条）

不改既有 schedule_service/课表页面（施工卡 §6.4 复用为主，不推倒）；教室字典未定稿前沿用 classroom_text 文本。
"""
from __future__ import annotations

import json
from datetime import datetime

from app.core.affairs_security import _derive_keys, build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.modules.academic_affairs.services.academic_affairs_schedule_service import _weeks_overlap
from app.services.db_service import _tid, session


def _bad(m):
    return AppException("VALIDATION_ERROR", m)


def _invalid(m):
    return AppException("DATA_CONFLICT", m, http_status=409)


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("userId") or ctx.get("loginName") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, biz_type, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=biz_id, action=action,
                             operator=_op(), role_name=_role(), detail=detail[:990], occurred_at=datetime.utcnow()))


def _ctx(user, db):
    return build_affairs_context(user, db)


def _require_school(ctx):
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可管理排课规则")


# ══════════ 排课规则中心 ══════════

def _rule_dto(r):
    return {"ruleId": str(r.id), "termId": str(r.term_id) if r.term_id else None,
            "batchId": str(r.batch_id) if r.batch_id else None, "ruleKey": r.rule_key,
            "ruleValue": json.loads(r.rule_value_json) if r.rule_value_json else None,
            "remark": r.remark, "status": r.status}


def save_rule(user, body):
    """保存/更新排课规则（同 term+batch+key 唯一，存在则更新）。"""
    from app.models import AaScheduleRule
    with session() as db:
        _require_school(_ctx(user, db))
        key = (getattr(body, "ruleKey", None) or "").strip()
        if not key:
            raise _bad("规则键必填")
        term_id = int(body.termId) if getattr(body, "termId", None) else None
        batch_id = int(body.batchId) if getattr(body, "batchId", None) else None
        r = db.query(AaScheduleRule).filter(AaScheduleRule.tenant_id == _tid(), AaScheduleRule.rule_key == key,
                                            AaScheduleRule.term_id == term_id, AaScheduleRule.batch_id == batch_id,
                                            AaScheduleRule.is_deleted.is_(False)).first()
        val = json.dumps(getattr(body, "ruleValue", None), ensure_ascii=False) if getattr(body, "ruleValue", None) is not None else None
        if r:
            r.rule_value_json = val
            r.remark = getattr(body, "remark", None)
        else:
            r = AaScheduleRule(tenant_id=_tid(), term_id=term_id, batch_id=batch_id, rule_key=key,
                               rule_value_json=val, remark=getattr(body, "remark", None), status="ENABLED")
            db.add(r)
        db.flush()
        _audit(db, "AA_SCHEDULE_RULE", r.id, "SCHEDULE_RULE_SAVE", key)
        db.commit()
        return _rule_dto(r)


def list_rules(user, term_id=None, batch_id=None):
    from app.models import AaScheduleRule
    with session() as db:
        _ctx(user, db)
        q = db.query(AaScheduleRule).filter(AaScheduleRule.tenant_id == _tid(), AaScheduleRule.is_deleted.is_(False))
        if term_id:
            q = q.filter(AaScheduleRule.term_id == int(term_id))
        if batch_id:
            q = q.filter(AaScheduleRule.batch_id == int(batch_id))
        return [_rule_dto(r) for r in q.order_by(AaScheduleRule.rule_key).all()]


def delete_rule(user, rule_id):
    from app.models import AaScheduleRule
    with session() as db:
        _require_school(_ctx(user, db))
        r = db.query(AaScheduleRule).filter(AaScheduleRule.id == rule_id, AaScheduleRule.tenant_id == _tid()).first()
        if not r:
            raise not_found("规则不存在")
        r.is_deleted = True
        _audit(db, "AA_SCHEDULE_RULE", r.id, "SCHEDULE_RULE_DELETE", r.rule_key)
        db.commit()
        return {"ruleId": str(r.id), "deleted": True}


# ══════════ 教师可用时间 ══════════

def _avail_dto(a):
    return {"availabilityId": str(a.id), "teacherKey": a.teacher_key, "teacherName": a.teacher_name,
            "termId": str(a.term_id) if a.term_id else None, "weekday": a.weekday, "slotNo": a.slot_no,
            "reason": a.reason, "reviewReason": a.review_reason, "status": a.status}


def submit_availability(user, body):
    """教师提交不可排课时段（同 teacher+term+weekday+slot 唯一，存在则更新回 PENDING）。"""
    from app.models import AaTeacherAvailability
    with session() as db:
        ctx0 = get_current_user_ctx() or {}
        # teacher_key 与课表条目同源：课表按登录名式键(counselor01)存；mock userId=u_counselor01 需剥 u_ 前缀
        uid = str(ctx0.get("userId") or "")
        tkey = (ctx0.get("loginName") or (uid[2:] if uid.startswith("u_") else uid)
                or next(iter(_derive_keys(user)), None) or _op())
        term_id = int(body.termId) if getattr(body, "termId", None) else None
        weekday = int(body.weekday)
        slot_no = int(body.slotNo)
        a = db.query(AaTeacherAvailability).filter(
            AaTeacherAvailability.tenant_id == _tid(), AaTeacherAvailability.teacher_key == tkey,
            AaTeacherAvailability.term_id == term_id, AaTeacherAvailability.weekday == weekday,
            AaTeacherAvailability.slot_no == slot_no).first()
        ctx = get_current_user_ctx() or {}
        if a:
            a.reason = getattr(body, "reason", None)
            a.status = "PENDING"
        else:
            a = AaTeacherAvailability(tenant_id=_tid(), teacher_key=tkey,
                                      teacher_name=ctx.get("realName"), term_id=term_id, weekday=weekday,
                                      slot_no=slot_no, reason=getattr(body, "reason", None), status="PENDING")
            db.add(a)
        db.flush()
        _audit(db, "AA_TEACHER_AVAIL", a.id, "TEACHER_AVAIL_SUBMIT", f"周{weekday}第{slot_no}节")
        db.commit()
        return _avail_dto(a)


def list_availability(user, term_id=None, teacher_key=None, status=None, mine=False):
    from app.models import AaTeacherAvailability
    with session() as db:
        _ctx(user, db)
        q = db.query(AaTeacherAvailability).filter(AaTeacherAvailability.tenant_id == _tid(),
                                                   AaTeacherAvailability.is_deleted.is_(False))
        if mine:
            keys = _derive_keys(user)
            q = q.filter(AaTeacherAvailability.teacher_key.in_(list(keys) or [""]))
        if term_id:
            q = q.filter(AaTeacherAvailability.term_id == int(term_id))
        if teacher_key:
            q = q.filter(AaTeacherAvailability.teacher_key == teacher_key)
        if status:
            q = q.filter(AaTeacherAvailability.status == status)
        return [_avail_dto(a) for a in q.order_by(AaTeacherAvailability.id.desc()).all()]


def review_availability(user, avail_id, action, reason=""):
    """学院采纳/驳回教师可用时间。"""
    from app.models import AaTeacherAvailability
    with session() as db:
        _require_school(_ctx(user, db))
        a = db.query(AaTeacherAvailability).filter(AaTeacherAvailability.id == avail_id,
                                                   AaTeacherAvailability.tenant_id == _tid()).first()
        if not a:
            raise not_found("教师可用时间记录不存在")
        if a.status != "PENDING":
            raise _invalid("仅待处理记录可采纳/驳回")
        if action == "ADOPT":
            a.status = "ADOPTED"
        elif action == "REJECT":
            a.status = "REJECTED"
            a.review_reason = (reason or "").strip()
        else:
            raise _bad("非法动作")
        _audit(db, "AA_TEACHER_AVAIL", a.id, "TEACHER_AVAIL_REVIEW", action)
        db.commit()
        return _avail_dto(a)


# ══════════ 全量冲突报告（HARD/SOFT 分级） ══════════

def conflict_report(user, batch_id):
    """批次内两两检测，收集全部冲突（既有 _detect_conflict 只返首条）。
    HARD：同教师/同班级/同教室 + 时段重叠（物理冲突，必须清零才可发布）。
    SOFT：与教师已采纳的不可排课时间(ADOPTED availability)撞（资源类，可备注放行）。"""
    from app.models import AaScheduleItem, AaTeacherAvailability
    with session() as db:
        _ctx(user, db)
        items = db.query(AaScheduleItem).filter(AaScheduleItem.batch_id == batch_id, AaScheduleItem.tenant_id == _tid(),
                                                AaScheduleItem.status == "EFFECTIVE",
                                                AaScheduleItem.is_deleted.is_(False)).all()
        hard = []
        n = len(items)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = items[i], items[j]
                if a.weekday != b.weekday or a.slot_no != b.slot_no:
                    continue
                if not _weeks_overlap(a.start_week, a.end_week, a.week_parity,
                                      b.start_week, b.end_week, b.week_parity):
                    continue
                dim = None
                if a.teacher_key and a.teacher_key == b.teacher_key:
                    dim = "TEACHER"
                elif a.class_id and a.class_id == b.class_id:
                    dim = "CLASS"
                elif a.classroom_text and a.classroom_text == b.classroom_text:
                    dim = "CLASSROOM"
                if dim:
                    hard.append({"level": "HARD", "dimension": dim, "weekday": a.weekday, "slotNo": a.slot_no,
                                 "itemA": {"id": str(a.id), "courseName": a.course_name, "className": a.class_name,
                                           "teacherName": a.teacher_name, "classroom": a.classroom_text},
                                 "itemB": {"id": str(b.id), "courseName": b.course_name, "className": b.class_name,
                                           "teacherName": b.teacher_name, "classroom": b.classroom_text}})
        # SOFT：撞教师已采纳的不可排课时段
        soft = []
        adopted = db.query(AaTeacherAvailability).filter(AaTeacherAvailability.tenant_id == _tid(),
                                                         AaTeacherAvailability.status == "ADOPTED",
                                                         AaTeacherAvailability.is_deleted.is_(False)).all()
        avail_set = {(a.teacher_key, a.weekday, a.slot_no) for a in adopted}
        for it in items:
            if it.teacher_key and (it.teacher_key, it.weekday, it.slot_no) in avail_set:
                soft.append({"level": "SOFT", "dimension": "TEACHER_UNAVAILABLE", "weekday": it.weekday,
                             "slotNo": it.slot_no, "item": {"id": str(it.id), "courseName": it.course_name,
                                                            "teacherName": it.teacher_name}})
        return {"batchId": str(batch_id), "hardCount": len(hard), "softCount": len(soft),
                "canPrePublish": len(hard) == 0, "hardConflicts": hard, "softConflicts": soft}


# ══════════ 10号卡·排课结果：汇总统计（预发布前核对站） ══════════

def summary(user, batch_id):
    """已排/应排任务数与学时、HARD/SOFT 冲突数——预发布前最后核对（10号卡）。

    应排任务口径：与本课表批次同学期(term_id)的 READY 教学任务（进入排课资源池，见 SM-06 §7.2）；
    已排任务：本批次条目中 task_id 命中该 READY 集合的去重任务数；已排学时=条目数（每条=1节）；
    应排学时=READY 任务 weekly_hours 汇总。冲突数复用 conflict_report（HARD/SOFT 分级）。"""
    from app.models import AaScheduleBatch, AaScheduleItem, AaTeachingTask, AaTeachingTaskBatch
    with session() as db:
        _ctx(user, db)
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        tb_ids = [r[0] for r in db.query(AaTeachingTaskBatch.id).filter(
            AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.term_id == b.term_id,
            AaTeachingTaskBatch.is_deleted.is_(False)).all()]
        ready_tasks = db.query(AaTeachingTask).filter(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id.in_(tb_ids or [-1]),
            AaTeachingTask.status == "READY", AaTeachingTask.is_deleted.is_(False)).all()
        ready_task_ids = {t.id for t in ready_tasks}
        total_tasks = len(ready_tasks)
        expected_hours = sum(t.weekly_hours or 0 for t in ready_tasks)
        items = db.query(AaScheduleItem).filter(
            AaScheduleItem.tenant_id == _tid(), AaScheduleItem.batch_id == b.id,
            AaScheduleItem.status == "EFFECTIVE", AaScheduleItem.is_deleted.is_(False)).all()
        scheduled_task_ids = {it.task_id for it in items if it.task_id}
        scheduled_tasks = len(scheduled_task_ids & ready_task_ids)
        scheduled_hours = len(items)
        rate = round(scheduled_tasks / total_tasks * 100, 1) if total_tasks else 0.0
        cr = conflict_report(user, batch_id)
        return {"batchId": str(batch_id), "batchStatus": b.status,
                "totalTasks": total_tasks, "scheduledTasks": scheduled_tasks, "completionRate": rate,
                "scheduledHours": scheduled_hours, "expectedHours": expected_hours,
                "hardConflicts": cr["hardCount"], "softConflicts": cr["softCount"],
                "canPrePublish": cr["canPrePublish"]}
