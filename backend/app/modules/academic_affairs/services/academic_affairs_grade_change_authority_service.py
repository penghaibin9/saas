"""Read/freeze existing grade prerequisites; never create a roster or policy."""
import json

from sqlalchemy import select

from app.core.exceptions import AppException
from app.models import AaCourse, AaTeachingClass, AaTeachingClassMember, AaTeachingClassRosterVersion, AaTerm
from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy
from app.services.db_service import _tid
from . import academic_affairs_roster_consumer_service as rosters
from . import academic_affairs_effective_grade_policy_service as policies
from .academic_affairs_effective_grade_policy_compat import select_chronological_policy
from .academic_affairs_grade_change_component_service import digest


def conflict(message):
    return AppException("DATA_CONFLICT", message, http_status=409)


def source(db, task, record, *, lock=False):
    if lock:
        # GradeTask/record are already owned; policy authority precedes term/class locks.
        policies.lock_policy_authority(db)

    def rows(model, *conditions):
        query = select(model).where(model.tenant_id == _tid(), model.is_deleted.is_(False), *conditions).order_by(model.id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return db.scalars(query).all()

    terms = rows(AaTerm, AaTerm.id == (task.term_id or 0))
    if not terms or terms[0].status == "ARCHIVED":
        raise conflict("更正学期不存在或已封存")
    courses = rows(AaCourse, AaCourse.id == (task.course_id or 0))
    if not courses or not courses[0].course_code or not courses[0].version:
        raise conflict("更正任务缺少正式课程版本")
    course = courses[0]
    classes = rows(AaTeachingClass, AaTeachingClass.teaching_task_id == (task.teaching_task_id or 0))
    if len(classes) != 1:
        raise conflict("成绩教学任务缺少唯一正式教学班")
    teaching_class = classes[0]
    snapshots = rosters._consumer_rows(db, "GRADE_TASK", int(task.id), lock=lock)
    snapshot = rosters._active_row(snapshots)
    versions = rows(AaTeachingClassRosterVersion, AaTeachingClassRosterVersion.id == (teaching_class.current_roster_version_id or 0))
    version = versions[0] if versions else None
    members = rows(AaTeachingClassMember, AaTeachingClassMember.roster_version_id == (version.id if version else 0),
                   AaTeachingClassMember.status == "ACTIVE")
    ids = sorted({int(row.student_id) for row in members})
    current = bool(snapshot and version and teaching_class.status == "ACTIVE" and version.status == "LOCKED"
                   and teaching_class.term_id == task.term_id and teaching_class.course_id == task.course_id
                   and version.teaching_class_id == teaching_class.id
                   and version.roster_hash == rosters.roster_hash(ids) and version.member_count == len(ids)
                   and rosters._matches(snapshot, int(task.teaching_task_id), {
                       "teachingClassId": teaching_class.id, "rosterVersionId": version.id,
                       "rosterVersionNo": version.version_no, "rosterHash": version.roster_hash,
                       "memberCount": version.member_count, "studentIds": ids,
                   }))
    resolved = rosters.teaching_class_service.resolve_teaching_task_roster(db, int(task.teaching_task_id)) if task.teaching_task_id else {}
    if (not current or not resolved.get("ready") or int(resolved.get("rosterVersionId") or 0) != version.id
            or rosters._ids(resolved.get("studentIds")) != ids or record.student_id not in ids):
        raise conflict("申请学生不在当前冻结正式名单，或来源名单已换版/失效")
    active = rows(AaEffectiveGradePolicy, AaEffectiveGradePolicy.status == "ACTIVE")
    term_ids = sorted({int(p.effective_from_term_id) for p in active if p.effective_from_term_id} | {int(task.term_id)})
    policy_terms = {term.id: term for term in rows(AaTerm, AaTerm.id.in_(term_ids))}
    policy = select_chronological_policy(active, policy_terms, task.term_id)
    return {"gradeTaskId": str(task.id), "gradeRecordId": str(record.id), "studentId": str(record.student_id),
            "termId": str(task.term_id), "courseId": str(course.id), "courseCode": course.course_code,
            "courseVersion": int(course.version), "credit": str(task.credit) if task.credit is not None else None,
            "usualRatio": task.usual_ratio, "midtermRatio": task.midterm_ratio, "finalRatio": task.final_ratio,
            "passLine": task.pass_line, "snapshotId": str(snapshot.id), "snapshotVersion": int(snapshot.snapshot_version),
            "teachingClassId": str(teaching_class.id), "rosterVersionId": str(version.id),
            "rosterVersionNo": int(version.version_no), "rosterHash": version.roster_hash,
            "policy": policies._policy_dto(policy)}


def validate(db, task, record, request, *, lock=False):
    try:
        frozen = json.loads(request.authority_snapshot_json)
        if not isinstance(frozen, dict) or digest(frozen) != request.authority_snapshot_hash:
            raise ValueError()
    except (TypeError, ValueError):
        raise conflict("申请缺少完整的名单与策略冻结证据，请驳回后重新申请")
    current = source(db, task, record, lock=lock)
    if frozen != current:
        raise conflict("申请后的正式名单、课程或生效策略已变化，请重新核对后申请")
    return current


def projection(db, task, record, request=None):
    try:
        facts = validate(db, task, record, request) if request is not None else source(db, task, record)
        return {"authorityEvidence": facts, "authorityEvidenceHash": digest(facts), "authorityProblems": []}
    except AppException as error:
        return {"authorityEvidence": None, "authorityEvidenceHash": None, "authorityProblems": [error.message]}
