"""岗位实习 · 教师巡访（P1-Stage2）。含企业/学生反馈、安全隐患与整改跟进。
owner + 数据范围复用 internship_service。审计 target_type=VISIT。"""
from __future__ import annotations

from datetime import datetime
import json

from pydantic import ValidationError

from sqlalchemy import and_, func, or_, select

from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import has_permission
from app.core.tenant_scoped import tenant_get
from app.models import (InternshipAuditTrail, InternshipRecord, InternshipVisit, StudentProfile)
from app.services.db_service import _as_id, _iso, _tid, session

METHOD_LABEL = {"ONSITE": "现场", "ONLINE": "线上", "PHONE": "电话", "VIDEO": "视频", "OTHER": "其他"}
RECTIFY_LABEL = {"NONE": "无需整改", "PENDING": "整改中", "DONE": "已整改"}


def normalize_visit_title(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise AppException('VALIDATION_ERROR', '巡访标题须为文字')
    title = value.strip()
    if not 2 <= len(title) <= 200:
        raise AppException('VALIDATION_ERROR', '巡访标题须为2至200字')
    return title


def encrypt_visit_location(value):
    if value is None:
        return None
    from app.core.field_crypto import encrypt_field
    from app.modules.internship.schemas.internship_visit import VisitLocation
    try:
        capture = VisitLocation.model_validate(value).model_dump(mode='json')
    except ValidationError as exc:
        raise AppException('VALIDATION_ERROR', '巡访位置须为主动采集的合法经纬度、精度、坐标系与时间') from exc
    return encrypt_field(json.dumps(capture, ensure_ascii=False))


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, vid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=vid, target_type="VISIT",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _get(db, vid) -> InternshipVisit:
    v = db.get(InternshipVisit, _as_id(vid))
    if not v or v.is_deleted or v.tenant_id != _tid():
        raise not_found("巡访记录不存在")
    return v


def _ctx(db, v):
    rec = tenant_get(db, InternshipRecord, v.internship_id)
    stu = tenant_get(db, StudentProfile, v.student_id) if rec else None
    if (not rec or rec.is_deleted or not stu or stu.is_deleted or rec.student_id != v.student_id):
        raise not_found("巡访关联的实习记录或学生档案已失效")
    from app.modules.internship.services.internship_batch_context import resolve_batch
    resolve_batch(db, rec.batch_id)
    return rec, stu


def authorize_visit_file(db, file_obj, bindings, user, action):
    """正式巡访照片只按当前巡访、查看权限和师生关系授权，上传者不兜底。"""
    if (db is None or str(user.get('userType') or '').upper() == 'STUDENT'
            or not has_permission(user, 'internship.visit.view')):
        return False
    from app.modules.internship.services.internship_scope import assert_internship_record_scope
    for binding in bindings:
        if (binding.tenant_id != _tid() or binding.is_deleted or binding.status != 'ACTIVE'
                or not binding.is_current or binding.biz_type != 'INTERNSHIP_VISIT'
                or str(binding.file_id) != str(file_obj.id)
                or not str(binding.biz_id or '').isascii() or not str(binding.biz_id or '').isdigit()):
            continue
        visit = tenant_get(db, InternshipVisit, int(binding.biz_id))
        if not visit or visit.is_deleted or str(visit.file_id or '') != str(file_obj.id):
            continue
        rec, stu = _ctx(db, visit)
        if (binding.student_id != stu.id or str(binding.batch_id or '') != str(rec.batch_id)
                or str((binding.scope_json or {}).get('internshipId') or '') != str(rec.id)):
            continue
        assert_internship_record_scope(db, rec.id, user, '访问巡访照片')
        return True
    return False


def bind_visit_file(db, visit, rec, stu, user):
    if not visit.file_id:
        return
    from app.services.file_business_binding_service import bind_file_to_business
    bind_file_to_business(db, file_id=visit.file_id, biz_type='INTERNSHIP_VISIT', biz_id=str(visit.id),
        actor=user, subject_type='STUDENT', subject_id=str(stu.id), module_code='INTERNSHIP',
        student_id=stu.id, batch_id=str(rec.batch_id), college_id=stu.college_id, class_id=stu.class_id,
        scope={'internshipId': str(rec.id), 'studentId': str(stu.id), 'studentNo': stu.student_no,
               'batchId': str(rec.batch_id), 'advisorUserId': str(rec.advisor_user_id or ''),
               'businessType': 'INTERNSHIP_VISIT', 'businessId': str(visit.id)},
        legacy_target_values={str(visit.id), str(rec.id), str(stu.id), stu.student_no})


def _row(v, rec, stu):
    return {
        "id": str(v.id), "internId": str(v.internship_id), "batchId": str(rec.batch_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": v.advisor_name or "", "enterpriseName": v.enterprise_name or (rec.enterprise_name if rec else ""),
        "title": v.visit_title or '', "hasLocation": bool(v.location_encrypted),
        "locationStatusLabel": '已登记位置，按权限留痕查看' if v.location_encrypted else '未登记位置',
        "visitAt": _iso(v.visit_at) or "", "method": v.method, "methodLabel": METHOD_LABEL.get(v.method, v.method),
        "enterpriseFeedback": v.enterprise_feedback or "", "studentFeedback": v.student_feedback or "",
        "safetyIssue": v.safety_issue or "", "rectifyRequire": v.rectify_require or "",
        "rectifyDeadline": v.rectify_deadline or "",
        "rectifyStatus": v.rectify_status, "rectifyStatusLabel": RECTIFY_LABEL.get(v.rectify_status, v.rectify_status),
        "version": int(v.version or 0), "createdAt": _iso(v.created_at) or "",
    }


def _scope_ctx(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _validate_file(file_id):
    """附件 file_id 校验：为空放行；非空必须是本租户已存在文件，否则拒绝。"""
    fid = (file_id or "").strip()
    if not fid:
        return None
    from app.services import file_service
    if not file_service.get_file_meta(fid):
        raise AppException("VALIDATION_ERROR", "附件不存在或无权访问，请重新上传")
    return fid


def create(user, body) -> dict:
    b = body or {}
    title = normalize_visit_title(b.get('title'))
    encrypted_location = encrypt_visit_location(b.get('location'))
    iid = b.get("internshipId") or b.get("internId")
    if not iid:
        raise AppException("VALIDATION_ERROR", "缺少实习记录 internshipId")
    file_id = _validate_file(b.get("fileId"))
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        rec = db.get(InternshipRecord, _as_id(iid))
        if not rec or rec.is_deleted or rec.tenant_id != _tid():
            raise not_found("实习记录不存在")
        from app.modules.internship.services.internship_batch_context import resolve_batch
        resolve_batch(db, rec.batch_id, for_write=True)
        stu = tenant_get(db, StudentProfile, rec.student_id)
        if not stu or stu.is_deleted:
            raise not_found('实习关联的学生档案已失效')
        if not in_scope(scope, db, rec, stu):  # owner
            raise no_permission("只能对本人指导学生新增巡访记录")
        has_rectify = bool((b.get("safetyIssue") or "").strip() or (b.get("rectifyRequire") or "").strip())
        v = InternshipVisit(
            tenant_id=_tid(), internship_id=rec.id, student_id=rec.student_id,
            advisor_name=_op_name(user), enterprise_name=b.get("enterpriseName") or (rec.enterprise_name or None),
            visit_title=title, location_encrypted=encrypted_location,
            visit_at=datetime.utcnow(), method=b.get("method") or "ONSITE",
            enterprise_feedback=b.get("enterpriseFeedback"), student_feedback=b.get("studentFeedback"),
            safety_issue=b.get("safetyIssue"), rectify_require=b.get("rectifyRequire"),
            rectify_deadline=b.get("rectifyDeadline"),
            rectify_status="PENDING" if has_rectify else "NONE",
            monthly_report=b.get("monthlyReport"), file_id=file_id)
        db.add(v); db.flush()
        bind_visit_file(db, v, rec, stu, user)
        _trail(db, v.id, "CREATE", {"method": v.method, "hasRectify": has_rectify},
               operator=_op_name(user))
        if has_rectify:
            from app.modules.internship.services import internship_todo_helper as ix_todo
            ix_todo.push_visit_rectify_todo(db, v, rec)
        db.commit()
        return {"id": str(v.id), "rectifyStatus": v.rectify_status}


def rectify_follow(user, visit_id, status, note="", *, expected_version=None, batch_id=None) -> dict:
    if status not in ("PENDING", "DONE"):
        raise AppException("VALIDATION_ERROR", "整改状态必须是 PENDING/DONE")
    if not (note or "").strip() or len(note.strip()) < 2:
        raise AppException("VALIDATION_ERROR", "整改跟进说明必填")
    from app.modules.internship.services.internship_version import (
        extract_expected_version, versioned_update,
    )
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        v = _get(db, visit_id)
        rec, stu = _ctx(db, v)
        from app.modules.internship.services.internship_batch_context import assert_record_batch, parse_required_batch_id
        assert_record_batch(rec, parse_required_batch_id(batch_id))
        if not in_scope(scope, db, rec, stu):  # owner 级写校验
            raise no_permission("只能跟进本人指导学生的巡访整改")
        if v.rectify_status == "NONE":
            raise AppException("DATA_CONFLICT", "该巡访无整改要求，无需跟进")
        current_version = int(v.version or 0)
        current_status = v.rectify_status
        client_version = extract_expected_version(
            {"expectedVersion": expected_version}, required=True)
        if client_version != current_version:
            raise AppException("DATA_CONFLICT", "巡访记录已被其他人更新，请刷新后重试", http_status=409)
        new_ver = versioned_update(
            db, InternshipVisit, entity_id=v.id, tenant_id=_tid(),
            expected_version=current_version, values={"rectify_status": status},
            extra_where=(InternshipVisit.rectify_status == current_status,))
        _trail(db, v.id, f"RECTIFY_{status}", {"note": note.strip()}, operator=_op_name(user))
        if status == "DONE":
            from app.modules.internship.services import internship_todo_helper as ix_todo
            ix_todo.todo_done(db, biz_id=v.id, todo_type=ix_todo.TODO_VISIT_RECTIFY)
        elif status == "PENDING":
            from app.modules.internship.services import internship_todo_helper as ix_todo
            ix_todo.push_visit_rectify_todo(db, v, rec)
        db.commit()
        return {"id": str(v.id), "rectifyStatus": status,
                "rectifyStatusLabel": RECTIFY_LABEL.get(status, status), "version": new_ver}


def list_visits(page, page_size, keyword=None, rectify=None, batch_id=None, user=None) -> tuple[list[dict], int]:
    from app.modules.internship.services.internship_scope import apply_internship_record_scope
    from app.modules.internship.services.internship_batch_context import resolve_batch
    with session() as db:
        batch = resolve_batch(db, batch_id)
        q = select(InternshipVisit, InternshipRecord, StudentProfile).join(InternshipRecord, and_(
            InternshipRecord.id == InternshipVisit.internship_id, InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False), InternshipRecord.student_id == InternshipVisit.student_id,
        )).join(StudentProfile, and_(StudentProfile.id == InternshipVisit.student_id,
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
        )).where(InternshipVisit.tenant_id == _tid(), InternshipVisit.is_deleted.is_(False),
                 InternshipRecord.batch_id == batch.id)
        q = apply_internship_record_scope(q, user)
        if rectify:
            q = q.where(InternshipVisit.rectify_status == rectify)
        if keyword and keyword.strip():
            q = q.where(or_(StudentProfile.real_name.contains(keyword.strip(), autoescape=True),
                            StudentProfile.student_no.contains(keyword.strip(), autoescape=True),
                            InternshipVisit.visit_title.contains(keyword.strip(), autoescape=True),
                            InternshipVisit.enterprise_name.contains(keyword.strip(), autoescape=True)))
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.execute(q.order_by(InternshipVisit.id.desc())
            .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        return [_row(v, rec, stu) for v, rec, stu in rows], total


def get_visit(vid, user=None) -> dict:
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        v = _get(db, vid)
        rec, stu = _ctx(db, v)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("该巡访记录不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "VISIT",
            InternshipAuditTrail.target_id == v.id).order_by(InternshipAuditTrail.id)).all()
        from app.services.internship_file_transfer_service import authorized_file
        attachment, attachment_error = None, ''
        if v.file_id:
            try:
                attachment = authorized_file(v.file_id, user, 'meta')[1]
            except AppException as error:
                if error.http_status != 404:
                    raise
                attachment_error = '巡访材料当前不可读取，请联系学校核对材料绑定及权限'
        return {**_row(v, rec, stu), "monthlyReport": v.monthly_report or "",
                "canViewLocation": has_permission(user, 'internship.visit.location.view'),
                "attachment": attachment, "attachmentError": attachment_error,
                "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                                "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                               for t in trail]}


def disclose_visit_location(vid, user, body):
    from app.core.field_crypto import decrypt_field
    from app.modules.internship.services.internship_batch_context import assert_record_batch
    if (str(user.get('userType') or '').upper() == 'STUDENT'
            or not has_permission(user, 'internship.visit.view')
            or not has_permission(user, 'internship.visit.location.view')):
        raise no_permission('无权查看巡访位置')
    reason = str(body.get('reason') or '').strip()
    if not 5 <= len(reason) <= 200:
        raise AppException('VALIDATION_ERROR', '查看位置须说明5至200字业务用途')
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        v = _get(db, vid)
        rec, stu = _ctx(db, v)
        if not in_scope(scope, db, rec, stu):
            raise no_permission('该巡访记录不在你的数据范围内')
        assert_record_batch(rec, body['batchId'])
        if int(v.version or 0) != body['expectedVersion']:
            raise AppException('DATA_CONFLICT', '巡访记录已变化，请重读后查看位置', http_status=409)
        if not v.location_encrypted:
            raise not_found('此巡访未登记位置')
        location = json.loads(decrypt_field(v.location_encrypted, allow_legacy_plaintext=False))
        _trail(db, v.id, 'DISCLOSE_LOCATION', {'reason': reason,
            'actorUserId': str(user.get('userId') or ''),
            'actorRole': user.get('currentRoleCode') or user.get('userType') or '',
            'batchId': str(rec.batch_id), 'internshipId': str(rec.id),
            'expectedVersion': body['expectedVersion']}, operator=_op_name(user))
        db.commit()  # 必需留痕提交后才返回明文；审计失败不得披露位置。
        return {'visitId': str(v.id), 'batchId': str(rec.batch_id), 'location': location}


def visit_stats(batch_id=None, user=None) -> dict:
    from app.modules.internship.services.internship_export_util import load_export_rows
    items, _ = load_export_rows(list_visits, batch_id=batch_id, user=user)
    return {"totalVisits": len(items),
            "pendingRectify": sum(1 for item in items if item["rectifyStatus"] == "PENDING"),
            "doneRectify": sum(1 for item in items if item["rectifyStatus"] == "DONE"),
            "withSafetyIssue": sum(1 for item in items if item["safetyIssue"])}


def export_visits(keyword=None, batch_id=None, user=None) -> dict:
    from app.services import xlsx_util
    from app.modules.internship.services.internship_export_util import load_export_rows
    items, _ = load_export_rows(
        list_visits, keyword=keyword, batch_id=batch_id, user=user)
    headers = ["学号", "姓名", "巡访教师", "企业", "巡访标题", "位置登记", "巡访时间", "方式", "安全隐患", "整改要求",
               "整改截止", "整改状态"]
    rows = [[it["studentNo"], it["studentName"], it["advisorName"], it["enterpriseName"],
             it['title'], '已登记' if it['hasLocation'] else '未登记', it["visitAt"], it["methodLabel"], it["safetyIssue"], it["rectifyRequire"],
             it["rectifyDeadline"], it["rectifyStatusLabel"]] for it in items]
    wm = f"岗位实习中心·巡访记录台账 · 导出人：{_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("巡访记录台账", headers, rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "巡访记录台账.xlsx", len(items))
