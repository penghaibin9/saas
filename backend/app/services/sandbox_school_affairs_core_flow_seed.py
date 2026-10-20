"""007 学工核心流程补全：资助、处分、宿舍、心理、谈心和审计留痕。"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, text


NOW = datetime(2026, 8, 28, 10, 30)
MARKER = "007-AFFAIRS-CORE-2026"


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


def seed_affairs_core_flows(db, tenant_id: int) -> dict:
    from app.models import (
        AffairsRiskHandle, AffairsRiskRecord, AidApply, AidBatch, AidObjection, CsAuditTrail, DisciplineAppeal,
        DisciplineCase, DisciplineRemoveApply, DormBed, DormBuilding, DormCheckRecord,
        DormCheckTask, DormRoom, DormTransfer, FeeReduction, FileObject, FundingAppeal,
        FundingApplication, FundingBatch, FundingProject, PsyReferral, PsySurveySubmission,
        StudentLoan, StudentProfile, TalkPlan, TalkRecord, User, WorkStudyMonthly,
        WorkStudyPost, WorkStudyRecord,
    )
    from app.models.affairs_discipline_integrity import DisciplineSubflowLock

    admin = _one(db, User, tenant_id, login_name="admin2")
    teacher = _one(db, User, tenant_id, login_name="teacher2")
    evidence = _one(db, FileObject, tenant_id, file_key="007-GOV-2026/leave-approval-evidence.md")
    students = list(db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id, StudentProfile.is_deleted.is_(False),
    ).order_by(StudentProfile.student_no).limit(20)).all())
    if not admin or not teacher or not evidence or len(students) < 12:
        raise RuntimeError("007 学工核心链前置主档不足")

    # 困难认定：历史公示异议已结案 + 当前公示异议待复核。
    approved_aid = db.scalars(select(AidApply).where(
        AidApply.tenant_id == tenant_id, AidApply.status == "APPROVED",
        AidApply.is_deleted.is_(False),
    ).order_by(AidApply.id)).first()
    if approved_aid is None:
        raise RuntimeError("007 学工核心链缺少既有困难认定结果")
    _put(db, AidObjection, tenant_id, {"apply_id": approved_aid.id, "status": "CLOSED"}, {
        "student_id": approved_aid.student_id, "objector_name": "班级评议代表",
        "reason": "公示期间申请复核家庭人口与收入证明的统计口径。", "result": "OVERRULED",
        "review_opinion": "辅导员、学院和资助中心三方复核原始材料，认定等级维持。",
        "reviewer": "学生资助中心复核组", "reviewed_at": datetime(2025, 10, 18, 16), "open_key": None,
    })
    current_aid_batch = _put(db, AidBatch, tenant_id, {"batch_name": f"{MARKER}-秋季临时困难认定"}, {
        "year_code": "2026-2027", "apply_start": NOW - timedelta(days=12),
        "apply_end": NOW - timedelta(days=3), "publicity_days": 5,
        "level_config_json": json.dumps({"GENERAL": "一般困难", "DIFFICULT": "困难", "SPECIAL": "特别困难"}, ensure_ascii=False),
        "scope_json": json.dumps({"grade": ["2024", "2025", "2026"]}, ensure_ascii=False), "status": "PUBLICITY",
    })
    public_aid = _put(db, AidApply, tenant_id, {"batch_id": current_aid_batch.id, "student_id": students[8].id}, {
        "apply_level": "DIFFICULT", "suggest_level": "GENERAL", "final_level": "GENERAL",
        "statement": "家庭主要劳动力近期因病停工，申请按最新材料复核困难等级。",
        "class_review_score": 87.5, "class_review_rank": 4, "status": "PUBLICITY",
        "publicity_at": NOW - timedelta(days=1),
    })
    _put(db, AidObjection, tenant_id, {"apply_id": public_aid.id, "status": "SUBMITTED"}, {
        "student_id": public_aid.student_id, "objector_name": "学生本人",
        "reason": "新增医疗支出证明尚未纳入认定材料，申请在公示期内补充复核。",
        "open_key": public_aid.id,
    })

    # 奖助：当前公示申请包含金额调整双人复核与公示申诉；不改历史 1,300 笔已发放事实。
    project = db.scalars(select(FundingProject).where(
        FundingProject.tenant_id == tenant_id, FundingProject.status == "ENABLED",
        FundingProject.is_deleted.is_(False),
    ).order_by(FundingProject.id)).first()
    if project is None:
        raise RuntimeError("007 学工核心链缺少资助项目")
    funding_batch = _put(db, FundingBatch, tenant_id, {
        "project_id": project.id, "year_code": "2026-2027-CORE-DEMO"
    }, {
        "project_type": project.project_type, "apply_start": NOW - timedelta(days=15),
        "apply_end": NOW - timedelta(days=5), "publicity_days": 5, "quota": 20,
        "amount_budget": Decimal("60000.00"), "reserved_quota": 0,
        "reserved_amount": Decimal("0.00"), "status": "PUBLICITY",
    })
    funding_apps = []
    for offset, status in enumerate(("PUBLICITY", "SCHOOL_REVIEW"), 9):
        app = _put(db, FundingApplication, tenant_id, {
            "batch_id": funding_batch.id, "student_id": students[offset].id
        }, {
            "apply_source": "SELF", "project_type": project.project_type,
            "amount": Decimal("3000.00"), "requested_amount": Decimal("3000.00"),
            "approved_amount": None, "quota_reserved": False,
            "statement": "家庭经济压力较大，学业表现稳定，申请本学年资助。",
            "check_snapshot_json": json.dumps({"studentStatus": "ACTIVE", "discipline": "NONE", "aidLevel": "GENERAL"}, ensure_ascii=False),
            "status": status, "publicity_at": NOW - timedelta(days=1) if status == "PUBLICITY" else None,
        })
        funding_apps.append(app)
    _put(db, FundingAppeal, tenant_id, {"application_id": funding_apps[0].id, "status": "SUBMITTED"}, {
        "student_id": funding_apps[0].student_id, "appellant_name": "学生本人",
        "reason": "公示金额未体现项目规则中的校级技能竞赛专项支持，申请复核。",
        "open_key": funding_apps[0].id,
    })
    existing_adjustment = db.scalar(text("""
        SELECT COUNT(*) FROM t_affairs_funding_amount_adjustment
        WHERE tenant_id=:tenant_id AND application_id=:application_id AND is_deleted=0
    """), {"tenant_id": tenant_id, "application_id": funding_apps[1].id})
    if not existing_adjustment:
        db.execute(text("""
            INSERT INTO t_affairs_funding_amount_adjustment
                (tenant_id, application_id, requested_amount, reason, requester_id, requester_name,
                 status, version, created_at, updated_at, is_deleted)
            VALUES (:tenant_id, :application_id, 3600.00, '技能竞赛集训产生额外学习与交通支出，申请调整资助金额。',
                    :requester_id, :requester_name, 'PENDING', 0, :created_at, :created_at, 0)
        """), {"tenant_id": tenant_id, "application_id": funding_apps[1].id,
                 "requester_id": teacher.id, "requester_name": teacher.real_name,
                 "created_at": NOW - timedelta(hours=5)})

    # 勤工、贷款、减免：在办、上岗、月度考核、完成发放并存。
    post = _put(db, WorkStudyPost, tenant_id, {"dept_name": "图书信息中心", "post_name": "数字资源整理助理"}, {
        "salary": Decimal("800.00"), "headcount": 6,
        "requirement": "每周不超过 8 小时，完成岗前培训，能规范处理电子资源元数据。", "status": "ENABLED",
    })
    onboard = _put(db, WorkStudyRecord, tenant_id, {"post_id": post.id, "student_id": students[0].id, "status": "ONBOARD"}, {
        "onboard_at": datetime(2026, 3, 1, 9), "subsidy_total": Decimal("4000.00"),
        "remark": "已完成岗前培训，按月由用人部门考核。",
    })
    _put(db, WorkStudyRecord, tenant_id, {"post_id": post.id, "student_id": students[1].id, "status": "APPLIED"}, {
        "subsidy_total": Decimal("0.00"), "remark": "学生已申请，等待用人部门审核。",
    })
    for month, hours, rating, amount in (("2026-06", 30, "GOOD", "800.00"), ("2026-07", 28, "PASS", "760.00")):
        _put(db, WorkStudyMonthly, tenant_id, {"record_id": onboard.id, "month_code": month}, {
            "student_id": onboard.student_id, "work_hours": hours, "rating": rating,
            "subsidy_amount": Decimal(amount), "remark": "部门负责人核对工时后确认。",
        })
    _put(db, StudentLoan, tenant_id, {"student_id": students[2].id, "year_code": "2026-2027"}, {
        "loan_type": "ORIGIN", "bank_name": "国家开发银行", "bank_last4": "6621",
        "amount": Decimal("12000.00"), "receipt_file_id": evidence.id, "status": "VERIFIED",
        "remark": "电子回执与学生身份、学年和金额核对一致。",
    })
    _put(db, StudentLoan, tenant_id, {"student_id": students[3].id, "year_code": "2026-2027"}, {
        "loan_type": "CAMPUS", "bank_name": "中国银行", "bank_last4": "3086",
        "amount": Decimal("8000.00"), "status": "REGISTERED", "remark": "等待上传银行回执。",
    })
    _put(db, FeeReduction, tenant_id, {"student_id": students[4].id, "item_type": "TEMP_AID"}, {
        "amount": Decimal("2000.00"), "reason": "家庭遭遇突发医疗支出，临时生活保障压力较大。",
        "status": "ISSUED", "review_opinion": "材料核验通过，同意一次性临时补助。",
        "reviewer": "学生资助中心", "reviewed_at": NOW - timedelta(days=8), "issued_at": NOW - timedelta(days=3),
    })
    _put(db, FeeReduction, tenant_id, {"student_id": students[5].id, "item_type": "REDUCTION"}, {
        "amount": Decimal("1500.00"), "reason": "符合学校学费减免申请条件，材料已提交。", "status": "SUBMITTED",
    })

    # 处分申诉和解除使用不同有效处分，活动子流程锁与主单一一对应。
    effective_cases = list(db.scalars(select(DisciplineCase).where(
        DisciplineCase.tenant_id == tenant_id, DisciplineCase.status == "EFFECTIVE",
        DisciplineCase.is_deleted.is_(False),
    ).order_by(DisciplineCase.id).limit(2)).all())
    if len(effective_cases) != 2:
        raise RuntimeError("007 学工核心链缺少两笔有效处分")
    appeal = _put(db, DisciplineAppeal, tenant_id, {"case_id": effective_cases[0].id}, {
        "student_id": effective_cases[0].student_id, "reason": "对处分事实无异议，申请复核处分等级与教育整改表现是否匹配。",
        "status": "REVIEWING", "review_opinion": "已受理，等待学院复核会议。", "reviewer": "学生申诉复核组",
    })
    remove = _put(db, DisciplineRemoveApply, tenant_id, {"case_id": effective_cases[1].id}, {
        "student_id": effective_cases[1].student_id, "apply_reason": "处分期内表现稳定，已完成志愿服务和纪律教育课程。",
        "min_months_check": True, "status": "RETURNED", "current_node": "COUNSELOR_REVIEW",
        "return_reason": "请补充最近三个月班级综合表现证明后重交。",
    })
    _put(db, DisciplineSubflowLock, tenant_id, {"case_id": appeal.case_id}, {
        "flow_type": "APPEAL", "flow_id": appeal.id, "created_at": NOW - timedelta(days=2),
    })
    _put(db, DisciplineSubflowLock, tenant_id, {"case_id": remove.case_id}, {
        "flow_type": "REMOVE", "flow_id": remove.id, "created_at": NOW - timedelta(days=1),
    })

    # 宿舍：不搬动现有床位事实，只生成可审核调宿单和已闭环检查任务。
    occupied_beds = list(db.scalars(select(DormBed).where(
        DormBed.tenant_id == tenant_id, DormBed.status == "OCCUPIED",
        DormBed.student_id.is_not(None), DormBed.is_deleted.is_(False),
    ).order_by(DormBed.id).limit(2)).all())
    vacant_beds = list(db.scalars(select(DormBed).where(
        DormBed.tenant_id == tenant_id, DormBed.status == "VACANT",
        DormBed.student_id.is_(None), DormBed.is_deleted.is_(False),
    ).order_by(DormBed.id).limit(2)).all())
    if len(occupied_beds) != 2 or len(vacant_beds) != 2:
        raise RuntimeError("007 学工核心链缺少可演示宿舍床位")
    _put(db, DormTransfer, tenant_id, {"student_id": occupied_beds[0].student_id, "status": "COUNSELOR_REVIEW"}, {
        "from_bed_id": occupied_beds[0].id, "to_bed_id": vacant_beds[0].id,
        "reason": "参加晚间技能集训，申请调整至同专业同学所在楼层便于互助。",
        "current_node": "COUNSELOR_REVIEW",
    })
    _put(db, DormTransfer, tenant_id, {"student_id": occupied_beds[1].student_id, "status": "RETURNED"}, {
        "from_bed_id": occupied_beds[1].id, "to_bed_id": vacant_beds[1].id,
        "reason": "申请更换床位。", "current_node": "STUDENT_RESUBMIT",
        "return_reason": "请补充健康或学习安排证明，并征求拟调入宿舍成员意见。",
    })
    building = db.get(DormBuilding, occupied_beds[0].building_id)
    room = db.get(DormRoom, occupied_beds[0].room_id)
    task = _put(db, DormCheckTask, tenant_id, {"task_name": f"{MARKER}-秋季开学宿舍安全检查"}, {
        "building_id": building.id, "check_type": "SAFETY", "checker_key": str(teacher.id),
        "planned_at": NOW - timedelta(days=2), "status": "DONE",
    })
    _put(db, DormCheckRecord, tenant_id, {"task_id": task.id, "room_id": room.id}, {
        "result": "ABNORMAL", "issue_type": "POWER_SAFETY",
        "detail": "插线板放置位置不规范；现场已断电并完成安全教育。",
        "rectify_deadline": NOW + timedelta(days=1),
        "student_ids_json": json.dumps([bed.student_id for bed in occupied_beds if bed.room_id == room.id]),
        "status": "RECTIFYING",
    })

    # 心理自评仅作主动求助线索，不产生诊断；人工转介后进入风险闭环。
    existing_risk = db.scalars(select(AffairsRiskRecord).where(
        AffairsRiskRecord.tenant_id == tenant_id, AffairsRiskRecord.is_deleted.is_(False),
    ).order_by(AffairsRiskRecord.id)).first()
    if existing_risk is None:
        raise RuntimeError("007 学工核心链缺少既有风险事实")
    _put(db, AffairsRiskHandle, tenant_id, {
        "risk_id": existing_risk.id, "action": "FOLLOW",
    }, {
        "content": "辅导员完成首次联系，核对宿舍、课堂和家庭支持情况，并转心理中心持续跟进。",
        "operator": teacher.real_name, "from_status": "PROCESSING", "to_status": "FOLLOWING",
    })
    referral = _put(db, PsyReferral, tenant_id, {"student_id": existing_risk.student_id, "channel": "校内咨询"}, {
        "level": "FOCUS", "reason_summary": "学生在自评中主动勾选希望老师联系。",
        "note": "心理老师已电话确认学生当前安全，约定线下面谈；本记录不构成临床诊断。",
        "referrer": "辅导员", "status": "FOLLOWING", "last_follow_time": NOW - timedelta(hours=6),
    })
    survey = _put(db, PsySurveySubmission, tenant_id, {"student_id": existing_risk.student_id, "submitted_at": NOW - timedelta(days=1)}, {
        "answers_json": json.dumps([{"qKey": f"Q{i}", "score": score} for i, score in enumerate((1, 2, 1, 2, 1), 1)]),
        "total_score": 7, "wants_contact": True, "triggered_referral_id": referral.id,
    })
    referral.risk_id = existing_risk.id
    survey.triggered_referral_id = referral.id

    plan = _put(db, TalkPlan, tenant_id, {"plan_name": f"{MARKER}-学业与生活适应谈话周"}, {
        "teacher_id": teacher.id, "topic_type": "DAILY", "planned_at": NOW + timedelta(days=2),
        "student_ids_json": json.dumps([existing_risk.student_id, students[7].id]), "status": "SCHEDULED",
    })
    talk_record = db.scalars(select(TalkRecord).where(
        TalkRecord.tenant_id == tenant_id, TalkRecord.plan_id.is_(None), TalkRecord.is_deleted.is_(False),
    ).order_by(TalkRecord.id)).first()
    if talk_record is None:
        raise RuntimeError("007 学工核心链缺少可回链的既有谈话记录")
    talk_record.plan_id = plan.id

    for biz_type, biz_id, action, before, after, detail in (
        ("AID_OBJECTION", public_aid.id, "SUBMIT", "PUBLICITY", "OBJECTION_REVIEW", "学生在公示期内补充医疗支出证据。"),
        ("FUNDING_AMOUNT", funding_apps[1].id, "ADJUST_REQUEST", "3000.00", "3600.00", "辅导员发起金额调整，等待资助中心双人复核。"),
        ("DORM_TRANSFER", occupied_beds[0].student_id, "COUNSELOR_REVIEW", "SUBMITTED", "COUNSELOR_REVIEW", "目标床位仍为空闲并已加审批占用提示。"),
        ("PSY_REFERRAL", referral.id, "FOLLOW_UP", "REFERRED", "FOLLOWING", "心理老师完成首次人工核实并预约面谈。"),
    ):
        _put(db, CsAuditTrail, tenant_id, {"biz_type": biz_type, "biz_id": str(biz_id), "action": action}, {
            "operator": teacher.real_name, "role_name": "辅导员/业务经办人", "detail": detail,
            "before_val": before, "after_val": after, "occurred_at": NOW,
        })

    db.commit()
    return validate_affairs_core_flows(db, tenant_id)


def validate_affairs_core_flows(db, tenant_id: int) -> dict:
    from app.models import (
        AffairsRiskHandle, AidObjection, CsAuditTrail, DisciplineAppeal, DisciplineRemoveApply, DormCheckRecord,
        DormCheckTask, DormTransfer, FeeReduction, FundingAppeal, PsyReferral,
        PsySurveySubmission, StudentLoan, TalkPlan, WorkStudyMonthly, WorkStudyPost, WorkStudyRecord,
    )
    from app.models.affairs_discipline_integrity import DisciplineSubflowLock

    models = {
        "aidObjection": AidObjection, "fundingAppeal": FundingAppeal,
        "disciplineAppeal": DisciplineAppeal, "disciplineRemove": DisciplineRemoveApply,
        "disciplineLocks": DisciplineSubflowLock, "dormTransfer": DormTransfer,
        "dormCheckTask": DormCheckTask, "dormCheckRecord": DormCheckRecord,
        "workStudyPost": WorkStudyPost, "workStudyRecord": WorkStudyRecord,
        "workStudyMonthly": WorkStudyMonthly, "studentLoan": StudentLoan,
        "feeReduction": FeeReduction, "riskHandle": AffairsRiskHandle, "psyReferral": PsyReferral,
        "psySurvey": PsySurveySubmission, "talkPlan": TalkPlan, "campusAudit": CsAuditTrail,
    }
    result = {}
    for key, model in models.items():
        terms = [model.tenant_id == tenant_id]
        if hasattr(model, "is_deleted"):
            terms.append(model.is_deleted.is_(False))
        result[key] = int(db.scalar(select(func.count()).select_from(model).where(*terms)) or 0)
    result["fundingAmountAdjustment"] = int(db.scalar(text("""
        SELECT COUNT(*) FROM t_affairs_funding_amount_adjustment
        WHERE tenant_id=:tenant_id AND is_deleted=0
    """), {"tenant_id": tenant_id}) or 0)
    result["passed"] = all(value > 0 for value in result.values())
    if not result["passed"]:
        raise RuntimeError(f"007 学工核心链校验失败: {result}")
    return result
