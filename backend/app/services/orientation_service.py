"""数字迎新域真实数据服务。租户过滤 + is_deleted + 脱敏 + 审计留痕。"""
from __future__ import annotations

from datetime import datetime
import re
import json

from sqlalchemy import and_, case, false, func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.core.tenant_scoped import tenant_get
from app.models import (GreenChannelApplication, OrientationArchive, OrientationAuditTrail,
                        OrientationBatch, OrientationCheckinPoint, OrientationException,
                        OrientationExceptionFollowup, OrientationFlowConfig, OrientationMaterial,
                        OrientationNoticeTask, OrientationPaymentAccount, OrientationStudent,
                        StudentProfile, User)
from app.core.field_crypto import mask_id_card_encrypted, mask_phone_encrypted
from app.services.db_service import _iso, _tid, session
from app.services.orientation_flow_service import (ensure_published_flow_version,
                                                    ensure_student_steps,
                                                    initialize_batch_student_steps,
                                                    set_student_step_status,
                                                    student_flow_steps,
                                                    student_step_projection)

L_STAGE = {"ADMITTED": "已录取", "PRE_STUDENT_VERIFIED": "预报到已核验",
           "REGISTERED_PENDING_ENROLLMENT": "已报到待注册", "ENROLLED": "已入学",
           "DEFERRED": "延迟报到", "NO_SHOW": "未到校", "CANCELLED": "取消入学"}
L_REPORT = {"NOT_REPORTED": "未报到", "PREPARED": "预报到完成", "CHECKED_IN": "已现场报到",
            "COLLEGE_CONFIRMED": "学院已确认", "DELAYED": "延迟报到", "NO_SHOW": "未到校",
            "ABNORMAL": "报到异常"}
L_PAY = {"PAID": "已缴清", "PARTIAL": "部分缴费", "UNPAID": "未缴费", "DEFERRED": "已批准缓缴",
         "GREEN_CHANNEL": "绿色通道"}
L_GC = {"NOT_APPLIED": "未申请", "SUBMITTED": "已提交", "REVIEWING": "审核中", "APPROVED": "已通过",
        "RETURNED": "已退回", "REJECTED": "已驳回", "WITHDRAWN": "已撤回"}
L_MAT = {"NOT_UPLOADED": "未上传", "UPLOADED": "待审核", "APPROVED": "已通过", "RETURNED": "已退回",
         "REJECTED": "已驳回"}
L_MATTYPE = {"ID_CARD": "身份证明", "ADMISSION_LETTER": "录取通知书", "PHOTO": "证件照",
             "ARCHIVE": "纸质档案", "AID_PROOF": "资助证明材料"}
L_DORM = {"UNASSIGNED": "未分配", "ASSIGNED": "已分配", "CHECKED_IN": "已入住", "EXCEPTION": "入住异常"}
L_EXCTYPE = {"IDENTITY": "身份核验异常", "PAYMENT": "缴费异常", "MATERIAL": "材料异常",
             "DORM": "宿舍异常", "NO_SHOW": "未到校"}
L_EXCSTATUS = {"OPEN": "待处理", "PROCESSING": "处理中", "RESOLVED": "已处理", "ESCALATED": "已升级"}
L_RISK = {"LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}

REGISTRATION_STEPS = [
    {"key": "ACTIVATE", "label": "账号激活"},
    {"key": "INFO", "label": "信息核对"},
    {"key": "MATERIAL", "label": "材料上传"},
    {"key": "PAYMENT", "label": "缴费/绿色通道"},
    {"key": "DORM", "label": "宿舍确认"},
    {"key": "CHECKIN", "label": "现场报到"},
    {"key": "CONFIRM", "label": "学院确认"},
]


def _default_steps_json() -> dict:
    return {s["key"]: "TODO" for s in REGISTRATION_STEPS}


def _op():
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("currentRoleCode") or ""


def _audit(db, biz_type, biz_id, action, detail="", before="", after=""):
    name, role = _op()
    row = OrientationAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=str(biz_id),
                                action=action, operator=name, role_name=role, detail=detail,
                                before_val=before, after_val=after, occurred_at=datetime.utcnow())
    db.add(row)
    return row


