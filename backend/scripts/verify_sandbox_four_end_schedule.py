"""Verify the active sandbox schedule through the shared four-end projections."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.context import set_current_user, set_tenant
from app.core.tenant_identity import SANDBOX_SCHOOL
from app.db.session import get_sessionmaker
from app.models import (
    AaScheduleBatch,
    AaScheduleItem,
    AaScheduleScopeHead,
    AaTerm,
    StudentAccountLink,
    StudentProfile,
    Tenant,
    User,
)
from app.modules.academic_affairs.services import mobile_academic_affairs_service


def main() -> None:
    tenant_id = int(SANDBOX_SCHOOL.tenant_id)
    set_tenant({
        "tenantId": str(tenant_id),
        "tenantCode": SANDBOX_SCHOOL.tenant_code,
        "tenantName": "体验沙箱学校",
        "status": "ACTIVE",
    })

    with get_sessionmaker()() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id))
        if tenant is None or tenant.tenant_code != SANDBOX_SCHOOL.tenant_code:
            raise RuntimeError("拒绝执行：当前数据库不是 sandbox-school")
        head = db.scalar(
            select(AaScheduleScopeHead)
            .join(
                AaTerm,
                (AaTerm.id == AaScheduleScopeHead.term_id)
                & (AaTerm.tenant_id == AaScheduleScopeHead.tenant_id),
            )
            .where(
                AaScheduleScopeHead.tenant_id == tenant_id,
                AaScheduleScopeHead.active_batch_id.is_not(None),
                AaScheduleScopeHead.is_deleted.is_(False),
                AaTerm.is_current.is_(True),
                AaTerm.is_deleted.is_(False),
            )
            .order_by(AaScheduleScopeHead.id.desc())
            .limit(1)
        )
        if head is None:
            raise RuntimeError("当前学期没有正式课表范围头")
        batch = db.scalar(select(AaScheduleBatch).where(
            AaScheduleBatch.id == int(head.active_batch_id),
            AaScheduleBatch.tenant_id == tenant_id,
            AaScheduleBatch.status == "PUBLISHED",
            AaScheduleBatch.is_deleted.is_(False),
        ))
        if batch is None:
            raise RuntimeError("范围头未指向有效 PUBLISHED 课表")

        teacher_pair = db.execute(
            select(User, AaScheduleItem)
            .join(
                AaScheduleItem,
                (AaScheduleItem.tenant_id == User.tenant_id)
                & (AaScheduleItem.teacher_key == User.login_name),
            )
            .where(
                User.tenant_id == tenant_id,
                User.status == "ACTIVE",
                User.is_deleted.is_(False),
                AaScheduleItem.batch_id == int(batch.id),
                AaScheduleItem.status == "EFFECTIVE",
                AaScheduleItem.is_deleted.is_(False),
            )
            .order_by(AaScheduleItem.id)
            .limit(1)
        ).first()
        if teacher_pair is None:
            raise RuntimeError("正式课表没有可回链的教师账号")
        teacher, teacher_seed_item = teacher_pair

        student_row = db.execute(
            select(StudentProfile, StudentAccountLink, User, AaScheduleItem)
            .join(
                AaScheduleItem,
                (AaScheduleItem.tenant_id == StudentProfile.tenant_id)
                & (AaScheduleItem.class_id == StudentProfile.class_id),
            )
            .join(
                StudentAccountLink,
                (StudentAccountLink.tenant_id == StudentProfile.tenant_id)
                & (StudentAccountLink.student_id == StudentProfile.id),
            )
            .join(
                User,
                (User.tenant_id == StudentAccountLink.tenant_id)
                & (User.id == StudentAccountLink.user_id),
            )
            .where(
                StudentProfile.tenant_id == tenant_id,
                StudentProfile.is_deleted.is_(False),
                StudentAccountLink.link_status == "ACTIVE",
                StudentAccountLink.is_deleted.is_(False),
                User.status == "ACTIVE",
                User.is_deleted.is_(False),
                AaScheduleItem.batch_id == int(batch.id),
                AaScheduleItem.status == "EFFECTIVE",
                AaScheduleItem.is_deleted.is_(False),
            )
            .order_by(AaScheduleItem.id, StudentProfile.id)
            .limit(1)
        ).first()
        if student_row is None:
            raise RuntimeError("正式课表没有可回链的学生账号")
        student, _link, student_user_row, student_seed_item = student_row

    teacher_user = {
        "userId": f"db-{teacher.id}",
        "loginName": teacher.login_name,
        "realName": teacher.real_name,
        "userType": "TEACHER",
        "currentRoleCode": "ACADEMIC_TEACHER",
    }
    set_current_user(teacher_user)
    teacher_projection = mobile_academic_affairs_service.teacher_schedule_my(teacher_user)

    student_user = {
        "userId": f"db-{student_user_row.id}",
        "loginName": student_user_row.login_name,
        "realName": student.real_name,
        "userType": "STUDENT",
        "currentRoleCode": "STUDENT",
        "studentId": str(student.id),
        "studentNo": student.student_no,
    }
    set_current_user(student_user)
    student_projection = mobile_academic_affairs_service.schedule_my(student_user)

    teacher_items = teacher_projection.get("items") or []
    student_items = student_projection.get("items") or []
    teacher_batch_ids = sorted({
        str(item.get("activeBatchId") or "")
        for item in teacher_items
        if item.get("activeBatchId")
    })
    output = {
        "activeBatchId": str(batch.id),
        "activeBatchStatus": batch.status,
        "teacherPCAndMiniapp": {
            "sharedProjection": "mobile_academic_affairs_service.teacher_schedule_my",
            "loginName": teacher.login_name,
            "seedScheduleItemId": str(teacher_seed_item.id),
            "activeBatchIds": teacher_batch_ids,
            "itemCount": len(teacher_items),
            "todayItemCount": len(teacher_projection.get("todayItems") or []),
            "hasData": bool(teacher_items),
        },
        "studentPCAndMiniapp": {
            "sharedProjection": "mobile_academic_affairs_service.schedule_my",
            "studentNo": student.student_no,
            "seedScheduleItemId": str(student_seed_item.id),
            "batchId": str(student_projection.get("batchId") or ""),
            "itemCount": len(student_items),
            "todayItemCount": len(student_projection.get("todayItems") or []),
            "hasData": bool(student_items),
        },
    }
    if teacher_batch_ids != [str(batch.id)]:
        raise RuntimeError("教师四端投影未切到新正式课表")
    if output["studentPCAndMiniapp"]["batchId"] != str(batch.id):
        raise RuntimeError("学生四端投影未切到新正式课表")
    if not teacher_items or not student_items:
        raise RuntimeError("四端正式课表投影为空")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
