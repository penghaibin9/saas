"""Stage C1 formal organization service facade.

Read/config operations delegate to the mature organization service. Student class
adjustment is overridden so class/major/college changes append StudentAcademicFact.
"""
from __future__ import annotations

import importlib
import hashlib
import json

from sqlalchemy import select

from app.core.exceptions import AppException, not_found

_legacy = importlib.import_module(".academic_affairs_org_service", package=__package__)


def __getattr__(name):
    return getattr(_legacy, name)


_EXITED = {"GRADUATED", "WITHDRAWN", "TRANSFER_SCHOOL", "COMPLETED", "INCOMPLETE", "MERGED", "RECYCLED"}


def _prepare_transfer(db, user, body):
    """Read current scope/impact under locks; callers own commit or read rollback."""
    from app.models import College, Major, SchoolClass, StudentProfile
    from .academic_affairs_status_service import STATUSES

    try:
        student_id = int(getattr(body, "studentId", 0))
        target_id = int(getattr(body, "targetClassId", 0))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "学生与目标班级参数非法")
    if student_id <= 0 or target_id <= 0:
        raise AppException("VALIDATION_ERROR", "学生与目标班级必填")
    ctx = _legacy._ctx(user, db)
    initial = db.scalar(select(StudentProfile).where(StudentProfile.id == student_id,
        StudentProfile.tenant_id == _legacy._tid(), StudentProfile.is_deleted.is_(False)))
    if not initial:
        raise not_found("学生不存在")
    initial_org = (initial.class_id, initial.major_id, initial.college_id)
    class_ids = {value for value in (initial.class_id, target_id) if value}
    # Match the batch adjustment lock order: classes, parents, then members.
    classes = {row.id: row for row in db.scalars(select(SchoolClass).where(
        SchoolClass.tenant_id == _legacy._tid(), SchoolClass.id.in_(sorted(class_ids)))
        .order_by(SchoolClass.id).with_for_update()).all()}
    target = classes.get(target_id)
    if not target or target.is_deleted:
        raise not_found("目标班级不存在")
    major_ids = {row.major_id for row in classes.values() if row.major_id} | ({initial.major_id} if initial.major_id else set())
    majors = {row.id: row for row in db.scalars(select(Major).where(Major.tenant_id == _legacy._tid(),
        Major.id.in_(sorted(major_ids))).order_by(Major.id).with_for_update()).all()}
    college_ids = {row.college_id for row in majors.values() if row.college_id} | ({initial.college_id} if initial.college_id else set())
    colleges = {row.id: row for row in db.scalars(select(College).where(College.tenant_id == _legacy._tid(),
        College.id.in_(sorted(college_ids))).order_by(College.id).with_for_update()).all()}
    target_major = majors.get(target.major_id)
    target_college = colleges.get(target_major.college_id) if target_major else None
    _legacy._require_college_write(ctx, db, target_college.id if target_college else None)
    source = classes.get(initial.class_id)
    source_major_ids = {value for value in (initial.major_id, source.major_id if source else None) if value}
    source_colleges = {majors[mid].college_id for mid in source_major_ids if mid in majors and majors[mid].college_id}
    if initial.college_id:
        source_colleges.add(initial.college_id)
    if not source_colleges:
        _legacy._require_college_write(ctx, db, None)  # Only a school-wide operator can complete unknown ownership.
    for college_id in source_colleges:
        _legacy._require_college_write(ctx, db, college_id)
    if target.status != "ACTIVE" or target.class_status != "NORMAL":
        raise AppException("VALIDATION_ERROR", "目标班级已停用或毕业，请选择在读班级")
    if not target_major or target_major.is_deleted or target_major.status != "ACTIVE" or not target_college or target_college.is_deleted or target_college.status != "ACTIVE":
        raise AppException("VALIDATION_ERROR", "目标班级所属专业或学院不可用，请先处理组织信息")

    student = db.scalar(select(StudentProfile).where(StudentProfile.id == student_id,
        StudentProfile.tenant_id == _legacy._tid(), StudentProfile.is_deleted.is_(False))
        .execution_options(populate_existing=True).with_for_update())
    if not student:
        raise not_found("学生不存在")
    if (student.class_id, student.major_id, student.college_id) != initial_org:
        raise AppException("DATA_CONFLICT", "学生归属已变化，请刷新名册后重新核对")
    expected = getattr(body, "expectedVersion", None)
    if expected is not None and int(student.version or 0) != expected:
        raise AppException("DATA_CONFLICT", "学生资料已变化，请刷新后重新核对")
    expected_target = getattr(body, "expectedTargetVersion", None)
    if expected_target is not None and int(target.version or 0) != expected_target:
        raise AppException("DATA_CONFLICT", "目标班级已变化，请重新核对")
    if student.student_status in _EXITED or student.student_status not in STATUSES or student.status != "ACTIVE":
        raise AppException("VALIDATION_ERROR", "学生当前学籍不可办理普通转班，请先核对学籍状态")
    if student.class_id == target.id:
        raise AppException("DATA_CONFLICT", "学生已在目标班级，请刷新名册")
    from .academic_affairs_student_fact_service import resolve_student_academic_fact
    fact = resolve_student_academic_fact(db, student.id, for_update=True)
    fields = ('student_status', 'college_id', 'major_id', 'class_id', 'grade')
    if any(getattr(fact, key) != getattr(student, key) for key in fields):
        raise AppException("DATA_CONFLICT", "当前学籍记录与学生资料不一致，请先完成学籍核对")
    members = db.execute(select(StudentProfile.id, StudentProfile.student_status).where(
        StudentProfile.tenant_id == _legacy._tid(), StudentProfile.class_id == target.id,
        StudentProfile.is_deleted.is_(False)).order_by(StudentProfile.id).with_for_update()).all()
    count = sum(status not in _EXITED for _, status in members)
    warnings = []
    if target.capacity is not None and count + 1 > target.capacity:
        warnings.append(f"转入后在籍人数为{count + 1}人，超过编制{target.capacity}人，请确认班级安排。")
    if student.major_id and student.major_id != target.major_id:
        warnings.append("本次同时变更学生所属专业，请按现有培养方案衔接结果继续复核课程与学分。")
    if student.grade and target.grade and student.grade != target.grade:
        warnings.append(f"目标班级年级为{target.grade}，本次保留学生原年级{student.grade}；年级变更请通过学籍异动办理。")
    snapshot = [student.id, int(student.version or 0), student.student_status, student.grade, initial_org, count,
        [[row.id, row.version, row.major_id, row.class_status, row.status, row.is_deleted, row.capacity, row.grade] for row in classes.values()],
        [[row.id, row.version, row.college_id, row.status, row.is_deleted] for row in majors.values()],
        [[row.id, row.version, row.status, row.is_deleted] for row in colleges.values()]]
    fingerprint = hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    if getattr(body, 'expectedSnapshotHash', None) and body.expectedSnapshotHash != fingerprint:
        raise AppException("DATA_CONFLICT", "班级人数或组织信息已变化，请重新核对转班影响")
    return student, target, {
        "student": {"id": str(student.id), "studentNo": student.student_no, "name": student.real_name,
                    "version": int(student.version or 0), "studentStatus": student.student_status, "grade": student.grade},
        "fromClassId": str(student.class_id) if student.class_id else None,
        "fromClassName": source.class_name if source else None,
        "target": {"id": str(target.id), "className": target.class_name, "majorName": target_major.major_name,
                   "collegeId": str(target_college.id), "collegeName": target_college.college_name,
                   "version": int(target.version or 0), "capacity": target.capacity,
                   "studentCount": count, "afterStudentCount": count + 1},
        "snapshotHash": fingerprint, "warnings": warnings,
    }


