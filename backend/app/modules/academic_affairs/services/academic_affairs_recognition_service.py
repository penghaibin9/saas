"""成绩认定/课程替代服务（对标商业教务 6-2）。

转专业/转学/证书折算场景：学生（或教务代录）申请用原修课程成绩替代现计划课程 →
教务审核 → 通过写 t_acad_grade(source=RECOGNIZED) 并刷新学生台账聚合（学分/绩点即时生效）。

纪律：
- 同学生同目标课程仅一条在途/已通过记录（幂等防重复认定）；
- 学生已通过的课程不允许再认定（无意义且会污染台账）；
- 通过与驳回都留痕（审核人/时间/意见），回写行 acad_grade_id 回链可倒查。
"""
from __future__ import annotations

from datetime import datetime

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session


def _bad(m):
    return AppException("VALIDATION_ERROR", m)


def _invalid(m):
    return AppException("DATA_CONFLICT", m, http_status=409)


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("realName") or ctx.get("loginName") or ctx.get("userId") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_GRADE_RECOGNITION", biz_id=biz_id,
                             action=action, operator=_op(), role_name=_role(), detail=detail[:990],
                             occurred_at=datetime.utcnow()))


def _require_school(user, db):
    ctx = build_affairs_context(user, db)
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可审核成绩认定")
    return ctx


def _dto(r):
    import json as _json
    atts = []
    if getattr(r, "attachment_file_ids", None):
        try:
            atts = _json.loads(r.attachment_file_ids) or []
        except (ValueError, TypeError):
            atts = []
    return {"recognitionId": str(r.id), "studentId": str(r.student_id), "studentNo": r.student_no,
            "studentName": r.student_name, "sourceCourseName": r.source_course_name,
            "sourceScore": r.source_score,
            "sourceCredit": float(r.source_credit) if r.source_credit is not None else None,
            "sourceOrigin": r.source_origin,
            "targetCourseId": str(r.target_course_id) if getattr(r, "target_course_id", None) else None,
            "targetCourseName": r.target_course_name,
            "attachmentFileIds": [str(x) for x in atts],
            "reason": r.reason, "reviewReason": r.review_reason, "reviewedBy": r.reviewed_by,
            "reviewedAt": _iso(r.reviewed_at), "status": r.status}


def _resolve_student(db, *, student_no=None):
    from app.models import StudentProfile
    ctx = get_current_user_ctx() or {}
    sno = student_no or ctx.get("studentNo")
    p = db.query(StudentProfile).filter(StudentProfile.tenant_id == _tid(),
                                        StudentProfile.student_no == sno,
                                        StudentProfile.is_deleted.is_(False)).first()
    if not p:
        raise not_found("学生档案不存在")
    return p


def _passed_courses(db, profile_id) -> set:
    from app.models import AcademicGrade, AcademicStudent
    a = db.query(AcademicStudent).filter(AcademicStudent.tenant_id == _tid(),
                                         AcademicStudent.student_id == profile_id).first()
    if not a:
        return set()
    rows = db.query(AcademicGrade).filter(
        AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == a.id,
        AcademicGrade.pass_status == "PASSED", AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False)).all()
    return {(g.course_name or "").strip() for g in rows}


def _resolve_target(db, body):
    """目标校内课程:传 targetCourseId 则校验课程库并取快照名(对标正方"选择校内课程");
    否则回退手填 targetCourseName。返回 (course_id 或 None, 课程名)。"""
    from app.models import AaCourse
    cid = getattr(body, "targetCourseId", None)
    if cid and str(cid).isdigit():
        c = db.query(AaCourse).filter(AaCourse.id == int(cid), AaCourse.tenant_id == _tid(),
                                      AaCourse.is_deleted.is_(False)).first()
        if not c:
            raise _bad("所选目标课程不存在")
        return int(cid), (c.course_name or "").strip()
    return None, (getattr(body, "targetCourseName", None) or "").strip()


def _validate_attachments(db, file_ids):
    """佐证附件:校验 file_id 均为本租户真实 FileObject(范式对齐免修 material_file_ids)。返回 JSON 串或 None。"""
    import json as _json
    from app.models import FileObject
    if not file_ids:
        return None
    ids = file_ids if isinstance(file_ids, list) else [file_ids]
    int_ids = [int(x) for x in ids if str(x).isdigit()]
    if int_ids:
        found = db.query(FileObject).filter(FileObject.tenant_id == _tid(),
                                            FileObject.id.in_(int_ids)).count()
        if found != len(int_ids):
            raise _bad("佐证附件包含无效文件，请重新上传")
    return _json.dumps([str(x) for x in ids], ensure_ascii=False)


