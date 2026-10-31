"""补考与清考共用开课学院范围、逐条审核事实及校级发布门禁。"""
from sqlalchemy import and_, case, func

from app.core.exceptions import no_data_scope
from app.core.permissions import has_permission
from app.core.timeutil import iso_utc, utc_now_naive
from . import academic_affairs_makeup_core_service as core

REVIEW_PERMISSION = "academicAffairs.grade.collegeReview"


def record_query(db):
    from app.models import AcademicMakeup as M, AcademicStudent as S, AcademicGrade as G
    from app.models import AaCourse as C, AaTeachingTask as T, AaTeachingTaskBatch as B

    # 历史未冻结行只沿精确课程/教学任务关系解析，不用学生所在学院或课程名称猜配。
    college = func.coalesce(M.review_college_id, C.owner_college_id, B.college_id)
    query = (db.query(M, S, college.label("review_college"))
        .outerjoin(S, and_(S.id == M.acad_student_id, S.tenant_id == M.tenant_id, S.is_deleted.is_(False)))
        .outerjoin(G, and_(G.id == M.origin_grade_id, G.tenant_id == M.tenant_id, G.is_deleted.is_(False)))
        .outerjoin(C, and_(C.id == M.course_id, C.tenant_id == M.tenant_id, C.is_deleted.is_(False)))
        .outerjoin(T, and_(T.id == func.coalesce(M.teaching_task_id, G.teaching_task_id), T.tenant_id == M.tenant_id, T.is_deleted.is_(False)))
        .outerjoin(B, and_(B.id == T.batch_id, B.tenant_id == M.tenant_id, B.is_deleted.is_(False)))
        .filter(M.tenant_id == core._tid(), M.is_deleted.is_(False)))
    return query, college


def scoped_records(db, ctx):
    query, college = record_query(db)
    if ctx.scope_type == "COLLEGE" and ctx.college_ids:
        return query.filter(college.in_(ctx.college_ids))
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("当前岗位不能查看补考、清考成绩名单")
    return query


def reviewed(row):
    return bool(row.review_college_id and row.college_reviewed_by and row.college_reviewed_at)


def summary(db, ctx, user, batch_ids):
    from app.models import AcademicMakeup as M

    if not batch_ids:
        return {}
    query = scoped_records(db, ctx).filter(M.batch_id.in_(batch_ids))
    done = and_(M.review_college_id.is_not(None), M.college_reviewed_by.is_not(None), M.college_reviewed_at.is_not(None))
    rows = query.with_entities(M.batch_id, func.count(M.id),
        func.sum(case((done, 1), else_=0)),
        func.sum(case((and_(M.status == "SCORED", M.final_score.is_not(None)), 1), else_=0)),
    ).group_by(M.batch_id).all()
    can_review = ctx.scope_type == "COLLEGE" and has_permission(user, REVIEW_PERMISSION)
    return {int(bid): {"reviewTotal": int(total), "reviewedCount": int(done_count or 0),
        "canCollegeReview": bool(can_review and scored == total and done_count < total)}
        for bid, total, done_count, scored in rows}


def approve_rows(rows, college_ids, actor):
    """只审核当前学院全部已录成绩；另一学院未录完不阻止本院办理。"""
    own = [(row, college) for row, _student, college in rows if college in college_ids]
    if not own:
        raise no_data_scope("本批次没有当前开课学院的成绩")
    if not actor:
        raise no_data_scope("当前账号身份无法核实")
    if any(row.status != "SCORED" or row.final_score is None for row, _ in own):
        raise core._invalid("本学院仍有未录入成绩，请先完成录分")
    changed = []
    for row, college in own:
        if reviewed(row):
            continue
        row.review_college_id = college
        row.college_reviewed_by = str(actor)
        row.college_reviewed_at = utc_now_naive()
        changed.append(row)
    return changed


def require_complete(records):
    if not records or any(row.status != "SCORED" or row.final_score is None or not reviewed(row) for row in records):
        raise core._invalid("全部开课学院完成成绩审核后，学校教务才能发布回写")


def list_records(user, batch_id, page=1, page_size=100, *, makeup_id=None, origin_grade_id=None, acad_student_id=None):
    from app.models import AcademicMakeup as M

    with core.session() as db:
        ctx = core._ctx(user, db)
        core._get_mb(db, int(batch_id))
        query = scoped_records(db, ctx).filter(M.batch_id == int(batch_id))
        for column, value in ((M.id, makeup_id), (M.origin_grade_id, origin_grade_id), (M.acad_student_id, acad_student_id)):
            if value is not None:
                query = query.filter(column == int(value))
        total = query.count()
        size = max(1, min(200, int(page_size)))
        rows = query.order_by(M.id).offset((max(1, int(page)) - 1) * size).limit(size).all()
        return [{"makeupId": str(m.id), "acadStudentId": str(m.acad_student_id),
            "originGradeId": str(m.origin_grade_id) if m.origin_grade_id else None,
            "studentId": str(s.student_id) if s and s.student_id else None,
            "studentNo": s.student_no if s else None, "studentName": s.name if s else "学生档案待核对",
            "courseName": m.course_name, "courseCode": m.course_code, "attemptNo": m.attempt_no,
            "kind": m.kind, "originScore": m.origin_score, "finalScore": m.final_score, "status": m.status,
            "reviewCollegeId": str(college) if college else None,
            "collegeReviewed": reviewed(m), "collegeReviewedAt": iso_utc(m.college_reviewed_at),
        } for m, s, college in rows], total
