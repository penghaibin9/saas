"""sandbox-school · R11 历史完整学期运行事实。

只服务 standard-20k 售前学校。它把既有 2025-2026-2 教学/考务/成绩真值
投影成 R11 reader 需要的独立教学班、LOCKED 名单、三类 consumer snapshot、
正式成绩主账回链和冻结统计快照；不修改生产 reader/signer，也不降低六阶段门禁。
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime

from sqlalchemy import bindparam, func, select, text

from app.services.sandbox_school_master_seed import _bulk_insert

TERM_CODE = "2025-2026-2"
EXPECTED_TASKS = 1024
EXPECTED_MEMBERS = 52_000
ACTOR = "sandbox-school-r11-seed"


def _scope(db, tenant_id: int) -> dict:
    from app.models import (
        AaExamCourse, AaGradeRecord, AaGradeTask, AaTeachingTask,
        AaTeachingTaskBatch, AaTerm,
    )

    term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == tenant_id,
        AaTerm.year_code == "2025-2026",
        AaTerm.term_no == 2,
        AaTerm.is_deleted.is_(False),
    )).one_or_none()
    if term is None:
        raise RuntimeError("R11 historical runtime: missing 2025-2026-2 term")

    batch_ids = [int(v) for (v,) in db.execute(select(AaTeachingTaskBatch.id).where(
        AaTeachingTaskBatch.tenant_id == tenant_id,
        AaTeachingTaskBatch.term_id == int(term.id),
        AaTeachingTaskBatch.is_deleted.is_(False),
    )).all()]
    if len(batch_ids) != 1:
        raise RuntimeError(f"R11 historical runtime: task batch count={len(batch_ids)}")

    tasks = list(db.execute(select(
        AaTeachingTask.id, AaTeachingTask.course_id, AaTeachingTask.course_name,
        AaTeachingTask.class_id, AaTeachingTask.teaching_class_code,
        AaTeachingTask.teaching_class_name, AaTeachingTask.teacher_id,
        AaTeachingTask.teacher_key, AaTeachingTask.teacher_name,
        AaTeachingTask.expected_students, AaTeachingTask.start_week,
        AaTeachingTask.end_week,
    ).where(
        AaTeachingTask.tenant_id == tenant_id,
        AaTeachingTask.batch_id == batch_ids[0],
        AaTeachingTask.status == "READY",
        AaTeachingTask.is_deleted.is_(False),
    ).order_by(AaTeachingTask.id)).all())
    if len(tasks) != EXPECTED_TASKS:
        raise RuntimeError(f"R11 historical runtime: tasks expected={EXPECTED_TASKS} actual={len(tasks)}")
    task_ids = {int(row.id) for row in tasks}

    grade_tasks = list(db.execute(select(AaGradeTask.id, AaGradeTask.teaching_task_id).where(
        AaGradeTask.tenant_id == tenant_id,
        AaGradeTask.term_id == int(term.id),
        AaGradeTask.status.in_(("PUBLISHED", "ARCHIVED")),
        AaGradeTask.is_deleted.is_(False),
    )).all())
    grade_by_tt = {int(row.teaching_task_id): int(row.id) for row in grade_tasks}
    if len(grade_tasks) != EXPECTED_TASKS or set(grade_by_tt) != task_ids:
        raise RuntimeError("R11 historical runtime: grade tasks are not 1:1 with teaching tasks")

    records = list(db.execute(select(
        AaGradeRecord.id, AaGradeRecord.task_id,
        AaGradeRecord.student_id, AaGradeRecord.acad_grade_id,
    ).where(
        AaGradeRecord.tenant_id == tenant_id,
        AaGradeRecord.task_id.in_(list(grade_by_tt.values())),
        AaGradeRecord.is_deleted.is_(False),
    ).order_by(AaGradeRecord.task_id, AaGradeRecord.student_id)).all())
    if len(records) != EXPECTED_MEMBERS:
        raise RuntimeError(f"R11 historical runtime: grade records expected={EXPECTED_MEMBERS} actual={len(records)}")

    tt_by_grade = {grade_id: tt_id for tt_id, grade_id in grade_by_tt.items()}
    rosters: dict[int, list[int]] = defaultdict(list)
    links = []
    seen_grades = set()
    for row in records:
        if row.acad_grade_id is None:
            raise RuntimeError(f"R11 historical runtime: grade record {row.id} lacks formal-grade backlink")
        grade_id = int(row.acad_grade_id)
        if grade_id in seen_grades:
            raise RuntimeError(f"R11 historical runtime: formal grade {grade_id} is reused")
        seen_grades.add(grade_id)
        tt_id = tt_by_grade[int(row.task_id)]
        rosters[tt_id].append(int(row.student_id))
        links.append((grade_id, int(row.id), int(row.task_id), tt_id))

    for task in tasks:
        ids = sorted(rosters[int(task.id)])
        if len(ids) != len(set(ids)) or len(ids) != int(task.expected_students or 0):
            raise RuntimeError(
                f"R11 historical runtime: roster mismatch task={task.id} "
                f"expected={task.expected_students} actual={len(ids)}"
            )
        rosters[int(task.id)] = ids

    exams = list(db.execute(select(AaExamCourse.id, AaExamCourse.teaching_task_id).where(
        AaExamCourse.tenant_id == tenant_id,
        AaExamCourse.teaching_task_id.in_(list(task_ids)),
        AaExamCourse.status == "CONFIRMED",
        AaExamCourse.is_deleted.is_(False),
    )).all())
    exam_by_tt = {int(row.teaching_task_id): int(row.id) for row in exams}
    if len(exams) != EXPECTED_TASKS or set(exam_by_tt) != task_ids:
        raise RuntimeError("R11 historical runtime: exam courses are not 1:1 with teaching tasks")

    return {
        "term": term, "tasks": tasks, "task_ids": task_ids, "rosters": rosters,
        "grade_by_tt": grade_by_tt, "exam_by_tt": exam_by_tt, "links": links,
    }


def _validate(db, tenant_id: int, scope: dict) -> dict:
    from app.models import (
        AaAttendanceSession, AaTeachingClass, AaTeachingClassMember,
        AaTeachingClassRosterVersion, AcademicGrade,
    )
    from app.models.academic_affairs_r10 import AaStatsSnapshot
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot

    task_ids = list(scope["task_ids"])
    classes = list(db.execute(select(
        AaTeachingClass.id, AaTeachingClass.current_roster_version_id,
    ).where(
        AaTeachingClass.tenant_id == tenant_id,
        AaTeachingClass.teaching_task_id.in_(task_ids),
        AaTeachingClass.status == "ACTIVE",
        AaTeachingClass.roster_status == "LOCKED",
        AaTeachingClass.is_deleted.is_(False),
    )).all())
    class_ids = [int(row.id) for row in classes]
    version_ids = [int(row.current_roster_version_id or 0) for row in classes]
    scalars = {
        "teachingClasses": len(classes),
        "lockedRosters": int(db.scalar(select(func.count()).select_from(AaTeachingClassRosterVersion).where(
            AaTeachingClassRosterVersion.tenant_id == tenant_id,
            AaTeachingClassRosterVersion.id.in_(version_ids or [0]),
            AaTeachingClassRosterVersion.status == "LOCKED",
            AaTeachingClassRosterVersion.is_deleted.is_(False),
        )) or 0),
        "rosterMembers": int(db.scalar(select(func.count()).select_from(AaTeachingClassMember).where(
            AaTeachingClassMember.tenant_id == tenant_id,
            AaTeachingClassMember.teaching_class_id.in_(class_ids or [0]),
            AaTeachingClassMember.status == "ACTIVE",
            AaTeachingClassMember.is_deleted.is_(False),
        )) or 0),
        "attendanceSessions": int(db.scalar(select(func.count()).select_from(AaAttendanceSession).where(
            AaAttendanceSession.tenant_id == tenant_id,
            AaAttendanceSession.term_code == TERM_CODE,
            AaAttendanceSession.status == "SUBMITTED",
            AaAttendanceSession.is_deleted.is_(False),
        )) or 0),
        "formalGrades": int(db.scalar(select(func.count()).select_from(AcademicGrade).where(
            AcademicGrade.tenant_id == tenant_id,
            AcademicGrade.grade_task_id.in_(list(scope["grade_by_tt"].values())),
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        )) or 0),
        "frozenStats": int(db.scalar(select(func.count()).select_from(AaStatsSnapshot).where(
            AaStatsSnapshot.tenant_id == tenant_id,
            AaStatsSnapshot.term_id == int(scope["term"].id),
            AaStatsSnapshot.status == "FROZEN",
            AaStatsSnapshot.is_deleted.is_(False),
        )) or 0),
    }
    consumers = {
        kind: int(db.scalar(select(func.count()).select_from(AaRosterConsumerSnapshot).where(
            AaRosterConsumerSnapshot.tenant_id == tenant_id,
            AaRosterConsumerSnapshot.teaching_task_id.in_(task_ids),
            AaRosterConsumerSnapshot.consumer_type == kind,
            AaRosterConsumerSnapshot.status == "ACTIVE",
            AaRosterConsumerSnapshot.is_deleted.is_(False),
        )) or 0)
        for kind in ("ATTENDANCE_SESSION", "EXAM_COURSE", "GRADE_TASK")
    }
    expected = {
        "teachingClasses": EXPECTED_TASKS, "lockedRosters": EXPECTED_TASKS,
        "rosterMembers": EXPECTED_MEMBERS, "attendanceSessions": EXPECTED_TASKS,
        "formalGrades": EXPECTED_MEMBERS,
    }
    mismatch = {k: {"expected": v, "actual": scalars[k]} for k, v in expected.items() if scalars[k] != v}
    mismatch.update({
        f"consumer:{k}": {"expected": EXPECTED_TASKS, "actual": v}
        for k, v in consumers.items() if v != EXPECTED_TASKS
    })
    if scalars["frozenStats"] < 1:
        mismatch["frozenStats"] = {"expected": ">=1", "actual": scalars["frozenStats"]}
    if mismatch:
        raise RuntimeError(f"R11 historical runtime validation failed: {mismatch}")
    return {**scalars, "consumerSnapshots": consumers, "passed": True}


def seed_school_academic_r11_runtime_20k(db, tenant_id: int) -> dict:
    from app.models import (
        AaAttendanceSession, AaTeachingClass, AaTeachingClassMember,
        AaTeachingClassRosterVersion, AaTeachingClassTeacher, AcademicGrade,
    )
    from app.models.academic_affairs_r10 import AaStatsSnapshot
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot
    from app.modules.academic_affairs.services.academic_affairs_roster_consumer_service import roster_hash
    from app.modules.academic_affairs.services.academic_affairs_stats_snapshot_service import canonical_json, payload_hash

    scope = _scope(db, tenant_id)
    task_ids = list(scope["task_ids"])
    existing = {
        "teachingClasses": int(db.scalar(select(func.count()).select_from(AaTeachingClass).where(
            AaTeachingClass.tenant_id == tenant_id,
            AaTeachingClass.teaching_task_id.in_(task_ids),
            AaTeachingClass.is_deleted.is_(False),
        )) or 0),
        "attendanceSessions": int(db.scalar(select(func.count()).select_from(AaAttendanceSession).where(
            AaAttendanceSession.tenant_id == tenant_id,
            AaAttendanceSession.term_code == TERM_CODE,
            AaAttendanceSession.is_deleted.is_(False),
        )) or 0),
        "consumerSnapshots": int(db.scalar(select(func.count()).select_from(AaRosterConsumerSnapshot).where(
            AaRosterConsumerSnapshot.tenant_id == tenant_id,
            AaRosterConsumerSnapshot.teaching_task_id.in_(task_ids),
            AaRosterConsumerSnapshot.is_deleted.is_(False),
        )) or 0),
        "linkedFormalGrades": int(db.scalar(select(func.count()).select_from(AcademicGrade).where(
            AcademicGrade.tenant_id == tenant_id,
            AcademicGrade.grade_task_id.in_(list(scope["grade_by_tt"].values())),
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        )) or 0),
    }
    if any(existing.values()):
        try:
            return {"created": False, "validation": _validate(db, tenant_id, scope)}
        except Exception as exc:
            raise RuntimeError(
                f"R11 historical runtime has partial residue; refusing silent repair: {existing}"
            ) from exc

    term = scope["term"]
    tasks = scope["tasks"]
    rosters = scope["rosters"]

    _bulk_insert(db, AaTeachingClass, [{
        "tenant_id": tenant_id,
        "teaching_task_id": int(task.id),
        "term_id": int(term.id),
        "course_id": int(task.course_id),
        "class_code": str(task.teaching_class_code or f"TC-{term.id}-{task.id}")[:80],
        "class_name": str(task.teaching_class_name or f"{task.course_name}-{task.class_id}")[:160],
        "class_type": "ADMIN",
        "source_type": "TEACHING_TASK",
        "source_id": int(task.id),
        "capacity": len(rosters[int(task.id)]),
        "current_roster_version_id": None,
        "current_roster_version_no": 0,
        "roster_status": "DRAFT",
        "status": "ACTIVE",
        "source_snapshot_json": json.dumps(
            {"teachingTaskId": str(task.id), "source": "HISTORICAL_GRADE_CLOSURE"},
            sort_keys=True, separators=(",", ":"),
        ),
    } for task in tasks], chunk_size=1000)
    db.flush()

    classes = list(db.execute(select(AaTeachingClass.id, AaTeachingClass.teaching_task_id).where(
        AaTeachingClass.tenant_id == tenant_id,
        AaTeachingClass.teaching_task_id.in_(task_ids),
        AaTeachingClass.status == "ACTIVE",
        AaTeachingClass.is_deleted.is_(False),
    )).all())
    class_by_tt = {int(row.teaching_task_id): int(row.id) for row in classes}
    if len(class_by_tt) != EXPECTED_TASKS:
        raise RuntimeError("R11 historical runtime: teaching-class projection count mismatch")

    teacher_rows, version_rows = [], []
    for task in tasks:
        tt_id, class_id, student_ids = int(task.id), class_by_tt[int(task.id)], rosters[int(task.id)]
        if task.teacher_key:
            teacher_rows.append({
                "tenant_id": tenant_id, "teaching_class_id": class_id,
                "teacher_id": int(task.teacher_id) if task.teacher_id else None,
                "teacher_key": str(task.teacher_key), "teacher_name": task.teacher_name,
                "role_type": "PRIMARY", "start_week": task.start_week,
                "end_week": task.end_week, "status": "ACTIVE",
            })
        version_rows.append({
            "tenant_id": tenant_id, "teaching_class_id": class_id, "version_no": 1,
            "source_type": "ADMIN_CLASS", "source_id": int(task.class_id) if task.class_id else None,
            "member_count": len(student_ids), "roster_hash": roster_hash(student_ids),
            "status": "LOCKED", "reason": "historical published-grade roster projection",
            "locked_at": datetime(2026, 2, 20, 18, 0), "locked_by": ACTOR,
        })
    _bulk_insert(db, AaTeachingClassTeacher, teacher_rows, chunk_size=1000)
    _bulk_insert(db, AaTeachingClassRosterVersion, version_rows, chunk_size=1000)
    db.flush()

    versions = list(db.execute(select(
        AaTeachingClassRosterVersion.id, AaTeachingClassRosterVersion.teaching_class_id,
        AaTeachingClassRosterVersion.roster_hash,
    ).where(
        AaTeachingClassRosterVersion.tenant_id == tenant_id,
        AaTeachingClassRosterVersion.teaching_class_id.in_(list(class_by_tt.values())),
        AaTeachingClassRosterVersion.status == "LOCKED",
        AaTeachingClassRosterVersion.is_deleted.is_(False),
    )).all())
    version_by_class = {int(row.teaching_class_id): row for row in versions}
    if len(version_by_class) != EXPECTED_TASKS:
        raise RuntimeError("R11 historical runtime: roster-version projection count mismatch")

    class_update = AaTeachingClass.__table__.update().where(
        AaTeachingClass.__table__.c.id == bindparam("_class_id")
    ).values(
        current_roster_version_id=bindparam("_version_id"),
        current_roster_version_no=1, roster_status="LOCKED",
    )
    class_updates, member_rows, meta = [], [], {}
    for tt_id, class_id in class_by_tt.items():
        version = version_by_class[class_id]
        version_id = int(version.id)
        student_ids = rosters[tt_id]
        class_updates.append({"_class_id": class_id, "_version_id": version_id})
        meta[tt_id] = (class_id, version_id, str(version.roster_hash), student_ids)
        member_rows.extend({
            "tenant_id": tenant_id, "teaching_class_id": class_id,
            "roster_version_id": version_id, "student_id": student_id,
            "source_type": "ADMIN_CLASS", "source_id": None,
            "status": "ACTIVE", "joined_at": datetime(2026, 2, 20, 18, 0),
        } for student_id in student_ids)
    db.execute(class_update, class_updates)
    _bulk_insert(db, AaTeachingClassMember, member_rows, chunk_size=2000)
    db.flush()

    _bulk_insert(db, AaAttendanceSession, [{
        "tenant_id": tenant_id,
        "class_id": int(task.class_id) if task.class_id else None,
        "course_name": task.course_name, "term_code": TERM_CODE,
        "teacher_key": task.teacher_key,
        "session_date": f"2026-03-{1 + (index % 28):02d}",
        "slot_no": 1 + (index % 8), "session_type": "常规",
        "roster_json": json.dumps(
            [{"studentId": str(student_id), "status": "PRESENT"} for student_id in rosters[int(task.id)]],
            ensure_ascii=False, separators=(",", ":"),
        ),
        "total_count": len(rosters[int(task.id)]),
        "present_count": len(rosters[int(task.id)]), "absent_count": 0,
        "status": "SUBMITTED",
    } for index, task in enumerate(tasks)], chunk_size=1000)
    db.flush()

    sessions = list(db.execute(select(
        AaAttendanceSession.id, AaAttendanceSession.class_id, AaAttendanceSession.course_name,
    ).where(
        AaAttendanceSession.tenant_id == tenant_id,
        AaAttendanceSession.term_code == TERM_CODE,
        AaAttendanceSession.status == "SUBMITTED",
        AaAttendanceSession.is_deleted.is_(False),
    )).all())
    attendance_by_key = {(int(row.class_id or 0), str(row.course_name or "")): int(row.id) for row in sessions}
    if len(sessions) != EXPECTED_TASKS or len(attendance_by_key) != EXPECTED_TASKS:
        raise RuntimeError("R11 historical runtime: attendance sessions are not 1:1 with tasks")

    snapshots = []
    for task in tasks:
        tt_id = int(task.id)
        class_id, version_id, digest, student_ids = meta[tt_id]
        common = {
            "tenant_id": tenant_id, "snapshot_version": 1,
            "teaching_task_id": tt_id, "teaching_class_id": class_id,
            "roster_version_id": version_id, "roster_version_no": 1,
            "roster_source": "ADMIN_CLASS", "roster_hash": digest,
            "member_count": len(student_ids),
            "student_ids_json": json.dumps(student_ids, separators=(",", ":")),
            "captured_by": ACTOR, "status": "ACTIVE",
        }
        attendance_id = attendance_by_key[(int(task.class_id or 0), str(task.course_name or ""))]
        snapshots.extend((
            {**common, "consumer_type": "ATTENDANCE_SESSION", "consumer_id": attendance_id,
             "captured_at": datetime(2026, 3, 31, 18, 0)},
            {**common, "consumer_type": "EXAM_COURSE", "consumer_id": scope["exam_by_tt"][tt_id],
             "captured_at": datetime(2026, 6, 20, 18, 0)},
            {**common, "consumer_type": "GRADE_TASK", "consumer_id": scope["grade_by_tt"][tt_id],
             "captured_at": datetime(2026, 6, 30, 18, 0)},
        ))
    _bulk_insert(db, AaRosterConsumerSnapshot, snapshots, chunk_size=1500)
    db.flush()

    if db.get_bind().dialect.name == "mysql":
        result = db.execute(text("""
            UPDATE t_acad_grade AS g
            JOIN t_aa_grade_record AS r
              ON r.tenant_id=:tid AND r.acad_grade_id=g.id AND r.is_deleted=0
            JOIN t_aa_grade_task AS gt
              ON gt.tenant_id=:tid AND gt.id=r.task_id AND gt.term_id=:term_id AND gt.is_deleted=0
            JOIN t_aa_teaching_class AS tc
              ON tc.tenant_id=:tid AND tc.teaching_task_id=gt.teaching_task_id
             AND tc.status='ACTIVE' AND tc.is_deleted=0
            SET g.grade_task_id=gt.id, g.grade_record_id=r.id,
                g.teaching_task_id=gt.teaching_task_id, g.teaching_class_id=tc.id,
                g.roster_version_id=tc.current_roster_version_id, g.active_record_key=r.id
            WHERE g.tenant_id=:tid AND g.term=:term_code
              AND g.record_status='ACTIVE' AND g.is_deleted=0
        """), {"tid": tenant_id, "term_id": int(term.id), "term_code": TERM_CODE})
        if result.rowcount not in (-1, EXPECTED_MEMBERS):
            raise RuntimeError(f"R11 historical runtime: formal-grade update rowcount={result.rowcount}")
    else:
        update_stmt = AcademicGrade.__table__.update().where(
            AcademicGrade.__table__.c.id == bindparam("_grade_id")
        ).values(
            grade_task_id=bindparam("_grade_task_id"),
            grade_record_id=bindparam("_record_id"),
            teaching_task_id=bindparam("_tt_id"),
            teaching_class_id=bindparam("_class_id"),
            roster_version_id=bindparam("_version_id"),
            active_record_key=bindparam("_record_id"),
        )
        rows = []
        for grade_id, record_id, grade_task_id, tt_id in scope["links"]:
            class_id, version_id, _digest, _students = meta[tt_id]
            rows.append({
                "_grade_id": grade_id, "_grade_task_id": grade_task_id,
                "_record_id": record_id, "_tt_id": tt_id,
                "_class_id": class_id, "_version_id": version_id,
            })
        for start in range(0, len(rows), 2000):
            db.execute(update_stmt, rows[start:start + 2000])
    db.flush()

    frozen = {
        "snapshotType": "OVERVIEW",
        "scope": {"tenantId": str(tenant_id), "termId": str(term.id), "termCode": TERM_CODE},
        "filters": {"termId": str(term.id)},
        "indicators": [
            {"code": "teachingClasses", "value": EXPECTED_TASKS},
            {"code": "rosterMembers", "value": EXPECTED_MEMBERS},
            {"code": "attendanceSessions", "value": EXPECTED_TASKS},
            {"code": "examCourses", "value": EXPECTED_TASKS},
            {"code": "gradeTasks", "value": EXPECTED_TASKS},
            {"code": "formalGrades", "value": EXPECTED_MEMBERS},
        ],
        "sourceAsOf": "2026-07-20T10:00:00", "schemaVersion": 1,
        "seedContract": "R11_HISTORICAL_RUNTIME_V1",
    }
    db.add(AaStatsSnapshot(
        tenant_id=tenant_id, snapshot_type="OVERVIEW", term_id=int(term.id),
        college_id=None, major_id=None,
        scope_json=canonical_json(frozen["scope"]),
        filters_json=canonical_json(frozen["filters"]),
        payload_json=canonical_json(frozen), payload_hash=payload_hash(frozen),
        source_as_of=datetime(2026, 7, 20, 10, 0),
        generated_at=datetime(2026, 7, 20, 10, 5),
        generated_by=ACTOR, status="FROZEN",
    ))
    db.commit()
    return {"created": True, "validation": _validate(db, tenant_id, scope)}


def validate_school_academic_r11_runtime_20k(db, tenant_id: int) -> dict:
    return _validate(db, tenant_id, _scope(db, tenant_id))
