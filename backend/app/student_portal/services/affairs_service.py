"""学生 PC 门户 · 学工事务（第4期）。

学工学生自视图已在 mobile_affairs_service（aff：leave_my/funding_my/aid_my/discipline_my/
overview_my，均经 aff._me 收口本人+非学生403）。学生写入口为 campus_service_apply（通用事务申请：
请假/咨询/工单）。本刀 PC 接出：学工自视图聚合 + 通用事务申请 + 打印回执/请假条。
（困难认定长表+批量材料+承诺书签署 见后续专卡。）
"""
from __future__ import annotations

from types import SimpleNamespace

from app.core.exceptions import AppException
from app.services import mobile_affairs_service as aff
from app.services import mobile_student_service as stu
from app.services.mobile_student_service import (_require_student, _session,
                                                 resolve_student)
from app.student_portal.services import common_service as common


def _resolve_self_id(user: dict) -> int:
    """解析当前登录学生本人的 StudentProfile.id（PC 写入口强制本人，禁止入参指定他人）。"""
    u = _require_student(user)
    with _session() as db:
        me = resolve_student(db, u)
        if not me:
            raise AppException("DATA_NOT_FOUND", "未找到你的学生档案")
        return int(me.id)


def overview(user: dict) -> dict:
    """学工总览（本人）。"""
    return aff.overview_my(user)


def leave(user: dict) -> dict:
    """我的请假（本人）。"""
    return aff.leave_my(user)


def funding(user: dict) -> dict:
    """我的奖助勤贷补申请（本人）。"""
    return aff.funding_my(user)


def aid(user: dict) -> dict:
    """我的困难资助等级（本人）。"""
    return aff.aid_my(user)


def discipline(user: dict) -> dict:
    """我的违纪处分（本人·仅数量，明细不在自助端）。"""
    return aff.discipline_my(user)


def service_apply(user: dict, body: dict) -> dict:
    """通用学工事务申请（请假/咨询/工单，复用现有学生写入口 campus_service_apply）。"""
    return stu.campus_service_apply(user, body or {})


def print_doc(user: dict, body: dict) -> dict:
    """打印学工回执/请假条（PORTAL_PRINT + 水印）。"""
    _require_student(user)
    body = body or {}
    biz_type = str(body.get("bizType") or "AFFAIRS").strip().upper()
    doc_name = str(body.get("docName") or "学工申请回执")
    return common.print_log(user, {"bizType": biz_type,
                                   "bizId": str(body.get("bizId") or ""), "docName": doc_name})


# ── 心理测评（PC 接出）+ 我的申请聚合 + 违纪申诉 ──

def psy_questions(user: dict) -> dict:
    """心理健康自评·题目（本人）。"""
    return stu.psy_survey_questions(user)


def psy_submit(user: dict, body: dict) -> dict:
    """心理健康自评·提交（本人，需作答）。"""
    body = body or {}
    if not body.get("answers"):
        raise AppException("VALIDATION_ERROR", "请先作答再提交")
    return stu.psy_survey_submit(user, body)


def psy_history(user: dict) -> dict:
    """心理健康自评·本人历史。"""
    return stu.psy_survey_history(user)


def applications(user: dict) -> dict:
    """我的申请（本人聚合）。"""
    return stu.my_applications(user)


def discipline_appeal(user: dict, body: dict) -> dict:
    """违纪处分申辩/申诉（对已生效处分发起正式申诉，走 affairs_discipline_service 真实审批链）。

    此前误接入 campus_service_apply 通用事务申请（落无关联学生标识字段的 CsWorkOrder），
    老师端申诉审核队列读的是 DisciplineAppeal 表，两者从不相交，学生提交后申诉永远
    进不了审核——修复为按本人生效处分的 caseId 走真实申诉入口。
    """
    body = body or {}
    case_id = str(body.get("caseId") or "").strip()
    reason = str(body.get("reason") or body.get("content") or "").strip()
    if not case_id:
        raise AppException("VALIDATION_ERROR", "处分案件（caseId）必填")
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "申辩内容至少 5 个字")
    sid = _resolve_self_id(user)
    from app.models import DisciplineCase
    from app.services.db_service import _tid
    with _session() as db:
        x = db.get(DisciplineCase, int(case_id))
        if not x or x.is_deleted or x.tenant_id != _tid() or int(x.student_id or 0) != sid:
            raise AppException("DATA_NOT_FOUND", "处分记录不存在或不属于本人")
    from types import SimpleNamespace
    from app.services import affairs_discipline_service as disc
    ns = SimpleNamespace(reason=reason)
    return disc.submit_appeal(case_id, ns, user, skip_scope_check=True)


