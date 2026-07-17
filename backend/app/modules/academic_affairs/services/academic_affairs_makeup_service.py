"""13B 补考重修缓考免修 service（SM-12，四条线）。

补考(批次5态)：成绩发布后不及格名单 → 建批次 → 学生报名 → 发布 → 录入成绩 → FINISHED 按计分规则回写。
重修(申请6态,单节点)：可重修课程 → 报名(次数上限校验) → 教务处审批 → 编入跟班。
免修(申请7态,三级审批)：申请(已获成绩422+每学期上限) → 任课教师→学院→教务处。
缓考合流：只读读取考务包 AaDeferredExam(APPROVED) → 并入下一补考批次(写 t_acad_makeup.batch_id)。

计分规则 academicAffairs.makeup.scoreRule=CAP60；重修上限 academicAffairs.retake.maxCount=2；
免修每学期上限 academicAffairs.exemption.maxCount=2（读规则中心，缺省显式默认值）。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import func

from app.core.affairs_security import _derive_keys, build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

_MB_DRAFT, _MB_ARRANGED, _MB_PUBLISHED = "DRAFT", "ARRANGED", "PUBLISHED"
_MB_SCORING, _MB_REVIEWED, _MB_FINISHED = "SCORING", "REVIEWED", "FINISHED"
_RT_SUBMITTED, _RT_REVIEW, _RT_APPROVED = "SUBMITTED", "ACADEMIC_REVIEW", "APPROVED"
_RT_REJECTED, _RT_ENROLLED, _RT_FINISHED = "REJECTED", "ENROLLED", "FINISHED"
_EX_SUBMITTED, _EX_TEACHER, _EX_COLLEGE = "SUBMITTED", "TEACHER_REVIEW", "COLLEGE_REVIEW"
_EX_ACADEMIC, _EX_APPROVED, _EX_REJECTED, _EX_CANCELLED = "ACADEMIC_REVIEW", "APPROVED", "REJECTED", "CANCELLED"
_EX_CHAIN = {_EX_SUBMITTED: _EX_TEACHER, _EX_TEACHER: _EX_COLLEGE, _EX_COLLEGE: _EX_ACADEMIC, _EX_ACADEMIC: _EX_APPROVED}


def _conflict(m):
    return AppException("DATA_CONFLICT", m, http_status=409)


def _invalid(m):
    return AppException("DATA_CONFLICT", m, http_status=409)


def _bad(m):
    return AppException("VALIDATION_ERROR", m)


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


def _rule(key, default):
    from app.services.platform_service import get_config_json
    cfg = get_config_json(_tid(), "ACAD_RULE", key)
    if cfg is not None:
        if isinstance(cfg, dict) and "value" in cfg:
            return cfg["value"]
        if not isinstance(cfg, dict):
            return cfg
    return default


def _ctx(user, db):
    return build_affairs_context(user, db)


def _require_school(ctx):
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可执行该操作")


def _student(db):
    from app.models import StudentProfile
    ctx = get_current_user_ctx() or {}
    return db.query(StudentProfile).filter(StudentProfile.tenant_id == _tid(),
                                           StudentProfile.student_no == ctx.get("studentNo")).first()


# ══════════ 补考 ══════════

def _mb_dto(b):
    return {"batchId": str(b.id), "batchName": b.batch_name, "termCode": b.term_code,
            "kind": getattr(b, "kind", "MAKEUP") or "MAKEUP",
            "targetGrades": [x for x in (b.target_grades or "").split(",") if x] if getattr(b, "target_grades", None) else [],
            "examBatchRef": str(b.exam_batch_ref) if b.exam_batch_ref else None,
            "scoreRule": b.score_rule, "status": b.status, "publishedAt": _iso(b.published_at)}


def _get_mb(db, bid):
    from app.models import AaMakeupBatch
    b = db.query(AaMakeupBatch).filter(AaMakeupBatch.id == bid, AaMakeupBatch.tenant_id == _tid(),
                                       AaMakeupBatch.is_deleted.is_(False)).first()
    if not b:
        raise not_found("补考批次不存在")
    return b


def makeup_pending(user, term=None, page=1, page_size=50):
    """成绩发布后不及格学生名单（补考候选，读 t_acad_grade FAILED）。"""
    from app.models import AcademicGrade, AcademicStudent
    with session() as db:
        _ctx(user, db)
        q = db.query(AcademicGrade, AcademicStudent).join(
            AcademicStudent, AcademicGrade.acad_student_id == AcademicStudent.id).filter(
            AcademicGrade.tenant_id == _tid(), AcademicGrade.pass_status.in_(["FAIL", "FAILED"]),
            AcademicGrade.record_status == "ACTIVE")
        rows = q.all()
        items = [{"gradeId": str(g.id), "acadStudentId": str(g.acad_student_id),
                  "studentNo": s.student_no, "studentName": s.name, "courseName": g.course_name,
                  "score": g.score, "className": s.class_name} for g, s in rows]
        total = len(items)
        return items[(page - 1) * page_size: page * page_size], total


def create_makeup_batch(user, body):
    from app.models import AaMakeupBatch
    with session() as db:
        _require_school(_ctx(user, db))
        name = (getattr(body, "batchName", None) or "").strip()
        if not name:
            raise _bad("批次名称必填")
        b = AaMakeupBatch(tenant_id=_tid(), batch_name=name, term_code=getattr(body, "termCode", None),
                          exam_batch_ref=int(body.examBatchRef) if getattr(body, "examBatchRef", None) else None,
                          score_rule=_rule("makeup_score_rule", "CAP60"), status=_MB_DRAFT)
        db.add(b); db.flush()
        _audit(db, "AA_MAKEUP", b.id, "MAKEUP_BATCH_CREATE", name)
        db.commit()
        return _mb_dto(b)


def list_makeup_batches(user, status=None, page=1, page_size=20, kind=None):
    from app.models import AaMakeupBatch
    with session() as db:
        _ctx(user, db)
        q = db.query(AaMakeupBatch).filter(AaMakeupBatch.tenant_id == _tid(), AaMakeupBatch.is_deleted.is_(False))
        if status:
            q = q.filter(AaMakeupBatch.status == status)
        if kind:
            q = q.filter(AaMakeupBatch.kind == kind)
        rows = q.order_by(AaMakeupBatch.id.desc()).all()
        return [_mb_dto(b) for b in rows[(page - 1) * page_size: page * page_size]], len(rows)


def link_exam_batch(user, batch_id, exam_batch_id):
    """补考批次挂考务批次编排（施工卡：exam_batch_ref 关联，考场/监考走考务包）。校验考务批次存在。"""
    from app.models import AaExamBatch
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_mb(db, batch_id)
        if b.status not in (_MB_DRAFT, _MB_ARRANGED):
            raise _invalid("仅 DRAFT/ARRANGED 补考批次可挂考务编排")
        eb = db.query(AaExamBatch).filter(AaExamBatch.id == int(exam_batch_id), AaExamBatch.tenant_id == _tid(),
                                          AaExamBatch.is_deleted.is_(False)).first()
        if not eb:
            raise not_found("考务批次不存在")
        b.exam_batch_ref = eb.id
        if b.status == _MB_DRAFT:
            b.status = _MB_ARRANGED
        _audit(db, "AA_MAKEUP", b.id, "MAKEUP_LINK_EXAM", f"挂考务批次 {eb.batch_name}")
        db.commit()
        return _mb_dto(b)


def enroll_makeup(user, batch_id, acad_student_id, course_name, origin_score=None):
    """将不及格学生纳入补考批次名单（t_acad_makeup + batch_id）。教务处操作。"""
    from app.models import AcademicMakeup
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_mb(db, batch_id)
        if b.status not in (_MB_DRAFT, _MB_ARRANGED):
            raise _invalid("仅 DRAFT/ARRANGED 批次可纳入名单")
        dup = db.query(AcademicMakeup).filter(AcademicMakeup.tenant_id == _tid(),
                                              AcademicMakeup.batch_id == b.id,
                                              AcademicMakeup.acad_student_id == int(acad_student_id),
                                              AcademicMakeup.course_name == course_name).first()
        if dup:
            return {"makeupId": str(dup.id), "status": dup.status}
        m = AcademicMakeup(tenant_id=_tid(), acad_student_id=int(acad_student_id), course_name=course_name,
                           origin_score=origin_score, batch_id=b.id, kind=(b.kind or "MAKEUP"),
                           status="PENDING_EXAM", record_status="ACTIVE")
        db.add(m); db.flush()
        b.status = _MB_ARRANGED
        _audit(db, "AA_MAKEUP", b.id, "MAKEUP_ENROLL", f"纳入 {course_name}")
        db.commit()
        return {"makeupId": str(m.id), "status": m.status}


def publish_makeup_batch(user, batch_id):
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_mb(db, batch_id)
        if b.status != _MB_ARRANGED:
            raise _invalid("仅 ARRANGED 批次可发布")
        b.status = _MB_PUBLISHED
        b.published_at = datetime.utcnow()
        _audit(db, "AA_MAKEUP", b.id, "MAKEUP_BATCH_PUBLISH", "发布")
        db.commit()
        return _mb_dto(b)


def enter_makeup_score(user, makeup_id, score):
    """录入补考成绩（批次 PUBLISHED→SCORING）。"""
    from app.models import AcademicMakeup
    with session() as db:
        _require_school(_ctx(user, db))
        m = db.query(AcademicMakeup).filter(AcademicMakeup.id == makeup_id, AcademicMakeup.tenant_id == _tid()).first()
        if not m:
            raise not_found("补考记录不存在")
        b = _get_mb(db, m.batch_id)
        if b.status not in (_MB_PUBLISHED, _MB_SCORING):
            raise _invalid("批次未发布，不可录入")
        m.final_score = int(score)
        m.status = "SCORED"
        if b.status == _MB_PUBLISHED:
            b.status = _MB_SCORING
        _audit(db, "AA_MAKEUP", m.id, "MAKEUP_SCORE", f"补考成绩 {score}")
        db.commit()
        return {"makeupId": str(m.id), "finalScore": m.final_score, "status": m.status}


def college_review_scores(user, batch_id):
    """补考成绩录入接 R1 同构审核链（施工卡 D-09）：录入(SCORING)→学院审(REVIEWED)→教务发布回写(FINISHED)。
    学院审：所有补考记录须已 SCORED；SCORING→REVIEWED。"""
    from app.models import AcademicMakeup
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_mb(db, batch_id)
        if b.status != _MB_SCORING:
            raise _invalid("仅 SCORING 批次可学院审核")
        pend = db.query(AcademicMakeup).filter(AcademicMakeup.batch_id == b.id, AcademicMakeup.tenant_id == _tid(),
                                               AcademicMakeup.status != "SCORED", AcademicMakeup.batch_id.isnot(None)).count()
        if pend:
            raise _invalid(f"尚有 {pend} 条补考成绩未录入，不可提交学院审核")
        b.status = _MB_REVIEWED
        _audit(db, "AA_MAKEUP", b.id, "MAKEUP_COLLEGE_REVIEW", "补考成绩学院审核通过")
        db.commit()
        return _mb_dto(b)


def finish_makeup_batch(user, batch_id):
    """REVIEWED→FINISHED（教务发布）：按计分规则回写 t_acad_grade(source=MAKEUP)（幂等）。接 R1 三级审核链末端。"""
    from app.models import AcademicGrade, AcademicMakeup
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_mb(db, batch_id)
        if b.status == _MB_FINISHED:
            return _mb_dto(b)
        if b.status != _MB_REVIEWED:
            raise _invalid("仅学院审核通过(REVIEWED)的批次可教务发布回写")
        recs = db.query(AcademicMakeup).filter(AcademicMakeup.batch_id == b.id, AcademicMakeup.tenant_id == _tid(),
                                               AcademicMakeup.status == "SCORED").all()
        cap = 60 if b.score_rule == "CAP60" else 100
        src = "CLEARANCE" if (getattr(b, "kind", None) == "CLEARANCE") else "MAKEUP"
        affected = set()
        for m in recs:
            fs = m.final_score or 0
            passed = fs >= 60
            recorded = min(fs, cap) if passed else fs
            # 学分从原修成绩行带出：补考/清考针对的就是原挂科课程，原行(PUBLISH等)已带真实学分。
            # 不带则回写行 credit_value=0，通过后学分被吞成 0，毕业学分核算失真(修 P0-1)。
            credit = db.query(func.max(AcademicGrade.credit_value)).filter(
                AcademicGrade.tenant_id == _tid(),
                AcademicGrade.acad_student_id == m.acad_student_id,
                AcademicGrade.course_name == m.course_name,
                AcademicGrade.credit_value.isnot(None)).scalar() or 0
            # 回写一条成绩行（幂等：同 acad_student+course+source 更新；补考/清考各自独立 source）
            g = db.query(AcademicGrade).filter(AcademicGrade.tenant_id == _tid(),
                                               AcademicGrade.acad_student_id == m.acad_student_id,
                                               AcademicGrade.course_name == m.course_name,
                                               AcademicGrade.source == src).first()
            if g:
                g.score = recorded
                g.pass_status = "PASSED" if passed else "FAILED"
                if credit and not (g.credit_value or 0):
                    g.credit_value = credit
            else:
                db.add(AcademicGrade(tenant_id=_tid(), acad_student_id=m.acad_student_id, course_name=m.course_name,
                                     credit_value=credit,
                                     score=recorded, pass_status="PASSED" if passed else "FAILED",
                                     source=src, record_status="ACTIVE"))
            affected.add(int(m.acad_student_id))
        db.flush()
        # 回写后刷新学生学业台账(GPA/已得学分/未通过门数)，否则预警/毕业/分流读旧数据(修 P0-2)。
        from app.models import AcademicStudent
        from app.modules.academic_affairs.services.academic_affairs_grade_service import _refresh_aggregates
        for aid in affected:
            a = db.get(AcademicStudent, aid)
            if a and not a.is_deleted:
                _refresh_aggregates(db, a)
        b.status = _MB_FINISHED
        _audit(db, "AA_MAKEUP", b.id, "MAKEUP_BATCH_FINISH",
               f"回写 {len(recs)} 条{'清考' if src == 'CLEARANCE' else '补考'}成绩，刷新 {len(affected)} 生台账")
        db.commit()
        return _mb_dto(b)


# ══════════ 毕业清考（对标商业教务 6-6：应届生未通过课程的最后一次考核机会）══════════

def create_clearance_batch(user, body):
    """建毕业清考批次：kind=CLEARANCE + 限定年级；计分固定 CAP60（清考通过按60记，不给高分投机）。"""
    from app.models import AaMakeupBatch
    with session() as db:
        _require_school(_ctx(user, db))
        name = (getattr(body, "batchName", None) or "").strip()
        if not name:
            raise _bad("批次名称必填")
        grades = [str(x).strip() for x in (getattr(body, "targetGrades", None) or []) if str(x).strip()]
        if not grades:
            raise _bad("清考必须限定毕业年级（如 2022）")
        b = AaMakeupBatch(tenant_id=_tid(), batch_name=name, kind="CLEARANCE",
                          target_grades=",".join(grades), term_code=getattr(body, "termCode", None),
                          score_rule="CAP60", status=_MB_DRAFT)
        db.add(b); db.flush()
        _audit(db, "AA_MAKEUP", b.id, "CLEARANCE_BATCH_CREATE", f"{name} 年级{grades}")
        db.commit()
        return _mb_dto(b)


def _clearance_candidates(db, grades):
    """自动圈定：限定年级在读学生中，同课程按最高分去重后仍 FAILED 的课程。

    口径与学生台账汇总(_refresh_aggregates)一致：重修/补考已通过的课程不再进清考，
    只捞"到今天为止最好成绩仍不及格"的课程——这是清考的法定对象。
    """
    from app.models import AcademicGrade, AcademicStudent, StudentProfile
    profiles = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _tid(), StudentProfile.grade.in_(grades),
        StudentProfile.student_status == "NORMAL", StudentProfile.is_deleted.is_(False)).all()
    pid_map = {p.id: p for p in profiles}
    if not pid_map:
        return []
    acads = db.query(AcademicStudent).filter(
        AcademicStudent.tenant_id == _tid(),
        AcademicStudent.student_id.in_(list(pid_map))).all()
    out = []
    for a in acads:
        rows = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == a.id,
            AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False)).all()
        best = {}
        for g in rows:
            key = (g.course_name or "").strip()
            if not key:
                continue
            cur = best.get(key)
            if cur is None or (g.score or -1) > (cur.score or -1):
                best[key] = g
        p = pid_map.get(a.student_id)
        for course, g in best.items():
            if g.pass_status == "FAILED":
                out.append({"acadStudentId": str(a.id), "studentNo": a.student_no,
                            "studentName": a.name, "grade": (p.grade if p else None),
                            "courseName": course, "bestScore": g.score})
    return out


def clearance_scan(user, batch_id, dry_run=False):
    """扫描并圈定清考名单（幂等；dry_run 只看不落）。"""
    from app.models import AcademicMakeup
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_mb(db, batch_id)
        if (getattr(b, "kind", None) or "MAKEUP") != "CLEARANCE":
            raise _invalid("仅清考批次可执行名单扫描")
        if b.status not in (_MB_DRAFT, _MB_ARRANGED):
            raise _invalid("仅 DRAFT/ARRANGED 批次可圈定名单")
        grades = [x for x in (b.target_grades or "").split(",") if x]
        cands = _clearance_candidates(db, grades)
        added, skipped = 0, 0
        if not dry_run:
            for c in cands:
                dup = db.query(AcademicMakeup).filter(
                    AcademicMakeup.tenant_id == _tid(), AcademicMakeup.batch_id == b.id,
                    AcademicMakeup.acad_student_id == int(c["acadStudentId"]),
                    AcademicMakeup.course_name == c["courseName"]).first()
                if dup:
                    skipped += 1
                    continue
                db.add(AcademicMakeup(tenant_id=_tid(), acad_student_id=int(c["acadStudentId"]),
                                      course_name=c["courseName"], origin_score=c["bestScore"],
                                      batch_id=b.id, kind="CLEARANCE",
                                      status="PENDING_EXAM", record_status="ACTIVE"))
                added += 1
            if added and b.status == _MB_DRAFT:
                b.status = _MB_ARRANGED
            _audit(db, "AA_MAKEUP", b.id, "CLEARANCE_SCAN", f"圈定{added}条(跳过{skipped})")
            db.commit()
        return {"batchId": str(b.id), "dryRun": dry_run, "candidates": len(cands),
                "added": (0 if dry_run else added), "skipped": (0 if dry_run else skipped),
                "items": cands}


def clearance_records(user, batch_id, page=1, page_size=100):
    """清考批次名单（含成绩录入状态）。收敛 TENANT_ALL,防越范围读全校清考不及格明细(修数据范围红线)。"""
    from app.models import AcademicMakeup, AcademicStudent
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_mb(db, batch_id)
        rows = db.query(AcademicMakeup, AcademicStudent).join(
            AcademicStudent, AcademicMakeup.acad_student_id == AcademicStudent.id).filter(
            AcademicMakeup.tenant_id == _tid(), AcademicMakeup.batch_id == b.id,
            AcademicMakeup.is_deleted.is_(False)).order_by(AcademicMakeup.id).all()
        items = [{"makeupId": str(m.id), "acadStudentId": str(m.acad_student_id),
                  "studentNo": s.student_no, "studentName": s.name,
                  "courseName": m.course_name, "originScore": m.origin_score,
                  "finalScore": m.final_score, "status": m.status} for m, s in rows]
        return items[(page - 1) * page_size: page * page_size], len(items)


# ══════════ 重修 ══════════

def _rt_dto(r):
    return {"applyId": str(r.id), "studentId": str(r.student_id), "studentName": r.student_name,
            "courseName": r.course_name, "termCode": r.term_code, "reason": r.reason,
            "retakeCount": r.retake_count, "reviewReason": r.review_reason, "status": r.status}


def retake_apply(user, body):
    """学生重修报名：次数上限校验（默2），同课程同学期在途唯一。"""
    from app.models import AaRetakeApply
    with session() as db:
        s = _student(db)
        if not s:
            raise not_found("学生档案不存在")
        course_name = (getattr(body, "courseName", None) or "").strip()
        term = getattr(body, "termCode", None)
        if not course_name:
            raise _bad("课程名必填")
        max_count = int(_rule("retake_max_count", 2))
        done = db.query(AaRetakeApply).filter(AaRetakeApply.tenant_id == _tid(),
                                              AaRetakeApply.student_id == s.id,
                                              AaRetakeApply.course_name == course_name,
                                              AaRetakeApply.status.notin_([_RT_REJECTED]),
                                              AaRetakeApply.is_deleted.is_(False)).all()
        active = [r for r in done if r.status in (_RT_SUBMITTED, _RT_REVIEW)]
        if active:
            raise _conflict("该课程本学期已有在途重修申请")
        if len(done) >= max_count:
            raise _bad(f"该课程重修次数已达上限 {max_count} 次")
        r = AaRetakeApply(tenant_id=_tid(), student_id=s.id, student_no=s.student_no, student_name=s.real_name,
                          course_name=course_name, term_code=term, reason=getattr(body, "reason", None),
                          retake_count=len(done) + 1, status=_RT_SUBMITTED)
        db.add(r); db.flush()
        _audit(db, "AA_RETAKE", r.id, "RETAKE_APPLY", f"重修报名 {course_name}")
        db.commit()
        return _rt_dto(r)


def retake_review(user, apply_id, action, reason=""):
    """教务处单节点审批（SUBMITTED→APPROVED/REJECTED）。APPROVED 编入跟班（ENROLLED）。"""
    from app.models import AaRetakeApply
    with session() as db:
        _require_school(_ctx(user, db))
        r = db.query(AaRetakeApply).filter(AaRetakeApply.id == apply_id, AaRetakeApply.tenant_id == _tid()).first()
        if not r:
            raise not_found("重修申请不存在")
        if r.status not in (_RT_SUBMITTED, _RT_REVIEW):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请已处理", http_status=409)
        if action == "APPROVE":
            r.status = _RT_APPROVED
        elif action == "REJECT":
            reason = (reason or "").strip()
            if len(reason) < 5:
                raise _bad("驳回原因必填且不少于5字")
            r.status = _RT_REJECTED
            r.review_reason = reason
        else:
            raise _bad("非法审批动作")
        _audit(db, "AA_RETAKE", r.id, "RETAKE_REVIEW", f"{action}")
        db.commit()
        return _rt_dto(r)


def retake_enroll(user, apply_id, teaching_task_ref=None):
    """APPROVED→ENROLLED：编入教学任务跟班。"""
    from app.models import AaRetakeApply
    with session() as db:
        _require_school(_ctx(user, db))
        r = db.query(AaRetakeApply).filter(AaRetakeApply.id == apply_id, AaRetakeApply.tenant_id == _tid()).first()
        if not r:
            raise not_found("重修申请不存在")
        if r.status != _RT_APPROVED:
            raise _invalid("仅 APPROVED 申请可编入跟班")
        r.status = _RT_ENROLLED
        r.teaching_task_ref = int(teaching_task_ref) if teaching_task_ref else None
        _audit(db, "AA_RETAKE", r.id, "RETAKE_ENROLL", "编入跟班")
        db.commit()
        return _rt_dto(r)


def retake_list(user, status=None, student_only=False, page=1, page_size=50):
    from app.models import AaRetakeApply
    ctx = get_current_user_ctx() or {}
    with session() as db:
        _ctx(user, db)
        q = db.query(AaRetakeApply).filter(AaRetakeApply.tenant_id == _tid(), AaRetakeApply.is_deleted.is_(False))
        if student_only:
            q = q.filter(AaRetakeApply.student_no == ctx.get("studentNo"))
        if status:
            q = q.filter(AaRetakeApply.status == status)
        rows = q.order_by(AaRetakeApply.id.desc()).all()
        return [_rt_dto(r) for r in rows[(page - 1) * page_size: page * page_size]], len(rows)


# ══════════ 免修（三级审批） ══════════

def _ex_dto(e):
    return {"exemptionId": str(e.id), "studentId": str(e.student_id), "studentName": e.student_name,
            "courseName": e.course_name, "termCode": e.term_code, "reason": e.reason,
            "currentNode": e.current_node, "returnReason": e.return_reason, "status": e.status}


def exemption_apply(user, body):
    """学生免修申请：已获成绩课程 422；每学期免修上限（默2）。"""
    from app.models import AaExemption, AcademicGrade, AcademicStudent
    with session() as db:
        s = _student(db)
        if not s:
            raise not_found("学生档案不存在")
        course_name = (getattr(body, "courseName", None) or "").strip()
        term = getattr(body, "termCode", None)
        if not course_name:
            raise _bad("课程名必填")
        # 已获成绩课程不可免修
        acad = db.query(AcademicStudent).filter(AcademicStudent.tenant_id == _tid(),
                                                AcademicStudent.student_id == s.id).first()
        if acad:
            passed = db.query(AcademicGrade).filter(AcademicGrade.tenant_id == _tid(),
                                                    AcademicGrade.acad_student_id == acad.id,
                                                    AcademicGrade.course_name == course_name,
                                                    AcademicGrade.pass_status == "PASSED").first()
            if passed:
                raise _bad("该课程已获及格成绩，不可申请免修")
        max_count = int(_rule("exemption_max_count", 2))
        term_applies = db.query(AaExemption).filter(AaExemption.tenant_id == _tid(),
                                                    AaExemption.student_id == s.id,
                                                    AaExemption.term_code == term,
                                                    AaExemption.status.notin_([_EX_REJECTED, _EX_CANCELLED]),
                                                    AaExemption.is_deleted.is_(False)).count()
        if term and term_applies >= max_count:
            raise _bad(f"本学期免修申请已达上限 {max_count} 门")
        # 免修材料附件接 t_file_object：校验传入的 file_id 均为本租户真实文件对象
        material_ids = getattr(body, "materialFileIds", None)
        if material_ids:
            from app.models import FileObject
            ids = material_ids if isinstance(material_ids, list) else [material_ids]
            int_ids = [int(x) for x in ids if str(x).isdigit()]
            if int_ids:
                found = db.query(FileObject).filter(FileObject.tenant_id == _tid(),
                                                    FileObject.id.in_(int_ids)).count()
                if found != len(int_ids):
                    raise _bad("免修材料附件包含无效文件，请重新上传")
            material_ids = json.dumps([str(x) for x in ids], ensure_ascii=False)
        e = AaExemption(tenant_id=_tid(), student_id=s.id, student_no=s.student_no, student_name=s.real_name,
                        course_name=course_name, term_code=term, college_id=getattr(s, "college_id", None),
                        reason=getattr(body, "reason", None), material_file_ids=material_ids,
                        current_node="TEACHER", status=_EX_TEACHER)
        db.add(e); db.flush()
        _audit(db, "AA_EXEMPTION", e.id, "EXEMPTION_APPLY", f"免修申请 {course_name}")
        db.commit()
        return _ex_dto(e)


def exemption_review(user, exemption_id, action, reason=""):
    """三级审批任一节点：APPROVE 推进/终 APPROVED；RETURN 退回；REJECT 驳回。"""
    from app.models import AaExemption
    with session() as db:
        _ctx(user, db)
        e = db.query(AaExemption).filter(AaExemption.id == exemption_id, AaExemption.tenant_id == _tid()).first()
        if not e:
            raise not_found("免修申请不存在")
        if e.status not in _EX_CHAIN:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请已处理", http_status=409)
        if action == "APPROVE":
            e.status = _EX_CHAIN[e.status]
            e.current_node = e.status
        elif action == "RETURN":
            reason = (reason or "").strip()
            if len(reason) < 5:
                raise _bad("退回原因必填且不少于5字")
            e.status = _EX_SUBMITTED
            e.return_reason = reason
        elif action == "REJECT":
            e.status = _EX_REJECTED
            e.return_reason = (reason or "").strip()
        else:
            raise _bad("非法审批动作")
        _audit(db, "AA_EXEMPTION", e.id, "EXEMPTION_REVIEW", f"{action}->{e.status}")
        db.commit()
        return _ex_dto(e)


def exemption_list(user, status=None, student_only=False, page=1, page_size=50):
    from app.models import AaExemption
    ctx = get_current_user_ctx() or {}
    with session() as db:
        _ctx(user, db)
        q = db.query(AaExemption).filter(AaExemption.tenant_id == _tid(), AaExemption.is_deleted.is_(False))
        if student_only:
            q = q.filter(AaExemption.student_no == ctx.get("studentNo"))
        if status:
            q = q.filter(AaExemption.status == status)
        rows = q.order_by(AaExemption.id.desc()).all()
        return [_ex_dto(e) for e in rows[(page - 1) * page_size: page * page_size]], len(rows)


# ══════════ 缓考合流（只读 + 并入补考批次） ══════════

def deferred_pool(user, page=1, page_size=50):
    """缓考 APPROVED 学生池（读考务包 AaDeferredExam），供并入下一补考批次。"""
    from app.models import AaDeferredExam
    with session() as db:
        _ctx(user, db)
        rows = db.query(AaDeferredExam).filter(AaDeferredExam.tenant_id == _tid(),
                                               AaDeferredExam.status == "APPROVED",
                                               AaDeferredExam.is_deleted.is_(False)).order_by(AaDeferredExam.id.desc()).all()
        items = [{"deferId": str(d.id), "studentId": str(d.student_id), "studentName": d.student_name,
                  "examCourseId": str(d.exam_course_id), "courseName": d.course_name,
                  "nextBatchRef": d.next_batch_ref} for d in rows]
        return items[(page - 1) * page_size: page * page_size], len(items)


def merge_deferred(user, defer_id, batch_id):
    """把缓考 APPROVED 学生并入补考批次（写 t_acad_makeup.batch_id，标记 next_batch_ref）。"""
    from app.models import AaDeferredExam, AcademicMakeup, AcademicStudent
    with session() as db:
        _require_school(_ctx(user, db))
        d = db.query(AaDeferredExam).filter(AaDeferredExam.id == defer_id, AaDeferredExam.tenant_id == _tid()).first()
        if not d:
            raise not_found("缓考记录不存在")
        if d.status != "APPROVED":
            raise _invalid("仅 APPROVED 缓考可并入补考批次")
        b = _get_mb(db, batch_id)
        acad = db.query(AcademicStudent).filter(AcademicStudent.tenant_id == _tid(),
                                                AcademicStudent.student_id == d.student_id).first()
        m = AcademicMakeup(tenant_id=_tid(), acad_student_id=acad.id if acad else d.student_id,
                           course_name=d.course_name or "缓考课程", batch_id=b.id,
                           status="PENDING_EXAM", record_status="ACTIVE")
        db.add(m)
        d.next_batch_ref = str(b.id)
        if b.status == _MB_DRAFT:
            b.status = _MB_ARRANGED
        _audit(db, "AA_MAKEUP", b.id, "DEFERRED_MERGE", f"缓考 {d.student_name} 并入补考批次")
        db.commit()
        return {"deferId": str(d.id), "batchId": str(b.id), "merged": True}


# ══════════ 统计分析（三级施工卡 10-统计分析 §7）══════════

def _scope_college_ids(ctx, college_id=None):
    """返回本次查询应过滤的学院 id 集合；None=不限（全租户角色未传学院）。传学院越权则拒绝。"""
    if college_id:
        cid = int(college_id)
        if ctx.scope_type == "COLLEGE" and cid not in ctx.college_ids:
            raise no_data_scope("该学院不在您的数据范围内")
        return {cid}
    if ctx.scope_type == "COLLEGE":
        return set(ctx.college_ids) if ctx.college_ids else set()
    return None


def _profile_ids_by_college(db, college_ids):
    """college_ids=None→不限(None)；空集→fail-closed(空集)；否则按 StudentProfile.college_id 过滤。"""
    if college_ids is None:
        return None
    from app.models import StudentProfile
    if not college_ids:
        return set()
    rows = db.query(StudentProfile.id).filter(StudentProfile.tenant_id == _tid(),
                                               StudentProfile.college_id.in_(college_ids)).all()
    return {r[0] for r in rows}


def _acad_ids_by_profile(db, profile_ids):
    """StudentProfile.id 集合 → AcademicStudent(t_acad_student).id 集合；None 透传（不限）。"""
    if profile_ids is None:
        return None
    from app.models import AcademicStudent
    if not profile_ids:
        return set()
    rows = db.query(AcademicStudent.id).filter(AcademicStudent.tenant_id == _tid(),
                                                AcademicStudent.student_id.in_(profile_ids)).all()
    return {r[0] for r in rows}


def _line_stat(rows, is_pass):
    """{count, passRate}：passRate 分母=已有终态判定结果的行数（None=未终态/不计入分母）。"""
    judged = [is_pass(r) for r in rows]
    scored = [j for j in judged if j is not None]
    passed = len([j for j in scored if j])
    rate = round(passed / len(scored), 4) if scored else None
    return {"count": len(rows), "passRate": rate}


def _group_by(rows, keyfn):
    counts: dict = {}
    for r in rows:
        k = keyfn(r)
        k = str(k) if k not in (None, "") else "未知"
        counts[k] = counts.get(k, 0) + 1
    return [{"key": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]


def aggregate_stats(user, term=None, college_id=None, dimension=None):
    """四条线统计聚合：补考/重修/免修/缓考各自人数(批次数)+通过率；dimension=course/term/college 时
    附加下钻分组（V1：不新建统计表，实时聚合既有四表，见二级总包 §8 性能提示）。"""
    from app.models import AaDeferredExam, AaExemption, AaMakeupBatch, AaRetakeApply, AcademicMakeup
    with session() as db:
        ctx = _ctx(user, db)
        college_ids = _scope_college_ids(ctx, college_id)
        profile_ids = _profile_ids_by_college(db, college_ids)
        acad_ids = _acad_ids_by_profile(db, profile_ids)

        batch_term = dict(db.query(AaMakeupBatch.id, AaMakeupBatch.term_code)
                          .filter(AaMakeupBatch.tenant_id == _tid()).all())

        # 补考：t_acad_makeup（batch_id 非空=四条线口径），学期按批次 term_code 过滤
        mq = db.query(AcademicMakeup).filter(AcademicMakeup.tenant_id == _tid(),
                                             AcademicMakeup.batch_id.isnot(None))
        if acad_ids is not None:
            mq = mq.filter(AcademicMakeup.acad_student_id.in_(acad_ids or [-1]))
        if term:
            bids = [bid for bid, tc in batch_term.items() if tc == term]
            mq = mq.filter(AcademicMakeup.batch_id.in_(bids or [-1]))
        makeup_rows = mq.all()
        makeup_stat = _line_stat(makeup_rows, lambda m: (m.final_score >= 60) if m.final_score is not None else None)

        # 重修：t_aa_retake_apply（APPROVED/ENROLLED/FINISHED=通过，REJECTED=不通过，在途不计分母）
        rq = db.query(AaRetakeApply).filter(AaRetakeApply.tenant_id == _tid(), AaRetakeApply.is_deleted.is_(False))
        if profile_ids is not None:
            rq = rq.filter(AaRetakeApply.student_id.in_(profile_ids or [-1]))
        if term:
            rq = rq.filter(AaRetakeApply.term_code == term)
        retake_rows = rq.all()
        _rt_terminal = ("APPROVED", "ENROLLED", "FINISHED", "REJECTED")
        retake_stat = _line_stat(retake_rows, lambda r: (r.status != "REJECTED") if r.status in _rt_terminal else None)

        # 免修：t_aa_exemption（有 college_id 直接列，APPROVED=通过）
        eq = db.query(AaExemption).filter(AaExemption.tenant_id == _tid(), AaExemption.is_deleted.is_(False))
        if college_ids is not None:
            eq = eq.filter(AaExemption.college_id.in_(college_ids or [-1]))
        if term:
            eq = eq.filter(AaExemption.term_code == term)
        exemption_rows = eq.all()
        _ex_terminal = (_EX_APPROVED, _EX_REJECTED, _EX_CANCELLED)
        exemption_stat = _line_stat(exemption_rows, lambda e: (e.status == _EX_APPROVED) if e.status in _ex_terminal else None)

        # 缓考：t_aa_deferred_exam（只读，APPROVED=已并入下一批次视为"通过"）
        dq = db.query(AaDeferredExam).filter(AaDeferredExam.tenant_id == _tid(), AaDeferredExam.is_deleted.is_(False))
        if profile_ids is not None:
            dq = dq.filter(AaDeferredExam.student_id.in_(profile_ids or [-1]))
        deferred_rows = dq.all()
        deferred_stat = _line_stat(deferred_rows, lambda d: (d.status == "APPROVED") if d.status in ("APPROVED", "REJECTED") else None)

        result = {"makeup": makeup_stat, "retake": retake_stat,
                  "deferred": deferred_stat, "exemption": exemption_stat}
        if dimension == "course":
            result["groups"] = {
                "makeup": _group_by(makeup_rows, lambda m: m.course_name),
                "retake": _group_by(retake_rows, lambda r: r.course_name),
                "deferred": _group_by(deferred_rows, lambda d: d.course_name),
                "exemption": _group_by(exemption_rows, lambda e: e.course_name),
            }
        elif dimension == "term":
            # 缓考无 term_code 建模（V1 未建模，分组统一置"未知"，如实登记不冒充数据）
            result["groups"] = {
                "makeup": _group_by(makeup_rows, lambda m: batch_term.get(m.batch_id)),
                "retake": _group_by(retake_rows, lambda r: r.term_code),
                "deferred": _group_by(deferred_rows, lambda d: None),
                "exemption": _group_by(exemption_rows, lambda e: e.term_code),
            }
        elif dimension == "college":
            from app.models import AcademicStudent, StudentProfile
            acad_to_profile = dict(db.query(AcademicStudent.id, AcademicStudent.student_id).filter(
                AcademicStudent.tenant_id == _tid(),
                AcademicStudent.id.in_({m.acad_student_id for m in makeup_rows} or [-1])).all())
            profile_ids_needed = (set(acad_to_profile.values())
                                  | {r.student_id for r in retake_rows} | {d.student_id for d in deferred_rows})
            profile_college = dict(db.query(StudentProfile.id, StudentProfile.college_id).filter(
                StudentProfile.tenant_id == _tid(), StudentProfile.id.in_(profile_ids_needed or [-1])).all())
            result["groups"] = {
                "makeup": _group_by(makeup_rows, lambda m: profile_college.get(acad_to_profile.get(m.acad_student_id))),
                "retake": _group_by(retake_rows, lambda r: profile_college.get(r.student_id)),
                "deferred": _group_by(deferred_rows, lambda d: profile_college.get(d.student_id)),
                "exemption": _group_by(exemption_rows, lambda e: e.college_id),
            }
        return result


def stats_detail(user, term=None, college_id=None, line=None, page=1, page_size=50):
    """下钻明细（三级施工卡 10-统计分析 §7 GET /makeup/stats/detail）。"""
    from app.models import AaDeferredExam, AaExemption, AaMakeupBatch, AaRetakeApply, AcademicMakeup
    line = (line or "makeup").strip()
    with session() as db:
        ctx = _ctx(user, db)
        college_ids = _scope_college_ids(ctx, college_id)
        profile_ids = _profile_ids_by_college(db, college_ids)
        acad_ids = _acad_ids_by_profile(db, profile_ids)
        if line == "makeup":
            q = db.query(AcademicMakeup, AaMakeupBatch).outerjoin(
                AaMakeupBatch, AcademicMakeup.batch_id == AaMakeupBatch.id).filter(
                AcademicMakeup.tenant_id == _tid(), AcademicMakeup.batch_id.isnot(None))
            if acad_ids is not None:
                q = q.filter(AcademicMakeup.acad_student_id.in_(acad_ids or [-1]))
            if term:
                q = q.filter(AaMakeupBatch.term_code == term)
            rows = q.order_by(AcademicMakeup.id.desc()).all()
            items = [{"makeupId": str(m.id), "courseName": m.course_name, "termCode": b.term_code if b else None,
                     "status": m.status, "finalScore": m.final_score, "batchId": str(m.batch_id)} for m, b in rows]
        elif line == "retake":
            q = db.query(AaRetakeApply).filter(AaRetakeApply.tenant_id == _tid(), AaRetakeApply.is_deleted.is_(False))
            if profile_ids is not None:
                q = q.filter(AaRetakeApply.student_id.in_(profile_ids or [-1]))
            if term:
                q = q.filter(AaRetakeApply.term_code == term)
            items = [_rt_dto(r) for r in q.order_by(AaRetakeApply.id.desc()).all()]
        elif line == "exemption":
            q = db.query(AaExemption).filter(AaExemption.tenant_id == _tid(), AaExemption.is_deleted.is_(False))
            if college_ids is not None:
                q = q.filter(AaExemption.college_id.in_(college_ids or [-1]))
            if term:
                q = q.filter(AaExemption.term_code == term)
            items = [_ex_dto(r) for r in q.order_by(AaExemption.id.desc()).all()]
        elif line == "deferred":
            q = db.query(AaDeferredExam).filter(AaDeferredExam.tenant_id == _tid(), AaDeferredExam.is_deleted.is_(False))
            if profile_ids is not None:
                q = q.filter(AaDeferredExam.student_id.in_(profile_ids or [-1]))
            items = [{"deferId": str(d.id), "studentName": d.student_name, "courseName": d.course_name,
                     "status": d.status} for d in q.order_by(AaDeferredExam.id.desc()).all()]
        else:
            raise _bad("line 参数非法（makeup/retake/exemption/deferred）")
        total = len(items)
        return items[(page - 1) * page_size: page * page_size], total


def export_makeup_stats_xlsx(user, term=None, college_id=None, purpose="") -> bytes:
    """四条线统计导出 xlsx（三级施工卡 10-统计分析 §11：水印+用途必填+审计；对齐「教务统计」
    export_stats_xlsx 同一套 xlsx 生成/水印/审计惯例，未接 6 大业务域通用导出——该框架列结构
    固定为"学生台账"型（姓名/学号/班级…），与本卡"四条线聚合数字"型导出不匹配，如实登记为
    与三级卡 §7 `/export/domain/academic-makeup` 字面表述的实现差异）。"""
    if not (purpose or "").strip() or len((purpose or "").strip()) < 5:
        raise _bad("导出用途必填（≥5 字）")
    data = aggregate_stats(user, term, college_id, None)
    from app.services.xlsx_util import build_ledger_xlsx
    watermark = f"导出人：{_op()}  时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose.strip()}"
    headers = ["条线", "人数/批次数", "通过率(%)"]
    labels = {"makeup": "补考", "retake": "重修", "deferred": "缓考", "exemption": "免修"}
    rows = []
    for key, label in labels.items():
        d = data[key]
        rate = round(d["passRate"] * 100, 1) if d["passRate"] is not None else "-"
        rows.append([label, d["count"], rate])
    content = build_ledger_xlsx("补考重修缓考免修统计", headers, rows, watermark=watermark)
    with session() as db:
        _audit(db, "AA_MAKEUP", None, "MAKEUP_STATS_EXPORT", f"统计导出 用途={purpose.strip()[:100]}")
        db.commit()
    return content


# ══════════ 材料归档（三级施工卡 11-材料归档 §7）══════════

def print_data(user, batch_id):
    """补考安排表打印页数据：批次+学生名单+（若挂考务批次，按课程名 best-effort 匹配）时间考场。
    仅 PUBLISHED 及以后状态可打印；学院角色范围内无匹配学生时拒绝（越权）。"""
    from app.models import AcademicMakeup, AcademicStudent
    with session() as db:
        ctx = _ctx(user, db)
        b = _get_mb(db, batch_id)
        if b.status not in (_MB_PUBLISHED, _MB_SCORING, _MB_REVIEWED, _MB_FINISHED):
            raise _invalid("补考批次尚未发布，暂不可打印安排表")
        rows = db.query(AcademicMakeup, AcademicStudent).join(
            AcademicStudent, AcademicMakeup.acad_student_id == AcademicStudent.id).filter(
            AcademicMakeup.tenant_id == _tid(), AcademicMakeup.batch_id == b.id).all()
        if ctx.scope_type == "COLLEGE":
            from app.models import College
            allowed_names = ({c.college_name for c in db.query(College).filter(
                College.tenant_id == _tid(), College.id.in_(ctx.college_ids)).all()} if ctx.college_ids else set())
            rows = [(m, s) for m, s in rows if s.college_name in allowed_names]
            if not rows:
                raise no_data_scope("该补考批次不在您的数据范围内")
        # 若挂考务批次，按课程名 best-effort 匹配考场/时间（缺失不阻断，前端显示"待补充"）
        exam_map = {}
        if b.exam_batch_ref:
            from app.models import AaExamCourse
            for c in db.query(AaExamCourse).filter(AaExamCourse.tenant_id == _tid(),
                                                    AaExamCourse.batch_id == b.exam_batch_ref,
                                                    AaExamCourse.is_deleted.is_(False)).all():
                exam_map[c.course_name] = {"examDate": c.exam_date, "startTime": c.start_time, "endTime": c.end_time}
        students = [{"studentNo": s.student_no, "studentName": s.name, "courseName": m.course_name,
                    "status": m.status, "finalScore": m.final_score,
                    **(exam_map.get(m.course_name) or {"examDate": None, "startTime": None, "endTime": None})}
                   for m, s in rows]
        _audit(db, "AA_MAKEUP", b.id, "MAKEUP_PRINT", f"打印补考安排表 {b.batch_name}")
        db.commit()
        return {"batchId": str(b.id), "batchName": b.batch_name, "termCode": b.term_code,
                "status": b.status, "publishedAt": _iso(b.published_at), "students": students}


def mark_archived(user, exemption_id):
    """标记免修材料已归档。仅审批已终态（APPROVED/REJECTED/CANCELLED）的申请可标记；已归档幂等。"""
    from app.models import AaExemption
    with session() as db:
        ctx = _ctx(user, db)
        e = db.query(AaExemption).filter(AaExemption.id == exemption_id, AaExemption.tenant_id == _tid()).first()
        if not e:
            raise not_found("免修申请不存在")
        if ctx.scope_type == "COLLEGE" and e.college_id and int(e.college_id) not in ctx.college_ids:
            raise no_data_scope("该学生不在您的数据范围内")
        if e.status not in (_EX_APPROVED, _EX_REJECTED, _EX_CANCELLED):
            raise _invalid("仅审批已终态的免修申请可标记归档")
        if e.archive_status == "ARCHIVED":
            return {"exemptionId": str(e.id), "archiveStatus": e.archive_status}
        e.archive_status = "ARCHIVED"
        _audit(db, "AA_EXEMPTION", e.id, "EXEMPTION_ARCHIVE", "标记材料已归档")
        db.commit()
        return {"exemptionId": str(e.id), "archiveStatus": e.archive_status}


def archive_list(user, term=None, status=None, page=1, page_size=50):
    """免修材料归档列表（教务处/学院教务员）：附材料文件名（查 t_file_object，仅限已终态申请可见原件）。"""
    from app.models import AaExemption
    with session() as db:
        ctx = _ctx(user, db)
        college_ids = _scope_college_ids(ctx, None)
        q = db.query(AaExemption).filter(AaExemption.tenant_id == _tid(), AaExemption.is_deleted.is_(False))
        if college_ids is not None:
            q = q.filter(AaExemption.college_id.in_(college_ids or [-1]))
        if term:
            q = q.filter(AaExemption.term_code == term)
        if status:
            q = q.filter(AaExemption.archive_status == status)
        rows = q.order_by(AaExemption.id.desc()).all()
        all_file_ids: set[int] = set()
        for e in rows:
            if e.material_file_ids:
                try:
                    all_file_ids.update(int(x) for x in json.loads(e.material_file_ids) if str(x).isdigit())
                except (ValueError, TypeError):
                    pass
        file_map = {}
        if all_file_ids:
            from app.models import FileObject
            file_map = {f.id: {"fileId": str(f.id), "fileName": f.file_name, "sizeBytes": f.size_bytes}
                       for f in db.query(FileObject).filter(FileObject.tenant_id == _tid(),
                                                             FileObject.id.in_(all_file_ids)).all()}
        items = []
        for e in rows:
            file_ids = []
            if e.material_file_ids:
                try:
                    file_ids = [int(x) for x in json.loads(e.material_file_ids) if str(x).isdigit()]
                except (ValueError, TypeError):
                    file_ids = []
            items.append({**_ex_dto(e), "archiveStatus": e.archive_status or "NOT_ARCHIVED",
                         "materialFiles": [file_map[fid] for fid in file_ids if fid in file_map]})
        total = len(items)
        return items[(page - 1) * page_size: page * page_size], total
