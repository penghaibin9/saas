"""毕业设计域演示种子：覆盖选题到归档的完整业务链。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import (
    GraduationArchiveRecord, GraduationAuditTrail, GraduationDefenseGroup,
    GraduationDefenseScore, GraduationFinal, GraduationGrade,
    GraduationGradeAppeal, GraduationGuidance, GraduationMentor,
    GraduationMentorAssignment, GraduationMidterm, GraduationPeerReview,
    GraduationPlagiarismCheck, GraduationProposal, GraduationReview,
    GraduationRiskCase, GraduationStudent, GraduationTaskBook,
    GraduationTopic, GraduationTopicChangeRequest,
)

TID = 1000000000000000001


def seed_graduation(db, tenant_id: int = TID) -> dict:
    if db.scalars(select(GraduationStudent).where(GraduationStudent.tenant_id == tenant_id)).first():
        return {"skipped": True}
    now = datetime.now()
    advisors = ["王芳", "钱立美", "孙晓梅"]
    classes = [("c-2301", "软件2301"), ("c-2302", "软件2302")]
    stages = ["TOPIC_SELECTING", "GUIDING", "MIDTERM", "FINAL_CHECK", "FINAL_CHECK", "DEFENSE",
              "GUIDING", "FINAL_CHECK", "MIDTERM", "TOPIC_SELECTING"]
    stus = []
    for i in range(10):
        cid, cname = classes[i % 2]
        risk = ["NONE", "LOW", "NONE", "MEDIUM", "NONE", "NONE", "HIGH", "LOW", "NONE", "MEDIUM"][i]
        stu = GraduationStudent(
            tenant_id=tenant_id, name=f"毕设生{i + 1:02d}", student_no=f"S2026-{i + 1:06d}",
            class_id=cid, class_name=cname,
            topic_title=f"基于 Vue3 的课题{i + 1}设计与实现" if i not in (0, 9) else None,
            topic_source="教师申报", advisor_name=advisors[i % 3], stage=stages[i],
            student_group=f"软件技术过程组{(i % 3) + 1}",
            material_summary="定稿 v3 待审" if stages[i] == "FINAL_CHECK" else "指导中",
            plagiarism_rate="12.6%" if stages[i] in ("FINAL_CHECK", "DEFENSE") else None,
            risk_level=risk, phone_encrypted=f"136{12340000 + i:08d}",
            midterm_conclusion="通过" if stages[i] in ("FINAL_CHECK", "DEFENSE") else None,
            defense_group="第 1 组" if stages[i] == "DEFENSE" else None,
        )
        db.add(stu)
        db.flush()
        stus.append(stu)

    topics = []
    for i in range(5):
        topic = GraduationTopic(
            tenant_id=tenant_id, title=f"课题库{i + 1}：智慧校园子系统设计",
            source="教师申报" if i % 2 == 0 else "企业课题", advisor_name=advisors[i % 3],
            major_name="软件技术", capacity=2, selected=1 if i < 3 else 0,
            review_status="APPROVED" if i < 3 else "PENDING_REVIEW",
            status="CONFIRMED" if i < 3 else "PENDING_CONFIRM",
            students_json=[f"毕设生{i + 1:02d}"] if i < 3 else [],
        )
        db.add(topic)
        db.flush()
        topics.append(topic)
    for i in range(3):
        stus[i].topic_id = topics[i].id

    proposal_specs = [
        (1, "PENDING_REVIEW", "v1", False), (6, "PENDING_REVIEW", "v2", True),
        (8, "PENDING_REVIEW", "v1", False), (2, "APPROVED", "v1", False),
        (3, "REJECTED", "v1", False),
    ]
    for idx, (sid_idx, status, version, resubmit) in enumerate(proposal_specs):
        db.add(GraduationProposal(
            tenant_id=tenant_id, gd_student_id=stus[sid_idx].id, version=version,
            is_resubmit=resubmit, submit_at=now - timedelta(days=idx + 1),
            background="围绕真实校园业务痛点开展研究", plan="调研、开发、测试、答辩分阶段推进",
            outcome="交付可运行系统、源码与论文", attachments_json=["开题报告.docx", "文献综述.pdf"],
            status=status, reviewer=advisors[sid_idx % 3] if status != "PENDING_REVIEW" else None,
            review_comment="需补充进度计划" if status == "REJECTED" else None,
        ))

    finals = []
    for idx, (sid_idx, status, rate) in enumerate([(3, "PENDING_REVIEW", "12.6%"),
                                                   (4, "PENDING_REVIEW", "18.4%"),
                                                   (5, "APPROVED", "9.2%")]):
        final = GraduationFinal(
            tenant_id=tenant_id, gd_student_id=stus[sid_idx].id, final_type="定稿", version=f"v{3-idx}",
            submit_at=now - timedelta(days=idx + 1), plagiarism_rate=rate,
            plagiarism_status="达标", status=status,
            reviewer=advisors[sid_idx % 3] if status == "APPROVED" else None,
        )
        db.add(final)
        db.flush()
        finals.append(final)

    groups = [
        GraduationDefenseGroup(tenant_id=tenant_id, group_name="第 1 组", defense_date="2026-07-08 09:00",
                               location="实训楼B401", chair="周正邦（教授）",
                               members_json=["孙晓梅", "企业专家陈志强"], secretary="林小婉",
                               student_count=12, published=True),
        GraduationDefenseGroup(tenant_id=tenant_id, group_name="第 2 组", defense_date="2026-07-08 14:00",
                               location="实训楼B402", chair="王芳（副教授）",
                               members_json=["王芳", "钱立美"], secretary="孙晓梅", student_count=10,
                               conflict="评委包含该生指导教师，待回避调整"),
        GraduationDefenseGroup(tenant_id=tenant_id, group_name="第 3 组", defense_date="2026-07-09 09:00",
                               location="待定", chair="待指定", members_json=["孙晓梅"],
                               secretary="待指定", student_count=8),
    ]
    db.add_all(groups)
    db.flush()
    stus[5].defense_group_id = groups[0].id

    mentors = [
        GraduationMentor(tenant_id=tenant_id, teacher_no="T-GD-001", teacher_name="王芳",
                         mentor_type="INTERNAL", title="副教授", college_name="信息工程学院",
                         major_name="软件技术", research_direction="Web应用与数据治理",
                         max_capacity=8, current_count=5, qualification_status="QUALIFIED"),
        GraduationMentor(tenant_id=tenant_id, teacher_no="T-GD-002", teacher_name="钱立美",
                         mentor_type="DUAL", title="讲师", college_name="信息工程学院",
                         major_name="软件技术", research_direction="企业信息化",
                         max_capacity=8, current_count=5, qualification_status="QUALIFIED"),
    ]
    db.add_all(mentors)
    db.flush()
    for i, stu in enumerate(stus):
        mentor = mentors[i % 2]
        stu.mentor_id = mentor.id
        db.add(GraduationMentorAssignment(
            tenant_id=tenant_id, gd_student_id=stu.id, mentor_id=mentor.id,
            assign_source="BATCH", assign_reason="2026届毕业设计统一分配", status="ACTIVE",
            confirmed_by_mentor=True, confirmed_at=now - timedelta(days=70),
            assigned_by="教务处", assigned_at=now - timedelta(days=72),
        ))

    db.add_all([
        GraduationTaskBook(tenant_id=tenant_id, gd_student_id=stus[0].id, mentor_id=mentors[0].id,
                           objective="完成可运行的学生全生命周期系统", content="需求、设计、编码、测试与论文",
                           progress_plan="第1-4周调研，第5-10周开发，第11-14周测试答辩",
                           outcome_requirement="系统、源码、论文、测试报告齐全", status="CONFIRMED",
                           issued_by="王芳", issued_at=now - timedelta(days=65), confirmed_at=now - timedelta(days=64)),
        GraduationGuidance(tenant_id=tenant_id, gd_student_id=stus[0].id, mentor_id=mentors[0].id,
                           guidance_date=now - timedelta(days=18), method="OFFLINE",
                           content="检查核心业务流程与数据库设计", issues="实习与就业模块关联需补充"),
        GraduationGuidance(tenant_id=tenant_id, gd_student_id=stus[1].id, mentor_id=mentors[1].id,
                           guidance_date=now - timedelta(days=11), method="ONLINE",
                           content="审阅论文第二稿", issues="图表编号和参考文献格式需统一"),
        GraduationMidterm(tenant_id=tenant_id, gd_student_id=stus[0].id, status="CHECKED_PASS",
                          conclusion="PASS", check_comment="进度符合计划，核心功能已经完成",
                          check_by="毕业设计检查组", checked_at=now - timedelta(days=30)),
        GraduationMidterm(tenant_id=tenant_id, gd_student_id=stus[1].id, status="RECTIFYING",
                          conclusion="RECTIFY", check_comment="测试用例覆盖不足",
                          check_by="毕业设计检查组", checked_at=now - timedelta(days=30),
                          rectify_deadline=now + timedelta(days=5), rectify_attempts=1),
        GraduationPlagiarismCheck(tenant_id=tenant_id, gd_student_id=stus[5].id,
                                  gd_final_id=finals[2].id, submit_at=now - timedelta(days=5),
                                  status="DONE", rate="9.2%", threshold=30, over_threshold=False,
                                  dispute_status="NONE"),
        GraduationReview(tenant_id=tenant_id, gd_student_id=stus[5].id, gd_final_id=finals[2].id,
                         reviewer_name="周正邦", status="COMPLETED", score=86,
                         opinion="结构完整，系统实现与论文内容一致", reviewed_at=now - timedelta(days=3)),
        GraduationDefenseScore(tenant_id=tenant_id, gd_student_id=stus[5].id,
                               defense_group_id=groups[0].id, judge_name="陈志强", score=88,
                               comment="表达清晰，能够准确回答技术问题", status="CONFIRMED",
                               confirmed_at=now - timedelta(days=2)),
        GraduationGrade(tenant_id=tenant_id, gd_student_id=stus[5].id, advisor_score=87,
                        reviewer_score=86, defense_score=88, total_score=87, grade_level="良好",
                        status="PUBLISHED", reviewed_by="教务处", reviewed_at=now - timedelta(days=2),
                        published_by="教务处", published_at=now - timedelta(days=1)),
        GraduationRiskCase(tenant_id=tenant_id, risk_code="GD-R06", risk_name="指导频次不足",
                           gd_student_id=stus[6].id, level="HIGH", status="PROCESSING",
                           assignee="王芳", handle_note="已约谈学生并制定每周指导计划",
                           detected_at=now - timedelta(days=7)),
        GraduationArchiveRecord(tenant_id=tenant_id, gd_student_id=stus[5].id,
                                checklist_json=[{"item": "论文定稿", "required": True, "present": True},
                                                {"item": "答辩记录", "required": True, "present": True}],
                                missing_items=[], status="FILED", generated_at=now - timedelta(days=2),
                                submitted_at=now - timedelta(days=1), verified_by="教务处",
                                filed_at=now, archive_batch_no="GD-ARCHIVE-2026-01"),
        GraduationPeerReview(tenant_id=tenant_id, gd_student_id=stus[4].id,
                             reviewer_gd_student_id=stus[5].id, gd_final_id=finals[1].id,
                             opinion="建议补充异常场景测试", rectify_note="已补充12条异常用例",
                             status="RECTIFIED", reviewed_at=now - timedelta(days=4)),
        GraduationGradeAppeal(tenant_id=tenant_id, gd_student_id=stus[5].id,
                              reason="申请复核答辩评分汇总是否准确", status="APPROVED",
                              review_comment="已复核，汇总无误", reviewed_by="教务处", reviewed_at=now),
        GraduationTopicChangeRequest(tenant_id=tenant_id, gd_student_id=stus[0].id,
                                     old_topic_id=topics[0].id, new_topic_id=topics[1].id,
                                     reason="企业真实项目方向调整", status="PENDING",
                                     requested_by=stus[0].name, requested_at=now - timedelta(days=2)),
    ])
    db.add_all([
        GraduationAuditTrail(tenant_id=tenant_id, biz_type="RECORD", biz_id=str(stus[0].id),
                             action="导入毕设台账", operator="系统", detail="批量导入10名毕设学生",
                             occurred_at=now - timedelta(days=30)),
        GraduationAuditTrail(tenant_id=tenant_id, biz_type="TOPIC", biz_id=str(topics[0].id),
                             action="课题审核通过", operator="教务处", detail="课题进入可选题库",
                             before_val="PENDING_REVIEW", after_val="APPROVED",
                             occurred_at=now - timedelta(days=60)),
    ])
    db.commit()
    return {"students": len(stus), "topics": 5, "proposals": 5, "finals": 3, "defenseGroups": 3}
