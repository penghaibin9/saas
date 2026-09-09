"""007 GD-2027 在办毕设的操作性过程数据。

只补充当前 2027 届已经处于选题/早期指导阶段时合理存在的表：选题志愿、换题、
指导计划、材料规则/清单、模板、过程评价和审计。绝不把中期、定稿、答辩、成绩或
归档提前写进当前届；这些完成态只能由独立历史批次提供。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select

REFERENCE_NOW = datetime(2026, 8, 28, 10, 30)
MARKER = "007-GD-2027-OPERATIONAL-V1"


def _count(db, model, tenant_id: int) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(
        model.tenant_id == tenant_id, model.is_deleted.is_(False),
    )) or 0)


def seed_graduation_operational_coverage(db, tenant_id: int) -> dict:
    from app.models import (
        GraduationAuditTrail, GraduationBatch, GraduationGuidancePlan, GraduationMaterialItem,
        GraduationMaterialRule, GraduationMentorEval, GraduationStudent, GraduationStudentEval,
        GraduationStudentMaterial, GraduationTemplate, GraduationTemplateAssetPolicy,
        GraduationTopic, GraduationTopicChangeRequest, GraduationTopicChoice, GraduationTopicRound,
    )

    batch = db.scalars(select(GraduationBatch).where(
        GraduationBatch.tenant_id == tenant_id, GraduationBatch.batch_no == "GD-2027",
        GraduationBatch.is_deleted.is_(False),
    )).first()
    if batch is None:
        raise RuntimeError("GD-2027 batch is required before operational coverage seed")
    prior = db.scalars(select(GraduationTopicRound).where(
        GraduationTopicRound.tenant_id == tenant_id,
        GraduationTopicRound.round_name == MARKER,
        GraduationTopicRound.is_deleted.is_(False),
    )).first()
    if prior is not None:
        return {"resumed": True, "validation": validate_graduation_operational_coverage(db, tenant_id)}

    students = list(db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == tenant_id, GraduationStudent.batch_id == batch.id,
        GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
        GraduationStudent.topic_id.is_not(None), GraduationStudent.mentor_id.is_not(None),
    ).order_by(GraduationStudent.student_no).limit(8)).all())
    if len(students) < 8:
        raise RuntimeError(f"GD-2027 active students insufficient: {len(students)}")
    topics = list(db.scalars(select(GraduationTopic).where(
        GraduationTopic.tenant_id == tenant_id, GraduationTopic.batch_id == batch.id,
        GraduationTopic.is_deleted.is_(False),
    ).order_by(GraduationTopic.id).limit(12)).all())
    if len(topics) < 3:
        raise RuntimeError("GD-2027 topic pool insufficient")

    round_row = GraduationTopicRound(
        tenant_id=tenant_id, batch_id=batch.id, round_name=MARKER, round_no=2, max_choices=3,
        status="MATCHED", start_at=datetime(2026, 8, 18, 9), end_at=datetime(2026, 8, 22, 18),
        college_scope="全校 2024 级；已完成二轮选题匹配", remark="007 标准演示：真实选题志愿与匹配留痕",
    )
    db.add(round_row)
    db.flush()

    for index, student in enumerate(students[:4]):
        db.add(GraduationTopicChoice(
            tenant_id=tenant_id, round_id=round_row.id, gd_student_id=student.id,
            topic_id=student.topic_id, choice_order=1, status="CONFIRMED", submission_version=2,
        ))
    # 正常申请、退回后取消两种状态均使用现有批次题目和当前学生，保留审核原因。
    db.add_all([
        GraduationTopicChangeRequest(
            tenant_id=tenant_id, gd_student_id=students[4].id, old_topic_id=students[4].topic_id,
            new_topic_id=topics[-1].id, reason="企业调研后发现原题目范围过宽，申请转为岗位数据质量专题。",
            status="PENDING", requested_by=students[4].name, requested_at=REFERENCE_NOW - timedelta(days=1),
        ),
        GraduationTopicChangeRequest(
            tenant_id=tenant_id, gd_student_id=students[5].id, old_topic_id=students[5].topic_id,
            new_topic_id=topics[-2].id, reason="申请更换为已满容量题目。", status="REJECTED",
            review_comment="目标题目已达到容量，请在开放题库中重新选择。", reviewer_name="专业负责人",
            requested_by=students[5].name, requested_at=REFERENCE_NOW - timedelta(days=3),
            reviewed_at=REFERENCE_NOW - timedelta(days=2),
        ),
    ])
    for index, student in enumerate(students[:6]):
        checked = index < 3
        db.add(GraduationGuidancePlan(
            tenant_id=tenant_id, gd_student_id=student.id, mentor_id=student.mentor_id,
            title=f"第 {index + 1} 次前期指导计划", plan_date=REFERENCE_NOW + timedelta(days=index - 2),
            content="核对岗位场景、任务书边界和调研证据；形成下一周可检查的成果清单。",
            status="CHECKED_IN" if checked else "PLANNED",
            checked_in_at=REFERENCE_NOW - timedelta(days=2 - index) if checked else None,
            checked_in_by=student.advisor_name if checked else None,
            checkin_role="MENTOR" if checked else None, checkin_method="ONLINE" if checked else None,
            checkin_note="已明确下周调研任务并同步学生。" if checked else None,
        ))

    rule = GraduationMaterialRule(
        tenant_id=tenant_id, batch_id=batch.id, rule_code="GD2027-EARLY-MATERIAL",
        rule_name="GD-2027 选题开题材料规则", rule_version=1, status="ENABLED", enabled=True,
        applicable_scope_json={"batchNo": "GD-2027", "stage": ["TOPIC_SELECTING", "GUIDING"]},
        required_items_json=["TOPIC_FORM", "PROPOSAL_OUTLINE"], allowed_ext_json=["pdf", "docx"],
        effective_at=REFERENCE_NOW - timedelta(days=10), remark="当前届早期过程材料，不包含未来定稿或答辩材料。",
    )
    db.add(rule)
    db.flush()
    db.add_all([
        GraduationMaterialItem(tenant_id=tenant_id, rule_id=rule.id, biz_stage="TOPIC_SELECTING",
                              material_code="TOPIC_FORM", material_name="选题志愿确认单", sort_no=1,
                              allowed_ext_json=["pdf"], description="学生确认选题后的电子签署材料。"),
        GraduationMaterialItem(tenant_id=tenant_id, rule_id=rule.id, biz_stage="GUIDING",
                              material_code="PROPOSAL_OUTLINE", material_name="开题报告提纲", sort_no=2,
                              allowed_ext_json=["docx", "pdf"], description="开题审核前的提纲版本。"),
    ])
    for index, student in enumerate(students[:4]):
        status = ("APPROVED", "RETURNED", "SUBMITTED", "MISSING")[index]
        review_status = {"APPROVED": "APPROVED", "RETURNED": "RETURNED", "SUBMITTED": "PENDING", "MISSING": "NOT_SUBMITTED"}[status]
        db.add(GraduationStudentMaterial(
            tenant_id=tenant_id, batch_id=batch.id, gd_student_id=student.id, student_id=student.student_id,
            topic_id=student.topic_id, rule_id=rule.id, material_code="PROPOSAL_OUTLINE",
            material_name="开题报告提纲", biz_stage="GUIDING", business_status=status,
            review_status=review_status, archive_status="NOT_ARCHIVED", submitted_at=REFERENCE_NOW - timedelta(days=index + 1) if status != "MISSING" else None,
            reviewer_name=student.advisor_name if status in {"APPROVED", "RETURNED"} else None,
            reviewed_at=REFERENCE_NOW - timedelta(days=index) if status in {"APPROVED", "RETURNED"} else None,
            reject_reason="缺少岗位调研访谈纪要，请补充后重交。" if status == "RETURNED" else None,
            source_record_type="GRADUATION_PROPOSAL", source_record_id=str(student.id),
        ))

    templates = []
    for template_type, name, default in (
        ("TASKBOOK", "GD-2027 任务书模板", True),
        ("PROPOSAL", "GD-2027 开题报告模板", False),
        ("MATERIAL", "GD-2027 材料清单模板", False),
    ):
        template = GraduationTemplate(
            tenant_id=tenant_id, template_type=template_type, name=name, template_version="v1.0",
            content="适用于 {studentName} / {topicTitle} 的 007 标准演示模板。",
            variables_json=["studentName", "topicTitle", "mentorName"], applicable_note="GD-2027 当前批次",
            status="ENABLED", is_default=default, remark="007 操作性流程演示模板",
        )
        db.add(template); templates.append(template)
    db.flush()
    db.add(GraduationTemplateAssetPolicy(
        tenant_id=tenant_id, template_id=templates[0].id, template_code="GD2027-TASKBOOK-V1",
        batch_id=batch.id, variable_schema_json={"required": ["studentName", "topicTitle"]},
        scope_json={"batchNo": "GD-2027"}, effective_at=REFERENCE_NOW - timedelta(days=8),
        enabled=True, status="ENABLED",
    ))
    for index, student in enumerate(students[:3]):
        db.add(GraduationStudentEval(
            tenant_id=tenant_id, gd_student_id=student.id, mentor_id=student.mentor_id, period="前期指导",
            score=90 - index * 4, level="优秀" if index == 0 else "良好",
            content="选题理解清晰，已完成阶段调研任务。", status="SUBMITTED",
            submitted_by=student.advisor_name, submitted_at=REFERENCE_NOW - timedelta(days=index + 1),
        ))
    mentor_ids = sorted({int(student.mentor_id) for student in students[:3]})
    for index, mentor_id in enumerate(mentor_ids):
        db.add(GraduationMentorEval(
            tenant_id=tenant_id, mentor_id=mentor_id, period="2026 秋季前期", score=92 - index,
            level="优秀", note="按计划完成首次指导和任务书下达。", evaluated_by="二级学院毕业设计工作组",
            evaluated_at=REFERENCE_NOW,
        ))
    db.add_all([
        GraduationAuditTrail(tenant_id=tenant_id, batch_id=batch.id, biz_type="TOPIC_ROUND", biz_id=str(round_row.id),
                            action="二轮选题匹配完成", operator="毕业设计管理办公室", role_name="学校管理员",
                            detail="四名学生志愿与题目匹配结果已确认", before_val="OPEN", after_val="MATCHED", occurred_at=REFERENCE_NOW - timedelta(days=6)),
        GraduationAuditTrail(tenant_id=tenant_id, batch_id=batch.id, biz_type="MATERIAL", biz_id=str(rule.id),
                            action="启用早期材料规则", operator="毕业设计管理办公室", role_name="学校管理员",
                            detail="选题确认单和开题提纲进入当前批次材料规则", before_val="DRAFT", after_val="ENABLED", occurred_at=REFERENCE_NOW - timedelta(days=8)),
    ])
    db.commit()
    return {"resumed": False, "validation": validate_graduation_operational_coverage(db, tenant_id)}


def validate_graduation_operational_coverage(db, tenant_id: int) -> dict:
    from app.models import GraduationMaterialRule, GraduationStudentMaterial, GraduationTemplate, GraduationTopicRound
    report = {
        "topicRounds": _count(db, GraduationTopicRound, tenant_id),
        "materialRules": _count(db, GraduationMaterialRule, tenant_id),
        "studentMaterials": _count(db, GraduationStudentMaterial, tenant_id),
        "templates": _count(db, GraduationTemplate, tenant_id),
    }
    if not all(report.values()):
        raise RuntimeError(f"GD-2027 operational coverage incomplete: {report}")
    report["passed"] = True
    return report
