"""sandbox-school · 20K 历史评教与教学质量事实。

参考日 2026-08-13：
- 只给已经结束并归档的 2025-2026-2 学期生成评教与质量事实；
- 2026-2027-1 尚未开学，严禁提前生成学生评教/教学质量结果；
- 学生评教保持架构级匿名：AaEvaluationRecord 不保存学生身份，STUDENT 任务 evaluator_key 必须为空；
- 教学质量只生成督导听课/巡课/教学检查和整改，不替学校自动认定教学事故(INCIDENT)；
- 评教结果投影必须复用 production evaluation policy，20K 不得维护第二套权重/等级算法。
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, select

from app.services.sandbox_school_academic_affairs_seed import EXPECTED_GRADE_RECORDS, EXPECTED_HISTORICAL_TASKS
from app.services.sandbox_school_master_seed import _bulk_insert

REFERENCE_NOW = datetime(2026, 8, 13, 9, 0)
EXPECTED_EVALUATION_BATCHES = 1
EXPECTED_EVALUATION_TASKS = EXPECTED_HISTORICAL_TASKS * 4
EXPECTED_STUDENT_EVALUATION_RECORDS = EXPECTED_GRADE_RECORDS
EXPECTED_NON_STUDENT_EVALUATION_RECORDS = EXPECTED_HISTORICAL_TASKS * 3
EXPECTED_EVALUATION_RESULTS = EXPECTED_HISTORICAL_TASKS
EXPECTED_QUALITY_RECORDS = 96
EXPECTED_SUPERVISION = 48
EXPECTED_PATROL = 32
EXPECTED_INSPECTION = 16
EXPECTED_INCIDENT = 0
EXPECTED_RECTIFICATIONS = 24


def _count(db, model, tenant_id: int, *where) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(
        model.tenant_id == tenant_id,
        model.is_deleted.is_(False),
        *where,
    )) or 0)


def _canonical_projection(student_avg, self_score, peer_avg, supervisor_avg) -> tuple[float | None, str | None]:
    """Reuse the current production evaluation policy; sandbox owns no scoring constants."""
    from app.modules.academic_affairs.services import academic_affairs_evaluation_service as evaluation_policy

    def _float(value):
        return float(value) if value is not None else None

    student_value = _float(student_avg)
    composite = evaluation_policy._composite(
        student_value,
        _float(self_score),
        _float(peer_avg),
        _float(supervisor_avg),
    )
    level_basis = composite if composite is not None else student_value
    return composite, evaluation_policy._level(level_basis)


def _historical_context(db, tenant_id: int) -> dict:
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm, Major, SchoolClass, User

    historical_term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == tenant_id,
        AaTerm.year_code == "2025-2026",
        AaTerm.term_no == 2,
        AaTerm.is_deleted.is_(False),
    )).first()
    current_term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == tenant_id,
        AaTerm.year_code == "2026-2027",
        AaTerm.term_no == 1,
        AaTerm.is_deleted.is_(False),
    )).first()
    if historical_term is None or current_term is None:
        raise RuntimeError("评教/质量种子缺少历史或当前学期")

    batch_ids = [
        int(row.id)
        for row in db.scalars(select(AaTeachingTaskBatch).where(
            AaTeachingTaskBatch.tenant_id == tenant_id,
            AaTeachingTaskBatch.term_id == int(historical_term.id),
            AaTeachingTaskBatch.is_deleted.is_(False),
        )).all()
    ]
    tasks = list(db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.tenant_id == tenant_id,
        AaTeachingTask.batch_id.in_(batch_ids),
        AaTeachingTask.status != "MERGED",
        AaTeachingTask.is_deleted.is_(False),
    ).order_by(AaTeachingTask.id)).all())
    if len(tasks) != EXPECTED_HISTORICAL_TASKS:
        raise RuntimeError(
            f"历史评教教学任务异常 expected={EXPECTED_HISTORICAL_TASKS} actual={len(tasks)}"
        )

    class_rows = list(db.execute(
        select(
            SchoolClass.id,
            SchoolClass.class_name,
            SchoolClass.major_id,
            Major.college_id,
        )
        .join(Major, Major.id == SchoolClass.major_id)
        .where(
            SchoolClass.tenant_id == tenant_id,
            SchoolClass.is_deleted.is_(False),
            Major.tenant_id == tenant_id,
            Major.is_deleted.is_(False),
        )
    ).all())
    class_org = {
        int(row.id): {
            "className": row.class_name,
            "majorId": int(row.major_id),
            "collegeId": int(row.college_id),
        }
        for row in class_rows
    }

    teachers = list(db.execute(select(User.login_name, User.real_name).where(
        User.tenant_id == tenant_id,
        User.login_name.like("sbx_t%"),
        User.status == "ACTIVE",
        User.is_deleted.is_(False),
    ).order_by(User.login_name)).all())
    academic_admins = list(db.execute(select(User.login_name, User.real_name).where(
        User.tenant_id == tenant_id,
        User.login_name.like("sbx_aa%"),
        User.status == "ACTIVE",
        User.is_deleted.is_(False),
    ).order_by(User.login_name)).all())
    if len(teachers) < 100 or not academic_admins:
        raise RuntimeError("评教/教学质量缺少真实教师或教务管理账号")

    return {
        "historicalTerm": historical_term,
        "currentTerm": current_term,
        "tasks": tasks,
        "classOrg": class_org,
        "teachers": teachers,
        "academicAdmins": academic_admins,
    }


def seed_school_academic_quality_20k(db, tenant_id: int) -> dict:
    from app.models import (
        AaEvaluationBatch,
        AaEvaluationRecord,
        AaEvaluationResult,
        AaEvaluationTask,
        AaQualityRecord,
        AaQualityRectification,
    )

    ctx = _historical_context(db, tenant_id)
    hist_term = ctx["historicalTerm"]
    tasks = ctx["tasks"]
    teachers = ctx["teachers"]
    academic_admins = ctx["academicAdmins"]
    class_org = ctx["classOrg"]

    batch = AaEvaluationBatch(
        tenant_id=tenant_id,
        batch_name="2025-2026学年第二学期学生评教与多元教学评价",
        term_id=int(hist_term.id),
        scope_json=json.dumps({"scope": "ALL_HISTORICAL_TEACHING_TASKS", "teachingTasks": len(tasks)}, ensure_ascii=False),
        template_json=json.dumps({
            "version": "2026-SPRING",
            "dimensions": ["教学准备", "教学组织", "专业实践", "课堂互动", "学习获得"],
            "scale": "5级量表",
            "studentAnonymous": True,
        }, ensure_ascii=False),
        anonymous=True,
        window_start=datetime(2026, 6, 8, 8, 0),
        window_end=datetime(2026, 6, 19, 22, 0),
        result_published_at=datetime(2026, 7, 15, 9, 0),
        status="ARCHIVED",
    )
    db.add(batch)
    db.flush()

    eval_task_rows = []
    for index, task in enumerate(tasks):
        peer = teachers[(index + 37) % len(teachers)]
        supervisor = academic_admins[index % len(academic_admins)]
        base = {
            "tenant_id": tenant_id,
            "batch_id": int(batch.id),
            "teaching_task_id": int(task.id),
            "course_id": int(task.course_id) if task.course_id else None,
            "course_name": task.course_name,
            "class_id": int(task.class_id) if task.class_id else None,
            "teacher_key": task.teacher_key,
            "teacher_name": task.teacher_name,
            "status": "SUBMITTED",
        }
        eval_task_rows.extend([
            {**base, "evaluator_type": "STUDENT", "evaluator_key": None,
             "submitted_count": int(task.expected_students or 0)},
            {**base, "evaluator_type": "SELF", "evaluator_key": task.teacher_key, "submitted_count": 1},
            {**base, "evaluator_type": "PEER", "evaluator_key": peer.login_name, "submitted_count": 1},
            {**base, "evaluator_type": "SUPERVISOR", "evaluator_key": supervisor.login_name, "submitted_count": 1},
        ])
    _bulk_insert(db, AaEvaluationTask, eval_task_rows, chunk_size=1000)
    db.flush()

    task_rows = list(db.execute(select(
        AaEvaluationTask.id,
        AaEvaluationTask.teaching_task_id,
        AaEvaluationTask.teacher_key,
        AaEvaluationTask.evaluator_type,
    ).where(
        AaEvaluationTask.tenant_id == tenant_id,
        AaEvaluationTask.batch_id == int(batch.id),
        AaEvaluationTask.is_deleted.is_(False),
    )).all())
    eval_task_by_key = {
        (int(row.teaching_task_id), row.evaluator_type): row
        for row in task_rows
    }

    record_rows = []
    result_rows = []
    for task_index, task in enumerate(tasks):
        student_task = eval_task_by_key[(int(task.id), "STUDENT")]
        student_scores = []
        student_count = int(task.expected_students or 0)
        for response_index in range(student_count):
            score = Decimal(82 + ((task_index * 5 + response_index * 3) % 14))
            student_scores.append(score)
            record_rows.append({
                "tenant_id": tenant_id,
                "batch_id": int(batch.id),
                "task_id": int(student_task.id),
                "teacher_key": task.teacher_key,
                "evaluator_type": "STUDENT",
                "answers_json": json.dumps({
                    "教学准备": int(score),
                    "教学组织": min(100, int(score) + 1),
                    "专业实践": max(60, int(score) - 1),
                    "课堂互动": int(score),
                    "学习获得": min(100, int(score) + 2),
                }, ensure_ascii=False),
                "objective_score": score,
                "comment": None,
            })

        non_student_scores = {}
        for offset, evaluator_type in enumerate(("SELF", "PEER", "SUPERVISOR")):
            eval_task = eval_task_by_key[(int(task.id), evaluator_type)]
            score = Decimal(86 + ((task_index * 3 + offset * 2) % 10))
            non_student_scores[evaluator_type] = score
            record_rows.append({
                "tenant_id": tenant_id,
                "batch_id": int(batch.id),
                "task_id": int(eval_task.id),
                "teacher_key": task.teacher_key,
                "evaluator_type": evaluator_type,
                "answers_json": json.dumps({"综合评价": int(score)}, ensure_ascii=False),
                "objective_score": score,
                "comment": (
                    "课堂组织规范，专业实践环节完整。"
                    if evaluator_type != "SELF"
                    else "按课程标准完成教学任务，并持续优化实践教学。"
                ),
            })

        student_avg = (
            sum(student_scores, Decimal("0")) / Decimal(len(student_scores))
            if student_scores else Decimal("0")
        ).quantize(Decimal("0.01"))
        self_score = non_student_scores["SELF"]
        peer_score = non_student_scores["PEER"]
        supervisor_score = non_student_scores["SUPERVISOR"]
        composite, level = _canonical_projection(
            student_avg,
            self_score,
            peer_score,
            supervisor_score,
        )
        result_rows.append({
            "tenant_id": tenant_id,
            "batch_id": int(batch.id),
            "teaching_task_id": int(task.id),
            "teacher_key": task.teacher_key,
            "teacher_name": task.teacher_name,
            "course_name": task.course_name,
            "student_avg": student_avg,
            "student_count": student_count,
            "self_score": self_score,
            "peer_avg": peer_score,
            "peer_count": 1,
            "supervisor_avg": supervisor_score,
            "supervisor_count": 1,
            "composite_score": composite,
            "level": level,
            "published": True,
        })

    _bulk_insert(db, AaEvaluationRecord, record_rows, chunk_size=1500)
    _bulk_insert(db, AaEvaluationResult, result_rows, chunk_size=500)
    db.flush()

    quality_rows = []
    quality_type_plan = (
        ["SUPERVISION"] * EXPECTED_SUPERVISION
        + ["PATROL"] * EXPECTED_PATROL
        + ["INSPECTION"] * EXPECTED_INSPECTION
    )
    for index, (task, record_type) in enumerate(zip(tasks[:EXPECTED_QUALITY_RECORDS], quality_type_plan)):
        org = class_org.get(int(task.class_id or 0))
        if org is None:
            raise RuntimeError(f"教学质量任务无行政班组织链 task={task.id} class={task.class_id}")
        need_rectify = index % 4 == 0
        recorder = academic_admins[index % len(academic_admins)]
        occurred_at = datetime(2026, 3, 10, 8, 30) + timedelta(days=index % 90, hours=(index % 4) * 2)
        score = Decimal(82 + ((index * 7) % 16))
        quality_rows.append({
            "tenant_id": tenant_id,
            "record_type": record_type,
            "term_id": int(hist_term.id),
            "college_id": org["collegeId"],
            "major_id": org["majorId"],
            "class_id": int(task.class_id),
            "teacher_key": task.teacher_key,
            "teacher_name": task.teacher_name,
            "course_id": int(task.course_id) if task.course_id else None,
            "course_name": task.course_name,
            "occurred_at": occurred_at,
            "location": f"教学楼{(index % 8) + 1}号楼{((index % 4) + 1)}0{(index % 9) + 1}",
            "title": f"{record_type}-{task.course_name}-{org['className']}",
            "category": "课堂教学质量" if record_type == "SUPERVISION" else ("教学秩序" if record_type == "PATROL" else "教学资料与执行"),
            "score": score,
            "conclusion": "待整改" if need_rectify else "合格",
            "description": (
                "课堂互动与实训任务衔接可进一步加强，已形成具体改进事项。"
                if need_rectify else "教学组织、课堂秩序与课程执行符合本学期教学要求。"
            ),
            "handling_note": "转入整改跟踪" if need_rectify else "记录归档",
            "need_rectify": need_rectify,
            "recorder_key": recorder.login_name,
            "recorder_name": recorder.real_name,
            "status": "CONFIRMED" if need_rectify else "CLOSED",
            "confirmed_at": occurred_at + timedelta(days=2),
            "confirmed_by_name": "教务处教学质量管理组",
        })
    _bulk_insert(db, AaQualityRecord, quality_rows, chunk_size=500)
    db.flush()

    rectification_sources = list(db.scalars(select(AaQualityRecord).where(
        AaQualityRecord.tenant_id == tenant_id,
        AaQualityRecord.term_id == int(hist_term.id),
        AaQualityRecord.need_rectify.is_(True),
        AaQualityRecord.is_deleted.is_(False),
    ).order_by(AaQualityRecord.id)).all())
    if len(rectification_sources) != EXPECTED_RECTIFICATIONS:
        raise RuntimeError(
            f"教学质量整改来源异常 expected={EXPECTED_RECTIFICATIONS} actual={len(rectification_sources)}"
        )

    rectification_rows = []
    for index, source in enumerate(rectification_sources):
        if index < 12:
            status = "CLOSED"
            closed_at = datetime(2026, 7, 5, 16, 0) + timedelta(days=index % 5)
            result_note = "复核通过，改进措施已落实并纳入课程组后续教学要求。"
        elif index < 18:
            status = "SUBMITTED"
            closed_at = None
            result_note = "责任教师已提交整改说明，等待学院复核。"
        else:
            status = "IN_PROGRESS"
            closed_at = None
            result_note = None
        rectification_rows.append({
            "tenant_id": tenant_id,
            "source_record_id": int(source.id),
            "source_type": source.record_type,
            "source_title": source.title,
            "title": f"整改：{source.course_name or source.title}",
            "term_id": int(hist_term.id),
            "college_id": int(source.college_id) if source.college_id else None,
            "major_id": int(source.major_id) if source.major_id else None,
            "class_id": int(source.class_id) if source.class_id else None,
            "requirement": "两周内补充课堂互动设计与实践任务说明，并由课程组完成一次复核听课。",
            "deadline": datetime(2026, 7, 20, 18, 0) + timedelta(days=index % 12),
            "responsible_key": source.teacher_key,
            "responsible_name": source.teacher_name,
            "initiator_key": source.recorder_key,
            "initiator_name": source.recorder_name,
            "progress_log_json": json.dumps([
                {"time": "2026-06-25 10:00", "operator": source.teacher_name, "action": "RECEIVE", "note": "已认领整改任务"},
                {"time": "2026-07-03 15:00", "operator": source.teacher_name, "action": "UPDATE", "note": "已补充课堂互动与实践任务设计"},
            ], ensure_ascii=False),
            "result_note": result_note,
            "status": status,
            "closed_at": closed_at,
        })
    _bulk_insert(db, AaQualityRectification, rectification_rows, chunk_size=500)
    db.commit()

    return validate_school_academic_quality_20k(db, tenant_id)


def _evaluation_score_truth(db, tenant_id: int) -> dict:
    """Recompute each batch/task result projection from active answers using production policy."""
    from app.models import AaEvaluationRecord, AaEvaluationResult, AaEvaluationTask

    score_rows = db.execute(
        select(
            AaEvaluationTask.batch_id,
            AaEvaluationTask.teaching_task_id,
            AaEvaluationTask.evaluator_type,
            func.avg(AaEvaluationRecord.objective_score).label("average_score"),
            func.count(AaEvaluationRecord.objective_score).label("score_count"),
        )
        .select_from(AaEvaluationTask)
        .outerjoin(
            AaEvaluationRecord,
            and_(
                AaEvaluationRecord.task_id == AaEvaluationTask.id,
                AaEvaluationRecord.tenant_id == AaEvaluationTask.tenant_id,
                AaEvaluationRecord.batch_id == AaEvaluationTask.batch_id,
                AaEvaluationRecord.is_deleted.is_(False),
            ),
        )
        .where(
            AaEvaluationTask.tenant_id == tenant_id,
            AaEvaluationTask.is_deleted.is_(False),
        )
        .group_by(
            AaEvaluationTask.batch_id,
            AaEvaluationTask.teaching_task_id,
            AaEvaluationTask.evaluator_type,
        )
    ).all()
    by_projection: dict[tuple[int, int], dict[str, tuple[float | None, int]]] = defaultdict(dict)
    for batch_id, teaching_task_id, evaluator_type, average_score, score_count in score_rows:
        if batch_id is None or teaching_task_id is None:
            continue
        by_projection[(int(batch_id), int(teaching_task_id))][str(evaluator_type)] = (
            round(float(average_score), 2) if average_score is not None else None,
            int(score_count or 0),
        )

    results = list(db.scalars(select(AaEvaluationResult).where(
        AaEvaluationResult.tenant_id == tenant_id,
        AaEvaluationResult.is_deleted.is_(False),
    ).order_by(AaEvaluationResult.id)).all())

    def _same(actual, expected) -> bool:
        if actual is None or expected is None:
            return actual is None and expected is None
        return round(float(actual), 2) == round(float(expected), 2)

    mismatches = []
    for result in results:
        sources = by_projection.get((int(result.batch_id), int(result.teaching_task_id)), {})
        student_avg, student_count = sources.get("STUDENT", (None, 0))
        self_score, _self_count = sources.get("SELF", (None, 0))
        peer_avg, peer_count = sources.get("PEER", (None, 0))
        supervisor_avg, supervisor_count = sources.get("SUPERVISOR", (None, 0))
        composite, level = _canonical_projection(
            student_avg,
            self_score,
            peer_avg,
            supervisor_avg,
        )
        bad_fields = []
        for field, actual, expected in (
            ("studentAvg", result.student_avg, student_avg),
            ("selfScore", result.self_score, self_score),
            ("peerAvg", result.peer_avg, peer_avg),
            ("supervisorAvg", result.supervisor_avg, supervisor_avg),
            ("compositeScore", result.composite_score, composite),
        ):
            if not _same(actual, expected):
                bad_fields.append(f"{field}:{actual}!={expected}")
        for field, actual, expected in (
            ("studentCount", int(result.student_count or 0), student_count),
            ("peerCount", int(result.peer_count or 0), peer_count),
            ("supervisorCount", int(result.supervisor_count or 0), supervisor_count),
            ("level", result.level, level),
        ):
            if actual != expected:
                bad_fields.append(f"{field}:{actual}!={expected}")
        if bad_fields:
            mismatches.append({
                "resultId": str(result.id),
                "batchId": str(result.batch_id),
                "teachingTaskId": str(result.teaching_task_id),
                "fields": bad_fields,
            })
    return {
        "checked": len(results),
        "mismatchCount": len(mismatches),
        "samples": mismatches[:20],
    }


def validate_school_academic_quality_20k(db, tenant_id: int) -> dict:
    from app.models import (
        AaEvaluationBatch,
        AaEvaluationRecord,
        AaEvaluationResult,
        AaEvaluationTask,
        AaQualityRecord,
        AaQualityRectification,
        AaTerm,
    )

    historical_term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == tenant_id,
        AaTerm.year_code == "2025-2026",
        AaTerm.term_no == 2,
        AaTerm.is_deleted.is_(False),
    )).one()
    current_term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == tenant_id,
        AaTerm.year_code == "2026-2027",
        AaTerm.term_no == 1,
        AaTerm.is_deleted.is_(False),
    )).one()

    historical_batches = _count(db, AaEvaluationBatch, tenant_id, AaEvaluationBatch.term_id == int(historical_term.id))
    current_batches = _count(db, AaEvaluationBatch, tenant_id, AaEvaluationBatch.term_id == int(current_term.id))
    student_tasks = _count(db, AaEvaluationTask, tenant_id, AaEvaluationTask.evaluator_type == "STUDENT")
    non_student_tasks = _count(db, AaEvaluationTask, tenant_id, AaEvaluationTask.evaluator_type != "STUDENT")
    student_records = _count(db, AaEvaluationRecord, tenant_id, AaEvaluationRecord.evaluator_type == "STUDENT")
    non_student_records = _count(db, AaEvaluationRecord, tenant_id, AaEvaluationRecord.evaluator_type != "STUDENT")
    anonymous_task_leaks = _count(
        db,
        AaEvaluationTask,
        tenant_id,
        AaEvaluationTask.evaluator_type == "STUDENT",
        AaEvaluationTask.evaluator_key.is_not(None),
    )
    score_truth = _evaluation_score_truth(db, tenant_id)

    quality_types = {
        record_type: _count(db, AaQualityRecord, tenant_id, AaQualityRecord.record_type == record_type)
        for record_type in ("SUPERVISION", "PATROL", "INSPECTION", "INCIDENT")
    }
    report = {
        "historicalEvaluationBatches": historical_batches,
        "currentAutumnEvaluationBatches": current_batches,
        "evaluationTasks": _count(db, AaEvaluationTask, tenant_id),
        "studentEvaluationTasks": student_tasks,
        "nonStudentEvaluationTasks": non_student_tasks,
        "studentAnonymousRecords": student_records,
        "nonStudentEvaluationRecords": non_student_records,
        "evaluationResults": _count(db, AaEvaluationResult, tenant_id),
        "studentTaskIdentityLeaks": anonymous_task_leaks,
        "evaluationScoreTruthChecked": score_truth["checked"],
        "evaluationScoreTruthMismatches": score_truth["mismatchCount"],
        "qualityRecords": _count(db, AaQualityRecord, tenant_id),
        "supervisionRecords": quality_types["SUPERVISION"],
        "patrolRecords": quality_types["PATROL"],
        "inspectionRecords": quality_types["INSPECTION"],
        "incidentRecords": quality_types["INCIDENT"],
        "rectifications": _count(db, AaQualityRectification, tenant_id),
    }
    expected = {
        "historicalEvaluationBatches": EXPECTED_EVALUATION_BATCHES,
        "currentAutumnEvaluationBatches": 0,
        "evaluationTasks": EXPECTED_EVALUATION_TASKS,
        "studentEvaluationTasks": EXPECTED_HISTORICAL_TASKS,
        "nonStudentEvaluationTasks": EXPECTED_NON_STUDENT_EVALUATION_RECORDS,
        "studentAnonymousRecords": EXPECTED_STUDENT_EVALUATION_RECORDS,
        "nonStudentEvaluationRecords": EXPECTED_NON_STUDENT_EVALUATION_RECORDS,
        "evaluationResults": EXPECTED_EVALUATION_RESULTS,
        "studentTaskIdentityLeaks": 0,
        "evaluationScoreTruthChecked": EXPECTED_EVALUATION_RESULTS,
        "evaluationScoreTruthMismatches": 0,
        "qualityRecords": EXPECTED_QUALITY_RECORDS,
        "supervisionRecords": EXPECTED_SUPERVISION,
        "patrolRecords": EXPECTED_PATROL,
        "inspectionRecords": EXPECTED_INSPECTION,
        "incidentRecords": EXPECTED_INCIDENT,
        "rectifications": EXPECTED_RECTIFICATIONS,
    }
    mismatches = {
        key: {"expected": value, "actual": report[key]}
        for key, value in expected.items()
        if report[key] != value
    }
    if mismatches:
        raise RuntimeError(
            f"20K 历史评教/教学质量验收失败: {mismatches}; "
            f"scoreTruthSamples={score_truth['samples']}"
        )
    report["passed"] = True
    return report
