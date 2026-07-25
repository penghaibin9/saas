"""毕业设计中心 · 导师管理 + 导师分配服务。

导师管理：导师资格库（申报→审核→启用/停用/归档）+ 容量 + 方向 + 工作量统计。
导师分配：学生-导师绑定关系（业务关系授权来源，对齐 CLAUDE.md §3.3"毕设导师能看哪些学生，
来自毕业设计导师分配关系"）；分配/调导师全部留痕于 t_gd_mentor_assignment，学生当前导师
落在 t_gd_student.mentor_id/advisor_name，供数据范围与学生详情引用。

隔离说明：不引用实习/迎新域文件；Excel 台账导出用 openpyxl 直连，导师名单导入接公共 Excel 底座。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.core.field_crypto import encrypt_field
from app.models import (GraduationAuditTrail, GraduationMentor, GraduationMentorAssignment,
                        GraduationMentorEval, GraduationStudent)
from app.services import excel
from app.services.db_service import _iso, _mask_phone, _tid, session
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access

QUAL_LABEL = {"PENDING_REVIEW": "待审核", "QUALIFIED": "已认证", "REJECTED": "已驳回",
              "DISABLED": "已停用", "ARCHIVED": "已归档"}
QUAL_TONE = {"PENDING_REVIEW": "warning", "QUALIFIED": "success", "REJECTED": "danger",
             "DISABLED": "default", "ARCHIVED": "default"}
TYPE_LABEL = {"INTERNAL": "校内导师", "ENTERPRISE": "企业导师", "DUAL": "双导师"}
ASSIGN_STATUS_LABEL = {"ACTIVE": "生效中", "CHANGED": "已调整", "CANCELLED": "已取消"}


def _op() -> tuple[str, str]:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("roleName") or u.get("currentRoleCode") or ""


def _audit(db, biz_type, bid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=str(bid), action=action,
                                operator=n, role_name=r, detail=detail, before_val=before,
                                after_val=after, occurred_at=datetime.now(timezone.utc)))


def _get_mentor(db, mid) -> GraduationMentor:
    m = db.get(GraduationMentor, int(mid))
    if not m or m.is_deleted or m.tenant_id != _tid():
        raise not_found("导师不存在或不在当前数据范围内")
    return m


def _mentor_row(m: GraduationMentor) -> dict:
    return {
        "id": str(m.id), "teacherNo": m.teacher_no, "teacherName": m.teacher_name,
        "mentorType": m.mentor_type, "mentorTypeLabel": TYPE_LABEL.get(m.mentor_type, m.mentor_type),
        "title": m.title or "", "collegeName": m.college_name or "", "majorName": m.major_name or "",
        "researchDirection": m.research_direction or "", "maxCapacity": m.max_capacity,
        "currentCount": m.current_count,
        "capacityText": f"{m.current_count}/{m.max_capacity}",
        "capacityFull": m.current_count >= m.max_capacity,
        "phone": _mask_phone(m.phone_encrypted),
        "qualificationStatus": m.qualification_status,
        "qualificationLabel": QUAL_LABEL.get(m.qualification_status, m.qualification_status),
        "qualificationTone": QUAL_TONE.get(m.qualification_status, "default"),
        "reviewComment": m.review_comment or "", "reviewerName": m.reviewer_name or "",
        "reviewedAt": _iso(m.reviewed_at), "remark": m.remark or "",
        "updatedAt": _iso(m.updated_at),
    }


# ═══════════ 导师管理：列表 / 详情 / 增改 ═══════════

def list_mentors(page: int, page_size: int, keyword=None, qualification_status=None,
                 mentor_type=None, has_capacity=None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(GraduationMentor).where(GraduationMentor.tenant_id == _tid(),
                                           GraduationMentor.is_deleted.is_(False))
        if keyword:
            like = f"%{keyword.strip()}%"
            q = q.where(or_(GraduationMentor.teacher_name.like(like),
                            GraduationMentor.teacher_no.like(like),
                            GraduationMentor.research_direction.like(like)))
        if qualification_status:
            q = q.where(GraduationMentor.qualification_status == qualification_status)
        if mentor_type:
            q = q.where(GraduationMentor.mentor_type == mentor_type)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(GraduationMentor.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        items = [_mentor_row(m) for m in rows]
        if has_capacity is not None:
            want_has = str(has_capacity).lower() in ("1", "true", "yes")
            items = [i for i in items if (not i["capacityFull"]) == want_has]
        return items, total


def get_mentor(mid) -> dict:
    with session() as db:
        m = _get_mentor(db, mid)
        students = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.mentor_id == m.id,
            GraduationStudent.is_deleted.is_(False))).all()
        trail = db.scalars(select(GraduationAuditTrail).where(
            GraduationAuditTrail.tenant_id == _tid(), GraduationAuditTrail.biz_type == "MENTOR",
            GraduationAuditTrail.biz_id == str(m.id)).order_by(
            GraduationAuditTrail.id.desc()).limit(30)).all()
        return {
            **_mentor_row(m),
            "latestEval": latest_eval(db, m.id),
            "students": [{"id": str(s.id), "name": s.name, "studentNo": s.student_no or "",
                         "className": s.class_name or "", "topicTitle": s.topic_title or "",
                         "stage": s.stage} for s in students],
            "auditTrail": [{"action": a.action, "operator": a.operator or "", "roleName": a.role_name or "",
                            "detail": a.detail or "", "occurredAt": _iso(a.occurred_at)} for a in trail],
        }


def create_mentor(body: dict) -> dict:
    with session() as db:
        no = (body.get("teacherNo") or "").strip()
        name = (body.get("teacherName") or "").strip()
        if not no or not name:
            raise AppException("VALIDATION_ERROR", "教师工号与姓名必填")
        dup = db.scalars(select(GraduationMentor).where(
            GraduationMentor.tenant_id == _tid(), GraduationMentor.teacher_no == no,
            GraduationMentor.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", f"该教师工号已在导师库：{no}")
        m = GraduationMentor(
            tenant_id=_tid(), teacher_no=no, teacher_name=name,
            mentor_type=body.get("mentorType") or "INTERNAL", title=body.get("title"),
            college_name=body.get("collegeName"), major_name=body.get("majorName"),
            research_direction=body.get("researchDirection"),
            max_capacity=int(body.get("maxCapacity") or 8), phone_encrypted=encrypt_field(body.get("phone")),
            remark=body.get("remark"), qualification_status="PENDING_REVIEW")
        db.add(m)
        db.flush()
        _audit(db, "MENTOR", m.id, "申报导师", detail=f"{name}/{no}")
        if body.get("submitReview"):
            pass  # PENDING_REVIEW 即待审核态，申报即视为提交审核
        db.commit()
        return _mentor_row(m)


def update_mentor(mid, body: dict) -> dict:
    with session() as db:
        m = _get_mentor(db, mid)
        if m.qualification_status in ("DISABLED", "ARCHIVED"):
            raise AppException("DATA_CONFLICT", f"「{QUAL_LABEL.get(m.qualification_status)}」导师不可编辑")
        for src, col in [("teacherName", "teacher_name"), ("mentorType", "mentor_type"),
                         ("title", "title"), ("collegeName", "college_name"),
                         ("majorName", "major_name"), ("researchDirection", "research_direction"),
                         ("phone", "phone_encrypted"), ("remark", "remark")]:
            if src in body and body[src] is not None:
                setattr(m, col, body[src])
        if "maxCapacity" in body and body["maxCapacity"] is not None:
            new_cap = int(body["maxCapacity"])
            if new_cap < m.current_count:
                raise AppException("VALIDATION_ERROR", f"最大容量不可低于当前已指导人数（{m.current_count}）")
            m.max_capacity = new_cap
        m.version += 1
        _audit(db, "MENTOR", m.id, "编辑导师信息")
        db.commit()
        return _mentor_row(m)


# ═══════════ 状态机：资格审核 / 停用 / 启用 / 归档 ═══════════

def review_mentor(mid, action: str, comment: str = None) -> dict:
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and (not comment or len(comment.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    with session() as db:
        m = _get_mentor(db, mid)
        if m.qualification_status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅「待审核」导师可审核")
        n, _ = _op()
        target = "QUALIFIED" if action == "APPROVE" else "REJECTED"
        m.qualification_status = target
        m.reviewer_name = n
        m.review_comment = (comment or "").strip()
        m.reviewed_at = datetime.now(timezone.utc)
        _audit(db, "MENTOR", m.id, "审核导师资格-" + ("通过" if action == "APPROVE" else "驳回"),
               (comment or "").strip())
        db.commit()
        return _mentor_row(m)


def disable_mentor(mid, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "停用原因必填且不少于 5 字")
    with session() as db:
        m = _get_mentor(db, mid)
        if m.qualification_status != "QUALIFIED":
            raise AppException("DATA_CONFLICT", "仅「已认证」导师可停用")
        m.qualification_status = "DISABLED"
        m.disabled_reason = reason.strip()
        _audit(db, "MENTOR", m.id, "停用导师", reason.strip())
        db.commit()
        return _mentor_row(m)


def enable_mentor(mid) -> dict:
    with session() as db:
        m = _get_mentor(db, mid)
        if m.qualification_status != "DISABLED":
            raise AppException("DATA_CONFLICT", "仅「已停用」导师可重新启用")
        m.qualification_status = "QUALIFIED"
        m.disabled_reason = None
        _audit(db, "MENTOR", m.id, "启用导师")
        db.commit()
        return _mentor_row(m)


def archive_mentor(mid) -> dict:
    with session() as db:
        m = _get_mentor(db, mid)
        if m.qualification_status not in ("DISABLED", "REJECTED"):
            raise AppException("DATA_CONFLICT", "仅「已停用/已驳回」导师可归档")
        if m.current_count > 0:
            raise AppException("DATA_CONFLICT", "该导师仍有在指导学生，不可归档")
        m.qualification_status = "ARCHIVED"
        m.archived_at = datetime.now(timezone.utc)
        _audit(db, "MENTOR", m.id, "归档导师")
        db.commit()
        return _mentor_row(m)


# ═══════════ 导师评价（Batch 4，新表 t_gd_mentor_eval，含历史） ═══════════

EVAL_LEVELS = ("优秀", "良好", "合格", "不合格")


def latest_eval(db, mentor_id) -> dict | None:
    e = db.scalars(select(GraduationMentorEval).where(
        GraduationMentorEval.tenant_id == _tid(), GraduationMentorEval.mentor_id == int(mentor_id),
        GraduationMentorEval.is_deleted.is_(False)).order_by(GraduationMentorEval.id.desc())).first()
    if not e:
        return None
    return {"id": str(e.id), "score": e.score, "level": e.level, "period": e.period or "",
            "note": e.note or "", "evaluatedBy": e.evaluated_by or "", "evaluatedAt": _iso(e.evaluated_at)}


def create_eval(mentor_id, score, level, note=None, period=None) -> dict:
    try:
        score = int(score)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "评分必须是 0-100 的整数")
    if not 0 <= score <= 100:
        raise AppException("VALIDATION_ERROR", "评分范围 0-100")
    if level not in EVAL_LEVELS:
        raise AppException("VALIDATION_ERROR", "评价等级必须是 优秀/良好/合格/不合格")
    with session() as db:
        m = _get_mentor(db, mentor_id)
        n, _ = _op()
        e = GraduationMentorEval(tenant_id=_tid(), mentor_id=m.id, period=(period or "").strip() or None,
                                score=score, level=level, note=(note or "").strip() or None,
                                evaluated_by=n, evaluated_at=datetime.now(timezone.utc))
        db.add(e)
        db.flush()
        _audit(db, "MENTOR", m.id, "导师评价", f"{m.teacher_name} {level} {score}分")
        db.commit()
        return {"id": str(e.id), "mentorId": str(m.id), "score": score, "level": level}


def list_evals(mentor_id) -> list[dict]:
    with session() as db:
        rows = db.scalars(select(GraduationMentorEval).where(
            GraduationMentorEval.tenant_id == _tid(), GraduationMentorEval.mentor_id == int(mentor_id),
            GraduationMentorEval.is_deleted.is_(False)).order_by(GraduationMentorEval.id.desc())).all()
        return [{"id": str(e.id), "score": e.score, "level": e.level, "period": e.period or "",
                 "note": e.note or "", "evaluatedBy": e.evaluated_by or "",
                 "evaluatedAt": _iso(e.evaluated_at)} for e in rows]


# ═══════════ 批量分配 / 分配冲突自动检测 / 批量归档（Batch 4） ═══════════

def batch_assign(assignments: list[dict]) -> dict:
    """批量分配：逐条 {gdStudentId, mentorId} 分配，容量/资格/已分配等冲突跳过并记原因。"""
    result = {"assigned": 0, "skipped": 0, "details": []}
    for a in assignments or []:
        sid, mid = a.get("gdStudentId"), a.get("mentorId")
        try:
            r = assign_mentor(sid, mid)
            result["assigned"] += 1
            result["details"].append({"gdStudentId": str(sid), "ok": True, "mentorName": r["mentorName"]})
        except AppException as e:
            result["skipped"] += 1
            result["details"].append({"gdStudentId": str(sid), "ok": False, "reason": e.message})
    return result


def detect_assignment_conflicts() -> dict:
    """分配冲突自动检测：①导师超容量 ②进入指导阶段却无导师 ③学生导师非「已认证」。"""
    with session() as db:
        over = []
        for m in db.scalars(select(GraduationMentor).where(
                GraduationMentor.tenant_id == _tid(), GraduationMentor.is_deleted.is_(False))).all():
            if m.current_count > m.max_capacity:
                over.append({"mentorId": str(m.id), "teacherName": m.teacher_name,
                             "current": m.current_count, "capacity": m.max_capacity})
        no_mentor, bad_mentor = [], []
        stus = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE")).all()
        for s in stus:
            advanced = s.stage in ("GUIDING", "MIDTERM", "FINAL_CHECK", "DEFENSE", "COMPLETED")
            if advanced and not s.mentor_id:
                no_mentor.append({"gdStudentId": str(s.id), "name": s.name, "className": s.class_name or "",
                                  "stage": s.stage})
            elif s.mentor_id:
                m = db.get(GraduationMentor, s.mentor_id)
                if m and m.qualification_status != "QUALIFIED":
                    bad_mentor.append({"gdStudentId": str(s.id), "name": s.name,
                                       "mentorName": m.teacher_name,
                                       "mentorStatus": QUAL_LABEL.get(m.qualification_status)})
        return {"overCapacity": over, "advancedNoMentor": no_mentor, "unqualifiedMentor": bad_mentor,
                "total": len(over) + len(no_mentor) + len(bad_mentor)}


def batch_archive(mentor_ids: list) -> dict:
    """批量归档：逐个归档（仅已停用/已驳回且无在指导学生），冲突跳过记原因。"""
    result = {"archived": 0, "skipped": 0, "details": []}
    for mid in mentor_ids or []:
        try:
            archive_mentor(mid)
            result["archived"] += 1
            result["details"].append({"mentorId": str(mid), "ok": True})
        except AppException as e:
            result["skipped"] += 1
            result["details"].append({"mentorId": str(mid), "ok": False, "reason": e.message})
        except Exception:  # noqa: BLE001
            result["skipped"] += 1
            result["details"].append({"mentorId": str(mid), "ok": False, "reason": "不存在或不可归档"})
    return result


# ═══════════ 导师分配 ═══════════

def _stu(db, sid) -> GraduationStudent:
    s = db.get(GraduationStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("毕设学生不存在或不在当前数据范围内")
    return assert_student_access(db, s, "mentor.assignment")


def list_assignments(page: int, page_size: int, mentor_id=None, gd_student_id=None,
                     status=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        q = select(GraduationMentorAssignment).where(
            GraduationMentorAssignment.tenant_id == _tid(),
            GraduationMentorAssignment.gd_student_id.in_(scope_ids or [-1]))
        if mentor_id:
            q = q.where(GraduationMentorAssignment.mentor_id == int(mentor_id))
        if gd_student_id:
            q = q.where(GraduationMentorAssignment.gd_student_id == int(gd_student_id))
        if status:
            q = q.where(GraduationMentorAssignment.status == status)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(GraduationMentorAssignment.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        items = []
        for a in rows:
            stu = db.get(GraduationStudent, a.gd_student_id)
            mentor = db.get(GraduationMentor, a.mentor_id)
            items.append({
                "id": str(a.id), "gdStudentId": str(a.gd_student_id),
                "studentName": stu.name if stu else "", "studentNo": stu.student_no if stu else "",
                "mentorId": str(a.mentor_id), "mentorName": mentor.teacher_name if mentor else "",
                "previousMentorId": str(a.previous_mentor_id) if a.previous_mentor_id else "",
                "assignSource": a.assign_source, "assignReason": a.assign_reason or "",
                "status": a.status, "statusLabel": ASSIGN_STATUS_LABEL.get(a.status, a.status),
                "assignedBy": a.assigned_by or "", "assignedAt": _iso(a.assigned_at),
                "endedAt": _iso(a.ended_at),
            })
        return items, total


def assign_mentor(gd_student_id, mentor_id, reason: str = None) -> dict:
    with session() as db:
        stu = _stu(db, gd_student_id)
        mentor = _get_mentor(db, mentor_id)
        if mentor.qualification_status != "QUALIFIED":
            raise AppException("DATA_CONFLICT", "仅「已认证」导师可被分配学生")
        if mentor.current_count >= mentor.max_capacity:
            raise AppException("DATA_CONFLICT", f"该导师已满员（{mentor.current_count}/{mentor.max_capacity}）")
        if stu.mentor_id:
            raise AppException("DATA_CONFLICT", "该生已有导师，如需更换请使用「调导师」")
        n, _ = _op()
        a = GraduationMentorAssignment(
            tenant_id=_tid(), gd_student_id=stu.id, mentor_id=mentor.id, assign_source="MANUAL",
            assign_reason=(reason or "").strip(), status="ACTIVE", assigned_by=n,
            assigned_at=datetime.now(timezone.utc))
        db.add(a)
        stu.mentor_id = mentor.id
        stu.advisor_name = mentor.teacher_name
        mentor.current_count += 1
        db.flush()
        _audit(db, "MENTOR_ASSIGN", a.id, "分配导师", detail=f"{stu.name}→{mentor.teacher_name}")
        from app.modules.graduation.services.graduation_risk_service import notify_risk_rescan
        notify_risk_rescan(db, stu.id)
        db.commit()
        return {"id": str(a.id), "gdStudentId": str(stu.id), "mentorId": str(mentor.id),
                "mentorName": mentor.teacher_name, "status": "ACTIVE"}


def change_mentor(gd_student_id, new_mentor_id, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "调导师原因必填且不少于 5 字")
    with session() as db:
        stu = _stu(db, gd_student_id)
        new_mentor = _get_mentor(db, new_mentor_id)
        if new_mentor.qualification_status != "QUALIFIED":
            raise AppException("DATA_CONFLICT", "仅「已认证」导师可被分配学生")
        if new_mentor.current_count >= new_mentor.max_capacity:
            raise AppException("DATA_CONFLICT", f"该导师已满员（{new_mentor.current_count}/{new_mentor.max_capacity}）")
        if not stu.mentor_id:
            raise AppException("DATA_CONFLICT", "该生尚无导师，请使用「分配导师」")
        if stu.mentor_id == new_mentor.id:
            raise AppException("DATA_CONFLICT", "新导师与当前导师相同")
        old_mentor = db.get(GraduationMentor, stu.mentor_id)
        old_active = db.scalars(select(GraduationMentorAssignment).where(
            GraduationMentorAssignment.tenant_id == _tid(),
            GraduationMentorAssignment.gd_student_id == stu.id,
            GraduationMentorAssignment.status == "ACTIVE")).first()
        n, _ = _op()
        now = datetime.now(timezone.utc)
        if old_active:
            old_active.status = "CHANGED"
            old_active.ended_at = now
        if old_mentor and old_mentor.current_count > 0:
            old_mentor.current_count -= 1
        a = GraduationMentorAssignment(
            tenant_id=_tid(), gd_student_id=stu.id, mentor_id=new_mentor.id,
            previous_mentor_id=old_mentor.id if old_mentor else None, assign_source="CHANGE",
            assign_reason=reason.strip(), status="ACTIVE", assigned_by=n, assigned_at=now)
        db.add(a)
        stu.mentor_id = new_mentor.id
        stu.advisor_name = new_mentor.teacher_name
        new_mentor.current_count += 1
        db.flush()
        _audit(db, "MENTOR_ASSIGN", a.id, "调导师", reason.strip(),
               before=old_mentor.teacher_name if old_mentor else "", after=new_mentor.teacher_name)
        db.commit()
        return {"id": str(a.id), "gdStudentId": str(stu.id), "mentorId": str(new_mentor.id),
                "mentorName": new_mentor.teacher_name, "status": "ACTIVE"}


def cancel_assignment(assignment_id, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "取消原因必填且不少于 5 字")
    with session() as db:
        a = db.get(GraduationMentorAssignment, int(assignment_id))
        if not a or a.tenant_id != _tid():
            raise not_found("分配记录不存在")
        if a.status != "ACTIVE":
            raise AppException("DATA_CONFLICT", "仅「生效中」分配可取消")
        stu = db.get(GraduationStudent, a.gd_student_id)
        assert_student_access(db, stu, "mentor.assignment.cancel")
        mentor = db.get(GraduationMentor, a.mentor_id)
        a.status = "CANCELLED"
        a.ended_at = datetime.now(timezone.utc)
        if stu and stu.mentor_id == a.mentor_id:
            stu.mentor_id = None
            stu.advisor_name = None
        if mentor and mentor.current_count > 0:
            mentor.current_count -= 1
        _audit(db, "MENTOR_ASSIGN", a.id, "取消分配", reason.strip())
        db.commit()
        return {"id": str(a.id), "status": "CANCELLED"}


def unassigned_students(page: int, page_size: int, keyword=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        q = select(GraduationStudent).where(GraduationStudent.tenant_id == _tid(),
                                            GraduationStudent.is_deleted.is_(False),
                                            GraduationStudent.mentor_id.is_(None),
                                            GraduationStudent.record_status == "ACTIVE",
                                            GraduationStudent.id.in_(scope_ids or [-1]))
        if keyword:
            like = f"%{keyword.strip()}%"
            q = q.where(or_(GraduationStudent.name.like(like), GraduationStudent.student_no.like(like)))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(GraduationStudent.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        items = [{"id": str(s.id), "name": s.name, "studentNo": s.student_no or "",
                 "className": s.class_name or "", "topicTitle": s.topic_title or "（未确认选题）",
                 "stage": s.stage} for s in rows]
        return items, total


# ═══════════ 统计 ═══════════

def mentor_stats(batch_id=None) -> dict:
    with session() as db:
        base = [GraduationMentor.tenant_id == _tid(), GraduationMentor.is_deleted.is_(False)]
        total = int(db.scalar(select(func.count()).select_from(GraduationMentor).where(*base)) or 0)
        by_status = [{"status": s, "label": QUAL_LABEL[s],
                      "count": int(db.scalar(select(func.count()).select_from(GraduationMentor).where(
                          *base, GraduationMentor.qualification_status == s)) or 0)} for s in QUAL_LABEL]
        qualified = db.scalars(select(GraduationMentor).where(
            *base, GraduationMentor.qualification_status == "QUALIFIED")).all()
        full_count = sum(1 for m in qualified if m.current_count >= m.max_capacity)
        total_capacity = sum(m.max_capacity for m in qualified)
        total_assigned = sum(m.current_count for m in qualified)
        scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
        unassigned_total = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
            GraduationStudent.mentor_id.is_(None), GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.id.in_(scope_ids or [-1]))) or 0)
        return {"total": total, "byStatus": by_status, "qualifiedCount": len(qualified),
                "fullCapacityCount": full_count, "totalCapacity": total_capacity,
                "totalAssigned": total_assigned, "unassignedStudents": unassigned_total,
                "batchId": str(batch_id) if batch_id else None}


# ═══════════ Excel：导师名单导入 + 台账/工作量导出 ═══════════

def _import_dup_check(rows: list[dict]) -> dict:
    with session() as db:
        existing = {m.teacher_no for m in db.scalars(select(GraduationMentor).where(
            GraduationMentor.tenant_id == _tid(), GraduationMentor.is_deleted.is_(False)))}
    errors = {}
    for i, row in enumerate(rows):
        no = (row.get("teacherNo") or "").strip()
        if no and no in existing:
            errors.setdefault(i, []).append(f"教师工号已存在：{no}")
    return errors


def _persist_import_mentors(rows: list[dict]) -> dict:
    created = 0
    with session() as db:
        for row in rows:
            m = GraduationMentor(
                tenant_id=_tid(), teacher_no=(row.get("teacherNo") or "").strip(),
                teacher_name=(row.get("teacherName") or "").strip(),
                mentor_type=row.get("mentorType") or "INTERNAL", title=row.get("title"),
                college_name=row.get("collegeName"), major_name=row.get("majorName"),
                research_direction=row.get("researchDirection"),
                max_capacity=int(row.get("maxCapacity") or 8),
                qualification_status="PENDING_REVIEW")
            db.add(m)
            db.flush()
            _audit(db, "MENTOR", m.id, "导入申报导师")
            created += 1
        db.commit()
        return {"created": created}


MENTOR_TYPE_IMPORT = ["校内导师", "企业导师", "双导师"]
_TYPE_IMPORT_MAP = {"校内导师": "INTERNAL", "企业导师": "ENTERPRISE", "双导师": "DUAL"}


def _import_transform(row: dict) -> dict:
    row["mentorType"] = _TYPE_IMPORT_MAP.get(row.get("mentorType"), row.get("mentorType") or "INTERNAL")
    return row


def build_import_spec() -> excel.ImportSpec:
    C = excel.ColumnSpec
    return excel.ImportSpec(
        module_key="graduationDesign", biz_type="gd-mentor", template_name="导师名单导入",
        columns=[
            C("teacherNo", "教师工号", required=True, unique_in_file=True, max_length=50, example="T2026001"),
            C("teacherName", "教师姓名", required=True, max_length=100, example="王芳"),
            C("mentorType", "导师类型", type="enum", options=MENTOR_TYPE_IMPORT, example="校内导师"),
            C("title", "职称", max_length=50, example="副教授"),
            C("collegeName", "所属学院", max_length=100, example="信息工程学院"),
            C("majorName", "所属专业", max_length=100, example="软件技术"),
            C("researchDirection", "指导方向", max_length=300, example="Web 开发/嵌入式"),
            C("maxCapacity", "最大指导人数", type="int", example="8"),
        ],
        notes=["1. 只导入「导入模板」页；第一行表头请勿改动。",
               "2. 带 * 为必填：教师工号、教师姓名。",
               "3. 教师工号租户内唯一。",
               "4. 导入后默认「待审核」，需在导师管理中审核通过才能被分配学生。"],
        duplicate_check=_import_dup_check,
        transform_row=_import_transform,
        persist_rows=_persist_import_mentors,
        permission_key="graduationDesign.mentor.import",
        audit_action="导入毕设导师名单",
    )


def build_export_spec() -> excel.ExportSpec:
    C = excel.ColumnSpec
    return excel.ExportSpec(
        module_key="graduationDesign", biz_type="gd-mentor", sheet_title="导师名单与工作量台账",
        file_name="导师名单与工作量台账.xlsx",
        columns=[
            C("teacherNo", "教师工号"), C("teacherName", "教师姓名"),
            C("mentorTypeLabel", "导师类型"), C("title", "职称"), C("collegeName", "学院"),
            C("majorName", "专业"), C("researchDirection", "指导方向"),
            C("capacityText", "工作量(已指导/上限)"), C("qualificationLabel", "资格状态"),
            C("updatedAt", "更新时间"),
        ],
    )


def import_template_bytes() -> bytes:
    return excel.build_template(build_import_spec())


def import_read(content: bytes) -> list[dict]:
    return excel.read_upload(build_import_spec(), content)


def import_errors_pack(rows: list[dict], errors: list[dict]) -> dict:
    return excel.build_error_rows(build_import_spec(), rows, errors)


def import_dry_run(rows: list[dict]) -> dict:
    return excel.pre_validate(build_import_spec(), rows)


def import_confirm(rows: list[dict]) -> dict:
    spec = build_import_spec()
    pre = excel.pre_validate(spec, rows)
    result = excel.confirm_import(spec, rows)
    excel.job_service.record_import(spec.module_key, spec.biz_type, pre=pre,
                                    result=result, status="IMPORTED")
    return {"created": result.get("created", 0)}


def export_mentors_xlsx(keyword=None, qualification_status=None, mentor_type=None) -> dict:
    items, _ = list_mentors(1, 100000, keyword=keyword, qualification_status=qualification_status,
                            mentor_type=mentor_type)
    user = get_current_user_ctx() or {}
    return excel.build_export(build_export_spec(), items, operator_name=user.get("realName") or "系统")
