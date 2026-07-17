"""13B 教学评价 service。

评教批次(6态) → 生成应评任务(挂教学任务,按评价类型) → 开放窗口(学生匿名/教师自评/同行/督导提交)
→ 关闭核算(学生均分分级,D-06 不加权) → 发布结果(教师可见本人) → 申诉(学院初审→教务终审) → 归档。

D-04 学生评教匿名：record 不存 evaluator 身份，仅存答卷与得分 + task.submitted_count 核销。
复用：AaTeachingTask(应评对象)/AffairsAuditTrail(biz_type=AA_EVALUATION)。
"""
from __future__ import annotations

import json
from datetime import datetime

from app.core.affairs_security import _derive_keys, build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.services.db_service import _iso, _tid, session

_B_DRAFT, _B_PUBLISHED, _B_OPEN = "DRAFT", "PUBLISHED", "OPEN"
_B_CLOSED, _B_RESULT, _B_ARCHIVED = "CLOSED", "RESULT_READY", "ARCHIVED"
_ROLE_EVAL_TYPES = ("SELF", "PEER", "SUPERVISOR")


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


def _tkey():
    ctx = get_current_user_ctx() or {}
    uid = str(ctx.get("userId") or "")
    return ctx.get("loginName") or (uid[2:] if uid.startswith("u_") else uid) or _op()


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_EVALUATION", biz_id=biz_id, action=action,
                             operator=_op(), role_name=_role(), detail=detail[:990], occurred_at=datetime.utcnow()))


def _ctx(user, db):
    return build_affairs_context(user, db)


def _require_school(ctx):
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可管理评教批次")


def _level(avg):
    if avg is None:
        return None
    if avg >= 90:
        return "EXCELLENT"
    if avg >= 80:
        return "GOOD"
    if avg >= 60:
        return "PASS"
    return "NEED_IMPROVE"


# 多来源评价（正方教师端5.x：学生评教/教师自评/同行评价/督导评价）
_EVALUATOR_TYPES = ("STUDENT", "SELF", "PEER", "SUPERVISOR")
# 综合分权重（designSource=ai_proposal，学校可后续按教学质量管理制度调整；缺失来源按现有来源归一化，不拉低）
_WEIGHTS = {"STUDENT": 0.6, "SUPERVISOR": 0.2, "PEER": 0.15, "SELF": 0.05}


def _composite(stu, self_s, peer, sup):
    """多来源加权综合分：仅对实际有分的来源按其权重归一化合成（无督导/同行时退化为学生均分）。"""
    parts = [("STUDENT", stu), ("SELF", self_s), ("PEER", peer), ("SUPERVISOR", sup)]
    active = [(k, v) for (k, v) in parts if v is not None]
    if not active:
        return None
    tw = sum(_WEIGHTS[k] for k, _ in active)
    if tw <= 0:
        return None
    return round(sum(_WEIGHTS[k] * v for k, v in active) / tw, 2)


# ══════════ 批次 ══════════

def _batch_dto(b):
    return {"batchId": str(b.id), "batchName": b.batch_name, "termId": str(b.term_id) if b.term_id else None,
            "anonymous": b.anonymous, "status": b.status,
            "template": json.loads(b.template_json) if b.template_json else None,
            "resultPublishedAt": _iso(b.result_published_at)}


def _get_batch(db, bid):
    from app.models import AaEvaluationBatch
    b = db.query(AaEvaluationBatch).filter(AaEvaluationBatch.id == bid, AaEvaluationBatch.tenant_id == _tid(),
                                           AaEvaluationBatch.is_deleted.is_(False)).first()
    if not b:
        raise not_found("评教批次不存在")
    return b


def create_batch(user, body):
    from app.models import AaEvaluationBatch
    with session() as db:
        _require_school(_ctx(user, db))
        name = (getattr(body, "batchName", None) or "").strip()
        if not name:
            raise _bad("批次名称必填")
        b = AaEvaluationBatch(tenant_id=_tid(), batch_name=name,
                              term_id=int(body.termId) if getattr(body, "termId", None) else None,
                              scope_json=json.dumps(body.scope, ensure_ascii=False) if getattr(body, "scope", None) else None,
                              template_json=json.dumps(body.template, ensure_ascii=False) if getattr(body, "template", None) else None,
                              anonymous=bool(getattr(body, "anonymous", True)), status=_B_DRAFT)
        db.add(b); db.flush()
        _audit(db, b.id, "EVAL_BATCH_CREATE", name)
        db.commit()
        return _batch_dto(b)


