"""D8-U 成绩认定管理只读查询。

写链、证据冻结、终审并发与权限语义继续唯一复用 hardened recognition public service；
这里只把管理列表从全量 ``.all()`` + Python 切片收口为数据库 COUNT + LIMIT/OFFSET。
"""
from __future__ import annotations

from app.modules.academic_affairs.services import academic_affairs_recognition_service as recognition_service


def get_detail(user, recognition_id):
    """Exact managed request; reuse the list's canonical scope and evidence DTO."""
    from app.core.exceptions import not_found
    from app.models import AaGradeRecognition

    with recognition_service.session() as db:
        recognition_service._require_school(user, db)
        row = db.query(AaGradeRecognition).filter(
            AaGradeRecognition.id == int(recognition_id),
            AaGradeRecognition.tenant_id == recognition_service._tid(),
            AaGradeRecognition.is_deleted.is_(False),
        ).first()
        if row is None:
            raise not_found("成绩认定申请不存在")
        return recognition_service._dto(row)


def list_all(user, status=None, page=1, page_size=50):
    from app.models import AaGradeRecognition

    with recognition_service.session() as db:
        recognition_service._require_school(user, db)
        query = db.query(AaGradeRecognition).filter(
            AaGradeRecognition.tenant_id == recognition_service._tid(),
            AaGradeRecognition.is_deleted.is_(False),
        )
        if status:
            query = query.filter(AaGradeRecognition.status == status)

        total = query.count()
        rows = (
            query.order_by(AaGradeRecognition.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [recognition_service._dto(row) for row in rows], total


def student_target_courses(user, keyword=None, page=1, page_size=20):
    """认定目标版本候选；不代替提交时的课程、成绩、重复申请与证据校验。"""
    from sqlalchemy import func, or_

    from app.core.exceptions import AppException
    from app.models import AaCourse
    from app.services.mobile_student_service import _require_student

    _require_student(user)
    if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 100:
        raise AppException("VALIDATION_ERROR", "页码须大于等于 1，每页数量须为 1 至 100")
    if keyword is not None and (not isinstance(keyword, str) or len(keyword) > 100):
        raise AppException("VALIDATION_ERROR", "课程搜索关键词最长 100 字符")
    keyword = (keyword or "").strip()

    with recognition_service.session() as db:
        # 使用与正式自助提交相同的账号/学生主档解析，不按姓名另建关联。
        recognition_service._resolve_student(db)
        query = db.query(AaCourse.id, AaCourse.course_code, AaCourse.course_name, AaCourse.version).filter(
            AaCourse.tenant_id == recognition_service._tid(),
            AaCourse.is_deleted.is_(False),
            func.trim(AaCourse.course_code) != "",
            AaCourse.version != 0,
        )
        if keyword:
            query = query.filter(or_(
                AaCourse.course_code.contains(keyword, autoescape=True),
                AaCourse.course_name.contains(keyword, autoescape=True),
            ))
        total = query.count()
        rows = (query.order_by(AaCourse.course_code.asc(), AaCourse.version.desc(), AaCourse.id.asc())
                .offset((page - 1) * page_size).limit(page_size).all())
        return [{"courseId": str(row.id), "courseCode": row.course_code,
                 "courseName": row.course_name, "version": int(row.version)} for row in rows], total