def _get_student(db, sid) -> OrientationStudent:
    s = db.get(OrientationStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("新生记录不存在或不在当前数据范围内")
    return s


def assert_orientation_student_scope(db, student: OrientationStudent, user=None) -> None:
    """教师端迎新详情/审核/文件统一复用稳定学籍数据范围；未绑定行仅全校范围可见。"""
    from app.core.affairs_security import build_affairs_context, no_data_scope
    ctx = build_affairs_context(user or get_current_user_ctx() or {}, db)
    if ctx.scope_type == "TENANT_ALL":
        return
    if not student.student_id:
        raise no_data_scope("迎新记录尚未绑定稳定学生主档，不在当前账号可证明的数据范围内")
    ctx.require_student(db, int(student.student_id))


def _amt(v) -> float:
    return float(v or 0)


def _stu_row(s: OrientationStudent, *, db=None, detail: bool = False) -> dict:
    row = {
        # studentId 固定为迎新台账主键，避免绑定学籍后与 StudentProfile.id 混用导致详情/操作串号。
        # profileStudentId 才是绑定的学籍档案 id（未绑定为空）。
        "id": str(s.id), "studentId": str(s.id), "version": int(s.version or 0),
        "profileStudentId": str(s.student_id) if s.student_id else "",
        "name": s.name, "batchId": str(s.batch_id),
        "admissionNo": s.admission_no, "studentNo": s.student_no or "",
        "gender": s.gender or "", "collegeName": s.college_name or "",
        "collegeId": str(s.college_id) if s.college_id else "",
        "majorName": s.major_name or "", "majorId": str(s.major_id) if s.major_id else "",
        "classId": str(s.class_id) if s.class_id else "", "className": s.class_name or "",
        "grade": s.grade or "", "admissionType": s.admission_type or "",
        "identityStatus": s.identity_status,
        "phone": mask_phone_encrypted(s.phone_encrypted),
        "idCard": mask_id_card_encrypted(s.id_card_encrypted), "origin": s.origin or "",
        "stage": s.stage, "stageLabel": L_STAGE.get(s.stage, s.stage),
        "reportStatus": s.report_status, "reportStatusLabel": L_REPORT.get(s.report_status, s.report_status),
        "paymentStatus": s.payment_status, "paymentStatusLabel": L_PAY.get(s.payment_status, s.payment_status),
        "greenChannelStatus": s.green_channel_status, "greenChannelStatusLabel": L_GC.get(s.green_channel_status, s.green_channel_status),
        "materialStatus": s.material_status, "materialStatusLabel": L_MAT.get(s.material_status, s.material_status),
        "dormStatus": s.dorm_status, "dormStatusLabel": L_DORM.get(s.dorm_status, s.dorm_status),
        "building": s.building or "", "room": s.room or "",
        "riskLevel": s.risk_level, "riskLabel": L_RISK.get(s.risk_level, s.risk_level),
        "recordStatus": s.record_status, "counselor": s.counselor or "",
        "payableAmount": _amt(s.payable_amount), "paidAmount": _amt(s.paid_amount),
        "blockedStep": s.blocked_step or "", "blockedReason": s.blocked_reason or "",
        "updateTime": _iso(s.updated_at),
    }
    if detail:
        if db is None:
            raise RuntimeError("detail serialization requires canonical step session")
        row["steps"] = student_step_projection(db, s)
        row["voidReason"] = s.void_reason or ""
        row["checkinTime"] = _iso(s.checkin_time) or ""
        row["exceptionNote"] = s.exception_note or ""
        from app.services.dorm_housing_projection import housing_map, housing_fields
        row.update(housing_map(db, [s.student_id]).get(int(s.student_id or 0),
                   housing_fields(linked=bool(s.student_id))))
        row["dormCheckinTime"] = row.pop("checkinTime", "")
        row["checkinTime"] = _iso(s.checkin_time) or ""
    return row


def _page(items, page, page_size):
    total = len(items)
    start = (max(1, page) - 1) * page_size
    return items[start:start + page_size], total


# ═══ 学生台账 ═══

def list_students(page, page_size, keyword=None, class_id=None, batch_id=None, stage=None,
                  report_status=None, payment_status=None, risk_level=None, user=None, pending_arrival=False):
    with session() as db:
        q = select(OrientationStudent).where(OrientationStudent.tenant_id == _tid(),
                                             OrientationStudent.is_deleted.is_(False),
                                             OrientationStudent.record_status == "ACTIVE")
        # 迎新台账只有已绑定 StudentProfile 的记录才可证明属于班级/学生范围。
        # 未绑定记录对范围角色 fail-closed；TENANT_ALL 才能查看。这一裁决同时被
        # 通用导出复用，避免列表收敛而导出泄露全校数据。
        from app.core.affairs_security import student_directory_scope
        class_ids, student_ids = student_directory_scope(user or get_current_user_ctx() or {})
        if student_ids is not None:
            q = q.where(
                OrientationStudent.student_id.in_(student_ids)
                if student_ids else false()
            )
        elif class_ids is not None:
            if not class_ids:
                q = q.where(false())
            else:
                scoped_profiles = select(StudentProfile.id).where(
                    StudentProfile.tenant_id == _tid(),
                    StudentProfile.is_deleted.is_(False),
                    StudentProfile.class_id.in_(class_ids),
                )
                q = q.where(OrientationStudent.student_id.in_(scoped_profiles))
        if stage:
            q = q.where(OrientationStudent.stage == stage)
        if pending_arrival:
            q = q.where(
                OrientationStudent.report_status.in_(["NOT_REPORTED", "PREPARED", "DELAYED", "NO_SHOW", "ABNORMAL"]),
                OrientationStudent.stage.notin_(["CANCELLED", "ENROLLED"]),
            )
        if report_status:
            q = q.where(OrientationStudent.report_status == report_status)
        if payment_status:
            q = q.where(OrientationStudent.payment_status == payment_status)
        if risk_level:
            q = q.where(OrientationStudent.risk_level == risk_level)
        if batch_id not in (None, ""):
            try:
                q = q.where(OrientationStudent.batch_id == int(batch_id))
            except (TypeError, ValueError):
                raise AppException("VALIDATION_ERROR", "batchId 须为数字")
        if class_id:
            try:
                q = q.where(OrientationStudent.class_id == int(class_id))
            except (TypeError, ValueError):
                raise AppException("VALIDATION_ERROR", "classId 须为数字")
        if keyword:
            kw = f"%{keyword.strip()}%"
            q = q.where(or_(OrientationStudent.name.like(kw),
                            OrientationStudent.admission_no.like(kw)))
        # P1-4（生产级审计整改）：DB 侧 count + offset/limit——此前整表拉取后 Python 分页，
        # 5000 新生的学校每次翻页都是「拉全量 + 序列化全量 + 丢弃绝大多数」。
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.scalars(q.order_by(OrientationStudent.id)
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        from app.services.dorm_housing_projection import housing_map, housing_fields
        facts = housing_map(db, [r.student_id for r in rows])
        return [{**_stu_row(r), **facts.get(int(r.student_id or 0),
                 housing_fields(linked=bool(r.student_id)))} for r in rows], total


def get_student_detail(sid, user=None) -> dict:
    with session() as db:
        s = _get_student(db, sid)
        assert_orientation_student_scope(db, s, user)
        gcs = db.scalars(select(GreenChannelApplication).where(
            GreenChannelApplication.tenant_id == _tid(),
            GreenChannelApplication.ori_student_id == s.id).order_by(GreenChannelApplication.id)).all()
        mats = db.scalars(select(OrientationMaterial).where(
            OrientationMaterial.tenant_id == _tid(),
            OrientationMaterial.ori_student_id == s.id).order_by(OrientationMaterial.id)).all()
        excs = db.scalars(select(OrientationException).where(
            OrientationException.tenant_id == _tid(),
            OrientationException.ori_student_id == s.id).order_by(OrientationException.id)).all()
        logs = db.scalars(select(OrientationAuditTrail).where(
            OrientationAuditTrail.tenant_id == _tid(),
            OrientationAuditTrail.biz_id == str(s.id)).order_by(OrientationAuditTrail.id.desc()).limit(20)).all()
        return {
            "student": _stu_row(s, db=db, detail=True),
            "steps": student_flow_steps(db, s),
            "greenChannels": [_gc_row(g) for g in gcs],
            "materials": [_mat_row(m) for m in mats],
            "exceptions": [_exc_row(e) for e in excs],
            "auditLogs": [_log_row(x) for x in logs],
        }


def create_student(body: dict, *, db=None) -> dict:
    """新建迎新台账行。db 由调用方传入时（批量导入整批事务）复用同一会话、不在本函数内提交，
    交由调用方统一 commit/rollback；单条调用（db=None）保持原有独立开合事务行为不变。"""
    name = str(body.get("name") or "").strip()
    adm = str(body.get("admissionNo") or "").strip()
    if not name or not adm:
        raise AppException("VALIDATION_ERROR", "姓名与录取编号必填")
    from contextlib import nullcontext
    owns_session = db is None
    with (session() if owns_session else nullcontext(db)) as db:
        try:
            batch_id = int(body.get("batchId") or 0)
        except (TypeError, ValueError):
            batch_id = 0
        batch = db.get(OrientationBatch, batch_id) if batch_id else None
        if not batch or batch.is_deleted or int(batch.tenant_id) != int(_tid()):
            raise AppException("VALIDATION_ERROR", "请选择本校有效迎新批次")
        if batch.status == "CLOSED":
            raise AppException("INVALID_STATE", "已结束迎新批次不可新增名单")

        from app.services.student_org_validator import validate_student_org_path
        org = validate_student_org_path(
            db,
            tenant_id=_tid(),
            college_id=body.get("collegeId"),
            major_id=body.get("majorId"),
            class_id=body.get("classId"),
            actor=get_current_user_ctx() or {},
            require_complete_org=True,
        )
        from app.models import College, Major, SchoolClass
        college = db.get(College, org.college_id)
        major = db.get(Major, org.major_id)
        school_class = db.get(SchoolClass, org.class_id)

        dup = db.scalars(select(OrientationStudent).where(
            OrientationStudent.tenant_id == _tid(), OrientationStudent.admission_no == adm,
            OrientationStudent.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", f"录取编号 {adm} 已存在")
        source_type = "DOMAIN_IMPORT" if body.get("sourceType") == "DOMAIN_IMPORT" else "MANUAL"
        source_record_id = str(body.get("sourceRecordId") or adm).strip()
        source_dup = db.scalars(select(OrientationStudent).where(
            OrientationStudent.tenant_id == _tid(),
            OrientationStudent.batch_id == batch_id,
            OrientationStudent.source_type == source_type,
            OrientationStudent.source_record_id == source_record_id,
        )).first()
        if source_dup:
            raise AppException("DATA_CONFLICT", f"来源记录 {source_record_id} 已导入该批次")
        from app.core.field_crypto import encrypt_field
        s = OrientationStudent(
            tenant_id=_tid(), batch_id=batch_id, name=name, admission_no=adm,
            student_no=str(body.get("studentNo") or "").strip() or None,
            college_id=org.college_id, college_name=college.college_name,
            major_id=org.major_id, major_name=major.major_name,
            class_id=org.class_id, class_name=school_class.class_name,
            gender=body.get("gender"), grade=body.get("grade"),
            admission_type=body.get("admissionType"),
            phone_encrypted=encrypt_field(body.get("phone")),
            id_card_encrypted=encrypt_field(body.get("idCard")),
            origin=body.get("origin"), counselor=body.get("counselor"),
            stage="ADMITTED", report_status="NOT_REPORTED",
            steps_json=_default_steps_json(), source_type=source_type,
            source_record_id=source_record_id)
        # 可选绑定学籍档案：优先 profileStudentId（与列表 studentId=迎新台账PK 区分）；
        # 兼容旧入参 studentId（仅当其指向真实学籍档案时才绑定，避免把迎新 PK 误当档案 id）。
        raw_sid = body.get("profileStudentId")
        if raw_sid in (None, ""):
            raw_sid = body.get("studentId")
        if raw_sid not in (None, ""):
            try:
                sid_int = int(raw_sid)
            except (TypeError, ValueError):
                raise AppException("VALIDATION_ERROR", "profileStudentId 须为数字")
            from app.models import StudentProfile
            prof = db.get(StudentProfile, sid_int)
            if not prof or prof.is_deleted or int(prof.tenant_id) != int(_tid()):
                raise AppException("VALIDATION_ERROR", "profileStudentId 对应学籍不存在或不属于本校")
            s.student_id = sid_int
            s.identity_status = "LINKED"
        else:
            s.identity_status = "UNLINKED"
        db.add(s)
        db.flush()
        ensure_student_steps(db, s, status_source="PROCESS_FACT")
        db.add(OrientationPaymentAccount(
            tenant_id=_tid(), orientation_student_id=s.id, student_id=s.student_id,
            payable_amount=0, paid_amount=0, status="UNPAID",
            source_type="LEGACY_BACKFILL", source_biz_id=f"orientation-student:{s.id}",
            synced_at=datetime.utcnow(),
        ))
        _audit(db, "STUDENT", s.id, "新增新生记录", f"{name}（{adm}）")
        if owns_session:
            db.commit()
        else:
            db.flush()
        return {"id": str(s.id), "studentId": str(s.id), "version": int(s.version or 0),
                "profileStudentId": str(s.student_id) if s.student_id else ""}


def update_student(sid, body: dict) -> dict:
    if any(body.get(key) is not None for key in ("reportStatus", "building", "room", "dormStatus")):
        raise AppException("INVALID_STATE", "报到与住宿状态由正式办理流程更新，请使用现场报到、学院确认或房态图")
    with session() as db:
        s = _get_student(db, sid)
        assert_orientation_student_scope(db, s)
        field_map = {"name": "name", "origin": "origin", "counselor": "counselor"}
        for k, col in field_map.items():
            if body.get(k) is not None:
                setattr(s, col, body[k])
        if body.get("classId") not in (None, ""):
            from app.services.student_org_validator import validate_student_org_path
            org = validate_student_org_path(
                db,
                tenant_id=_tid(),
                college_id=body.get("collegeId"),
                major_id=body.get("majorId"),
                class_id=body.get("classId"),
                actor=get_current_user_ctx() or {},
                require_complete_org=True,
            )
            from app.models import College, Major, SchoolClass
            college = tenant_get(db, College, org.college_id)
            major = tenant_get(db, Major, org.major_id)
            school_class = tenant_get(db, SchoolClass, org.class_id)
            s.college_id, s.college_name = org.college_id, college.college_name
            s.major_id, s.major_name = org.major_id, major.major_name
            s.class_id, s.class_name = org.class_id, school_class.class_name
        phone = body.get("phone")
        if phone is not None and phone.strip() and "*" not in phone:
            from app.core.field_crypto import encrypt_field
            s.phone_encrypted = encrypt_field(phone.strip())
        s.version += 1
        _audit(db, "STUDENT", s.id, "编辑报到信息")
        db.commit()
        return {"id": str(s.id)}


def disposition_student(sid, body):
    from app.core.optimistic_lock import require_expected_version
    from app.models import DormStay, DormBed, DormAllocationItem, OrientationCheckinToken
    from app.services.dorm_housing_projection import sync_orientation
    status = str(body.get("status") or "").upper()
    reason = str(body.get("reason") or "").strip()
    if status not in {"NO_SHOW", "CANCELLED", "DEFERRED", "RESUME"} or len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "请选择处理结果，原因至少填写 5 个字")
    version = require_expected_version(body.get("expectedVersion"))
    with session() as db:
        _archive_scope(db)
        student = _get_student(db, sid)
        if student.student_id:
            db.execute(select(StudentProfile.id).where(StudentProfile.id == student.student_id,
                StudentProfile.tenant_id == _tid()).with_for_update()).first()
        student = db.scalars(select(OrientationStudent).where(OrientationStudent.id == student.id,
            OrientationStudent.tenant_id == _tid()).execution_options(populate_existing=True).with_for_update()).one()
        if student.version != version:
            raise AppException("VERSION_CONFLICT", "记录已变化，请刷新后重试", http_status=409)
        if student.stage == "ENROLLED" or student.report_status in {"CHECKED_IN", "COLLEGE_CONFIRMED"}:
            raise AppException("INVALID_STATE", "已报到学生请通过学籍及住宿正式流程办理")
        batch = _get_batch(db, student.batch_id)
        if batch.status != "ACTIVE":
            raise AppException("INVALID_STATE", "仅开放中的迎新批次可办理")
        stays = db.scalars(select(DormStay).where(DormStay.tenant_id == _tid(),
            DormStay.student_id == student.student_id, DormStay.is_deleted.is_(False),
            DormStay.status.in_(["RESERVED", "ACTIVE"])).with_for_update()).all() if student.student_id else []
        if any(stay.status == "ACTIVE" for stay in stays):
            raise AppException("INVALID_STATE", "学生已实际入住，请先办理正式退宿")
        before = student.stage
        if status == "RESUME" and before not in {"NO_SHOW", "CANCELLED", "DEFERRED"}:
            raise AppException("INVALID_STATE", "当前记录无需恢复报到")
        # Delay keeps the reserved bed. A confirmed non-arrival/cancellation releases it atomically.
        if status in {"NO_SHOW", "CANCELLED"}:
            for stay in stays:
                bed = db.scalars(select(DormBed).where(DormBed.id == stay.bed_id,
                    DormBed.tenant_id == _tid(), DormBed.is_deleted.is_(False)).with_for_update()).first()
                if not bed or bed.status != "LOCKED" or bed.student_id:
                    raise AppException("DATA_CONFLICT", "预留床位状态不一致，请先核查房态")
                bed.status = "VACANT"
                bed.version += 1
                stay.status = "CANCELLED"
                stay.version += 1
            if student.student_id:
                items = db.scalars(select(DormAllocationItem).where(DormAllocationItem.tenant_id == _tid(),
                    DormAllocationItem.student_id == student.student_id,
                    DormAllocationItem.is_deleted.is_(False),
                    DormAllocationItem.status.in_(["PENDING", "PROPOSED", "RESERVED", "CONFIRMED"])).with_for_update()).all()
                for item in items:
                    item.status = "CANCELLED"
                    item.version += 1
                sync_orientation(db, student.student_id)
        tokens = db.scalars(select(OrientationCheckinToken).where(OrientationCheckinToken.tenant_id == _tid(),
            OrientationCheckinToken.orientation_student_id == student.id,
            OrientationCheckinToken.status == "ISSUED").with_for_update()).all()
        for token in tokens:
            token.status = "REVOKED"
        student.stage = "ADMITTED" if status == "RESUME" else status
        student.report_status = "DELAYED" if status == "DEFERRED" else "NO_SHOW" if status in {"NO_SHOW", "CANCELLED"} else "NOT_REPORTED"
        student.exception_note = reason[:500]
        student.version += 1
        _audit(db, "STUDENT", student.id, "调整报到安排", reason[:1000], before=before, after=student.stage)
        db.commit()
        return {"id": str(student.id), "stage": student.stage, "version": student.version}


def void_student(sid, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        s = _get_student(db, sid)
        s.record_status = "VOIDED"
        s.void_reason = reason.strip()
        s.is_deleted = True
        s.version += 1
        _audit(db, "STUDENT", s.id, "作废报到记录", reason.strip())
        db.commit()
        return {"id": str(s.id)}


def verify_student(sid, passed: bool = True, reason: str = "") -> dict:
    """新生信息核验：通过 → 预报到已核验（stage=PRE_STUDENT_VERIFIED，环节 INFO=DONE）；
    不通过 → 记录原因 + 标记高风险，stage 不前进。"""
    with session() as db:
        s = _get_student(db, sid)
        assert_orientation_student_scope(db, s)
        if s.stage in ("ENROLLED", "CANCELLED", "NO_SHOW", "DEFERRED"):
            raise AppException("INVALID_STATE", "该新生已入学/已取消，不可再核验")
        if passed:
            before = s.stage
            if s.report_status != "CHECKED_IN":
                s.stage = "PRE_STUDENT_VERIFIED"
            s.exception_note = ""
            set_student_step_status(db, s, "INFO", "DONE", status_source="PROCESS_FACT",
                                    source_biz_id=f"student:{s.id}:verify")
            _audit(db, "STUDENT", s.id, "信息核验通过", before=before, after="PRE_STUDENT_VERIFIED")
        else:
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "核验不通过原因必填且不少于 5 字")
            s.exception_note = reason.strip()
            if s.risk_level == "LOW":
                s.risk_level = "HIGH"
            _audit(db, "STUDENT", s.id, "信息核验不通过", reason.strip())
        s.version += 1
        db.commit()
        return {"id": str(s.id), "stage": s.stage}


# ═══ 报到进度 ═══

def list_progress(page, page_size, keyword=None, blocked_only="NO"):
    with session() as db:
        q = select(OrientationStudent).where(OrientationStudent.tenant_id == _tid(),
                                             OrientationStudent.is_deleted.is_(False),
                                             OrientationStudent.record_status == "ACTIVE")
        if keyword:
            kw = f"%{keyword.strip()}%"
            q = q.where(or_(OrientationStudent.name.like(kw),
                            OrientationStudent.admission_no.like(kw)))
        if blocked_only == "YES":
            q = q.where(OrientationStudent.blocked_step.is_not(None))
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.scalars(q.order_by(OrientationStudent.id)
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        items = []
        for r in rows:
            steps = student_step_projection(db, r)
            active_keys = [step["key"] for step in student_flow_steps(db, r)]
            # 只按当前启用的环节计分母/分子——停用的环节不再拖累进度分数（真正让流程配置生效）
            done = sum(1 for k in active_keys if steps.get(k) in ("DONE", "WAIVED", "NOT_REQUIRED"))
            items.append({"id": str(r.id), "name": r.name, "admissionNo": r.admission_no,
                          "className": r.class_name or "",
                          "progress": f"{done}/{len(active_keys) or 7}",
                          "blockedStep": r.blocked_step or "", "blockedReason": r.blocked_reason or "",
                          "reportStatus": r.report_status,
                          "reportStatusLabel": L_REPORT.get(r.report_status, r.report_status)})
        page_items, total = _page(items, page, page_size)
        return page_items, total


def update_blocked(sid, blocked_step=None, blocked_reason=None) -> dict:
    if blocked_step and (not blocked_reason or len(str(blocked_reason).strip()) < 5):
        raise AppException("VALIDATION_ERROR", "卡点说明必填且不少于 5 字")
    with session() as db:
        s = _get_student(db, sid)
        if blocked_step is not None:
            step_key = blocked_step or None
            if step_key is None and s.blocked_step:
                raise AppException("INVALID_STATE", "清除卡点须走业务事实完成或人工豁免")
            s.blocked_step = step_key
            if step_key:
                set_student_step_status(
                    db, s, step_key, "BLOCKED", status_source="PROCESS_FACT",
                    source_biz_id=f"student:{s.id}:blocked",
                    blocked_reason=str(blocked_reason or s.blocked_reason or "").strip(),
                )
        if blocked_reason is not None:
            s.blocked_reason = blocked_reason or None
        s.version += 1
        _audit(db, "PROGRESS", s.id, "编辑卡点事项", blocked_reason or "")
        db.commit()
        return {"id": str(s.id)}


def resolve_blocked(sid, note="") -> dict:
    note = str(note or "").strip()
    if len(note) < 5:
        raise AppException("VALIDATION_ERROR", "人工豁免原因必填且不少于 5 字")
    with session() as db:
        s = _get_student(db, sid)
        prev = s.blocked_step or ""
        if not prev:
            raise AppException("INVALID_STATE", "当前新生没有待处理卡点")
        audit = _audit(db, "PROGRESS", s.id, "人工豁免卡点", note,
                       before="BLOCKED", after="WAIVED")
        db.flush()
        actor = str((get_current_user_ctx() or {}).get("userId") or "").strip()
        raw_actor = actor[3:] if actor.startswith("db-") else actor
        try:
            actor_id = int(raw_actor)
        except (TypeError, ValueError):
            import zlib
            actor_id = (zlib.crc32(actor.encode("utf-8")) & 0x7FFFFFFF) or 1
        set_student_step_status(
            db, s, prev, "WAIVED", status_source="MANUAL_WAIVER",
            source_biz_id=f"audit:{audit.id}", waived_by=actor_id, waive_reason=note,
            waive_evidence_ref=f"orientation-audit:{audit.id}",
        )
        s.blocked_step = None
        s.blocked_reason = None
        s.version += 1
        db.commit()
        return {"id": str(s.id), "stepStatus": "WAIVED"}


# ═══ 缴费 ═══

def list_payments(page, page_size, keyword=None, payment_status=None, user=None):
    with session() as db:
        q = (select(OrientationPaymentAccount, OrientationStudent)
             .join(OrientationStudent, (
                 OrientationStudent.id == OrientationPaymentAccount.orientation_student_id
             ) & (OrientationStudent.tenant_id == OrientationPaymentAccount.tenant_id))
             .where(
                 OrientationPaymentAccount.tenant_id == _tid(),
                 OrientationPaymentAccount.is_deleted.is_(False),
                 OrientationStudent.is_deleted.is_(False),
                 OrientationStudent.record_status == "ACTIVE",
             ))
        from app.core.affairs_security import student_directory_scope
        class_ids, student_ids = student_directory_scope(user or get_current_user_ctx() or {})
        if student_ids is not None:
            q = q.where(
                OrientationStudent.student_id.in_(student_ids) if student_ids else false()
            )
        elif class_ids is not None:
            if not class_ids:
                q = q.where(false())
            else:
                q = q.where(OrientationStudent.student_id.in_(select(StudentProfile.id).where(
                    StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                    StudentProfile.class_id.in_(class_ids),
                )))
        if payment_status:
            if payment_status == "GREEN_CHANNEL":
                q = q.where(OrientationStudent.green_channel_status == "APPROVED")
            else:
                q = q.where(OrientationPaymentAccount.status == payment_status)
        if keyword:
            value = f"%{keyword.strip()}%"
            q = q.where(or_(OrientationStudent.name.like(value),
                            OrientationStudent.admission_no.like(value)))
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.execute(q.order_by(OrientationStudent.id)
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        items = [{"id": str(r.id), "paymentAccountId": str(account.id),
                  "paymentVersion": int(account.version or 0),
                  "name": r.name, "admissionNo": r.admission_no,
                  "className": r.class_name or "",
                  "payableAmount": f"¥{_amt(account.payable_amount):.0f}",
                  "paidAmount": f"¥{_amt(account.paid_amount):.0f}",
                  "paymentStatus": "GREEN_CHANNEL" if r.green_channel_status == "APPROVED" else account.status,
                  "paymentStatusLabel": ("绿色通道" if r.green_channel_status == "APPROVED"
                                           else L_PAY.get(account.status, account.status)),
                  "greenChannelStatus": r.green_channel_status,
                  "phone": mask_phone_encrypted(r.phone_encrypted)} for account, r in rows]
        return items, total


# ═══ 绿色通道 ═══

def _gc_row(g: GreenChannelApplication, stu: OrientationStudent | None = None,
            attachments=None) -> dict:
    return {"id": str(g.id), "studentId": str(g.ori_student_id),
            "profileStudentId": str(g.student_id or ""), "version": int(g.version or 0),
            "name": stu.name if stu else "", "className": stu.class_name if stu else "",
            "applyType": g.apply_type, "applyAmount": _amt(g.apply_amount),
            "submitTime": _iso(g.submit_time) or "", "status": g.status,
            "statusLabel": L_GC.get(g.status, g.status), "reviewer": g.reviewer or "",
            "reviewTime": _iso(g.review_time) or "", "rejectReason": g.reject_reason or "",
            "remark": g.remark or "", "attachments": list(attachments or [])}


def list_green_channels(page, page_size, keyword=None, status=None, user=None, batch_id=None):
    with session() as db:
        # P1-4：join 学生表消 N+1（此前每行一次 db.get），keyword/分页全部下沉 DB
        q = (select(GreenChannelApplication, OrientationStudent)
             .join(OrientationStudent, OrientationStudent.id == GreenChannelApplication.ori_student_id)
             .where(GreenChannelApplication.tenant_id == _tid(),
                    GreenChannelApplication.is_deleted.is_(False),
                    OrientationStudent.tenant_id == _tid(),
                    OrientationStudent.is_deleted.is_(False),
                    OrientationStudent.record_status == "ACTIVE"))
        from app.core.affairs_security import student_directory_scope
        class_ids, student_ids = student_directory_scope(user or get_current_user_ctx() or {})
        if student_ids is not None:
            q = q.where(
                OrientationStudent.student_id.in_(student_ids) if student_ids else false()
            )
        elif class_ids is not None:
            if not class_ids:
                q = q.where(false())
            else:
                q = q.where(OrientationStudent.student_id.in_(select(StudentProfile.id).where(
                    StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                    StudentProfile.class_id.in_(class_ids),
                )))
        if batch_id is not None:
            q = q.where(OrientationStudent.batch_id == int(batch_id))
        if status:
            q = q.where(GreenChannelApplication.status == status)
        if keyword:
            q = q.where(OrientationStudent.name.like(f"%{keyword.strip()}%"))
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.execute(q.order_by(GreenChannelApplication.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        ids = [str(g.id) for g, _ in rows]
        attachments = {value: [] for value in ids}
        if ids:
            from app.models.file import FileBinding, FileObject
            file_rows = db.execute(select(FileBinding.biz_id, FileObject.file_name).join(
                FileObject,
                (FileObject.id == FileBinding.file_id)
                & (FileObject.tenant_id == FileBinding.tenant_id),
            ).where(
                FileBinding.tenant_id == _tid(),
                FileBinding.biz_type == "ORIENTATION_GREEN_CHANNEL",
                FileBinding.biz_id.in_(ids),
                FileBinding.is_current.is_(True), FileBinding.status == "ACTIVE",
                FileBinding.is_deleted.is_(False), FileObject.is_deleted.is_(False),
            )).all()
            for biz_id, file_name in file_rows:
                attachments.setdefault(str(biz_id), []).append(file_name)
        return [_gc_row(g, stu, attachments.get(str(g.id))) for g, stu in rows], total


def _gc_act(gid, target_status, reason_field=None, reason=None, need_reason=False,
            action_label="", expected_version=None, user=None):
    if need_reason and (not reason or len(reason.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "原因必填且不少于 5 字")
    with session() as db:
        g = db.scalars(select(GreenChannelApplication).where(
            GreenChannelApplication.tenant_id == _tid(),
            GreenChannelApplication.id == int(gid),
            GreenChannelApplication.is_deleted.is_(False),
        ).with_for_update()).first()
        if not g or g.is_deleted or g.tenant_id != _tid():
            raise not_found("绿色通道申请不存在")
        if g.status in ("APPROVED", "REJECTED"):
            raise AppException("DATA_CONFLICT", "该申请已终审，请刷新")
        if expected_version is None or int(expected_version) != int(g.version or 0):
            raise AppException("APPROVAL_VERSION_CONFLICT", "申请状态已变化，请刷新后重试")
        before = g.status
        name, _ = _op()
        g.status = target_status
        g.reviewer = name
        g.review_time = datetime.utcnow()
        if reason_field == "reject":
            g.reject_reason = (reason or "").strip()
        elif reason_field == "remark":
            g.remark = (reason or "").strip()
        g.version += 1
        stu = tenant_get(db, OrientationStudent, g.ori_student_id)
        audit_detail = reason or ""
        if stu:
            assert_orientation_student_scope(db, stu, user)
            if target_status == "APPROVED":
                stu.green_channel_status = "APPROVED"
                if stu.payment_status in ("UNPAID", "PARTIAL"):
                    stu.payment_status = "GREEN_CHANNEL"
                steps = student_step_projection(db, stu)
                if stu.blocked_step == "PAYMENT" or steps.get("PAYMENT") == "BLOCKED":
                    stu.blocked_step = None
                    stu.blocked_reason = None
                    set_student_step_status(
                        db, stu, "PAYMENT", "DONE", status_source="PROCESS_FACT",
                        source_biz_id=f"green-channel:{g.id}",
                    )
                    audit_detail = (audit_detail + "；绿色通道通过，缴费卡点自动解除").lstrip("；")
            elif target_status == "REJECTED":
                stu.green_channel_status = "REJECTED"
            elif target_status == "RETURNED":
                stu.green_channel_status = "RETURNED"
            from app.services.orientation_qualification_service import evaluate
            evaluate(db, stu, persist=True, actor_id=None)
        _audit(db, "GREEN_CHANNEL", g.id, action_label, audit_detail or action_label, before, target_status)
        db.commit()
        return {"id": str(g.id), "status": target_status, "version": int(g.version or 0)}


def approve_green_channel(gid, remark="", expected_version=None, user=None):
    return _gc_act(gid, "APPROVED", "remark", remark, False, "审核通过",
                   expected_version=expected_version, user=user)


def reject_green_channel(gid, reason, expected_version=None, user=None):
    return _gc_act(gid, "REJECTED", "reject", reason, True, "驳回申请",
                   expected_version=expected_version, user=user)


def return_green_channel(gid, reason, expected_version=None, user=None):
    return _gc_act(gid, "RETURNED", "reject", reason, True, "退回补充",
                   expected_version=expected_version, user=user)


# ═══ 学生自助（移动端·预报到信息采集 + 绿色通道申请）+ 现场报到核验 ═══

def student_submit_collect(sid, phone: str = "", origin: str = "") -> dict:
    """预报到信息采集（学生自助）：确认联系电话/生源地，推进 INFO 环节为已完成；
    报到状态仍为未报到时转入预报到中（PREPARED）。"""
    phone = (phone or "").strip()
    origin = (origin or "").strip()
    if phone and not (phone.isdigit() and 6 <= len(phone) <= 20):
        raise AppException("VALIDATION_ERROR", "手机号格式不正确")
    with session() as db:
        s = _get_student(db, sid)
        if phone:
            from app.core.field_crypto import encrypt_field
            s.phone_encrypted = encrypt_field(phone)
        if origin:
            s.origin = origin
        set_student_step_status(db, s, "INFO", "DONE", status_source="PROCESS_FACT",
                                source_biz_id=f"student:{s.id}:collect")
        if s.blocked_step == "INFO":
            s.blocked_step = None
            s.blocked_reason = None
        if s.report_status == "NOT_REPORTED":
            s.report_status = "PREPARED"
        s.version += 1
        _audit(db, "PROGRESS", s.id, "学生提交预报到信息",
              "已确认联系方式" + ("、生源地" if origin else ""))
        db.commit()
        return {"id": str(s.id), "reportStatus": s.report_status}


def student_submit_green_channel(sid, apply_type: str, apply_amount=0, remark: str = "",
                                 file_ids=None, actor: dict | None = None,
                                 client_request_id: str = "") -> dict:
    """绿色通道申请（学生自助提交，等待辅导员/资助中心审核）。

    V3 §8.1：附件以 TEMP_PRIVATE fileId 传入，正式绑定在本函数的事务里由 canonical
    file binding 服务完成——校验 owner/tenant/扫描状态/用途后才建 FileBinding。
    任一附件不可用会让整笔申请回滚，临时文件保持私有等 TTL 回收。
    """
    apply_type = (apply_type or "").strip()
    if not apply_type:
        raise AppException("VALIDATION_ERROR", "请选择困难类型")
    client_request_id = str(client_request_id or "").strip()
    if len(client_request_id) < 8:
        raise AppException("VALIDATION_ERROR", "clientRequestId 必填")
    with session() as db:
        s = db.scalars(select(OrientationStudent).where(
            OrientationStudent.tenant_id == _tid(), OrientationStudent.id == int(sid),
            OrientationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        if not s:
            raise not_found("新生记录不存在")
        prior = db.scalars(select(GreenChannelApplication).where(
            GreenChannelApplication.tenant_id == _tid(),
            GreenChannelApplication.client_request_id == client_request_id,
            GreenChannelApplication.is_deleted.is_(False),
        ).with_for_update()).first()
        if prior:
            if (int(prior.ori_student_id) == int(s.id)
                    and prior.apply_type == apply_type
                    and _amt(prior.apply_amount) == _amt(apply_amount)
                    and (prior.remark or "") == (remark or "").strip()):
                return _gc_row(prior, s)
            raise AppException("IDEMPOTENCY_CONFLICT", "clientRequestId 已用于其他绿色通道申请")
        if s.green_channel_status in ("SUBMITTED", "REVIEWING", "APPROVED"):
            raise AppException("DATA_CONFLICT", "已有申请正在处理或已通过，无需重复提交")
        g = GreenChannelApplication(
            tenant_id=_tid(), ori_student_id=s.id, student_id=s.student_id,
            client_request_id=client_request_id, apply_type=apply_type,
            apply_amount=_amt(apply_amount), submit_time=datetime.utcnow(),
            status="SUBMITTED", remark=(remark or "").strip())
        db.add(g)
        s.green_channel_status = "SUBMITTED"
        s.version += 1
        db.flush()
        for file_id in (file_ids or []):
            from app.services import file_business_binding_service as file_binding_svc
            file_binding_svc.bind_file_to_business(
                db,
                file_id=file_id,
                biz_type="ORIENTATION_GREEN_CHANNEL",
                biz_id=g.id,
                actor=actor or {},
                subject_type="STUDENT",
                subject_id=s.student_id or s.id,
                relation_type="BUSINESS_EVIDENCE",
                module_code="ORIENTATION",
                student_id=s.student_id,
                batch_id=str(s.batch_id),
                college_id=s.college_id,
                class_id=s.class_id,
                scope={
                    "orientationStudentId": str(s.id), "studentId": str(s.student_id or ""),
                    "applyType": apply_type,
                },
            )
        _audit(db, "GREEN_CHANNEL", g.id, "学生提交绿色通道申请",
              f"{apply_type} ¥{_amt(apply_amount):.0f}")
        db.commit()
        return _gc_row(g, s)


def teacher_checkin_by_admission_no(admission_no: str, operator_name: str = "") -> dict:
    """O5 closes the insecure admission-number write path."""
    raise AppException(
        "DEPRECATED_WRITE_PATH",
        "录取编号只是展示事实，不能作为现场报到凭证；请使用签名凭证流程",
        http_status=410,
    )


# ═══ 材料审核 ═══

def _mat_row(m: OrientationMaterial, stu: OrientationStudent | None = None,
             file_data: dict | None = None) -> dict:
    return {"id": str(m.id), "studentId": str(m.ori_student_id),
            "name": stu.name if stu else "", "className": stu.class_name if stu else "",
            "materialType": m.material_type, "materialTypeLabel": L_MATTYPE.get(m.material_type, m.material_type),
            "fileName": m.file_name or "", "submitTime": _iso(m.submit_time) or "",
            "submissionNo": int(m.submission_no or 1), "isCurrent": bool(m.is_current),
            "assetId": str(m.asset_id or ""), "fileVersionId": str(m.file_version_id or ""),
            "status": m.status, "statusLabel": L_MAT.get(m.status, m.status),
            "reviewer": m.reviewer or "", "reviewTime": _iso(m.review_time) or "",
            "returnReason": m.return_reason or "", **(file_data or {})}


def list_materials(page, page_size, keyword=None, status=None, material_type=None, user=None,
                   batch_id=None, orientation_student_id=None):
    with session() as db:
        q = select(OrientationMaterial, OrientationStudent).join(
            OrientationStudent,
            (OrientationStudent.id == OrientationMaterial.ori_student_id)
            & (OrientationStudent.tenant_id == OrientationMaterial.tenant_id),
        ).where(
            OrientationMaterial.tenant_id == _tid(),
            OrientationMaterial.is_deleted.is_(False),
            OrientationMaterial.is_current.is_(True),
            OrientationStudent.is_deleted.is_(False),
            OrientationStudent.record_status == "ACTIVE",
        )
        from app.core.affairs_security import student_directory_scope
        class_ids, student_ids = student_directory_scope(user or get_current_user_ctx() or {})
        if student_ids is not None:
            q = q.where(
                OrientationStudent.student_id.in_(student_ids) if student_ids else false()
            )
        elif class_ids is not None:
            if not class_ids:
                q = q.where(false())
            else:
                q = q.where(OrientationStudent.student_id.in_(select(StudentProfile.id).where(
                    StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                    StudentProfile.class_id.in_(class_ids),
                )))
        if batch_id is not None:
            q = q.where(OrientationStudent.batch_id == int(batch_id))
        if orientation_student_id is not None:
            q = q.where(OrientationMaterial.ori_student_id == int(orientation_student_id))
        if status:
            q = q.where(OrientationMaterial.status == status)
        if material_type:
            q = q.where(OrientationMaterial.material_type == material_type)
        if keyword:
            q = q.where(OrientationStudent.name.like(f"%{keyword.strip()}%"))
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.execute(q.order_by(OrientationMaterial.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        material_ids = [str(material.id) for material, _student in rows]
        file_by_material: dict[str, dict] = {}
        if material_ids:
            from app.models.file import FileBinding, FileObject
            from app.services import file_access_resolvers as _file_access_resolvers  # noqa: F401
            from app.services.file_access_service import file_view

            file_rows = db.execute(select(FileBinding, FileObject).join(
                FileObject,
                (FileObject.id == FileBinding.file_id)
                & (FileObject.tenant_id == FileBinding.tenant_id),
            ).where(
                FileBinding.tenant_id == _tid(),
                FileBinding.biz_type == "ORIENTATION_MATERIAL",
                FileBinding.biz_id.in_(material_ids),
                FileBinding.is_current.is_(True),
                FileBinding.status == "ACTIVE",
                FileBinding.is_deleted.is_(False),
                FileObject.is_deleted.is_(False),
            )).all()
            actor = user or get_current_user_ctx() or {}
            for binding, file_obj in file_rows:
                view = file_view(file_obj, user=actor, bindings=[binding], db=db)
                allowed = list(view.get("allowedActions") or [])
                file_by_material[str(binding.biz_id)] = {
                    **view,
                    "canPreview": "preview" in allowed,
                    "canDownload": "download" in allowed,
                }
        return [
            _mat_row(material, student, file_by_material.get(str(material.id)))
            for material, student in rows
        ], total


def _refresh_material_status(db, stu):
    mats = db.scalars(select(OrientationMaterial).where(
        OrientationMaterial.tenant_id == _tid(),
        OrientationMaterial.ori_student_id == stu.id,
        OrientationMaterial.is_current.is_(True),
        OrientationMaterial.is_deleted.is_(False))).all()
    if mats and all(m.status == "APPROVED" for m in mats):
        stu.material_status = "APPROVED"
        if stu.blocked_step == "MATERIAL":
            stu.blocked_step = None
            stu.blocked_reason = None
            set_student_step_status(
                db, stu, "MATERIAL", "DONE", status_source="PROCESS_FACT",
                source_biz_id=f"student:{stu.id}:materials-approved",
            )


def approve_material(mid, comment="", user=None):
    with session() as db:
        m = db.get(OrientationMaterial, int(mid))
        if not m or m.is_deleted or m.tenant_id != _tid():
            raise not_found("材料不存在")
        if not m.is_current:
            raise AppException("DATA_CONFLICT", "历史材料版本不可审核")
        stu = tenant_get(db, OrientationStudent, m.ori_student_id)
        if not stu:
            raise not_found("材料所属迎新记录不存在")
        assert_orientation_student_scope(db, stu, user)
        if m.status == "APPROVED":
            raise AppException("DATA_CONFLICT", "该材料已通过")
        before = m.status
        name, _ = _op()
        m.status = "APPROVED"
        m.reviewer = name
        m.review_time = datetime.utcnow()
        m.version += 1
        if m.file_version_id:
            from app.models.file import FileVersion
            version = tenant_get(db, FileVersion, m.file_version_id)
            if version:
                version.status = "APPROVED"
        _refresh_material_status(db, stu)
        from app.services.orientation_qualification_service import evaluate
        evaluate(db, stu, persist=True, actor_id=None)
        _audit(db, "MATERIAL", m.id, "审核通过", comment, before, "APPROVED")
        db.commit()
        return {"id": str(m.id), "status": "APPROVED"}


def return_material(mid, reason, user=None):
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        m = db.get(OrientationMaterial, int(mid))
        if not m or m.is_deleted or m.tenant_id != _tid():
            raise not_found("材料不存在")
        if not m.is_current:
            raise AppException("DATA_CONFLICT", "历史材料版本不可审核")
        stu = tenant_get(db, OrientationStudent, m.ori_student_id)
        if not stu:
            raise not_found("材料所属迎新记录不存在")
        assert_orientation_student_scope(db, stu, user)
        before = m.status
        name, _ = _op()
        m.status = "RETURNED"
        m.reviewer = name
        m.review_time = datetime.utcnow()
        m.return_reason = reason.strip()
        m.version += 1
        if m.file_version_id:
            from app.models.file import FileVersion
            version = tenant_get(db, FileVersion, m.file_version_id)
            if version:
                version.status = "REJECTED"
        stu.material_status = "RETURNED"
        from app.services.orientation_qualification_service import evaluate
        evaluate(db, stu, persist=True, actor_id=None)
        _audit(db, "MATERIAL", m.id, "退回材料", reason.strip(), before, "RETURNED")
        db.commit()
        return {"id": str(m.id), "status": "RETURNED"}


# ═══ 宿舍 ═══

def list_dorms(page, page_size, keyword=None, dorm_status=None, building=None, batch_id=None):
    from app.models import SchoolClass
    from app.services.dorm_housing_projection import housing_query, housing_fields
    from app.core.affairs_security import student_directory_scope
    with session() as db:
        facts = housing_query().subquery()
        q = select(OrientationStudent, facts).outerjoin(
            facts, facts.c.student_id == OrientationStudent.student_id).where(
            OrientationStudent.tenant_id == _tid(), OrientationStudent.is_deleted.is_(False),
            OrientationStudent.record_status == "ACTIVE")
        if batch_id is not None:
            q = q.where(OrientationStudent.batch_id == int(batch_id))
        class_ids, student_ids = student_directory_scope(get_current_user_ctx() or {})
        if student_ids is not None:
            q = q.where(OrientationStudent.student_id.in_(student_ids) if student_ids else false())
        elif class_ids is not None:
            profiles = select(StudentProfile.id).where(StudentProfile.tenant_id == _tid(),
                StudentProfile.is_deleted.is_(False), StudentProfile.class_id.in_(class_ids))
            q = q.where(OrientationStudent.student_id.in_(profiles))
        current_status = case((facts.c.housing_status == "ACTIVE", "CHECKED_IN"),
            (facts.c.housing_status == "RESERVED", "ASSIGNED"),
            (facts.c.housing_status == "EXCEPTION", "EXCEPTION"), else_="UNASSIGNED")
        if dorm_status:
            q = q.where(current_status == dorm_status)
        if building:
            q = q.where(facts.c.building_name == building,
                        facts.c.housing_status.in_(["ACTIVE", "RESERVED"]))
        if keyword and keyword.strip():
            kw = f"%{keyword.strip()}%"
            q = q.where(or_(OrientationStudent.name.like(kw),
                OrientationStudent.admission_no.like(kw), facts.c.room_no.like(kw)))
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.execute(q.order_by(OrientationStudent.id)
            .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        visible_ids = [row[0].student_id for row in rows if row[0].student_id]
        class_names = dict(db.execute(select(StudentProfile.id, SchoolClass.class_name).join(
            SchoolClass, and_(SchoolClass.id == StudentProfile.class_id, SchoolClass.tenant_id == _tid(),
                SchoolClass.is_deleted.is_(False))).where(StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False), StudentProfile.id.in_(visible_ids or [-1]))).all())
        items = []
        for result in rows:
            r = result[0]
            fact = result._mapping if result._mapping["housing_status"] else None
            fields = housing_fields(fact, linked=bool(r.student_id))
            items.append({"id": str(r.id), "profileStudentId": str(r.student_id or ""),
                "batchId": str(r.batch_id), "name": r.name, "className": class_names.get(r.student_id, r.class_name or ""),
                **fields, "exceptionNote": r.exception_note or "",
                "phone": mask_phone_encrypted(r.phone_encrypted)})
        return items, total


def update_dorm(sid, body: dict) -> dict:
    raise AppException("INVALID_STATE", "请通过分配计划安排床位，或在房态图办理入住；迎新台账自动同步住宿状态")


def batch_confirm_checkin(ids: list) -> dict:
    raise AppException("INVALID_STATE", "请在房态图按实际床位办理入住，不能仅修改迎新入住状态")


def mark_dorm_exception(sid, note) -> dict:
    if not note or len(note.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "异常说明必填且不少于 5 字")
    with session() as db:
        s = _get_student(db, sid)
        assert_orientation_student_scope(db, s)
        s.exception_note = note.strip()
        s.version += 1
        db.add(OrientationException(tenant_id=_tid(), ori_student_id=s.id, exception_type="DORM",
                                    description=note.strip(), risk_level="MEDIUM", status="OPEN",
                                    handler=_op()[0]))
        _audit(db, "DORM", s.id, "标记入住异常", note.strip())
        db.commit()
        return {"id": str(s.id)}


# ═══ 异常 ═══

def _exc_row(e: OrientationException, stu: OrientationStudent | None = None) -> dict:
    return {"id": str(e.id), "studentId": str(e.ori_student_id),
            "name": stu.name if stu else "", "className": stu.class_name if stu else "",
            "exceptionType": e.exception_type, "exceptionTypeLabel": L_EXCTYPE.get(e.exception_type, e.exception_type),
            "description": e.description or "", "riskLevel": e.risk_level,
            "riskLabel": L_RISK.get(e.risk_level, e.risk_level), "status": e.status,
            "statusLabel": L_EXCSTATUS.get(e.status, e.status), "handler": e.handler or "",
            "lastFollowTime": _iso(e.last_follow_time) or ""}


def create_exception(student_id, exception_type, description, risk_level="MEDIUM") -> dict:
    """通用异常登记入口（IDENTITY/PAYMENT/MATERIAL/DORM/NO_SHOW）；此前仅 mark_dorm_exception 一处能造数据，
    字典里定义的其余 4 种异常类型永远不会出现记录（异常识别名不副实）。"""
    etype = (exception_type or "").upper()
    if etype not in L_EXCTYPE:
        raise AppException("VALIDATION_ERROR", "异常类型非法")
    if not description or len(description.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "异常说明必填且不少于 5 字")
    level = (risk_level or "MEDIUM").upper()
    if level not in L_RISK:
        raise AppException("VALIDATION_ERROR", "风险等级非法")
    with session() as db:
        s = _get_student(db, student_id)
        e = OrientationException(tenant_id=_tid(), ori_student_id=s.id, exception_type=etype,
                                 description=description.strip(), risk_level=level, status="OPEN",
                                 handler=_op()[0])
        assert_orientation_student_scope(db, s)
        db.add(e)
        db.flush()
        _audit(db, "EXCEPTION", s.id, f"登记异常({etype})", description.strip())
        db.commit()
        db.refresh(e)
        return _exc_row(e, s)


def list_exceptions(page, page_size, keyword=None, exception_type=None, status=None, risk_level=None, batch_id=None):
    with session() as db:
        q = select(OrientationException, OrientationStudent).join(OrientationStudent,
            (OrientationStudent.id == OrientationException.ori_student_id)
            & (OrientationStudent.tenant_id == OrientationException.tenant_id)).where(
                OrientationException.tenant_id == _tid(), OrientationException.is_deleted.is_(False),
                OrientationStudent.is_deleted.is_(False))
        from app.core.affairs_security import student_directory_scope
        class_ids, student_ids = student_directory_scope(get_current_user_ctx() or {})
        if student_ids is not None:
            q = q.where(OrientationStudent.student_id.in_(student_ids) if student_ids else false())
        elif class_ids is not None:
            q = q.where(OrientationStudent.student_id.in_(select(StudentProfile.id).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                StudentProfile.class_id.in_(class_ids))) if class_ids else false())
        if batch_id is not None:
            q = q.where(OrientationStudent.batch_id == int(batch_id))
        if exception_type:
            q = q.where(OrientationException.exception_type == exception_type)
        if status:
            q = q.where(OrientationException.status == status)
        if risk_level:
            q = q.where(OrientationException.risk_level == risk_level)
        if keyword:
            q = q.where(OrientationStudent.name.contains(keyword.strip(), autoescape=True))
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.execute(q.order_by(OrientationException.id.desc())
            .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        return [_exc_row(e, stu) for e, stu in rows], total


def _scoped_exception(db, eid, *, for_update=False):
    q = select(OrientationException).where(OrientationException.id == int(eid),
        OrientationException.tenant_id == _tid(), OrientationException.is_deleted.is_(False))
    e = db.scalar(q.with_for_update() if for_update else q)
    if not e:
        raise not_found("异常记录不存在")
    student = _get_student(db, e.ori_student_id)
    assert_orientation_student_scope(db, student)
    return e, student


def get_exception_detail(eid) -> dict:
    with session() as db:
        e, stu = _scoped_exception(db, eid)
        fus = db.scalars(select(OrientationExceptionFollowup).where(
            OrientationExceptionFollowup.tenant_id == _tid(),
            OrientationExceptionFollowup.exception_id == e.id).order_by(
            OrientationExceptionFollowup.id.desc())).all()
        row = _exc_row(e, stu)
        row["followUps"] = [{"id": str(f.id), "followTime": _iso(f.follow_time), "way": f.way,
                             "content": f.content or "", "operator": f.operator or "",
                             "status": f.status} for f in fus]
        return {"exception": row, "student": _stu_row(stu) if stu else None}


def add_followup(eid, content, way="PHONE") -> dict:
    if not content or not content.strip():
        raise AppException("VALIDATION_ERROR", "跟进内容必填")
    with session() as db:
        e, _stu = _scoped_exception(db, eid, for_update=True)
        f = OrientationExceptionFollowup(tenant_id=_tid(), exception_id=e.id, way=way,
                                         content=content.strip(), operator=_op()[0], status="ACTIVE",
                                         follow_time=datetime.utcnow())
        db.add(f)
        if e.status == "OPEN":
            e.status = "PROCESSING"
        e.last_follow_time = datetime.utcnow()
        e.version += 1
        _audit(db, "EXCEPTION", e.id, "新增跟进", content.strip())
        db.commit()
        db.refresh(f)
        return {"id": str(f.id)}


def resolve_exception(eid, note="") -> dict:
    with session() as db:
        e, stu = _scoped_exception(db, eid, for_update=True)
        e.status = "RESOLVED"
        e.version += 1
        if stu and stu.risk_level == "HIGH":
            stu.risk_level = "MEDIUM"
        _audit(db, "EXCEPTION", e.id, "标记已处理", note)
        db.commit()
        return {"id": str(e.id), "status": "RESOLVED"}


def escalate_exception(eid, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "升级原因必填且不少于 5 字")
    with session() as db:
        e, stu = _scoped_exception(db, eid, for_update=True)
        e.status = "ESCALATED"
        e.risk_level = "HIGH"
        e.version += 1
        if stu:
            stu.risk_level = "HIGH"
        _audit(db, "EXCEPTION", e.id, "升级风险", reason.strip())
        db.commit()
        return {"id": str(e.id), "status": "ESCALATED"}


# ═══ 审计 ═══

def _log_row(x: OrientationAuditTrail) -> dict:
    return {"id": str(x.id), "time": _iso(x.occurred_at), "operator": x.operator or "",
            "roleName": x.role_name or "", "bizType": x.biz_type, "bizId": x.biz_id or "",
            "action": x.action, "detail": x.detail or "", "before": x.before_val or "",
            "after": x.after_val or ""}


def list_audit(page, page_size, biz_type=None, keyword=None):
    with session() as db:
        q = select(OrientationAuditTrail).where(OrientationAuditTrail.tenant_id == _tid())
        if biz_type:
            q = q.where(OrientationAuditTrail.biz_type == biz_type)
        rows = db.scalars(q.order_by(OrientationAuditTrail.id.desc())).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.action or "") or kw in (r.detail or "")]
        return _page([_log_row(r) for r in rows], page, page_size)


# ═══ 看板 ═══

def get_dashboard(user=None, batch_id=None) -> dict:
    with session() as db:
        batch_query = select(OrientationBatch).where(
            OrientationBatch.tenant_id == _tid(), OrientationBatch.is_deleted.is_(False),
        )
        if batch_id not in (None, ""):
            try:
                batch_query = batch_query.where(OrientationBatch.id == int(batch_id))
            except (TypeError, ValueError):
                raise AppException("VALIDATION_ERROR", "batchId 须为数字") from None
        else:
            batch_query = batch_query.order_by(
                case((OrientationBatch.status == "ACTIVE", 0), else_=1),
                OrientationBatch.id.desc(),
            )
        batch = db.scalars(batch_query.limit(1)).first()
        q = select(OrientationStudent).where(
            OrientationStudent.tenant_id == _tid(), OrientationStudent.is_deleted.is_(False),
            OrientationStudent.record_status == "ACTIVE",
            OrientationStudent.batch_id == (int(batch.id) if batch else -1),
        )
        from app.core.affairs_security import student_directory_scope
        class_ids, student_ids = student_directory_scope(user or get_current_user_ctx() or {})
        if student_ids is not None:
            q = q.where(OrientationStudent.student_id.in_(student_ids) if student_ids else false())
        elif class_ids is not None:
            q = q.where(OrientationStudent.student_id.in_(select(StudentProfile.id).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                StudentProfile.class_id.in_(class_ids or {-1}),
            )))
        rows = db.scalars(q.order_by(OrientationStudent.id)).all()
        scoped_ids = [int(row.id) for row in rows]
        total = len(rows)
        paid_ids = set(db.scalars(select(OrientationPaymentAccount.orientation_student_id).where(
            OrientationPaymentAccount.tenant_id == _tid(),
            OrientationPaymentAccount.orientation_student_id.in_(scoped_ids or [-1]),
            OrientationPaymentAccount.status.in_(("PAID", "WAIVED", "DEFERRED")),
            OrientationPaymentAccount.is_deleted.is_(False),
        )).all())
        paid_ids.update(db.scalars(select(GreenChannelApplication.ori_student_id).where(
            GreenChannelApplication.tenant_id == _tid(),
            GreenChannelApplication.ori_student_id.in_(scoped_ids or [-1]),
            GreenChannelApplication.status == "APPROVED",
            GreenChannelApplication.is_deleted.is_(False),
        )).all())
        paid = len(paid_ids)
        pending_gc = db.scalar(select(func.count()).select_from(GreenChannelApplication).where(
            GreenChannelApplication.tenant_id == _tid(),
            GreenChannelApplication.ori_student_id.in_(scoped_ids or [-1]),
            GreenChannelApplication.status.in_(["SUBMITTED", "REVIEWING"]),
            GreenChannelApplication.is_deleted.is_(False))) or 0
        pending_mat = db.scalar(select(func.count()).select_from(OrientationMaterial).where(
            OrientationMaterial.tenant_id == _tid(),
            OrientationMaterial.ori_student_id.in_(scoped_ids or [-1]),
            OrientationMaterial.is_current.is_(True), OrientationMaterial.status == "UPLOADED",
            OrientationMaterial.is_deleted.is_(False))) or 0
        open_exc = db.scalar(select(func.count()).select_from(OrientationException).where(
            OrientationException.tenant_id == _tid(),
            OrientationException.ori_student_id.in_(scoped_ids or [-1]),
            OrientationException.status.in_(["OPEN", "PROCESSING", "ESCALATED"]),
            OrientationException.is_deleted.is_(False))) or 0
        rate = lambda a, b: f"{(a / b * 100):.1f}%" if b else "0%"  # noqa: E731
        from app.models import OrientationCheckinRecord
        checked_in = int(db.scalar(select(func.count()).select_from(OrientationCheckinRecord).where(
            OrientationCheckinRecord.tenant_id == _tid(),
            OrientationCheckinRecord.orientation_student_id.in_(scoped_ids or [-1]),
            OrientationCheckinRecord.status == "CONFIRMED",
            OrientationCheckinRecord.is_deleted.is_(False),
        )) or 0)
        gc_total = db.scalar(select(func.count()).select_from(GreenChannelApplication).where(
            GreenChannelApplication.tenant_id == _tid(),
            GreenChannelApplication.ori_student_id.in_(scoped_ids or [-1]),
            GreenChannelApplication.is_deleted.is_(False))) or 0
        from app.models import OrientationFlowStep, OrientationStudentStep
        step_labels = {
            row.step_key: row.step_name
            for row in db.scalars(select(OrientationFlowStep).where(
                OrientationFlowStep.tenant_id == _tid(),
                OrientationFlowStep.flow_version_id == (int(batch.flow_version_id) if batch and batch.flow_version_id else -1),
                OrientationFlowStep.enabled.is_(True), OrientationFlowStep.is_deleted.is_(False),
            ).order_by(OrientationFlowStep.sort_order, OrientationFlowStep.id)).all()
        }
        steps = db.scalars(select(OrientationStudentStep).where(
            OrientationStudentStep.tenant_id == _tid(),
            OrientationStudentStep.orientation_student_id.in_(scoped_ids or [-1]),
            OrientationStudentStep.is_deleted.is_(False),
        ).order_by(OrientationStudentStep.flow_step_id, OrientationStudentStep.id)).all()
        prepared_ids = {
            int(step.orientation_student_id) for step in steps
            if step.step_key == "INFO" and step.status in ("DONE", "WAIVED", "NOT_REQUIRED")
        }
        prepared = len(prepared_ids)
        funnel = {}
        for step in steps:
            item = funnel.setdefault(step.step_key, {
                "key": step.step_key, "label": step_labels.get(step.step_key, step.step_key), "done": 0,
            })
            if step.status in ("DONE", "WAIVED", "NOT_REQUIRED"):
                item["done"] += 1
        step_funnel = list(funnel.values())
        start = (batch.report_start_date or batch.start_date) if batch else None
        end = (batch.report_end_date or batch.end_date) if batch else None
        return {
            "batchId": str(batch.id) if batch else "",
            "batchName": batch.batch_name if batch else "当前无迎新批次",
            "batchPeriod": f"{start:%Y-%m-%d} ~ {end:%Y-%m-%d}" if start and end else "未配置报到周期",
            "updateTime": _iso(datetime.now()),
            "kpis": [
                {"key": "total", "label": "新生总数", "value": str(total), "trend": "", "trendQuality": "neutral"},
                {"key": "prepared", "label": "预报到完成", "value": str(prepared),
                 "trend": rate(prepared, total), "trendQuality": "good"},
                {"key": "checkedIn", "label": "已现场报到", "value": str(checked_in),
                 "trend": f"已报到 {checked_in}", "trendQuality": "good"},
                {"key": "paidRate", "label": "缴费完成率", "value": rate(paid, total),
                 "trend": f"已完成 {paid}", "trendQuality": "good"},
                {"key": "greenChannel", "label": "绿色通道申请", "value": str(gc_total),
                 "trend": f"{pending_gc} 待审", "trendQuality": "neutral"},
                {"key": "exception", "label": "迎新异常", "value": str(open_exc),
                 "trend": f"待处理 {open_exc}", "trendQuality": "bad" if open_exc else "good"},
            ],
            "todos": [
                {"id": "t1", "label": "待审绿色通道", "value": pending_gc, "link": "/admin/orientation/payment"},
                {"id": "t2", "label": "待审材料", "value": pending_mat, "link": "/admin/orientation/materials"},
                {"id": "t3", "label": "待处理异常", "value": open_exc, "link": "/admin/orientation/exceptions"},
            ],
            "riskAlerts": [], "flow": [], "stepFunnel": step_funnel, "collegeRates": [],
        }


# ═══ 迎新批次（组织时间轴 + 状态机 DRAFT→ACTIVE→CLOSED） ═══

L_BATCH = {"DRAFT": "草稿", "ACTIVE": "进行中", "CLOSED": "已结束"}


def _parse_dt(v):
    if not v:
        return None
    s = str(v).strip().replace("Z", "").replace("/", "-")
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:19])
    except ValueError:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None


def _batch_row(b: OrientationBatch) -> dict:
    return {
        "id": str(b.id), "batchName": b.batch_name, "batchNo": b.batch_no, "year": b.year or "",
        "startDate": _iso(b.start_date) or "", "endDate": _iso(b.end_date) or "",
        "reportStartDate": _iso(b.report_start_date) or "", "reportEndDate": _iso(b.report_end_date) or "",
        "status": b.status, "statusLabel": L_BATCH.get(b.status, b.status),
        "flowVersionId": str(b.flow_version_id) if b.flow_version_id else "",
        "plannedCount": int(b.planned_count or 0), "remark": b.remark or "",
        "updateTime": _iso(b.updated_at),
    }


def _get_batch(db, bid) -> OrientationBatch:
    b = db.get(OrientationBatch, int(bid))
    if not b or b.is_deleted or b.tenant_id != _tid():
        raise not_found("迎新批次不存在或不在当前数据范围内")
    return b


def list_batches(page, page_size, keyword=None, status=None):
    with session() as db:
        q = select(OrientationBatch).where(OrientationBatch.tenant_id == _tid(),
                                           OrientationBatch.is_deleted.is_(False))
        if status:
            q = q.where(OrientationBatch.status == status)
        rows = db.scalars(q.order_by(OrientationBatch.id.desc())).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.batch_name or "") or kw in (r.batch_no or "")]
        items, total = _page([_batch_row(r) for r in rows], page, page_size)
        return items, total


def get_batch(bid) -> dict:
    with session() as db:
        return _batch_row(_get_batch(db, bid))


def create_batch(body: dict) -> dict:
    name = str(body.get("batchName") or "").strip()
    no = str(body.get("batchNo") or "").strip()
    if not name or not no:
        raise AppException("VALIDATION_ERROR", "批次名称与批次编号必填")
    with session() as db:
        dup = db.scalars(select(OrientationBatch).where(
            OrientationBatch.tenant_id == _tid(), OrientationBatch.batch_no == no,
            OrientationBatch.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", f"批次编号 {no} 已存在")
        b = OrientationBatch(
            tenant_id=_tid(), batch_name=name, batch_no=no, year=body.get("year"),
            start_date=_parse_dt(body.get("startDate")), end_date=_parse_dt(body.get("endDate")),
            report_start_date=_parse_dt(body.get("reportStartDate")),
            report_end_date=_parse_dt(body.get("reportEndDate")),
            planned_count=int(body.get("plannedCount") or 0), remark=body.get("remark"), status="DRAFT")
        db.add(b)
        db.flush()
        _audit(db, "BATCH", b.id, "新建迎新批次", f"{name}（{no}）")
        db.commit()
        return {"id": str(b.id)}


def update_batch(bid, body: dict) -> dict:
    with session() as db:
        b = _get_batch(db, bid)
        if b.status == "CLOSED":
            raise AppException("INVALID_STATE", "已结束的批次不可编辑")
        for k, col in {"batchName": "batch_name", "year": "year", "remark": "remark"}.items():
            if body.get(k) is not None:
                setattr(b, col, body[k])
        for k, col in {"startDate": "start_date", "endDate": "end_date",
                       "reportStartDate": "report_start_date", "reportEndDate": "report_end_date"}.items():
            if body.get(k) is not None:
                setattr(b, col, _parse_dt(body[k]))
        if body.get("plannedCount") is not None:
            b.planned_count = int(body["plannedCount"] or 0)
        b.version += 1
        _audit(db, "BATCH", b.id, "编辑迎新批次")
        db.commit()
        return {"id": str(b.id)}


def activate_batch(bid) -> dict:
    with session() as db:
        b = _get_batch(db, bid)
        if b.status != "DRAFT":
            raise AppException("INVALID_STATE", "仅草稿批次可启用")
        if not b.flow_version_id:
            b.flow_version_id = ensure_published_flow_version(db, b.tenant_id).id
        b.status = "ACTIVE"
        b.version += 1
        _audit(db, "BATCH", b.id, "启用迎新批次", before="DRAFT", after="ACTIVE")
        db.commit()
        return {"id": str(b.id), "status": b.status}


def assign_batch_student_numbers(bid, body: dict) -> dict:
    """Assign up to 20k reserved student numbers in one transaction; never requires per-row clicks."""
    prefix = str((body or {}).get("prefix") or "").strip().upper()
    try:
        start = int((body or {}).get("startNumber") or 1)
        width = int((body or {}).get("width") or 6)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "起始序号和序号位数必须是整数")
    dry_run = bool((body or {}).get("dryRun", False))
    if not re.fullmatch(r"[A-Z0-9-]{1,30}", prefix):
        raise AppException("VALIDATION_ERROR", "学号前缀仅支持 1-30 位字母、数字或短横线")
    if start < 0 or start > 999_999_999 or width < 4 or width > 10:
        raise AppException("VALIDATION_ERROR", "起始序号须为非负整数，序号位数须为 4-10 位")
    with session() as db:
        batch = _get_batch(db, bid)
        rows = list(db.scalars(select(OrientationStudent).where(
            OrientationStudent.tenant_id == _tid(),
            OrientationStudent.batch_id == batch.id,
            or_(OrientationStudent.student_no.is_(None), OrientationStudent.student_no == ""),
            OrientationStudent.record_status == "ACTIVE",
            OrientationStudent.is_deleted.is_(False),
        ).order_by(OrientationStudent.id).with_for_update()).all())
        if len(rows) > 20_000:
            raise AppException("VALIDATION_ERROR", "单批次最多自动编制 20000 个学号")
        numbers = [f"{prefix}{start + index:0{width}d}" for index in range(len(rows))]
        if any(len(number) > 50 for number in numbers):
            raise AppException("VALIDATION_ERROR", "生成后的学号长度不能超过 50 位")
        collisions: set[str] = set()
        if numbers:
            collisions |= set(db.scalars(select(OrientationStudent.student_no).where(
                OrientationStudent.tenant_id == _tid(),
                OrientationStudent.student_no.in_(numbers),
            )).all())
            collisions |= set(db.scalars(select(StudentProfile.student_no).where(
                StudentProfile.tenant_id == _tid(),
                StudentProfile.student_no.in_(numbers),
            )).all())
            collisions |= set(db.scalars(select(User.login_name).where(
                User.tenant_id == _tid(), User.login_name.in_(numbers),
                User.is_deleted.is_(False),
            )).all())
        if collisions:
            sample = sorted(value for value in collisions if value)[:10]
            raise AppException(
                "DATA_CONFLICT", "拟生成的学号已被占用，请调整前缀或起始序号",
                details={"collisionSample": sample, "collisionCount": len(collisions)},
            )
        result = {
            "batchId": str(batch.id), "missingCount": len(rows),
            "assignedCount": 0 if dry_run else len(rows),
            "sample": numbers[:5], "dryRun": dry_run,
        }
        if dry_run:
            return result
        for row, number in zip(rows, numbers):
            row.student_no = number
            row.version = int(row.version or 0) + 1
        # Bulk roster readiness is one operation: every candidate in the batch must
        # receive the frozen canonical step rows, including candidates that already
        # had a student number before this assignment.
        initialize_batch_student_steps(db, batch.id, status_source="PROCESS_FACT")
        _audit(
            db, "BATCH", batch.id, "批量自动编制新生学号",
            f"count={len(rows)}; prefix={prefix}; start={start}; width={width}",
        )
        db.commit()
        return result


def close_batch(bid) -> dict:
    with session() as db:
        b = _get_batch(db, bid)
        if b.status != "ACTIVE":
            raise AppException("INVALID_STATE", "仅进行中批次可结束")
        pending = db.scalar(select(func.count()).select_from(OrientationStudent).where(
            OrientationStudent.tenant_id == _tid(), OrientationStudent.batch_id == b.id,
            OrientationStudent.is_deleted.is_(False), OrientationStudent.record_status == "ACTIVE",
            OrientationStudent.stage.not_in(["ENROLLED", "NO_SHOW", "CANCELLED"]))) or 0
        if pending:
            raise AppException("INVALID_STATE", f"仍有 {pending} 名新生未办结，请先完成入学确认或处理未到校事项")
        b.status = "CLOSED"
        b.version += 1
        _audit(db, "BATCH", b.id, "结束迎新批次", before="ACTIVE", after="CLOSED")
        db.commit()
        return {"id": str(b.id), "status": b.status}


def delete_batch(bid, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        b = _get_batch(db, bid)
        if b.status == "ACTIVE":
            raise AppException("INVALID_STATE", "进行中的批次不可作废，请先结束")
        b.is_deleted = True
        b.version += 1
        _audit(db, "BATCH", b.id, "作废迎新批次", reason.strip())
        db.commit()
        return {"id": str(b.id)}


# ═══ 现场报到点 ═══

L_POINT = {"ENABLED": "启用", "DISABLED": "停用"}


def _point_row(p):
    return {"id": str(p.id), "name": p.name, "location": p.location or "",
            "capacity": int(p.capacity or 0), "inCharge": p.in_charge or "",
            "status": p.status, "statusLabel": L_POINT.get(p.status, p.status),
            "remark": p.remark or "", "updateTime": _iso(p.updated_at)}


def _get_point(db, pid):
    p = db.get(OrientationCheckinPoint, int(pid))
    if not p or p.is_deleted or p.tenant_id != _tid():
        raise not_found("报到点不存在或不在当前数据范围内")
    return p


def list_checkin_points(page, page_size, keyword=None, status=None):
    with session() as db:
        q = select(OrientationCheckinPoint).where(OrientationCheckinPoint.tenant_id == _tid(),
                                                  OrientationCheckinPoint.is_deleted.is_(False))
        if status:
            q = q.where(OrientationCheckinPoint.status == status)
        rows = db.scalars(q.order_by(OrientationCheckinPoint.id.desc())).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.name or "") or kw in (r.location or "")]
        items, total = _page([_point_row(r) for r in rows], page, page_size)
        return items, total


def create_checkin_point(body):
    name = str(body.get("name") or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "报到点名称必填")
    with session() as db:
        p = OrientationCheckinPoint(tenant_id=_tid(), name=name, location=body.get("location"),
                                    capacity=int(body.get("capacity") or 0), in_charge=body.get("inCharge"),
                                    status="ENABLED", remark=body.get("remark"))
        db.add(p)
        db.flush()
        _audit(db, "CHECKIN_POINT", p.id, "新增报到点", name)
        db.commit()
        return {"id": str(p.id)}


def update_checkin_point(pid, body):
    with session() as db:
        p = _get_point(db, pid)
        for k, col in {"name": "name", "location": "location", "inCharge": "in_charge", "remark": "remark"}.items():
            if body.get(k) is not None:
                setattr(p, col, body[k])
        if body.get("capacity") is not None:
            p.capacity = int(body["capacity"] or 0)
        p.version += 1
        _audit(db, "CHECKIN_POINT", p.id, "编辑报到点")
        db.commit()
        return {"id": str(p.id)}


def toggle_checkin_point(pid):
    with session() as db:
        p = _get_point(db, pid)
        p.status = "DISABLED" if p.status == "ENABLED" else "ENABLED"
        p.version += 1
        _audit(db, "CHECKIN_POINT", p.id, "切换报到点状态", after=p.status)
        db.commit()
        return {"id": str(p.id), "status": p.status}


def delete_checkin_point(pid):
    with session() as db:
        p = _get_point(db, pid)
        p.is_deleted = True
        p.version += 1
        _audit(db, "CHECKIN_POINT", p.id, "删除报到点")
        db.commit()
        return {"id": str(p.id)}


# ═══ 报到流程配置 ═══

def _flow_row(f):
    return {"id": str(f.id), "stepKey": f.step_key, "stepName": f.step_name,
            "enabled": bool(f.enabled), "required": bool(f.required),
            "sortOrder": int(f.sort_order or 0), "remark": f.remark or ""}


def _ensure_flow_seed(db):
    exists = db.scalar(select(func.count()).select_from(OrientationFlowConfig).where(
        OrientationFlowConfig.tenant_id == _tid())) or 0
    if exists:
        return
    for i, s in enumerate(REGISTRATION_STEPS):
        db.add(OrientationFlowConfig(tenant_id=_tid(), step_key=s["key"], step_name=s["label"],
                                     enabled=True, required=True, sort_order=i))
    db.commit()


def list_flow_config():
    with session() as db:
        _ensure_flow_seed(db)
        rows = db.scalars(select(OrientationFlowConfig).where(
            OrientationFlowConfig.tenant_id == _tid(),
            OrientationFlowConfig.is_deleted.is_(False)).order_by(OrientationFlowConfig.sort_order)).all()
        return [_flow_row(r) for r in rows]


def update_flow_config(fid, body):
    with session() as db:
        f = db.get(OrientationFlowConfig, int(fid))
        if not f or f.is_deleted or f.tenant_id != _tid():
            raise not_found("流程环节不存在")
        if body.get("enabled") is not None:
            f.enabled = bool(body["enabled"])
        if body.get("required") is not None:
            f.required = bool(body["required"])
        if body.get("remark") is not None:
            f.remark = body["remark"]
        f.version += 1
        _audit(db, "FLOW_CONFIG", f.id, "调整流程环节", detail=f.step_name)
        db.commit()
        return {"id": str(f.id), "enabled": bool(f.enabled)}


# ═══ 迎新通知（本轮不接真实短信/邮件：仅站内渠道已配置，其余显示未配置） ═══

L_NOTICE = {"PENDING": "待发送", "SENT": "已发送", "FAILED": "发送失败", "DISABLED": "渠道未配置"}
L_CHANNEL = {"INAPP": "站内通知", "SMS": "短信", "EMAIL": "邮件", "MINIAPP": "小程序"}
CONFIGURED_CHANNELS = {"INAPP"}


def _notice_row(n):
    return {"id": str(n.id), "title": n.title, "content": n.content or "",
            "channel": n.channel, "channelLabel": L_CHANNEL.get(n.channel, n.channel),
            "targetScope": n.target_scope or "", "status": n.status,
            "statusLabel": L_NOTICE.get(n.status, n.status), "failReason": n.fail_reason or "",
            "sentCount": int(n.sent_count or 0), "updateTime": _iso(n.updated_at)}


def list_notice_tasks(page, page_size, keyword=None, status=None, channel=None):
    with session() as db:
        q = select(OrientationNoticeTask).where(OrientationNoticeTask.tenant_id == _tid(),
                                                OrientationNoticeTask.is_deleted.is_(False))
        if status:
            q = q.where(OrientationNoticeTask.status == status)
        if channel:
            q = q.where(OrientationNoticeTask.channel == channel)
        rows = db.scalars(q.order_by(OrientationNoticeTask.id.desc())).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.title or "")]
        items, total = _page([_notice_row(r) for r in rows], page, page_size)
        return items, total


def create_notice_task(body):
    title = str(body.get("title") or "").strip()
    if not title:
        raise AppException("VALIDATION_ERROR", "通知标题必填")
    with session() as db:
        n = OrientationNoticeTask(tenant_id=_tid(), title=title, content=body.get("content"),
                                  channel=body.get("channel") or "INAPP",
                                  target_scope=body.get("targetScope"), status="PENDING")
        db.add(n)
        db.flush()
        _audit(db, "NOTICE", n.id, "新建迎新通知", title)
        db.commit()
        return {"id": str(n.id)}


def send_notice_task(nid):
    with session() as db:
        n = db.get(OrientationNoticeTask, int(nid))
        if not n or n.is_deleted or n.tenant_id != _tid():
            raise not_found("通知任务不存在")
        if n.status == "SENT":
            raise AppException("INVALID_STATE", "该通知已发送")
        if n.channel not in CONFIGURED_CHANNELS:
            n.status = "DISABLED"
            n.fail_reason = f"{L_CHANNEL.get(n.channel, n.channel)}渠道未配置，请先在系统管理接入"
            _audit(db, "NOTICE", n.id, "发送失败（渠道未配置）", detail=n.channel)
        else:
            n.status = "SENT"
            n.sent_count = 1
            n.fail_reason = ""
            _audit(db, "NOTICE", n.id, "发送站内通知", after="SENT")
        n.version += 1
        db.commit()
        return {"id": str(n.id), "status": n.status, "failReason": n.fail_reason or ""}


# ═══ 迎新归档 ═══

L_ARCHIVE = {"PENDING": "待归档", "DONE": "已归档"}


def _archive_row(a):
    return {"id": str(a.id), "archiveName": a.archive_name, "batchNo": a.batch_no or "",
            "scope": a.scope or "", "status": a.status, "statusLabel": L_ARCHIVE.get(a.status, a.status),
            "itemCount": int(a.item_count or 0), "archivedBy": a.archived_by or "",
            "archivedAt": _iso(a.archived_at) or "", "remark": a.remark or "", "updateTime": _iso(a.updated_at)}


def list_archives(page, page_size, keyword=None, status=None):
    with session() as db:
        q = select(OrientationArchive).where(OrientationArchive.tenant_id == _tid(),
                                             OrientationArchive.is_deleted.is_(False))
        if status:
            q = q.where(OrientationArchive.status == status)
        rows = db.scalars(q.order_by(OrientationArchive.id.desc())).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.archive_name or "")]
        items, total = _page([_archive_row(r) for r in rows], page, page_size)
        return items, total


def _archive_scope(db):
    from app.core.affairs_security import build_affairs_context, no_data_scope
    ctx = build_affairs_context(get_current_user_ctx() or {}, db)
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("批次归档需由学校迎新管理人员办理")


def _archive_batch(db, batch_no):
    batch = db.scalars(select(OrientationBatch).where(
        OrientationBatch.tenant_id == _tid(), OrientationBatch.is_deleted.is_(False),
        OrientationBatch.batch_no == str(batch_no or "").strip(),
    )).first()
    if not batch:
        raise AppException("VALIDATION_ERROR", "请选择有效的迎新批次")
    return batch


def create_archive(body):
    name = str(body.get("archiveName") or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "归档名称必填")
    with session() as db:
        _archive_scope(db)
        batch = _archive_batch(db, body.get("batchNo"))
        a = OrientationArchive(tenant_id=_tid(), archive_name=name, batch_no=batch.batch_no,
                               scope="本批次", status="PENDING", remark=body.get("remark"))
        db.add(a)
        db.flush()
        _audit(db, "ARCHIVE", a.id, "新建归档任务", name)
        db.commit()
        return {"id": str(a.id)}


def run_archive(aid):
    from app.services.dorm_housing_projection import housing_map
    with session() as db:
        _archive_scope(db)
        a = db.scalars(select(OrientationArchive).where(
            OrientationArchive.id == int(aid), OrientationArchive.tenant_id == _tid(),
            OrientationArchive.is_deleted.is_(False)).with_for_update()).first()
        if not a:
            raise not_found("归档任务不存在")
        if a.status == "DONE":
            return {"id": str(a.id), "status": a.status, "itemCount": a.item_count}
        batch = _archive_batch(db, a.batch_no)
        if batch.status != "CLOSED":
            raise AppException("INVALID_STATE", "请先办结新生事项并关闭迎新批次，再执行归档")
        rows = db.scalars(select(OrientationStudent).where(
            OrientationStudent.tenant_id == _tid(), OrientationStudent.is_deleted.is_(False),
            OrientationStudent.batch_id == batch.id, OrientationStudent.record_status == "ACTIVE",
        ).with_for_update()).all()
        pending = sum(r.stage not in ("ENROLLED", "NO_SHOW", "CANCELLED") for r in rows)
        if pending:
            raise AppException("INVALID_STATE", f"本批次仍有 {pending} 名新生未办结，请先确认入学或处理未到校事项")
        facts = housing_map(db, [r.student_id for r in rows])
        for r in rows:
            snapshot = {"orientationStudentId": str(r.id), "profileStudentId": str(r.student_id or ""),
                        "name": r.name, "admissionNo": r.admission_no, "stage": r.stage,
                        "reportStatus": r.report_status, "paymentStatus": r.payment_status,
                        "materialStatus": r.material_status, "version": r.version,
                        "housingStatus": facts.get(int(r.student_id or 0), {}).get("housingStatus", "UNLINKED")}
            _audit(db, "ARCHIVE_ITEM", a.id, "新生归档快照", json.dumps(snapshot, ensure_ascii=False))
        name, _role = _op()
        a.status, a.item_count, a.archived_by = "DONE", len(rows), name
        a.archived_at = datetime.utcnow()
        a.version += 1
        _audit(db, "ARCHIVE", a.id, "执行归档", after="DONE", detail=f"批次 {batch.batch_no}，归档 {len(rows)} 名新生")
        db.commit()
        return {"id": str(a.id), "status": a.status, "itemCount": len(rows)}


def archive_items(aid, page, page_size):
    with session() as db:
        _archive_scope(db)
        archive = tenant_get(db, OrientationArchive, int(aid))
        if not archive:
            raise not_found("归档任务不存在")
        q = select(OrientationAuditTrail).where(OrientationAuditTrail.tenant_id == _tid(),
            OrientationAuditTrail.biz_type == "ARCHIVE_ITEM", OrientationAuditTrail.biz_id == str(aid))
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.scalars(q.order_by(OrientationAuditTrail.id).offset((page - 1) * page_size).limit(page_size)).all()
        return [dict(json.loads(r.detail), id=str(r.id), archivedAt=_iso(r.occurred_at)) for r in rows], total
