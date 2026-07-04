"""毕业设计域真实数据服务。租户过滤 + 脱敏 + 审计留痕 + 开题批阅/答辩发布闭环。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (GraduationAuditTrail, GraduationDefenseGroup, GraduationFinal,
                        GraduationProposal, GraduationStudent, GraduationTopic)
from app.services.db_service import _iso, _mask_phone, _tid, session

L_STAGE = {"TOPIC_SELECTING": "选题中", "TASKBOOK_CONFIRM": "任务书确认", "GUIDING": "指导中",
           "MIDTERM": "中期检查", "FINAL_CHECK": "成果检查", "DEFENSE": "答辩中", "ARCHIVED": "已归档"}
L_RISK = {"NONE": "无风险", "LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}
L_MAT = {"PENDING_REVIEW": "待审阅", "APPROVED": "已通过", "REJECTED": "已驳回", "NOT_SUBMITTED": "未提交"}
L_TOPIC = {"CONFIRMED": "已确认", "PENDING_CONFIRM": "待确认", "DISABLED": "已停用"}


def _op():
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("currentRoleCode") or ""


def _audit(db, bt, bid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type=bt, biz_id=str(bid), action=action,
                                operator=n, role_name=r, detail=detail, before_val=before,
                                after_val=after, occurred_at=datetime.utcnow()))


def _page(items, page, ps):
    total = len(items)
    start = (max(1, page) - 1) * ps
    return items[start:start + ps], total


def _stu_of(db, sid):
    return db.get(GraduationStudent, sid)


def _stu_row(s: GraduationStudent) -> dict:
    return {"id": str(s.id), "studentId": str(s.student_id or s.id), "name": s.name,
            "studentNo": s.student_no or "", "className": s.class_name or "", "classId": s.class_id or "",
            "topicTitle": s.topic_title or "（未确认选题）", "topicSource": s.topic_source or "",
            "advisorName": s.advisor_name or "", "stage": s.stage,
            "stageLabel": L_STAGE.get(s.stage, s.stage), "materialSummary": s.material_summary or "",
            "plagiarismRate": s.plagiarism_rate or "—",
            "plagiarismTone": "danger" if (s.plagiarism_rate and _rate_over(s.plagiarism_rate)) else "success",
            "riskLevel": s.risk_level, "riskLabel": L_RISK.get(s.risk_level, s.risk_level),
            "phone": _mask_phone(s.phone_encrypted), "recordStatus": s.record_status,
            "updateTime": _iso(s.updated_at)}


def _rate_over(r, threshold=30):
    try:
        return float(str(r).replace("%", "")) > threshold
    except ValueError:
        return False


# ═══ 学生 ═══

def list_students(page, ps, keyword=None, class_id=None, stage=None, risk_level=None):
    with session() as db:
        q = select(GraduationStudent).where(GraduationStudent.tenant_id == _tid(),
                                            GraduationStudent.is_deleted.is_(False),
                                            GraduationStudent.record_status == "ACTIVE")
        if class_id:
            q = q.where(GraduationStudent.class_id == class_id)
        if stage:
            q = q.where(GraduationStudent.stage == stage)
        if risk_level:
            q = q.where(GraduationStudent.risk_level == risk_level)
        rows = db.scalars(q.order_by(GraduationStudent.id)).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.name or "") or kw in (r.student_no or "") or kw in (r.topic_title or "")]
        return _page([_stu_row(r) for r in rows], page, ps)


def get_student_detail(sid) -> dict:
    with session() as db:
        s = _stu_of(db, int(sid))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("毕设记录不存在或不在当前数据范围内")
        props = db.scalars(select(GraduationProposal).where(GraduationProposal.tenant_id == _tid(),
                           GraduationProposal.gd_student_id == s.id).order_by(GraduationProposal.id.desc())).all()
        finals = db.scalars(select(GraduationFinal).where(GraduationFinal.tenant_id == _tid(),
                            GraduationFinal.gd_student_id == s.id).order_by(GraduationFinal.id.desc())).all()
        logs = db.scalars(select(GraduationAuditTrail).where(GraduationAuditTrail.tenant_id == _tid(),
                          GraduationAuditTrail.biz_id == str(s.id)).order_by(GraduationAuditTrail.id.desc()).limit(20)).all()
        return {"student": _stu_row(s),
                "proposals": [{"id": str(p.id), "type": "开题报告", "version": p.version or "",
                               "submitAt": _iso(p.submit_at) or "", "status": p.status,
                               "statusLabel": L_MAT.get(p.status, p.status), "reviewer": p.reviewer or ""}
                              for p in props],
                "midterm": {"conclusion": s.midterm_conclusion or "—"},
                "finals": [{"id": str(f.id), "type": f.final_type, "version": f.version or "",
                            "submitAt": _iso(f.submit_at) or "", "status": f.status,
                            "statusLabel": L_MAT.get(f.status, f.status),
                            "plagiarism": f.plagiarism_status or "—"} for f in finals],
                "defense": {"group": s.defense_group or "待分组"},
                "auditTrail": [{"who": x.operator or "系统", "time": _iso(x.occurred_at),
                                "action": x.action, "affected": x.detail or ""} for x in logs]}


# ═══ 选题 ═══

def list_topics(page, ps, keyword=None, status=None):
    with session() as db:
        q = select(GraduationTopic).where(GraduationTopic.tenant_id == _tid(),
                                          GraduationTopic.is_deleted.is_(False))
        if status:
            q = q.where(GraduationTopic.status == status)
        rows = db.scalars(q.order_by(GraduationTopic.id)).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.title or "")]
        items = [{"id": str(t.id), "title": t.title, "source": t.source or "",
                  "advisorName": t.advisor_name or "", "majorName": t.major_name or "",
                  "capacity": t.capacity, "selected": t.selected, "status": t.status,
                  "statusLabel": L_TOPIC.get(t.status, t.status), "students": t.students_json or [],
                  "disabledNote": t.disabled_note or ""} for t in rows]
        return _page(items, page, ps)


# ═══ 开题 ═══

def _prop_row(p: GraduationProposal, stu=None) -> dict:
    return {"id": str(p.id), "projectId": str(p.gd_student_id),
            "studentName": stu.name if stu else "", "className": stu.class_name if stu else "",
            "topicTitle": stu.topic_title if stu else "", "advisorName": stu.advisor_name if stu else "",
            "version": p.version or "—", "isResubmit": p.is_resubmit, "submitAt": _iso(p.submit_at) or "",
            "attachments": len(p.attachments_json or []), "status": p.status,
            "statusLabel": L_MAT.get(p.status, p.status)}


def list_proposals(page, ps, keyword=None, status=None):
    with session() as db:
        q = select(GraduationProposal).where(GraduationProposal.tenant_id == _tid(),
                                             GraduationProposal.is_deleted.is_(False))
        if status:
            q = q.where(GraduationProposal.status == status)
        rows = db.scalars(q.order_by(GraduationProposal.id.desc())).all()
        items = []
        for p in rows:
            stu = _stu_of(db, p.gd_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_prop_row(p, stu))
        return _page(items, page, ps)


def get_proposal_detail(pid) -> dict:
    with session() as db:
        p = db.get(GraduationProposal, int(pid))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("开题材料不存在")
        stu = _stu_of(db, p.gd_student_id)
        logs = db.scalars(select(GraduationAuditTrail).where(GraduationAuditTrail.tenant_id == _tid(),
                          GraduationAuditTrail.biz_type == "PROPOSAL",
                          GraduationAuditTrail.biz_id == str(p.id)).order_by(GraduationAuditTrail.id)).all()
        row = _prop_row(p, stu)
        row.update({"content": {"background": p.background or "", "plan": p.plan or "",
                                "outcome": p.outcome or ""},
                    "attachmentsList": p.attachments_json or [], "reviewComment": p.review_comment or "",
                    "trail": [{"who": x.operator or "系统", "time": _iso(x.occurred_at),
                               "action": x.action, "affected": x.detail or ""} for x in logs]})
        return row


def review_proposal(pid, action, comment=None) -> dict:
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and (not comment or len(comment.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    with session() as db:
        p = db.get(GraduationProposal, int(pid))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("开题材料不存在")
        if p.status in ("APPROVED", "REJECTED"):
            raise AppException("DATA_CONFLICT", "该开题已批阅，请刷新")
        before = p.status
        n, _ = _op()
        target = "APPROVED" if action == "APPROVE" else "REJECTED"
        p.status = target
        p.reviewer = n
        p.review_comment = (comment or "").strip()
        p.review_time = datetime.utcnow()
        p.version = p.version or "v1"
        _audit(db, "PROPOSAL", p.id, "批阅开题-" + ("通过" if action == "APPROVE" else "驳回"),
               (comment or "").strip(), before, target)
        # 开题通过推进学生阶段
        stu = _stu_of(db, p.gd_student_id)
        if stu and action == "APPROVE" and stu.stage in ("TOPIC_SELECTING", "TASKBOOK_CONFIRM"):
            stu.stage = "GUIDING"
        db.commit()
        return {"id": str(p.id), "status": target, "statusLabel": L_MAT.get(target, target)}


# ═══ 成果 ═══

def _final_row(f: GraduationFinal, stu=None) -> dict:
    return {"id": str(f.id), "projectId": str(f.gd_student_id),
            "studentName": stu.name if stu else "", "className": stu.class_name if stu else "",
            "topicTitle": stu.topic_title if stu else "", "advisorName": stu.advisor_name if stu else "",
            "type": f.final_type, "version": f.version or "", "submitAt": _iso(f.submit_at) or "",
            "plagiarismRate": f.plagiarism_rate or "—", "plagiarismStatus": f.plagiarism_status or "未检测",
            "plagiarismTone": "danger" if _rate_over(f.plagiarism_rate) else "success",
            "status": f.status, "statusLabel": L_MAT.get(f.status, f.status)}


def list_finals(page, ps, keyword=None, status=None):
    with session() as db:
        q = select(GraduationFinal).where(GraduationFinal.tenant_id == _tid(),
                                          GraduationFinal.is_deleted.is_(False))
        if status:
            q = q.where(GraduationFinal.status == status)
        rows = db.scalars(q.order_by(GraduationFinal.id.desc())).all()
        items = []
        for f in rows:
            stu = _stu_of(db, f.gd_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_final_row(f, stu))
        return _page(items, page, ps)


def review_final(fid, action, comment=None) -> dict:
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and (not comment or len(comment.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    with session() as db:
        f = db.get(GraduationFinal, int(fid))
        if not f or f.is_deleted or f.tenant_id != _tid():
            raise not_found("成果不存在")
        if f.status in ("APPROVED", "REJECTED"):
            raise AppException("DATA_CONFLICT", "该成果已批阅，请刷新")
        before = f.status
        n, _ = _op()
        target = "APPROVED" if action == "APPROVE" else "REJECTED"
        f.status = target
        f.reviewer = n
        f.review_comment = (comment or "").strip()
        f.review_time = datetime.utcnow()
        _audit(db, "FINAL", f.id, "批阅成果-" + ("通过" if action == "APPROVE" else "驳回"),
               (comment or "").strip(), before, target)
        db.commit()
        return {"id": str(f.id), "status": target, "statusLabel": L_MAT.get(target, target)}


# ═══ 答辩 ═══

def _def_row(g: GraduationDefenseGroup) -> dict:
    return {"id": str(g.id), "groupName": g.group_name, "date": g.defense_date or "待定",
            "location": g.location or "待定", "chair": g.chair or "待指定",
            "members": g.members_json or [], "secretary": g.secretary or "待指定",
            "studentCount": g.student_count, "conflict": g.conflict or "",
            "published": g.published,
            "publishedLabel": "已发布（学生端 P17 可见）" if g.published else "待调整后发布"}


def list_defense_groups(page, ps, keyword=None):
    with session() as db:
        rows = db.scalars(select(GraduationDefenseGroup).where(
            GraduationDefenseGroup.tenant_id == _tid(),
            GraduationDefenseGroup.is_deleted.is_(False)).order_by(GraduationDefenseGroup.id)).all()
        items = [_def_row(g) for g in rows]
        if keyword:
            kw = keyword.strip()
            items = [i for i in items if kw in i["groupName"]]
        return _page(items, page, ps)


def publish_defense(gid) -> dict:
    with session() as db:
        g = db.get(GraduationDefenseGroup, int(gid))
        if not g or g.is_deleted or g.tenant_id != _tid():
            raise not_found("答辩组不存在")
        if g.conflict:
            raise AppException("VALIDATION_ERROR", "存在评委与导师冲突，调整评委后方可发布")
        if (g.chair or "待指定") == "待指定" or (g.location or "待定") == "待定":
            raise AppException("VALIDATION_ERROR", "评委或地点未安排完整，暂不能发布")
        g.published = True
        g.version += 1
        _audit(db, "DEFENSE", g.id, "发布答辩安排", g.group_name)
        db.commit()
        return {"id": str(g.id), "published": True}


# ═══ 审计 + 看板 ═══

def list_audit(page, ps, biz_type=None, keyword=None):
    with session() as db:
        q = select(GraduationAuditTrail).where(GraduationAuditTrail.tenant_id == _tid())
        if biz_type:
            q = q.where(GraduationAuditTrail.biz_type == biz_type)
        rows = db.scalars(q.order_by(GraduationAuditTrail.id.desc())).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.action or "") or kw in (r.detail or "")]
        items = [{"id": str(x.id), "time": _iso(x.occurred_at), "operator": x.operator or "",
                  "roleName": x.role_name or "", "bizType": x.biz_type, "bizId": x.biz_id or "",
                  "action": x.action, "detail": x.detail or "", "before": x.before_val or "",
                  "after": x.after_val or ""} for x in rows]
        return _page(items, page, ps)


def get_dashboard() -> dict:
    with session() as db:
        total = db.scalar(select(func.count()).select_from(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE")) or 0
        pend_prop = db.scalar(select(func.count()).select_from(GraduationProposal).where(
            GraduationProposal.tenant_id == _tid(), GraduationProposal.status == "PENDING_REVIEW",
            GraduationProposal.is_deleted.is_(False))) or 0
        pend_final = db.scalar(select(func.count()).select_from(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(), GraduationFinal.status == "PENDING_REVIEW",
            GraduationFinal.is_deleted.is_(False))) or 0
        high_risk = db.scalar(select(func.count()).select_from(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.risk_level == "HIGH",
            GraduationStudent.is_deleted.is_(False))) or 0
        flow = {}
        for s in db.scalars(select(GraduationStudent).where(GraduationStudent.tenant_id == _tid(),
                            GraduationStudent.is_deleted.is_(False))).all():
            flow[s.stage] = flow.get(s.stage, 0) + 1
        return {"batchName": "2026 届毕业设计批次", "batchRange": "2025-11-01 ~ 2026-06-30",
                "batchStatus": "进行中",
                "stats": [
                    {"label": "毕设学生", "value": str(total), "trend": "", "trendQuality": "neutral"},
                    {"label": "开题待审阅", "value": str(pend_prop),
                     "trend": f"待批 {pend_prop}", "trendQuality": "bad" if pend_prop else "good"},
                    {"label": "成果待审阅", "value": str(pend_final),
                     "trend": f"待批 {pend_final}", "trendQuality": "neutral"},
                    {"label": "高风险学生", "value": str(high_risk),
                     "trend": "", "trendQuality": "bad" if high_risk else "good"},
                ],
                "flow": [{"label": L_STAGE[k], "value": flow.get(k, 0), "active": k == "FINAL_CHECK"}
                         for k in L_STAGE],
                "todos": [
                    {"id": "t1", "label": "开题材料待审阅", "count": pend_prop, "tone": "danger",
                     "route": "/admin/graduation/proposals"},
                    {"id": "t2", "label": "成果待审阅", "count": pend_final, "tone": "warning",
                     "route": "/admin/graduation/finals"},
                ],
                "riskAlerts": []}
