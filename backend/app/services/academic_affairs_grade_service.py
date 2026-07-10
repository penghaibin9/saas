"""13B-P5 成绩录入（平时+期末按比例合成）+ 成绩读侧视图。

商业教务软件标准：成绩录入任务配平时/期末占比→录入两项分→合成总评→发布原子回写 t_acad_grade
(经 t_acad_student 映射，投影不复制)。读侧：学生成绩单/挂科清单/成绩分析(零写入)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_type, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


def _acad_student_id(db, student_id, name=""):
    """全局学生 → 学业过程台账 id；无则建一行（投影落点）。"""
    from app.models import AcademicStudent, StudentProfile
    a = db.scalars(select(AcademicStudent).where(
        AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == int(student_id),
        AcademicStudent.is_deleted.is_(False))).first()
    if a:
        return a.id
    s = db.get(StudentProfile, int(student_id))
    a = AcademicStudent(tenant_id=_tid(), student_id=int(student_id), student_no=(s.student_no if s else None),
                        name=(s.real_name if s else name), class_id=(str(s.class_id) if s and s.class_id else None))
    db.add(a)
    db.flush()
    return a.id


# ═══════════ 成绩录入任务 ═══════════

def create_grade_task(body, user) -> dict:
    usual = int(getattr(body, "usualRatio", 30) or 30)
    final = int(getattr(body, "finalRatio", 70) or 70)
    if usual + final != 100:
        raise AppException("VALIDATION_ERROR", "平时占比+期末占比必须=100")
    with session() as db:
        from app.models import AaGradeTask
        t = AaGradeTask(tenant_id=_tid(),
                        teaching_task_id=(int(body.teachingTaskId) if getattr(body, "teachingTaskId", None) else None),
                        term_id=(int(body.termId) if getattr(body, "termId", None) else None),
                        term_code=getattr(body, "termCode", None), course_name=getattr(body, "courseName", None),
                        class_id=(int(body.classId) if getattr(body, "classId", None) else None),
                        credit=getattr(body, "credit", None), usual_ratio=usual, final_ratio=final,
                        pass_line=int(getattr(body, "passLine", 60) or 60), status="DRAFT")
        db.add(t)
        db.flush()
        _audit(db, "AA_GRADE_TASK", t.id, "CREATE", getattr(body, "courseName", "") or "")
        db.commit()
        db.refresh(t)
        return {"gradeTaskId": str(t.id), "courseName": t.course_name or "", "usualRatio": t.usual_ratio,
                "finalRatio": t.final_ratio, "status": t.status}


def enter_score(task_id, user, body) -> dict:
    """录入某生平时/期末分，实时合成总评（未发布，可改）。"""
    with session() as db:
        from app.models import AaGradeRecord, AaGradeTask
        t = db.get(AaGradeTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("成绩录入任务不存在")
        if t.status == "PUBLISHED":
            raise AppException("DATA_CONFLICT", "成绩已发布，不可再录入（更正走教务）")
        sid = int(body.studentId)
        usual = getattr(body, "usualScore", None)
        final = getattr(body, "finalScore", None)
        total = None
        if usual is not None and final is not None:
            total = round(usual * t.usual_ratio / 100 + final * t.final_ratio / 100)
        rec = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _tid(), AaGradeRecord.task_id == t.id,
            AaGradeRecord.student_id == sid, AaGradeRecord.is_deleted.is_(False))).first()
        if not rec:
            rec = AaGradeRecord(tenant_id=_tid(), task_id=t.id, student_id=sid)
            db.add(rec)
        rec.usual_score, rec.final_score, rec.total_score = usual, final, total
        rec.pass_status = ("PASSED" if (total is not None and total >= t.pass_line) else
                           ("FAIL" if total is not None else None))
        if t.status == "DRAFT":
            t.status = "ENTERING"
        db.flush()
        db.commit()
        return {"recordId": str(rec.id), "studentId": str(sid), "usualScore": usual,
                "finalScore": final, "totalScore": total, "passStatus": rec.pass_status}


def publish_grades(task_id, user) -> dict:
    """发布成绩：合成总评原子回写 t_acad_grade（经 t_acad_student 映射投影）。"""
    with session() as db:
        from app.models import AaGradeRecord, AaGradeTask, AcademicGrade, StudentProfile
        t = db.get(AaGradeTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("成绩录入任务不存在")
        if t.status == "PUBLISHED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "成绩已发布")
        recs = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _tid(), AaGradeRecord.task_id == t.id,
            AaGradeRecord.is_deleted.is_(False))).all()
        incomplete = [r for r in recs if r.total_score is None]
        if not recs or incomplete:
            raise AppException("DATA_CONFLICT", f"仍有 {len(incomplete)} 名学生成绩未录全，不可发布")
        projected = 0
        for r in recs:
            s = db.get(StudentProfile, int(r.student_id))
            asid = _acad_student_id(db, r.student_id, s.real_name if s else "")
            g = AcademicGrade(tenant_id=_tid(), acad_student_id=asid, course_name=t.course_name or "",
                              term=t.term_code, nature="REQUIRED", credit_value=(t.credit or 0),
                              score=r.total_score, pass_status=r.pass_status, exam_type="FINAL",
                              record_status="ACTIVE")
            db.add(g)
            db.flush()
            r.acad_grade_id = g.id
            projected += 1
        t.status, t.publish_at = "PUBLISHED", datetime.utcnow()
        _audit(db, "AA_GRADE_TASK", t.id, "PUBLISH", f"projected={projected}")
        db.commit()
        return {"gradeTaskId": str(task_id), "status": "PUBLISHED", "projected": projected}


# ═══════════ 成绩读侧视图（零写入）═══════════

def transcript(student_id, user) -> dict:
    """学生成绩单（读 t_acad_grade）。"""
    from app.models import AcademicGrade, AcademicStudent
    with session() as db:
        a = db.scalars(select(AcademicStudent).where(
            AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == int(student_id),
            AcademicStudent.is_deleted.is_(False))).first()
        if not a:
            return {"items": [], "totalCredits": 0, "gpa": None, "note": "无学业记录"}
        rows = db.scalars(select(AcademicGrade).where(
            AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == a.id,
            AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False))
            .order_by(AcademicGrade.term)).all()
        items = [{"courseName": g.course_name, "term": g.term or "", "credit": float(g.credit_value or 0),
                  "score": g.score, "passStatus": g.pass_status} for g in rows]
        earned = sum(float(g.credit_value or 0) for g in rows if g.pass_status == "PASSED")
        return {"items": items, "earnedCredits": earned,
                "failCount": sum(1 for g in rows if g.pass_status == "FAIL")}


def fail_list(user, term=None, page=1, page_size=50):
    """挂科清单（下钻，读侧）。与 t_acad_student 一次性 JOIN 取数 + DB 级分页，
    避免逐行 db.get(AcademicStudent) 的 N+1 与全量加载后内存切片。"""
    from app.models import AcademicGrade, AcademicStudent
    with session() as db:
        join = and_(AcademicStudent.id == AcademicGrade.acad_student_id,
                    AcademicStudent.tenant_id == AcademicGrade.tenant_id)
        conds = [AcademicGrade.tenant_id == _tid(), AcademicGrade.pass_status == "FAIL",
                 AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False)]
        if term:
            conds.append(AcademicGrade.term == term)
        total = db.scalar(select(func.count()).select_from(AcademicGrade)
                          .outerjoin(AcademicStudent, join).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.execute(select(AcademicGrade, AcademicStudent)
                          .outerjoin(AcademicStudent, join).where(*conds)
                          .order_by(AcademicGrade.id.desc()).offset(offset).limit(page_size)).all()
        out = [{"studentName": a.name if a else "", "studentId": str(a.student_id or "") if a else "",
                "courseName": g.course_name, "term": g.term or "", "score": g.score} for g, a in rows]
        return out, total


def grade_analysis(user, term=None):
    """成绩分析：分数段分布 + 及格率（读侧聚合）。"""
    from app.models import AcademicGrade
    with session() as db:
        conds = [AcademicGrade.tenant_id == _tid(), AcademicGrade.score.is_not(None),
                 AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False)]
        if term:
            conds.append(AcademicGrade.term == term)
        rows = db.scalars(select(AcademicGrade).where(*conds)).all()
        buckets = {"90-100": 0, "80-89": 0, "70-79": 0, "60-69": 0, "0-59": 0}
        passed = 0
        for g in rows:
            sc = g.score or 0
            if sc >= 90:
                buckets["90-100"] += 1
            elif sc >= 80:
                buckets["80-89"] += 1
            elif sc >= 70:
                buckets["70-79"] += 1
            elif sc >= 60:
                buckets["60-69"] += 1
            else:
                buckets["0-59"] += 1
            if g.pass_status == "PASSED":
                passed += 1
        total = len(rows)
        return {"total": total, "passRate": round(passed / total, 3) if total else 0.0,
                "distribution": [{"range": k, "count": v} for k, v in buckets.items()]}
