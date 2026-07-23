"""毕业设计中心 · 毕设学生服务（生产级，DB_ENABLED=true 走本模块）。

核心：把毕设学生 t_gd_student 与毕设批次(t_gd_batch)/选题库(t_gd_topic)真实打通——
学生-选题分配闭环让选题库 selected 变为真实值；再叠加节点状态机 + 风险 + 统计 + Excel 导入导出。
横切：租户隔离 + is_deleted 软删 + 手机号脱敏 + 审计 t_gd_audit_trail(biz_type=STUDENT)。
数据范围（预留）：默认按租户；毕设导师限本人指导学生，接 resolve_teacher_scope。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (GraduationAuditTrail, GraduationBatch, GraduationDefenseGroup, GraduationFinal,
                        GraduationMidterm, GraduationPlagiarismCheck, GraduationProposal, GraduationReview,
                        GraduationStudent, GraduationTopic, StudentContact, StudentProfile)
from app.services import excel
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access, can_access_student
from app.services.db_service import _iso, _mask_phone, _tid, session

STAGE_LABEL = {
    "TOPIC_SELECTING": "选题中", "TASKBOOK_CONFIRM": "任务书确认", "GUIDING": "指导中",
    "MIDTERM": "中期检查", "FINAL_CHECK": "成果检查", "DEFENSE": "答辩中", "COMPLETED": "已完成",
    "ARCHIVED": "已归档",
}
STAGE_TONE = {
    "TOPIC_SELECTING": "default", "TASKBOOK_CONFIRM": "info", "GUIDING": "processing",
    "MIDTERM": "warning", "FINAL_CHECK": "processing", "DEFENSE": "warning", "COMPLETED": "info",
    "ARCHIVED": "success",
}
# COMPLETED 位于 DEFENSE 与 ARCHIVED 之间：成绩发布后（graduation_grade_service.publish_grade）自动置为
# COMPLETED，撤回成绩（withdraw_grade）退回 DEFENSE；不可通过通用 ADVANCE 手动跨越，见 set_stage() 的拦截。
STAGE_ORDER = ["TOPIC_SELECTING", "TASKBOOK_CONFIRM", "GUIDING", "MIDTERM", "FINAL_CHECK", "DEFENSE",
              "COMPLETED", "ARCHIVED"]
RISK_LABEL = {"NONE": "无", "LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}
ELIG_LABEL = {"PENDING": "待认定", "QUALIFIED": "资格合格", "UNQUALIFIED": "资格不合格"}
ELIG_TONE = {"PENDING": "warning", "QUALIFIED": "success", "UNQUALIFIED": "danger"}
GRAD_QUAL_LABEL = {"UNKNOWN": "未联动", "NONE": "未预审", "PENDING": "预审中",
                   "PASS": "毕业资格通过", "FAIL": "毕业资格不通过"}
GRAD_QUAL_TONE = {"UNKNOWN": "default", "NONE": "default", "PENDING": "warning",
                  "PASS": "success", "FAIL": "danger"}
MAT_LABEL = {"PENDING_REVIEW": "待审阅", "APPROVED": "已通过", "REJECTED": "已驳回", "NOT_SUBMITTED": "未提交"}


def _midterm_summary(db, s: GraduationStudent) -> dict:
    """学生详情中期摘要：读真实中期行，不用从未写入的 denormalized 字段冒充。"""
    from app.modules.graduation.services.graduation_midterm_service import CONCLUSION_LABEL, STATUS_LABEL
    mid = db.scalars(select(GraduationMidterm).where(
        GraduationMidterm.tenant_id == _tid(),
        GraduationMidterm.gd_student_id == s.id,
        GraduationMidterm.is_deleted.is_(False),
    ).order_by(GraduationMidterm.id.desc())).first()
    if not mid:
        return {"conclusion": "—", "status": "", "statusLabel": "未开始", "time": "—", "note": ""}
    conclusion = CONCLUSION_LABEL.get(mid.conclusion or "", "") or mid.conclusion or "—"
    return {
        "conclusion": conclusion,
        "status": mid.status or "",
        "statusLabel": STATUS_LABEL.get(mid.status or "", mid.status or ""),
        "time": _iso(mid.reviewed_at) or _iso(mid.checked_at) or "—",
        "note": (mid.review_comment or mid.check_comment or "").strip(),
    }


def _op() -> tuple[str, str]:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("roleName") or ""


def _audit(db, sid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type="STUDENT", biz_id=str(sid), action=action,
                                operator=n, role_name=r, detail=detail, before_val=before,
                                after_val=after, occurred_at=datetime.utcnow()))


def _get(db, sid) -> GraduationStudent:
    s = db.get(GraduationStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid() or s.record_status != "ACTIVE":
        raise not_found("毕设学生记录不存在或不在当前数据范围内")
    return s


def _get_for_update(db, sid) -> GraduationStudent:
    s = db.scalars(select(GraduationStudent).where(
        GraduationStudent.id == int(sid),
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
    ).with_for_update()).first()
    if not s:
        raise not_found("毕设学生记录不存在或不在当前数据范围内")
    return s


def _rate_over(r, threshold=30):
    try:
        return float(str(r).replace("%", "")) > threshold
    except ValueError:
        return False


def _material_snapshot(db, sid: int) -> dict:
    prop = db.scalars(select(GraduationProposal).where(
        GraduationProposal.tenant_id == _tid(), GraduationProposal.gd_student_id == sid,
        GraduationProposal.is_deleted.is_(False)).order_by(GraduationProposal.id.desc())).first()
    final = db.scalars(select(GraduationFinal).where(
        GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == sid,
        GraduationFinal.is_deleted.is_(False)).order_by(GraduationFinal.id.desc())).first()
    prop_st = prop.status if prop else "NOT_SUBMITTED"
    final_st = final.status if final else "NOT_SUBMITTED"
    gaps = []
    if prop_st != "APPROVED":
        gaps.append("开题")
    if final_st != "APPROVED":
        gaps.append("成果")
    return {
        "proposalStatus": prop_st, "proposalStatusLabel": MAT_LABEL.get(prop_st, prop_st),
        "finalStatus": final_st, "finalStatusLabel": MAT_LABEL.get(final_st, final_st),
        "materialGap": "、".join(gaps) if gaps else "齐全",
        "materialComplete": len(gaps) == 0,
    }


def _row(s: GraduationStudent, batch: GraduationBatch | None = None, material: dict | None = None) -> dict:
    mat = material or {}
    return {
        "id": str(s.id), "studentId": str(s.student_id or s.id), "name": s.name,
        "studentNo": s.student_no or "", "className": s.class_name or "", "classId": s.class_id or "",
        "batchId": str(s.batch_id) if s.batch_id else "",
        "batchName": batch.batch_name if batch else "",
        "topicId": str(s.topic_id) if s.topic_id else "",
        "topicTitle": s.topic_title or "（未确认选题）", "topicSource": s.topic_source or "",
        "advisorName": s.advisor_name or "", "stage": s.stage,
        "stageLabel": STAGE_LABEL.get(s.stage, s.stage), "stageTone": STAGE_TONE.get(s.stage, "default"),
        "materialSummary": s.material_summary or mat.get("materialGap", "—"),
        "proposalStatus": mat.get("proposalStatus", "NOT_SUBMITTED"),
        "proposalStatusLabel": mat.get("proposalStatusLabel", "未提交"),
        "finalStatus": mat.get("finalStatus", "NOT_SUBMITTED"),
        "finalStatusLabel": mat.get("finalStatusLabel", "未提交"),
        "materialGap": mat.get("materialGap", "—"),
        "materialComplete": mat.get("materialComplete", False),
        "plagiarismRate": s.plagiarism_rate or "—",
        "plagiarismTone": "danger" if (s.plagiarism_rate and _rate_over(s.plagiarism_rate)) else "success",
        "riskLevel": s.risk_level, "riskLabel": RISK_LABEL.get(s.risk_level, s.risk_level),
        "eligibilityStatus": getattr(s, "eligibility_status", "PENDING") or "PENDING",
        "eligibilityLabel": ELIG_LABEL.get(getattr(s, "eligibility_status", "PENDING") or "PENDING", "待认定"),
        "eligibilityTone": ELIG_TONE.get(getattr(s, "eligibility_status", "PENDING") or "PENDING", "warning"),
        "studentGroup": s.student_group or "",
        "defenseGroupId": str(s.defense_group_id) if getattr(s, "defense_group_id", None) else "",
        "defenseGroup": s.defense_group or "",
        "gradQualStatus": getattr(s, "grad_qual_status", "UNKNOWN") or "UNKNOWN",
        "gradQualLabel": GRAD_QUAL_LABEL.get(getattr(s, "grad_qual_status", "UNKNOWN") or "UNKNOWN", "未联动"),
        "gradQualTone": GRAD_QUAL_TONE.get(getattr(s, "grad_qual_status", "UNKNOWN") or "UNKNOWN", "default"),
        "gradQualNote": getattr(s, "grad_qual_note", None) or "",
        "phone": _mask_phone(s.phone_encrypted), "recordStatus": s.record_status,
        "updatedAt": _iso(s.updated_at),
    }


def _row_of(db, s: GraduationStudent) -> dict:
    batch = db.get(GraduationBatch, s.batch_id) if s.batch_id else None
    return _row(s, batch if batch and not batch.is_deleted else None, _material_snapshot(db, s.id))


def _state_flow(stage: str) -> list[dict]:
    labels = {
        "TOPIC_SELECTING": "选题确认", "TASKBOOK_CONFIRM": "任务书确认", "GUIDING": "开题指导",
        "MIDTERM": "中期检查", "FINAL_CHECK": "成果检查", "DEFENSE": "答辩与成绩", "COMPLETED": "已完成",
        "ARCHIVED": "归档",
    }
    idx = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else 0
    flow = []
    for i, code in enumerate(STAGE_ORDER):
        if code == "ARCHIVED" and stage != "ARCHIVED":
            continue
        tone = "default"
        time = "未到达"
        if i < idx:
            tone, time = "success", "已完成"
        elif i == idx:
            tone = "processing" if stage != "ARCHIVED" else "success"
            time = "当前" if stage != "ARCHIVED" else "已归档"
        flow.append({"title": labels.get(code, code), "time": time, "tone": tone})
    return flow


# ═══════════ 列表 / 详情 ═══════════

def list_students(page: int, page_size: int, keyword=None, class_id=None, batch_id=None,
                  stage=None, risk_level=None, advisor_name=None, has_topic=None,
                  eligibility=None, student_group=None, has_defense_group=None,
                  grad_qual_status=None, material_complete=None, archive_view=None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(GraduationStudent).where(GraduationStudent.tenant_id == _tid(),
                                            GraduationStudent.is_deleted.is_(False),
                                            GraduationStudent.record_status == "ACTIVE")
        if class_id:
            q = q.where(GraduationStudent.class_id == class_id)
        if batch_id:
            q = q.where(GraduationStudent.batch_id == int(batch_id))
        if stage:
            q = q.where(GraduationStudent.stage == stage)
        if risk_level:
            q = q.where(GraduationStudent.risk_level == risk_level)
        if advisor_name:
            q = q.where(GraduationStudent.advisor_name == advisor_name)
        if has_topic is True:
            q = q.where(GraduationStudent.topic_id.is_not(None))
        elif has_topic is False:
            q = q.where(GraduationStudent.topic_id.is_(None))
        if eligibility:
            q = q.where(GraduationStudent.eligibility_status == eligibility)
        if student_group:
            q = q.where(GraduationStudent.student_group == student_group)
        if has_defense_group is True:
            q = q.where(GraduationStudent.defense_group_id.is_not(None))
        elif has_defense_group is False:
            q = q.where(GraduationStudent.defense_group_id.is_(None))
        if grad_qual_status:
            q = q.where(GraduationStudent.grad_qual_status == grad_qual_status)
        if archive_view == "archived":
            q = q.where(GraduationStudent.stage == "ARCHIVED")
        elif archive_view == "candidates":
            q = q.where(GraduationStudent.stage != "ARCHIVED")
        rows = db.scalars(q.order_by(GraduationStudent.id.desc())).all()
        batches = {b.id: b for b in db.scalars(select(GraduationBatch).where(
            GraduationBatch.tenant_id == _tid(), GraduationBatch.is_deleted.is_(False))).all()}
        items = []
        for s in rows:
            if not can_access_student(db, s):
                continue
            if keyword:
                kw = keyword.strip()
                if kw not in (s.name or "") and kw not in (s.student_no or "") and kw not in (s.topic_title or ""):
                    continue
            mat = _material_snapshot(db, s.id)
            if material_complete is True and not mat["materialComplete"]:
                continue
            if material_complete is False and mat["materialComplete"]:
                continue
            items.append(_row(s, batches.get(s.batch_id), mat))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_student(sid) -> dict:
    """详情：主档 + 批次/选题关联 + 开题/成果/查重 + 状态流 + 审计。"""
    with session() as db:
        s = _get(db, sid)
        assert_student_access(db, s, "student.detail")
        batch = db.get(GraduationBatch, s.batch_id) if s.batch_id else None
        topic = db.get(GraduationTopic, s.topic_id) if s.topic_id else None
        props = db.scalars(select(GraduationProposal).where(
            GraduationProposal.tenant_id == _tid(), GraduationProposal.gd_student_id == s.id,
            GraduationProposal.is_deleted.is_(False)).order_by(GraduationProposal.id.desc())).all()
        finals = db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == s.id,
            GraduationFinal.is_deleted.is_(False)).order_by(GraduationFinal.id.desc())).all()
        # 学生详情审计：该生自身事件(STUDENT) + 催交(remind-{id}) + 本人各业务实体
        # (开题/成果/评阅/查重)事件。此前只按 biz_id==student.id 过滤，导致开题/成果批阅
        # (biz_id=提案/成果自身ID)全部漏记。按 (biz_type,biz_id) 精确匹配，避免不同表
        # 主键撞号误纳入他人事件；不含导师库(MENTOR)/答辩组(DEFENSE)等跨学生的组级事件。
        proposal_ids = [str(p.id) for p in props]
        final_ids = [str(f.id) for f in finals]
        review_ids = [str(r) for r in db.scalars(select(GraduationReview.id).where(
            GraduationReview.tenant_id == _tid(), GraduationReview.gd_student_id == s.id,
            GraduationReview.is_deleted.is_(False))).all()]
        plag_ids = [str(p) for p in db.scalars(select(GraduationPlagiarismCheck.id).where(
            GraduationPlagiarismCheck.tenant_id == _tid(), GraduationPlagiarismCheck.gd_student_id == s.id,
            GraduationPlagiarismCheck.is_deleted.is_(False))).all()]
        audit_conds = [
            and_(GraduationAuditTrail.biz_type == "STUDENT", GraduationAuditTrail.biz_id == str(s.id)),
            GraduationAuditTrail.biz_id == f"remind-{s.id}",
        ]
        for biz_type, ids in (("PROPOSAL", proposal_ids), ("FINAL", final_ids),
                              ("REVIEW", review_ids), ("PLAGIARISM", plag_ids)):
            if ids:
                audit_conds.append(and_(GraduationAuditTrail.biz_type == biz_type,
                                        GraduationAuditTrail.biz_id.in_(ids)))
        logs = db.scalars(select(GraduationAuditTrail).where(
            GraduationAuditTrail.tenant_id == _tid(),
            or_(*audit_conds)).order_by(
            GraduationAuditTrail.id.desc()).limit(30)).all()
        base = _row(s, batch if batch and not batch.is_deleted else None, _material_snapshot(db, s.id))
        # 此前按 s.stage 猜任务书状态（非 TOPIC_SELECTING 即判"已确认"），与任务书 tab
        # 的真实查询（GraduationTaskBook 是否存在）矛盾——学生越过任务书环节直接到开题
        # 等阶段时，摘要卡会谎报"已确认"而任务书 tab 如实显示"尚未下达"。改为查真实记录。
        from app.models import GraduationTaskBook
        tb = db.scalars(select(GraduationTaskBook).where(
            GraduationTaskBook.tenant_id == _tid(), GraduationTaskBook.gd_student_id == s.id,
            GraduationTaskBook.is_deleted.is_(False)).order_by(GraduationTaskBook.id.desc())).first()
        _TB_LABEL = {"PENDING_CONFIRM": "任务书待学生确认", "CONFIRMED": "任务书已确认",
                    "CHANGE_PENDING": "任务书变更待确认"}
        taskbook = _TB_LABEL.get(tb.status, "任务书待确认") if tb else "尚未下达任务书"
        return {
            **base,
            "taskbook": taskbook,
            "batch": {"id": str(batch.id), "batchName": batch.batch_name, "status": batch.status}
                      if batch and not batch.is_deleted else None,
            "topic": {"id": str(topic.id), "title": topic.title, "capacity": topic.capacity,
                      "selected": topic.selected, "status": topic.status}
                     if topic and not topic.is_deleted else None,
            "proposals": [{"id": str(p.id), "type": "开题报告", "version": p.version or "",
                           "submitAt": _iso(p.submit_at) or "", "status": p.status,
                           "statusLabel": MAT_LABEL.get(p.status, p.status), "reviewer": p.reviewer or ""}
                          for p in props],
            "midterm": _midterm_summary(db, s),
            "finals": [{"id": str(f.id), "type": f.final_type, "version": f.version or "",
                        "submitAt": _iso(f.submit_at) or "", "status": f.status,
                        "statusLabel": MAT_LABEL.get(f.status, f.status),
                        "plagiarism": f"{f.plagiarism_rate or '—'} · {f.plagiarism_status or '未检测'}"}
                       for f in finals],
            "plagiarisms": [{"id": str(f.id), "version": f"{f.final_type} {f.version or ''}".strip(),
                             "rate": f.plagiarism_rate or "—", "status": f.plagiarism_status or "未检测",
                             "time": _iso(f.submit_at) or "", "report": f"查重报告-{f.version or f.id}.pdf"}
                            for f in finals if f.plagiarism_rate],
            "defense": {"group": s.defense_group or "待分组", "time": "待定", "location": "待定",
                        "secretary": "待指定", "published": False},
            "stateFlow": _state_flow(s.stage),
            "auditTrail": [{"who": x.operator or "系统", "time": _iso(x.occurred_at),
                            "action": x.action, "affected": x.detail or ""} for x in logs],
        }


# ═══════════ 建档 / 编辑 ═══════════

def create_student_record(body) -> dict:
    with session() as db:
        sid = int(body.studentId)
        stu = db.get(StudentProfile, sid)
        if not stu or stu.is_deleted or stu.tenant_id != _tid():
            raise not_found("学生不存在或不在当前数据范围内")
        batch_id = int(body.batchId) if getattr(body, "batchId", None) else None
        if batch_id:
            b = db.get(GraduationBatch, batch_id)
            if not b or b.is_deleted or b.tenant_id != _tid():
                raise not_found("毕设批次不存在")
            if b.status in ("ARCHIVED", "VOIDED"):
                raise AppException("DATA_CONFLICT", "已归档/已作废批次不可建档")
        dup_q = select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.student_id == sid,
            GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE")
        if batch_id:
            dup_q = dup_q.where(GraduationStudent.batch_id == batch_id)
        else:
            dup_q = dup_q.where(GraduationStudent.batch_id.is_(None))
        if db.scalars(dup_q).first():
            raise AppException("DATA_CONFLICT", "该学生在此批次已有毕设记录")
        phone = db.scalars(select(StudentContact).where(
            StudentContact.tenant_id == _tid(), StudentContact.student_id == sid,
            StudentContact.contact_type == "PHONE")).first()
        s = GraduationStudent(
            tenant_id=_tid(), batch_id=batch_id, student_id=sid, student_no=stu.student_no,
            name=stu.real_name, class_id=str(stu.class_id) if stu.class_id else None,
            class_name=f"{stu.grade}级" if stu.grade else None,
            advisor_name=getattr(body, "advisorName", None) or None,
            phone_encrypted=phone.contact_value_encrypted if phone else None,
            stage="TOPIC_SELECTING", risk_level="NONE", eligibility_status="PENDING",
            grad_qual_status="UNKNOWN", record_status="ACTIVE")
        db.add(s)
        db.flush()
        _audit(db, s.id, "CREATE", f"学号 {stu.student_no}")
        db.commit()
        return _row_of(db, s)


def update_student_record(sid, body) -> dict:
    with session() as db:
        s = _get(db, sid)
        assert_student_access(db, s, "student.update")
        if s.stage == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档记录不可编辑")
        if getattr(body, "advisorName", None) is not None:
            s.advisor_name = body.advisorName
        s.version += 1
        _audit(db, s.id, "UPDATE")
        db.commit()
        return _row_of(db, s)


# ═══════════ 学生-选题分配（选题库 selected 收口）═══════════

def assign_topic_in_session(db, sid, topic_id, *, relationship_authorized: bool = False) -> GraduationStudent:
    """Assign under row locks. Caller owns commit, allowing larger workflows to stay atomic."""
    # Lock order is topic -> student across both direct assignment and round matching.
    # A stable order prevents capacity oversubscription and reduces deadlock risk.
    t = db.scalars(select(GraduationTopic).where(
        GraduationTopic.id == int(topic_id),
        GraduationTopic.tenant_id == _tid(),
        GraduationTopic.is_deleted.is_(False),
    ).with_for_update()).first()
    if not t:
        raise not_found("选题不存在或不在当前数据范围内")
    s = _get_for_update(db, sid)
    if not relationship_authorized:
        assert_student_access(db, s, "student.assign_topic")
    if s.stage == "ARCHIVED":
        raise AppException("DATA_CONFLICT", "已归档记录不可分配选题")
    elig = getattr(s, "eligibility_status", None) or "PENDING"
    if elig == "UNQUALIFIED":
        raise AppException(
            "DATA_CONFLICT",
            f"资格不合格学生不能确认选题（当前：{ELIG_LABEL.get(elig, elig)}）",
        )
    if s.topic_id == t.id:
        raise AppException("DATA_CONFLICT", "该学生已分配到此选题")
    if t.status == "DISABLED":
        raise AppException("DATA_CONFLICT", "已停用选题不可分配")
    if getattr(t, "review_status", "APPROVED") != "APPROVED" or t.status != "CONFIRMED":
        raise AppException("DATA_CONFLICT", "仅「已审核入池」选题可分配")
    if int(t.selected or 0) >= int(t.capacity or 0):
        raise AppException("DATA_CONFLICT", "该选题已满员，不能再分配")
    if s.topic_id:
        old = db.scalars(select(GraduationTopic).where(
            GraduationTopic.id == s.topic_id,
            GraduationTopic.tenant_id == _tid(),
        ).with_for_update()).first()
        if old and old.selected > 0:
            old.selected -= 1
            old.version += 1
    s.topic_id = t.id
    s.topic_title = t.title
    s.topic_source = t.source or ""
    if not s.advisor_name and t.advisor_name:
        s.advisor_name = t.advisor_name
    if s.stage == "TOPIC_SELECTING":
        s.stage = "TASKBOOK_CONFIRM"
    t.selected = int(t.selected or 0) + 1
    s.version += 1
    t.version += 1
    _audit(db, s.id, "ASSIGN_TOPIC", t.title, "", str(t.id))
    return s


def assign_topic(sid, topic_id, *, relationship_authorized: bool = False) -> dict:
    with session() as db:
        s = assign_topic_in_session(
            db, sid, topic_id, relationship_authorized=relationship_authorized
        )
        db.commit()
        return _row_of(db, s)


def unassign_topic(sid, reason: str = "") -> dict:
    with session() as db:
        s = _get_for_update(db, sid)
        assert_student_access(db, s, "student.unassign_topic")
        if not s.topic_id:
            raise AppException("DATA_CONFLICT", "该学生未分配选题")
        if s.stage not in ("TOPIC_SELECTING", "TASKBOOK_CONFIRM"):
            raise AppException("DATA_CONFLICT", "已进入指导阶段，不能退选（需走选题调整流程）")
        t = db.scalars(select(GraduationTopic).where(
            GraduationTopic.id == s.topic_id,
            GraduationTopic.tenant_id == _tid(),
        ).with_for_update()).first()
        if t and t.selected > 0:
            t.selected -= 1
            t.version += 1
        s.topic_id = None
        s.topic_title = None
        s.topic_source = None
        s.stage = "TOPIC_SELECTING"
        s.version += 1
        _audit(db, s.id, "UNASSIGN_TOPIC", reason or "退选")
        db.commit()
        return _row_of(db, s)


def assign_advisor(sid, advisor_name: str) -> dict:
    with session() as db:
        s = _get(db, sid)
        assert_student_access(db, s, "student.assign_advisor")
        if s.stage == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档记录不可分配导师")
        before = s.advisor_name or ""
        s.advisor_name = advisor_name.strip()
        _audit(db, s.id, "ASSIGN_ADVISOR", advisor_name, before, s.advisor_name)
        db.commit()
        return _row_of(db, s)


# ═══════════ 状态机 / 风险 ═══════════

def set_stage(sid, action: str, reason: str = "") -> dict:
    """ADVANCE 推进节点；ARCHIVE 归档（需成果已通过或管理员强制）。"""
    with session() as db:
        s = _get(db, sid)
        assert_student_access(db, s, "student.stage")
        if action == "ADVANCE":
            if s.stage == "ARCHIVED":
                raise AppException("DATA_CONFLICT", "已归档不可再推进")
            idx = STAGE_ORDER.index(s.stage)
            if s.stage == "TOPIC_SELECTING":
                raise AppException("DATA_CONFLICT", "未分配选题，不能推进（请先分配选题）")
            if s.stage == "TASKBOOK_CONFIRM" and not s.advisor_name:
                raise AppException("DATA_CONFLICT", "未分配指导教师，不能进入指导阶段")
            if s.stage == "DEFENSE":
                raise AppException("DATA_CONFLICT", "已在答辩阶段，请通过发布成绩推进为「已完成」")
            if s.stage == "COMPLETED":
                raise AppException("DATA_CONFLICT", "已完成，请用归档操作")
            before = s.stage
            s.stage = STAGE_ORDER[idx + 1]
            _audit(db, s.id, "STAGE_ADVANCE", reason or STAGE_LABEL[s.stage], before, s.stage)
        elif action == "ARCHIVE":
            if s.stage == "ARCHIVED":
                raise AppException("DATA_CONFLICT", "已归档")
            before = s.stage
            s.stage = "ARCHIVED"
            _audit(db, s.id, "ARCHIVE", reason or "归档", before, "ARCHIVED")
        else:
            raise AppException("VALIDATION_ERROR", "非法状态动作")
        db.commit()
        return _row_of(db, s)


def set_risk(sid, risk_level: str, reason: str = "") -> dict:
    if risk_level not in RISK_LABEL:
        raise AppException("VALIDATION_ERROR", "非法风险等级")
    with session() as db:
        s = _get(db, sid)
        assert_student_access(db, s, "student.risk")
        before = s.risk_level
        s.risk_level = risk_level
        _audit(db, s.id, "SET_RISK", reason or risk_level, before, risk_level)
        db.commit()
        return _row_of(db, s)


# ═══════════ 资格 / 分组 / 答辩组 / 毕业资格联动 / 归档 ═══════════

def _sync_defense_group_count(db, gid: int | None) -> None:
    if not gid:
        return
    g = db.get(GraduationDefenseGroup, gid)
    if not g or g.is_deleted or g.tenant_id != _tid():
        return
    cnt = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(), GraduationStudent.defense_group_id == gid,
        GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE")) or 0)
    g.student_count = cnt


def set_eligibility(sid, status: str, reason: str = "") -> dict:
    if status not in ELIG_LABEL:
        raise AppException("VALIDATION_ERROR", "非法资格状态")
    with session() as db:
        s = _get(db, sid)
        assert_student_access(db, s, "student.eligibility")
        if s.stage == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档不可修改资格")
        before = s.eligibility_status
        s.eligibility_status = status
        _audit(db, s.id, "ELIGIBILITY", reason or ELIG_LABEL[status], before, status)
        db.commit()
        return _row_of(db, s)


def set_student_group(sid, group_name: str, reason: str = "") -> dict:
    with session() as db:
        s = _get(db, sid)
        assert_student_access(db, s, "student.group")
        if s.stage == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档不可修改分组")
        before = s.student_group or ""
        s.student_group = (group_name or "").strip() or None
        _audit(db, s.id, "SET_GROUP", reason or (s.student_group or "清空分组"), before, s.student_group or "")
        db.commit()
        return _row_of(db, s)


def batch_set_student_group(record_ids: list[str], group_name: str, reason: str = "") -> dict:
    name = (group_name or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "分组名称不能为空")
    updated = 0
    with session() as db:
        for rid in record_ids or []:
            s = _get(db, rid)
            assert_student_access(db, s, "student.batch_group")
            if s.stage == "ARCHIVED":
                continue
            before = s.student_group or ""
            s.student_group = name
            _audit(db, s.id, "SET_GROUP", reason or name, before, name)
            updated += 1
        db.commit()
    return {"updated": updated}


def list_student_groups() -> list[str]:
    with session() as db:
        scope_ids = [int(x) for x in accessible_student_ids(db, _tid())]
        rows = db.scalars(select(GraduationStudent.student_group).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
            GraduationStudent.id.in_(scope_ids or [-1]),
            GraduationStudent.student_group.is_not(None), GraduationStudent.student_group != "")).all()
        return sorted({r for r in rows if r})


def assign_defense_group(sid, group_id: str, reason: str = "") -> dict:
    with session() as db:
        s = _get(db, sid)
        assert_student_access(db, s, "student.defense_group")
        if s.stage == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档不可分配答辩组")
        g = db.get(GraduationDefenseGroup, int(group_id))
        if not g or g.is_deleted or g.tenant_id != _tid():
            raise not_found("答辩组不存在")
        old_gid = s.defense_group_id
        before = s.defense_group or ""
        s.defense_group_id = g.id
        s.defense_group = g.group_name
        if s.stage in ("FINAL_CHECK", "GUIDING", "MIDTERM"):
            s.stage = "DEFENSE"
        _audit(db, s.id, "ASSIGN_DEFENSE_GROUP", reason or g.group_name, before, g.group_name)
        _sync_defense_group_count(db, old_gid)
        _sync_defense_group_count(db, g.id)
        db.commit()
        return _row_of(db, s)


def set_grad_qual(sid, status: str, note: str = "", reason: str = "") -> dict:
    if status not in GRAD_QUAL_LABEL:
        raise AppException("VALIDATION_ERROR", "非法毕业资格联动状态")
    with session() as db:
        s = _get(db, sid)
        assert_student_access(db, s, "student.grad_qualification")
        before = s.grad_qual_status
        s.grad_qual_status = status
        if note is not None:
            s.grad_qual_note = (note or "").strip() or None
        _audit(db, s.id, "GRAD_QUAL", reason or GRAD_QUAL_LABEL[status], before, status)
        db.commit()
        return _row_of(db, s)


def batch_archive(record_ids: list[str], reason: str = "") -> dict:
    archived = 0
    with session() as db:
        for rid in record_ids or []:
            s = _get(db, rid)
            assert_student_access(db, s, "student.batch_archive")
            if s.stage == "ARCHIVED":
                continue
            before = s.stage
            s.stage = "ARCHIVED"
            _audit(db, s.id, "ARCHIVE", reason or "批量归档", before, "ARCHIVED")
            archived += 1
        db.commit()
    return {"archived": archived}


# ═══════════ 统计 ═══════════

def student_stats() -> dict:
    with session() as db:
        scope_ids = [int(x) for x in accessible_student_ids(db, _tid())]
        base = [GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
                GraduationStudent.record_status == "ACTIVE", GraduationStudent.id.in_(scope_ids or [-1])]
        total = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(*base)) or 0)
        by_stage = [{"stage": st, "label": STAGE_LABEL[st],
                     "count": int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
                         *base, GraduationStudent.stage == st)) or 0)} for st in STAGE_ORDER if st != "ARCHIVED"]
        with_topic = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
            *base, GraduationStudent.topic_id.is_not(None))) or 0)
        high_risk = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
            *base, GraduationStudent.risk_level == "HIGH")) or 0)
        pending_elig = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
            *base, GraduationStudent.eligibility_status == "PENDING")) or 0)
        no_defense = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
            *base, GraduationStudent.defense_group_id.is_(None), GraduationStudent.stage != "ARCHIVED")) or 0)
        archived = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE", GraduationStudent.id.in_(scope_ids or [-1]),
            GraduationStudent.stage == "ARCHIVED")) or 0)
        return {"total": total, "byStage": by_stage, "withTopic": with_topic,
                "withoutTopic": total - with_topic, "highRisk": high_risk,
                "pendingEligibility": pending_elig, "withoutDefenseGroup": no_defense, "archived": archived}


# ═══════════ 导入 / 导出（公共 Excel 底座）═══════════

def _profiles_map(db) -> dict[str, StudentProfile]:
    return {s.student_no: s for s in db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))).all()}


def _batches_map(db) -> dict[str, GraduationBatch]:
    return {b.batch_no: b for b in db.scalars(select(GraduationBatch).where(
        GraduationBatch.tenant_id == _tid(), GraduationBatch.is_deleted.is_(False))).all()}


def _existing_keys(db) -> set[tuple[int, int | None]]:
    return {(r.student_id, r.batch_id) for r in db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE")).all()}


def _dup_check(rows: list[dict]) -> dict[int, str]:
    """库内查重 + 文件内（学号+批次）联合查重。"""
    out: dict[int, str] = {}
    seen: set[tuple[str, str]] = set()
    with session() as db:
        profiles = _profiles_map(db)
        batches = _batches_map(db)
        existing = _existing_keys(db)
        for i, r in enumerate(rows or []):
            row_no = i + 1
            no = (r.get("studentNo") or "").strip()
            batch_no = (r.get("batchNo") or "").strip()
            if not no:
                continue
            key = (no, batch_no)
            if key in seen:
                out[row_no] = f"文件内重复：{no}" + (f"（批次 {batch_no}）" if batch_no else "")
                continue
            seen.add(key)
            stu = profiles.get(no)
            if not stu:
                out[row_no] = f"未匹配到学生主档：{no}"
                continue
            if batch_no and batch_no not in batches:
                out[row_no] = f"毕设批次编号不存在：{batch_no}"
                continue
            batch_id = batches[batch_no].id if batch_no else None
            if (stu.id, batch_id) in existing:
                out[row_no] = f"该学生在此批次已有毕设记录：{no}"
    return out


def _business_validate(row: dict, row_no: int) -> str | None:
    batch_no = (row.get("batchNo") or "").strip()
    if not batch_no:
        return None
    with session() as db:
        b = _batches_map(db).get(batch_no)
        if b and b.status in ("ARCHIVED", "VOIDED"):
            return "批次已归档/已作废，不可导入"
    return None


def _persist_gd_students(rows: list[dict]) -> dict:
    with session() as db:
        profiles = _profiles_map(db)
        batches = _batches_map(db)
        created = 0
        for r in rows or []:
            no = (r.get("studentNo") or "").strip()
            stu = profiles[no]
            batch_no = (r.get("batchNo") or "").strip()
            batch_id = batches[batch_no].id if batch_no else None
            phone = db.scalars(select(StudentContact).where(
                StudentContact.tenant_id == _tid(), StudentContact.student_id == stu.id,
                StudentContact.contact_type == "PHONE")).first()
            s = GraduationStudent(
                tenant_id=_tid(), batch_id=batch_id, student_id=stu.id, student_no=stu.student_no,
                name=stu.real_name, class_id=str(stu.class_id) if stu.class_id else None,
                class_name=f"{stu.grade}级" if stu.grade else None,
                advisor_name=(r.get("advisorName") or "").strip() or None,
                phone_encrypted=phone.contact_value_encrypted if phone else None,
                stage="TOPIC_SELECTING", risk_level="NONE", eligibility_status="PENDING",
            grad_qual_status="UNKNOWN", record_status="ACTIVE")
            db.add(s)
            db.flush()
            _audit(db, s.id, "IMPORT", no)
            created += 1
        db.commit()
        return {"created": created}


def build_import_spec() -> excel.ImportSpec:
    C = excel.ColumnSpec
    return excel.ImportSpec(
        module_key="graduationDesign", biz_type="gd-student", template_name="毕设学生导入",
        columns=[
            C("studentNo", "学号", required=True, example="2023115001",
              help_text="须为学生主档已有学号"),
            C("batchNo", "批次编号", example="GD-2026-1",
              help_text="可选；须为毕设批次管理中已存在的批次编号"),
            C("advisorName", "指导教师", max_length=50, example="王芳"),
        ],
        notes=[
            "1. 只导入「导入模板」页；第一行表头请勿改动。",
            "2. 带 * 为必填：学号。",
            "3. 批次编号可选；同一学号在同一批次内不可重复建档。",
            "4. 导入后初始节点为「选题中」，选题请在学生名单或详情中从选题库分配。",
        ],
        duplicate_check=_dup_check,
        business_validate=_business_validate,
        persist_rows=_persist_gd_students,
        permission_key="graduationDesign.student.import",
        audit_action="导入毕设学生",
    )


def build_export_spec() -> excel.ExportSpec:
    C = excel.ColumnSpec
    return excel.ExportSpec(
        module_key="graduationDesign", biz_type="gd-student", sheet_title="毕设学生台账",
        file_name="毕设学生台账.xlsx",
        columns=[
            C("name", "姓名"),
            C("studentNo", "学号", mask=lambda v: (v[: -4] + "**" + v[-2:]) if v and len(v) > 4 else v),
            C("className", "班级"),
            C("batchName", "批次"),
            C("topicTitle", "课题"),
            C("advisorName", "指导教师"),
            C("stageLabel", "节点状态"),
            C("materialSummary", "材料摘要"),
            C("plagiarismRate", "查重率"),
            C("riskLabel", "风险"),
            C("defenseGroup", "答辩组"),
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


def export_students_xlsx(keyword=None, batch_id=None, stage=None, risk_level=None) -> dict:
    items, _ = list_students(1, 100000, keyword=keyword, batch_id=batch_id, stage=stage, risk_level=risk_level)
    user = get_current_user_ctx() or {}
    return excel.build_export(build_export_spec(), items, operator_name=user.get("realName") or "系统")
