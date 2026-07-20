"""学校开户业务关系安装器。

关系候选来自统一师生导入文件的“业务关系”工作表。安装器不创建教学任务、毕设学生、
实习记录或宿舍楼栋，只在这些真实业务对象已经存在且学校确认后写入关系字段。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import func, select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models import (
    AaTeachingTask, DormBuilding, GraduationBatch, GraduationMentor,
    GraduationMentorAssignment, GraduationStudent, InternshipBatch,
    InternshipRecord, SchoolClass, StudentProfile, SystemBusinessRelationBatch,
    SystemBusinessRelationInstallItem, SystemImplementationProject,
    SystemImplementationSection, TeacherStudentScope, User,
)
from app.services import audit_log
from app.services.identity_import_file_service import RELATION_TYPES, get_batch
from app.services.saas_role_templates import role_codes_from_row


_TARGETS = {
    "COUNSELOR_CLASS": ("t_class", "counselor_id", "COUNSELOR", "CLASS"),
    "HEAD_TEACHER_CLASS": ("t_class", "head_teacher_id", "COUNSELOR", "CLASS"),
    "TEACHER_TEACHING_TASK": ("t_aa_teaching_task", "teacher_id", "ACADEMIC_TEACHER", None),
    "GRADUATION_MENTOR_STUDENT": ("t_gd_student", "mentor_id", "GD_MENTOR", "ADVISOR"),
    "INTERNSHIP_ADVISOR_STUDENT": ("t_internship_record", "advisor_user_id", "INTERN_MENTOR", "ADVISOR"),
    "DORM_MANAGER_BUILDING": ("t_affairs_dorm_building", "manager_teacher_key", "DORM_MANAGER", "DORM_BUILDING"),
}


def _tid() -> int:
    value = current_tenant_id()
    if value is None:
        raise AppException("TENANT_NOT_FOUND", "当前请求没有学校租户上下文")
    return int(value)


def _actor(user: dict) -> int | None:
    try:
        return int(user.get("userId") or user.get("id"))
    except (TypeError, ValueError):
        return None


def _hash(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _project(db, project_id: int, tenant_id: int):
    row = db.scalars(select(SystemImplementationProject).where(
        SystemImplementationProject.id == project_id,
        SystemImplementationProject.tenant_id == tenant_id,
        SystemImplementationProject.is_deleted.is_(False))).first()
    if row is None:
        raise AppException("DATA_NOT_FOUND", "实施项目不存在")
    return row


def _batch(db, tenant_id: int, project_id: int, batch_no: str):
    row = db.scalars(select(SystemBusinessRelationBatch).where(
        SystemBusinessRelationBatch.tenant_id == tenant_id,
        SystemBusinessRelationBatch.project_id == project_id,
        SystemBusinessRelationBatch.batch_no == batch_no,
        SystemBusinessRelationBatch.is_deleted.is_(False))).first()
    if row is None:
        raise AppException("DATA_NOT_FOUND", "业务关系批次不存在")
    return row


def _single(rows: list, missing: str, ambiguous: str):
    if not rows:
        return None, missing
    if len(rows) > 1:
        return None, ambiguous
    return rows[0], None


def _user(db, tenant_id: int, login_name: str):
    return db.scalars(select(User).where(
        User.tenant_id == tenant_id, User.login_name == login_name,
        User.is_deleted.is_(False), User.status == "ACTIVE")).first()


def _class(db, tenant_id: int, ref: str):
    rows = db.scalars(select(SchoolClass).where(
        SchoolClass.tenant_id == tenant_id, SchoolClass.is_deleted.is_(False),
        (SchoolClass.class_code == ref) | (SchoolClass.class_name == ref))).all()
    return _single(rows, "班级不存在", "班级编号/名称不唯一")


def _building(db, tenant_id: int, ref: str):
    rows = db.scalars(select(DormBuilding).where(
        DormBuilding.tenant_id == tenant_id, DormBuilding.is_deleted.is_(False),
        (DormBuilding.building_code == ref) | (DormBuilding.building_name == ref))).all()
    return _single(rows, "宿舍楼栋不存在", "楼栋编号/名称不唯一")


def _teaching_task(db, tenant_id: int, ref: str):
    rows = db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.tenant_id == tenant_id, AaTeachingTask.is_deleted.is_(False),
        AaTeachingTask.teaching_class_code == ref, AaTeachingTask.status != "MERGED")).all()
    return _single(rows, "教学班编码不存在", "教学班编码不唯一")


def _student_profile(db, tenant_id: int, student_no: str):
    return db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id, StudentProfile.student_no == student_no,
        StudentProfile.is_deleted.is_(False))).first()


def _graduation_student(db, tenant_id: int, student_no: str, context_ref: str):
    stmt = select(GraduationStudent).where(
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.student_no == student_no,
        GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE")
    if context_ref:
        batch = db.scalars(select(GraduationBatch).where(
            GraduationBatch.tenant_id == tenant_id, GraduationBatch.batch_no == context_ref,
            GraduationBatch.is_deleted.is_(False))).first()
        if batch is None:
            return None, "毕设批次编号不存在"
        stmt = stmt.where(GraduationStudent.batch_id == batch.id)
    return _single(db.scalars(stmt).all(), "毕设学生记录不存在", "同一学号存在多个毕设批次，请填写业务批次编号")


def _internship_record(db, tenant_id: int, student_no: str, context_ref: str):
    profile = _student_profile(db, tenant_id, student_no)
    if profile is None:
        return None, "学号不存在"
    stmt = select(InternshipRecord).where(
        InternshipRecord.tenant_id == tenant_id, InternshipRecord.student_id == profile.id,
        InternshipRecord.is_deleted.is_(False))
    if context_ref:
        batch = db.scalars(select(InternshipBatch).where(
            InternshipBatch.tenant_id == tenant_id, InternshipBatch.batch_no == context_ref,
            InternshipBatch.is_deleted.is_(False))).first()
        if batch is None:
            return None, "实习批次编号不存在"
        stmt = stmt.where(InternshipRecord.batch_id == batch.id)
    return _single(db.scalars(stmt).all(), "实习记录不存在", "同一学号存在多个实习批次，请填写业务批次编号")


def _resolve(db, tenant_id: int, source: dict) -> dict:
    relation_type = str(source.get("relationType") or "").strip().upper()
    subject_ref = str(source.get("subjectRef") or "").strip()
    object_ref = str(source.get("objectRef") or "").strip()
    context_ref = str(source.get("contextRef") or "").strip()
    key = _hash({"type": relation_type, "subject": subject_ref,
                 "object": object_ref, "context": context_ref})
    result = {
        "candidateId": key, "relationKey": key, "relationType": relation_type,
        "relationName": RELATION_TYPES.get(relation_type, relation_type),
        "subjectRef": subject_ref, "objectRef": object_ref, "contextRef": context_ref,
        "sourceRows": [int(source.get("_rowNo") or 0)], "remark": str(source.get("remark") or ""),
        "status": "BLOCKED", "issues": [], "targetTable": "", "targetId": "",
        "subjectName": "", "objectName": "", "current": {},
    }
    if relation_type not in _TARGETS:
        result["issues"].append("不支持的关系类型")
        result["recommendation"] = {"action": "IGNORE", "reason": "关系类型无效"}
        return result
    if not subject_ref or not object_ref:
        result["issues"].append("主体工号和对象编号/学号均为必填")
        result["recommendation"] = {"action": "IGNORE", "reason": "必填引用缺失"}
        return result
    subject = _user(db, tenant_id, subject_ref)
    if subject is None or subject.user_type not in {"TEACHER", "STAFF"}:
        result["issues"].append("主体教师账号不存在或未启用")
        result["recommendation"] = {"action": "IGNORE", "reason": "教师账号未就绪"}
        return result
    result["subjectId"] = str(subject.id)
    result["subjectName"] = subject.real_name

    target = None; error = None; current_value = None; current_name = ""
    table, field, _role, _scope = _TARGETS[relation_type]
    if relation_type in {"COUNSELOR_CLASS", "HEAD_TEACHER_CLASS"}:
        target, error = _class(db, tenant_id, object_ref)
        if target:
            current_value = getattr(target, field); result["objectName"] = target.class_name
    elif relation_type == "TEACHER_TEACHING_TASK":
        target, error = _teaching_task(db, tenant_id, object_ref)
        if target:
            current_value = target.teacher_id; result["objectName"] = target.teaching_class_name or object_ref
    elif relation_type == "DORM_MANAGER_BUILDING":
        target, error = _building(db, tenant_id, object_ref)
        if target:
            current_value = target.manager_teacher_key; result["objectName"] = target.building_name
    elif relation_type == "GRADUATION_MENTOR_STUDENT":
        target, error = _graduation_student(db, tenant_id, object_ref, context_ref)
        mentor = db.scalars(select(GraduationMentor).where(
            GraduationMentor.tenant_id == tenant_id, GraduationMentor.teacher_no == subject_ref,
            GraduationMentor.is_deleted.is_(False))).first()
        if mentor is None:
            error = error or "导师资格库中没有该教师"
        elif mentor.qualification_status != "QUALIFIED":
            error = error or "导师资格尚未审核通过"
        else:
            result["resolvedSubjectBusinessId"] = str(mentor.id)
        if target:
            current_value = target.mentor_id; result["objectName"] = target.name
    elif relation_type == "INTERNSHIP_ADVISOR_STUDENT":
        target, error = _internship_record(db, tenant_id, object_ref, context_ref)
        if target:
            current_value = target.advisor_user_id
            profile = _student_profile(db, tenant_id, object_ref)
            result["objectName"] = profile.real_name if profile else object_ref

    if error or target is None:
        result["issues"].append(error or "业务对象不存在")
        result["recommendation"] = {"action": "IGNORE", "reason": result["issues"][0]}
        return result
    result["targetTable"] = table; result["targetId"] = str(target.id)
    desired = (subject_ref if relation_type == "DORM_MANAGER_BUILDING" else
               int(result.get("resolvedSubjectBusinessId") or subject.id))
    if current_value in (None, ""):
        status, action, reason = "READY", "INSTALL", "目标关系为空，可安全安装"
    elif str(current_value) == str(desired):
        status, action, reason = "ALREADY", "KEEP", "真实业务主表已是该关系"
    else:
        current_user = db.get(User, int(current_value)) if isinstance(current_value, int) and relation_type != "GRADUATION_MENTOR_STUDENT" else None
        if relation_type == "GRADUATION_MENTOR_STUDENT" and current_value:
            current_mentor = db.get(GraduationMentor, int(current_value)); current_name = current_mentor.teacher_name if current_mentor else ""
        elif current_user:
            current_name = current_user.real_name
        else:
            current_name = str(current_value)
        status, action, reason = "CONFLICT", "REVIEW", "目标已有其他负责人，必须明确覆盖或忽略"
    result["status"] = status
    result["current"] = {"value": current_value, "name": current_name}
    result["desired"] = {"value": desired, "name": subject.real_name}
    result["stateHash"] = _hash({"target": target.id, "current": current_value})
    result["recommendation"] = {"action": action, "reason": reason}
    return result


def _derived_relations(entry: dict) -> list[dict]:
    rows = list(entry.get("relationships") or [])
    existing = {(str(x.get("relationType")), str(x.get("subjectRef")), str(x.get("objectRef"))) for x in rows}
    for teacher in entry.get("payload", {}).get("teachers") or []:
        try:
            roles = role_codes_from_row(teacher)
        except AppException:
            continue
        scope_type = str(teacher.get("scopeType") or "").upper()
        scope_ref = str(teacher.get("scopeRef") or "").strip()
        relation_type = None
        if "COUNSELOR" in roles and scope_type == "CLASS":
            relation_type = "COUNSELOR_CLASS"
        elif "DORM_MANAGER" in roles and scope_type == "DORM_BUILDING":
            relation_type = "DORM_MANAGER_BUILDING"
        key = (relation_type, str(teacher.get("loginName") or ""), scope_ref)
        if relation_type and scope_ref and key not in existing:
            rows.append({"_rowNo": int(teacher.get("_rowNo") or 0), "relationType": relation_type,
                         "subjectRef": key[1], "objectRef": scope_ref, "contextRef": "",
                         "remark": "由教师角色与数据范围自动推导"})
            existing.add(key)
    return rows


def discover(user: dict, project_id: int, import_batch_no: str) -> dict:
    tenant_id = _tid()
    entry = get_batch(user, tenant_id, import_batch_no)
    if not entry.get("identityConfirmed"):
        raise AppException("DATA_CONFLICT", "请先确认创建师生账号，再生成业务关系候选")
    if entry.get("relationErrors"):
        raise AppException("VALIDATION_ERROR", "业务关系工作表存在格式错误", {"errors": entry["relationErrors"]})
    sources = _derived_relations(entry)
    if not sources:
        raise AppException("VALIDATION_ERROR", "导入文件没有可安装的业务关系")
    db = get_sessionmaker()()
    try:
        project = _project(db, project_id, tenant_id)
        existing = db.scalars(select(SystemBusinessRelationBatch).where(
            SystemBusinessRelationBatch.tenant_id == tenant_id,
            SystemBusinessRelationBatch.project_id == project_id,
            SystemBusinessRelationBatch.source_import_batch_no == import_batch_no,
            SystemBusinessRelationBatch.source_hash == entry["fileSha256"],
            SystemBusinessRelationBatch.is_deleted.is_(False))).first()
        if existing:
            return _batch_row(existing, project.version)
        candidates_by_key = {}
        for source in sources:
            candidate = _resolve(db, tenant_id, source)
            old = candidates_by_key.get(candidate["relationKey"])
            if old:
                old["sourceRows"] = sorted(set(old["sourceRows"] + candidate["sourceRows"]))
            else:
                candidates_by_key[candidate["relationKey"]] = candidate
        candidates = list(candidates_by_key.values())
        by_target = {}
        for candidate in candidates:
            if candidate["targetId"]:
                by_target.setdefault((candidate["relationType"], candidate["targetId"]), []).append(candidate)
        for group in by_target.values():
            if len({x["subjectRef"] for x in group}) > 1:
                for candidate in group:
                    candidate["status"] = "BLOCKED"
                    candidate["issues"].append("同一目标在文件中指定了多个负责人")
                    candidate["recommendation"] = {"action": "IGNORE", "reason": "文件内关系冲突"}
        now = datetime.utcnow()
        row = SystemBusinessRelationBatch(
            tenant_id=tenant_id, batch_no=f"REL{now:%Y%m%d%H%M%S}{entry['fileSha256'][:6].upper()}",
            project_id=project_id, source_import_batch_no=import_batch_no,
            source_hash=entry["fileSha256"], status="DISCOVERED", candidates_json=candidates,
            decisions_json=[], summary_json=_summary(candidates), created_by=_actor(user), updated_by=_actor(user))
        db.add(row); project.version += 1; project.updated_by = _actor(user); db.commit(); db.refresh(row)
        audit_log.record("IMPLEMENTATION_RELATIONS_DISCOVERED", f"relation-batch:{row.batch_no}",
                         {"projectId": project_id, **row.summary_json})
        return _batch_row(row, project.version)
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def _summary(candidates: list[dict]) -> dict:
    return {"total": len(candidates), "ready": sum(x["status"] == "READY" for x in candidates),
            "already": sum(x["status"] == "ALREADY" for x in candidates),
            "conflicts": sum(x["status"] == "CONFLICT" for x in candidates),
            "blocked": sum(x["status"] == "BLOCKED" for x in candidates)}


def _batch_row(row, project_version: int) -> dict:
    return {"batchNo": row.batch_no, "sourceImportBatchNo": row.source_import_batch_no,
            "status": row.status, "summary": row.summary_json, "candidates": row.candidates_json,
            "decisions": row.decisions_json, "projectVersion": project_version,
            "appliedAt": str(row.applied_at or "")[:19], "rolledBackAt": str(row.rolled_back_at or "")[:19]}


def confirm(user: dict, project_id: int, body: dict) -> dict:
    tenant_id = _tid(); batch_no = str(body.get("batchNo") or "").strip()
    supplied = {str(x.get("candidateId") or ""): str(x.get("action") or "").upper()
                for x in body.get("decisions") or []}
    db = get_sessionmaker()()
    try:
        project = _project(db, project_id, tenant_id)
        if body.get("projectVersion") is not None and int(body["projectVersion"]) != project.version:
            raise AppException("DATA_CONFLICT", "项目版本已变化，请刷新")
        row = _batch(db, tenant_id, project_id, batch_no)
        if row.status in {"CONFIRMED", "APPLIED"}:
            return _batch_row(row, project.version)
        decisions = []
        for candidate in row.candidates_json or []:
            action = supplied.get(candidate["candidateId"])
            if not action and body.get("acceptRecommendations"):
                action = candidate["recommendation"]["action"]
            allowed = {"IGNORE"}
            if candidate["status"] == "READY": allowed |= {"INSTALL"}
            elif candidate["status"] == "ALREADY": allowed |= {"KEEP"}
            elif candidate["status"] == "CONFLICT": allowed |= {"REPLACE"}
            if action not in allowed:
                raise AppException("VALIDATION_ERROR", f"关系 {candidate['relationName']}（来源行 {candidate['sourceRows']}）尚未作出有效决定")
            decisions.append({"candidateId": candidate["candidateId"], "action": action,
                              "stateHash": candidate.get("stateHash") or ""})
        row.decisions_json = decisions; row.status = "CONFIRMED"; row.confirmed_at = datetime.utcnow()
        row.version += 1; row.updated_by = _actor(user); project.version += 1; project.updated_by = _actor(user)
        db.commit(); audit_log.record("IMPLEMENTATION_RELATIONS_CONFIRMED", f"relation-batch:{batch_no}",
                                      {"projectId": project_id, "decisions": len(decisions)})
        return _batch_row(row, project.version)
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def _ensure_scope(db, tenant_id: int, candidate: dict, role_code: str, scope_type: str | None,
                  actor: int | None) -> tuple[int | None, bool]:
    if not scope_type:
        return None, False
    ref = None
    if scope_type in {"CLASS", "DORM_BUILDING"}:
        ref = candidate["objectName"]
    row = db.scalars(select(TeacherStudentScope).where(
        TeacherStudentScope.tenant_id == tenant_id,
        TeacherStudentScope.teacher_key == candidate["subjectRef"],
        TeacherStudentScope.role_code == role_code,
        TeacherStudentScope.scope_type == scope_type,
        TeacherStudentScope.ref_value == ref)).first()
    if row:
        if row.is_deleted or row.status != "ACTIVE":
            row.is_deleted = False; row.status = "ACTIVE"; row.version += 1; row.updated_by = actor
        return row.id, False
    row = TeacherStudentScope(tenant_id=tenant_id, teacher_key=candidate["subjectRef"],
        teacher_name=candidate["subjectName"], role_code=role_code, scope_type=scope_type,
        ref_value=ref, status="ACTIVE", created_by=actor, updated_by=actor)
    db.add(row); db.flush()
    return row.id, True


def _recount_mentor(db, tenant_id: int, mentor_id: int | None) -> None:
    if not mentor_id:
        return
    mentor = db.scalars(select(GraduationMentor).where(
        GraduationMentor.id == mentor_id, GraduationMentor.tenant_id == tenant_id)).first()
    if mentor:
        mentor.current_count = int(db.scalar(select(func.count(GraduationStudent.id)).where(
            GraduationStudent.tenant_id == tenant_id, GraduationStudent.mentor_id == mentor_id,
            GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE")) or 0)


def _apply_one(db, tenant_id: int, project_id: int, row, candidate: dict, actor: int | None):
    relation_type = candidate["relationType"]
    table, field, role_code, scope_type = _TARGETS[relation_type]
    subject = _user(db, tenant_id, candidate["subjectRef"])
    if subject is None:
        raise AppException("DATA_CONFLICT", f"教师账号已不存在：{candidate['subjectRef']}")
    before = {}; after = {}; target = None
    if relation_type in {"COUNSELOR_CLASS", "HEAD_TEACHER_CLASS"}:
        target, error = _class(db, tenant_id, candidate["objectRef"])
        if error: raise AppException("DATA_CONFLICT", error)
        before[field] = getattr(target, field); setattr(target, field, subject.id); after[field] = subject.id
    elif relation_type == "TEACHER_TEACHING_TASK":
        target, error = _teaching_task(db, tenant_id, candidate["objectRef"])
        if error: raise AppException("DATA_CONFLICT", error)
        before = {"teacher_id": target.teacher_id, "teacher_key": target.teacher_key, "teacher_name": target.teacher_name}
        target.teacher_id = subject.id; target.teacher_key = subject.login_name; target.teacher_name = subject.real_name
        after = {"teacher_id": subject.id, "teacher_key": subject.login_name, "teacher_name": subject.real_name}
    elif relation_type == "DORM_MANAGER_BUILDING":
        target, error = _building(db, tenant_id, candidate["objectRef"])
        if error: raise AppException("DATA_CONFLICT", error)
        before[field] = target.manager_teacher_key; target.manager_teacher_key = subject.login_name
        after[field] = subject.login_name
    elif relation_type == "INTERNSHIP_ADVISOR_STUDENT":
        target, error = _internship_record(db, tenant_id, candidate["objectRef"], candidate["contextRef"])
        if error: raise AppException("DATA_CONFLICT", error)
        before = {"advisor_user_id": target.advisor_user_id, "advisor_name": target.advisor_name}
        target.advisor_user_id = subject.id; target.advisor_name = subject.real_name
        after = {"advisor_user_id": subject.id, "advisor_name": subject.real_name}
    else:
        target, error = _graduation_student(db, tenant_id, candidate["objectRef"], candidate["contextRef"])
        if error: raise AppException("DATA_CONFLICT", error)
        mentor = db.scalars(select(GraduationMentor).where(
            GraduationMentor.tenant_id == tenant_id, GraduationMentor.teacher_no == subject.login_name,
            GraduationMentor.qualification_status == "QUALIFIED", GraduationMentor.is_deleted.is_(False))).first()
        if mentor is None: raise AppException("DATA_CONFLICT", "导师资格已变化，请重新预览")
        active = db.scalars(select(GraduationMentorAssignment).where(
            GraduationMentorAssignment.tenant_id == tenant_id,
            GraduationMentorAssignment.gd_student_id == target.id,
            GraduationMentorAssignment.status == "ACTIVE",
            GraduationMentorAssignment.is_deleted.is_(False))).all()
        before = {"mentor_id": target.mentor_id, "advisor_name": target.advisor_name,
                  "active_assignment_ids": [x.id for x in active]}
        previous = target.mentor_id
        for assignment in active:
            assignment.status = "CHANGED"; assignment.ended_at = datetime.utcnow()
        assignment = GraduationMentorAssignment(tenant_id=tenant_id, gd_student_id=target.id,
            mentor_id=mentor.id, previous_mentor_id=previous, assign_source="BATCH",
            assign_reason="学校开户业务关系预设安装", status="ACTIVE", assigned_by=str(actor or ""),
            assigned_at=datetime.utcnow(), created_by=actor, updated_by=actor)
        db.add(assignment); db.flush()
        target.mentor_id = mentor.id; target.advisor_name = mentor.teacher_name
        after = {"mentor_id": mentor.id, "advisor_name": mentor.teacher_name,
                 "assignment_id": assignment.id}
        _recount_mentor(db, tenant_id, previous); _recount_mentor(db, tenant_id, mentor.id)
    target.version += 1; target.updated_by = actor
    scope_id, scope_created = _ensure_scope(db, tenant_id, candidate, role_code, scope_type, actor)
    after["scope_id"] = scope_id; after["scope_created"] = scope_created
    return table, target.id, before, after


def apply(user: dict, project_id: int, body: dict) -> dict:
    if str(body.get("confirmText") or "").strip() != "确认安装业务关系":
        raise AppException("VALIDATION_ERROR", "请输入“确认安装业务关系”")
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 2: raise AppException("VALIDATION_ERROR", "请填写安装原因")
    tenant_id = _tid(); batch_no = str(body.get("batchNo") or "").strip(); actor = _actor(user)
    db = get_sessionmaker()()
    try:
        project = _project(db, project_id, tenant_id)
        if body.get("projectVersion") is not None and int(body["projectVersion"]) != project.version:
            raise AppException("DATA_CONFLICT", "项目版本已变化，请刷新后再回滚")
        row = _batch(db, tenant_id, project_id, batch_no)
        if body.get("projectVersion") is not None and int(body["projectVersion"]) != project.version:
            raise AppException("DATA_CONFLICT", "项目版本已变化，请刷新")
        if row.status == "APPLIED":
            return {**_batch_row(row, project.version), "idempotent": True}
        if row.status != "CONFIRMED": raise AppException("DATA_CONFLICT", "业务关系候选尚未确认")
        candidates = {x["candidateId"]: x for x in row.candidates_json or []}
        installed = kept = ignored = 0
        for decision in row.decisions_json or []:
            action = decision["action"]; candidate = candidates[decision["candidateId"]]
            if action == "IGNORE": ignored += 1; continue
            if action == "KEEP": kept += 1; continue
            live = _resolve(db, tenant_id, candidate)
            if not live.get("targetId") or live["targetId"] != candidate["targetId"]:
                raise AppException("DATA_CONFLICT", f"关系目标已变化：{candidate['relationName']} {candidate['objectRef']}")
            if live.get("stateHash") != decision.get("stateHash"):
                raise AppException("DATA_CONFLICT", f"关系已被他人修改，请重新生成候选：{candidate['objectRef']}")
            old_ledger = db.scalars(select(SystemBusinessRelationInstallItem).where(
                SystemBusinessRelationInstallItem.tenant_id == tenant_id,
                SystemBusinessRelationInstallItem.project_id == project_id,
                SystemBusinessRelationInstallItem.relation_key == candidate["relationKey"],
                SystemBusinessRelationInstallItem.is_deleted.is_(False))).first()
            if old_ledger and old_ledger.status == "APPLIED":
                kept += 1; continue
            table, target_id, before, after = _apply_one(db, tenant_id, project_id, row, candidate, actor)
            ledger = old_ledger or SystemBusinessRelationInstallItem(
                tenant_id=tenant_id, project_id=project_id, relation_batch_id=row.id,
                relation_key=candidate["relationKey"], relation_type=candidate["relationType"],
                subject_ref=candidate["subjectRef"], object_ref=candidate["objectRef"],
                context_ref=candidate["contextRef"] or None, target_table=table, target_row_id=target_id,
                created_by=actor, updated_by=actor)
            ledger.relation_batch_id = row.id; ledger.before_json = before; ledger.after_json = after
            ledger.status = "APPLIED"; ledger.applied_at = datetime.utcnow(); ledger.rolled_back_at = None
            ledger.rollback_reason = None; ledger.updated_by = actor
            if not old_ledger: db.add(ledger)
            installed += 1
        row.status = "APPLIED"; row.applied_at = datetime.utcnow()
        row.summary_json = {**(row.summary_json or {}), "installed": installed, "kept": kept, "ignored": ignored}
        row.version += 1; row.updated_by = actor
        section = db.scalars(select(SystemImplementationSection).where(
            SystemImplementationSection.tenant_id == tenant_id,
            SystemImplementationSection.project_id == project_id,
            SystemImplementationSection.section_code == "business_relation",
            SystemImplementationSection.is_deleted.is_(False))).first()
        if section:
            config = dict(section.config_json or {}); config["lastInstalledBatchNo"] = row.batch_no
            config["installedSummary"] = row.summary_json; section.config_json = config
            section.status = "APPLIED"; section.version += 1; section.updated_by = actor
        project.version += 1; project.updated_by = actor; db.commit()
        audit_log.record("IMPLEMENTATION_RELATIONS_APPLIED", f"relation-batch:{batch_no}",
                         {"projectId": project_id, "installed": installed, "kept": kept,
                          "ignored": ignored, "reason": reason})
        return {**_batch_row(row, project.version), "idempotent": False}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def list_batches(project_id: int) -> list[dict]:
    tenant_id = _tid(); db = get_sessionmaker()()
    try:
        project = _project(db, project_id, tenant_id)
        rows = db.scalars(select(SystemBusinessRelationBatch).where(
            SystemBusinessRelationBatch.tenant_id == tenant_id,
            SystemBusinessRelationBatch.project_id == project_id,
            SystemBusinessRelationBatch.is_deleted.is_(False)).order_by(
                SystemBusinessRelationBatch.id.desc())).all()
        return [_batch_row(x, project.version) for x in rows]
    finally:
        db.close()


def rollback(user: dict, project_id: int, batch_no: str, body: dict) -> dict:
    if str(body.get("confirmText") or "").strip() != "确认回滚业务关系":
        raise AppException("VALIDATION_ERROR", "请输入“确认回滚业务关系”")
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 2: raise AppException("VALIDATION_ERROR", "请填写回滚原因")
    tenant_id = _tid(); actor = _actor(user); db = get_sessionmaker()()
    try:
        project = _project(db, project_id, tenant_id); row = _batch(db, tenant_id, project_id, batch_no)
        if row.status == "ROLLED_BACK": return {**_batch_row(row, project.version), "idempotent": True}
        if row.status != "APPLIED": raise AppException("DATA_CONFLICT", "只有已安装的业务关系批次可以回滚")
        items = db.scalars(select(SystemBusinessRelationInstallItem).where(
            SystemBusinessRelationInstallItem.tenant_id == tenant_id,
            SystemBusinessRelationInstallItem.relation_batch_id == row.id,
            SystemBusinessRelationInstallItem.status == "APPLIED",
            SystemBusinessRelationInstallItem.is_deleted.is_(False)).order_by(
                SystemBusinessRelationInstallItem.id.desc())).all()
        # 先做漂移检查，保证整批回滚不会覆盖安装后的人工作业。
        targets = []
        for item in items:
            model = {"t_class": SchoolClass, "t_aa_teaching_task": AaTeachingTask,
                     "t_gd_student": GraduationStudent, "t_internship_record": InternshipRecord,
                     "t_affairs_dorm_building": DormBuilding}[item.target_table]
            target = db.scalars(select(model).where(model.id == item.target_row_id,
                model.tenant_id == tenant_id, model.is_deleted.is_(False))).first()
            if target is None: raise AppException("DATA_CONFLICT", f"关系目标已删除，不能自动回滚：{item.object_ref}")
            for field, expected in (item.after_json or {}).items():
                if field in {"scope_id", "scope_created", "assignment_id"}: continue
                if getattr(target, field) != expected:
                    raise AppException("DATA_CONFLICT", f"关系安装后已被修改，不能覆盖回滚：{item.object_ref}")
            targets.append((item, target))
        for item, target in targets:
            before, after = item.before_json or {}, item.after_json or {}
            for field, value in before.items():
                if field == "active_assignment_ids": continue
                setattr(target, field, value)
            if item.relation_type == "GRADUATION_MENTOR_STUDENT":
                assignment_id = after.get("assignment_id")
                assignment = db.get(GraduationMentorAssignment, int(assignment_id)) if assignment_id else None
                if assignment:
                    assignment.status = "CANCELLED"; assignment.ended_at = datetime.utcnow()
                for old_id in before.get("active_assignment_ids") or []:
                    old = db.get(GraduationMentorAssignment, int(old_id))
                    if old: old.status = "ACTIVE"; old.ended_at = None
                _recount_mentor(db, tenant_id, before.get("mentor_id")); _recount_mentor(db, tenant_id, after.get("mentor_id"))
            if after.get("scope_created") and after.get("scope_id"):
                scope = db.get(TeacherStudentScope, int(after["scope_id"]))
                if scope and not scope.is_deleted:
                    scope.is_deleted = True; scope.status = "DISABLED"; scope.version += 1; scope.updated_by = actor
            target.version += 1; target.updated_by = actor
            item.status = "ROLLED_BACK"; item.rolled_back_at = datetime.utcnow()
            item.rollback_reason = reason; item.version += 1; item.updated_by = actor
        row.status = "ROLLED_BACK"; row.rolled_back_at = datetime.utcnow(); row.version += 1; row.updated_by = actor
        project.version += 1; project.updated_by = actor; db.commit()
        audit_log.record("IMPLEMENTATION_RELATIONS_ROLLED_BACK", f"relation-batch:{batch_no}",
                         {"projectId": project_id, "items": len(items), "reason": reason})
        return {**_batch_row(row, project.version), "idempotent": False}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
