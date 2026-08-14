"""sandbox-school · 20K 2027届毕业设计早期过程数据。

参考日固定 2026-08-13。目标是让 2027 届毕业设计像真实学校正在运行，而不是把全年流程
一次性提前跑完：
- 6,400 名学生都有当前导师分配历史，和 t_gd_student.mentor_id 一致；
- 2,240 名已确定选题、进入早期指导的学生生成任务书；
- 其中一部分已经提交/审核开题材料，一部分已有 8 月早期指导记录；
- 中期、定稿、查重、评阅、答辩、最终成绩、归档在参考日必须保持 0 行。

所有内容均为确定性虚构售前数据，仅允许作用于 sandbox-school。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.services.sandbox_school_master_seed import _bulk_insert

REFERENCE_NOW = datetime(2026, 8, 13, 9, 0)
EXPECTED_STUDENTS = 6400
EXPECTED_GUIDING = 2240
EXPECTED_ASSIGNMENTS = 6400
EXPECTED_TASKBOOKS = 2240
EXPECTED_TASKBOOK_CONFIRMED = 1680
EXPECTED_TASKBOOK_PENDING = 560
EXPECTED_PROPOSALS = 960
EXPECTED_PROPOSAL_APPROVED = 480
EXPECTED_PROPOSAL_PENDING = 320
EXPECTED_PROPOSAL_REJECTED = 160
EXPECTED_GUIDANCE = 1120


def _count(db, model, tenant_id: int, *where) -> int:
    return int(db.scalar(
        select(func.count()).select_from(model).where(
            model.tenant_id == tenant_id,
            model.is_deleted.is_(False),
            *where,
        )
    ) or 0)


def seed_school_graduation_process_20k(db, tenant_id: int) -> dict:
    from app.models import (
        GraduationBatch,
        GraduationGuidance,
        GraduationMentor,
        GraduationMentorAssignment,
        GraduationProposal,
        GraduationStudent,
        GraduationTaskBook,
    )

    batch = db.scalars(select(GraduationBatch).where(
        GraduationBatch.tenant_id == tenant_id,
        GraduationBatch.batch_no == "GD-2027",
        GraduationBatch.is_deleted.is_(False),
    )).first()
    if batch is None:
        raise RuntimeError("GD-2027 毕设批次不存在")

    batch.stage_config = [
        {"code": "TOPIC_SELECTING", "name": "选题与确认", "startDate": "2026-08-01", "endDate": "2026-09-10"},
        {"code": "GUIDING", "name": "任务书与前期指导", "startDate": "2026-08-11", "endDate": "2027-03-31"},
        {"code": "MIDTERM", "name": "中期检查", "startDate": "2027-04-01", "endDate": "2027-04-30"},
        {"code": "FINAL_CHECK", "name": "定稿与评阅", "startDate": "2027-05-01", "endDate": "2027-05-31"},
        {"code": "DEFENSE", "name": "答辩与成绩", "startDate": "2027-06-01", "endDate": "2027-06-20"},
    ]
    batch.last_transition_at = REFERENCE_NOW
    batch.last_transition_by = "毕业设计管理办公室"
    batch.transition_reason = "2027届按学生选题确认进度进入并行早期指导"

    students = list(db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.is_deleted.is_(False),
    ).order_by(GraduationStudent.student_no)).all())
    if len(students) != EXPECTED_STUDENTS:
        raise RuntimeError(f"毕设学生基数异常 expected={EXPECTED_STUDENTS} actual={len(students)}")

    mentors = {
        int(mid): (teacher_no, teacher_name)
        for mid, teacher_no, teacher_name in db.execute(select(
            GraduationMentor.id, GraduationMentor.teacher_no, GraduationMentor.teacher_name,
        ).where(
            GraduationMentor.tenant_id == tenant_id,
            GraduationMentor.is_deleted.is_(False),
        )).all()
    }

    assignment_rows = []
    guiding_students = []
    for index, student in enumerate(students, 1):
        mentor_id = int(student.mentor_id or 0)
        if mentor_id not in mentors:
            raise RuntimeError(f"毕设学生缺合法导师 student={student.student_no} mentor={student.mentor_id}")
        assignment_rows.append({
            "tenant_id": tenant_id,
            "gd_student_id": int(student.id),
            "mentor_id": mentor_id,
            "assign_source": "BATCH",
            "assign_reason": "2027届毕业设计按专业与导师容量统一分配",
            "status": "ACTIVE",
            "confirmed_by_mentor": True,
            "confirmed_at": datetime(2026, 8, 5, 17, 0) + timedelta(minutes=index % 180),
            "assigned_by": "二级学院毕业设计工作组",
            "assigned_at": datetime(2026, 8, 4, 9, 0) + timedelta(minutes=index % 360),
        })
        if student.stage == "GUIDING":
            if not student.topic_id or not student.topic_title:
                raise RuntimeError(f"GUIDING 学生未确定题目 student={student.student_no}")
            guiding_students.append(student)

    if len(guiding_students) != EXPECTED_GUIDING:
        raise RuntimeError(f"早期指导人数异常 expected={EXPECTED_GUIDING} actual={len(guiding_students)}")
    _bulk_insert(db, GraduationMentorAssignment, assignment_rows, chunk_size=1000)

    taskbook_rows = []
    for index, student in enumerate(guiding_students, 1):
        confirmed = index <= EXPECTED_TASKBOOK_CONFIRMED
        taskbook_rows.append({
            "tenant_id": tenant_id,
            "gd_student_id": int(student.id),
            "mentor_id": int(student.mentor_id),
            "objective": f"围绕《{student.topic_title}》完成岗位需求分析、方案设计、实践验证与成果总结。",
            "content": "完成资料调研、需求分析、方案设计、实践实现、测试验证及毕业设计文档整理。",
            "progress_plan": "8-9月选题与任务书；10月至次年3月过程指导；4月中期；5月定稿评阅；6月答辩。",
            "outcome_requirement": "形成可验收的实践成果、过程记录、毕业设计文档和答辩材料。",
            "taskbook_version": 1,
            "status": "CONFIRMED" if confirmed else "PENDING_CONFIRM",
            "history_json": [],
            "issued_by": student.advisor_name,
            "issued_at": datetime(2026, 8, 11, 9, 0) + timedelta(minutes=index % 480),
            "confirmed_at": datetime(2026, 8, 12, 8, 30) + timedelta(minutes=index % 600) if confirmed else None,
        })
    _bulk_insert(db, GraduationTaskBook, taskbook_rows, chunk_size=1000)

    proposal_rows = []
    for index, student in enumerate(guiding_students[:EXPECTED_PROPOSALS], 1):
        if index <= EXPECTED_PROPOSAL_APPROVED:
            status = "APPROVED"
        elif index <= EXPECTED_PROPOSAL_APPROVED + EXPECTED_PROPOSAL_PENDING:
            status = "PENDING_REVIEW"
        else:
            status = "REJECTED"
        proposal_rows.append({
            "tenant_id": tenant_id,
            "gd_student_id": int(student.id),
            "version": "v1",
            "is_resubmit": False,
            "submit_at": datetime(2026, 8, 12, 10, 0) + timedelta(minutes=index % 540),
            "background": f"围绕《{student.topic_title}》对应的专业岗位任务开展背景调研和需求分析。",
            "plan": "按调研、方案、实现、验证、文档五个阶段推进，过程接受导师指导。",
            "outcome": "形成可展示、可验收的专业实践成果及完整过程材料。",
            "attachments_json": ["proposal-outline-v1"],
            "status": status,
            "active_key": f"pending:{int(student.id)}" if status == "PENDING_REVIEW" else None,
            "reviewer": student.advisor_name if status != "PENDING_REVIEW" else None,
            "review_comment": "选题边界清晰，前期方案可进入持续指导。" if status == "APPROVED" else ("请补充岗位调研证据和阶段验收指标后重新提交。" if status == "REJECTED" else None),
            "review_time": datetime(2026, 8, 13, 8, 0) + timedelta(minutes=index % 60) if status != "PENDING_REVIEW" else None,
        })
    _bulk_insert(db, GraduationProposal, proposal_rows, chunk_size=1000)

    guidance_rows = []
    for index, student in enumerate(guiding_students[:EXPECTED_GUIDANCE], 1):
        guidance_rows.append({
            "tenant_id": tenant_id,
            "gd_student_id": int(student.id),
            "mentor_id": int(student.mentor_id),
            "guidance_date": datetime(2026, 8, 12, 14, 0) + timedelta(minutes=index % 420),
            "method": "OFFLINE" if index % 3 == 0 else "ONLINE",
            "content": "完成第一次任务书/选题范围核对，明确岗位场景、成果边界和下阶段调研任务。",
            "issues": "需持续补充企业或真实业务场景证据，避免课题范围过大。" if index % 5 == 0 else None,
            "attachments_json": [],
        })
    _bulk_insert(db, GraduationGuidance, guidance_rows, chunk_size=1000)
    db.commit()
    return validate_school_graduation_process_20k(db, tenant_id)


def validate_school_graduation_process_20k(db, tenant_id: int) -> dict:
    from app.models import (
        GraduationArchiveRecord, GraduationBatch, GraduationDefenseGroup, GraduationFinal,
        GraduationGrade, GraduationGuidance, GraduationMentorAssignment, GraduationMidterm,
        GraduationPlagiarismCheck, GraduationProposal, GraduationReview, GraduationStudent,
        GraduationTaskBook,
    )

    batch = db.scalars(select(GraduationBatch).where(
        GraduationBatch.tenant_id == tenant_id,
        GraduationBatch.batch_no == "GD-2027",
        GraduationBatch.is_deleted.is_(False),
    )).first()
    if batch is None:
        raise RuntimeError("GD-2027 毕设批次不存在")
    stages = {row.get("code"): row for row in (batch.stage_config or [])}
    timeline_ok = (
        (stages.get("TOPIC_SELECTING") or {}).get("startDate") == "2026-08-01"
        and (stages.get("TOPIC_SELECTING") or {}).get("endDate") == "2026-09-10"
        and (stages.get("GUIDING") or {}).get("startDate") == "2026-08-11"
    )

    report = {
        "mentorAssignments": _count(db, GraduationMentorAssignment, tenant_id, GraduationMentorAssignment.status == "ACTIVE"),
        "taskBooks": _count(db, GraduationTaskBook, tenant_id),
        "taskBooksConfirmed": _count(db, GraduationTaskBook, tenant_id, GraduationTaskBook.status == "CONFIRMED"),
        "taskBooksPending": _count(db, GraduationTaskBook, tenant_id, GraduationTaskBook.status == "PENDING_CONFIRM"),
        "proposals": _count(db, GraduationProposal, tenant_id),
        "proposalsApproved": _count(db, GraduationProposal, tenant_id, GraduationProposal.status == "APPROVED"),
        "proposalsPending": _count(db, GraduationProposal, tenant_id, GraduationProposal.status == "PENDING_REVIEW"),
        "proposalsRejected": _count(db, GraduationProposal, tenant_id, GraduationProposal.status == "REJECTED"),
        "guidanceRecords": _count(db, GraduationGuidance, tenant_id),
        "guidingStudents": _count(db, GraduationStudent, tenant_id, GraduationStudent.stage == "GUIDING"),
        "timelineAligned": timeline_ok,
        "midterms": _count(db, GraduationMidterm, tenant_id),
        "finalSubmissions": _count(db, GraduationFinal, tenant_id),
        "plagiarismChecks": _count(db, GraduationPlagiarismCheck, tenant_id),
        "reviews": _count(db, GraduationReview, tenant_id),
        "defenseGroups": _count(db, GraduationDefenseGroup, tenant_id),
        "grades": _count(db, GraduationGrade, tenant_id),
        "archives": _count(db, GraduationArchiveRecord, tenant_id),
    }
    expected = {
        "mentorAssignments": EXPECTED_ASSIGNMENTS,
        "taskBooks": EXPECTED_TASKBOOKS,
        "taskBooksConfirmed": EXPECTED_TASKBOOK_CONFIRMED,
        "taskBooksPending": EXPECTED_TASKBOOK_PENDING,
        "proposals": EXPECTED_PROPOSALS,
        "proposalsApproved": EXPECTED_PROPOSAL_APPROVED,
        "proposalsPending": EXPECTED_PROPOSAL_PENDING,
        "proposalsRejected": EXPECTED_PROPOSAL_REJECTED,
        "guidanceRecords": EXPECTED_GUIDANCE,
        "guidingStudents": EXPECTED_GUIDING,
        "timelineAligned": True,
        "midterms": 0,
        "finalSubmissions": 0,
        "plagiarismChecks": 0,
        "reviews": 0,
        "defenseGroups": 0,
        "grades": 0,
        "archives": 0,
    }
    mismatches = {key: {"expected": expected[key], "actual": report[key]} for key in expected if report[key] != expected[key]}
    if mismatches:
        raise RuntimeError(f"20K 毕设早期过程验收失败: {mismatches}")

    student_ids = {int(value) for (value,) in db.execute(select(GraduationStudent.id).where(
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.is_deleted.is_(False),
    )).all()}
    invalid_refs = 0
    for model in (GraduationMentorAssignment, GraduationTaskBook, GraduationProposal, GraduationGuidance):
        for value, in db.execute(select(model.gd_student_id).where(
            model.tenant_id == tenant_id,
            model.is_deleted.is_(False),
        )).all():
            if int(value) not in student_ids:
                invalid_refs += 1
    report["invalidStudentReferences"] = invalid_refs
    if invalid_refs:
        raise RuntimeError(f"20K 毕设过程存在孤立学生引用: {invalid_refs}")

    report["passed"] = True
    return report