def list_batches(user, status=None, page=1, page_size=20):
    from app.models import AaEvaluationBatch
    with session() as db:
        _ctx(user, db)
        q = db.query(AaEvaluationBatch).filter(AaEvaluationBatch.tenant_id == _tid(),
                                               AaEvaluationBatch.is_deleted.is_(False))
        if status:
            q = q.filter(AaEvaluationBatch.status == status)
        rows = q.order_by(AaEvaluationBatch.id.desc()).all()
        return [_batch_dto(b) for b in rows[(page - 1) * page_size: page * page_size]], len(rows)


def get_batch(user, bid):
    with session() as db:
        _ctx(user, db)
        return _batch_dto(_get_batch(db, bid))


def generate_tasks(user, bid, teaching_task_ids, evaluator_type="STUDENT"):
    """按教学任务生成某来源的应评任务（每教学任务一条）。
    evaluator_type ∈ STUDENT/SELF/PEER/SUPERVISOR（正方教师端5.x 多角色评价）。"""
    from app.models import AaEvaluationTask, AaTeachingTask
    et = (evaluator_type or "STUDENT").upper()
    if et not in _EVALUATOR_TYPES:
        raise _bad("评价来源非法（STUDENT/SELF/PEER/SUPERVISOR）")
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, bid)
        if b.status != _B_DRAFT:
            raise _invalid("仅 DRAFT 批次可生成应评任务")
        cnt = 0
        for tt_id in [int(x) for x in teaching_task_ids if str(x).isdigit()]:
            tt = db.query(AaTeachingTask).filter(AaTeachingTask.id == tt_id, AaTeachingTask.tenant_id == _tid()).first()
            if not tt:
                continue
            dup = db.query(AaEvaluationTask).filter(AaEvaluationTask.tenant_id == _tid(),
                                                    AaEvaluationTask.batch_id == b.id,
                                                    AaEvaluationTask.teaching_task_id == tt_id,
                                                    AaEvaluationTask.evaluator_type == et).first()
            if dup:
                continue
            db.add(AaEvaluationTask(tenant_id=_tid(), batch_id=b.id, teaching_task_id=tt_id,
                                    course_id=getattr(tt, "course_id", None), course_name=getattr(tt, "course_name", None),
                                    class_id=getattr(tt, "class_id", None), teacher_key=getattr(tt, "teacher_key", None),
                                    teacher_name=getattr(tt, "teacher_name", None), evaluator_type=et,
                                    status="PENDING"))
            cnt += 1
        _audit(db, b.id, "EVAL_TASK_GENERATE", f"{et} {cnt} 条应评任务")
        db.commit()
        return {"batchId": str(b.id), "taskCount": cnt, "evaluatorType": et}


