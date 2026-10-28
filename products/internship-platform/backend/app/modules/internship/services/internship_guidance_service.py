"""岗位实习 · 指导记录（P1-Stage2）。指导教师对本人指导学生的过程指导留痕。
owner + 数据范围复用 internship_service 的 _current_scope / _rec_in_scope。审计 target_type=GUIDANCE。"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import ValidationError

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import has_permission
from app.core.tenant_scoped import tenant_get
from app.core.timeutil import local_now
from app.models import (InternshipAuditTrail, InternshipBatch, InternshipGuidance,
                        InternshipRecord, StudentProfile)
from app.services.db_service import _as_id, _iso, _tid, session

METHOD_LABEL = {"ONLINE": "微信或QQ（即时聊天）指导", "PHONE": "电话", "ONSITE": "现场",
                "ENTERPRISE_FEEDBACK": "企业导师反馈", "VIDEO": "视频"}


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, gid, action, detail=None, operator="系统"):
    from app.modules.internship.services.internship_audit_service import add_audit
    add_audit(db, target_id=gid, target_type='GUIDANCE', action=action, detail=detail or {})


def _get(db, gid) -> InternshipGuidance:
    g = db.get(InternshipGuidance, _as_id(gid))
    if not g or g.is_deleted or g.tenant_id != _tid():
        raise not_found("指导记录不存在")
    return g


def _ctx(db, g):
    rec = tenant_get(db, InternshipRecord, g.internship_id)
    stu = tenant_get(db, StudentProfile, g.student_id) if rec else None
    if not rec or rec.is_deleted or not stu or stu.is_deleted or rec.student_id != g.student_id:
        raise not_found('指导关联的实习记录或学生档案已失效')
    from app.modules.internship.services.internship_batch_context import resolve_batch
    resolve_batch(db, rec.batch_id)
    return rec, stu


def _row(g, rec, stu):
    return {
        "id": str(g.id), "internId": str(g.internship_id), "batchId": str(rec.batch_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": g.advisor_name or (rec.advisor_name if rec else ""),
        "enterpriseName": rec.enterprise_name if rec else "",
        "method": g.method, "methodLabel": METHOD_LABEL.get(g.method, '方式待确认'),
        "guidanceDate": g.guidance_date.isoformat() if g.guidance_date else '',
        "guidanceDateLabel": g.guidance_date.isoformat() if g.guidance_date else '未登记指导日期',
        "topic": g.topic or "", "content": g.content or "", "problemType": g.problem_type or "",
        "suggestion": g.suggestion or "", "nextFollowDate": g.next_follow_date or "",
        "toRisk": bool(g.to_risk), "notifyCounselor": bool(g.notify_counselor),
        "status": g.status, "version": int(g.version or 0), 'hasAttachment': bool(g.file_id),
        "createdAt": _iso(g.created_at) or "",
    }


def _scope_ctx(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def authorize_guidance_file(db, file_obj, bindings, user, action):
    """指导附件按当前原单授权；上传者身份不能绕过撤权或作废。"""
    if db is None or not has_permission(user, 'internship.guidance.view'):
        return False
    from app.modules.internship.services.internship_scope import assert_internship_record_scope
    for binding in bindings:
        if (binding.tenant_id != _tid() or binding.is_deleted or not binding.is_current
                or binding.status != 'ACTIVE' or binding.biz_type != 'INTERNSHIP_GUIDANCE'
                or str(binding.file_id) != str(file_obj.id) or not str(binding.biz_id or '').isascii()
                or not str(binding.biz_id or '').isdigit()):
            continue
        guide = tenant_get(db, InternshipGuidance, int(binding.biz_id))
        if not guide or guide.is_deleted or guide.status != 'NORMAL' or str(guide.file_id or '') != str(file_obj.id):
            continue
        rec, stu = _ctx(db, guide)
        if (binding.student_id != stu.id or str(binding.batch_id or '') != str(rec.batch_id)
                or str((binding.scope_json or {}).get('internshipId') or '') != str(rec.id)):
            continue
        assert_internship_record_scope(db, rec.id, user, '读取指导附件')
        return True
    return False


def _bind_file(db, guide, rec, stu, user):
    if not guide.file_id:
        return
    from app.services.file_business_binding_service import bind_file_to_business
    bind_file_to_business(db, file_id=guide.file_id, biz_type='INTERNSHIP_GUIDANCE', biz_id=str(guide.id),
        actor=user, subject_type='STUDENT', subject_id=str(stu.id), module_code='INTERNSHIP',
        student_id=stu.id, batch_id=str(rec.batch_id), college_id=stu.college_id, class_id=stu.class_id,
        scope={'internshipId': str(rec.id), 'studentId': str(stu.id), 'studentNo': stu.student_no,
               'batchId': str(rec.batch_id), 'advisorUserId': str(rec.advisor_user_id or ''),
               'businessType': 'INTERNSHIP_GUIDANCE', 'businessId': str(guide.id)},
        legacy_target_values={str(guide.id), str(rec.id), str(stu.id), stu.student_no})


def _spawn_risk(db, rec, stu, g, user):
    """指导「转风险」联动：to_risk=True 时在 t_risk_record 生成一条待处理风险单并写审计。
    返回新建 risk_id 或 None。风险处置闭环见 internship_risk_service。"""
    from app.models import RiskRecord
    risk = RiskRecord(
        tenant_id=_tid(), internship_id=rec.id,
        risk_code="INT-GUIDE", risk_title=f"指导发现问题：{g.topic or g.problem_type or '需跟进'}",
        risk_level="MEDIUM", source_module="guidance",
        owner_name=_op_name(user), status="PENDING_HANDLE",
        last_follow_note=(g.suggestion or g.content or "")[:500])
    db.add(risk); db.flush()
    notified = False
    if g.notify_counselor:
        from app.modules.internship.services.internship_service import notify_counselor_for_student
        notified = notify_counselor_for_student(
            db, stu, title=f"实习风险提醒：{stu.real_name if stu else '学生'}",
            content=f"指导教师 {_op_name(user)} 在指导中发现问题「{g.topic or g.problem_type or '需跟进'}」，"
                    f"已形成风险单待处置。建议：{(g.suggestion or g.content or '')[:200]}",
            source_biz_id=risk.id, message_type="INTERNSHIP_RISK")
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=risk.id, target_type="RISK", action="CREATE_FROM_GUIDANCE",
        operator_name=_op_name(user),
        detail_json={"guidanceId": str(g.id), "studentName": stu.real_name if stu else "",
                     "notifyCounselor": bool(g.notify_counselor), "counselorNotified": notified},
        occurred_at=datetime.utcnow()))
    return risk.id


def create(user, body) -> dict:
    from app.modules.internship.schemas.internship_guidance import GuidanceCreate
    from app.modules.internship.services.internship_batch_context import assert_record_batch, resolve_batch
    from app.modules.internship.services.internship_identity import stable_user_id
    from app.modules.internship.services.internship_scope import assert_internship_record_scope
    try:
        b = GuidanceCreate.model_validate(body).model_dump()
    except ValidationError as error:
        raise AppException('VALIDATION_ERROR', '请核对指导日期、方式、正文及学生信息') from error
    actor_id = stable_user_id(user)
    if not actor_id or not has_permission(user, 'internship.guidance.manage'):
        raise no_permission('当前账号不能登记指导记录')
    with session() as db:
        rec = assert_internship_record_scope(db, b['internshipId'], user, '登记指导', lock=True)
        assert_record_batch(rec, b['batchId'])
        resolve_batch(db, rec.batch_id, for_write=True)
        stu = tenant_get(db, StudentProfile, rec.student_id)
        fields = dict(guidance_date=date.fromisoformat(b['guidanceDate']), method=b['method'],
            topic=b['topic'], content=b['content'], problem_type=b['problemType'], suggestion=b['suggestion'],
            next_follow_date=b['nextFollowDate'], to_risk=b['toRisk'], notify_counselor=b['notifyCounselor'],
            file_id=b['fileId'])
        existing = db.scalar(select(InternshipGuidance).where(
            InternshipGuidance.tenant_id == _tid(), InternshipGuidance.internship_id == rec.id,
            InternshipGuidance.request_key == b['requestKey']))
        if existing:
            if (existing.created_by != actor_id or existing.is_deleted or existing.status != 'NORMAL'
                    or any(getattr(existing, name) != value for name, value in fields.items())):
                raise AppException('DATA_CONFLICT', '该提交已办理或内容已改变，请核对原记录再提交', http_status=409)
            return _receipt(db, existing, rec, stu, replayed=True)
        g = InternshipGuidance(
            tenant_id=_tid(), internship_id=rec.id, student_id=rec.student_id,
            advisor_name=_op_name(user), created_by=actor_id, request_key=b['requestKey'], status='NORMAL', **fields)
        db.add(g); db.flush()
        _bind_file(db, g, rec, stu, user)
        _trail(db, g.id, "CREATE", {"method": g.method, "topic": g.topic or "",
                                    "guidanceDate": b['guidanceDate'], 'internshipId': str(rec.id),
                                    'batchId': str(rec.batch_id), "hasFile": bool(g.file_id)}, operator=_op_name(user))
        risk_id = _spawn_risk(db, rec, stu, g, user) if g.to_risk else None
        if risk_id:
            _trail(db, g.id, "SPAWN_RISK", {"riskId": str(risk_id)}, operator=_op_name(user))
        elif g.notify_counselor:  # 仅通知辅导员、未形成风险
            from app.modules.internship.services.internship_service import notify_counselor_for_student
            if notify_counselor_for_student(
                    db, stu, title=f"实习指导提醒：{stu.real_name if stu else '学生'}",
                    content=f"指导教师 {_op_name(user)} 反馈：{(g.content or '')[:200]}",
                    source_biz_id=g.id, message_type="INTERNSHIP_GUIDANCE"):
                _trail(db, g.id, "NOTIFY_COUNSELOR", {}, operator=_op_name(user))
        db.commit()
        return _receipt(db, g, rec, stu)


def _receipt(db, guide, rec, stu, *, replayed=False):
    risk = db.scalar(select(InternshipAuditTrail).where(InternshipAuditTrail.tenant_id == _tid(),
        InternshipAuditTrail.target_type == 'GUIDANCE', InternshipAuditTrail.target_id == guide.id,
        InternshipAuditTrail.action == 'SPAWN_RISK'))
    detail = (risk.detail_json or {}) if risk else {}
    detail = detail.get('detailJson', detail)
    return {'id': str(guide.id), 'internshipId': str(rec.id), 'batchId': str(rec.batch_id),
            'studentName': stu.real_name, 'studentNo': stu.student_no, 'guidanceDate': guide.guidance_date.isoformat(),
            'riskId': detail.get('riskId'), 'replayed': replayed}


def create_batch(user, body):
    from app.modules.internship.schemas.internship_guidance import GuidanceBatch
    try:
        batch = GuidanceBatch.model_validate(body)
    except ValidationError as error:
        raise AppException('VALIDATION_ERROR', '请核对批量学生、指导日期、正文及附件') from error
    common = batch.model_dump(exclude={'items'})
    results = []
    for item in batch.items:
        try:
            saved = create(user, {**common, **item.model_dump()})
            results.append({**saved, 'requestKey': item.requestKey, 'success': True, 'message': '已保存'})
        except AppException as error:
            results.append({'internshipId': item.internshipId, 'requestKey': item.requestKey, 'success': False,
                            'code': error.code, 'message': error.message, 'saveUnconfirmed': error.http_status >= 500})
        except SQLAlchemyError:
            results.append({'internshipId': item.internshipId, 'requestKey': item.requestKey,
                            'success': False, 'code': 'SAVE_FAILED', 'saveUnconfirmed': True,
                            'message': '本条保存未确认，请保留原输入重试；已成功的其他学生不受影响'})
    succeeded = sum(item['success'] for item in results)
    return {'batchId': str(batch.batchId), 'items': results, 'successCount': succeeded,
            'failedCount': len(results) - succeeded}


def void_guidance(user, gid, reason="", *, expected_version=None, batch_id=None) -> dict:
    from app.modules.internship.services.internship_version import (
        extract_expected_version, versioned_update,
    )
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        g = _get(db, gid)
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        from app.modules.internship.services.internship_batch_context import assert_record_batch
        assert_internship_record_scope(db, g.internship_id, user, '撤销指导', lock=True)
        g = db.scalar(select(InternshipGuidance).where(InternshipGuidance.id == g.id,
            InternshipGuidance.tenant_id == _tid()).with_for_update().execution_options(populate_existing=True))
        rec, stu = _ctx(db, g)
        assert_record_batch(rec, batch_id)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("只能撤销本人指导学生的指导记录")
        current_version = int(g.version or 0)
        client_version = extract_expected_version(
            {"expectedVersion": expected_version}, required=True)
        if client_version is not None and client_version != current_version:
            raise AppException("DATA_CONFLICT", "指导记录已被其他人更新，请刷新后重试")
        new_ver = versioned_update(
            db, InternshipGuidance, entity_id=g.id, tenant_id=_tid(),
            expected_version=current_version, expected_status=g.status,
            values={"is_deleted": True, "status": "VOIDED"})
        _trail(db, g.id, "VOID", {"reason": reason}, operator=_op_name(user))
        from app.models.file import FileBinding
        for binding in db.scalars(select(FileBinding).where(FileBinding.tenant_id == _tid(),
            FileBinding.biz_type == 'INTERNSHIP_GUIDANCE', FileBinding.biz_id == str(g.id),
            FileBinding.status == 'ACTIVE', FileBinding.is_current.is_(True))).all():
            binding.status = 'REVOKED'; binding.is_current = False
        db.commit()
        return {"id": str(g.id), "status": "VOIDED", "version": new_ver}


def list_guidances(page, page_size, keyword=None, batch_id=None, user=None) -> tuple[list[dict], int]:
    from app.modules.internship.services.internship_scope import apply_internship_record_scope
    from app.modules.internship.services.internship_batch_context import resolve_batch
    with session() as db:
        batch = resolve_batch(db, batch_id)
        query = select(InternshipGuidance, InternshipRecord, StudentProfile).join(InternshipRecord, and_(
            InternshipRecord.id == InternshipGuidance.internship_id, InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False), InternshipRecord.student_id == InternshipGuidance.student_id,
        )).join(StudentProfile, and_(StudentProfile.id == InternshipGuidance.student_id,
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))).where(
            InternshipGuidance.tenant_id == _tid(), InternshipGuidance.is_deleted.is_(False),
            InternshipGuidance.status == 'NORMAL', InternshipRecord.batch_id == batch.id)
        query = apply_internship_record_scope(query, user)
        if keyword and keyword.strip():
            query = query.where(or_(StudentProfile.real_name.contains(keyword.strip(), autoescape=True),
                StudentProfile.student_no.contains(keyword.strip(), autoescape=True),
                InternshipGuidance.topic.contains(keyword.strip(), autoescape=True),
                InternshipRecord.enterprise_name.contains(keyword.strip(), autoescape=True)))
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.execute(query.order_by(InternshipGuidance.id.desc())
            .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        return [_row(g, rec, stu) for g, rec, stu in rows], total


def _guidance_limits(batch) -> tuple[int, int]:
    rules = (batch.rules_config or {}).get("guidance", {}) if batch else {}
    # Earlier batch rules used a boolean enable flag, with default quantities.
    if not isinstance(rules, dict):
        rules = {}
    try:
        month = max(0, int(rules.get("minCommunicationsPerMonth", 2)))
    except (TypeError, ValueError):
        month = 2
    try:
        term = max(0, int(rules.get("minVisitsPerTerm", 2)))
    except (TypeError, ValueError):
        term = 2
    return month, term


def list_guidance_plans(page, page_size, keyword=None, plan_status=None,
                        insufficient_only=False, batch_id=None, user=None) -> tuple[list[dict], int]:
    """按学生实习记录与批次规则实时聚合指导达成情况，避免维护平行计划表。"""
    from app.modules.internship.services.internship_scope import apply_internship_record_scope
    from app.modules.internship.services.internship_batch_context import resolve_batch
    current = local_now().date(); month_start = current.replace(day=1)
    next_month = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
    with session() as db:
        batch = resolve_batch(db, batch_id)
        min_month, min_term = _guidance_limits(batch)
        counts = select(InternshipGuidance.internship_id.label('record_id'),
            func.count().label('term_count'),
            func.sum(case((and_(InternshipGuidance.guidance_date >= month_start,
                InternshipGuidance.guidance_date < next_month), 1), else_=0)).label('month_count'),
            func.sum(case((InternshipGuidance.guidance_date.is_(None), 1), else_=0)).label('unknown_dates'),
            func.max(InternshipGuidance.id).label('latest_id')).join(InternshipRecord, and_(
                InternshipRecord.id == InternshipGuidance.internship_id, InternshipRecord.tenant_id == _tid(),
                InternshipRecord.is_deleted.is_(False))).where(
            InternshipGuidance.tenant_id == _tid(), InternshipGuidance.is_deleted.is_(False),
            InternshipGuidance.status == 'NORMAL', InternshipRecord.batch_id == batch.id)
        counts = apply_internship_record_scope(counts, user).group_by(InternshipGuidance.internship_id).subquery()
        month_count = func.coalesce(counts.c.month_count, 0)
        term_count = func.coalesce(counts.c.term_count, 0)
        status = case((and_(month_count < min_month, term_count < min_term), 'INSUFFICIENT_BOTH'),
            (month_count < min_month, 'INSUFFICIENT_MONTH'), (term_count < min_term, 'INSUFFICIENT_TERM'), else_='OK')
        query = select(InternshipRecord, StudentProfile, month_count, term_count,
            func.coalesce(counts.c.unknown_dates, 0), InternshipGuidance.next_follow_date, status).join(StudentProfile,
            and_(StudentProfile.id == InternshipRecord.student_id, StudentProfile.tenant_id == _tid(),
                StudentProfile.is_deleted.is_(False))).outerjoin(counts, counts.c.record_id == InternshipRecord.id)
        query = query.outerjoin(InternshipGuidance, InternshipGuidance.id == counts.c.latest_id).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False),
            InternshipRecord.batch_id == batch.id, InternshipRecord.status.in_(('PREPARING', 'READY', 'ONBOARD', 'ASSESSING')))
        query = apply_internship_record_scope(query, user)
        if keyword and keyword.strip():
            query = query.where(or_(StudentProfile.real_name.contains(keyword.strip(), autoescape=True),
                                    StudentProfile.student_no.contains(keyword.strip(), autoescape=True)))
        if insufficient_only:
            query = query.where(status != 'OK')
        if plan_status:
            query = query.where(status == plan_status)
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.execute(query.order_by(InternshipRecord.id)
            .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        items = []
        for rec, stu, month_count, term_count, unknown_dates, next_follow, status in rows:
            items.append({
                "internId": str(rec.id), "studentNo": stu.student_no if stu else "-",
                "studentName": stu.real_name if stu else "-", "advisorName": rec.advisor_name or "",
                "enterpriseName": rec.enterprise_name or "", "batchId": str(rec.batch_id or ""),
                "batchName": batch.batch_name if batch else "", "minMonth": min_month,
                "monthCount": month_count, "minTerm": min_term, "termCount": term_count,
                "unknownDateCount": unknown_dates,
                "nextFollowDate": next_follow or '', "planStatus": status,
                "planStatusLabel": {"OK": "达标", "INSUFFICIENT_MONTH": "本月不足",
                                    "INSUFFICIENT_TERM": "学期不足",
                                    "INSUFFICIENT_BOTH": "月/学期均不足"}[status],
            })
        return items, total


def guidance_stats(threshold=2, batch_id=None, user=None) -> dict:
    try:
        threshold = max(0, int(threshold))
    except (TypeError, ValueError):
        threshold = 2
    from app.modules.internship.services.internship_export_util import load_export_rows
    items, _ = load_export_rows(
        list_guidance_plans, batch_id=batch_id, user=user)
    total_count = sum(int(item["termCount"]) for item in items)
    return {"studentCount": len(items), "totalCount": total_count,
            "avgCount": round(total_count / len(items), 1) if items else 0,
            "threshold": threshold,
            "insufficientCount": sum(1 for item in items if int(item["termCount"]) < threshold)}


def export_guidance_plans(keyword=None, batch_id=None, user=None) -> dict:
    from app.services import xlsx_util
    from app.modules.internship.services.internship_export_util import load_export_rows
    items, _ = load_export_rows(
        list_guidance_plans, keyword=keyword, batch_id=batch_id, user=user)
    headers = ["学号", "姓名", "指导教师", "企业", "批次", "月最低", "本月次数",
               "学期最低", "学期次数", "历史未登记日期次数", "下次跟进", "计划状态"]
    rows = [[it["studentNo"], it["studentName"], it["advisorName"], it["enterpriseName"],
             it["batchName"], it["minMonth"], it["monthCount"], it["minTerm"], it["termCount"],
             it['unknownDateCount'], it["nextFollowDate"], it["planStatusLabel"]] for it in items]
    wm = f"岗位实习中心·指导计划台账 · 导出人：{_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("指导计划台账", headers, rows, watermark=wm)
    from app.services.db_service import audit_insert_in_session
    from app.modules.internship.services.internship_batch_context import resolve_batch
    with session() as db:
        batch = resolve_batch(db, batch_id)
        audit_insert_in_session(db, '导出指导计划台账', 'internship-guidance-plans:export',
            {'batchId': str(batch.id), 'keyword': keyword or '', 'rowCount': len(items)}, 'SUCCESS', actor_override=user)
        db.commit()
    return xlsx_util.pack_xlsx_result(content, "指导计划台账.xlsx", len(items))


def get_guidance(gid, user=None) -> dict:
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        g = _get(db, gid)
        rec, stu = _ctx(db, g)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("该指导记录不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "GUIDANCE",
            InternshipAuditTrail.target_id == g.id).order_by(InternshipAuditTrail.id)).all()
        from app.services.internship_file_transfer_service import authorized_file
        attachment, attachment_error = None, ''
        if g.file_id:
            try:
                attachment = authorized_file(g.file_id, user, 'meta')[1]
            except AppException as error:
                if error.http_status != 404:
                    raise
                attachment_error = '指导材料当前不可读取，请联系学校核对绑定及权限'
        return {**_row(g, rec, stu), "attachment": attachment, 'attachmentError': attachment_error,
                "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                                "occurredAt": _iso(t.occurred_at)} for t in trail]}


def export_guidances(keyword=None, batch_id=None, user=None) -> dict:
    from app.services import xlsx_util
    from app.modules.internship.services.internship_export_util import load_export_rows
    items, _ = load_export_rows(
        list_guidances, keyword=keyword, batch_id=batch_id, user=user)
    headers = ["指导编号", "实习编号", "学号", "姓名", "指导教师", "企业", "指导日期", "指导方式", "主题", "指导正文",
               "问题类型", "处理建议", "下次跟进", "是否形成风险", "是否通知辅导员", "是否登记附件"]
    rows = [[it['id'], it['internId'], it["studentNo"], it["studentName"], it["advisorName"], it["enterpriseName"],
             it['guidanceDateLabel'], it["methodLabel"], it["topic"], it['content'], it["problemType"],
             it["suggestion"], it["nextFollowDate"], "是" if it["toRisk"] else "否",
             "是" if it['notifyCounselor'] else "否", "是" if it['hasAttachment'] else "否"] for it in items]
    wm = f"岗位实习中心·指导记录台账 · 导出人：{_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("指导记录台账", headers, rows, watermark=wm)
    from app.services.db_service import audit_insert_in_session
    from app.modules.internship.services.internship_batch_context import resolve_batch
    with session() as db:
        batch = resolve_batch(db, batch_id)
        audit_insert_in_session(db, '导出指导记录台账', 'internship-guidance:export',
            {'batchId': str(batch.id), 'keyword': keyword or '', 'rowCount': len(items)}, 'SUCCESS', actor_override=user)
        db.commit()
    return xlsx_util.pack_xlsx_result(content, "指导记录台账.xlsx", len(items))