def submit(user, body, *, student_no=None) -> dict:
    """提交认定申请（学生自助时 student_no=None 取 token；教务代录传学号）。"""
    from app.models import AaGradeRecognition
    with session() as db:
        if student_no is not None:
            _require_school(user, db)
        p = _resolve_student(db, student_no=student_no)
        src = (getattr(body, "sourceCourseName", None) or "").strip()
        # 目标课程:优先课程库选择器(targetCourseId → 快照名),否则手填 targetCourseName
        target_course_id, tgt = _resolve_target(db, body)
        score = getattr(body, "sourceScore", None)
        if not src or not tgt:
            raise _bad("原课程与目标课程必填")
        if score is None or not (0 <= int(score) <= 100):
            raise _bad("原成绩必填（0-100）")
        if int(score) < 60:
            raise _bad("原成绩未及格，不可用于课程替代认定")
        if tgt in _passed_courses(db, p.id):
            raise _invalid("目标课程已通过，无需认定")
        attach_json = _validate_attachments(db, getattr(body, "attachmentFileIds", None))
        dup = db.query(AaGradeRecognition).filter(
            AaGradeRecognition.tenant_id == _tid(), AaGradeRecognition.student_id == p.id,
            AaGradeRecognition.target_course_name == tgt,
            AaGradeRecognition.status.in_(("SUBMITTED", "APPROVED")),
            AaGradeRecognition.is_deleted.is_(False)).first()
        if dup:
            raise _invalid("该目标课程已有在途或已通过的认定记录")
        r = AaGradeRecognition(
            tenant_id=_tid(), student_id=p.id, student_no=p.student_no, student_name=p.real_name,
            source_course_name=src, source_score=int(score),
            source_credit=getattr(body, "sourceCredit", None),
            source_origin=getattr(body, "sourceOrigin", None),
            target_course_id=target_course_id, target_course_name=tgt,
            attachment_file_ids=attach_json,
            reason=getattr(body, "reason", None), status="SUBMITTED")
        db.add(r)
        db.flush()
        _audit(db, r.id, "RECOG_SUBMIT", f"{p.student_no} {src}→{tgt}")
        db.commit()
        return _dto(r)


def review(user, recognition_id, action, reason="") -> dict:
    """教务审核：APPROVE 写 t_acad_grade(source=RECOGNIZED)+刷新台账；REJECT 原因≥5字。"""
    from app.models import AaGradeRecognition, AcademicGrade
    from app.modules.academic_affairs.services.academic_affairs_grade_service import (
        _acad_student_id, _refresh_aggregates)
    with session() as db:
        _require_school(user, db)
        r = db.get(AaGradeRecognition, int(recognition_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("认定记录不存在")
        if r.status != "SUBMITTED":
            raise _invalid("仅待审核记录可审核")
        act = (action or "").upper()
        if act == "REJECT":
            if not reason or len(reason.strip()) < 5:
                raise _bad("驳回原因必填且不少于 5 字")
            r.status, r.review_reason = "REJECTED", reason.strip()
            r.reviewed_by, r.reviewed_at = _op(), datetime.utcnow()
            _audit(db, r.id, "RECOG_REJECT", reason.strip()[:100])
            db.commit()
            return _dto(r)
        if act != "APPROVE":
            raise _bad("无效操作")
        a = _acad_student_id(db, r.student_id, r.student_name or "")
        g = AcademicGrade(tenant_id=_tid(), acad_student_id=a.id,
                          course_name=r.target_course_name, score=r.source_score,
                          credit_value=(r.source_credit or 0), pass_status="PASSED",
                          source="RECOGNIZED", record_status="ACTIVE")
        db.add(g)
        db.flush()
        r.acad_grade_id = g.id
        r.status, r.review_reason = "APPROVED", (reason or "").strip() or None
        r.reviewed_by, r.reviewed_at = _op(), datetime.utcnow()
        _refresh_aggregates(db, a)
        _audit(db, r.id, "RECOG_APPROVE",
               f"{r.student_no} {r.source_course_name}→{r.target_course_name} 计{r.source_score}分")
        db.commit()
        return _dto(r)


def list_all(user, status=None, page=1, page_size=50):
    """成绩认定台账(教务处口径)。收敛到 TENANT_ALL:本域为教务处管理视图,
    读侧与写侧(review 需 _require_school)口径一致,防越院/越范围读全校认定明细(修数据范围红线)。"""
    from app.models import AaGradeRecognition
    with session() as db:
        _require_school(user, db)
        q = db.query(AaGradeRecognition).filter(AaGradeRecognition.tenant_id == _tid(),
                                                AaGradeRecognition.is_deleted.is_(False))
        if status:
            q = q.filter(AaGradeRecognition.status == status)
        rows = q.order_by(AaGradeRecognition.id.desc()).all()
        return [_dto(r) for r in rows[(page - 1) * page_size: page * page_size]], len(rows)


def my(user):
    from app.models import AaGradeRecognition
    with session() as db:
        p = _resolve_student(db)
        rows = db.query(AaGradeRecognition).filter(
            AaGradeRecognition.tenant_id == _tid(), AaGradeRecognition.student_id == p.id,
            AaGradeRecognition.is_deleted.is_(False)).order_by(AaGradeRecognition.id.desc()).all()
        return [_dto(r) for r in rows]
