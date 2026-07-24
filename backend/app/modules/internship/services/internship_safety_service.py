from __future__ import annotations
from datetime import datetime
from sqlalchemy import select
from app.core.exceptions import AppException, not_found
from app.models import InternshipSafetyCompletion, InternshipSafetyCourse
from app.services.db_service import _as_id, _tid, session
def _row(x): return {"id":str(x.id),"title":x.title,"status":x.status,"requiredMinutes":x.required_minutes,"passingScore":x.passing_score,"maxAttempts":x.max_attempts}
def list_courses(batch_id):
    with session() as db:return [_row(x) for x in db.scalars(select(InternshipSafetyCourse).where(InternshipSafetyCourse.tenant_id==_tid(),InternshipSafetyCourse.batch_id==_as_id(batch_id),InternshipSafetyCourse.is_deleted.is_(False))).all()]
def create_course(body):
    b=body or {}
    with session() as db:
        x=InternshipSafetyCourse(tenant_id=_tid(),batch_id=_as_id(b.get("batchId")) if b.get("batchId") else None,title=b.get("title") or "",course_version=b.get("courseVersion") or "v1",required_minutes=int(b.get("requiredMinutes",60)),passing_score=int(b.get("passingScore",80)),max_attempts=int(b.get("maxAttempts",3)),require_commitment=bool(b.get("requireCommitment",True)),content_snapshot=b.get("contentSnapshot"),material_file_ids=b.get("materialFileIds"),status=b.get("status") or "ACTIVE")
        if not x.title: raise AppException("VALIDATION_ERROR","课程名称必填")
        db.add(x);db.commit();return _row(x)
def teacher_review_completion(completion_id, score=None, studied_minutes=None, commitment=None, user=None):
    if score is None or studied_minutes is None or commitment is None: raise AppException("VALIDATION_ERROR","审核须提交 score、studiedMinutes、commitment，禁止客户端 passed 直传")
    with session() as db:
        x=db.get(InternshipSafetyCompletion,_as_id(completion_id))
        if not x or x.tenant_id!=_tid():raise not_found("安全教育完成记录不存在")
        c=db.get(InternshipSafetyCourse,x.course_id)
        if not c:raise not_found("安全教育课程不存在")
        if x.attempt_count >= c.max_attempts:raise AppException("DATA_CONFLICT","已超过最大尝试次数")
        x.attempt_count+=1;x.score=int(score);x.studied_minutes=int(studied_minutes);x.commitment_confirmed=bool(commitment);x.commitment_at=datetime.utcnow() if commitment else None;x.reviewed_by_name=(user or {}).get("realName") or "系统";x.reviewed_at=datetime.utcnow()
        x.passed=x.score>=c.passing_score and x.studied_minutes>=c.required_minutes and (not c.require_commitment or x.commitment_confirmed);x.status="PASSED" if x.passed else "FAILED";x.completed_at=datetime.utcnow();db.commit();return {"id":str(x.id),"status":x.status,"passed":x.passed,"courseVersion":x.course_version}


def ensure_completion(body, user=None):
    """为学生创建待审完成记录（不可直接写 passed）。"""
    b = body or {}
    if not b.get("internshipId") or not b.get("courseId"):
        raise AppException("VALIDATION_ERROR", "internshipId 与 courseId 必填")
    from app.models import InternshipRecord
    with session() as db:
        rec = db.get(InternshipRecord, _as_id(b["internshipId"]))
        course = db.get(InternshipSafetyCourse, _as_id(b["courseId"]))
        if not rec or rec.tenant_id != _tid():
            raise not_found("实习记录不存在")
        if not course or course.tenant_id != _tid() or course.status != "ACTIVE":
            raise not_found("安全教育课程不可用")
        exist = db.scalars(select(InternshipSafetyCompletion).where(
            InternshipSafetyCompletion.tenant_id == _tid(),
            InternshipSafetyCompletion.internship_id == rec.id,
            InternshipSafetyCompletion.course_id == course.id,
            InternshipSafetyCompletion.is_deleted.is_(False),
        )).first()
        if exist:
            return {"id": str(exist.id), "status": exist.status, "passed": exist.passed}
        x = InternshipSafetyCompletion(
            tenant_id=_tid(), internship_id=rec.id, batch_id=rec.batch_id,
            student_id=rec.student_id, course_id=course.id,
            course_version=course.course_version, started_at=datetime.utcnow(),
            status="PENDING", review_mode="TEACHER_REVIEW",
        )
        db.add(x); db.commit()
        return {"id": str(x.id), "status": x.status, "passed": False}