def generate_role_tasks(user, bid, evaluator_type, assignments):
    """为教师自评/同行评价/督导评价生成应评任务（挂教学任务，指定评价人）。

    Tier1 R2（本轮新增）：`t_aa_evaluation_task` 既有 `evaluator_key` 列此前只在 STUDENT 类留空，
    SELF/PEER/SUPERVISOR 三类始终没有生成入口（`generate_tasks` 硬编码 evaluator_type=STUDENT）。
    assignments=[{teachingTaskId, evaluatorKey?}]；SELF 类 evaluatorKey 缺省时=该教学任务授课教师本人（自评）；
    PEER/SUPERVISOR 类必须显式指定 evaluatorKey（教务处按同行/督导人工号指定，本项目未建督导角色/数据范围，
    评价人身份用既有 `_derive_keys` 同源匹配机制核验，而非新建 SUPERVISE scope_type，见二级施工包 D-07 说明）。
    """
    from app.models import AaEvaluationTask, AaTeachingTask
    if evaluator_type not in _ROLE_EVAL_TYPES:
        raise _bad("非法评价类型，仅支持 SELF/PEER/SUPERVISOR")
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, bid)
        if b.status != _B_DRAFT:
            raise _invalid("仅 DRAFT 批次可生成应评任务")
        cnt = 0
        for a in assignments or []:
            tt_id = a.get("teachingTaskId") if isinstance(a, dict) else getattr(a, "teachingTaskId", None)
            if not (tt_id and str(tt_id).isdigit()):
                continue
            tt_id = int(tt_id)
            tt = db.query(AaTeachingTask).filter(AaTeachingTask.id == tt_id, AaTeachingTask.tenant_id == _tid()).first()
            if not tt:
                continue
            ev_key = ((a.get("evaluatorKey") if isinstance(a, dict) else getattr(a, "evaluatorKey", None)) or "").strip()
            if evaluator_type == "SELF":
                ev_key = ev_key or (getattr(tt, "teacher_key", None) or "")
            if not ev_key:
                raise _bad(f"{evaluator_type} 类型必须指定评价人 evaluatorKey")
            dup = db.query(AaEvaluationTask).filter(AaEvaluationTask.tenant_id == _tid(),
                                                    AaEvaluationTask.batch_id == b.id,
                                                    AaEvaluationTask.teaching_task_id == tt_id,
                                                    AaEvaluationTask.evaluator_type == evaluator_type,
                                                    AaEvaluationTask.evaluator_key == ev_key).first()
            if dup:
                continue
            db.add(AaEvaluationTask(tenant_id=_tid(), batch_id=b.id, teaching_task_id=tt_id,
                                    course_id=getattr(tt, "course_id", None), course_name=getattr(tt, "course_name", None),
                                    class_id=getattr(tt, "class_id", None), teacher_key=getattr(tt, "teacher_key", None),
                                    teacher_name=getattr(tt, "teacher_name", None), evaluator_type=evaluator_type,
                                    evaluator_key=ev_key, status="PENDING"))
            cnt += 1
        _audit(db, b.id, "EVAL_TASK_GENERATE", f"{evaluator_type} {cnt} 条应评任务")
        db.commit()
        return {"batchId": str(b.id), "evaluatorType": evaluator_type, "taskCount": cnt}


def list_my_role_tasks(user, evaluator_type, batch_id=None):
    """我的评价任务（教师自评/同行/督导查看自己的待办与已提交，按 evaluator_key 匹配当前登录身份）。"""
    from app.models import AaEvaluationBatch, AaEvaluationTask
    if evaluator_type not in _ROLE_EVAL_TYPES:
        raise _bad("非法评价类型，仅支持 SELF/PEER/SUPERVISOR")
    with session() as db:
        _ctx(user, db)
        keys = list(_derive_keys(user)) or [""]
        q = db.query(AaEvaluationTask).filter(AaEvaluationTask.tenant_id == _tid(),
                                              AaEvaluationTask.is_deleted.is_(False),
                                              AaEvaluationTask.evaluator_type == evaluator_type,
                                              AaEvaluationTask.evaluator_key.in_(keys))
        if batch_id:
            q = q.filter(AaEvaluationTask.batch_id == int(batch_id))
        rows = q.order_by(AaEvaluationTask.id.desc()).all()
        bids = {t.batch_id for t in rows}
        bstatus = {}
        if bids:
            for b in db.query(AaEvaluationBatch).filter(AaEvaluationBatch.tenant_id == _tid(),
                                                        AaEvaluationBatch.id.in_(list(bids))).all():
                bstatus[b.id] = b.status
        return [{"taskId": str(t.id), "batchId": str(t.batch_id), "batchStatus": bstatus.get(t.batch_id),
                 "courseName": t.course_name, "teacherName": t.teacher_name,
                 "evaluatorType": t.evaluator_type, "status": t.status} for t in rows]


def _advance(user, bid, frm, to, action):
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, bid)
        if b.status != frm:
            raise _invalid(f"仅 {frm} 批次可{action}，当前 {b.status}")
        b.status = to
        if to == _B_RESULT:
            b.result_published_at = datetime.utcnow()
        _audit(db, b.id, f"EVAL_BATCH_{action}", action)
        db.commit()
        return _batch_dto(b)


