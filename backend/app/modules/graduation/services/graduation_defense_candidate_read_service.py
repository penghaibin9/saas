"""答辩分组候选学生 SQL 只读模型。

只负责候选检索；真正分配仍由 graduation_service.assign_defense_students
执行同批次、阶段、容量、数据范围和回避等最终校验。
"""
from __future__ import annotations

from sqlalchemy import or_, select

from app.core.exceptions import no_permission, not_found
from app.models import GraduationDefenseGroup, GraduationStudent
from app.modules.graduation.services.graduation_scope_service import has_full_scope
from app.services.db_service import _tid, session

CANDIDATE_LIMIT = 200
ELIGIBLE_STAGES = ("FINAL_CHECK", "DEFENSE", "COMPLETED")


def list_defense_eligible_students(gid=None, keyword=None) -> list[dict]:
    """返回同批次可分配学生；SQL 侧筛选并限制候选窗口，避免全租户加载。"""
    tenant_id = _tid()
    if not has_full_scope():
        raise no_permission("Only graduation managers can list defense assignment candidates")

    gid_int = int(gid) if gid else None
    with session() as db:
        group_batch = None
        if gid_int:
            group = db.get(GraduationDefenseGroup, gid_int)
            if not group or group.is_deleted or group.tenant_id != tenant_id:
                raise not_found("答辩组不存在")
            group_batch = group.batch_id

        filters = [
            GraduationStudent.tenant_id == tenant_id,
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.stage.in_(ELIGIBLE_STAGES),
        ]
        if group_batch is not None:
            filters.append(GraduationStudent.batch_id == group_batch)

        value = str(keyword or "").strip()
        if value:
            filters.append(or_(
                GraduationStudent.name.contains(value),
                GraduationStudent.student_no.contains(value),
            ))

        students = db.scalars(
            select(GraduationStudent)
            .where(*filters)
            .order_by(GraduationStudent.id)
            .limit(CANDIDATE_LIMIT)
        ).all()

        return [
            {
                "id": str(student.id),
                "name": student.name,
                "studentNo": student.student_no or "",
                "className": student.class_name or "",
                "topicTitle": student.topic_title or "",
                "advisorName": student.advisor_name or "",
                "currentGroup": student.defense_group or "",
                "assignedHere": student.defense_group_id == gid_int if gid_int else False,
                "assignedElsewhere": bool(student.defense_group_id) and student.defense_group_id != gid_int,
            }
            for student in students
        ]
