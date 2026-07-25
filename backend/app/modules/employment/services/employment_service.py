"""就业服务域真实数据服务。租户过滤 + 脱敏 + 审计留痕。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (EmpAuditTrail, EmpCompany, EmpFollowup, EmpJob, EmpMaterial, EmpStudent)
from app.services.db_service import _iso, _mask_id_card, _mask_phone, _tid, session

L_DEST = {"SIGNED": "签约就业", "FLEXIBLE": "灵活就业", "FURTHER_STUDY": "升学", "ENLISTED": "入伍",
          "STARTUP": "自主创业", "FREELANCE": "自由职业", "UNEMPLOYED": "待就业"}
L_VERIFY = {"PENDING_VERIFY": "待核验", "VERIFIED": "已核验", "RETURNED": "已退回"}
L_MAT = {"SUBMITTED": "待审核", "REVIEWING": "审核中", "APPROVED": "已通过", "RETURNED": "退回补充",
         "REJECTED": "已驳回"}
L_MATTYPE = {"AGREEMENT": "就业协议", "CONTRACT": "劳动合同", "OFFER": "录用通知", "STUDY_PROOF": "升学证明",
             "ENLIST_PROOF": "入伍证明", "STARTUP_PROOF": "创业证明", "OTHER": "其他材料"}
L_HELP = {"NORMAL": "常规跟进", "KEY_HELP": "重点帮扶"}
L_RISK = {"LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}
L_WAY = {"PHONE": "电话联系", "FACE": "面谈", "RECOMMEND": "岗位推荐", "VISIT": "走访"}
L_FU = {"OPEN": "跟进中", "CLOSED": "已闭环", "VOIDED": "已作废"}
L_COMP = {"ACTIVE": "合作中", "DISABLED": "已停用"}
L_JOB = {"OPEN": "招聘中", "CLOSED": "已停止"}


def _op():
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("currentRoleCode") or ""


def _audit(db, bt, bid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(EmpAuditTrail(tenant_id=_tid(), biz_type=bt, biz_id=str(bid), action=action, operator=n,
                         role_name=r, detail=detail, before_val=before, after_val=after,
                         occurred_at=datetime.utcnow()))


def _page(items, page, ps):
    total = len(items)
    start = (max(1, page) - 1) * ps
    return items[start:start + ps], total


def _get_stu(db, sid) -> EmpStudent:
    s = db.get(EmpStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("就业记录不存在或不在当前数据范围内")
    return s


def _stu_of(db, sid):
    return db.get(EmpStudent, sid)


def _emp_students_by_ids(db, rows, attr="emp_student_id"):
    """批量取回 rows 涉及的就业档案 {id: EmpStudent}，替代列表循环内逐行 _stu_of（消 N+1）。"""
    sids = {int(getattr(x, attr)) for x in rows if getattr(x, attr, None)}
    if not sids:
        return {}
    return {s.id: s for s in db.scalars(select(EmpStudent).where(EmpStudent.id.in_(sids))).all()}


def _salary_mask(v):
    return v or "—"


TODO_FOLLOWUP = "EMPLOYMENT_FOLLOWUP"


def _resolve_teacher_user_id(db, teacher: str) -> int:
    """就业老师字符串 → User.id：优先 login_name，其次唯一 real_name。"""
    from app.models import User
    t = (teacher or "").strip()
    if not t:
        return 0
    row = db.scalars(select(User).where(
        User.tenant_id == _tid(), User.login_name == t,
        User.is_deleted.is_(False), User.status == "ACTIVE")).first()
    if row:
        return int(row.id)
    rows = db.scalars(select(User).where(
        User.tenant_id == _tid(), User.real_name == t,
        User.user_type.in_(("TEACHER", "STAFF", "SCHOOL_ADMIN", "ADMIN")),
        User.is_deleted.is_(False), User.status == "ACTIVE")).all()
    return int(rows[0].id) if len(rows) == 1 else 0


def _needs_followup(s: EmpStudent) -> bool:
    return (s.destination_type or "") == "UNEMPLOYED" or (s.help_level or "") == "KEY_HELP"


def _todo_upsert_followup(db, emp: EmpStudent, assignee_id: int) -> bool:
    from app.models import UnifiedTodo
    aid = int(assignee_id or 0)
    if aid <= 0 or not emp or not emp.id:
        return False
    bid = int(emp.id)
    title = f"就业跟进：{emp.name or ''}"
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "employment",
        UnifiedTodo.source_biz_id == bid, UnifiedTodo.todo_type == TODO_FOLLOWUP,
        UnifiedTodo.assignee_id == aid, UnifiedTodo.is_deleted.is_(False))).first()
    if row:
        row.title = title
        row.status = "PENDING"
        row.student_id = emp.student_id
        row.source_biz_type = "EMP_FOLLOWUP"
        row.version = int(row.version or 0) + 1
        return True
    db.add(UnifiedTodo(
        tenant_id=_tid(), source_module="employment", source_biz_type="EMP_FOLLOWUP",
        source_biz_id=bid, todo_type=TODO_FOLLOWUP, assignee_id=aid,
        student_id=emp.student_id, title=title, status="PENDING"))
    return True


def _todo_done_followup(db, emp_student_id) -> int:
    from app.models import UnifiedTodo
    if not emp_student_id:
        return 0
    n = 0
    for r in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "employment",
            UnifiedTodo.source_biz_id == int(emp_student_id), UnifiedTodo.todo_type == TODO_FOLLOWUP,
            UnifiedTodo.is_deleted.is_(False), UnifiedTodo.status == "PENDING")).all():
        r.status = "DONE"
        r.version = int(r.version or 0) + 1
        n += 1
    return n


def _stu_row(s: EmpStudent) -> dict:
    return {"id": str(s.id), "studentId": str(s.student_id or s.id), "name": s.name,
            "studentNo": s.student_no or "", "gender": s.gender or "", "grade": s.grade or "",
            "collegeName": s.college_name or "", "majorName": s.major_name or "",
            "classId": s.class_id or "", "className": s.class_name or "",
            "phone": _mask_phone(s.phone_encrypted), "idCard": _mask_id_card(s.id_card_encrypted),
            "destinationType": s.destination_type, "destinationLabel": L_DEST.get(s.destination_type, s.destination_type),
            "companyName": s.company_name or "", "jobTitle": s.job_title or "",
            "salaryRange": _salary_mask(s.salary_range), "signDate": s.sign_date or "",
            "isMatchMajor": s.is_match_major, "fromInternship": s.from_internship,
            "verifyStatus": s.verify_status, "verifyLabel": L_VERIFY.get(s.verify_status, s.verify_status),
            "materialStatus": s.material_status, "materialLabel": L_MAT.get(s.material_status, s.material_status),
            "helpLevel": s.help_level, "helpLabel": L_HELP.get(s.help_level, s.help_level),
            "riskLevel": s.risk_level, "riskLabel": L_RISK.get(s.risk_level, s.risk_level),
            "recordStatus": s.record_status, "counselor": s.counselor or "",
            "employmentTeacher": s.employment_teacher or "", "unemployedReason": s.unemployed_reason or "",
            "lastFollowUpTime": _iso(s.last_follow_up_time) or "", "followUpCount": s.follow_up_count,
            "updateTime": _iso(s.updated_at)}


# ═══ 学生 ═══

def list_students(page, ps, keyword=None, class_id=None, destination_type=None, verify_status=None,
                  help_level=None):
    with session() as db:
        q = select(EmpStudent).where(EmpStudent.tenant_id == _tid(), EmpStudent.is_deleted.is_(False),
                                     EmpStudent.record_status == "ACTIVE")
        if class_id:
            q = q.where(EmpStudent.class_id == class_id)
        if destination_type:
            q = q.where(EmpStudent.destination_type == destination_type)
        if verify_status:
            q = q.where(EmpStudent.verify_status == verify_status)
        if help_level:
            q = q.where(EmpStudent.help_level == help_level)
        rows = db.scalars(q.order_by(EmpStudent.id)).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.name or "") or kw in (r.student_no or "")]
        return _page([_stu_row(r) for r in rows], page, ps)


def get_student_detail(sid) -> dict:
    with session() as db:
        s = _get_stu(db, sid)
        mats = db.scalars(select(EmpMaterial).where(EmpMaterial.tenant_id == _tid(),
                          EmpMaterial.emp_student_id == s.id).order_by(EmpMaterial.id.desc())).all()
        fus = db.scalars(select(EmpFollowup).where(EmpFollowup.tenant_id == _tid(),
                         EmpFollowup.emp_student_id == s.id).order_by(EmpFollowup.id.desc())).all()
        logs = db.scalars(select(EmpAuditTrail).where(EmpAuditTrail.tenant_id == _tid(),
                          EmpAuditTrail.biz_id == str(s.id)).order_by(EmpAuditTrail.id.desc()).limit(20)).all()
        return {"student": _stu_row(s),
                "materials": [_mat_row(m, s) for m in mats],
                "followUps": [_fu_row(f, s) for f in fus],
                "auditLogs": [_log_row(x) for x in logs]}


def create_student(body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    no = str(body.get("studentNo") or "").strip()
    if not name or not no:
        raise AppException("VALIDATION_ERROR", "姓名与学号必填")
    with session() as db:
        from app.core.field_crypto import encrypt_field
        s = EmpStudent(tenant_id=_tid(), name=name, student_no=no, class_id=body.get("classId"),
                       class_name=body.get("className"), phone_encrypted=encrypt_field(body.get("phone")),
                       destination_type=body.get("destinationType") or "UNEMPLOYED",
                       company_name=body.get("companyName"), sign_date=body.get("signDate"),
                       counselor=body.get("counselor"))
        db.add(s)
        db.flush()
        _audit(db, "RECORD", s.id, "新增就业记录", f"{name}（{no}）")
        db.commit()
        return {"id": str(s.id)}


def update_student(sid, body: dict) -> dict:
    with session() as db:
        s = _get_stu(db, sid)
        for k, col in {"destinationType": "destination_type", "companyName": "company_name",
                       "jobTitle": "job_title", "salaryRange": "salary_range", "signDate": "sign_date",
                       "employmentTeacher": "employment_teacher"}.items():
            if body.get(k) is not None:
                setattr(s, col, body[k])
        s.version += 1
        _audit(db, "RECORD", s.id, "编辑就业记录")
        db.commit()
        return {"id": str(s.id)}


def void_student(sid, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        s = _get_stu(db, sid)
        s.record_status = "VOIDED"
        s.void_reason = reason.strip()
        s.is_deleted = True
        s.version += 1
        _audit(db, "RECORD", s.id, "作废就业记录", reason.strip())
        db.commit()
        return {"id": str(s.id)}


def batch_mark_destination(ids, destination_type) -> dict:
    if destination_type not in L_DEST:
        raise AppException("VALIDATION_ERROR", "非法去向类型")
    cnt = 0
    with session() as db:
        for sid in ids:
            s = db.get(EmpStudent, int(sid))
            if not s or s.is_deleted or s.tenant_id != _tid():
                continue
            s.destination_type = destination_type
            s.verify_status = "PENDING_VERIFY"
            s.version += 1
            if destination_type != "UNEMPLOYED":
                _todo_done_followup(db, s.id)
            _audit(db, "RECORD", s.id, "批量标记去向", L_DEST[destination_type])
            cnt += 1
        db.commit()
        return {"count": cnt}


# ═══ 材料 ═══

def _mat_row(m: EmpMaterial, stu=None) -> dict:
    return {"id": str(m.id), "studentId": str(m.emp_student_id), "name": stu.name if stu else "",
            "className": stu.class_name if stu else "", "materialType": m.material_type,
            "materialTypeLabel": L_MATTYPE.get(m.material_type, m.material_type), "fileName": m.file_name or "",
            "submitTime": _iso(m.submit_time) or "", "status": m.status,
            "statusLabel": L_MAT.get(m.status, m.status), "reviewer": m.reviewer or "",
            "reviewTime": _iso(m.review_time) or "", "returnReason": m.return_reason or ""}


def list_materials(page, ps, keyword=None, status=None, material_type=None):
    with session() as db:
        q = select(EmpMaterial).where(EmpMaterial.tenant_id == _tid(), EmpMaterial.is_deleted.is_(False))
        if status:
            q = q.where(EmpMaterial.status == status)
        if material_type:
            q = q.where(EmpMaterial.material_type == material_type)
        rows = db.scalars(q.order_by(EmpMaterial.id.desc())).all()
        students = _emp_students_by_ids(db, rows)
        items = []
        for m in rows:
            stu = students.get(int(m.emp_student_id)) if m.emp_student_id else None
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_mat_row(m, stu))
        return _page(items, page, ps)


def approve_material(mid, comment="") -> dict:
    with session() as db:
        m = db.get(EmpMaterial, int(mid))
        if not m or m.is_deleted or m.tenant_id != _tid():
            raise not_found("材料不存在")
        if m.status == "APPROVED":
            raise AppException("DATA_CONFLICT", "该材料已通过")
        before = m.status
        n, _ = _op()
        m.status = "APPROVED"
        m.reviewer = n
        m.review_time = datetime.utcnow()
        m.version += 1
        stu = _stu_of(db, m.emp_student_id)
        if stu:
            stu.material_status = "APPROVED"
            stu.verify_status = "VERIFIED"
        _audit(db, "MATERIAL", m.id, "审核通过", comment, before, "APPROVED")
        db.commit()
        return {"id": str(m.id), "status": "APPROVED"}


def return_material(mid, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        m = db.get(EmpMaterial, int(mid))
        if not m or m.is_deleted or m.tenant_id != _tid():
            raise not_found("材料不存在")
        before = m.status
        n, _ = _op()
        m.status = "RETURNED"
        m.reviewer = n
        m.review_time = datetime.utcnow()
        m.return_reason = reason.strip()
        m.version += 1
        stu = _stu_of(db, m.emp_student_id)
        if stu:
            stu.material_status = "RETURNED"
        _audit(db, "MATERIAL", m.id, "退回材料", reason.strip(), before, "RETURNED")
        db.commit()
        return {"id": str(m.id), "status": "RETURNED"}


# ═══ 未就业帮扶 ═══

def list_unemployed(page, ps, keyword=None, help_level=None, risk_level=None):
    with session() as db:
        q = select(EmpStudent).where(EmpStudent.tenant_id == _tid(), EmpStudent.is_deleted.is_(False),
                                     EmpStudent.record_status == "ACTIVE",
                                     EmpStudent.destination_type == "UNEMPLOYED")
        if help_level:
            q = q.where(EmpStudent.help_level == help_level)
        if risk_level:
            q = q.where(EmpStudent.risk_level == risk_level)
        rows = db.scalars(q.order_by(EmpStudent.id)).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.name or "")]
        items = [{**_stu_row(r), "assignedTeacher": r.employment_teacher or "未分配"} for r in rows]
        return _page(items, page, ps)


def _batch_stu(ids, fn, action):
    cnt = 0
    with session() as db:
        for sid in ids:
            s = db.get(EmpStudent, int(sid))
            if not s or s.is_deleted or s.tenant_id != _tid():
                continue
            fn(s)
            s.version += 1
            _audit(db, "RECORD", s.id, action)
            cnt += 1
        db.commit()
        return {"count": cnt}


def mark_employed(ids):
    def f(s):
        s.destination_type = "SIGNED"
        s.verify_status = "PENDING_VERIFY"

    cnt = 0
    with session() as db:
        for sid in ids:
            s = db.get(EmpStudent, int(sid))
            if not s or s.is_deleted or s.tenant_id != _tid():
                continue
            f(s)
            s.version += 1
            _todo_done_followup(db, s.id)
            _audit(db, "RECORD", s.id, "标记已就业")
            cnt += 1
        db.commit()
        return {"count": cnt}


def mark_key_help(ids):
    def f(s):
        s.help_level = "KEY_HELP"
        s.risk_level = "HIGH"
    return _batch_stu(ids, f, "标记重点帮扶")


def assign_teacher(ids, teacher):
    if not teacher:
        raise AppException("VALIDATION_ERROR", "就业老师必填")
    cnt = 0
    with session() as db:
        aid = _resolve_teacher_user_id(db, teacher)
        for sid in ids:
            s = db.get(EmpStudent, int(sid))
            if not s or s.is_deleted or s.tenant_id != _tid():
                continue
            s.employment_teacher = teacher
            s.version += 1
            if aid and _needs_followup(s):
                _todo_upsert_followup(db, s, aid)
            _audit(db, "RECORD", s.id, "分配就业老师")
            cnt += 1
        db.commit()
        return {"count": cnt}


# ═══ 跟进 ═══

def _fu_row(f: EmpFollowup, stu=None) -> dict:
    return {"id": str(f.id), "studentId": str(f.emp_student_id), "studentName": stu.name if stu else "",
            "className": stu.class_name if stu else "", "followTime": _iso(f.follow_time),
            "way": f.way, "wayLabel": L_WAY.get(f.way, f.way), "content": f.content or "",
            "result": f.result or "", "nextPlan": f.next_plan or "", "operator": f.operator or "",
            "status": f.status, "statusLabel": L_FU.get(f.status, f.status)}


def list_followups(page, ps, keyword=None, status=None):
    with session() as db:
        q = select(EmpFollowup).where(EmpFollowup.tenant_id == _tid(), EmpFollowup.is_deleted.is_(False))
        if status:
            q = q.where(EmpFollowup.status == status)
        rows = db.scalars(q.order_by(EmpFollowup.id.desc())).all()
        students = _emp_students_by_ids(db, rows)
        items = []
        for f in rows:
            stu = students.get(int(f.emp_student_id)) if f.emp_student_id else None
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_fu_row(f, stu))
        return _page(items, page, ps)


def create_followup(body: dict) -> dict:
    content = str(body.get("content") or "").strip()
    if not body.get("studentId") or not content:
        raise AppException("VALIDATION_ERROR", "学生、跟进内容必填")
    with session() as db:
        s = _get_stu(db, body["studentId"])
        n, _ = _op()
        f = EmpFollowup(tenant_id=_tid(), emp_student_id=s.id, way=body.get("way") or "PHONE",
                        content=content, result=body.get("result"), next_plan=body.get("nextPlan"),
                        operator=n, status="OPEN", follow_time=datetime.utcnow())
        db.add(f)
        s.last_follow_up_time = datetime.utcnow()
        s.follow_up_count = (s.follow_up_count or 0) + 1
        _audit(db, "FOLLOWUP", s.id, "新增就业跟进", content)
        db.commit()
        db.refresh(f)
        return {"id": str(f.id)}


def void_followup(fid, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        f = db.get(EmpFollowup, int(fid))
        if not f or f.is_deleted or f.tenant_id != _tid():
            raise not_found("跟进记录不存在")
        f.status = "VOIDED"
        f.void_reason = reason.strip()
        f.is_deleted = True
        f.version += 1
        _audit(db, "FOLLOWUP", f.id, "作废跟进", reason.strip())
        db.commit()
        return {"id": str(f.id)}


# ═══ 企业 / 岗位 ═══

def _comp_row(c: EmpCompany) -> dict:
    return {"id": str(c.id), "name": c.name, "creditCode": c.credit_code or "", "industry": c.industry or "",
            "nature": c.nature or "", "city": c.city or "", "contactPerson": c.contact_person or "",
            "contactPhone": _mask_phone(c.contact_phone_encrypted),
            "cooperationLevel": c.cooperation_level or "", "status": c.status,
            "statusLabel": L_COMP.get(c.status, c.status), "disableReason": c.disable_reason or "",
            "hiredCount": c.hired_count}


def list_companies(page, ps, keyword=None, status=None):
    with session() as db:
        q = select(EmpCompany).where(EmpCompany.tenant_id == _tid(), EmpCompany.is_deleted.is_(False))
        if status:
            q = q.where(EmpCompany.status == status)
        rows = db.scalars(q.order_by(EmpCompany.id.desc())).all()
        items = []
        for c in rows:
            job_cnt = db.scalar(select(func.count()).select_from(EmpJob).where(
                EmpJob.tenant_id == _tid(), EmpJob.company_id == c.id, EmpJob.status == "OPEN",
                EmpJob.is_deleted.is_(False))) or 0
            row = _comp_row(c)
            row["jobCount"] = job_cnt
            if keyword and keyword.strip() not in c.name:
                continue
            items.append(row)
        return _page(items, page, ps)


def create_company(body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    cc = str(body.get("creditCode") or "").strip()
    if not name or not cc:
        raise AppException("VALIDATION_ERROR", "企业名称与统一社会信用代码必填")
    with session() as db:
        from app.core.field_crypto import encrypt_field
        c = EmpCompany(tenant_id=_tid(), name=name, credit_code=cc, industry=body.get("industry"),
                       nature=body.get("nature"), city=body.get("city"),
                       contact_person=body.get("contactPerson"),
                       contact_phone_encrypted=encrypt_field(body.get("contactPhone")),
                       cooperation_level=body.get("cooperationLevel") or "常规合作", status="ACTIVE")
        db.add(c)
        db.flush()
        _audit(db, "COMPANY", c.id, "新增企业", name)
        db.commit()
        return {"id": str(c.id)}


def disable_company(cid, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "停用原因必填且不少于 5 字")
    with session() as db:
        c = db.get(EmpCompany, int(cid))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("企业不存在")
        c.status = "DISABLED"
        c.disable_reason = reason.strip()
        c.version += 1
        # 级联停用关联岗位
        for j in db.scalars(select(EmpJob).where(EmpJob.tenant_id == _tid(), EmpJob.company_id == c.id,
                            EmpJob.is_deleted.is_(False))).all():
            j.status = "CLOSED"
            j.disable_reason = "企业停用连带关闭"
        _audit(db, "COMPANY", c.id, "停用企业", reason.strip())
        db.commit()
        return {"id": str(c.id)}


def _job_row(j: EmpJob) -> dict:
    return {"id": str(j.id), "companyId": str(j.company_id), "companyName": j.company_name or "",
            "title": j.title, "category": j.category or "", "salaryRange": j.salary_range or "",
            "headcount": j.headcount, "signedCount": j.signed_count, "status": j.status,
            "statusLabel": L_JOB.get(j.status, j.status), "disableReason": j.disable_reason or "",
            "publishTime": j.publish_time or ""}


def list_jobs(page, ps, keyword=None, status=None, company_id=None):
    with session() as db:
        q = select(EmpJob).where(EmpJob.tenant_id == _tid(), EmpJob.is_deleted.is_(False))
        if status:
            q = q.where(EmpJob.status == status)
        if company_id:
            q = q.where(EmpJob.company_id == int(company_id))
        rows = db.scalars(q.order_by(EmpJob.id.desc())).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in r.title or kw in (r.company_name or "")]
        return _page([_job_row(j) for j in rows], page, ps)


def create_job(body: dict) -> dict:
    title = str(body.get("title") or "").strip()
    if not body.get("companyId") or not title:
        raise AppException("VALIDATION_ERROR", "企业、岗位名称必填")
    with session() as db:
        c = db.get(EmpCompany, int(body["companyId"]))
        if not c or c.tenant_id != _tid():
            raise not_found("企业不存在")
        j = EmpJob(tenant_id=_tid(), company_id=c.id, company_name=c.name, title=title,
                   category=body.get("category"), salary_range=body.get("salaryRange"),
                   headcount=body.get("headcount") or 1, status="OPEN",
                   publish_time=body.get("publishTime") or datetime.now().strftime("%Y-%m-%d"))
        db.add(j)
        db.flush()
        _audit(db, "JOB", j.id, "新增岗位", title)
        db.commit()
        return {"id": str(j.id)}


def disable_job(jid, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "停用原因必填且不少于 5 字")
    with session() as db:
        j = db.get(EmpJob, int(jid))
        if not j or j.is_deleted or j.tenant_id != _tid():
            raise not_found("岗位不存在")
        j.status = "CLOSED"
        j.disable_reason = reason.strip()
        j.version += 1
        _audit(db, "JOB", j.id, "停用岗位", reason.strip())
        db.commit()
        return {"id": str(j.id)}


# ═══ 审计 + 看板 ═══

def _log_row(x: EmpAuditTrail) -> dict:
    return {"id": str(x.id), "time": _iso(x.occurred_at), "operator": x.operator or "",
            "roleName": x.role_name or "", "bizType": x.biz_type, "bizId": x.biz_id or "",
            "action": x.action, "detail": x.detail or "", "before": x.before_val or "",
            "after": x.after_val or ""}


def list_audit(page, ps, biz_type=None, keyword=None):
    with session() as db:
        q = select(EmpAuditTrail).where(EmpAuditTrail.tenant_id == _tid())
        if biz_type:
            q = q.where(EmpAuditTrail.biz_type == biz_type)
        rows = db.scalars(q.order_by(EmpAuditTrail.id.desc())).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.action or "") or kw in (r.detail or "")]
        return _page([_log_row(r) for r in rows], page, ps)


def get_dashboard() -> dict:
    with session() as db:
        rows = db.scalars(select(EmpStudent).where(EmpStudent.tenant_id == _tid(),
                          EmpStudent.is_deleted.is_(False),
                          EmpStudent.record_status == "ACTIVE")).all()
        total = len(rows)
        implemented = sum(1 for r in rows if r.destination_type != "UNEMPLOYED")
        unemployed = total - implemented
        key_help = sum(1 for r in rows if r.help_level == "KEY_HELP")
        pend_mat = db.scalar(select(func.count()).select_from(EmpMaterial).where(
            EmpMaterial.tenant_id == _tid(), EmpMaterial.status.in_(["SUBMITTED", "REVIEWING"]),
            EmpMaterial.is_deleted.is_(False))) or 0
        rate = f"{(implemented / total * 100):.1f}%" if total else "0%"
        dist = {}
        for r in rows:
            dist[r.destination_type] = dist.get(r.destination_type, 0) + 1
        return {"batchName": "2026 届毕业生就业批次", "batchPeriod": "2026-03-01 ~ 2026-08-31",
                "updateTime": _iso(datetime.now()),
                "kpis": [
                    {"label": "毕业生总数", "value": str(total), "trend": "", "trendQuality": "neutral"},
                    {"label": "去向已落实", "value": str(implemented), "trend": f"落实率 {rate}", "trendQuality": "good"},
                    {"label": "未就业", "value": str(unemployed), "trend": f"待帮扶 {unemployed}",
                     "trendQuality": "bad" if unemployed else "good"},
                    {"label": "重点帮扶", "value": str(key_help), "trend": "", "trendQuality": "bad" if key_help else "good"},
                    {"label": "材料待审核", "value": str(pend_mat), "trend": "", "trendQuality": "neutral"},
                ],
                "destinationDist": [{"label": L_DEST.get(k, k), "value": v} for k, v in dist.items()],
                "todos": [
                    {"id": "t1", "label": "材料待审核", "value": pend_mat, "link": "/admin/employment/materials"},
                    {"id": "t2", "label": "未就业帮扶", "value": unemployed, "link": "/admin/employment/unemployed"},
                ],
                "flow": [], "collegeRates": [], "riskAlerts": []}
