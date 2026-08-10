"""专业分流统一公开入口。

学生志愿相关入口只使用当前账号的稳定学生主档绑定；管理端批次、分配、调剂和确认
继续复用既有状态机。Stage C1 起正式 confirm 不再调用旧服务里的 Profile direct-write，
而是在整批事务中追加 StudentAcademicFact 并同步当前 Profile 投影。
"""
from __future__ import annotations

import importlib
import json
from datetime import datetime

from app.core.context import get_current_user_ctx
from app.core.exceptions import not_found

_legacy = importlib.import_module(
    ".academic_affairs_major_split_service",
    package=__package__,
)


def __getattr__(name):
    return getattr(_legacy, name)


def _student_profile(db, user=None):
    from app.services.mobile_student_identity_facade import resolve_student

    profile = resolve_student(db, user or get_current_user_ctx() or {})
    if not profile:
        raise not_found("当前账号尚未绑定唯一学生档案")
    return profile


def submit_volunteer(user, batch_id, choices) -> dict:
    """学生提交/修改志愿；本人身份来自账号稳定绑定，不信任 token 学号。"""
    from app.models import AaMajorSplitOption, AaMajorSplitVolunteer

    with _legacy.session() as db:
        batch = _legacy._get_batch(db, batch_id)
        if batch.status != "OPEN":
            raise _legacy._invalid("不在志愿填报时间内")
        profile = _student_profile(db, user)
        if (profile.grade or "") != batch.grade:
            raise _legacy._bad(f"本批次面向 {batch.grade} 级，当前学籍年级不符")
        if batch.source_major_id and int(profile.major_id or 0) != int(batch.source_major_id):
            raise _legacy._bad("不在本批次分流的大类专业范围内")
        if profile.student_status != "NORMAL":
            raise _legacy.no_data_scope("当前学籍状态不可填报分流志愿")

        choice_ids = [int(value) for value in (choices or [])]
        if not choice_ids:
            raise _legacy._bad("至少填报一个志愿")
        if len(choice_ids) > batch.max_choices:
            raise _legacy._bad(f"志愿数不得超过 {batch.max_choices} 个")
        if len(set(choice_ids)) != len(choice_ids):
            raise _legacy._bad("志愿不得重复")

        valid_ids = {
            int(option.major_id)
            for option in db.query(AaMajorSplitOption).filter(
                AaMajorSplitOption.tenant_id == _legacy._tid(),
                AaMajorSplitOption.batch_id == batch.id,
                AaMajorSplitOption.is_deleted.is_(False),
            ).all()
        }
        if any(value not in valid_ids for value in choice_ids):
            raise _legacy._bad("志愿中包含不在可选列表的专业")

        volunteer = db.query(AaMajorSplitVolunteer).filter(
            AaMajorSplitVolunteer.tenant_id == _legacy._tid(),
            AaMajorSplitVolunteer.batch_id == batch.id,
            AaMajorSplitVolunteer.student_id == profile.id,
            AaMajorSplitVolunteer.is_deleted.is_(False),
        ).with_for_update().first()
        if volunteer:
            volunteer.choices_json = json.dumps(choice_ids)
            volunteer.status = "PENDING"
            volunteer.result_major_id = None
            volunteer.result_choice_rank = None
            volunteer.adjust_reason = None
        else:
            volunteer = AaMajorSplitVolunteer(
                tenant_id=_legacy._tid(),
                batch_id=batch.id,
                student_id=profile.id,
                student_no=profile.student_no,
                student_name=profile.real_name,
                choices_json=json.dumps(choice_ids),
                status="PENDING",
            )
            db.add(volunteer)
        db.flush()
        _legacy._audit(
            db,
            batch.id,
            "SPLIT_VOLUNTEER_SUBMIT",
            f"studentId={profile.id};studentNo={profile.student_no};choices={choice_ids}",
        )
        db.commit()
        return _legacy._v_dto(volunteer)


def student_open_batches(user):
    """返回与本人年级和源专业匹配的开放批次。"""
    from app.models import AaMajorSplitBatch, AaMajorSplitOption

    with _legacy.session() as db:
        profile = _student_profile(db, user)
        batches = db.query(AaMajorSplitBatch).filter(
            AaMajorSplitBatch.tenant_id == _legacy._tid(),
            AaMajorSplitBatch.status == "OPEN",
            AaMajorSplitBatch.grade == (profile.grade or ""),
            AaMajorSplitBatch.is_deleted.is_(False),
        ).all()
        output = []
        for batch in batches:
            if batch.source_major_id and int(profile.major_id or 0) != int(batch.source_major_id):
                continue
            options = db.query(AaMajorSplitOption).filter(
                AaMajorSplitOption.tenant_id == _legacy._tid(),
                AaMajorSplitOption.batch_id == batch.id,
                AaMajorSplitOption.is_deleted.is_(False),
            ).order_by(AaMajorSplitOption.id).all()
            item = _legacy._b_dto(batch)
            item["options"] = [
                {
                    "majorId": str(option.major_id),
                    "majorName": option.major_name,
                    "capacity": option.capacity,
                    "remain": max(0, option.capacity - option.allocated_count),
                }
                for option in options
            ]
            output.append(item)
        return output


