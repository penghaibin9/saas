"""专业分流统一公开入口。

学生志愿相关入口只使用当前账号的稳定学生主档绑定；管理端批次、分配、调剂和确认
继续复用既有状态机。Stage C1 起正式 confirm 不再调用旧服务里的 Profile direct-write，
而是在整批事务中追加 StudentAcademicFact 并同步当前 Profile 投影。
"""
from __future__ import annotations

import importlib
import json
from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found

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


def _normalize_choice_ids(choices):
    """兼容结构化志愿与旧数字 ID；非法输入必须返回业务校验错误而不是 500。"""
    choice_ids = []
    for value in choices or []:
        raw = value
        if isinstance(value, dict):
            raw = value.get("majorId") or value.get("optionId") or value.get("id")
        try:
            choice_id = int(raw)
        except (TypeError, ValueError):
            raise _legacy._bad("志愿专业格式无效")
        if choice_id <= 0:
            raise _legacy._bad("志愿专业格式无效")
        choice_ids.append(choice_id)
    return choice_ids


def _mobile_page(value, page_size, *, label):
    if isinstance(value, bool) or isinstance(page_size, bool):
        raise AppException("VALIDATION_ERROR", f"{label}页码格式不正确")
    try:
        page = int(value)
        size = int(page_size)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", f"{label}页码格式不正确") from exc
    if page < 1 or page > 100000 or size < 1 or size > 50:
        raise AppException("VALIDATION_ERROR", f"{label}每页最多50条")
    return page, size


def _positive_id(value, *, label):
    if isinstance(value, bool):
        raise _legacy._bad(f"{label}格式无效")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise _legacy._bad(f"{label}格式无效") from exc
    if result <= 0:
        raise _legacy._bad(f"{label}格式无效")
    return result


def _locked_batch(db, batch_id):
    from app.models import AaMajorSplitBatch

    batch_id = _positive_id(batch_id, label="分流批次")
    batch = db.query(AaMajorSplitBatch).filter(
        AaMajorSplitBatch.id == batch_id,
        AaMajorSplitBatch.tenant_id == _legacy._tid(),
        AaMajorSplitBatch.is_deleted.is_(False),
    ).with_for_update().first()
    if not batch:
        raise not_found("分流批次不存在")
    return batch


def _student_status_label(status):
    return {
        "PENDING": "志愿已提交，等待学校分流",
        "ALLOCATED": "已分配专业，等待学校确认",
        "UNALLOCATED": "暂未分配，等待学校调剂",
        "CONFIRMED": "分流已生效",
    }.get(str(status or "").upper(), "状态待学校核对")


def submit_volunteer(user, batch_id, choices) -> dict:
    """学生提交/修改志愿；本人身份来自账号稳定绑定，不信任 token 学号。"""
    from app.models import AaMajorSplitOption, AaMajorSplitVolunteer, StudentProfile

    with _legacy.session() as db:
        # 截止和学生提交竞争同一批次行锁。旧页面即使在截止瞬间点击，提交也会在
        # 拿到锁后重新核验 OPEN，而不是写出“已截止批次的新志愿”。
        batch = _locked_batch(db, batch_id)
        if batch.status != "OPEN":
            raise _legacy._invalid("不在志愿填报时间内")
        profile = _student_profile(db, user)
        profile = db.query(StudentProfile).filter(
            StudentProfile.id == profile.id,
            StudentProfile.tenant_id == _legacy._tid(),
            StudentProfile.is_deleted.is_(False),
        ).with_for_update().first()
        if not profile:
            raise not_found("当前账号尚未绑定唯一学生档案")
        if (profile.grade or "") != batch.grade:
            raise _legacy._bad(f"本批次面向 {batch.grade} 级，当前学籍年级不符")
        if batch.source_major_id and int(profile.major_id or 0) != int(batch.source_major_id):
            raise _legacy._bad("不在本批次分流的大类专业范围内")
        if profile.student_status != "NORMAL":
            raise _legacy.no_data_scope("当前学籍状态不可填报分流志愿")

        choice_ids = _normalize_choice_ids(choices)
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
            previous_choices = json.loads(volunteer.choices_json) if volunteer.choices_json else []
            # 相同命令的双击/网络重试只回读已有业务单，不再次写入或重复留下审计。
            if volunteer.status == "PENDING" and previous_choices == choice_ids:
                return _legacy._v_dto(volunteer)
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


