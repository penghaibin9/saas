"""岗位实习批次计划书：草稿编制、版本化发布、学生本人确认。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    InternshipAuditTrail, InternshipBatch, InternshipBatchPlan, InternshipBatchScopeRule,
    InternshipPlanAck, InternshipPlanAssignment, InternshipPlanTaskProgress,
    InternshipRecord, StudentProfile,
)
from app.services import file_service
from app.services.db_service import _as_id, _iso, _tid, session

STATUS_LABEL = {"DRAFT": "草稿", "PUBLISHED": "已发布"}
ACK_LABEL = {"PENDING": "待确认", "ACKNOWLEDGED": "已确认"}

PLAN_TYPES = {
    "POST": "顶岗实习（岗位实习）",
    "COGNITIVE": "认知实习",
    "FOLLOW_POST": "跟岗实习",
    "APPRENTICESHIP": "学徒制",
    "COMPREHENSIVE": "综合实训",
    "OTHER": "其他",
}
MAX_PLAN_ATTACHMENTS = 20

PLAN_TEMPLATES = (
    {
        "code": "SOFTWARE_POST",
        "name": "软件技术专业岗位实习方案",
        "internshipType": "POST",
        "title": "软件技术专业岗位实习计划",
        "targetAudience": "软件技术及相关专业参加岗位实习的学生",
        "objectives": "通过真实岗位实践巩固软件开发、测试、运维与团队协作能力，形成职业规范和岗位胜任力。",
        "requirements": "遵守学校与实习单位制度，完成岗前安全教育、协议和保险要求；按计划签到、提交周记及过程材料，接受校企双方指导。",
        "content": "围绕需求分析、编码实现、测试验证、版本管理、部署运维和项目协作开展岗位实践，过程任务以实际岗位安排为准。",
        "assessmentContent": "结合签到与纪律、周记及过程报告、计划任务、企业评价、教师评价和总结考核形成综合成绩。",
        "tasks": [
            {"name": "完成岗前安全与制度学习", "requirement": "完成学校和企业要求的岗前学习并留存完成事实"},
            {"name": "完成岗位实践任务", "requirement": "按企业岗位安排参与真实项目或生产任务"},
            {"name": "完成过程报告与总结", "requirement": "按计划提交周记、过程报告和实习总结"},
        ],
    },
    {
        "code": "ECOMMERCE_POST",
        "name": "电子商务专业岗位实习方案",
        "internshipType": "POST",
        "title": "电子商务专业岗位实习计划",
        "targetAudience": "电子商务及相关专业参加岗位实习的学生",
        "objectives": "在真实业务环境中训练商品运营、内容运营、客户服务、数据分析与合规经营能力。",
        "requirements": "遵守实习单位业务规范和数据安全要求，按计划完成签到、业务任务、周记、月报和总结。",
        "content": "围绕店铺运营、商品管理、营销活动、客户服务、数据复盘等岗位工作开展实践。",
        "assessmentContent": "综合过程任务完成情况、报告质量、企业评价、教师评价与实习总结进行考核。",
        "tasks": [
            {"name": "完成岗位业务熟悉", "requirement": "掌握所在岗位流程、工具与合规要求"},
            {"name": "完成阶段业务任务", "requirement": "按岗位要求完成可核验的运营或服务任务"},
            {"name": "完成数据复盘与总结", "requirement": "形成阶段复盘和实习总结"},
        ],
    },
    {
        "code": "MECHATRONICS_POST",
        "name": "机电一体化专业岗位实习方案",
        "internshipType": "POST",
        "title": "机电一体化专业岗位实习计划",
        "targetAudience": "机电一体化及相关专业参加岗位实习的学生",
        "objectives": "在真实生产环境中训练设备操作、维护、质量意识、安全规范和现场协作能力。",
        "requirements": "严格执行安全生产和设备操作规程，未经授权不得独立操作高风险设备；按计划完成签到、任务和过程记录。",
        "content": "围绕设备认知、生产操作、点检维护、质量控制和现场改善开展岗位实践。",
        "assessmentContent": "重点考核安全纪律、岗位技能、任务完成质量、企业评价、教师评价和总结表现。",
        "tasks": [
            {"name": "完成安全生产培训", "requirement": "通过企业和学校规定的安全培训后方可上岗"},
            {"name": "完成设备与工艺学习", "requirement": "掌握所在岗位设备、工艺和质量控制要求"},
            {"name": "完成岗位实践与总结", "requirement": "按指导要求完成实践任务和总结材料"},
        ],
    },
    {
        "code": "COGNITIVE_GENERAL",
        "name": "认知实习通用方案",
        "internshipType": "COGNITIVE",
        "title": "认知实习计划",
        "targetAudience": "参加本批次认知实习的学生",
        "objectives": "了解行业、企业、岗位和职业规范，建立专业学习与职业发展的联系。",
        "requirements": "按统一安排参加参观、讲解、岗位认知和交流活动，遵守安全及保密要求并完成认知记录。",
        "content": "行业认知、企业认知、岗位认知、职业规范与安全教育。",
        "assessmentContent": "根据出勤、任务完成、认知报告和指导教师评价进行考核。",
        "tasks": [
            {"name": "完成企业与岗位认知", "requirement": "参加计划安排的认知活动"},
            {"name": "提交认知实习报告", "requirement": "形成结构完整的认知实习总结"},
        ],
    },
    {
        "code": "APPRENTICESHIP_GENERAL",
        "name": "学徒制通用方案",
        "internshipType": "APPRENTICESHIP",
        "title": "现代学徒制实习计划",
        "targetAudience": "参加现代学徒制培养的学生",
        "objectives": "通过校企双导师和真实岗位任务形成持续的职业技能训练与岗位能力评价。",
        "requirements": "执行校企联合培养要求，接受双导师指导，按阶段完成岗位任务、过程记录和考核。",
        "content": "按培养方案开展岗位学习、技能训练、生产任务、阶段评价与综合总结。",
        "assessmentContent": "按照校企共同确定的考核内容与分数比例形成综合评价。",
        "tasks": [
            {"name": "完成双导师见面与岗位确认", "requirement": "明确岗位、导师和阶段任务"},
            {"name": "完成阶段技能任务", "requirement": "按培养计划完成可核验的技能任务"},
            {"name": "完成阶段与综合考核", "requirement": "完成校企双方要求的阶段评价和总结"},
        ],
    },
)


def list_plan_templates() -> list[dict]:
    return [dict(item) for item in PLAN_TEMPLATES]


def _template(code: str | None) -> dict | None:
    value = str(code or "").strip().upper()
    if not value:
        return None
    item = next((row for row in PLAN_TEMPLATES if row["code"] == value), None)
    if not item:
        raise AppException("VALIDATION_ERROR", "所选内置实习方案模板不存在")
    return dict(item)


def _plan_attachments(raw) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise AppException("VALIDATION_ERROR", "计划附件必须以列表提交")
    result = []
    for value in raw:
        fid = str(value or "").strip()
        if not fid or fid in result:
            continue
        if len(result) >= MAX_PLAN_ATTACHMENTS:
            raise AppException("VALIDATION_ERROR", f"计划附件最多上传 {MAX_PLAN_ATTACHMENTS} 个")
        if not file_service.get_file_meta(fid):
            raise AppException("VALIDATION_ERROR", f"计划附件 {fid} 不存在或无权访问")
        result.append(fid)
    return result


def _attachment_views(file_ids) -> list[dict]:
    result = []
    for fid in list(file_ids or []):
        try:
            item = file_service.attachment_view(str(fid))
        except Exception:  # noqa: BLE001
            item = None
        if item:
            result.append(item)
    return result


def _batch_snapshot(batch) -> dict:
    start = batch.start_date.date() if batch.start_date else None
    end = batch.end_date.date() if batch.end_date else None
    weeks = None
    if start and end and end >= start:
        weeks = round(((end - start).days + 1) / 7.0, 1)
    return {
        "batchId": str(batch.id),
        "batchName": batch.batch_name or "",
        "batchNo": batch.batch_no or "",
        "academicYear": batch.academic_year or "",
        "term": batch.term or "",
        "plannedCount": int(batch.planned_count or 0),
        "startDate": start.isoformat() if start else "",
        "endDate": end.isoformat() if end else "",
        "internshipWeeks": weeks,
    }


def _rules_snapshot(batch) -> dict:
    from app.modules.internship.services.internship_service import DEFAULT_RULES, _deep_merge
    rules = _deep_merge(DEFAULT_RULES, dict(batch.rules_config or {}))
    checkin = dict(rules.get("checkin") or {})
    weekly = dict(rules.get("weeklyReport") or {})
    process = dict(rules.get("processReport") or {})
    score = dict(rules.get("score") or {})
    evaluation = dict(rules.get("evaluation") or {})
    return {
        "rulesVersion": int(batch.rules_version or 1),
        "requiredCheckinDays": int(checkin.get("requiredDays") or 0),
        "weeklyRequiredCount": int(weekly.get("requiredCount") or 0),
        "weeklyMinWordCount": int(weekly.get("minWordCount") or 0),
        "dailyRequiredCount": int(process.get("dailyRequiredCount") or 0),
        "dailyMinWordCount": int(process.get("dailyMinWords") or 0),
        "monthlyRequiredCount": int(process.get("monthlyRequiredCount") or 0),
        "monthlyMinWordCount": int(process.get("monthlyMinWords") or 0),
        "summaryRequiredCount": int(process.get("summaryRequiredCount") or 0),
        "summaryMinWordCount": int(process.get("summaryMinWords") or 0),
        "scorePassThreshold": float(score.get("passThreshold") or 0),
        "scoreComponents": list(score.get("components") or []),
        "evaluationWeights": evaluation,
    }


def _validate_plan_fields(payload: dict) -> dict:
    internship_type = str(payload.get("internshipType") or "").strip().upper()
    if internship_type not in PLAN_TYPES:
        raise AppException("VALIDATION_ERROR", "实习类别必须选择岗位实习、认知实习、跟岗实习、学徒制、综合实训或其他")
    target = str(payload.get("targetAudience") or "").strip()
    objectives = str(payload.get("objectives") or "").strip()
    requirements = str(payload.get("requirements") or "").strip()
    assessment = str(payload.get("assessmentContent") or "").strip()
    responsible = str(payload.get("responsibleName") or "").strip()
    plan_no = str(payload.get("planNo") or "").strip()
    major_name = str(payload.get("majorName") or "").strip()
    education_level = str(payload.get("educationLevel") or "").strip()
    subsidy_standard = str(payload.get("subsidyStandard") or "").strip()
    if plan_no and not 2 <= len(plan_no) <= 100:
        raise AppException("VALIDATION_ERROR", "计划编号需为 2 到 100 个字")
    if major_name and not 2 <= len(major_name) <= 200:
        raise AppException("VALIDATION_ERROR", "适用专业需为 2 到 200 个字")
    if education_level and not 2 <= len(education_level) <= 100:
        raise AppException("VALIDATION_ERROR", "培养层次需为 2 到 100 个字")
    if subsidy_standard and len(subsidy_standard) > 200:
        raise AppException("VALIDATION_ERROR", "补贴标准不能超过 200 个字")
    if len(target) < 2 or len(target) > 500:
        raise AppException("VALIDATION_ERROR", "实习对象需填写 2 到 500 个字")
    if len(objectives) < 5 or len(objectives) > 4000:
        raise AppException("VALIDATION_ERROR", "实习目的需填写 5 到 4000 个字")
    if len(requirements) < 5 or len(requirements) > 8000:
        raise AppException("VALIDATION_ERROR", "实习要求需填写 5 到 8000 个字")
    if len(assessment) < 5 or len(assessment) > 8000:
        raise AppException("VALIDATION_ERROR", "考核内容需填写 5 到 8000 个字")
    if len(responsible) < 2 or len(responsible) > 100:
        raise AppException("VALIDATION_ERROR", "负责人需填写 2 到 100 个字")
    return {
        "internshipType": internship_type,
        "planNo": plan_no,
        "majorName": major_name,
        "educationLevel": education_level,
        "subsidyStandard": subsidy_standard,
        "targetAudience": target,
        "objectives": objectives,
        "requirements": requirements,
        "assessmentContent": assessment,
        "responsibleName": responsible,
        "templateCode": str(payload.get("templateCode") or "").strip().upper() or None,
        "attachmentFileIds": _plan_attachments(payload.get("attachmentFileIds")),
    }


def _normalize_tasks(raw) -> list:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise AppException("VALIDATION_ERROR", "tasks 必须是数组")
    if len(raw) > 50:
        raise AppException("VALIDATION_ERROR", "任务清单最多50条")
    result = []
    used_orders = set()
    for index, task in enumerate(raw):
        if not isinstance(task, dict):
            raise AppException("VALIDATION_ERROR", f"任务第{index + 1}项格式错误")
        name = str(task.get("name") or "").strip()
        requirement = str(task.get("requirement") or "").strip()
        deadline = str(task.get("deadline") or "").strip() or None
        if not name and not requirement and not deadline:
            continue
        if not 2 <= len(name) <= 100:
            raise AppException("VALIDATION_ERROR", f"任务第{index + 1}项名称须为2至100字")
        if len(requirement) > 500:
            raise AppException("VALIDATION_ERROR", f"任务第{index + 1}项要求过长")
        try:
            sort_order = int(task.get("sortOrder") if task.get("sortOrder") is not None else index + 1)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", f"任务第{index + 1}项序号无效")
        if sort_order <= 0 or sort_order in used_orders:
            raise AppException("VALIDATION_ERROR", "任务序号必须为不重复的正整数")
        used_orders.add(sort_order)
        result.append({
            "sortOrder": sort_order,
            "name": name,
            "requirement": requirement or None,
            "deadline": deadline,
        })
    return sorted(result, key=lambda item: item["sortOrder"])


def _op_name(user=None) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, plan_id, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=plan_id, target_type="BATCH_PLAN",
        action=action, operator_name=operator, detail_json=detail or {},
        occurred_at=datetime.utcnow()))


def _expected(raw, current: int, label="计划") -> None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise AppException("DATA_CONFLICT", f"缺少有效{label}版本，请刷新后重试")
    if value != int(current or 0):
        raise AppException("DATA_CONFLICT", f"{label}已被其他用户修改，请刷新后重试")


def _plan_row(plan, batch=None):
    basic = dict(plan.basic_snapshot_json or {}) if plan else {}
    rules = dict(plan.rules_snapshot_json or {}) if plan else {}
    if batch and (not basic or plan.status == "DRAFT"):
        basic = _batch_snapshot(batch)
    if batch and (not rules or plan.status == "DRAFT"):
        rules = _rules_snapshot(batch)
    return {
        "id": str(plan.id), "batchId": str(plan.batch_id),
        "batchName": batch.batch_name if batch else basic.get("batchName", ""),
        "title": plan.title,
        "planNo": plan.plan_no or "",
        "majorName": plan.major_name or "",
        "educationLevel": plan.education_level or "",
        "subsidyStandard": plan.subsidy_standard or "",
        "internshipType": plan.internship_type or "",
        "internshipTypeLabel": PLAN_TYPES.get(plan.internship_type, plan.internship_type or ""),
        "targetAudience": plan.target_audience or "",
        "objectives": plan.objectives or "",
        "requirements": plan.plan_requirements or "",
        "content": plan.content or "",
        "assessmentContent": plan.assessment_content or "",
        "responsibleName": plan.responsible_name or "",
        "attachmentFileIds": list(plan.attachment_file_ids_json or []),
        "attachments": _attachment_views(plan.attachment_file_ids_json or []),
        "templateCode": plan.template_code or "",
        "tasks": plan.tasks_json or [],
        "basicSnapshot": basic,
        "rulesSnapshot": rules,
        "status": plan.status, "statusLabel": STATUS_LABEL.get(plan.status, plan.status),
        "publishedAt": _iso(plan.published_at) or "",
        "publishedByName": plan.published_by_name or "",
        "version": int(plan.version or 0),
    }


def _assert_plan_batch_scope(db, batch: InternshipBatch, user, action: str) -> None:
    """Batch-level plan may be used by scoped leaders only when the whole target cohort is in scope."""
    from app.modules.internship.services.internship_service import _current_scope
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    scope = _current_scope(user)
    if scope.get("mode") != "SCOPED":
        return

    base = select(InternshipRecord.id).where(
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.batch_id == batch.id,
        InternshipRecord.is_deleted.is_(False),
    )
    total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    if total:
        scoped = apply_internship_record_scope(base, user).subquery()
        scoped_count = int(db.scalar(select(func.count()).select_from(scoped)) or 0)
        if scoped_count == total:
            return
        raise no_permission(f"{action}超出当前学院/专业授权范围")

    scope_rule = db.scalar(select(InternshipBatchScopeRule).where(
        InternshipBatchScopeRule.tenant_id == _tid(),
        InternshipBatchScopeRule.batch_id == batch.id,
        InternshipBatchScopeRule.is_deleted.is_(False),
    ))
    if scope_rule and scope_rule.rule_json:
        from app.services import student_scope_resolver
        rule = student_scope_resolver.parse_rule(scope_rule.rule_json)
        all_result = student_scope_resolver.resolve(
            db, _tid(), rule, user=None, limit=None,
        )
        scoped_result = student_scope_resolver.resolve(
            db, _tid(), rule, user=user, limit=None,
        )
        if (
            all_result.matched_count > 0
            and scoped_result.out_of_scope_count == 0
            and scoped_result.matched_count == all_result.matched_count
        ):
            return
    raise no_permission(
        f"{action}无法证明当前批次全部属于你的学院/专业范围；请先配置批次选人范围或由校级管理员处理"
    )


def get_plan_context(batch_id, user=None) -> dict:
    with session() as db:
        batch = db.get(InternshipBatch, _as_id(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("批次不存在")
        _assert_plan_batch_scope(db, batch, user, "查看实习计划")
        return {
            "basicSnapshot": _batch_snapshot(batch),
            "rulesSnapshot": _rules_snapshot(batch),
            "planTypes": [{"value": code, "label": label} for code, label in PLAN_TYPES.items()],
        }


def get_plan_by_batch(batch_id, user=None):
    with session() as db:
        batch = db.get(InternshipBatch, _as_id(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("批次不存在")
        _assert_plan_batch_scope(db, batch, user, "查看实习计划")
        plan = db.scalar(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(),
            InternshipBatchPlan.batch_id == batch.id,
            InternshipBatchPlan.is_deleted.is_(False)))
        return _plan_row(plan, batch) if plan else None


def save_plan(batch_id, body, user=None) -> dict:
    from app.core.permissions import enforce_permission
    enforce_permission(user or {}, "internship.plan.manage")
    payload = body or {}
    title = str(payload.get("title") or "").strip()
    content = str(payload.get("content") or "").strip()
    if len(title) < 2 or len(title) > 200:
        raise AppException("VALIDATION_ERROR", "计划标题需为 2 到 200 个字")
    if len(content) < 20 or len(content) > 20000:
        raise AppException("VALIDATION_ERROR", "实习内容需为 20 到 20000 个字")
    template = _template(payload.get("templateCode"))
    fields = _validate_plan_fields(payload)
    if template and template["internshipType"] != fields["internshipType"]:
        raise AppException("VALIDATION_ERROR", "当前实习类别与所选模板类型不一致")
    tasks = _normalize_tasks(payload.get("tasks"))
    if not tasks:
        raise AppException("VALIDATION_ERROR", "至少配置1项可执行计划任务")
    with session() as db:
        batch = db.scalar(select(InternshipBatch).where(
            InternshipBatch.id == _as_id(batch_id),
            InternshipBatch.tenant_id == _tid(),
            InternshipBatch.is_deleted.is_(False)).with_for_update())
        if not batch:
            raise not_found("批次不存在")
        _assert_plan_batch_scope(db, batch, user, "保存实习计划")
        plan = db.scalar(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(),
            InternshipBatchPlan.batch_id == batch.id,
            InternshipBatchPlan.is_deleted.is_(False)).with_for_update())
        if plan and plan.status == "PUBLISHED":
            raise AppException("DATA_CONFLICT", "已发布计划不可直接编辑；请通过新批次或正式版本变更流程处理")
        if plan:
            _expected(payload.get("expectedVersion"), plan.version)
        else:
            plan = InternshipBatchPlan(
                tenant_id=_tid(), batch_id=batch.id, title=title, status="DRAFT")
            db.add(plan)
        plan.title = title
        plan.plan_no = fields["planNo"] or None
        plan.major_name = fields["majorName"] or None
        plan.education_level = fields["educationLevel"] or None
        plan.subsidy_standard = fields["subsidyStandard"] or None
        plan.internship_type = fields["internshipType"]
        plan.target_audience = fields["targetAudience"]
        plan.objectives = fields["objectives"]
        plan.plan_requirements = fields["requirements"]
        plan.content = content
        plan.assessment_content = fields["assessmentContent"]
        plan.responsible_name = fields["responsibleName"]
        plan.attachment_file_ids_json = fields["attachmentFileIds"] or None
        plan.template_code = fields["templateCode"]
        plan.tasks_json = tasks
        plan.basic_snapshot_json = _batch_snapshot(batch)
        plan.rules_snapshot_json = _rules_snapshot(batch)
        plan.version = int(plan.version or 0) + 1
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            if "uk_ix_intern_plan_no" in str(exc.orig):
                raise AppException("DATA_CONFLICT", "计划编号已被使用，请更换编号后重试", http_status=409) from exc
            raise
        for file_id in fields["attachmentFileIds"]:
            file_service.bind_file_biz(
                file_id, "INTERNSHIP_PLAN", str(plan.id), user=user, db=db)
        _trail(db, plan.id, "SAVE_VERSIONED", {
            "batchId": str(batch.id),
            "internshipType": fields["internshipType"],
            "templateCode": fields["templateCode"] or "",
            "taskCount": len(tasks),
            "attachmentCount": len(fields["attachmentFileIds"]),
            "rulesVersion": int(batch.rules_version or 1),
            "newVersion": int(plan.version or 0),
        }, _op_name(user))
        db.commit()
        return _plan_row(plan, batch)


def publish_plan(batch_id, body=None, user=None) -> dict:
    from app.core.permissions import enforce_permission
    enforce_permission(user or {}, "internship.plan.manage")
    payload = body or {}
    with session() as db:
        batch = db.scalar(select(InternshipBatch).where(
            InternshipBatch.id == _as_id(batch_id),
            InternshipBatch.tenant_id == _tid(),
            InternshipBatch.is_deleted.is_(False)).with_for_update())
        if not batch:
            raise not_found("批次不存在")
        _assert_plan_batch_scope(db, batch, user, "发布实习计划")
        plan = db.scalar(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(),
            InternshipBatchPlan.batch_id == batch.id,
            InternshipBatchPlan.is_deleted.is_(False)).with_for_update())
        if not plan:
            raise not_found("请先保存实习计划书")
        _expected(payload.get("expectedVersion"), plan.version)
        if plan.status == "PUBLISHED":
            raise AppException("DATA_CONFLICT", "计划已发布")
        if not (plan.tasks_json or []):
            raise AppException("DATA_CONFLICT", "计划未配置任务清单，不能发布")
        if not plan.internship_type or plan.internship_type not in PLAN_TYPES:
            raise AppException("DATA_CONFLICT", "计划未配置合法实习类别，不能发布")
        for value, label in (
            (plan.target_audience, "实习对象"),
            (plan.objectives, "实习目的"),
            (plan.plan_requirements, "实习要求"),
            (plan.content, "实习内容"),
            (plan.assessment_content, "考核内容"),
            (plan.responsible_name, "负责人"),
        ):
            if not str(value or "").strip():
                raise AppException("DATA_CONFLICT", f"计划缺少{label}，不能发布")
        plan.basic_snapshot_json = _batch_snapshot(batch)
        plan.rules_snapshot_json = _rules_snapshot(batch)
        plan.status = "PUBLISHED"
        plan.published_at = datetime.utcnow()
        plan.published_by_name = _op_name(user)
        plan.version = int(plan.version or 0) + 1
        records = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False))).all()
        ack_count = 0
        for record in records:
            ack = db.scalar(select(InternshipPlanAck).where(
                InternshipPlanAck.tenant_id == _tid(),
                InternshipPlanAck.plan_id == plan.id,
                InternshipPlanAck.internship_id == record.id,
                InternshipPlanAck.is_deleted.is_(False)))
            if ack:
                if ack.status == "PENDING":
                    ack_count += 1
                continue
            db.add(InternshipPlanAck(
                tenant_id=_tid(), plan_id=plan.id, internship_id=record.id,
                student_id=record.student_id, status="PENDING"))
            ack_count += 1
        from app.modules.internship.services.internship_plan_task_service import init_progress_for_plan
        progress_count = init_progress_for_plan(db, plan, records)
        from app.modules.internship.services import internship_plan_assignment_service as assignment_svc
        primary_assignment_count = 0
        for record in records:
            assignment_svc.ensure_primary_assignment_in_tx(
                db, plan=plan, record=record, user=user)
            primary_assignment_count += 1
        _trail(db, plan.id, "PUBLISH_VERSIONED", {
            "ackCount": ack_count, "taskProgressInit": progress_count,
            "primaryPlanAssignmentCount": primary_assignment_count,
            "internshipType": plan.internship_type,
            "rulesVersion": int(batch.rules_version or 1),
            "newVersion": int(plan.version or 0),
        }, _op_name(user))
        db.commit()
        return {
            **_plan_row(plan, batch), "ackCount": ack_count,
            "taskProgressInit": progress_count,
            "primaryPlanAssignmentCount": primary_assignment_count,
        }


def _plan_document_lines(plan_view: dict) -> list[str]:
    basic = plan_view.get("basicSnapshot") or {}
    rules = plan_view.get("rulesSnapshot") or {}
    components = rules.get("scoreComponents") or []
    comp_text = "；".join(
        f"{item.get('name') or '考核项'} {round(float(item.get('weight') or 0) * 100, 1)}%"
        for item in components
    ) or "未配置"
    lines = [
        f"计划编号：{plan_view.get('planNo') or '—'}",
        f"适用专业：{plan_view.get('majorName') or '—'}",
        f"培养层次：{plan_view.get('educationLevel') or '—'}",
        f"补贴标准：{plan_view.get('subsidyStandard') or '—'}",
        f"实习对象：{plan_view.get('targetAudience') or '—'}",
        f"实习类别：{plan_view.get('internshipTypeLabel') or '—'}",
        f"实习人数：{basic.get('plannedCount', 0)} 人",
        f"实习目的：{plan_view.get('objectives') or '—'}",
        f"实习要求：{plan_view.get('requirements') or '—'}",
        f"实习内容：{plan_view.get('content') or '—'}",
        f"考核内容：{plan_view.get('assessmentContent') or '—'}",
        f"开始时间：{basic.get('startDate') or '—'}",
        f"结束时间：{basic.get('endDate') or '—'}",
        f"实习周数：{basic.get('internshipWeeks') if basic.get('internshipWeeks') is not None else '—'}",
        f"负责人：{plan_view.get('responsibleName') or '—'}",
        f"计划签到天数：{rules.get('requiredCheckinDays') if rules.get('requiredCheckinDays') is not None else '未配置'}",
        f"日报篇数：{rules.get('dailyRequiredCount') if rules.get('dailyRequiredCount') is not None else '未配置'}；最少字数：{rules.get('dailyMinWordCount') if rules.get('dailyMinWordCount') is not None else '未配置'}",
        f"周记篇数：{rules.get('weeklyRequiredCount') if rules.get('weeklyRequiredCount') is not None else '未配置'}",
        f"月报篇数：{rules.get('monthlyRequiredCount') if rules.get('monthlyRequiredCount') is not None else '未配置'}；最少字数：{rules.get('monthlyMinWordCount') if rules.get('monthlyMinWordCount') is not None else '未配置'}",
        f"总结篇数：{rules.get('summaryRequiredCount') if rules.get('summaryRequiredCount') is not None else '未配置'}；最少字数：{rules.get('summaryMinWordCount') if rules.get('summaryMinWordCount') is not None else '未配置'}",
        f"周记最少字数：{rules.get('weeklyMinWordCount') if rules.get('weeklyMinWordCount') is not None else '未配置'}",
        f"考核分数比例：{comp_text}",
        f"及格线：{rules.get('scorePassThreshold') if rules.get('scorePassThreshold') is not None else '—'}",
        "",
        "任务清单：",
    ]
    for index, task in enumerate(plan_view.get("tasks") or [], 1):
        lines.append(
            f"{index}. {task.get('name') or '未命名'}；"
            f"要求：{task.get('requirement') or '—'}；截止：{task.get('deadline') or '—'}"
        )
    attachments = plan_view.get("attachments") or []
    if attachments:
        lines.append("")
        lines.append("计划附件：" + "；".join(
            str(item.get("fileName") or item.get("name") or item.get("fileId") or "")
            for item in attachments
        ))
    return lines


def export_plan_pdf(batch_id, user=None) -> dict:
    from app.services import pdf_util
    plan = get_plan_by_batch(batch_id, user=user)
    if not plan:
        raise not_found("当前批次没有实习计划")
    content = pdf_util.build_text_pdf(
        plan["title"],
        "\n".join(_plan_document_lines(plan)),
        watermark=(
            f"跃科岗位实习管理平台 · 批次 {plan.get('batchName') or plan.get('batchId')} · "
            f"计划版本 V{plan.get('version')}"
        ),
    )
    return pdf_util.pack_pdf_result(content, f"{plan['title']}.pdf")


def export_plan_xlsx(batch_id, user=None) -> dict:
    from app.services import xlsx_util
    plan = get_plan_by_batch(batch_id, user=user)
    if not plan:
        raise not_found("当前批次没有实习计划")
    basic = plan.get("basicSnapshot") or {}
    rules = plan.get("rulesSnapshot") or {}
    rows = [
        ["计划编号", plan.get("planNo") or ""],
        ["适用专业", plan.get("majorName") or ""],
        ["培养层次", plan.get("educationLevel") or ""],
        ["补贴标准", plan.get("subsidyStandard") or ""],
        ["实习对象", plan.get("targetAudience") or ""],
        ["实习类别", plan.get("internshipTypeLabel") or ""],
        ["实习人数", basic.get("plannedCount", 0)],
        ["实习目的", plan.get("objectives") or ""],
        ["实习要求", plan.get("requirements") or ""],
        ["实习内容", plan.get("content") or ""],
        ["考核内容", plan.get("assessmentContent") or ""],
        ["开始时间", basic.get("startDate") or ""],
        ["结束时间", basic.get("endDate") or ""],
        ["实习周数", basic.get("internshipWeeks") if basic.get("internshipWeeks") is not None else ""],
        ["负责人", plan.get("responsibleName") or ""],
        ["计划签到天数", rules.get("requiredCheckinDays") if rules.get("requiredCheckinDays") is not None else "未配置"],
        ["日报篇数", rules.get("dailyRequiredCount") if rules.get("dailyRequiredCount") is not None else "未配置"],
        ["周记篇数", rules.get("weeklyRequiredCount") if rules.get("weeklyRequiredCount") is not None else "未配置"],
        ["月报篇数", rules.get("monthlyRequiredCount") if rules.get("monthlyRequiredCount") is not None else "未配置"],
        ["总结篇数", rules.get("summaryRequiredCount") if rules.get("summaryRequiredCount") is not None else "未配置"],
        ["周记最少字数", rules.get("weeklyMinWordCount") if rules.get("weeklyMinWordCount") is not None else "未配置"],
        ["日报最少字数", rules.get("dailyMinWordCount") if rules.get("dailyMinWordCount") is not None else "未配置"],
        ["月报最少字数", rules.get("monthlyMinWordCount") if rules.get("monthlyMinWordCount") is not None else "未配置"],
        ["总结最少字数", rules.get("summaryMinWordCount") if rules.get("summaryMinWordCount") is not None else "未配置"],
        ["及格线", rules.get("scorePassThreshold") if rules.get("scorePassThreshold") is not None else ""],
    ]
    for index, item in enumerate(rules.get("scoreComponents") or [], 1):
        rows.append([
            f"考核比例{index}",
            f"{item.get('name') or '考核项'}：{round(float(item.get('weight') or 0) * 100, 1)}%",
        ])
    for index, task in enumerate(plan.get("tasks") or [], 1):
        rows.append([
            f"任务{index}",
            f"{task.get('name') or ''}｜{task.get('requirement') or ''}｜{task.get('deadline') or ''}",
        ])
    for index, item in enumerate(plan.get("attachments") or [], 1):
        rows.append([
            f"附件{index}",
            item.get("fileName") or item.get("name") or item.get("fileId") or "",
        ])
    content = xlsx_util.build_ledger_xlsx(
        "实习计划",
        ["计划字段", "内容"],
        rows,
        watermark=(
            f"跃科岗位实习管理平台 · {plan.get('batchName') or ''} · "
            f"计划版本 V{plan.get('version')}"
        ),
    )
    return xlsx_util.pack_xlsx_result(content, f"{plan['title']}.xlsx", len(rows))


def _bulk_plan_views(batch_ids, user=None) -> list[dict]:
    if not isinstance(batch_ids, list) or not batch_ids:
        raise AppException("VALIDATION_ERROR", "请选择实习批次数组")
    if len(batch_ids) > 100:
        raise AppException("VALIDATION_ERROR", "单次最多批量导出 100 个实习计划")
    ids = []
    for raw in batch_ids:
        if isinstance(raw, bool) or not isinstance(raw, (str, int)):
            raise AppException("VALIDATION_ERROR", "批量导出的批次 ID 格式非法")
        value = str(raw).strip()
        if len(value) > 19 or not value.isascii() or not value.isdigit() or not 0 < int(value) <= 9223372036854775807:
            raise AppException("VALIDATION_ERROR", "批量导出的批次 ID 必须为有效正整数")
        bid = int(value)
        if bid not in ids:
            ids.append(bid)
    plans = []
    missing = []
    for bid in ids:
        plan = get_plan_by_batch(bid, user=user)
        if not plan:
            missing.append(str(bid))
        else:
            plans.append(plan)
    if missing:
        raise AppException(
            "DATA_CONFLICT",
            "以下批次尚未建立实习计划，不能静默跳过：" + "、".join(missing),
        )
    return plans


def bulk_export_plans_pdf(batch_ids, user=None) -> dict:
    from app.services import pdf_util
    plans = _bulk_plan_views(batch_ids, user=user)
    sections = []
    for index, plan in enumerate(plans, 1):
        if index > 1:
            sections.extend(["", "----------------------------------------", ""])
        sections.extend([
            f"第 {index} 份计划｜{plan.get('batchName') or plan.get('batchId')}",
            f"计划标题：{plan.get('title') or '—'}",
            *_plan_document_lines(plan),
        ])
    content = pdf_util.build_text_pdf(
        "岗位实习计划批量导出",
        "\n".join(sections),
        watermark=f"跃科岗位实习管理平台 · 共 {len(plans)} 份计划 · {datetime.now():%Y-%m-%d %H:%M}",
    )
    return pdf_util.pack_pdf_result(content, "岗位实习计划_批量导出.pdf")


def bulk_export_plans_xlsx(batch_ids, user=None) -> dict:
    from app.services import xlsx_util
    plans = _bulk_plan_views(batch_ids, user=user)
    rows = []
    for plan in plans:
        basic = plan.get("basicSnapshot") or {}
        rules = plan.get("rulesSnapshot") or {}
        component_text = "；".join(
            f"{item.get('name') or '考核项'} {round(float(item.get('weight') or 0) * 100, 1)}%"
            for item in rules.get("scoreComponents") or []
        )
        rows.append([
            plan.get("batchName") or "",
            basic.get("batchNo") or "",
            plan.get("title") or "",
            plan.get("internshipTypeLabel") or "",
            plan.get("targetAudience") or "",
            basic.get("plannedCount", 0),
            plan.get("responsibleName") or "",
            basic.get("startDate") or "",
            basic.get("endDate") or "",
            basic.get("internshipWeeks") if basic.get("internshipWeeks") is not None else "",
            plan.get("objectives") or "",
            plan.get("requirements") or "",
            plan.get("content") or "",
            plan.get("assessmentContent") or "",
            rules.get("requiredCheckinDays") if rules.get("requiredCheckinDays") is not None else "未配置",
            rules.get("weeklyRequiredCount") if rules.get("weeklyRequiredCount") is not None else "未配置",
            rules.get("weeklyMinWordCount") if rules.get("weeklyMinWordCount") is not None else "未配置",
            component_text or "未配置",
            plan.get("statusLabel") or "",
            plan.get("version") or 0,
            plan.get("planNo") or "",
            plan.get("majorName") or "",
            plan.get("educationLevel") or "",
            plan.get("subsidyStandard") or "",
            *[rules.get(key) if rules.get(key) is not None else "未配置" for key in (
                "dailyRequiredCount", "dailyMinWordCount", "monthlyRequiredCount",
                "monthlyMinWordCount", "summaryRequiredCount", "summaryMinWordCount")],
        ])
    content = xlsx_util.build_ledger_xlsx(
        "实习计划批量导出",
        [
            "批次名称", "批次编号", "计划标题", "实习类别", "实习对象", "实习人数",
            "负责人", "开始时间", "结束时间", "实习周数", "实习目的", "实习要求",
            "实习内容", "考核内容", "签到天数", "周记篇数", "周记字数",
            "考核分数比例", "计划状态", "计划版本",
            "计划编号", "专业", "培养层次", "补贴标准",
            "日报篇数", "日报字数", "月报篇数", "月报字数", "总结篇数", "总结字数",
        ],
        rows,
        watermark=f"跃科岗位实习管理平台 · 批量导出 {len(rows)} 份计划 · {datetime.now():%Y-%m-%d %H:%M}",
    )
    return xlsx_util.pack_xlsx_result(content, "岗位实习计划_批量导出.xlsx", len(rows))


def list_acks(page, page_size, batch_id=None, status=None, keyword=None, user=None):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    scope, in_scope = _current_scope(user), _rec_in_scope
    with session() as db:
        query = select(InternshipPlanAck).where(
            InternshipPlanAck.tenant_id == _tid(),
            InternshipPlanAck.is_deleted.is_(False))
        if status:
            query = query.where(InternshipPlanAck.status == status)
        rows = db.scalars(query.order_by(InternshipPlanAck.id.desc())).all()
        items = []
        for ack in rows:
            record = db.get(InternshipRecord, ack.internship_id)
            student = db.get(StudentProfile, ack.student_id)
            plan = db.get(InternshipBatchPlan, ack.plan_id)
            if batch_id and (not record or str(record.batch_id) != str(batch_id)):
                continue
            if keyword and (not student or keyword.strip() not in (student.real_name or "")):
                continue
            if not in_scope(scope, db, record, student):
                continue
            items.append({
                "id": str(ack.id), "internId": str(ack.internship_id),
                "studentName": student.real_name if student else "-",
                "studentNo": student.student_no if student else "-",
                "batchId": str(record.batch_id) if record and record.batch_id else "",
                "planId": str(plan.id) if plan else "",
                "planTitle": plan.title if plan else "",
                "planVersion": int(plan.version or 0) if plan else 0,
                "status": ack.status, "statusLabel": ACK_LABEL.get(ack.status, ack.status),
                "acknowledgedAt": _iso(ack.acknowledged_at) or "",
                "version": int(ack.version or 0),
            })
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def _student_plan_for_record(db, record, plan_id=None, *, lock=False):
    """Resolve one plan explicitly assigned to this student's canonical internship record.

    Compatibility: legacy/current primary plan may be projected from record.batch_id when old data
    predates plan-assignment rows.  Any non-primary plan requires an ACTIVE assignment fact.
    """
    if not record or not record.batch_id:
        return None, None
    assignment = None
    plan = None

    if plan_id not in (None, ""):
        try:
            pid = int(plan_id)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "planId 格式非法") from None
        aq = select(InternshipPlanAssignment).where(
            InternshipPlanAssignment.tenant_id == _tid(),
            InternshipPlanAssignment.internship_id == record.id,
            InternshipPlanAssignment.plan_id == pid,
            InternshipPlanAssignment.status == "ACTIVE",
            InternshipPlanAssignment.is_deleted.is_(False),
        )
        assignment = db.scalar(aq.with_for_update() if lock else aq)
        pq = select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(),
            InternshipBatchPlan.id == pid,
            InternshipBatchPlan.status == "PUBLISHED",
            InternshipBatchPlan.is_deleted.is_(False),
        )
        plan = db.scalar(pq.with_for_update() if lock else pq)
        if not plan:
            raise AppException("DATA_NOT_FOUND", "实习方案不存在或尚未发布")
        if not assignment and int(plan.batch_id or 0) != int(record.batch_id or 0):
            raise AppException("NO_PERMISSION", "该实习方案未分配给当前学生", http_status=403)
    else:
        aq = select(InternshipPlanAssignment).where(
            InternshipPlanAssignment.tenant_id == _tid(),
            InternshipPlanAssignment.internship_id == record.id,
            InternshipPlanAssignment.status == "ACTIVE",
            InternshipPlanAssignment.is_primary.is_(True),
            InternshipPlanAssignment.is_deleted.is_(False),
        ).order_by(
            InternshipPlanAssignment.assigned_at.asc(),
            InternshipPlanAssignment.id.asc(),
        )
        assignment = db.scalar(aq.with_for_update() if lock else aq)
        if assignment:
            pq = select(InternshipBatchPlan).where(
                InternshipBatchPlan.tenant_id == _tid(),
                InternshipBatchPlan.id == assignment.plan_id,
                InternshipBatchPlan.status == "PUBLISHED",
                InternshipBatchPlan.is_deleted.is_(False),
            )
            plan = db.scalar(pq.with_for_update() if lock else pq)
        if not plan:
            pq = select(InternshipBatchPlan).where(
                InternshipBatchPlan.tenant_id == _tid(),
                InternshipBatchPlan.batch_id == record.batch_id,
                InternshipBatchPlan.status == "PUBLISHED",
                InternshipBatchPlan.is_deleted.is_(False),
            )
            plan = db.scalar(pq.with_for_update() if lock else pq)
    return plan, assignment


def student_assigned_plans(user) -> dict:
    from app.modules.internship.services.internship_agreement_service import _student_record
    with session() as db:
        record, _student = _student_record(db, user)
        if not record:
            return {"items": [], "total": 0, "primaryPlanId": ""}

        assignments = db.scalars(select(InternshipPlanAssignment).where(
            InternshipPlanAssignment.tenant_id == _tid(),
            InternshipPlanAssignment.internship_id == record.id,
            InternshipPlanAssignment.status == "ACTIVE",
            InternshipPlanAssignment.is_deleted.is_(False),
        ).order_by(
            InternshipPlanAssignment.is_primary.desc(),
            InternshipPlanAssignment.assigned_at.asc(),
            InternshipPlanAssignment.id.asc(),
        )).all()

        rows = []
        seen_plan_ids = set()
        for assignment in assignments:
            plan = db.scalar(select(InternshipBatchPlan).where(
                InternshipBatchPlan.id == assignment.plan_id,
                InternshipBatchPlan.tenant_id == _tid(),
                InternshipBatchPlan.status == "PUBLISHED",
                InternshipBatchPlan.is_deleted.is_(False),
            ))
            if not plan:
                continue
            batch = db.get(InternshipBatch, plan.batch_id)
            ack = db.scalar(select(InternshipPlanAck).where(
                InternshipPlanAck.tenant_id == _tid(),
                InternshipPlanAck.plan_id == plan.id,
                InternshipPlanAck.internship_id == record.id,
                InternshipPlanAck.is_deleted.is_(False),
            ))
            progress = db.scalars(select(InternshipPlanTaskProgress).where(
                InternshipPlanTaskProgress.tenant_id == _tid(),
                InternshipPlanTaskProgress.plan_id == plan.id,
                InternshipPlanTaskProgress.internship_id == record.id,
                InternshipPlanTaskProgress.is_deleted.is_(False),
            )).all()
            approved = sum(1 for item in progress if item.status == "APPROVED")
            rows.append({
                "assignmentId": str(assignment.id),
                "planId": str(plan.id),
                "planVersion": int(plan.version or 0),
                "planTitle": plan.title,
                "planBatchId": str(plan.batch_id),
                "batchName": batch.batch_name if batch else "",
                "internshipType": plan.internship_type or "",
                "internshipTypeLabel": PLAN_TYPES.get(plan.internship_type, plan.internship_type or ""),
                "isPrimary": bool(assignment.is_primary),
                "ackStatus": ack.status if ack else "PENDING",
                "ackStatusLabel": ACK_LABEL.get(ack.status if ack else "PENDING"),
                "taskCount": len(progress),
                "approvedTaskCount": approved,
                "taskRate": round(approved * 100 / len(progress)) if progress else 0,
            })
            seen_plan_ids.add(int(plan.id))

        # Legacy compatibility before ix0021 backfill has run.
        primary = db.scalar(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(),
            InternshipBatchPlan.batch_id == record.batch_id,
            InternshipBatchPlan.status == "PUBLISHED",
            InternshipBatchPlan.is_deleted.is_(False),
        ))
        if primary and int(primary.id) not in seen_plan_ids:
            batch = db.get(InternshipBatch, primary.batch_id)
            ack = db.scalar(select(InternshipPlanAck).where(
                InternshipPlanAck.tenant_id == _tid(),
                InternshipPlanAck.plan_id == primary.id,
                InternshipPlanAck.internship_id == record.id,
                InternshipPlanAck.is_deleted.is_(False),
            ))
            progress = db.scalars(select(InternshipPlanTaskProgress).where(
                InternshipPlanTaskProgress.tenant_id == _tid(),
                InternshipPlanTaskProgress.plan_id == primary.id,
                InternshipPlanTaskProgress.internship_id == record.id,
                InternshipPlanTaskProgress.is_deleted.is_(False),
            )).all()
            approved = sum(1 for item in progress if item.status == "APPROVED")
            rows.insert(0, {
                "assignmentId": "",
                "planId": str(primary.id),
                "planVersion": int(primary.version or 0),
                "planTitle": primary.title,
                "planBatchId": str(primary.batch_id),
                "batchName": batch.batch_name if batch else "",
                "internshipType": primary.internship_type or "",
                "internshipTypeLabel": PLAN_TYPES.get(primary.internship_type, primary.internship_type or ""),
                "isPrimary": True,
                "ackStatus": ack.status if ack else "PENDING",
                "ackStatusLabel": ACK_LABEL.get(ack.status if ack else "PENDING"),
                "taskCount": len(progress),
                "approvedTaskCount": approved,
                "taskRate": round(approved * 100 / len(progress)) if progress else 0,
            })

        primary_id = next((item["planId"] for item in rows if item["isPrimary"]), "")
        return {"items": rows, "total": len(rows), "primaryPlanId": primary_id}


def student_my_plan(user, plan_id=None) -> dict | None:
    from app.modules.internship.services.internship_agreement_service import _student_record
    with session() as db:
        record, _student = _student_record(db, user)
        if not record:
            return None
        plan, assignment = _student_plan_for_record(db, record, plan_id)
        if not plan:
            return None
        ack = db.scalar(select(InternshipPlanAck).where(
            InternshipPlanAck.tenant_id == _tid(),
            InternshipPlanAck.plan_id == plan.id,
            InternshipPlanAck.internship_id == record.id,
            InternshipPlanAck.is_deleted.is_(False)))
        from app.modules.internship.services.internship_plan_task_service import _merge_tasks_with_progress
        progress_rows = db.scalars(select(InternshipPlanTaskProgress).where(
            InternshipPlanTaskProgress.tenant_id == _tid(),
            InternshipPlanTaskProgress.plan_id == plan.id,
            InternshipPlanTaskProgress.internship_id == record.id,
            InternshipPlanTaskProgress.is_deleted.is_(False))).all()
        tasks = _merge_tasks_with_progress(plan, progress_rows)
        total = len(tasks)
        approved = sum(1 for task in tasks if task.get("progressStatus") == "APPROVED")
        return {
            **_plan_row(plan),
            "assignmentId": str(assignment.id) if assignment else "",
            "isPrimary": bool(assignment.is_primary) if assignment else int(plan.batch_id) == int(record.batch_id),
            "planBatchId": str(plan.batch_id),
            "ackId": str(ack.id) if ack else "",
            "ackStatus": ack.status if ack else "PENDING",
            "ackStatusLabel": ACK_LABEL.get(ack.status if ack else "PENDING"),
            "ackVersion": int(ack.version or 0) if ack else 0,
            "acknowledgedAt": _iso(ack.acknowledged_at) if ack else "",
            "tasks": tasks,
            "taskSummary": {
                "total": total, "approved": approved,
                "rate": round(approved * 100 / total) if total else 0,
            },
        }


def student_acknowledge(user, body=None) -> dict:
    from app.modules.internship.services.internship_agreement_service import _student_record
    payload = body or {}
    with session() as db:
        if payload.get("batchId") is not None or payload.get("internshipId") is not None:
            from app.modules.internship.services.internship_student_context_guard import (
                require_explicit_context,
            )
            record, student, _batch_id = require_explicit_context(
                db, user, payload, for_write=True)
        else:
            record, student = _student_record(db, user, for_write=True)
        plan, _assignment = _student_plan_for_record(
            db, record, payload.get("planId"), lock=True)
        if not plan:
            raise AppException("DATA_NOT_FOUND", "当前没有可确认的已发布实习方案")
        ack = db.scalar(select(InternshipPlanAck).where(
            InternshipPlanAck.tenant_id == _tid(),
            InternshipPlanAck.plan_id == plan.id,
            InternshipPlanAck.internship_id == record.id,
            InternshipPlanAck.is_deleted.is_(False)).with_for_update())
        if not ack:
            raise AppException("DATA_NOT_FOUND", "当前没有待确认的实习计划回执")
        _expected(payload.get("planVersion"), plan.version, "计划正文")
        _expected(payload.get("expectedVersion"), ack.version, "确认回执")
        if ack.status != "PENDING":
            if ack.status == "ACKNOWLEDGED":
                return {
                    "id": str(ack.id), "status": ack.status,
                    "version": int(ack.version or 0), "message": "实习计划已确认",
                }
            raise AppException("DATA_CONFLICT", "当前计划回执不可确认")
        ack.status = "ACKNOWLEDGED"
        ack.acknowledged_at = datetime.utcnow()
        ack.version = int(ack.version or 0) + 1
        _trail(db, plan.id, "STUDENT_ACK_VERSIONED", {
            "studentNo": student.student_no if student else "",
            "planId": str(plan.id),
            "planBatchId": str(plan.batch_id),
            "planVersion": int(plan.version or 0),
            "newAckVersion": int(ack.version or 0),
        }, _op_name(user))
        db.commit()
        return {
            "id": str(ack.id), "status": ack.status,
            "version": int(ack.version or 0), "message": "已确认当前版本实习计划",
        }