def my_volunteer(user, batch_id=None):
    from app.models import AaMajorSplitVolunteer

    with _legacy.session() as db:
        profile = _student_profile(db, user)
        query = db.query(AaMajorSplitVolunteer).filter(
            AaMajorSplitVolunteer.tenant_id == _legacy._tid(),
            AaMajorSplitVolunteer.student_id == profile.id,
            AaMajorSplitVolunteer.is_deleted.is_(False),
        )
        if batch_id:
            query = query.filter(AaMajorSplitVolunteer.batch_id == int(batch_id))
        rows = query.order_by(AaMajorSplitVolunteer.id.desc()).all()
        return [_legacy._v_dto(row) for row in rows]


def confirm(user, batch_id) -> dict:
    """Stage C1 canonical major-split cutover.

    The whole batch is one transaction. Every student transition shares one effective
    timestamp and goes through ``append_student_academic_fact``. Any stale source major,
    missing fact, overlap or projection drift aborts the *entire* batch so there is no
    partially-applied cohort.
    """
    from app.models import AaMajorSplitBatch, AaMajorSplitVolunteer, Major, StudentProfile
    from app.modules.academic_affairs.services.academic_affairs_student_fact_service import (
        append_student_academic_fact,
    )

    with _legacy.session() as db:
        _legacy._require_school(user, db)
        batch = db.query(AaMajorSplitBatch).filter(
            AaMajorSplitBatch.id == int(batch_id),
            AaMajorSplitBatch.tenant_id == _legacy._tid(),
            AaMajorSplitBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("分流批次不存在")
        if batch.status != "ALLOCATED":
            raise _legacy._invalid("仅已分配批次可确认")

        unallocated = db.query(AaMajorSplitVolunteer).filter(
            AaMajorSplitVolunteer.tenant_id == _legacy._tid(),
            AaMajorSplitVolunteer.batch_id == batch.id,
            AaMajorSplitVolunteer.status == "UNALLOCATED",
            AaMajorSplitVolunteer.is_deleted.is_(False),
        ).count()
        if unallocated:
            raise _legacy._invalid(f"尚有 {unallocated} 名学生未分配到专业，请先人工调剂后再确认")

        volunteers = db.query(AaMajorSplitVolunteer).filter(
            AaMajorSplitVolunteer.tenant_id == _legacy._tid(),
            AaMajorSplitVolunteer.batch_id == batch.id,
            AaMajorSplitVolunteer.status == "ALLOCATED",
            AaMajorSplitVolunteer.is_deleted.is_(False),
        ).order_by(AaMajorSplitVolunteer.student_id).with_for_update().all()
        if not volunteers:
            raise _legacy._invalid("没有可确认的已分配学生")

        effective_at = datetime.utcnow()
        confirmed = 0
        classes_created = 0
        for volunteer in volunteers:
            profile = db.query(StudentProfile).filter(
                StudentProfile.id == int(volunteer.student_id),
                StudentProfile.tenant_id == _legacy._tid(),
                StudentProfile.is_deleted.is_(False),
            ).with_for_update().first()
            if not profile:
                raise _legacy._invalid(f"学生 {volunteer.student_no} 主档不存在，整批确认已取消")
            if batch.source_major_id and int(profile.major_id or 0) != int(batch.source_major_id):
                raise _legacy._invalid(
                    f"学生 {volunteer.student_no} 当前专业已变化，整批确认已取消，请重新分配"
                )
            if batch.grade and (profile.grade or "") != batch.grade:
                raise _legacy._invalid(
                    f"学生 {volunteer.student_no} 当前年级已变化，整批确认已取消，请重新核对"
                )
            if not volunteer.result_major_id:
                raise _legacy._invalid(f"学生 {volunteer.student_no} 缺少分流目标专业")

            target_major_id = int(volunteer.result_major_id)
            major = db.query(Major).filter(
                Major.id == target_major_id,
                Major.tenant_id == _legacy._tid(),
                Major.is_deleted.is_(False),
            ).first()
            if not major:
                raise _legacy._invalid(f"学生 {volunteer.student_no} 的目标专业已失效，整批确认已取消")

            old_major, old_class = profile.major_id, profile.class_id
            target_class_id, created = _legacy._resolve_split_class(
                db, target_major_id, batch.grade or profile.grade, major
            )
            if created:
                classes_created += 1

            _fact, projected = append_student_academic_fact(
                db,
                int(profile.id),
                effective_at=effective_at,
                college_id=(major.college_id if major.college_id else profile.college_id),
                major_id=target_major_id,
                class_id=target_class_id,
                source_type="MAJOR_SPLIT",
                source_ref_id=int(batch.id),
                source_quality="EXACT",
                expected_student_version=int(profile.version or 0),
            )
            volunteer.status = "CONFIRMED"
            confirmed += 1
            _legacy._audit(
                db,
                batch.id,
                "SPLIT_APPLY_STUDENT",
                f"{volunteer.student_no} 专业 {old_major}→{projected.major_id} "
                f"班级 {old_class}→{projected.class_id} "
                f"（第{volunteer.result_choice_rank or '调剂'}志愿，绩点{volunteer.gpa_snapshot}，"
                f"academicFactVersion={_fact.version_no}）",
            )

        batch.status = "CONFIRMED"
        _legacy._audit(
            db,
            batch.id,
            "SPLIT_CONFIRM",
            f"分流生效 {confirmed} 人，新建班级 {classes_created}，effectiveAt={effective_at.isoformat()}",
        )
        db.commit()
        return {
            "batchId": str(batch.id),
            "confirmed": confirmed,
            "classesCreated": classes_created,
            "status": batch.status,
            "effectiveAt": effective_at.isoformat(),
        }
