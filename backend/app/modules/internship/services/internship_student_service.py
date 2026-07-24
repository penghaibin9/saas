"""岗位实习中心 · 实习学生服务（生产级，DB_ENABLED=true 走本模块）。

核心：把实习学生记录 t_internship_record 与企业库(t_emp_company)/岗位库(t_internship_position)真实打通——
学生-岗位分配闭环让岗位库 allocated_count 变为真实值，并落地「满员不可再分配 / 黑名单·未上架岗位不可分配」。
再叠加 学生实习状态机 + 实习资格 + 实习去向 + 统计 + 导入导出。
横切：租户隔离 + is_deleted 软删 + 手机号脱敏 + 审计到 t_internship_audit_trail(target_type=INTERN_STUDENT)。
数据范围（预留）：默认按租户；辅导员/指导教师限本班/本人指导，接 resolve_teacher_scope。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (EmpCompany, InternshipAgreement, InternshipAuditTrail, InternshipBatch,
                        InternshipInsurance, InternshipPosition, InternshipRecord,
                        Role, StudentContact, StudentProfile, User, UserRole)
from app.services.db_service import _as_id, _iso, _mask_phone, _tid, session

STATUS_LABEL = {"PREPARING": "准备中", "READY": "待上岗", "ONBOARD": "在岗中",
                "ASSESSING": "考核中", "ARCHIVED": "已归档"}
STATUS_TONE = {"PREPARING": "default", "READY": "warning", "ONBOARD": "success",
               "ASSESSING": "primary", "ARCHIVED": "default"}
RISK_LABEL = {"NONE": "无", "LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}
ELIG_LABEL = {"PENDING": "待认定", "QUALIFIED": "资格合格", "UNQUALIFIED": "资格不合格"}
DEST_LABEL = {"NONE": "未落实", "ASSIGNED": "已分配岗位", "SELF_ARRANGED": "自主实习", "EXEMPTED": "免实习"}
ADVISOR_ROLE_CODES = ("INTERN_MENTOR", "INTERNSHIP_MENTOR")


def _op_name() -> str:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统"


def _trail(db, rec_id: int, action: str, detail: dict | None = None):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=rec_id, target_type="INTERN_STUDENT",
                                action=action, operator_name=_op_name(), detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _get(db, rec_id) -> InternshipRecord:
    r = db.get(InternshipRecord, _as_id(rec_id))
    if not r or r.is_deleted or r.tenant_id != _tid():
        raise not_found("实习学生记录不存在或不在当前数据范围内")
    return r


def _assert_write_scope(db, r: InternshipRecord, user) -> None:
    """写操作数据范围校验：越出教师数据范围的写 → 403（与详情读 get_student 同边界）。
    ADMIN_TENANT（校级管理员）恒通过；SCOPED（指导教师/学院负责人）按本人指导/本院收敛。
    _current_scope / _rec_in_scope 在本模块下方定义，调用时已就绪（Python 运行期解析）。"""
    stu = db.get(StudentProfile, r.student_id)
    if not _rec_in_scope(_current_scope(user), db, r, stu):
        from app.core.exceptions import no_permission
        raise no_permission("该实习学生不在你的数据范围内")


def _students_map(db, ids: list[int]) -> dict:
    if not ids:
        return {}
    rows = db.scalars(select(StudentProfile).where(StudentProfile.id.in_(ids))).all()
    return {s.id: s for s in rows}


def _advisor_role_user_ids(db) -> set[int]:
    """岗位实习指导教师必须同时具有有效账号和有效带教角色。"""
    rows = db.scalars(select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(
        UserRole.tenant_id == _tid(), UserRole.is_deleted.is_(False), UserRole.status == "ACTIVE",
        Role.tenant_id == _tid(), Role.is_deleted.is_(False), Role.status == "ACTIVE",
        Role.role_code.in_(ADVISOR_ROLE_CODES))).all()
    return {int(value) for value in rows}


def _advisor(db, advisor_user_id=None, advisor_name=None) -> User | None:
    """Resolve a new advisor to one active staff account; names remain display-only compatibility input."""
    if advisor_user_id:
        row = db.get(User, _as_id(advisor_user_id))
        if not row or row.is_deleted or row.tenant_id != _tid() or row.status != "ACTIVE":
            raise not_found("指导教师账号不存在、已停用或不在当前租户")
        if row.user_type not in ("TEACHER", "STAFF", "SCHOOL_ADMIN", "ADMIN"):
            raise AppException("VALIDATION_ERROR", "所选账号不是教职工，不能担任实习指导教师")
        if row.id not in _advisor_role_user_ids(db):
            raise AppException("VALIDATION_ERROR", "所选教师尚未分配“岗位实习指导教师”角色")
        return row
    name = (advisor_name or "").strip()
    if not name:
        return None
    eligible_ids = _advisor_role_user_ids(db)
    rows = db.scalars(select(User).where(
        User.tenant_id == _tid(), User.real_name == name, User.status == "ACTIVE",
        User.id.in_(eligible_ids),
        User.user_type.in_(("TEACHER", "STAFF", "SCHOOL_ADMIN", "ADMIN")),
        User.is_deleted.is_(False))).all()
    if len(rows) != 1:
        raise AppException("VALIDATION_ERROR", "指导教师必须匹配唯一的在职岗位实习指导教师账号")
    return rows[0]


def list_advisors(keyword: str | None = None) -> list[dict]:
    with session() as db:
        eligible_ids = _advisor_role_user_ids(db)
        q = select(User).where(User.tenant_id == _tid(), User.is_deleted.is_(False),
                               User.status == "ACTIVE",
                               User.id.in_(eligible_ids),
                               User.user_type.in_(("TEACHER", "STAFF", "SCHOOL_ADMIN", "ADMIN")))
        if keyword:
            like = f"%{keyword.strip()}%"
            q = q.where((User.real_name.like(like)) | (User.login_name.like(like)))
        rows = db.scalars(q.order_by(User.real_name, User.id).limit(200)).all()
        return [{"id": str(u.id), "name": u.real_name, "loginName": u.login_name,
                 "userType": u.user_type} for u in rows]


def list_assignment_logs(page: int, page_size: int, keyword: str | None = None, user=None) -> tuple[list[dict], int]:
    """Assignment-only audit ledger, filtered by the same record scope as the student list."""
    actions = ("ASSIGN_ADVISOR", "ASSIGN_POSITION", "UNASSIGN_POSITION")
    with session() as db:
        logs = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(),
            InternshipAuditTrail.target_type == "INTERN_STUDENT",
            InternshipAuditTrail.action.in_(actions)).order_by(InternshipAuditTrail.id.desc())).all()
        from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
        scope = _current_scope(user)
        items = []
        needle = (keyword or "").strip().lower()
        for log in logs:
            rec = db.get(InternshipRecord, log.target_id)
            stu = db.get(StudentProfile, rec.student_id) if rec else None
            if not rec or not stu or not _rec_in_scope(scope, db, rec, stu):
                continue
            row = {"id": str(log.id), "recordId": str(rec.id), "studentName": stu.real_name,
                   "studentNo": stu.student_no, "action": log.action,
                   "operator": log.operator_name or "系统", "detail": log.detail_json or {},
                   "occurredAt": _iso(log.occurred_at) or ""}
            if needle and needle not in (row["studentName"] + row["studentNo"] + row["action"] + row["operator"]).lower():
                continue
            items.append(row)
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


# ═══════════ 数据范围（P0-D：管理端按教师范围收敛，不仅租户） ═══════════

def _current_scope(user: dict | None = None) -> dict:
    """教师数据范围。user 由 API 层显式传入（FastAPI 同步端点在独立线程上下文，contextvar 不可靠传播，
    故不能只依赖 get_current_user_ctx）；懒加载 resolve_teacher_scope 避免与 mobile_teacher_service 循环 import。
    ADMIN_TENANT（明确的校级业务管理员）→ 看全校；SCOPED（指导教师/学院负责人/辅导员）
    按关系收敛；无范围信息保持空范围并默认拒绝。"""
    from app.services.mobile_teacher_service import resolve_teacher_scope
    return resolve_teacher_scope(user or get_current_user_ctx() or {})


def _rec_in_scope(scope: dict, db, r: InternshipRecord, stu) -> bool:
    """实习记录是否在教师数据范围内。复用 internship_service 统一推导（含缺 college_id）。"""
    if scope.get("mode") != "SCOPED":
        return True
    from app.modules.internship.services.internship_service import (
        resolve_student_class_college_names)
    from app.services.mobile_teacher_service import scope_match_row
    class_name, college_name = resolve_student_class_college_names(db, stu)
    return scope_match_row(scope, student_no=(stu.student_no if stu else None),
                           class_name=class_name, advisor_name=r.advisor_name,
                           college_name=college_name, advisor_user_id=r.advisor_user_id)


def _row(r: InternshipRecord, stu: StudentProfile | None, batch_name: str = "",
         class_name: str | None = None) -> dict:
    return {
        "id": str(r.id), "studentId": str(r.student_id),
        "name": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "className": class_name or "-",
        "classId": str(stu.class_id) if stu and stu.class_id else "",
        "batchId": str(r.batch_id) if r.batch_id else "",
        # BUG-009：同一学生跨批次会有多条实习记录，下拉必须能靠批次名区分
        "batchName": batch_name or "",
        "enterpriseId": str(r.enterprise_id) if r.enterprise_id else "",
        "enterpriseName": r.enterprise_name or "",
        "positionId": str(r.position_id) if r.position_id else "",
        "positionName": r.position_name or "",
        "mentorContactId": str(r.mentor_contact_id) if r.mentor_contact_id else "",
        "mentorName": r.enterprise_mentor_name or "", "advisorName": r.advisor_name or "",
        "advisorUserId": str(r.advisor_user_id) if r.advisor_user_id else "",
        "status": r.status, "statusLabel": STATUS_LABEL.get(r.status, r.status),
        "statusTone": STATUS_TONE.get(r.status, "default"),
        "riskLevel": r.risk_level, "riskLabel": RISK_LABEL.get(r.risk_level, r.risk_level),
        "eligibilityStatus": r.eligibility_status,
        "eligibilityLabel": ELIG_LABEL.get(r.eligibility_status, r.eligibility_status),
        "destinationType": r.destination_type,
        "destinationLabel": DEST_LABEL.get(r.destination_type, r.destination_type),
        "internRange": (f"{_iso(r.intern_start_date)[:10]} ~ {_iso(r.intern_end_date)[:10]}"
                        if r.intern_start_date and r.intern_end_date else ""),
        "updatedAt": _iso(r.updated_at),
    }


def _batch_names(db, batch_ids) -> dict:
    """批量取批次名（消 N+1），用于列表/下拉区分同一学生的跨批次记录。"""
    ids = {b for b in batch_ids if b}
    if not ids:
        return {}
    rows = db.scalars(select(InternshipBatch).where(InternshipBatch.id.in_(ids))).all()
    return {b.id: b.batch_name or "" for b in rows}


def _row_of(db, r: InternshipRecord) -> dict:
    from app.modules.internship.services.internship_service import resolve_student_class_college_names
    batch_name = ""
    if r.batch_id:
        b = db.get(InternshipBatch, r.batch_id)
        batch_name = (b.batch_name or "") if b else ""
    stu = db.get(StudentProfile, r.student_id)
    class_name, _ = resolve_student_class_college_names(db, stu)
    return _row(r, stu, batch_name, class_name=class_name)


# ═══════════ 列表 / 详情 ═══════════

def _collect_scoped_records(db, *, batch_id, keyword=None, class_id=None, status=None,
                            risk_level=None, eligibility=None, destination=None,
                            has_position=None, user=None) -> list[InternshipRecord]:
    """列表 / 统计 / 导出共用过滤：tenant + batch_id(SQL) + 业务筛选 + 数据范围。

    缺少或非法 batchId 一律拒绝，禁止静默回退到全历史。
    """
    from app.modules.internship.services.internship_batch_context import resolve_batch
    batch = resolve_batch(db, batch_id, for_write=False)
    q = select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.is_deleted.is_(False),
        InternshipRecord.batch_id == batch.id,
    )
    if status:
        q = q.where(InternshipRecord.status == status)
    if risk_level:
        q = q.where(InternshipRecord.risk_level == risk_level)
    if eligibility:
        q = q.where(InternshipRecord.eligibility_status == eligibility)
    if destination:
        q = q.where(InternshipRecord.destination_type == destination)
    if has_position is True:
        q = q.where(InternshipRecord.position_id.is_not(None))
    elif has_position is False:
        q = q.where(InternshipRecord.position_id.is_(None))
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.join(StudentProfile, StudentProfile.id == InternshipRecord.student_id).where(
            or_(StudentProfile.real_name.like(like), StudentProfile.student_no.like(like)))
    if class_id:
        q = q.join(StudentProfile, StudentProfile.id == InternshipRecord.student_id).where(
            StudentProfile.class_id == _as_id(class_id))
    rows = db.scalars(q.order_by(InternshipRecord.updated_at.desc(), InternshipRecord.id.desc())).all()
    smap = _students_map(db, [r.student_id for r in rows])
    scope = _current_scope(user)
    kept = []
    for r in rows:
        stu = smap.get(r.student_id)
        if keyword:
            kw = keyword.strip()
            if not stu or (kw not in (stu.real_name or "") and kw not in (stu.student_no or "")):
                continue
        if class_id and (not stu or str(stu.class_id) != str(class_id)):
            continue
        if not _rec_in_scope(scope, db, r, stu):
            continue
        kept.append(r)
    return kept


def list_students(page: int, page_size: int, keyword=None, class_id=None, status=None,
                  risk_level=None, eligibility=None, destination=None,
                  has_position=None, batch_id=None, user=None) -> tuple[list[dict], int]:
    with session() as db:
        # The common collector retains the complete Python scope fallback for
        # class/college scopes.  For tenant-wide and advisor-id-only scopes,
        # paginate in SQL so the flagship list does not load an entire batch.
        scope = _current_scope(user)
        sql_safe = scope.get("mode") != "SCOPED" or (
            scope.get("by") == "ADVISOR" and scope.get("advisorUserIds"))
        if sql_safe:
            from app.modules.internship.services.internship_batch_context import resolve_batch
            batch = resolve_batch(db, batch_id, for_write=False)
            q = select(InternshipRecord).where(
                InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False),
                InternshipRecord.batch_id == batch.id)
            if status: q = q.where(InternshipRecord.status == status)
            if risk_level: q = q.where(InternshipRecord.risk_level == risk_level)
            if eligibility: q = q.where(InternshipRecord.eligibility_status == eligibility)
            if destination: q = q.where(InternshipRecord.destination_type == destination)
            if has_position is True: q = q.where(InternshipRecord.position_id.is_not(None))
            elif has_position is False: q = q.where(InternshipRecord.position_id.is_(None))
            if scope.get("mode") == "SCOPED":
                q = q.where(InternshipRecord.advisor_user_id.in_(scope["advisorUserIds"]))
            if keyword or class_id:
                q = q.join(StudentProfile, StudentProfile.id == InternshipRecord.student_id)
                if keyword:
                    like = f"%{keyword.strip()}%"
                    q = q.where(or_(StudentProfile.real_name.like(like), StudentProfile.student_no.like(like)))
                if class_id: q = q.where(StudentProfile.class_id == _as_id(class_id))
            total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
            offset = (max(1, page) - 1) * page_size
            kept = db.scalars(q.order_by(InternshipRecord.updated_at.desc(), InternshipRecord.id.desc())
                              .offset(offset).limit(page_size)).all()
        else:
            kept = _collect_scoped_records(
                db, batch_id=batch_id, keyword=keyword, class_id=class_id, status=status,
                risk_level=risk_level, eligibility=eligibility, destination=destination,
                has_position=has_position, user=user)
            total = len(kept)
            start = (max(1, page) - 1) * page_size
            kept = kept[start:start + page_size]
        smap = _students_map(db, [r.student_id for r in kept])
        bmap = _batch_names(db, [r.batch_id for r in kept])
        from app.modules.internship.services.internship_service import resolve_student_class_college_names
        items = []
        for r in kept:
            stu = smap.get(r.student_id)
            cn, _ = resolve_student_class_college_names(db, stu)
            items.append(_row(r, stu, bmap.get(r.batch_id, ""), class_name=cn))
        return items, total


def get_student(rec_id, user=None) -> dict:
    """详情：主档 + 企业/岗位/导师关联 + 资格/去向/状态 + 联系电话脱敏 + 审计。"""
    with session() as db:
        r = _get(db, rec_id)
        stu = db.get(StudentProfile, r.student_id)
        if not _rec_in_scope(_current_scope(user), db, r, stu):  # P0-D：越范围访问详情 → 403
            from app.core.exceptions import no_permission
            raise no_permission("该实习学生不在你的数据范围内")
        phone = db.scalars(select(StudentContact).where(
            StudentContact.tenant_id == _tid(), StudentContact.student_id == r.student_id,
            StudentContact.contact_type == "PHONE")).first()
        company = position = None
        if r.enterprise_id:
            c = db.get(EmpCompany, r.enterprise_id)
            if c and not c.is_deleted:
                company = {"id": str(c.id), "name": c.name, "coopStatus": c.coop_status,
                           "blacklist": bool(c.blacklist)}
        if r.position_id:
            p = db.get(InternshipPosition, r.position_id)
            if p and not p.is_deleted:
                position = {"id": str(p.id), "title": p.title, "status": p.status,
                            "workLocation": p.work_location or "",
                            "capacity": f"{p.allocated_count}/{p.headcount}"}
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(),
            InternshipAuditTrail.target_type == "INTERN_STUDENT",
            InternshipAuditTrail.target_id == r.id).order_by(
            InternshipAuditTrail.occurred_at.desc()).limit(20)).all()
        return {
            **_row(r, stu),
            "phone": _mask_phone(phone.contact_value_encrypted if phone else None),
            "insurance": r.insurance_info or "", "agreement": r.agreement_info or "",
            "remark": r.remark or "", "company": company, "position": position,
            "auditTrail": [{"action": a.action, "operator": a.operator_name or "",
                            "detail": a.detail_json or {}, "occurredAt": _iso(a.occurred_at)}
                           for a in trail],
        }


# ═══════════ 建档 / 编辑 ═══════════

def create_student_record(body, user=None) -> dict:
    from sqlalchemy.exc import IntegrityError

    from app.modules.internship.services.internship_batch_context import resolve_batch
    with session() as db:
        sid = int(getattr(body, "studentId"))
        stu = db.get(StudentProfile, sid)
        if not stu or stu.is_deleted or stu.tenant_id != _tid():
            raise not_found("学生不存在或不在当前数据范围内")
        from app.modules.internship.services.internship_service import assert_student_in_scope
        assert_student_in_scope(db, sid, user, "该学生不在你的数据范围内")
        batch = resolve_batch(db, getattr(body, "batchId", None), for_write=True)
        batch_id = batch.id
        dup = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.student_id == sid,
            InternshipRecord.batch_id == batch_id,
            InternshipRecord.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该学生在此批次已有实习记录")
        advisor = _advisor(db, getattr(body, "advisorUserId", None), getattr(body, "advisorName", None))
        r = InternshipRecord(
            tenant_id=_tid(), student_id=sid, batch_id=batch_id,
            advisor_user_id=advisor.id if advisor else None,
            advisor_name=advisor.real_name if advisor else None, remark=getattr(body, "remark", None),
            status="PREPARING", eligibility_status="PENDING", destination_type="NONE", risk_level="NONE")
        db.add(r)
        try:
            db.flush()
            _trail(db, r.id, "CREATE", {"studentId": str(sid), "batchId": str(batch_id),
                                          "advisorUserId": str(advisor.id) if advisor else ""})
            db.commit()
        except IntegrityError:
            db.rollback()
            raise AppException("DATA_CONFLICT", "该学生在此批次已有实习记录") from None
        return _row_of(db, r)


def update_student_record(rec_id, body, user=None) -> dict:
    with session() as db:
        r = _get(db, rec_id)
        _assert_write_scope(db, r, user)
        if r.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档记录不可编辑")
        before_advisor = r.advisor_user_id
        if getattr(body, "advisorUserId", None) is not None or getattr(body, "advisorName", None) is not None:
            advisor = _advisor(db, getattr(body, "advisorUserId", None), getattr(body, "advisorName", None))
            r.advisor_user_id = advisor.id if advisor else None
            r.advisor_name = advisor.real_name if advisor else None
        for src, col in [("insurance", "insurance_info"), ("agreement", "agreement_info"),
                         ("remark", "remark")]:
            v = getattr(body, src, None)
            if v is not None:
                setattr(r, col, v)
        r.version = int(r.version or 0) + 1
        _trail(db, r.id, "UPDATE", {"advisorUserIdBefore": str(before_advisor or ""),
                                      "advisorUserIdAfter": str(r.advisor_user_id or "")})
        db.commit()
        return _row_of(db, r)


def assign_advisor(rec_id, advisor_user_id, reason: str = "", user=None) -> dict:
    with session() as db:
        r = _get(db, rec_id)
        _assert_write_scope(db, r, user)
        if r.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档记录不可变更指导教师")
        advisor = _advisor(db, advisor_user_id)
        before = r.advisor_user_id
        if before == advisor.id:
            raise AppException("DATA_CONFLICT", "该学生已分配给此指导教师")
        r.advisor_user_id, r.advisor_name = advisor.id, advisor.real_name
        r.version = int(r.version or 0) + 1
        _trail(db, r.id, "ASSIGN_ADVISOR", {"fromUserId": str(before or ""),
                                             "toUserId": str(advisor.id), "reason": (reason or "").strip()})
        db.commit()
        return _row_of(db, r)


# ═══════════ 学生-岗位分配（岗位库 allocated_count 收口）═══════════

_RELEASE_SQL = (
    "UPDATE t_internship_position SET "
    "allocated_count = CASE WHEN allocated_count > 0 THEN allocated_count - 1 ELSE 0 END, "
    "status = CASE WHEN status = 'FULL' AND "
    "CASE WHEN allocated_count > 0 THEN allocated_count - 1 ELSE 0 END < headcount "
    "THEN 'PUBLISHED' ELSE status END, "
    "version = version + 1 "
    "WHERE id = :pid AND tenant_id = :tid AND is_deleted = 0"
)
_CLAIM_SQL = (
    "UPDATE t_internship_position SET allocated_count = allocated_count + 1, "
    "status = CASE WHEN allocated_count + 1 >= headcount THEN 'FULL' ELSE status END, "
    "version = version + 1 "
    "WHERE id = :pid AND tenant_id = :tid AND is_deleted = 0 "
    "AND status = 'PUBLISHED' AND allocated_count < headcount"
)


def assign_position(rec_id, position_id, user=None) -> dict:
    """分配/调岗：先原子占用新岗位，成功后再释放旧岗位，避免新岗失败时丢旧岗。"""
    from sqlalchemy import text
    with session() as db:
        r = _get(db, rec_id)
        _assert_write_scope(db, r, user)
        if r.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档记录不可分配岗位")
        p = db.get(InternshipPosition, _as_id(position_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("岗位不存在或不在当前数据范围内")
        if r.position_id == p.id:
            raise AppException("DATA_CONFLICT", "该学生已分配到此岗位")
        if p.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", f"仅「已上架」岗位可分配（当前：{p.status}）")
        c = db.get(EmpCompany, p.company_id)
        if not c or c.is_deleted:
            raise not_found("岗位所属企业不存在")
        if c.blacklist or c.coop_status == "BLACKLIST":
            raise AppException("DATA_CONFLICT", "黑名单企业岗位不可分配学生")
        from app.modules.internship.services.internship_compliance_rules import get_batch_compliance_rules
        from app.modules.internship.services.internship_enterprise_inspection_service import is_enterprise_access_valid
        from app.modules.internship.services.internship_position_rights import evaluate_position_compliance
        batch = db.get(InternshipBatch, r.batch_id) if r.batch_id else None
        compliance_rules = get_batch_compliance_rules(db, batch)
        ea = compliance_rules.get("enterpriseAccess") or {}
        if ea.get("required"):
            access_ok, access_reason = is_enterprise_access_valid(db, c.id, compliance_rules)
            if not access_ok:
                raise AppException("DATA_CONFLICT", f"企业准入未通过：{access_reason}")
        wr = compliance_rules.get("workRights") or {}
        if wr.get("required"):
            rights = evaluate_position_compliance(p, None, compliance_rules)
            if rights["blockers"]:
                raise AppException("DATA_CONFLICT", "岗位劳动权益不合规：" + "；".join(rights["blockers"]))
        elif p.prohibited_reason:
            raise AppException("DATA_CONFLICT", f"岗位禁止安排：{p.prohibited_reason}")
        old_id = r.position_id
        # 为降低死锁：同时涉及两岗时按 id 升序加行锁，再 claim 新岗 / release 旧岗
        lock_ids = sorted({i for i in (old_id, p.id) if i})
        for lid in lock_ids:
            db.execute(text(
                "SELECT id FROM t_internship_position WHERE id = :pid AND tenant_id = :tid "
                "AND is_deleted = 0 FOR UPDATE"
            ), {"pid": lid, "tid": _tid()})
        claimed = db.execute(text(_CLAIM_SQL), {"pid": p.id, "tid": _tid()}).rowcount
        if claimed != 1:
            raise AppException("DATA_CONFLICT", "该岗位已满员或状态已变化，不能再分配")
        if old_id:
            db.execute(text(_RELEASE_SQL), {"pid": old_id, "tid": _tid()})
        db.refresh(p)
        r.position_id = p.id
        r.enterprise_id = c.id
        r.mentor_contact_id = p.mentor_contact_id
        r.position_name = p.title
        r.enterprise_name = c.name
        r.enterprise_mentor_name = p.mentor_name
        r.destination_type = "ASSIGNED"
        _trail(db, r.id, "ASSIGN_POSITION", {
            "positionId": str(p.id), "title": p.title,
            "fromPositionId": str(old_id or ""),
        })
        db.commit()
        return _row_of(db, r)


def unassign_position(rec_id, reason: str = "", user=None) -> dict:
    from sqlalchemy import text
    with session() as db:
        r = _get(db, rec_id)
        _assert_write_scope(db, r, user)
        if not r.position_id:
            raise AppException("DATA_CONFLICT", "该学生未分配岗位")
        old_id = r.position_id
        db.execute(text(
            "SELECT id FROM t_internship_position WHERE id = :pid AND tenant_id = :tid "
            "AND is_deleted = 0 FOR UPDATE"
        ), {"pid": old_id, "tid": _tid()})
        db.execute(text(_RELEASE_SQL), {"pid": old_id, "tid": _tid()})
        r.position_id = None
        r.enterprise_id = None
        r.mentor_contact_id = None
        r.position_name = None
        r.enterprise_name = None
        r.enterprise_mentor_name = None
        r.destination_type = "NONE"
        _trail(db, r.id, "UNASSIGN_POSITION", {"reason": reason})
        db.commit()
        return _row_of(db, r)


# ═══════════ 状态机 / 资格 / 去向 ═══════════

def _onboard_rules(db, r: InternshipRecord) -> dict:
    """取该记录所属批次的上岗前置规则；批次未配置时用系统默认（全部要求）。"""
    default = {"requireAgreement": True, "requireInsurance": True, "requireAdvisor": True}
    if not r.batch_id:
        return default
    b = db.get(InternshipBatch, r.batch_id)
    cfg = ((b.rules_config or {}).get("onboard") or {}) if b else {}
    values = {k: bool(cfg.get(k, v)) for k, v in default.items()}
    if b:
        values["compliance"] = ((b.rules_config or {}).get("compliance") or {})
    return values


def _onboard_blockers(db, r: InternshipRecord) -> list[str]:
    """上岗前置：岗位硬门槛 + 统一合规评估（含协议/保险/知情/安全/备案等）。"""
    missing: list[str] = []
    if not r.position_id:
        missing.append("未分配岗位")
    from app.modules.internship.services.internship_compliance_service import evaluate_internship_compliance
    result = evaluate_internship_compliance(r.id, "ONBOARD")
    for item in result.get("blockers") or []:
        tip = item.get("label") or item.get("code")
        reason = item.get("reason") or item.get("status")
        missing.append(f"{tip}：{reason}")
    return missing


def get_onboard_checklist(rec_id, user=None) -> dict:
    """上岗前置检查清单（供前端在点「上岗」前展示，不做写操作）。"""
    with session() as db:
        r = _get(db, rec_id)
        _assert_write_scope(db, r, user)
        blockers = _onboard_blockers(db, r)
        return {"internshipId": str(r.id), "canOnboard": not blockers and r.status == "READY",
                "statusReady": r.status == "READY", "blockers": blockers}


def set_status(rec_id, action: str, reason: str = "", user=None) -> dict:
    """READY / ONBOARD / ASSESS / ARCHIVE。上岗需已合格 + 已分配岗位。"""
    with session() as db:
        r = _get(db, rec_id)
        _assert_write_scope(db, r, user)
        if action == "READY":
            if r.status != "PREPARING":
                raise AppException("DATA_CONFLICT", "仅「准备中」可置为待上岗")
            if r.eligibility_status != "QUALIFIED":
                raise AppException("DATA_CONFLICT", "实习资格未认定合格，不能待上岗")
            r.status = "READY"
        elif action == "ONBOARD":
            if r.status != "READY":
                raise AppException("DATA_CONFLICT", "仅「待上岗」可上岗")
            missing = _onboard_blockers(db, r)
            if missing:
                raise AppException("DATA_CONFLICT", "上岗前置未完成：" + "；".join(missing))
            r.status = "ONBOARD"
            if not r.intern_start_date:
                r.intern_start_date = datetime.utcnow()
        elif action == "ASSESS":
            if r.status != "ONBOARD":
                raise AppException("DATA_CONFLICT", "仅「在岗中」可进入考核")
            r.status = "ASSESSING"
        elif action == "ARCHIVE":
            if r.status not in ("ASSESSING", "ONBOARD"):
                raise AppException("DATA_CONFLICT", "仅在岗/考核中可归档")
            r.status = "ARCHIVED"
        else:
            raise AppException("VALIDATION_ERROR", "非法状态动作")
        _trail(db, r.id, f"STATUS_{action}", {"reason": reason, "to": r.status})
        db.commit()
        return _row_of(db, r)


def set_eligibility(rec_id, status: str, reason: str = "", user=None) -> dict:
    if status not in ("QUALIFIED", "UNQUALIFIED", "PENDING"):
        raise AppException("VALIDATION_ERROR", "非法资格状态")
    with session() as db:
        r = _get(db, rec_id)
        _assert_write_scope(db, r, user)
        r.eligibility_status = status
        _trail(db, r.id, "ELIGIBILITY", {"status": status, "reason": reason})
        db.commit()
        return _row_of(db, r)


def set_destination(rec_id, destination: str, reason: str = "", user=None) -> dict:
    """自主实习 / 免实习 / 未落实。已分配岗位(ASSIGNED)请走退岗，不在此改。"""
    if destination not in ("SELF_ARRANGED", "EXEMPTED", "NONE"):
        raise AppException("VALIDATION_ERROR", "非法去向（分配岗位请用分配接口）")
    with session() as db:
        r = _get(db, rec_id)
        _assert_write_scope(db, r, user)
        if r.position_id:
            raise AppException("DATA_CONFLICT", "已分配岗位，请先退岗再改去向")
        r.destination_type = destination
        _trail(db, r.id, "DESTINATION", {"destination": destination, "reason": reason})
        db.commit()
        return _row_of(db, r)


# ═══════════ 统计 ═══════════

def student_stats(batch_id=None, keyword=None, class_id=None, status=None,
                  risk_level=None, eligibility=None, destination=None,
                  has_position=None, user=None) -> dict:
    """与 list_students / export_students 共用同一过滤条件，保证 total 一致。"""
    with session() as db:
        kept = _collect_scoped_records(
            db, batch_id=batch_id, keyword=keyword, class_id=class_id, status=status,
            risk_level=risk_level, eligibility=eligibility, destination=destination,
            has_position=has_position, user=user)
        total = len(kept)
        by_status = [{"status": s, "label": STATUS_LABEL[s],
                      "count": sum(1 for r in kept if r.status == s)} for s in STATUS_LABEL]
        assigned = sum(1 for r in kept if r.position_id)
        unassigned = total - assigned
        qualified = sum(1 for r in kept if r.eligibility_status == "QUALIFIED")
        from app.modules.internship.services.internship_batch_context import (
            batch_public_fields, resolve_batch)
        batch = resolve_batch(db, batch_id, for_write=False)
        return {"total": total, "byStatus": by_status, "assigned": assigned,
                "unassigned": unassigned, "qualified": qualified,
                **batch_public_fields(batch)}


# ═══════════ 导入 / 导出 ═══════════

def _parse_date(s):
    """宽松解析日期：支持 2026-03-02 / 2026/3/2 / 2026.3.2；空返回 None；非法返回 False。"""
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s.split(" ")[0] if fmt != "%Y-%m-%d %H:%M:%S" else s, fmt)
        except ValueError:
            continue
    return False


def import_dry_run(rows: list[dict], batch_id=None) -> dict:
    """xlsx 逐行预校验：学生与指导教师均引用既有账号/主档，不隐式创建身份。
    批次来自页面上下文 batchId，不依赖 Excel 填写数据库 ID。
    """
    from app.modules.internship.services.internship_batch_context import (
        batch_public_fields, resolve_batch)
    with session() as db:
        batch = resolve_batch(db, batch_id, for_write=True)
        profiles = {s.student_no: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))).all()}
        existing_sids = {r.student_id for r in db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False),
            InternshipRecord.batch_id == batch.id)).all()}
        eligible_ids = _advisor_role_user_ids(db)
        advisors_by_name: dict[str, list[User]] = {}
        for teacher in db.scalars(select(User).where(
                User.tenant_id == _tid(), User.id.in_(eligible_ids), User.status == "ACTIVE",
                User.is_deleted.is_(False))).all():
            advisors_by_name.setdefault((teacher.real_name or "").strip(), []).append(teacher)
        errors, seen, valid = [], set(), 0
        for i, r in enumerate(rows or []):
            row_no = i + 1
            no = (r.get("studentNo") or "").strip()
            if not no:
                errors.append({"rowNo": row_no, "field": "studentNo", "message": "学号必填"})
                continue
            stu = profiles.get(no)
            if not stu:
                errors.append({"rowNo": row_no, "field": "studentNo", "message": f"未匹配到学生：{no}"})
                continue
            if stu.id in existing_sids or no in seen:
                errors.append({"rowNo": row_no, "field": "studentNo",
                               "message": f"该学生在本批次已有实习记录：{no}"})
                continue
            advisor_name = (r.get("advisorName") or "").strip()
            if advisor_name and len(advisors_by_name.get(advisor_name, [])) != 1:
                errors.append({"rowNo": row_no, "field": "advisorName",
                               "message": "指导教师未匹配到唯一的在职岗位实习指导教师账号"})
                continue
            bad_date = False
            for fld in ("startDate", "endDate"):
                if _parse_date(r.get(fld)) is False:
                    errors.append({"rowNo": row_no, "field": fld, "message": "日期格式应为 YYYY-MM-DD"})
                    bad_date = True
                    break
            if bad_date:
                continue
            seen.add(no)
            valid += 1
        return {"total": len(rows or []), "validRows": valid,
                "invalidRows": len(errors), "errors": errors,
                **batch_public_fields(batch)}


def import_confirm(rows: list[dict], batch_id=None, user=None) -> dict:
    from sqlalchemy.exc import IntegrityError

    from app.modules.internship.services.internship_batch_context import (
        batch_public_fields, resolve_batch)
    from app.modules.internship.services.internship_service import assert_admin_tenant
    assert_admin_tenant(user, "实习学生批量导入")
    # confirm 重新校验批次状态，不信任 dry-run 时的快照
    pre = import_dry_run(rows, batch_id=batch_id)
    if pre["invalidRows"] > 0:
        raise AppException("DATA_CONFLICT", "存在未通过预校验的行，禁止确认导入")
    with session() as db:
        batch = resolve_batch(db, batch_id, for_write=True)
        profiles = {s.student_no: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))).all()}
        created, skipped, failed = 0, 0, 0
        try:
            for r in rows or []:
                stu = profiles.get((r.get("studentNo") or "").strip())
                if not stu:
                    failed += 1
                    continue
                # confirm 再次查重（防 dry-run 后并发写入）
                dup = db.scalars(select(InternshipRecord).where(
                    InternshipRecord.tenant_id == _tid(), InternshipRecord.student_id == stu.id,
                    InternshipRecord.batch_id == batch.id,
                    InternshipRecord.is_deleted.is_(False))).first()
                if dup:
                    skipped += 1
                    continue
                sd, ed = _parse_date(r.get("startDate")), _parse_date(r.get("endDate"))
                advisor = _advisor(db, advisor_name=r.get("advisorName"))
                rec = InternshipRecord(
                    tenant_id=_tid(), student_id=stu.id, batch_id=batch.id,
                    advisor_user_id=advisor.id if advisor else None,
                    advisor_name=advisor.real_name if advisor else None,
                    intern_start_date=sd or None, intern_end_date=ed or None,
                    remark=(r.get("remark") or None),
                    status="PREPARING", eligibility_status="PENDING",
                    destination_type="NONE", risk_level="NONE")
                db.add(rec)
                db.flush()
                _trail(db, rec.id, "IMPORT", {"studentNo": stu.student_no,
                                              "batchId": str(batch.id),
                                              "advisorUserId": str(rec.advisor_user_id or ""),
                                              "advisorName": rec.advisor_name or ""})
                created += 1
            db.commit()
        except IntegrityError:
            db.rollback()
            raise AppException("DATA_CONFLICT", "导入冲突：同一学生在本批次已有实习记录") from None
        return {"created": created, "skipped": skipped, "failed": failed,
                **batch_public_fields(batch)}


# 导入模板仅含真实可写入字段（P0-6）。本次导入只建实习学生名单，不自动分岗、不上岗。
IMPORT_HEADERS = ["学号", "指导教师", "实习开始日期", "实习结束日期", "备注"]
IMPORT_REQUIRED = ["学号"]
IMPORT_HEADER_MAP = {
    "学号": "studentNo", "指导教师": "advisorName",
    "实习开始日期": "startDate", "实习结束日期": "endDate", "备注": "remark",
}
IMPORT_SAMPLE = ["2023115001", "刘强", "2026-03-02", "2026-08-28", ""]
IMPORT_NOTES = [
    "学号必填，且必须是本校已有学生。",
    "导入归属当前页面所选批次（必选），本模板不包含企业/岗位/状态等字段。",
    "本次导入仅建立实习学生名单，不自动分岗、不自动上岗。",
    "指导教师须为本校已有教师姓名（可选）。",
    "日期格式：YYYY-MM-DD（如 2026-03-02）。",
    "仅导入「导入模板」页。",
]


def _row_values_for_error(r: dict) -> list:
    return [r.get(IMPORT_HEADER_MAP[h], "") for h in IMPORT_HEADERS]


def export_students(keyword=None, status=None, eligibility=None, batch_id=None,
                    class_id=None, risk_level=None, destination=None, has_position=None,
                    user=None) -> dict:
    """导出实习学生台账（xlsx）：与 list_students 同过滤；文件名含水印含批次名；审计记 batchId。"""
    from app.modules.internship.services.internship_batch_context import (
        batch_public_fields, resolve_batch)
    from app.services import xlsx_util
    with session() as db:
        batch = resolve_batch(db, batch_id, for_write=False)
        batch_meta = batch_public_fields(batch)
    items, total = list_students(
        1, 100000, keyword=keyword, status=status, eligibility=eligibility,
        batch_id=batch_id, class_id=class_id, risk_level=risk_level,
        destination=destination, has_position=has_position, user=user)
    from app.modules.internship.services.internship_export_util import pack_export_meta, require_exportable
    require_exportable(total)
    headers = ["学号", "姓名", "班级", "批次", "校内指导教师", "企业名称", "岗位名称",
               "实习状态", "实习资格", "实习去向", "风险"]
    data_rows = [[it["studentNo"], it["name"], it["className"], batch_meta["batchName"],
                  it["advisorName"], it["enterpriseName"], it["positionName"], it["statusLabel"],
                  it["eligibilityLabel"], it["destinationLabel"], it["riskLabel"]] for it in items]
    user_ctx = get_current_user_ctx() or {}
    bname = batch_meta["batchName"] or "未命名批次"
    wm = (f"岗位实习中心·实习学生台账 · 批次：{bname} · 导出人：{user_ctx.get('realName', '-')} · "
          f"{datetime.now():%Y-%m-%d %H:%M} · 敏感字段已脱敏，导出留痕")
    content = xlsx_util.build_ledger_xlsx("实习学生台账", headers, data_rows, watermark=wm)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in bname)[:40] or "batch"
    packed = xlsx_util.pack_xlsx_result(content, f"实习学生台账_{safe_name}.xlsx", len(items))
    packed.update(batch_meta)
    packed.update(pack_export_meta(total, len(items)))
    return packed
