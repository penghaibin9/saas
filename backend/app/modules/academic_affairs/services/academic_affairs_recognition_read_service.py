"""D8-U 成绩认定管理只读查询。

写链、证据冻结、终审并发与权限语义继续唯一复用 hardened recognition public service；
这里只把管理列表从全量 ``.all()`` + Python 切片收口为数据库 COUNT + LIMIT/OFFSET。
"""
from __future__ import annotations

from app.modules.academic_affairs.services import academic_affairs_recognition_service as recognition_service


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