def publish_batch(user, bid):
    from app.models import AaEvaluationTask
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, bid)
        if b.status != _B_DRAFT:
            raise _invalid("仅 DRAFT 批次可发布")
        cnt = db.query(AaEvaluationTask).filter(AaEvaluationTask.batch_id == b.id, AaEvaluationTask.tenant_id == _tid()).count()
        if not cnt:
            raise _bad("批次无应评任务，不可发布")
        b.status = _B_PUBLISHED
        _audit(db, b.id, "EVAL_BATCH_PUBLISH", "发布")
        db.commit()
        return _batch_dto(b)


def open_batch(user, bid):
    return _advance(user, bid, _B_PUBLISHED, _B_OPEN, "OPEN")


def archive_batch(user, bid):
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, bid)
        if b.status == _B_ARCHIVED:
            return _batch_dto(b)
        if b.status != _B_RESULT:
            raise _invalid("仅 RESULT_READY 批次可归档")
        b.status = _B_ARCHIVED
        _audit(db, b.id, "EVAL_BATCH_ARCHIVE", "归档")
        db.commit()
        return _batch_dto(b)


def close_and_score(user, bid):
    """OPEN→核算→RESULT_READY：多来源(学生/自评/同行/督导)分别求均分，按权重合成综合分。
    level 取综合分（无其它来源时综合分==学生均分，与旧口径一致）。"""
    from app.models import AaEvaluationRecord, AaEvaluationResult, AaEvaluationTask
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, bid)
        if b.status != _B_OPEN:
            raise _invalid("仅 OPEN 批次可关闭核算")
        tasks = db.query(AaEvaluationTask).filter(AaEvaluationTask.batch_id == b.id,
                                                  AaEvaluationTask.tenant_id == _tid()).all()
        agg: dict = {}   # teaching_task_id -> {evaluator_type: [scores]}
        meta: dict = {}  # teaching_task_id -> (teacher_key, teacher_name, course_name)
        for t in tasks:
            recs = db.query(AaEvaluationRecord).filter(AaEvaluationRecord.task_id == t.id,
                                                       AaEvaluationRecord.tenant_id == _tid()).all()
            scores = [float(r.objective_score) for r in recs if r.objective_score is not None]
            agg.setdefault(t.teaching_task_id, {}).setdefault(t.evaluator_type, []).extend(scores)
            meta[t.teaching_task_id] = (t.teacher_key, t.teacher_name, t.course_name)
        for ttid, by_type in agg.items():
            def _avg(tp, _bt=by_type):
                s = _bt.get(tp, [])
                return (round(sum(s) / len(s), 2) if s else None), len(s)
            stu_avg, stu_n = _avg("STUDENT")
            self_avg, _self_n = _avg("SELF")
            peer_avg, peer_n = _avg("PEER")
            sup_avg, sup_n = _avg("SUPERVISOR")
            comp = _composite(stu_avg, self_avg, peer_avg, sup_avg)
            tk, tn, cn = meta[ttid]
            existing = db.query(AaEvaluationResult).filter(AaEvaluationResult.tenant_id == _tid(),
                                                           AaEvaluationResult.batch_id == b.id,
                                                           AaEvaluationResult.teaching_task_id == ttid).first()
            if not existing:
                existing = AaEvaluationResult(tenant_id=_tid(), batch_id=b.id, teaching_task_id=ttid,
                                              teacher_key=tk, teacher_name=tn, course_name=cn, published=False)
                db.add(existing)
            existing.student_avg, existing.student_count = stu_avg, stu_n
            existing.self_score = self_avg
            existing.peer_avg, existing.peer_count = peer_avg, peer_n
            existing.supervisor_avg, existing.supervisor_count = sup_avg, sup_n
            existing.composite_score = comp
            existing.level = _level(comp if comp is not None else stu_avg)
        b.status = _B_RESULT
        b.result_published_at = datetime.utcnow()
        _audit(db, b.id, "EVAL_BATCH_SCORE", f"多来源核算 {len(agg)} 门结果")
        db.commit()
        return _batch_dto(b)