# ── 奖助勤贷补申请 / 困难认定申请（PC 长表 + 材料 + 承诺书签署；强制本人） ──

def funding_batches_open(user: dict) -> dict:
    """当前开放中的奖助勤贷补批次（本人可申请；student_id 强制走 _require_student）。"""
    _require_student(user)
    from app.services import affairs_funding_service as funding
    items, total = funding.list_batches(user, status="OPEN", page=1, page_size=50)
    return {"items": items, "total": total}


def funding_apply(user: dict, body: dict) -> dict:
    """奖助勤贷补申请（studentId 强制为本人；需勾选承诺；成功后承诺书电子签留痕）。"""
    body = body or {}
    if not str(body.get("batchId") or "").strip():
        raise AppException("VALIDATION_ERROR", "资助批次（batchId）必填")
    if not bool(body.get("confirm")):
        raise AppException("VALIDATION_ERROR", "请先阅读并勾选确认承诺书")
    sid = _resolve_self_id(user)
    ns = SimpleNamespace(studentId=str(sid), batchId=str(body.get("batchId")),
                         applySource="SELF", amount=body.get("amount"),
                         statement=str(body.get("statement") or ""))
    from app.services import affairs_funding_service as funding
    result = funding.apply(ns, user, skip_scope_check=True)
    common.sign(user, {"bizType": "FUNDING_COMMIT",
                       "bizId": str(result.get("applicationId") or ""),
                       "content": f"资助申请承诺 student={sid} batch={body.get('batchId')} "
                                  f"statement={body.get('statement') or ''}",
                       "confirm": True})
    return result


def funding_appeal(user: dict, body: dict) -> dict:
    """公示期本人对资助申请提起申诉（applicationId 须属本人且状态 PUBLICITY）。"""
    body = body or {}
    app_id = str(body.get("applicationId") or body.get("appId") or "").strip()
    reason = str(body.get("reason") or "").strip()
    if not app_id:
        raise AppException("VALIDATION_ERROR", "资助申请（applicationId）必填")
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "申诉理由至少 5 字")
    sid = _resolve_self_id(user)
    from app.models import FundingApplication
    from app.services.db_service import _tid
    from app.services.db_service import session as _session
    with _session() as db:
        x = db.get(FundingApplication, int(app_id))
        if not x or x.is_deleted or x.tenant_id != _tid() or int(x.student_id or 0) != sid:
            raise AppException("DATA_NOT_FOUND", "资助申请不存在或不属于本人")
    from types import SimpleNamespace
    from app.services import affairs_funding_service as funding
    ns = SimpleNamespace(reason=reason, appellantName=str(body.get("appellantName") or ""))
    return funding.submit_appeal(app_id, ns, user, skip_scope_check=True)


def leave_cancel(user: dict, leave_id: str, body: dict | None = None) -> dict:
    """本人对已通过/逾期请假发起销假（成熟学工产品常见：学生返校后自助销假，辅导员确认）。"""
    body = body or {}
    from app.services import affairs_leave_service as leave_svc
    note = str(body.get("proofNote") or body.get("note") or "").strip()
    version = body.get("version")
    return leave_svc.submit_cancel(leave_id, user, proof_note=note, expected_version=version, self_only=True)


def leave_extend(user: dict, leave_id: str, body: dict | None = None) -> dict:
    """本人对已通过/逾期请假发起续假（须晚于原结束时间；辅导员审批）。"""
    body = body or {}
    from app.services import affairs_leave_service as leave_svc
    new_end = body.get("newEndTime") or body.get("newEnd") or body.get("endTime") or ""
    reason = str(body.get("reason") or "").strip()
    version = body.get("version")
    return leave_svc.apply_extension(
        leave_id, user, new_end, reason=reason, expected_version=version, self_only=True)