def preview_student_class_adjustment(user, body) -> dict:
    with _legacy.session() as db:
        _, _, result = _prepare_transfer(db, user, body)
        return result


def adjust_student_class(user, body) -> dict:
    from app.core.context import get_current_user_ctx
    from app.models import User
    from .academic_affairs_student_fact_service import append_student_academic_fact

    reason = (getattr(body, 'reason', None) or '').strip()
    if getattr(body, 'reason', None) is not None and not 5 <= len(reason) <= 500:
        raise AppException("VALIDATION_ERROR", "调整原因需为5至500个字符")
    with _legacy.session() as db:
        student, target, checked = _prepare_transfer(db, user, body)
        old_class = student.class_id
        actor = {**(user or {}), **(get_current_user_ctx() or {})}
        actor_id = str(actor.get('userId') or '')
        created_by = int(actor_id) if actor_id.isdigit() else db.scalar(select(User.id).where(
            User.tenant_id == _legacy._tid(), User.login_name == (actor.get('loginName') or ''),
            User.is_deleted.is_(False)))
        fact, projected = append_student_academic_fact(
            db,
            int(student.id),
            college_id=int(checked['target']['collegeId']),
            major_id=target.major_id,
            class_id=target.id,
            source_type="CLASS_ADJUST",
            source_ref_id=int(target.id),
            expected_student_version=int(student.version or 0),
            created_by=created_by,
        )
        _legacy._audit(
            db,
            "AA_ORG_CLASS_ADJUST",
            projected.id,
            "ADJUST_CLASS",
            f"{projected.real_name}：{checked['fromClassName'] or '未分班'} → {target.class_name}；{reason or '教务班级归属调整'}",
            before=str(old_class or ""),
            after=str(target.id),
        )
        db.commit()
        return {
            "studentId": str(student.id), "studentName": student.real_name,
            "fromClassId": str(old_class) if old_class else None,
            "fromClassName": checked['fromClassName'],
            "toClassId": str(target.id),
            "toClassName": target.class_name, "studentVersion": int(projected.version or 0),
            "effectiveAt": fact.valid_from.isoformat(), "reason": reason,
            "warnings": checked['warnings'],
            "academicFactVersion": int(fact.version_no),
        }