def publish_results(user, bid):
    from app.models import AaEvaluationResult
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, bid)
        if b.status != _B_RESULT:
            raise _invalid("仅 RESULT_READY 批次可发布结果")
        db.query(AaEvaluationResult).filter(AaEvaluationResult.batch_id == b.id,
                                            AaEvaluationResult.tenant_id == _tid()).update(
            {AaEvaluationResult.published: True}, synchronize_session=False)
        _audit(db, b.id, "EVAL_RESULT_PUBLISH", "发布结果")
        db.commit()
        return {"batchId": str(b.id), "published": True}


# ══════════ 提交评价 ══════════

def submit_evaluation(user, task_id, answers, objective_score, comment=None):
    """提交评价。学生类：匿名不存 evaluator，task.submitted_count+1；其它类：存 evaluator_key。

    Tier1 R2 修复：此前本函数对 SELF/PEER/SUPERVISOR 三类任务未校验"提交人是否就是任务指定的评价人"
    （evaluator_key），也未拦截重复提交——任何已认证用户凭 taskId 即可代任意教师提交/反复提交评价，
    属越权与状态机漏洞（对照二级施工包 §7.2 状态机 PENDING→SUBMITTED 后应拒绝再次提交）。现补齐：
    非 STUDENT 类必须 evaluator_key 命中当前登录身份的 `_derive_keys` 匹配集，否则 403；
    已 SUBMITTED 的非 STUDENT 任务重复提交 409（STUDENT 类任务代表"班级/课程整体评教槽位"，
    由多名学生各自提交、以 submitted_count 计数，不适用单任务幂等拦截，此处不变更既有语义）。
    """
    from app.models import AaEvaluationRecord, AaEvaluationTask
    with session() as db:
        _ctx(user, db)
        t = db.query(AaEvaluationTask).filter(AaEvaluationTask.id == task_id, AaEvaluationTask.tenant_id == _tid()).first()
        if not t:
            raise not_found("应评任务不存在")
        if t.evaluator_type != "STUDENT":
            keys = _derive_keys(user)
            if not t.evaluator_key or t.evaluator_key not in keys:
                raise no_permission("仅本任务指定的评价人本人可提交")
            if t.status == "SUBMITTED":
                raise _invalid("该任务已提交，不可重复提交")
        b = _get_batch(db, t.batch_id)
        if b.status != _B_OPEN:
            raise _invalid("评教窗口未开放")
        rec = AaEvaluationRecord(tenant_id=_tid(), batch_id=b.id, task_id=t.id, teacher_key=t.teacher_key,
                                 evaluator_type=t.evaluator_type,
                                 answers_json=json.dumps(answers, ensure_ascii=False) if answers else None,
                                 objective_score=objective_score, comment=comment)
        db.add(rec)
        t.submitted_count = (t.submitted_count or 0) + 1
        if t.evaluator_type != "STUDENT":
            t.status = "SUBMITTED"
        db.flush()
        # 学生匿名：审计只记任务核销，不记学生身份
        _audit(db, t.id, "EVAL_SUBMIT", f"{t.evaluator_type} 提交" + ("(匿名)" if t.evaluator_type == "STUDENT" else ""))
        db.commit()
        return {"taskId": str(t.id), "submittedCount": t.submitted_count}


def list_tasks(user, bid, evaluator_type=None):
    from app.models import AaEvaluationTask
    with session() as db:
        _ctx(user, db)
        q = db.query(AaEvaluationTask).filter(AaEvaluationTask.batch_id == bid, AaEvaluationTask.tenant_id == _tid(),
                                              AaEvaluationTask.is_deleted.is_(False))
        if evaluator_type:
            q = q.filter(AaEvaluationTask.evaluator_type == evaluator_type)
        rows = q.order_by(AaEvaluationTask.id).all()
        return [{"taskId": str(t.id), "courseName": t.course_name, "teacherName": t.teacher_name,
                 "evaluatorType": t.evaluator_type, "submittedCount": t.submitted_count, "status": t.status}
                for t in rows]


