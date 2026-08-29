"""007 教务核心流程演示数据：选课、排课、考务、成绩、学籍、教材与归档。"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256

from sqlalchemy import func, select


NOW = datetime(2026, 8, 28, 10, 30)
MARKER = "007-AA-CORE-2026"


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _one(db, model, tenant_id: int, **where):
    terms = [model.tenant_id == tenant_id]
    if hasattr(model, "is_deleted"):
        terms.append(model.is_deleted.is_(False))
    terms.extend(getattr(model, key) == value for key, value in where.items())
    return db.scalars(select(model).where(*terms)).first()


def _put(db, model, tenant_id: int, key: dict, values: dict):
    row = _one(db, model, tenant_id, **key)
    if row is None:
        row = model(tenant_id=tenant_id, **key, **values)
        db.add(row)
        db.flush()
    return row


def _classes():
    from app.db.base import Base
    return {mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers}


def seed_academic_core_flows(db, tenant_id: int) -> dict:
    from app.models import (
        AaArchiveBatch, AaClassroom, AaCourse, AaEvaluationResult, AaExamBatch, AaExamCourse,
        AaExamRoom, AaGradeRecord, AaGradeTask, AaProgram, AaScheduleBatch, AaScheduleItem,
        AaTeachingTask, AaTerm, AaTextbook, AaTextbookOrderBatch, AaTextbookOrderItem,
        AcademicGrade, AcademicStudent, SchoolClass, FileObject, Major, StudentProfile, User,
    )

    c = _classes()
    admin = _one(db, User, tenant_id, login_name="admin2")
    teacher = _one(db, User, tenant_id, login_name="teacher2")
    evidence = _one(db, FileObject, tenant_id, file_key="007-GOV-2026/leave-approval-evidence.md")
    current_term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == tenant_id, AaTerm.is_current.is_(True), AaTerm.is_deleted.is_(False),
    )).first()
    archived_term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == tenant_id, AaTerm.status == "ARCHIVED", AaTerm.is_deleted.is_(False),
    ).order_by(AaTerm.id.desc())).first()
    course = db.scalars(select(AaCourse).where(
        AaCourse.tenant_id == tenant_id, AaCourse.status == "ENABLED", AaCourse.is_deleted.is_(False),
    ).order_by(AaCourse.id)).first()
    task = db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.tenant_id == tenant_id, AaTeachingTask.is_deleted.is_(False),
    ).order_by(AaTeachingTask.id)).first()
    schedule = db.scalars(select(AaScheduleItem).where(
        AaScheduleItem.tenant_id == tenant_id, AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    ).order_by(AaScheduleItem.id)).first()
    exam_course = db.scalars(select(AaExamCourse).where(
        AaExamCourse.tenant_id == tenant_id, AaExamCourse.is_deleted.is_(False),
    ).order_by(AaExamCourse.id)).first()
    exam_batch = db.get(AaExamBatch, exam_course.batch_id) if exam_course else None
    exam_room = db.scalars(select(AaExamRoom).where(
        AaExamRoom.tenant_id == tenant_id, AaExamRoom.exam_course_id == (exam_course.id if exam_course else -1),
        AaExamRoom.is_deleted.is_(False),
    ).order_by(AaExamRoom.id)).first()
    grade_record = db.scalars(select(AaGradeRecord).where(
        AaGradeRecord.tenant_id == tenant_id, AaGradeRecord.acad_grade_id.is_not(None),
        AaGradeRecord.is_deleted.is_(False),
    ).order_by(AaGradeRecord.id)).first()
    grade_task = db.get(AaGradeTask, grade_record.task_id) if grade_record else None
    student = db.get(StudentProfile, grade_record.student_id) if grade_record else None
    acad_grade = db.get(AcademicGrade, grade_record.acad_grade_id) if grade_record else None
    acad_student = db.get(AcademicStudent, acad_grade.acad_student_id) if acad_grade else None
    major = db.get(Major, student.major_id) if student else None
    klass = db.get(SchoolClass, student.class_id) if student else None
    program = db.scalars(select(AaProgram).where(
        AaProgram.tenant_id == tenant_id, AaProgram.major_id == (major.id if major else -1),
        AaProgram.is_deleted.is_(False),
    ).order_by(AaProgram.id.desc())).first()
    if not all((admin, teacher, evidence, current_term, archived_term, course, task, schedule,
                exam_course, exam_batch, grade_record, grade_task, student, acad_grade,
                acad_student, major, klass, program)):
        raise RuntimeError("007 教务核心链前置业务事实不足")

    # 选课：开放批次、两轮、课程供给和已选/退选/候补三种真实状态。
    selection_batch = _put(db, c["t_aa_selection_batch"], tenant_id, {
        "term_id": current_term.id, "batch_name": "2026-2027 学年第一学期公共选修课选课"
    }, {
        "select_start_at": NOW - timedelta(days=2), "select_end_at": NOW + timedelta(days=5),
        "apply_scope_json": json.dumps({"grades": ["2024", "2025", "2026"], "majorIds": []}),
        "rule_json": json.dumps({"maxCredits": 4, "allowRetake": False, "dropDeadlineHours": 48}),
        "remark": "第一轮正选、第二轮补退选；容量按明细实时计算。", "status": "OPEN",
    })
    round1 = _put(db, c["t_aa_selection_round"], tenant_id, {
        "batch_id": selection_batch.id, "round_no": 1
    }, {"round_name": "第一轮正选", "mode": "NORMAL", "start_at": NOW - timedelta(days=2),
        "end_at": NOW + timedelta(days=1), "allow_enroll": True, "allow_drop": True, "status": "OPEN"})
    _put(db, c["t_aa_selection_round"], tenant_id, {"batch_id": selection_batch.id, "round_no": 2}, {
        "round_name": "第二轮补退选", "mode": "SUPPLEMENT", "start_at": NOW + timedelta(days=2),
        "end_at": NOW + timedelta(days=5), "allow_enroll": True, "allow_drop": True, "status": "DRAFT",
    })
    selection_course = _put(db, c["t_aa_selection_course"], tenant_id, {
        "batch_id": selection_batch.id, "course_id": course.id
    }, {
        "course_name": course.course_name, "teaching_task_id": task.id, "teacher_key": task.teacher_key,
        "teacher_name": task.teacher_name, "credit": course.credit, "capacity": 60, "min_capacity": 20,
        "selected_count": 1, "status": "OPEN",
    })
    selection_students = list(db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id, StudentProfile.status == "ACTIVE",
        StudentProfile.is_deleted.is_(False),
    ).order_by(StudentProfile.student_no).limit(3)).all())
    for idx, (sp, status) in enumerate(zip(selection_students, ("SELECTED", "DROPPED", "PENDING_LOTTERY")), 1):
        _put(db, c["t_aa_selection_record"], tenant_id, {
            "batch_id": selection_batch.id, "selection_course_id": selection_course.id, "student_id": sp.id
        }, {
            "course_id": course.id, "course_name": course.course_name, "credit": course.credit,
            "student_no": sp.student_no, "student_name": sp.real_name,
            "enrolled_at": NOW - timedelta(hours=idx * 2),
            "dropped_at": NOW - timedelta(hours=1) if status == "DROPPED" else None,
            "adjust_reason": "与必修课临时调课冲突，学生在截止前主动退选。" if status == "DROPPED" else None,
            "re_enroll": False, "round_id": round1.id, "status": status,
        })

    # 排课与资源：发布留痕、在办调课、预约、实验室设备和维修闭环。
    schedule_batch = db.get(AaScheduleBatch, schedule.batch_id)
    _put(db, c["t_aa_schedule_publish"], tenant_id, {"batch_id": schedule.batch_id, "action": "PUBLISH"}, {
        "term_id": current_term.id, "operator_name": admin.real_name, "notified_count": 1280,
        "note": "2026 秋季课表首版发布，教师与学生消息回执已生成。",
    })
    _put(db, c["t_aa_schedule_change"], tenant_id, {"origin_item_id": schedule.id, "status": "COLLEGE_REVIEW"}, {
        "term_id": current_term.id, "batch_id": schedule.batch_id, "task_id": schedule.task_id,
        "change_type": "ADJUST", "course_name": schedule.course_name, "class_id": schedule.class_id,
        "class_name": schedule.class_name, "teacher_key": schedule.teacher_key, "teacher_name": schedule.teacher_name,
        "origin_weekday": schedule.weekday, "origin_slot_no": schedule.slot_no,
        "origin_start_week": schedule.start_week, "origin_end_week": schedule.end_week,
        "origin_week_parity": schedule.week_parity, "origin_classroom": schedule.classroom_text,
        "target_weekday": 4 if schedule.weekday != 4 else 5, "target_slot_no": 3,
        "target_start_week": 3, "target_end_week": 3, "target_week_parity": "ALL",
        "target_classroom": "产教融合楼 B203", "makeup_plan": "仅调整第 3 周一次课，其他周次不变。",
        "reason": "任课教师参加省级教学能力比赛现场评审，申请单周调课。",
        "applicant_id": teacher.id, "current_node": "COLLEGE_REVIEW",
    })
    classroom = db.get(AaClassroom, schedule.classroom_id) if schedule.classroom_id else db.scalars(select(AaClassroom).where(
        AaClassroom.tenant_id == tenant_id, AaClassroom.is_deleted.is_(False))).first()
    _put(db, c["t_aa_classroom_booking"], tenant_id, {
        "classroom_id": classroom.id, "booking_date": date(2026, 9, 3), "slot_no": 7
    }, {"classroom_text": schedule.classroom_text, "purpose": "省赛项目集中答疑",
        "applicant_key": task.teacher_key, "applicant_name": task.teacher_name,
        "review_reason": "晚间时段无课程冲突，容量满足。", "status": "APPROVED"})
    lab = _put(db, c["t_aa_lab_resource"], tenant_id, {"lab_code": "YK-LAB-AI-01"}, {
        "lab_name": "人工智能综合实训室", "building_name": "产教融合楼", "capacity": 56,
        "lab_type": "AI_COMPUTING", "responsible_name": "罗启明", "responsible_key": "sbx_t0385",
        "remark": "用于数据分析、模型训练和专业综合实训。", "status": "AVAILABLE",
    })
    _put(db, c["t_aa_lab_booking"], tenant_id, {"lab_id": lab.id, "booking_date": date(2026, 9, 4), "slot_no": 5}, {
        "lab_text": lab.lab_name, "purpose": "课程综合项目环境验收", "applicant_key": task.teacher_key,
        "applicant_name": task.teacher_name, "review_reason": "资源与软件镜像均已确认。", "status": "APPROVED",
    })
    equipment = _put(db, c["t_aa_equipment"], tenant_id, {"equipment_code": "YK-EQ-AI-001"}, {
        "equipment_name": "边缘计算教学实训箱", "spec_model": "YK-EdgeLab V2", "quantity": 24,
        "owner_kind": "LAB", "owner_id": lab.id, "owner_label": lab.lab_name,
        "responsible_name": lab.responsible_name, "purchase_date": date(2025, 8, 20),
            "status": "IDLE", "remark": "每两名学生一套，用于部署与联调。",
    })
    _put(db, c["t_aa_resource_repair"], tenant_id, {"resource_kind": "EQUIPMENT", "resource_id": equipment.id}, {
        "resource_label": equipment.equipment_name, "fault_desc": "3 号实训箱网络接口接触不稳定。",
        "reporter_key": task.teacher_key, "reporter_name": task.teacher_name,
        "repair_note": "更换接口模块并完成连续 2 小时压力测试。", "status": "DONE",
        "resolved_at": NOW - timedelta(days=1),
    })

    # 考务：巡考、监考锁、违纪事件、缓考与审计留痕。
    _put(db, c["t_aa_exam_teacher_lock"], tenant_id, {"teacher_key": task.teacher_key}, {})
    _put(db, c["t_aa_exam_patrol"], tenant_id, {"batch_id": exam_batch.id, "teacher_key": task.teacher_key}, {
        "teacher_name": task.teacher_name, "patrol_date": "2026-06-25", "start_time": "14:20",
        "end_time": "16:20", "area_scope_json": json.dumps(["教学楼 A 区", "教学楼 B 区"], ensure_ascii=False),
        "status": "FINISHED",
    })
    incident = _put(db, c["t_aa_exam_incident"], tenant_id, {
        "exam_course_id": exam_course.id, "student_id": student.id
    }, {
        "exam_room_id": exam_room.id if exam_room else None, "student_no": student.student_no,
        "student_name": student.real_name, "incident_type": "ABSENT",
        "description": "学生未按时到场；监考教师完成缺考登记并联动学业风险提醒。",
        "evidence_file_ids": json.dumps([evidence.id]), "recorded_by": task.teacher_name,
        "recorded_at": datetime(2026, 6, 25, 14, 42), "risk_alert_sent": True,
        "discipline_case_ref": None, "status": "ACTIVE",
    })
    _put(db, c["t_aa_exam_audit_trail"], tenant_id, {"biz_type": "EXAM_INCIDENT", "biz_id": str(incident.id), "action": "EXAM_INCIDENT_CLOSE"}, {
        "operator": "考务管理员", "role_name": "教务处", "detail": "缺考事实、考场签字和风险提醒均已核验闭环。",
        "before_val": "ACTIVE", "after_val": "RISK_TRANSFERRED", "occurred_at": datetime(2026, 6, 26, 10),
    })
    _put(db, c["t_aa_deferred_exam"], tenant_id, {"student_id": selection_students[1].id, "exam_course_id": exam_course.id}, {
        "student_no": selection_students[1].student_no, "student_name": selection_students[1].real_name,
        "course_name": exam_course.course_name, "reason_type": "MEDICAL",
        "reason": "考试当日因急性肠胃炎就诊，申请参加下一批次缓考。",
        "material_file_ids": json.dumps([evidence.id]), "apply_at": datetime(2026, 6, 24, 21),
        "current_node": "COMPLETED", "next_batch_ref": "2026-2027-1-MAKEUP", "status": "APPROVED",
    })

    # 成绩：动态方案与分项、复查维持、变更驳回、认定退回、GPA 规则和受控策略绕行债务。
    scheme = _put(db, c["t_aa_grade_scheme_snapshot"], tenant_id, {"grade_task_id": grade_task.id}, {
        "scheme_version": 1,
        "scheme_json": json.dumps({"components": [{"code": "USUAL", "name": "过程考核", "weight": 30},
                                                    {"code": "FINAL", "name": "期末考核", "weight": 70}]}, ensure_ascii=False),
        "total_weight": 100, "status": "LOCKED", "locked_at": grade_task.submitted_at,
        "locked_by": grade_task.teacher_key,
    })
    for code, name, weight, score in (("USUAL", "过程考核", 30, grade_record.usual_score or 0),
                                      ("FINAL", "期末考核", 70, grade_record.final_score or 0)):
        _put(db, c["t_aa_grade_component_score"], tenant_id, {
            "grade_task_id": grade_task.id, "student_id": grade_record.student_id, "component_code": code
        }, {"grade_record_id": grade_record.id, "component_name": name, "weight": weight,
            "score": score, "weighted_score": round(score * weight / 100, 2), "scheme_version": scheme.scheme_version})
    _put(db, c["t_aa_grade_recheck"], tenant_id, {"acad_grade_id": acad_grade.id}, {
        "student_id": student.id, "student_no": student.student_no, "student_name": student.real_name,
        "course_name": acad_grade.course_name, "term": acad_grade.term, "original_score": acad_grade.score,
        "reason": "申请核对期末卷面加分题和总评合成过程。", "status": "UPHELD",
        "new_score": acad_grade.score, "review_note": "复核答卷、评分细则与分项权重，原成绩计算无误。",
        "reviewed_by": "成绩复核组", "reviewed_at": datetime(2026, 7, 8, 15),
    })
    _put(db, c["t_aa_grade_change_request"], tenant_id, {"grade_record_id": grade_record.id}, {
        "grade_task_id": grade_task.id, "student_id": student.id, "source": "TEACHER_REQUEST",
        "proposed_usual_score": grade_record.usual_score, "proposed_midterm_score": grade_record.midterm_score,
        "proposed_final_score": (grade_record.final_score or 0) + 2, "proposed_total_score": (grade_record.total_score or 0) + 1,
        "proposed_pass_status": grade_record.pass_status, "before_usual_score": grade_record.usual_score,
        "before_midterm_score": grade_record.midterm_score, "before_final_score": grade_record.final_score,
        "before_total_score": grade_record.total_score, "current_grade_id": acad_grade.id,
        "expected_grade_version": acad_grade.version,
        "reason": "教师复核时发现一道题疑似漏加步骤分，提交更正申请。",
        "status": "REJECTED", "decided_by": admin.id, "decided_at": datetime(2026, 7, 9, 16),
    })
    _put(db, c["t_aa_grade_recognition"], tenant_id, {"student_id": student.id, "target_course_id": course.id}, {
        "student_no": student.student_no, "student_name": student.real_name,
        "source_course_name": "企业网络技术认证课程", "source_score": 86, "source_credit": Decimal("2.0"),
        "source_origin": "校企认证学习中心", "target_course_name": course.course_name,
        "attachment_file_ids": json.dumps([evidence.id]),
        "evidence_manifest_json": json.dumps({"fileId": evidence.id, "ownerStudentId": student.id}),
        "evidence_manifest_hash": _digest(f"{MARKER}:recognition:{student.id}"),
        "reason": "申请以校企认证课程替代同类专业选修课程。",
        "review_reason": "认证课程学时不足，退回后可补充企业项目实践证明。", "reviewed_by": admin.real_name,
        "reviewed_at": NOW - timedelta(days=1), "status": "REJECTED",
    })
    _put(db, c["t_aa_gpa_point_policy"], tenant_id, {"policy_code": "YK-GPA-4.0"}, {
        "policy_version": 1, "active_scope_key": "ACTIVE", "scale_type": "BANDS",
        "linear_fail_score": 60, "linear_anchor_score": 60, "linear_divisor": 10,
        "bands_json": json.dumps([{"min": 90, "point": 4.0}, {"min": 80, "point": 3.0},
                                  {"min": 70, "point": 2.0}, {"min": 60, "point": 1.0}], ensure_ascii=False),
        "status": "ACTIVE", "activated_at": datetime(2026, 7, 1, 0),
        "remark": "007 正式演示 GPA 绩点换算政策，适用于 2026-2027 学年。",
    })
    _put(db, c["t_aa_grade_identity_head"], tenant_id, {"acad_student_id": acad_student.id, "course_code": course.course_code}, {
        "current_attempt_no": 1, "last_source_biz_type": "GRADE_PUBLISH", "last_allocated_at": grade_task.publish_at,
    })
    _put(db, c["t_aa_effective_grade_policy_bypass"], tenant_id, {"batch_no": f"{MARKER}-LEGACY-GRADE"}, {
        "source": "LEGACY_RECONCILIATION", "operator": admin.real_name,
        "debt_reason": "历史成绩导入时课程代码缺失，受控绕行后已补建成绩身份头并登记技术债。",
        "grade_count": 1, "started_at": datetime(2026, 7, 10, 9), "ended_at": datetime(2026, 7, 10, 9, 2),
    })

    # 补考、重修、免修：只新增流程事实，不改变 174,600 条基线成绩。
    failed_grade = db.scalars(select(AcademicGrade).where(
        AcademicGrade.tenant_id == tenant_id, AcademicGrade.pass_status == "FAILED",
        AcademicGrade.is_deleted.is_(False),
    ).order_by(AcademicGrade.id)).first() or acad_grade
    failed_student = db.get(AcademicStudent, failed_grade.acad_student_id)
    failed_profile = db.get(StudentProfile, failed_student.student_id)
    makeup_batch = _put(db, c["t_aa_makeup_batch"], tenant_id, {"batch_name": "2025-2026-2 学期期末补缓考"}, {
        "kind": "MAKEUP", "target_grades": "2024,2025", "term_id": archived_term.id,
        "term_code": f"{archived_term.year_code}-{archived_term.term_no}", "exam_batch_ref": exam_batch.id,
        "score_rule": "CAP60", "published_at": datetime(2026, 7, 15, 9),
        "remark": "覆盖不及格补考与经批准缓考学生，成绩已发布回写。", "status": "FINISHED",
    })
    _put(db, c["t_acad_makeup"], tenant_id, {"acad_student_id": failed_student.id, "batch_id": makeup_batch.id}, {
        "kind": "补考", "course_name": failed_grade.course_name, "term": failed_grade.term,
        "origin_score": failed_grade.score, "exam_date": "2026-08-20", "status": "FINISHED",
        "remind_count": 2, "record_status": "ACTIVE", "final_score": 60,
        "origin_grade_id": failed_grade.id, "source_biz_type": "MAKEUP_BATCH",
        "source_biz_id": str(makeup_batch.id), "course_id": course.id, "course_code": course.course_code,
        "course_version": course.version, "attempt_no": 2,
    })
    retake_apply = _put(db, c["t_aa_retake_apply"], tenant_id, {"student_id": failed_profile.id, "course_id": course.id}, {
        "student_no": failed_profile.student_no, "student_name": failed_profile.real_name,
        "acad_student_id": failed_student.id, "course_name": failed_grade.course_name,
        "term_code": f"{current_term.year_code}-{current_term.term_no}",
        "reason": "补考后仍需系统巩固课程能力，申请跟班重修。", "retake_count": 1,
        "review_reason": "符合重修次数与学籍状态要求，已编入当前教学班。",
        "teaching_task_ref": task.id, "status": "ENROLLED",
    })
    _put(db, c["t_acad_retake"], tenant_id, {"acad_student_id": failed_student.id, "apply_id": retake_apply.id}, {
        "course_name": failed_grade.course_name, "retake_term": f"{current_term.year_code}-{current_term.term_no}",
        "reason": retake_apply.reason, "status": "IN_PROGRESS", "record_status": "ACTIVE",
    })
    _put(db, c["t_aa_exemption"], tenant_id, {"student_id": selection_students[2].id, "course_id": course.id}, {
        "student_no": selection_students[2].student_no, "student_name": selection_students[2].real_name,
        "course_name": course.course_name, "term_code": f"{current_term.year_code}-{current_term.term_no}",
        "college_id": selection_students[2].college_id, "teacher_key": task.teacher_key,
        "reason": "已取得同领域职业技能等级证书，申请免修但不免考。",
        "material_file_ids": json.dumps([evidence.id]), "current_node": "COLLEGE_REVIEW",
        "status": "COLLEGE_REVIEW", "archive_status": "NOT_ARCHIVED",
        "evidence_manifest_json": json.dumps({"fileId": evidence.id, "ownerStudentId": selection_students[2].id}),
        "evidence_manifest_hash": _digest(f"{MARKER}:exemption:{selection_students[2].id}"),
    })

    # 学籍、分流与班级：申请链存在，但不直接改写 20K 学生主档。
    direction = _put(db, c["t_aa_major_direction"], tenant_id, {"major_id": major.id, "code": f"{major.code}-AI"}, {
        "direction_name": f"{major.major_name}·智能应用方向", "status": "ACTIVE",
    })
    other_major = db.scalars(select(Major).where(
        Major.tenant_id == tenant_id, Major.id != major.id, Major.college_id == major.college_id,
        Major.is_deleted.is_(False),
    ).order_by(Major.id)).first() or major
    split_batch = _put(db, c["t_aa_major_split_batch"], tenant_id, {"batch_name": "2026 级专业方向分流"}, {
        "grade": "2026", "source_major_id": major.id, "max_choices": 2,
        "volunteer_start": NOW - timedelta(days=1), "volunteer_end": NOW + timedelta(days=7), "status": "OPEN",
    })
    for opt_major, capacity in ((major, 120), (other_major, 80)):
        _put(db, c["t_aa_major_split_option"], tenant_id, {"batch_id": split_batch.id, "major_id": opt_major.id}, {
            "major_name": opt_major.major_name, "capacity": capacity, "allocated_count": 0,
        })
    _put(db, c["t_aa_major_split_volunteer"], tenant_id, {"batch_id": split_batch.id, "student_id": selection_students[2].id}, {
        "student_no": selection_students[2].student_no, "student_name": selection_students[2].real_name,
        "choices_json": json.dumps([major.id, other_major.id]), "gpa_snapshot": Decimal("3.12"), "status": "PENDING",
    })
    fact = _put(db, c["t_aa_student_academic_fact"], tenant_id, {"student_id": student.id, "version_no": 1}, {
        "valid_from": student.enroll_date or datetime(2024, 9, 1), "valid_to": None,
        "student_status": student.student_status, "college_id": student.college_id,
        "major_id": student.major_id, "class_id": student.class_id, "grade": student.grade,
        "source_type": "BASELINE_IMPORT", "source_ref_id": str(student.id), "source_quality": "VERIFIED",
    })
    _put(db, c["t_aa_status_change"], tenant_id, {"student_id": student.id, "idempotency_key": f"{MARKER}:STATUS:{student.id}"}, {
        "change_type": "TRANSFER_MAJOR", "from_status": student.student_status, "to_status": student.student_status,
        "from_college_id": student.college_id, "from_major_id": student.major_id, "from_class_id": student.class_id,
        "to_college_id": student.college_id, "to_major_id": other_major.id, "to_class_id": None,
        "reason": "学生提交跨专业转入申请，因目标专业先修课程不足主动撤回。",
        "effective_date": date(2026, 9, 1), "term_code": f"{current_term.year_code}-{current_term.term_no}",
        "current_node": "CANCELLED", "status": "CANCELLED", "expected_student_version": student.version,
        "decision_version": 1,
    })
    _put(db, c["t_aa_program_transition_assessment"], tenant_id, {"student_id": student.id, "source_fact_id": fact.id}, {
        "source_fact_version": fact.version_no, "source_type": "STATUS_CHANGE", "source_ref_id": None,
        "from_major_id": student.major_id, "to_major_id": other_major.id, "target_class_id": None,
        "grade": student.grade, "from_program_id": program.id, "target_program_id": None,
        "decision": "REJECTED", "assessment_status": "COMPLETED",
        "evidence_json": json.dumps({"missingPrerequisites": [course.course_code], "studentVersion": student.version}),
        "assessed_at": NOW - timedelta(hours=4),
    })
    _put(db, c["t_aa_class_adjustment_request"], tenant_id, {"adjust_type": "MERGE", "from_class_ids": json.dumps([klass.id])}, {
        "to_class_id": klass.id, "reason": "模拟核验小班合并条件，不执行主档变更。",
        "check_result_json": json.dumps({"studentCount": 52, "capacity": klass.capacity, "canExecute": False}),
        "checked_at": NOW, "status": "CHECKED",
    })
    _put(db, c["t_aa_student_correction"], tenant_id, {"student_id": student.id, "field_key": "REAL_NAME"}, {
        "old_value": student.real_name, "new_value": student.real_name,
        "reason": "学生申请核对姓名生僻字，复核后确认主档无误。",
        "material_file_ids": json.dumps([evidence.id]), "status": "REJECTED",
        "review_note": "户籍证明与当前主档一致，无需更正。", "reviewed_at": NOW,
        "reviewed_by": admin.id,
    })

    # 等级考试、教师工作量与评价申诉。
    level_exam = _put(db, c["t_aa_level_exam"], tenant_id, {"exam_name": "2026 年下半年全国英语应用能力考试"}, {
        "category": "ENGLISH", "level": "A", "exam_date": date(2026, 12, 13),
        "fee": Decimal("30.00"), "reg_start": NOW - timedelta(days=3), "reg_end": NOW + timedelta(days=8),
        "pass_line": 60, "status": "OPEN",
    })
    _put(db, c["t_aa_level_exam_reg"], tenant_id, {"exam_id": level_exam.id, "student_id": student.id}, {
        "student_no": student.student_no, "student_name": student.real_name,
        "fee_status": "PAID", "status": "REGISTERED",
    })
    _put(db, c["t_aa_workload_declaration"], tenant_id, {"teacher_key": task.teacher_key, "category": "MARKING"}, {
        "teacher_name": task.teacher_name, "term_code": f"{archived_term.year_code}-{archived_term.term_no}",
        "hours": Decimal("12.0"), "description": "承担期末试卷评阅、复核与成绩归档。",
        "status": "APPROVED", "review_note": "工作量与考务分工、阅卷记录一致。",
        "reviewed_by": admin.real_name, "reviewed_at": datetime(2026, 7, 6, 10),
    })
    eval_result = db.scalars(select(AaEvaluationResult).where(
        AaEvaluationResult.tenant_id == tenant_id, AaEvaluationResult.is_deleted.is_(False),
    ).order_by(AaEvaluationResult.id)).first()
    _put(db, c["t_aa_evaluation_appeal"], tenant_id, {"result_id": eval_result.id}, {
        "teacher_key": eval_result.teacher_key, "reason": "申请核对同行评价任务是否包含跨专业课程。",
        "review_reason": "复核任务范围无误，原综合评价结果维持。", "current_node": "RESOLVED",
        "status": "RESOLVED",
    })

    # 教材发放：从真实征订批次、到书明细和学生主档生成签收与费用来源明细。
    order_item = db.scalars(select(AaTextbookOrderItem).join(
        AaTextbookOrderBatch, AaTextbookOrderBatch.id == AaTextbookOrderItem.order_batch_id
    ).where(
        AaTextbookOrderItem.tenant_id == tenant_id,
        AaTextbookOrderItem.arrived_qty > 0,
        AaTextbookOrderItem.is_deleted.is_(False),
    ).order_by(AaTextbookOrderItem.id)).first()
    order_batch = db.get(AaTextbookOrderBatch, order_item.order_batch_id)
    textbook = db.get(AaTextbook, order_item.textbook_id)
    dist_batch = _put(db, c["t_aa_textbook_distribution_batch"], tenant_id, {
        "order_batch_id": order_batch.id, "class_id": klass.id
    }, {"class_name": klass.class_name, "started_at": NOW - timedelta(days=1), "status": "DISTRIBUTING"})
    for idx, sp in enumerate(selection_students[:2]):
        status = "RECEIVED" if idx == 0 else "EXCLUDED"
        record = _put(db, c["t_aa_textbook_distribution_record"], tenant_id, {
            "batch_id": dist_batch.id, "student_id": sp.id, "textbook_id": textbook.id
        }, {"textbook_name": textbook.name, "qty": 1,
            "received_at": NOW - timedelta(hours=3) if status == "RECEIVED" else None,
            "received_by": sp.real_name if status == "RECEIVED" else None,
            "exclude_reason": "学生已持有同版次教材并经任课教师核验。" if status == "EXCLUDED" else None,
            "status": status})
        _put(db, c["t_aa_textbook_fee_ledger"], tenant_id, {"distribution_record_id": record.id}, {
            "student_id": sp.id, "textbook_name": textbook.name, "amount": textbook.unit_price,
            "paid_amount": textbook.unit_price if status == "RECEIVED" else Decimal("0.00"),
            "paid_at": NOW - timedelta(hours=2) if status == "RECEIVED" else None,
            "waive_reason": "未领教材，不生成应收。" if status == "EXCLUDED" else None,
            "status": "PAID" if status == "RECEIVED" else "WAIVED",
        })

    # 当前学期真实试点保留 RUNNING/阻塞态；历史归档追加不可变 manifest 和驳回更正案。
    pilot = _put(db, c["t_aa_semester_pilot"], tenant_id, {"term_id": current_term.id}, {
        "term_code": f"{current_term.year_code}-{current_term.term_no}", "pilot_name": "007 真实学校完整学期运行试点",
        "status": "RUNNING", "purpose": "以真实业务明细验证开学、教学、考务、成绩、归档六阶段闭环。",
        "real_data_confirmed": True, "check_run_no": 1, "passed_stage_count": 1, "blocker_count": 1,
        "latest_evidence_hash": _digest(f"{MARKER}:pilot:1"), "latest_checked_at": NOW,
    })
    for code, name, passed, blockers, conclusion in (
        ("OPENING", "开学准备", True, 0, "学籍注册、课表与教材到书数据均来自正式业务表。"),
        ("TEACHING", "教学运行", False, 1, "一笔调课申请正在学院审核，完成后可通过本阶段。"),
    ):
        evidence_json = json.dumps({"termId": current_term.id, "stage": code, "realData": True}, ensure_ascii=False)
        _put(db, c["t_aa_semester_pilot_checkpoint"], tenant_id, {
            "pilot_id": pilot.id, "run_no": 1, "stage_code": code
        }, {"stage_name": name, "passed": passed, "blocker_count": blockers, "warning_count": 0,
            "conclusion": conclusion, "evidence_json": evidence_json,
            "evidence_hash": _digest(evidence_json), "checked_at": NOW, "checked_by": admin.real_name})
    archive_batch = db.scalars(select(AaArchiveBatch).where(
        AaArchiveBatch.tenant_id == tenant_id, AaArchiveBatch.status == "ARCHIVED",
        AaArchiveBatch.is_deleted.is_(False),
    ).order_by(AaArchiveBatch.id.desc())).first()
    domain_counts = {"STUDENT": 13000, "REGISTRATION": 33000, "TEACHING_TASK": 1792,
                     "SCHEDULE": 1792, "EXAM": 1024, "GRADE": 52000}
    manifest_payload = json.dumps(domain_counts, sort_keys=True)
    manifest_v1 = _put(db, c["t_aa_archive_manifest"], tenant_id, {"archive_batch_id": archive_batch.id, "version_no": 1}, {
        "term_id": archive_batch.term_id, "domain_counts_json": json.dumps(domain_counts),
        "domain_hashes_json": json.dumps({key: _digest(f"{archive_batch.id}:{key}:{value}") for key, value in domain_counts.items()}),
        "max_ids_json": json.dumps({"grade": grade_record.id, "exam": exam_course.id}),
        "manifest_hash": _digest(manifest_payload), "reason": "历史学期十三域完整性检查通过后正式封存。",
        "archived_at": archive_batch.archived_at or datetime(2026, 7, 20, 16), "archived_by": admin.id,
    })
    _put(db, c["t_aa_post_archive_correction_case"], tenant_id, {
        "archive_batch_id": archive_batch.id, "correction_no": 1
    }, {"business_type": "GRADE", "target_ref": f"acadGrade:{acad_grade.id}",
        "reason": "教师申请在归档后更正一道题步骤分。",
        "correction_json": json.dumps({"before": acad_grade.score, "after": (acad_grade.score or 0) + 1}),
        "evidence_manifest": json.dumps({"fileId": evidence.id, "sha256": _digest(str(evidence.id))}),
        "risk_level": "HIGH", "rejected_by": admin.id, "rejected_at": NOW,
        "reject_reason": "现有证据不足以证明原评分错误，维持归档事实。", "status": "REJECTED",
    })
    applied_case = _one(db, c["t_aa_post_archive_correction_case"], tenant_id,
                        archive_batch_id=archive_batch.id, correction_no=2)
    if applied_case is None:
        correction_record = db.scalars(select(AaGradeRecord).join(
            AcademicGrade, AcademicGrade.id == AaGradeRecord.acad_grade_id
        ).where(
            AaGradeRecord.tenant_id == tenant_id, AaGradeRecord.id != grade_record.id,
            AaGradeRecord.is_deleted.is_(False), AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.active_record_key.is_not(None), AcademicGrade.is_deleted.is_(False),
        ).order_by(AaGradeRecord.id)).first()
        if correction_record is None:
            raise RuntimeError("007 教务更正链缺少可追加版本的正式成绩")
        original_grade = db.get(AcademicGrade, correction_record.acad_grade_id)
        correction_student = db.get(StudentProfile, correction_record.student_id)
        correction_task = db.get(AaGradeTask, correction_record.task_id)
        new_score = min(100, int(original_grade.score or 0) + 1)
        approved_request = _put(db, c["t_aa_grade_change_request"], tenant_id, {
            "grade_record_id": correction_record.id
        }, {"grade_task_id": correction_record.task_id, "student_id": correction_record.student_id,
            "source": "TEACHER_REQUEST", "proposed_usual_score": correction_record.usual_score,
            "proposed_midterm_score": correction_record.midterm_score,
            "proposed_final_score": min(100, int(correction_record.final_score or 0) + 1),
            "proposed_total_score": new_score, "proposed_pass_status": "PASSED" if new_score >= 60 else "FAILED",
            "before_usual_score": correction_record.usual_score, "before_midterm_score": correction_record.midterm_score,
            "before_final_score": correction_record.final_score, "before_total_score": correction_record.total_score,
            "current_grade_id": original_grade.id, "expected_grade_version": original_grade.version,
            "reason": f"{MARKER}：复核确认一道客观题录入时少计 1 分，申请归档后正式更正。",
            "status": "APPROVED", "decided_by": str(admin.id), "decided_at": NOW})
        original_grade.record_status = "SUPERSEDED"
        original_grade.void_reason = f"由成绩更正单 {approved_request.id} 追加新版本"
        original_grade.active_record_key = None
        db.flush()
        corrected_grade = AcademicGrade(
            tenant_id=tenant_id, acad_student_id=original_grade.acad_student_id,
            course_name=original_grade.course_name, term=original_grade.term, nature=original_grade.nature,
            credit_value=original_grade.credit_value, score=new_score,
            pass_status="PASSED" if new_score >= 60 else "FAILED", exam_type=original_grade.exam_type,
            record_status="ACTIVE", source="CHANGE", course_id=original_grade.course_id,
            course_code=original_grade.course_code, course_version=original_grade.course_version,
            attempt_no=original_grade.attempt_no, grade_task_id=original_grade.grade_task_id,
            grade_record_id=original_grade.grade_record_id, source_biz_type="GRADE_CHANGE_REQUEST",
            source_biz_id=approved_request.id, teaching_task_id=original_grade.teaching_task_id,
            teaching_class_id=original_grade.teaching_class_id, roster_version_id=original_grade.roster_version_id,
            effective_policy_code=original_grade.effective_policy_code,
            effective_policy_version=original_grade.effective_policy_version,
            effective_attempt_strategy=original_grade.effective_attempt_strategy,
            pass_line_snapshot=original_grade.pass_line_snapshot, active_record_key=correction_record.id,
            gpa_point=original_grade.gpa_point, gpa_policy_code=original_grade.gpa_policy_code,
            gpa_policy_version=original_grade.gpa_policy_version,
        )
        db.add(corrected_grade); db.flush()
        correction = _put(db, c["t_aa_grade_correction"], tenant_id, {
            "source_type": "CHANGE_REQUEST", "source_ref_id": approved_request.id
        }, {"recheck_id": None, "original_grade_id": original_grade.id,
            "corrected_grade_id": corrected_grade.id, "before_score": original_grade.score,
            "after_score": corrected_grade.score, "pass_line": original_grade.pass_line_snapshot or 60,
            "rule_snapshot_json": json.dumps({"policy": original_grade.effective_policy_code,
                                               "version": original_grade.effective_policy_version,
                                               "archiveBatchId": archive_batch.id}),
            "reason": approved_request.reason, "operator": admin.real_name, "effective_at": NOW,
            "status": "ACTIVE"})
        applied_case = _put(db, c["t_aa_post_archive_correction_case"], tenant_id, {
            "archive_batch_id": archive_batch.id, "correction_no": 2
        }, {"business_type": "GRADE", "target_ref": f"acadGrade:{original_grade.id}",
            "reason": approved_request.reason,
            "correction_json": json.dumps({"beforeGradeId": original_grade.id,
                                           "afterGradeId": corrected_grade.id,
                                           "beforeScore": original_grade.score, "afterScore": corrected_grade.score}),
            "evidence_manifest": json.dumps({"fileId": evidence.id, "studentId": correction_student.id,
                                             "gradeTaskId": correction_task.id}),
            "risk_level": "HIGH", "second_approved_by": admin.id, "applied_at": NOW,
            "official_fact_type": "AA_GRADE_CORRECTION", "official_fact_id": correction.id,
            "status": "APPLIED"})
        manifest_v2_payload = json.dumps({"v1": manifest_v1.manifest_hash,
                                          "correctionId": correction.id,
                                          "activeGradeId": corrected_grade.id}, sort_keys=True)
        manifest_v2 = _put(db, c["t_aa_archive_manifest"], tenant_id, {
            "archive_batch_id": archive_batch.id, "version_no": 2
        }, {"term_id": archive_batch.term_id, "domain_counts_json": json.dumps(domain_counts),
            "domain_hashes_json": json.dumps({**{key: _digest(f"{archive_batch.id}:{key}:{value}")
                                                    for key, value in domain_counts.items()},
                                               "GRADE_CORRECTION": _digest(manifest_v2_payload)}),
            "max_ids_json": json.dumps({"grade": corrected_grade.id, "exam": exam_course.id}),
            "manifest_hash": _digest(manifest_v2_payload),
            "reason": "双人复核通过的归档后成绩更正；追加 V2 清单，不覆盖 V1。",
            "supersedes_id": manifest_v1.id, "archived_at": NOW, "archived_by": admin.id})
        applied_case.resulting_manifest_id = manifest_v2.id

    # 毕业资格按 2027 届当前时间点做正式预审：材料不足形成“延期结论”；一张错误预生成
    # 的结业证已在未签发前作废，既覆盖异常处置，也不伪造已经毕业的学生。
    grad_batch = _put(db, c["t_aa_graduation_audit_batch"], tenant_id, {
        "batch_name": "2027 届毕业资格第一次正式预审"
    }, {"grade_year": "2027", "major_id": major.id,
        "scope_json": json.dumps({"grade": "2024", "majorId": major.id, "phase": "PRECHECK"}),
        "status": "REVIEWING", "generate_at": NOW - timedelta(days=2)})
    items = {
        "studentStatus": {"status": "PASS", "ref": f"student:{student.id}"},
        "credits": {"status": "FAIL", "obtained": float(acad_student.obtained_credits),
                    "required": float(acad_student.required_credits or program.total_credits)},
        "internship": {"status": "PASS", "ref": f"student:{student.id}"},
        "graduationDesign": {"status": "UNKNOWN", "reason": "当前届尚处于前期指导阶段"},
        "discipline": {"status": "PASS"}, "fees": {"status": "PASS"}, "physical": {"status": "UNKNOWN"},
    }
    grad_result = _put(db, c["t_aa_graduation_audit_result"], tenant_id, {
        "batch_id": grad_batch.id, "student_id": student.id
    }, {"item_results_json": json.dumps(items, ensure_ascii=False), "overall": "SYSTEM_ABNORMAL",
        "conclusion": "DELAYED", "rerun_count": 0,
        "review_note": "应修学分和毕业设计尚未完成，保持在籍并纳入下次自动复审。", "status": "DELAYED"})
    eval_payload = json.dumps({"studentId": student.id, "programId": program.id, "items": items}, ensure_ascii=False, sort_keys=True)
    eval_run = _put(db, c["t_aa_graduation_evaluation_run"], tenant_id, {
        "result_id": grad_result.id, "run_no": 1
    }, {"batch_id": grad_batch.id, "student_id": student.id, "program_id": program.id,
        "input_snapshot_json": eval_payload, "input_hash": _digest(eval_payload),
        "item_results_json": json.dumps(items, ensure_ascii=False), "overall": "SYSTEM_ABNORMAL",
        "evaluator_version": "STAGE_C3_V1"})
    _put(db, c["t_aa_graduation_decision_fact"], tenant_id, {
        "result_id": grad_result.id, "decision_no": 1
    }, {"batch_id": grad_batch.id, "student_id": student.id, "evaluation_run_id": eval_run.id,
        "conclusion": "DELAYED", "decision_at": NOW - timedelta(days=1), "decision_by": admin.id,
        "review_note": "预审证据显示学生尚未达到毕业条件；决定延期到下一轮复审。"})
    _put(db, c["t_aa_graduation_certificate"], tenant_id, {"cert_no": f"YK-VOID-2027-{student.student_no}"}, {
        "student_id": student.id, "student_no": student.student_no, "student_name": student.real_name,
        "audit_batch_id": grad_batch.id, "cert_type": "COMPLETION", "e_reg_no": None,
        "issue_year": "2027", "issue_date": None, "major_name": major.major_name,
        "void_reason": "批量预生成前置校验发现学生尚未达到结业条件，未签发即作废并保留审计证据。",
        "status": "VOIDED"})

    _put(db, c["t_acad_audit_trail"], tenant_id, {"biz_type": "ACADEMIC_CORE", "biz_id": MARKER, "action": "VALIDATE"}, {
        "operator": admin.real_name, "role_name": "教务处管理员",
        "detail": "选课、排课、考务、成绩、学籍、教材和归档关系校验通过。",
        "before_val": "PENDING", "after_val": "VALIDATED", "occurred_at": NOW,
    })
    db.commit()
    return validate_academic_core_flows(db, tenant_id)


def validate_academic_core_flows(db, tenant_id: int) -> dict:
    c = _classes()
    tables = (
        "t_aa_archive_manifest t_aa_class_adjustment_request t_aa_classroom_booking t_aa_deferred_exam "
        "t_aa_effective_grade_policy_bypass t_aa_equipment t_aa_evaluation_appeal t_aa_exam_audit_trail "
        "t_aa_exam_incident t_aa_exam_patrol t_aa_exam_teacher_lock t_aa_exemption t_aa_gpa_point_policy "
        "t_aa_grade_change_request t_aa_grade_component_score t_aa_grade_correction "
        "t_aa_grade_identity_head t_aa_grade_recheck "
        "t_aa_grade_recognition t_aa_grade_scheme_snapshot t_aa_graduation_audit_batch "
        "t_aa_graduation_audit_result t_aa_graduation_certificate t_aa_graduation_decision_fact "
        "t_aa_graduation_evaluation_run t_aa_lab_booking t_aa_lab_resource t_aa_level_exam "
        "t_aa_level_exam_reg t_aa_major_direction t_aa_major_split_batch t_aa_major_split_option "
        "t_aa_major_split_volunteer t_aa_makeup_batch t_aa_post_archive_correction_case "
        "t_aa_program_transition_assessment t_aa_resource_repair t_aa_retake_apply t_aa_schedule_change "
        "t_aa_schedule_publish t_aa_selection_batch t_aa_selection_course t_aa_selection_record "
        "t_aa_selection_round t_aa_semester_pilot t_aa_semester_pilot_checkpoint t_aa_status_change "
        "t_aa_student_academic_fact t_aa_student_correction t_aa_textbook_distribution_batch "
        "t_aa_textbook_distribution_record t_aa_textbook_fee_ledger t_aa_workload_declaration "
        "t_acad_audit_trail t_acad_makeup t_acad_retake"
    ).split()
    result = {}
    for table in tables:
        model = c[table]
        terms = [model.tenant_id == tenant_id]
        if hasattr(model, "is_deleted"):
            terms.append(model.is_deleted.is_(False))
        result[table] = int(db.scalar(select(func.count()).select_from(model).where(*terms)) or 0)
    result["passed"] = all(value > 0 for value in result.values())
    if not result["passed"]:
        missing = [key for key, value in result.items() if value == 0]
        raise RuntimeError(f"007 教务核心链校验失败: {missing}")
    return {"coveredCoreTables": len(tables), "emptyCoreTables": 0, "passed": True}
