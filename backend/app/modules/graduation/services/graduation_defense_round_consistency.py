"""二次答辩严格状态机。

只能在第一轮评分全部确认后创建一次第二轮；禁止第三轮及以上，禁止在成绩已经
核算、复核或发布后继续创建答辩轮次。若学校未来需要延期答辩/多轮补答辩，应另建
明确业务类型，不能复用“二次答辩”按钮无限递增轮次。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import (
    GraduationDefenseGroup,
    GraduationDefenseScore,
    GraduationGrade,
    GraduationStudent,
)
from app.modules.graduation.policies import defense_policy
from app.modules.graduation.services.graduation_command_service import _conflict_guard
from app.services.db_service import _tid, session

@_conflict_guard
def create_second_defense(gd_student_id, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "二次答辩原因必填且不少于 5 字")

    from app.modules.graduation.services import graduation_defense_score_service as service
    from app.modules.graduation.services import graduation_identity as identity
    from app.modules.graduation.services import graduation_todo_helper as todo

    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(gd_student_id),
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
        ).with_for_update()).first()
        if not student:
            raise not_found("毕设学生不存在")
        defense_policy.authorize(db, student, "secondRound")
        if student.stage in ("COMPLETED", "ARCHIVED"):
            raise AppException("DATA_CONFLICT", "已完成或已归档学生不可直接创建二次答辩，请先按成绩撤回流程处理")

        grade = db.scalars(select(GraduationGrade).where(
            GraduationGrade.tenant_id == _tid(),
            GraduationGrade.gd_student_id == student.id,
            GraduationGrade.is_deleted.is_(False),
        ).with_for_update()).first()
        if grade and grade.status in ("CALCULATED", "REVIEWED", "PUBLISHED"):
            raise AppException(
                "DATA_CONFLICT",
                "成绩已经核算、复核或发布，须先按成绩退回/撤回流程恢复到答辩阶段后再创建二次答辩",
            )

        all_rows = db.scalars(select(GraduationDefenseScore).where(
            GraduationDefenseScore.tenant_id == _tid(),
            GraduationDefenseScore.gd_student_id == student.id,
            GraduationDefenseScore.is_deleted.is_(False),
        ).order_by(GraduationDefenseScore.round_no, GraduationDefenseScore.id).with_for_update()).all()
        if not all_rows:
            raise AppException("DATA_CONFLICT", "尚未完成首次答辩评分，不能创建二次答辩")
        rounds = {int(row.round_no or 1) for row in all_rows}
        if any(round_no >= 2 for round_no in rounds):
            raise AppException("DATA_CONFLICT", "该生已存在二次答辩，不能重复创建或生成第三轮")
        first_round = [row for row in all_rows if int(row.round_no or 1) == 1]
        if not first_round or any(row.status != "CONFIRMED" for row in first_round):
            raise AppException("DATA_CONFLICT", "首次答辩评分尚未全部确认，不能创建二次答辩")

        group = db.scalars(select(GraduationDefenseGroup).where(
            GraduationDefenseGroup.id == int(student.defense_group_id or 0),
            GraduationDefenseGroup.tenant_id == _tid(),
            GraduationDefenseGroup.is_deleted.is_(False),
        ).with_for_update()).first()
        if not group:
            raise AppException("DATA_CONFLICT", "学生未绑定有效答辩组，不能创建二次答辩")

        judges: list[tuple[str, int | None, int | None]] = []
        if group.chair_mentor_id or (group.chair or "").strip():
            judges.append((
                (group.chair or "").strip(),
                int(group.chair_mentor_id) if group.chair_mentor_id else None,
                None,
            ))
        for raw in (group.members_json or []):
            item = identity.normalize_member(raw)
            mentor_id = int(item["mentorId"]) if item.get("mentorId") else None
            expert_id = int(raw.get("expertId")) if isinstance(raw, dict) and raw.get("expertId") else None
            name = item.get("name") or ""
            if name or mentor_id or expert_id:
                judges.append((name, mentor_id, expert_id))

        seen: set[str] = set()
        unique_judges: list[tuple[str, int | None, int | None]] = []
        for name, mentor_id, expert_id in judges:
            if not mentor_id and not expert_id:
                raise AppException(
                    "DATA_CONFLICT",
                    f"评委「{name or '未知'}」未绑定稳定导师/专家身份，不能创建二次答辩",
                )
            identity_key = f"MENTOR:{mentor_id}" if mentor_id else f"EXPERT:{expert_id}"
            if identity_key in seen:
                continue
            seen.add(identity_key)
            unique_judges.append((name, mentor_id, expert_id))
        if not unique_judges:
            raise AppException("DATA_CONFLICT", "无法创建二次答辩：答辩组没有有效评委")

        pending_rows = []
        for name, mentor_id, expert_id in unique_judges:
            row = GraduationDefenseScore(
                tenant_id=_tid(), gd_student_id=student.id,
                defense_group_id=group.id,
                judge_name=name or "评委", judge_mentor_id=mentor_id,
                expert_id=expert_id,
                judge_identity=f"MENTOR:{mentor_id}" if mentor_id else f"EXPERT:{expert_id}",
                round_no=2, status="PENDING", score=None, absent=False,
            )
            db.add(row)
            pending_rows.append(row)
        db.flush()
        for row in pending_rows:
            todo.push_defense_score_todo(db, row, student)
        service._audit(db, student.id, "创建二次答辩", reason.strip(), before="1", after="2")
        student.stage = "DEFENSE"
        student.version = int(student.version or 0) + 1
        db.commit()
        return {
            "gdStudentId": str(student.id), "newRound": 2,
            "pendingJudges": [name for name, _, _ in unique_judges],
        }