def dorm(user: dict) -> dict:
    """本人宿舍只读卡（床位/楼栋/房间；选床入口仍走小程序）。"""
    return aff.dorm_my(user)


def talk(user: dict) -> dict:
    """本人谈心谈话摘要。"""
    return aff.talk_my(user)


def aid_objection(user: dict, body: dict) -> dict:
    """公示期本人对困难认定结果提异议（对齐奖助公示申诉）。"""
    body = body or {}
    apply_id = str(body.get("applyId") or body.get("applicationId") or "").strip()
    reason = str(body.get("reason") or "").strip()
    if not apply_id:
        raise AppException("VALIDATION_ERROR", "认定申请（applyId）必填")
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "异议理由至少 5 字")
    sid = _resolve_self_id(user)
    from app.models import AidApply
    from app.services.db_service import _tid, session as _session
    with _session() as db:
        x = db.get(AidApply, int(apply_id))
        if not x or x.is_deleted or x.tenant_id != _tid() or int(x.student_id or 0) != sid:
            raise AppException("DATA_NOT_FOUND", "认定申请不存在或不属于本人")
    from app.services import affairs_aid_service as aid_svc
    return aid_svc.submit_objection(apply_id, body, user, skip_scope_check=True)


def aid_batches_open(user: dict) -> dict:
    """当前开放中的困难认定批次（本人可申请）。"""
    _require_student(user)
    from app.services import affairs_aid_service as aid_svc
    items, total = aid_svc.list_batches(user, status="OPEN", page=1, page_size=50)
    return {"items": items, "total": total}


def aid_apply(user: dict, body: dict) -> dict:
    """困难认定申请（长表 + 家庭经济强敏感；studentId 强制本人；承诺书签署）。

    家庭隐私字段仅本人录入 + 审计，不对家长/他人开放（底层 AidFamilyEconomy 独立强敏感存储）。
    """
    body = body or {}
    if not str(body.get("batchId") or "").strip():
        raise AppException("VALIDATION_ERROR", "认定批次（batchId）必填")
    if not str(body.get("applyLevel") or "").strip():
        raise AppException("VALIDATION_ERROR", "申请等级（applyLevel）必填")
    if not bool(body.get("confirm")):
        raise AppException("VALIDATION_ERROR", "请先阅读并勾选确认承诺书")
    sid = _resolve_self_id(user)
    ns = SimpleNamespace(
        studentId=str(sid), batchId=str(body.get("batchId")),
        applyLevel=str(body.get("applyLevel")), statement=str(body.get("statement") or ""),
        memberCount=body.get("memberCount"), annualIncome=body.get("annualIncome"),
        debt=body.get("debt"), familyMembers=body.get("familyMembers") or [],
        specialTags=body.get("specialTags") or [])
    from app.services import affairs_aid_service as aid_svc
    result = aid_svc.apply(ns, user, skip_scope_check=True)
    common.sign(user, {"bizType": "DIFFICULTY_COMMIT",
                       "bizId": str(result.get("applyId") or ""),
                       "content": f"困难认定承诺 student={sid} batch={body.get('batchId')} "
                                  f"level={body.get('applyLevel')}",
                       "confirm": True})
    return result


# ── 活动二课与社团报名（复用 affairs_activity_service） ──

def activities(user: dict, page: int = 1, page_size: int = 20) -> dict:
    _require_student(user)
    from app.services import affairs_activity_service as act
    res = act.list_activities(user, page=page, page_size=page_size)
    if isinstance(res, tuple):
        items, total, _status_counts = res
        return {"items": items, "total": total}
    return res


def activities_my(user: dict) -> dict:
    _require_student(user)
    from app.services import affairs_activity_service as act
    return act.my_activities(user)


def activity_enroll(user: dict, activity_id) -> dict:
    _require_student(user)
    try:
        aid = int(activity_id)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "无效的活动ID")
    from app.services import affairs_activity_service as act
    return act.enroll(aid, user)