def close_batch(user, batch_id) -> dict:
    """截止志愿与学生提交使用同一批次锁，避免旧页绕过状态机。"""
    with _legacy.session() as db:
        _legacy._require_school(user, db)
        batch = _locked_batch(db, batch_id)
        if batch.status != "OPEN":
            raise _legacy._invalid("仅开放中的批次可截止")
        batch.status = "CLOSED"
        _legacy._audit(db, batch.id, "SPLIT_CLOSE", "志愿截止")
        db.commit()
        return _legacy._b_dto(batch)


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


def student_open_batches_page(user, page=1, page_size=20):
    """学生移动端仅取当前页批次元数据；可选专业改由独立有界接口读取。"""
    from app.models import AaMajorSplitBatch, AaMajorSplitVolunteer

    page, page_size = _mobile_page(page, page_size, label="分流批次")
    with _legacy.session() as db:
        profile = _student_profile(db, user)
        conditions = [
            AaMajorSplitBatch.tenant_id == _legacy._tid(),
            AaMajorSplitBatch.status == "OPEN",
            AaMajorSplitBatch.grade == (profile.grade or ""),
            AaMajorSplitBatch.is_deleted.is_(False),
        ]
        if profile.major_id:
            conditions.append(or_(
                AaMajorSplitBatch.source_major_id.is_(None),
                AaMajorSplitBatch.source_major_id == int(profile.major_id),
            ))
        else:
            conditions.append(AaMajorSplitBatch.source_major_id.is_(None))
        total = int(db.scalar(select(func.count()).select_from(AaMajorSplitBatch).where(*conditions)) or 0)
        rows = db.scalars(
            select(AaMajorSplitBatch).where(*conditions).order_by(AaMajorSplitBatch.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        batch_ids = {int(row.id) for row in rows}
        volunteers = {
            int(row.batch_id): row for row in db.scalars(select(AaMajorSplitVolunteer).where(
                AaMajorSplitVolunteer.tenant_id == _legacy._tid(),
                AaMajorSplitVolunteer.student_id == profile.id,
                AaMajorSplitVolunteer.batch_id.in_(batch_ids),
                AaMajorSplitVolunteer.is_deleted.is_(False),
            )).all()
        } if batch_ids else {}
        output = []
        for row in rows:
            item = _legacy._b_dto(row)
            volunteer = volunteers.get(int(row.id))
            if volunteer:
                mine = _legacy._v_dto(volunteer)
                mine["statusLabel"] = _student_status_label(volunteer.status)
                item["myVolunteer"] = mine
            else:
                item["myVolunteer"] = None
            output.append(item)
        return output, total


def student_options_page(user, batch_id, page=1, page_size=20, keyword=None):
    """当前学生可填报批次的专业选项，服务端搜索和分页。"""
    from app.models import AaMajorSplitBatch, AaMajorSplitOption

    page, page_size = _mobile_page(page, page_size, label="可选专业")
    search = str(keyword or "").strip()
    with _legacy.session() as db:
        profile = _student_profile(db, user)
        batch_id = _positive_id(batch_id, label="分流批次")
        batch = db.scalars(select(AaMajorSplitBatch).where(
            AaMajorSplitBatch.id == batch_id,
            AaMajorSplitBatch.tenant_id == _legacy._tid(),
            AaMajorSplitBatch.is_deleted.is_(False),
        )).first()
        if not batch:
            raise not_found("分流批次不存在")
        if batch.status != "OPEN":
            raise _legacy._invalid("该分流批次已截止，不能继续填写志愿")
        if (profile.grade or "") != (batch.grade or "") or (
            batch.source_major_id and int(profile.major_id or 0) != int(batch.source_major_id)
        ):
            raise _legacy.no_data_scope("无权查看该分流批次")
        conditions = [
            AaMajorSplitOption.tenant_id == _legacy._tid(),
            AaMajorSplitOption.batch_id == batch.id,
            AaMajorSplitOption.is_deleted.is_(False),
        ]
        if search:
            conditions.append(AaMajorSplitOption.major_name.contains(search, autoescape=True))
        total = int(db.scalar(select(func.count()).select_from(AaMajorSplitOption).where(*conditions)) or 0)
        rows = db.scalars(
            select(AaMajorSplitOption).where(*conditions).order_by(AaMajorSplitOption.id.asc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        return [{
            "optionId": str(option.id), "majorId": str(option.major_id),
            "majorName": option.major_name or "专业名称待学校核对",
            "capacity": option.capacity,
            "remain": max(0, int(option.capacity or 0) - int(option.allocated_count or 0)),
        } for option in rows], total


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


def my_volunteer_page(user, page=1, page_size=20):
    """本人志愿历史分页并批量补齐批次、专业名称，不能依赖当前开放批次。"""
    from app.models import AaMajorSplitBatch, AaMajorSplitVolunteer, Major

    page, page_size = _mobile_page(page, page_size, label="我的志愿")
    with _legacy.session() as db:
        profile = _student_profile(db, user)
        conditions = [
            AaMajorSplitVolunteer.tenant_id == _legacy._tid(),
            AaMajorSplitVolunteer.student_id == profile.id,
            AaMajorSplitVolunteer.is_deleted.is_(False),
        ]
        total = int(db.scalar(select(func.count()).select_from(AaMajorSplitVolunteer).where(*conditions)) or 0)
        rows = db.scalars(
            select(AaMajorSplitVolunteer).where(*conditions).order_by(AaMajorSplitVolunteer.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        batch_ids = {int(row.batch_id) for row in rows}
        batches = {
            int(row.id): row for row in db.scalars(select(AaMajorSplitBatch).where(
                AaMajorSplitBatch.tenant_id == _legacy._tid(),
                AaMajorSplitBatch.id.in_(batch_ids),
                AaMajorSplitBatch.is_deleted.is_(False),
            )).all()
        } if batch_ids else {}
        choice_ids = set()
        decoded = {}
        for row in rows:
            choices = json.loads(row.choices_json) if row.choices_json else []
            decoded[int(row.id)] = choices
            choice_ids.update(int(value) for value in choices if str(value).isdigit())
            if row.result_major_id:
                choice_ids.add(int(row.result_major_id))
        current_names = {
            int(row.id): (row.major_name or "专业名称待学校核对")
            for row in db.scalars(select(Major).where(
                Major.tenant_id == _legacy._tid(), Major.id.in_(choice_ids),
                Major.is_deleted.is_(False),
            )).all()
        } if choice_ids else {}
        from app.models import AaMajorSplitOption
        option_names = {
            (int(row.batch_id), int(row.major_id)): (row.major_name or "专业名称待学校核对")
            for row in db.scalars(select(AaMajorSplitOption).where(
                AaMajorSplitOption.tenant_id == _legacy._tid(),
                AaMajorSplitOption.batch_id.in_(batch_ids),
                AaMajorSplitOption.major_id.in_(choice_ids),
            )).all()
        } if batch_ids and choice_ids else {}

        def _name(batch_id, major_id):
            return option_names.get((int(batch_id), int(major_id))) or current_names.get(
                int(major_id), "专业名称待学校核对"
            )

        output = []
        for row in rows:
            item = _legacy._v_dto(row)
            choices = decoded[int(row.id)]
            batch = batches.get(int(row.batch_id))
            item.update({
                "batchName": batch.batch_name if batch else "分流批次名称待学校核对",
                "batchStatus": batch.status if batch else None,
                "choiceNames": [_name(row.batch_id, value) for value in choices],
                "resultMajorName": _name(row.batch_id, row.result_major_id) if row.result_major_id else None,
                "statusLabel": _student_status_label(row.status),
            })
            output.append(item)
        return output, total


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