# ══════════ 结果 / 申诉 ══════════

def list_results(user, bid, mine=False, page=1, page_size=50):
    from app.models import AaEvaluationResult
    with session() as db:
        _ctx(user, db)
        q = db.query(AaEvaluationResult).filter(AaEvaluationResult.batch_id == bid, AaEvaluationResult.tenant_id == _tid())
        if mine:
            keys = _derive_keys(user)
            q = q.filter(AaEvaluationResult.teacher_key.in_(list(keys) or [""]), AaEvaluationResult.published.is_(True))
        rows = q.order_by(AaEvaluationResult.id).all()
        total = len(rows)

        def _f(v):
            return float(v) if v is not None else None
        return [{"resultId": str(r.id), "teacherName": r.teacher_name, "courseName": r.course_name,
                 "studentAvg": _f(r.student_avg), "studentCount": r.student_count,
                 "selfScore": _f(r.self_score), "peerAvg": _f(r.peer_avg), "peerCount": r.peer_count,
                 "supervisorAvg": _f(r.supervisor_avg), "supervisorCount": r.supervisor_count,
                 "compositeScore": _f(r.composite_score),
                 "level": r.level, "published": r.published}
                for r in rows[(page - 1) * page_size: page * page_size]], total


def submit_appeal(user, result_id, reason):
    """教师对结果申诉。修复：此前未校验 result 是否属于当前登录教师本人——任何持
    require_staff 权限者传任意 resultId 即可代任意教师发起申诉，属越权。现补齐：非
    TENANT_ALL（教务处/学校管理员，允许代管）角色必须 result.teacher_key 命中 _derive_keys。"""
    from app.models import AaEvaluationAppeal, AaEvaluationResult
    with session() as db:
        ctx = _ctx(user, db)
        reason = (reason or "").strip()
        if len(reason) < 5:
            raise _bad("申诉理由必填且不少于5字")
        r = db.query(AaEvaluationResult).filter(AaEvaluationResult.id == result_id, AaEvaluationResult.tenant_id == _tid()).first()
        if not r:
            raise not_found("评价结果不存在")
        if ctx.scope_type != "TENANT_ALL":
            if not r.teacher_key or r.teacher_key not in _derive_keys(user):
                raise no_data_scope("仅可对本人的评价结果发起申诉")
        a = AaEvaluationAppeal(tenant_id=_tid(), result_id=result_id, teacher_key=_tkey(), reason=reason,
                               current_node="COLLEGE", status="COLLEGE_REVIEW")
        db.add(a); db.flush()
        _audit(db, a.id, "EVAL_APPEAL_SUBMIT", "申诉")
        db.commit()
        return {"appealId": str(a.id), "status": a.status}


def review_appeal(user, appeal_id, action, reason=""):
    """两级审：COLLEGE_REVIEW → RESOLVED/REJECTED（学院初审+教务终审简化为单动作确认）。"""
    from app.models import AaEvaluationAppeal
    with session() as db:
        _require_school(_ctx(user, db))
        a = db.query(AaEvaluationAppeal).filter(AaEvaluationAppeal.id == appeal_id, AaEvaluationAppeal.tenant_id == _tid()).first()
        if not a:
            raise not_found("申诉不存在")
        if a.status not in ("SUBMITTED", "COLLEGE_REVIEW"):
            raise _invalid("该申诉已处理")
        if action == "RESOLVE":
            a.status = "RESOLVED"
        elif action == "REJECT":
            reason = (reason or "").strip()
            if len(reason) < 5:
                raise _bad("驳回原因必填且不少于5字")
            a.status = "REJECTED"
            a.review_reason = reason
        else:
            raise _bad("非法动作")
        _audit(db, a.id, "EVAL_APPEAL_REVIEW", action)
        db.commit()
        return {"appealId": str(a.id), "status": a.status}


