"""007 毕业设计历史批次全流程演示链。

当前 GD-2027 继续保留选题/开题阶段；本文件使用独立的 GD-2026-HIST 批次承载
已完成、整改重交、延期答辩、风险关闭、成绩申诉和不可变归档证据。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
import json

from sqlalchemy import func, select, text


MARKER = "007-GD-2026-HIST"
FILED_AT = datetime(2026, 6, 25, 16, 30)


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


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def seed_graduation_historical_coverage(db, tenant_id: int) -> dict:
    from app.models import (
        FileObject,
        GraduationArchiveRecord,
        GraduationBatch,
        GraduationDefenseExpert,
        GraduationDefenseGroup,
        GraduationDefenseScore,
        GraduationFinal,
        GraduationGrade,
        GraduationGradeAppeal,
        GraduationGuidance,
        GraduationMentor,
        GraduationMentorAssignment,
        GraduationMidterm,
        GraduationPeerReview,
        GraduationPlagiarismCheck,
        GraduationProposal,
        GraduationReview,
        GraduationRiskCase,
        GraduationStudent,
        GraduationTaskBook,
        GraduationTopic,
        StudentProfile,
    )
    from app.models.graduation_extension import GraduationDefenseDelay, GraduationExcellentOutcome
    from app.models.graduation_material import GraduationMaterialBackfillCheckpoint
    from app.models.graduation_review_evidence import GraduationReviewFeedbackTable

    current_batch = _one(db, GraduationBatch, tenant_id, batch_no="GD-2027")
    evidence = _one(db, FileObject, tenant_id, file_key="007-GOV-2026/leave-approval-evidence.md")
    if current_batch is None or evidence is None:
        raise RuntimeError("007 毕设历史链缺少 GD-2027 基线或演示证据文件")

    batch = _put(db, GraduationBatch, tenant_id, {"batch_no": "GD-2026-HIST"}, {
        "batch_name": "2026 届毕业设计历史归档批次",
        "academic_year": "2025-2026", "grade_year": "2026届", "college_scope": "全校",
        "start_date": datetime(2025, 9, 1), "end_date": datetime(2026, 6, 25),
        "planned_count": 3, "status": "ARCHIVED", "previous_status": "CLOSED",
        "last_transition_at": FILED_AT, "last_transition_by": "教务处毕设管理员",
        "transition_reason": "答辩、成绩复核与材料核验全部完成",
        "archive_status": "ARCHIVED", "archived_at": FILED_AT, "archived_by": "档案管理员",
        "stage_config": [
            {"code": "TOPIC", "name": "选题", "startDate": "2025-09-01", "endDate": "2025-10-10"},
            {"code": "PROPOSAL", "name": "开题", "startDate": "2025-10-11", "endDate": "2025-11-20"},
            {"code": "MIDTERM", "name": "中期", "startDate": "2026-02-23", "endDate": "2026-03-20"},
            {"code": "DEFENSE", "name": "答辩", "startDate": "2026-05-25", "endDate": "2026-06-12"},
            {"code": "ARCHIVE", "name": "归档", "startDate": "2026-06-13", "endDate": "2026-06-25"},
        ],
        "rules_config": {"plagiarismThreshold": 30, "reviewPass": 60, "defenseJudges": 2,
                         "scoreWeights": {"advisor": 30, "reviewer": 30, "defense": 40}},
        "remark": "007 正式演示历史批次：所有统计均来自真实流程明细。",
        "last_risk_scan_at": datetime(2026, 6, 20, 8),
        "last_risk_scan_stats_json": {"open": 0, "closed": 2, "critical": 0},
    })

    current_students = list(db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.batch_id == current_batch.id,
        GraduationStudent.topic_id.is_not(None),
        GraduationStudent.mentor_id.is_not(None),
        GraduationStudent.is_deleted.is_(False),
    ).order_by(GraduationStudent.student_no).limit(3)).all())
    if len(current_students) != 3:
        raise RuntimeError("007 毕设历史链需要 3 名已有选题学生")

    historical_students = []
    topics = []
    for index, current in enumerate(current_students, 1):
        profile = db.get(StudentProfile, current.student_id)
        mentor = db.get(GraduationMentor, current.mentor_id)
        if profile is None or mentor is None:
            raise RuntimeError("007 毕设历史链学生或导师断链")
        title = (
            f"{profile.real_name}所在专业岗位业务数据质量分析与改进"
            if index == 1 else
            f"面向产教融合场景的{current.topic_title or '专业实践项目'}设计与验证"
        )
        topic = _put(db, GraduationTopic, tenant_id, {
            "batch_id": batch.id, "topic_no": f"GD26-HIST-{index:03d}"
        }, {
            "title": title, "source": "企业实践", "source_type": "ENTERPRISE",
            "advisor_name": mentor.teacher_name, "advisor_mentor_id": mentor.id,
            "college_id": current.college_id, "major_id": current.major_id,
            "major_name": mentor.major_name, "category": "实践应用类", "difficulty": "MEDIUM",
            "enterprise_name": "跃科产教融合实践基地",
            "requirements": "基于真实岗位问题完成需求调研、方案设计、实现验证和改进复盘。",
            "outcome": "毕业设计论文、可验证成果、答辩材料和完整过程证据包。",
            "skills": "需求分析、专业实践、数据分析、文档表达",
            "attachments_json": [evidence.id], "capacity": 1, "selected": 1,
            "review_status": "APPROVED", "review_comment": "选题边界清晰，实践工作量符合要求。",
            "status": "ARCHIVED", "students_json": [current.student_no],
            "archive_reason": "2026 届毕设完成后随批次归档", "archived_at": FILED_AT,
        })
        student = _put(db, GraduationStudent, tenant_id, {
            "batch_id": batch.id, "student_id": current.student_id
        }, {
            "topic_id": topic.id, "student_no": current.student_no, "name": current.name,
            "class_id": current.class_id, "class_name": current.class_name,
            "college_id": current.college_id, "major_id": current.major_id,
            "topic_title": topic.title, "topic_source": topic.source,
            "advisor_name": mentor.teacher_name, "stage": "DEFENSE",
            "material_summary": "任务书、开题、中期、定稿、查重、评阅、答辩、成绩材料齐全",
            "plagiarism_rate": ("8.6%", "12.4%", "10.8%")[index - 1],
            "risk_level": "NONE", "midterm_conclusion": "PASS",
            "eligibility_status": "QUALIFIED", "mentor_id": mentor.id,
            "student_group": "2026 届历史演示组", "grad_qual_status": "PASS",
            "grad_qual_note": "培养方案学分与毕业设计均通过审核", "record_status": "ACTIVE",
        })
        historical_students.append(student)
        topics.append(topic)

        _put(db, GraduationMentorAssignment, tenant_id, {
            "gd_student_id": student.id, "mentor_id": mentor.id
        }, {
            "assign_source": "BATCH", "assign_reason": "按专业方向和导师容量自动分配",
            "status": "ACTIVE", "confirmed_by_mentor": True,
            "confirmed_at": datetime(2025, 9, 8, 10), "assigned_by": "专业负责人",
            "assigned_at": datetime(2025, 9, 5, 9),
        })
        _put(db, GraduationTaskBook, tenant_id, {"gd_student_id": student.id}, {
            "mentor_id": mentor.id, "objective": "解决真实岗位场景问题并形成可验证成果。",
            "content": "完成调研、方案、实现、测试、论文和答辩材料。",
            "progress_plan": "9月选题；11月开题；3月中期；5月定稿；6月答辩归档。",
            "outcome_requirement": "论文、成果演示、检测报告、评阅和答辩记录齐全。",
            "taskbook_version": 2 if index == 2 else 1, "status": "CONFIRMED",
            "history_json": ([{"version": 1, "status": "CHANGE_PENDING", "reason": "企业需求边界调整"}]
                             if index == 2 else []),
            "issued_by": mentor.teacher_name, "issued_at": datetime(2025, 9, 12, 9),
            "confirmed_at": datetime(2025, 9, 13, 20),
            "change_reason": "根据企业反馈缩小验证范围" if index == 2 else None,
        })

        if index == 2:
            _put(db, GraduationProposal, tenant_id, {"gd_student_id": student.id, "version": "v1"}, {
                "is_resubmit": False, "submit_at": datetime(2025, 10, 20, 19),
                "background": "首次开题版本，岗位访谈证据不足。", "plan": "完成原型设计与测试。",
                "outcome": "论文与原型", "attachments_json": [evidence.id], "status": "REJECTED",
                "active_key": None, "reviewer": mentor.teacher_name,
                "review_comment": "缺少企业访谈纪要与可量化验收指标，请修改后重交。",
                "review_time": datetime(2025, 10, 23, 15), "defense_result": "FAIL",
                "defense_comment": "补齐调研证据后重新组织开题复核。", "defense_at": datetime(2025, 10, 23, 14),
            })
        _put(db, GraduationProposal, tenant_id, {"gd_student_id": student.id, "version": "v2" if index == 2 else "v1"}, {
            "is_resubmit": index == 2, "submit_at": datetime(2025, 11, 3, 20),
            "background": "基于企业访谈、岗位数据和专业培养目标开展研究。",
            "plan": "需求分析、方案设计、实现验证、指标复盘四阶段推进。",
            "outcome": "形成论文、成果系统、测试报告和企业评价。",
            "attachments_json": [evidence.id], "status": "APPROVED", "active_key": None,
            "reviewer": mentor.teacher_name, "review_comment": "修改内容完整，研究路径和验收指标明确。",
            "review_time": datetime(2025, 11, 8, 15), "defense_result": "PASS",
            "defense_comment": "同意开题并进入实施阶段。", "defense_at": datetime(2025, 11, 8, 14),
        })
        for visit in range(3):
            _put(db, GraduationGuidance, tenant_id, {
                "gd_student_id": student.id, "guidance_date": datetime(2025, 12, 5 + visit * 7, 14)
            }, {
                "mentor_id": mentor.id, "method": "OFFLINE" if visit != 1 else "ONLINE",
                "content": ("核对需求范围与岗位证据。", "评审阶段成果并调整验证指标。", "检查论文结构和引用规范。")[visit],
                "issues": "按指导意见完成修订并在下一次指导时复核。", "attachments_json": [evidence.id],
            })

    for index, student in enumerate(historical_students, 1):
        mentor = db.get(GraduationMentor, student.mentor_id)
        _put(db, GraduationMidterm, tenant_id, {"gd_student_id": student.id}, {
            "batch_id": batch.id, "status": "RECTIFIED_PASS" if index == 2 else "CHECKED_PASS",
            "conclusion": "PASS", "check_comment": ("按计划完成阶段成果。" if index != 2 else "测试样本不足，限期补充。"),
            "check_by": mentor.teacher_name, "checked_at": datetime(2026, 3, 10, 14),
            "rectify_deadline": datetime(2026, 3, 18, 18) if index == 2 else None,
            "rectify_content": "新增三组真实岗位样本并补充对比测试。" if index == 2 else None,
            "rectify_submitted_at": datetime(2026, 3, 16, 20) if index == 2 else None,
            "rectify_attempts": 1 if index == 2 else 0,
            "review_comment": "整改证据完整，中期复核通过。" if index == 2 else "中期检查通过。",
            "reviewed_by": "专业负责人", "reviewed_at": datetime(2026, 3, 18, 10),
        })
        if index == 2:
            _put(db, GraduationFinal, tenant_id, {"gd_student_id": student.id, "final_type": "初稿", "version": "v1"}, {
                "submit_at": datetime(2026, 4, 25, 20), "plagiarism_rate": None,
                "plagiarism_status": "NOT_CHECKED", "status": "REJECTED", "active_key": None,
                "reviewer": mentor.teacher_name, "review_comment": "图表数据口径与结论不一致，修订后重交。",
                "review_time": datetime(2026, 4, 28, 15), "attachments_json": [evidence.id],
            })
        final = _put(db, GraduationFinal, tenant_id, {"gd_student_id": student.id, "final_type": "定稿", "version": "v2" if index == 2 else "v1"}, {
            "submit_at": datetime(2026, 5, 8 + index, 20),
            "plagiarism_rate": ("8.6%", "12.4%", "10.8%")[index - 1],
            "plagiarism_status": "PASSED", "status": "APPROVED", "active_key": None,
            "reviewer": mentor.teacher_name, "review_comment": "定稿内容、数据口径与成果演示一致，同意送审。",
            "review_time": datetime(2026, 5, 13, 15), "attachments_json": [evidence.id],
        })
        if index == 2:
            first_check = _put(db, GraduationPlagiarismCheck, tenant_id, {"gd_final_id": final.id, "recheck_of_id": None}, {
                "gd_student_id": student.id, "submit_at": datetime(2026, 5, 10, 9), "status": "DONE",
                "active_key": None, "rate": "34.8%", "report_url": f"file://007/gd/{student.student_no}/plagiarism-v1.pdf",
                "threshold": 30, "over_threshold": True, "dispute_reason": "标准规范条文引用被误计入重复率。",
                "dispute_status": "APPROVED", "dispute_comment": "复核同意排除规范引用并重新检测。",
            })
            _put(db, GraduationPlagiarismCheck, tenant_id, {"gd_final_id": final.id, "recheck_of_id": first_check.id}, {
                "gd_student_id": student.id, "submit_at": datetime(2026, 5, 12, 9), "status": "DONE",
                "active_key": None, "rate": "12.4%", "report_url": f"file://007/gd/{student.student_no}/plagiarism-v2.pdf",
                "threshold": 30, "over_threshold": False, "dispute_status": "NONE",
            })
        else:
            _put(db, GraduationPlagiarismCheck, tenant_id, {"gd_final_id": final.id, "recheck_of_id": None}, {
                "gd_student_id": student.id, "submit_at": datetime(2026, 5, 11, 9), "status": "DONE",
                "active_key": None, "rate": ("8.6%", "10.8%")[0 if index == 1 else 1],
                "report_url": f"file://007/gd/{student.student_no}/plagiarism.pdf", "threshold": 30,
                "over_threshold": False, "dispute_status": "NONE",
            })

        reviewer = db.scalars(select(GraduationMentor).where(
            GraduationMentor.tenant_id == tenant_id,
            GraduationMentor.major_name == mentor.major_name,
            GraduationMentor.id != mentor.id,
            GraduationMentor.qualification_status == "QUALIFIED",
            GraduationMentor.is_deleted.is_(False),
        ).order_by(GraduationMentor.id)).first()
        if reviewer is None:
            raise RuntimeError("007 历史毕设缺少符合职责分离要求的同专业评阅导师")
        review = _put(db, GraduationReview, tenant_id, {"gd_final_id": final.id, "reviewer_mentor_id": reviewer.id}, {
            "gd_student_id": student.id, "reviewer_name": reviewer.teacher_name, "status": "COMPLETED",
            "score": (94, 84, 88)[index - 1], "opinion": "成果与论文相互印证，工作量充分，建议参加答辩。",
            "reviewed_at": datetime(2026, 5, 20, 16), "assigned_by": "专业负责人",
            "assigned_at": datetime(2026, 5, 15, 9),
        })
        feedback_key = f"{MARKER}:REVIEW:{student.id}:1"
        exists = db.scalar(select(func.count()).select_from(GraduationReviewFeedbackTable).where(
            GraduationReviewFeedbackTable.c.tenant_id == tenant_id,
            GraduationReviewFeedbackTable.c.idempotency_key == feedback_key,
        ))
        if not exists:
            db.execute(GraduationReviewFeedbackTable.insert().values(
                tenant_id=tenant_id, batch_id=batch.id, gd_student_id=student.id, stage="FINAL_REVIEW",
                source_record_id=final.id, review_id=review.id, file_version_id=None,
                source_sha256=_digest(f"{MARKER}:{student.id}:final"), round_no=1,
                categories=["结构规范", "数据口径", "岗位价值"],
                issues=[] if index != 2 else [{"code": "DATA_LABEL", "resolved": True}],
                summary="独立评阅完成；整改项已在送审版本闭环。", result="PASS",
                reviewer_mentor_id=reviewer.id, visible_to_student=True,
                idempotency_key=feedback_key, is_superseded=False, created_at=datetime(2026, 5, 20, 16),
            ))
        student._historical_final = final
        student._historical_reviewer = reviewer

    group_chair = historical_students[0]._historical_reviewer
    expert = _put(db, GraduationDefenseExpert, tenant_id, {"expert_name": "周岚清"}, {
        "title": "高级工程师", "college_name": "跃科产教融合专家委员会", "is_external": True,
        "avoid_note": "不参与存在企业项目直接利益关系的学生评分", "status": "ACTIVE",
    })
    group = _put(db, GraduationDefenseGroup, tenant_id, {"batch_id": batch.id, "group_name": "2026届第一答辩组"}, {
        "defense_date": "2026-06-05 09:00", "location": "产教融合楼 A301",
        "chair": group_chair.teacher_name, "chair_mentor_id": group_chair.id,
        "members_json": [{"mentorId": group_chair.id, "name": group_chair.teacher_name},
                         {"expertId": expert.id, "name": expert.expert_name, "external": True}],
        "secretary": "陈晓彤", "student_count": 3, "conflict": "已完成导师、评阅人和答辩评委回避校验",
        "published": True,
    })
    for index, student in enumerate(historical_students, 1):
        student.defense_group = group.group_name
        student.defense_group_id = group.id
        scores = ((95, 93), (84, 86), (89, 88))[index - 1]
        for judge_index, score in enumerate(scores):
            if judge_index == 0:
                key = f"MENTOR:{group_chair.id}"
                values = {"judge_name": group_chair.teacher_name, "judge_mentor_id": group_chair.id,
                          "expert_id": None}
            else:
                key = f"EXPERT:{expert.id}"
                values = {"judge_name": expert.expert_name, "judge_mentor_id": None, "expert_id": expert.id}
            _put(db, GraduationDefenseScore, tenant_id, {
                "gd_student_id": student.id, "defense_group_id": group.id, "round_no": 1,
                "judge_identity": key,
            }, {**values, "score": score, "comment": "陈述清晰，成果可验证，回答问题准确。",
                "absent": False, "status": "CONFIRMED", "confirmed_at": datetime(2026, 6, 5, 16)})
        final = student._historical_final
        _put(db, GraduationPeerReview, tenant_id, {
            "gd_student_id": student.id,
            "reviewer_gd_student_id": historical_students[index % 3].id,
            "task_version": 1,
        }, {
            "gd_final_id": final.id, "opinion": "图表编号、关键结论和岗位指标已逐项互查。",
            "rectify_note": "已统一图表口径并补充验证截图。" if index == 2 else None,
            "status": "RECTIFIED" if index == 2 else "REVIEWED", "reviewed_at": datetime(2026, 5, 18, 20),
        })
        advisor_score, reviewer_score, defense_score = ((96, 94, 94), (86, 84, 85), (90, 88, 89))[index - 1]
        total = round(advisor_score * .3 + reviewer_score * .3 + defense_score * .4)
        level = "优秀" if total >= 90 else "良好"
        grade_hash = _digest(f"{MARKER}:{student.id}:{advisor_score}:{reviewer_score}:{defense_score}:{total}")
        _put(db, GraduationGrade, tenant_id, {"gd_student_id": student.id}, {
            "advisor_score": advisor_score, "reviewer_score": reviewer_score, "defense_score": defense_score,
            "total_score": total, "grade_level": level, "status": "PUBLISHED",
            "remark": "按 30% 导师、30% 评阅、40% 答辩自动核算，复核后发布。",
            "calculated_at": datetime(2026, 6, 6, 9), "reviewed_by": "专业负责人",
            "reviewed_at": datetime(2026, 6, 8, 15), "published_by": "教务处毕设管理员",
            "published_at": datetime(2026, 6, 10, 10), "source_snapshot_hash": grade_hash,
        })
        if index in {2, 3}:
            _put(db, GraduationGradeAppeal, tenant_id, {"gd_student_id": student.id}, {
                "reason": ("申请核对答辩评分汇总是否遗漏评委确认记录。" if index == 2
                           else "企业成果加分材料在首次核算后补齐，申请复核。"),
                "status": "REJECTED" if index == 2 else "APPROVED", "active_key": None,
                "review_comment": ("两名评委确认记录齐全，综合分核算无误。" if index == 2
                                   else "补充材料真实有效，已纳入导师过程评价说明。"),
                "reviewed_by": "学院教学院长", "reviewed_at": datetime(2026, 6, 12, 16),
            })

        checklist = [{"item": item, "required": True, "present": True} for item in
                     ("任务书", "开题报告", "中期检查", "定稿", "查重报告", "评阅意见", "答辩记录", "成绩单")]
        manifest_hash = _digest(f"{MARKER}:{student.id}:archive:v1")
        archive = _put(db, GraduationArchiveRecord, tenant_id, {"gd_student_id": student.id}, {
            "checklist_json": checklist, "missing_items": [], "status": "FILED",
            "generated_at": datetime(2026, 6, 15, 9), "submitted_at": datetime(2026, 6, 18, 17),
            "verified_by": "档案管理员", "filed_at": FILED_AT,
            "archive_batch_no": "GD-2026-HIST-ARCHIVE-01", "manifest_hash": manifest_hash,
        })
        archive_version_exists = db.scalar(text("""
            SELECT COUNT(*) FROM t_gd_archive_version
            WHERE tenant_id=:tenant_id AND archive_record_id=:archive_record_id AND archive_version=1
              AND is_deleted=0
        """), {"tenant_id": tenant_id, "archive_record_id": archive.id})
        if not archive_version_exists:
            db.execute(text("""
                INSERT INTO t_gd_archive_version
                    (tenant_id, archive_record_id, gd_student_id, archive_version, current_flag,
                     previous_archive_id, invalidated_reason, source_manifest_json, source_manifest_hash,
                     archive_batch_no, filed_at, filed_by, created_at, updated_at, is_deleted, version)
                VALUES
                    (:tenant_id, :archive_record_id, :gd_student_id, 1, 1, NULL, NULL,
                     :source_manifest_json, :source_manifest_hash, :archive_batch_no,
                     :filed_at, '档案管理员', :filed_at, :filed_at, 0, 1)
            """), {
                "tenant_id": tenant_id, "archive_record_id": archive.id, "gd_student_id": student.id,
                "source_manifest_json": json.dumps({
                    "batchNo": batch.batch_no, "studentNo": student.student_no, "fileId": evidence.id,
                    "checklist": checklist, "gradeHash": grade_hash,
                }, ensure_ascii=False),
                "source_manifest_hash": manifest_hash, "archive_batch_no": archive.archive_batch_no,
                "filed_at": FILED_AT,
            })

    _put(db, GraduationExcellentOutcome, tenant_id, {"gd_student_id": historical_students[0].id}, {
        "batch_id": batch.id, "status": "PUBLISHED",
        "nomination_reason": "成果解决企业真实数据质量问题，验证指标完整，综合成绩与答辩表现突出。",
        "evidence_json": [{"fileId": evidence.id, "name": "企业成果应用证明"}],
        "grade_snapshot_json": {"totalScore": 95, "level": "优秀"}, "nominated_by": "指导教师",
        "nominated_at": datetime(2026, 6, 11, 9), "major_review_comment": "同意推荐校级优秀成果。",
        "major_reviewed_by": "专业负责人", "major_reviewed_at": datetime(2026, 6, 13, 15),
        "college_review_comment": "成果证据和评审程序完整，同意发布。", "college_reviewed_by": "学院教学院长",
        "college_reviewed_at": datetime(2026, 6, 16, 15), "published_at": datetime(2026, 6, 18, 10),
    })
    _put(db, GraduationDefenseDelay, tenant_id, {"gd_student_id": historical_students[2].id, "batch_id": batch.id}, {
        "active_key": None, "status": "SCHEDULED", "reason": "校企联合项目验收与原答辩时段冲突。",
        "evidence_json": [{"fileId": evidence.id, "name": "企业项目验收通知"}],
        "requested_at": datetime(2026, 5, 20, 20), "advisor_comment": "项目验收属于毕业设计成果验证，同意延期。",
        "advisor_reviewed_by": historical_students[2].advisor_name, "advisor_reviewed_at": datetime(2026, 5, 21, 10),
        "major_comment": "材料属实，建议调整至同一答辩周后段。", "major_reviewed_by": "专业负责人",
        "major_reviewed_at": datetime(2026, 5, 22, 14), "college_comment": "批准并纳入答辩冲突校验。",
        "college_reviewed_by": "学院教学院长", "college_reviewed_at": datetime(2026, 5, 23, 14),
        "planned_defense_date": "2026-06-05 14:00", "defense_group_id": group.id,
        "scheduled_at": datetime(2026, 5, 24, 9),
    })
    _put(db, GraduationRiskCase, tenant_id, {"risk_code": "GD-R04", "gd_student_id": historical_students[1].id}, {
        "risk_name": "中期整改临近超期", "level": "HIGH", "status": "CLOSED", "assignee": "专业负责人",
        "handle_note": "风险升级后安排导师每日跟踪；学生补齐三组岗位样本并通过复核。",
        "close_reason": "整改材料复核通过，风险条件消除。", "detected_at": datetime(2026, 3, 14, 8),
        "first_detected_at": datetime(2026, 3, 12, 8), "last_detected_at": datetime(2026, 3, 16, 8),
        "reopen_count": 1, "last_reopened_at": datetime(2026, 3, 15, 8), "condition_active": False,
        "condition_summary": "中期整改已提交并复核通过", "condition_hash": _digest("GD-R04:resolved")[:64],
        "closed_at": datetime(2026, 3, 18, 10),
    })
    _put(db, GraduationRiskCase, tenant_id, {"risk_code": "GD-R09", "gd_student_id": historical_students[2].id}, {
        "risk_name": "答辩排期冲突", "level": "MEDIUM", "status": "CLOSED", "assignee": "学院毕设秘书",
        "handle_note": "完成延期审批并重新排入第一答辩组下午场。", "close_reason": "新排期发布且学生确认。",
        "detected_at": datetime(2026, 5, 20, 8), "first_detected_at": datetime(2026, 5, 20, 8),
        "last_detected_at": datetime(2026, 5, 24, 8), "condition_active": False,
        "condition_summary": "冲突已通过延期答辩流程解除", "condition_hash": _digest("GD-R09:resolved")[:64],
        "closed_at": datetime(2026, 5, 24, 10),
    })
    _put(db, GraduationMaterialBackfillCheckpoint, tenant_id, {"migration_key": f"{MARKER}:ATTACHMENTS"}, {
        "status": "COMPLETED", "dry_run": False, "cursor_model": "GraduationFinal",
        "cursor_id": max(student._historical_final.id for student in historical_students), "page_size": 50,
        "scanned_rows": 3, "converted_rows": 3, "skipped_rows": 0, "failed_rows": 0,
        "diff_report_json": {"before": 3, "after": 3, "missing": 0, "crossTenant": 0},
        "started_at": datetime(2026, 6, 14, 9), "finished_at": datetime(2026, 6, 14, 9, 2),
    })

    issue_exists = db.scalar(text("""
        SELECT COUNT(*) FROM t_gd_migration_issue
        WHERE tenant_id=:tenant_id AND table_name='t_gd_final' AND issue_type='HISTORICAL_ATTACHMENT_NORMALIZED'
    """), {"tenant_id": tenant_id})
    if not issue_exists:
        db.execute(text("""
            INSERT INTO t_gd_migration_issue
                (tenant_id, table_name, row_id, issue_type, detail, status, created_at)
            VALUES
                (:tenant_id, 't_gd_final', :row_id, 'HISTORICAL_ATTACHMENT_NORMALIZED',
                 '历史定稿附件已从 JSON 引用核对到租户文件中心，差异为 0。', 'RESOLVED', :created_at)
        """), {"tenant_id": tenant_id, "row_id": historical_students[0]._historical_final.id,
                 "created_at": datetime(2026, 6, 14, 9, 2)})

    for student in historical_students:
        student.stage = "ARCHIVED"
        # record_status 表示主档是否仍为有效权威记录，不是流程阶段。
        # 已归档学生仍必须保持 ACTIVE，由 stage=ARCHIVED 和批次的
        # status/archive_status 表达归档终态；否则看板、成绩、评阅和归档
        # 读服务会按 record_status=ACTIVE 正确地把整条历史链隐藏。
        student.record_status = "ACTIVE"
        if hasattr(student, "_historical_final"):
            delattr(student, "_historical_final")
        if hasattr(student, "_historical_reviewer"):
            delattr(student, "_historical_reviewer")
    db.commit()
    return validate_graduation_historical_coverage(db, tenant_id)


def validate_graduation_historical_coverage(db, tenant_id: int) -> dict:
    from app.models import (
        GraduationArchiveRecord, GraduationBatch, GraduationDefenseScore, GraduationFinal,
        GraduationGrade, GraduationMidterm, GraduationPlagiarismCheck, GraduationReview,
        GraduationRiskCase, GraduationStudent, GraduationTaskBook,
    )
    from app.models.graduation_extension import GraduationDefenseDelay

    batch = _one(db, GraduationBatch, tenant_id, batch_no="GD-2026-HIST")
    student_ids = select(GraduationStudent.id).where(
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.batch_id == (batch.id if batch else -1),
        GraduationStudent.is_deleted.is_(False),
    )
    def count(model, *terms):
        return int(db.scalar(select(func.count()).select_from(model).where(
            model.tenant_id == tenant_id, model.is_deleted.is_(False), *terms,
        )) or 0)
    result = {
        "batchArchived": bool(batch and batch.status == "ARCHIVED" and batch.archive_status == "ARCHIVED"),
        "students": count(GraduationStudent, GraduationStudent.id.in_(student_ids)),
        "activeStudents": count(
            GraduationStudent,
            GraduationStudent.id.in_(student_ids),
            GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.stage == "ARCHIVED",
        ),
        "taskbooksConfirmed": count(GraduationTaskBook, GraduationTaskBook.gd_student_id.in_(student_ids), GraduationTaskBook.status == "CONFIRMED"),
        "midtermsTerminal": count(GraduationMidterm, GraduationMidterm.gd_student_id.in_(student_ids), GraduationMidterm.status.in_(("CHECKED_PASS", "RECTIFIED_PASS"))),
        "finalsApproved": count(GraduationFinal, GraduationFinal.gd_student_id.in_(student_ids), GraduationFinal.final_type == "定稿", GraduationFinal.status == "APPROVED"),
        "plagiarismDone": count(GraduationPlagiarismCheck, GraduationPlagiarismCheck.gd_student_id.in_(student_ids), GraduationPlagiarismCheck.status == "DONE"),
        "reviewsCompleted": count(GraduationReview, GraduationReview.gd_student_id.in_(student_ids), GraduationReview.status == "COMPLETED"),
        "defenseScoresConfirmed": count(GraduationDefenseScore, GraduationDefenseScore.gd_student_id.in_(student_ids), GraduationDefenseScore.status == "CONFIRMED"),
        "gradesPublished": count(GraduationGrade, GraduationGrade.gd_student_id.in_(student_ids), GraduationGrade.status == "PUBLISHED"),
        "archivesFiled": count(GraduationArchiveRecord, GraduationArchiveRecord.gd_student_id.in_(student_ids), GraduationArchiveRecord.status == "FILED"),
        "archiveVersions": int(db.scalar(text("""
            SELECT COUNT(*) FROM t_gd_archive_version v
            JOIN t_gd_student s ON s.id=v.gd_student_id AND s.tenant_id=v.tenant_id
            WHERE v.tenant_id=:tenant_id AND s.batch_id=:batch_id
              AND v.current_flag=1 AND v.is_deleted=0 AND s.is_deleted=0
        """), {"tenant_id": tenant_id, "batch_id": batch.id if batch else -1}) or 0),
        "closedRisks": count(GraduationRiskCase, GraduationRiskCase.gd_student_id.in_(student_ids), GraduationRiskCase.status == "CLOSED"),
        "scheduledDelay": count(GraduationDefenseDelay, GraduationDefenseDelay.gd_student_id.in_(student_ids), GraduationDefenseDelay.status == "SCHEDULED"),
    }
    result["passed"] = (
        result["batchArchived"] and result["students"] == 3 and result["activeStudents"] == 3
        and result["taskbooksConfirmed"] == 3
        and result["midtermsTerminal"] == 3 and result["finalsApproved"] == 3
        and result["plagiarismDone"] >= 3 and result["reviewsCompleted"] == 3
        and result["defenseScoresConfirmed"] == 6 and result["gradesPublished"] == 3
        and result["archivesFiled"] == 3 and result["archiveVersions"] == 3
        and result["closedRisks"] >= 2 and result["scheduledDelay"] == 1
    )
    if not result["passed"]:
        raise RuntimeError(f"007 毕设历史链校验失败: {result}")
    return result
