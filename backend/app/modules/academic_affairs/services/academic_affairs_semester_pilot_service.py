"""R11 真实学校完整学期试点控制台。

六阶段证据：
BASELINE 基础数据 → PRE_TERM 开学准备 → IN_TERM 教学运行 → EXAM 考务 →
GRADE 成绩 → ARCHIVE 学期归档。

本服务不生成学生、课程、任务、考勤、考试或成绩数据；只读取当前租户真实事实并冻结检查证据。
只有生产部署、关闭 mock 登录、明确确认真实数据，且六阶段全部通过后，才能显式标记 COMPLETED。
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime

from sqlalchemy import func, select

from app.core.config import settings
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.services.db_service import _tid, session

_STAGE_ORDER = (
    ("BASELINE", "基础数据"),
    ("PRE_TERM", "开学准备"),
    ("IN_TERM", "教学运行"),
    ("EXAM", "考务运行"),
    ("GRADE", "成绩闭环"),
    ("ARCHIVE", "学期归档"),
)
_ADMIN_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN"}
_ACTIVE_PROGRAM_STATUSES = {"PUBLISHED", "ENABLED", "FROZEN"}
_READY_TASK_STATUSES = {
    "TEACHER_CONFIRMED", "READY", "PUBLISHED", "RUNNING", "COMPLETED", "ARCHIVED",
}
_FINISHED_EXAM_STATUSES = {"PUBLISHED", "FINISHED", "ARCHIVED"}
_FINISHED_GRADE_STATUSES = {"PUBLISHED", "ARCHIVED"}


def _ctx(user=None) -> dict:
    return user or get_current_user_ctx() or {}


def _role(user=None) -> str:
    data = _ctx(user)
    return str(data.get("currentRoleCode") or "").upper()


def _operator(user=None) -> str:
    data = _ctx(user)
    return str(data.get("userId") or data.get("loginName") or data.get("realName") or "")


def _require_admin(user) -> None:
    data = _ctx(user)
    if _role(data) not in _ADMIN_ROLES and str(data.get("userType") or "").upper() != "PLATFORM_SUPER_ADMIN":
        raise no_permission("仅教务处、学校管理员可管理真实学期试点")


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _mock_login_effective() -> bool:
    raw = str(settings.MOCK_LOGIN_ENABLED or "").strip().lower()
    if raw:
        return raw in {"1", "true", "yes", "on"}
    return not settings.is_prod


def _environment_evidence() -> dict:
    production = bool(settings.is_prod and settings.DEPLOYMENT_MODE == "production")
    mock_enabled = _mock_login_effective()
    return {
        "appEnv": settings.APP_ENV,
        "deploymentMode": settings.DEPLOYMENT_MODE,
        "dbEnabled": bool(settings.DB_ENABLED),
        "productionDeployment": production,
        "mockLoginEnabled": mock_enabled,
        "eligibleForRealCompletion": production and bool(settings.DB_ENABLED) and not mock_enabled,
    }


def _audit(db, biz_id, action, detail, user=None) -> None:
    from app.models import AffairsAuditTrail

    data = _ctx(user)
    db.add(AffairsAuditTrail(
        tenant_id=_tid(), biz_type="AA_SEMESTER_PILOT", biz_id=int(biz_id) if biz_id else None,
        action=action, operator=_operator(data), role_name=str(data.get("currentRoleCode") or ""),
        detail=str(detail or "")[:990], occurred_at=datetime.utcnow(),
    ))


def _term(db, term_id):
    from app.models import AaTerm

    row = db.query(AaTerm).filter(
        AaTerm.id == int(term_id), AaTerm.tenant_id == _tid(), AaTerm.is_deleted.is_(False),
    ).first()
    if not row:
        raise not_found("试点学期不存在")
    return row


def _pilot(db, pilot_id, *, lock=False):
    from app.models.academic_affairs_r11 import AaSemesterPilot

    query = db.query(AaSemesterPilot).filter(
        AaSemesterPilot.id == int(pilot_id),
        AaSemesterPilot.tenant_id == _tid(),
        AaSemesterPilot.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    row = query.first()
    if not row:
        raise not_found("学期试点不存在")
    return row


def _stage(code, name, *, evidence, blockers=None, warnings=None) -> dict:
    blocker_items = [str(item) for item in (blockers or []) if str(item).strip()]
    warning_items = [str(item) for item in (warnings or []) if str(item).strip()]
    passed = not blocker_items
    conclusion = (
        f"{name}证据通过"
        if passed else f"{name}存在 {len(blocker_items)} 个阻断项"
    )
    payload = {
        "stageCode": code,
        "stageName": name,
        "passed": passed,
        "blockerCount": len(blocker_items),
        "warningCount": len(warning_items),
        "blockers": blocker_items,
        "warnings": warning_items,
        "evidence": evidence,
        "conclusion": conclusion,
    }
    payload["evidenceHash"] = _hash(payload)
    return payload


def _baseline_stage(pilot, user) -> dict:
    from app.models import AaProgram, AaProgramBinding, SchoolClass, StudentProfile

    with session() as db:
        term = _term(db, pilot.term_id)
        students = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
        ).count()
        classes = db.query(SchoolClass).filter(
            SchoolClass.tenant_id == _tid(), SchoolClass.class_status == "NORMAL",
            SchoolClass.is_deleted.is_(False),
        ).count()
        programs = db.query(AaProgram).filter(
            AaProgram.tenant_id == _tid(), AaProgram.status.in_(sorted(_ACTIVE_PROGRAM_STATUSES)),
            AaProgram.is_deleted.is_(False),
        ).count()
        bindings = db.query(AaProgramBinding).filter(
            AaProgramBinding.tenant_id == _tid(), AaProgramBinding.status == "ACTIVE",
            AaProgramBinding.is_deleted.is_(False),
        ).count()
        env = _environment_evidence()
        evidence = {
            "termId": str(term.id),
            "termCode": f"{term.year_code}-{term.term_no}",
            "termName": getattr(term, "term_name", None) or "",
            "startDate": str(term.start_date or ""),
            "endDate": str(term.end_date or ""),
            "studentCount": students,
            "normalClassCount": classes,
            "activeProgramCount": programs,
            "activeProgramBindingCount": bindings,
            "realDataConfirmed": bool(pilot.real_data_confirmed),
            "environment": env,
        }
        blockers = []
        if not pilot.real_data_confirmed:
            blockers.append("尚未确认本试点使用真实学校数据")
        if not env["eligibleForRealCompletion"]:
            blockers.append("当前不是关闭mock登录的生产部署，不能认定真实学校试点完成")
        if not term.start_date or not term.end_date:
            blockers.append("正式学期缺少开始或结束日期")
        if students <= 0:
            blockers.append("当前租户没有真实学生主档")
        if classes <= 0:
            blockers.append("当前租户没有正常在用行政班")
        if programs <= 0:
            blockers.append("没有已发布/已启用/已冻结培养方案")
        if bindings <= 0:
            blockers.append("没有生效培养方案绑定")
        return _stage("BASELINE", "基础数据", evidence=evidence, blockers=blockers)


def _pre_term_stage(pilot, user) -> dict:
    from app.models import (
        AaScheduleBatch, AaTeachingClass, AaTeachingClassRosterVersion,
        AaTeachingTask, AaTeachingTaskBatch,
    )
    from app.modules.academic_affairs.services import academic_affairs_program_quality_service as quality

    with session() as db:
        term = _term(db, pilot.term_id)
        batch_ids = [int(value) for (value,) in db.query(AaTeachingTaskBatch.id).filter(
            AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.term_id == term.id,
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).all()]
        tasks = db.query(AaTeachingTask).filter(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id.in_(batch_ids or [-1]),
            AaTeachingTask.status != "MERGED", AaTeachingTask.is_deleted.is_(False),
        ).all()
        task_ids = [int(row.id) for row in tasks]
        teaching_classes = db.query(AaTeachingClass).filter(
            AaTeachingClass.tenant_id == _tid(),
            AaTeachingClass.teaching_task_id.in_(task_ids or [-1]),
            AaTeachingClass.status == "ACTIVE", AaTeachingClass.is_deleted.is_(False),
        ).all()
        current_version_ids = [int(row.current_roster_version_id) for row in teaching_classes if row.current_roster_version_id]
        roster_versions = db.query(AaTeachingClassRosterVersion).filter(
            AaTeachingClassRosterVersion.tenant_id == _tid(),
            AaTeachingClassRosterVersion.id.in_(current_version_ids or [-1]),
            AaTeachingClassRosterVersion.status == "LOCKED",
            AaTeachingClassRosterVersion.is_deleted.is_(False),
        ).count()
        schedule_batches = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.tenant_id == _tid(), AaScheduleBatch.term_id == term.id,
            AaScheduleBatch.status == "PUBLISHED", AaScheduleBatch.is_deleted.is_(False),
        ).count()
        invalid_tasks = [row for row in tasks if str(row.status or "").upper() not in _READY_TASK_STATUSES]

    try:
        opening = quality.opening_differences(user, int(pilot.term_id))
        opening_blockers = int((opening.get("summary") or {}).get("blockerCount") or 0)
        opening_conclusion = (opening.get("summary") or {}).get("conclusion") or ""
    except Exception as exc:
        opening_blockers = 1
        opening_conclusion = f"开课差异检查失败：{str(exc)[:160]}"

    evidence = {
        "teachingTaskBatchCount": len(batch_ids),
        "teachingTaskCount": len(tasks),
        "invalidTeachingTaskCount": len(invalid_tasks),
        "independentTeachingClassCount": len(teaching_classes),
        "lockedCurrentRosterVersionCount": roster_versions,
        "publishedScheduleBatchCount": schedule_batches,
        "openingDifferenceBlockerCount": opening_blockers,
        "openingDifferenceConclusion": opening_conclusion,
    }
    blockers = []
    if not batch_ids:
        blockers.append("本学期没有教学任务批次")
    if not tasks:
        blockers.append("本学期没有真实教学任务")
    if invalid_tasks:
        blockers.append(f"仍有 {len(invalid_tasks)} 条教学任务未进入可执行状态")
    if len(teaching_classes) != len(tasks):
        blockers.append(f"独立教学班 {len(teaching_classes)} 个，与教学任务 {len(tasks)} 条不一致")
    if roster_versions != len(teaching_classes):
        blockers.append(f"仍有 {len(teaching_classes) - roster_versions} 个教学班没有当前锁定名单版本")
    if schedule_batches <= 0:
        blockers.append("本学期没有已发布课表")
    if opening_blockers > 0:
        blockers.append(f"培养方案与开课任务仍有 {opening_blockers} 个阻断差异")
    return _stage("PRE_TERM", "开学准备", evidence=evidence, blockers=blockers)


def _in_term_stage(pilot, user) -> dict:
    from app.models import AaAttendanceSession
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot

    with session() as db:
        term = _term(db, pilot.term_id)
        term_code = f"{term.year_code}-{term.term_no}"
        sessions = db.query(AaAttendanceSession).filter(
            AaAttendanceSession.tenant_id == _tid(), AaAttendanceSession.term_code == term_code,
            AaAttendanceSession.is_deleted.is_(False),
        ).all()
        session_ids = [int(row.id) for row in sessions]
        snapshots = db.query(AaRosterConsumerSnapshot).filter(
            AaRosterConsumerSnapshot.tenant_id == _tid(),
            AaRosterConsumerSnapshot.consumer_type == "ATTENDANCE_SESSION",
            AaRosterConsumerSnapshot.consumer_id.in_(session_ids or [-1]),
            AaRosterConsumerSnapshot.status == "ACTIVE",
            AaRosterConsumerSnapshot.is_deleted.is_(False),
        ).count()
        draft_count = sum(1 for row in sessions if str(row.status or "").upper() == "DRAFT")
        submitted_count = len(sessions) - draft_count
        total_student_events = sum(int(row.total_count or 0) for row in sessions)
        evidence = {
            "attendanceSessionCount": len(sessions),
            "submittedAttendanceSessionCount": submitted_count,
            "draftAttendanceSessionCount": draft_count,
            "attendanceRosterSnapshotCount": snapshots,
            "studentAttendanceEventCount": total_student_events,
        }
        blockers = []
        if not sessions:
            blockers.append("本学期没有真实课堂考勤场次")
        if draft_count > 0:
            blockers.append(f"仍有 {draft_count} 个考勤场次未提交")
        if snapshots != len(sessions):
            blockers.append(f"有 {len(sessions) - snapshots} 个考勤场次未冻结正式名单版本")
        if total_student_events <= 0:
            blockers.append("考勤场次没有真实学生名单事件")
        return _stage("IN_TERM", "教学运行", evidence=evidence, blockers=blockers)


def _exam_stage(pilot, user) -> dict:
    from app.models import AaExamBatch, AaExamCourse, AaExamRoomStudent
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot

    with session() as db:
        batches = db.query(AaExamBatch).filter(
            AaExamBatch.tenant_id == _tid(), AaExamBatch.term_id == int(pilot.term_id),
            AaExamBatch.is_deleted.is_(False),
        ).all()
        batch_ids = [int(row.id) for row in batches]
        courses = db.query(AaExamCourse).filter(
            AaExamCourse.tenant_id == _tid(), AaExamCourse.batch_id.in_(batch_ids or [-1]),
            AaExamCourse.is_deleted.is_(False),
        ).all()
        confirmed = [row for row in courses if row.status == "CONFIRMED"]
        confirmed_ids = [int(row.id) for row in confirmed]
        snapshot_count = db.query(AaRosterConsumerSnapshot).filter(
            AaRosterConsumerSnapshot.tenant_id == _tid(),
            AaRosterConsumerSnapshot.consumer_type == "EXAM_COURSE",
            AaRosterConsumerSnapshot.consumer_id.in_(confirmed_ids or [-1]),
            AaRosterConsumerSnapshot.status == "ACTIVE",
            AaRosterConsumerSnapshot.is_deleted.is_(False),
        ).count()
        seat_count = db.query(AaExamRoomStudent).filter(
            AaExamRoomStudent.tenant_id == _tid(),
            AaExamRoomStudent.exam_course_id.in_(confirmed_ids or [-1]),
            AaExamRoomStudent.is_deleted.is_(False),
        ).count()
        pending_count = sum(1 for row in courses if row.status == "PENDING_CONFIRM")
        finished_batches = sum(1 for row in batches if str(row.status or "").upper() in _FINISHED_EXAM_STATUSES)
        evidence = {
            "examBatchCount": len(batches),
            "publishedOrFinishedExamBatchCount": finished_batches,
            "examCourseCount": len(courses),
            "confirmedExamCourseCount": len(confirmed),
            "pendingExamCourseCount": pending_count,
            "examRosterSnapshotCount": snapshot_count,
            "examSeatCount": seat_count,
        }
        blockers = []
        if not batches:
            blockers.append("本学期没有真实考试批次")
        if finished_batches <= 0:
            blockers.append("没有已发布、已结束或已归档考试批次")
        if not confirmed:
            blockers.append("考试批次没有已确认课程")
        if pending_count > 0:
            blockers.append(f"仍有 {pending_count} 门考试课程待确认")
        if snapshot_count != len(confirmed):
            blockers.append(f"有 {len(confirmed) - snapshot_count} 门考试课程未冻结正式名单版本")
        if seat_count <= 0:
            blockers.append("没有真实考生座位明细")
        return _stage("EXAM", "考务运行", evidence=evidence, blockers=blockers)


def _grade_stage(pilot, user) -> dict:
    from app.models import AaGradeRecord, AaGradeTask, AcademicGrade
    from app.models.academic_affairs_r10 import AaGradeComponentScore, AaGradeSchemeSnapshot
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot

    with session() as db:
        tasks = db.query(AaGradeTask).filter(
            AaGradeTask.tenant_id == _tid(), AaGradeTask.term_id == int(pilot.term_id),
            AaGradeTask.is_deleted.is_(False),
        ).all()
        task_ids = [int(row.id) for row in tasks]
        unfinished = [row for row in tasks if str(row.status or "").upper() not in _FINISHED_GRADE_STATUSES]
        snapshots = db.query(AaRosterConsumerSnapshot).filter(
            AaRosterConsumerSnapshot.tenant_id == _tid(),
            AaRosterConsumerSnapshot.consumer_type == "GRADE_TASK",
            AaRosterConsumerSnapshot.consumer_id.in_(task_ids or [-1]),
            AaRosterConsumerSnapshot.status == "ACTIVE",
            AaRosterConsumerSnapshot.is_deleted.is_(False),
        ).count()
        records = db.query(AaGradeRecord).filter(
            AaGradeRecord.tenant_id == _tid(), AaGradeRecord.task_id.in_(task_ids or [-1]),
            AaGradeRecord.is_deleted.is_(False),
        ).count()
        projected = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == _tid(), AcademicGrade.grade_task_id.in_(task_ids or [-1]),
            AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False),
        ).count()
        dynamic_schemes = db.query(AaGradeSchemeSnapshot).filter(
            AaGradeSchemeSnapshot.tenant_id == _tid(),
            AaGradeSchemeSnapshot.grade_task_id.in_(task_ids or [-1]),
            AaGradeSchemeSnapshot.status == "LOCKED",
            AaGradeSchemeSnapshot.is_deleted.is_(False),
        ).count()
        dynamic_scores = db.query(AaGradeComponentScore).filter(
            AaGradeComponentScore.tenant_id == _tid(),
            AaGradeComponentScore.grade_task_id.in_(task_ids or [-1]),
            AaGradeComponentScore.is_deleted.is_(False),
        ).count()
        evidence = {
            "gradeTaskCount": len(tasks),
            "unfinishedGradeTaskCount": len(unfinished),
            "gradeRosterSnapshotCount": snapshots,
            "gradeRecordCount": records,
            "publishedAcademicGradeCount": projected,
            "lockedDynamicGradeSchemeCount": dynamic_schemes,
            "dynamicGradeComponentScoreCount": dynamic_scores,
        }
        blockers = []
        warnings = []
        if not tasks:
            blockers.append("本学期没有真实成绩任务")
        if unfinished:
            blockers.append(f"仍有 {len(unfinished)} 个成绩任务未发布或归档")
        if snapshots != len(tasks):
            blockers.append(f"有 {len(tasks) - snapshots} 个成绩任务未冻结正式名单版本")
        if records <= 0:
            blockers.append("没有成绩录入明细")
        if projected <= 0:
            blockers.append("没有发布到正式成绩主账的记录")
        if dynamic_schemes <= 0:
            warnings.append("本试点未使用动态成绩项，固定三段成绩链已验证")
        return _stage("GRADE", "成绩闭环", evidence=evidence, blockers=blockers, warnings=warnings)


def _archive_stage(pilot, user) -> dict:
    from app.models import AaArchiveBatch, AaTerm
    from app.models.academic_affairs_r10 import AaStatsSnapshot
    from app.modules.academic_affairs.services import academic_affairs_archive_service as archive

    with session() as db:
        term = _term(db, pilot.term_id)
        term_code = f"{term.year_code}-{term.term_no}"
        domains = archive._evaluate_domains(db, int(term.id), term_code)
        failed_domains = [row for row in domains if not bool(row.get("passed"))]
        archive_batches = db.query(AaArchiveBatch).filter(
            AaArchiveBatch.tenant_id == _tid(), AaArchiveBatch.term_id == term.id,
            AaArchiveBatch.is_deleted.is_(False),
        ).all()
        archived_batches = [row for row in archive_batches if row.status == "ARCHIVED"]
        stats_snapshots = db.query(AaStatsSnapshot).filter(
            AaStatsSnapshot.tenant_id == _tid(), AaStatsSnapshot.term_id == term.id,
            AaStatsSnapshot.status == "FROZEN", AaStatsSnapshot.is_deleted.is_(False),
        ).count()
        evidence = {
            "termStatus": term.status,
            "archiveBatchCount": len(archive_batches),
            "archivedBatchCount": len(archived_batches),
            "archiveDomainChecks": domains,
            "failedArchiveDomainCount": len(failed_domains),
            "frozenStatsSnapshotCount": stats_snapshots,
        }
        blockers = []
        if str(term.status or "").upper() != "ARCHIVED":
            blockers.append("正式学期尚未归档")
        if not archived_batches:
            blockers.append("没有已确认归档的学期归档批次")
        if failed_domains:
            blockers.append(f"归档语义检查仍有 {len(failed_domains)} 个失败域")
        if stats_snapshots <= 0:
            blockers.append("归档前未冻结教务统计快照")
        return _stage("ARCHIVE", "学期归档", evidence=evidence, blockers=blockers)


def _run_stages(pilot, user) -> list[dict]:
    return [
        _baseline_stage(pilot, user),
        _pre_term_stage(pilot, user),
        _in_term_stage(pilot, user),
        _exam_stage(pilot, user),
        _grade_stage(pilot, user),
        _archive_stage(pilot, user),
    ]


def _pilot_row(row) -> dict:
    return {
        "pilotId": str(row.id),
        "termId": str(row.term_id),
        "termCode": row.term_code,
        "pilotName": row.pilot_name,
        "status": row.status,
        "purpose": row.purpose,
        "realDataConfirmed": bool(row.real_data_confirmed),
        "checkRunNo": int(row.check_run_no or 0),
        "passedStageCount": int(row.passed_stage_count or 0),
        "stageCount": len(_STAGE_ORDER),
        "blockerCount": int(row.blocker_count or 0),
        "latestEvidenceHash": row.latest_evidence_hash or "",
        "latestCheckedAt": row.latest_checked_at.isoformat() if row.latest_checked_at else None,
        "completedAt": row.completed_at.isoformat() if row.completed_at else None,
        "completedBy": row.completed_by or "",
        "completionNote": row.completion_note or "",
        "externalSemesterActuallyCompleted": row.status == "COMPLETED",
    }


def create_pilot(user, *, term_id, pilot_name, purpose, real_data_confirmed) -> dict:
    _require_admin(user)
    name = str(pilot_name or "").strip()
    purpose_text = str(purpose or "").strip()
    if len(name) < 3:
        raise AppException("VALIDATION_ERROR", "试点名称不少于3字")
    if len(purpose_text) < 5:
        raise AppException("VALIDATION_ERROR", "试点用途不少于5字")
    if not real_data_confirmed:
        raise AppException("VALIDATION_ERROR", "必须明确确认当前租户使用真实学校数据；测试或mock数据不得创建真实试点")

    from app.models.academic_affairs_r11 import AaSemesterPilot
    with session() as db:
        term = _term(db, term_id)
        existing = db.query(AaSemesterPilot).filter(
            AaSemesterPilot.tenant_id == _tid(), AaSemesterPilot.term_id == term.id,
            AaSemesterPilot.is_deleted.is_(False),
        ).first()
        if existing:
            raise AppException("DATA_CONFLICT", "该学期已存在试点，请进入原试点继续检查", details={"pilotId": str(existing.id)}, http_status=409)
        row = AaSemesterPilot(
            tenant_id=_tid(), term_id=term.id, term_code=f"{term.year_code}-{term.term_no}",
            pilot_name=name, status="PREPARING", purpose=purpose_text,
            real_data_confirmed=True, check_run_no=0, passed_stage_count=0, blocker_count=0,
        )
        db.add(row)
        db.flush()
        _audit(db, row.id, "SEMESTER_PILOT_CREATE", f"term={row.term_code};purpose={purpose_text}", user)
        db.commit()
        db.refresh(row)
        return _pilot_row(row)


def run_check(user, pilot_id) -> dict:
    _require_admin(user)
    with session() as db:
        pilot = _pilot(db, pilot_id)
        if pilot.status in {"COMPLETED", "CANCELLED"}:
            raise AppException("DATA_CONFLICT", "已完成或已取消试点不可重新检查")
        detached = _pilot_row(pilot)
        detached["id"] = int(pilot.id)
        detached["term_id"] = int(pilot.term_id)
        detached["term_code"] = pilot.term_code
        detached["real_data_confirmed"] = bool(pilot.real_data_confirmed)

    proxy = type("PilotEvidence", (), detached)()
    stages = _run_stages(proxy, user)
    checked_at = datetime.utcnow()
    overall_hash = _hash({"pilotId": str(pilot_id), "stages": [{"code": row["stageCode"], "hash": row["evidenceHash"]} for row in stages]})
    passed_count = sum(1 for row in stages if row["passed"])
    blocker_count = sum(int(row["blockerCount"]) for row in stages)

    from app.models.academic_affairs_r11 import AaSemesterPilotCheckpoint
    with session() as db:
        pilot = _pilot(db, pilot_id, lock=True)
        run_no = int(pilot.check_run_no or 0) + 1
        for row in stages:
            db.add(AaSemesterPilotCheckpoint(
                tenant_id=_tid(), pilot_id=pilot.id, run_no=run_no,
                stage_code=row["stageCode"], stage_name=row["stageName"],
                passed=bool(row["passed"]), blocker_count=int(row["blockerCount"]),
                warning_count=int(row["warningCount"]), conclusion=row["conclusion"],
                evidence_json=_canonical(row), evidence_hash=row["evidenceHash"],
                checked_at=checked_at, checked_by=_operator(user),
            ))
        pilot.check_run_no = run_no
        pilot.passed_stage_count = passed_count
        pilot.blocker_count = blocker_count
        pilot.latest_evidence_hash = overall_hash
        pilot.latest_checked_at = checked_at
        if passed_count == len(_STAGE_ORDER):
            pilot.status = "READY_TO_COMPLETE"
        elif not stages[0]["passed"]:
            pilot.status = "BLOCKED"
        else:
            pilot.status = "RUNNING"
        _audit(
            db, pilot.id, "SEMESTER_PILOT_CHECK",
            f"run={run_no};passed={passed_count}/{len(_STAGE_ORDER)};blockers={blocker_count};hash={overall_hash}",
            user,
        )
        db.commit()
        db.refresh(pilot)
        return {**_pilot_row(pilot), "stages": stages, "environment": _environment_evidence()}


def _latest_stages(db, pilot) -> list[dict]:
    from app.models.academic_affairs_r11 import AaSemesterPilotCheckpoint

    if not pilot.check_run_no:
        return []
    rows = db.query(AaSemesterPilotCheckpoint).filter(
        AaSemesterPilotCheckpoint.tenant_id == _tid(),
        AaSemesterPilotCheckpoint.pilot_id == pilot.id,
        AaSemesterPilotCheckpoint.run_no == int(pilot.check_run_no),
        AaSemesterPilotCheckpoint.is_deleted.is_(False),
    ).order_by(AaSemesterPilotCheckpoint.id).all()
    by_code = {row.stage_code: row for row in rows}
    result = []
    for code, name in _STAGE_ORDER:
        row = by_code.get(code)
        if not row:
            continue
        try:
            payload = json.loads(row.evidence_json or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {
                "stageCode": code, "stageName": name, "passed": bool(row.passed),
                "blockerCount": int(row.blocker_count or 0), "warningCount": int(row.warning_count or 0),
                "conclusion": row.conclusion, "evidenceHash": row.evidence_hash,
                "blockers": ["检查证据JSON损坏"], "warnings": [], "evidence": {},
            }
        result.append(payload)
    return result


def get_pilot(user, pilot_id) -> dict:
    _require_admin(user)
    with session() as db:
        pilot = _pilot(db, pilot_id)
        stages = _latest_stages(db, pilot)
        return {**_pilot_row(pilot), "stages": stages, "environment": _environment_evidence()}


def list_pilots(user, *, status=None, page=1, page_size=50) -> tuple[list[dict], int]:
    _require_admin(user)
    from app.models.academic_affairs_r11 import AaSemesterPilot

    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 50)))
    with session() as db:
        query = db.query(AaSemesterPilot).filter(
            AaSemesterPilot.tenant_id == _tid(), AaSemesterPilot.is_deleted.is_(False),
        )
        if status:
            query = query.filter(AaSemesterPilot.status == str(status).upper())
        total = query.count()
        rows = query.order_by(AaSemesterPilot.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return [_pilot_row(row) for row in rows], total


def complete_pilot(user, pilot_id, *, confirm_text, completion_note) -> dict:
    _require_admin(user)
    if str(confirm_text or "").strip() != "CONFIRM_REAL_SEMESTER_COMPLETED":
        raise AppException("VALIDATION_ERROR", "请输入完整确认口令 CONFIRM_REAL_SEMESTER_COMPLETED")
    note = str(completion_note or "").strip()
    if len(note) < 5:
        raise AppException("VALIDATION_ERROR", "完成说明不少于5字")
    env = _environment_evidence()
    if not env["eligibleForRealCompletion"]:
        raise AppException(
            "DATA_CONFLICT",
            "仅关闭mock登录的生产部署可确认真实学校完整学期试点完成",
            details=env,
            http_status=409,
        )
    with session() as db:
        pilot = _pilot(db, pilot_id, lock=True)
        if pilot.status == "COMPLETED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "试点已完成")
        if pilot.status != "READY_TO_COMPLETE" or int(pilot.passed_stage_count or 0) != len(_STAGE_ORDER) or int(pilot.blocker_count or 0) != 0:
            raise AppException("DATA_CONFLICT", "六阶段尚未全部通过，禁止确认完成")
        stages = _latest_stages(db, pilot)
        if len(stages) != len(_STAGE_ORDER) or any(not row.get("passed") for row in stages):
            raise AppException("APPROVAL_VERSION_CONFLICT", "最新检查证据不完整或已有变化，请重新检查")
        expected_hash = _hash({"pilotId": str(pilot.id), "stages": [{"code": row["stageCode"], "hash": row["evidenceHash"]} for row in stages]})
        if expected_hash != pilot.latest_evidence_hash:
            raise AppException("APPROVAL_VERSION_CONFLICT", "试点总证据哈希校验失败，禁止确认完成")
        pilot.status = "COMPLETED"
        pilot.completed_at = datetime.utcnow()
        pilot.completed_by = _operator(user)
        pilot.completion_note = note
        _audit(db, pilot.id, "SEMESTER_PILOT_COMPLETE", f"hash={expected_hash};note={note}", user)
        db.commit()
        db.refresh(pilot)
        return {**_pilot_row(pilot), "stages": stages, "environment": env}


def cancel_pilot(user, pilot_id, reason) -> dict:
    _require_admin(user)
    reason_text = str(reason or "").strip()
    if len(reason_text) < 5:
        raise AppException("VALIDATION_ERROR", "取消原因不少于5字")
    with session() as db:
        pilot = _pilot(db, pilot_id, lock=True)
        if pilot.status == "COMPLETED":
            raise AppException("DATA_CONFLICT", "已完成试点不可取消")
        pilot.status = "CANCELLED"
        pilot.completion_note = reason_text
        _audit(db, pilot.id, "SEMESTER_PILOT_CANCEL", reason_text, user)
        db.commit()
        db.refresh(pilot)
        return _pilot_row(pilot)