def list_appeals(user, status=None, page=1, page_size=50):
    from app.models import AaEvaluationAppeal
    with session() as db:
        _ctx(user, db)
        q = db.query(AaEvaluationAppeal).filter(AaEvaluationAppeal.tenant_id == _tid(),
                                                AaEvaluationAppeal.is_deleted.is_(False))
        if status:
            q = q.filter(AaEvaluationAppeal.status == status)
        rows = q.order_by(AaEvaluationAppeal.id.desc()).all()
        total = len(rows)
        return [{"appealId": str(a.id), "resultId": str(a.result_id), "teacherKey": a.teacher_key,
                 "reason": a.reason, "status": a.status} for a in rows[(page - 1) * page_size: page * page_size]], total


def stats(user, bid):
    """评价统计：结果分级分布 + 按评价类型(STUDENT/SELF/PEER/SUPERVISOR)的参评率（Tier1 R2 新增participation）。"""
    from app.models import AaEvaluationResult, AaEvaluationTask
    with session() as db:
        _ctx(user, db)
        rows = db.query(AaEvaluationResult).filter(AaEvaluationResult.batch_id == bid, AaEvaluationResult.tenant_id == _tid()).all()
        by_level = {}
        for r in rows:
            by_level[r.level or "N/A"] = by_level.get(r.level or "N/A", 0) + 1
        avgs = [float(r.student_avg) for r in rows if r.student_avg is not None]
        tasks = db.query(AaEvaluationTask).filter(AaEvaluationTask.batch_id == bid, AaEvaluationTask.tenant_id == _tid(),
                                                  AaEvaluationTask.is_deleted.is_(False)).all()
        by_type = {}
        for t in tasks:
            d = by_type.setdefault(t.evaluator_type, {"total": 0, "submitted": 0})
            d["total"] += 1
            submitted = t.status == "SUBMITTED" or (t.evaluator_type == "STUDENT" and (t.submitted_count or 0) > 0)
            if submitted:
                d["submitted"] += 1
        participation = {k: {"total": v["total"], "submitted": v["submitted"],
                             "rate": round(v["submitted"] / v["total"] * 100, 1) if v["total"] else 0.0}
                         for k, v in by_type.items()}
        return {"batchId": str(bid), "resultCount": len(rows),
                "overallAvg": round(sum(avgs) / len(avgs), 2) if avgs else None, "byLevel": by_level,
                "participation": participation}


def export_evaluation_xlsx(user, bid, domain, purpose):
    """导出评价结果/参评统计 xlsx（水印+审计；复用 xlsx_util，同 教学质量/教务统计 既有导出模式）。

    domain=results：评价结果分级清单；domain=stats：按评价类型的参评率统计（供"评价统计""评价归档"两个
    三级模块共用同一导出能力，符合二级总包 §12"Excel导出需要"的红线要求）。
    """
    purpose = (purpose or "").strip()
    if len(purpose) < 5:
        raise _bad("导出用途必填（≥5字）")
    from app.services.xlsx_util import build_ledger_xlsx
    with session() as db:
        _ctx(user, db)
        b = _get_batch(db, bid)
        batch_name = b.batch_name
    ctx = get_current_user_ctx() or {}
    watermark = (f"导出人：{ctx.get('realName') or ctx.get('loginName') or '-'}  "
                f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose}")
    if domain == "stats":
        s = stats(user, bid)
        headers = ["评价类型", "应评数", "已评数", "参评率(%)"]
        rows = [[k, v["total"], v["submitted"], v["rate"]] for k, v in (s.get("participation") or {}).items()]
        content = build_ledger_xlsx(f"{batch_name}-参评统计", headers, rows, watermark=watermark)
    elif domain == "results":
        items, _total = list_results(user, bid, mine=False, page=1, page_size=10000)
        headers = ["教师", "课程", "均分", "评价数", "等级", "已发布"]
        rows = [[i["teacherName"], i["courseName"], i["studentAvg"], i["studentCount"], i["level"],
                "是" if i["published"] else "否"] for i in items]
        content = build_ledger_xlsx(f"{batch_name}-评价结果", headers, rows, watermark=watermark)
    else:
        raise _bad("非法导出域，仅支持 results/stats")
    with session() as db:
        _audit(db, bid, "EVAL_EXPORT", f"{domain} 用途={purpose[:100]}")
        db.commit()
    return content
