"""13A 学工中心 · 班级与辅导员（班级列表/班级画像/班级学生/班级材料 + 辅导员考评）。

数据范围复用 affairs_dashboard_service 的 `_allowed_class_ids` / `_class_in_scope_or_403`；
审计复用其 `_audit`（AffairsAuditTrail，biz_type=CLASS_MATERIAL / COUNSELOR_EVAL）。
不新建教师账号体系；辅导员/班主任来自 t_class.counselor_id/head_teacher_id（读 t_user 取姓名）。
辅导员绑定调整（#12，需院/处角色 + scope 同步）本轮不做，见历史欠账。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.services.affairs_dashboard_service import (_allowed_class_ids, _audit,
                                                    _class_in_scope_or_403)
from app.services.db_service import _iso, _mask_phone, _tid, session

MATERIAL_TYPES = {"CLASS_MEETING": "班会记录", "THEME_ACTIVITY": "主题活动", "EVALUATION": "评优材料",
                  "ATTENDANCE": "考勤台账", "SUMMARY": "班级总结", "OTHER": "其他"}
_LEAVE_ACTIVE = ("COUNSELOR_REVIEW", "COLLEGE_REVIEW", "STUDENT_AFFAIRS_REVIEW", "APPROVED",
                 "EXTENSION_REVIEW", "WAIT_CANCEL_LEAVE", "OVERDUE")


def _parse_dt(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def _teacher_name(db, uid) -> str:
    if not uid:
        return ""
    from app.models import User
    u = db.get(User, int(uid))
    return (u.real_name if u else "") or ""


def _college_major_maps(db):
    from app.models import College, Major
    majors = {m.id: m for m in db.scalars(select(Major).where(Major.tenant_id == _tid())).all()}
    colleges = {c.id: c.college_name for c in db.scalars(select(College).where(College.tenant_id == _tid())).all()}
    return majors, colleges


# ═══════════ 班级列表（增强：名称 + 指标 + 筛选）═══════════

def class_list(user, college_id=None, major_id=None, grade=None, keyword=None, page=1, page_size=20):
    from app.models import AffairsRiskRecord, CsLeave, SchoolClass, StudentProfile
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        q = select(SchoolClass).where(SchoolClass.tenant_id == _tid(),
                                      SchoolClass.is_deleted.is_(False))
        if allowed is not None:
            q = q.where(SchoolClass.id.in_(allowed or {-1}))
        classes = db.scalars(q.order_by(SchoolClass.id)).all()
        majors, colleges = _college_major_maps(db)
        # 学院筛选：解析该学院下的专业
        college_major_ids = None
        if college_id:
            college_major_ids = {mid for mid, m in majors.items() if str(m.college_id) == str(college_id)}
        # 先过滤
        rows = []
        for c in classes:
            if major_id and str(c.major_id) != str(major_id):
                continue
            if college_major_ids is not None and c.major_id not in college_major_ids:
                continue
            if grade and (c.grade or "") != grade:
                continue
            if keyword and keyword not in (c.class_name or ""):
                continue
            rows.append(c)
        class_ids = [c.id for c in rows]
        # 指标：学生数（group by）、在假数、在办风险数（经 student→class 映射）
        stu_count, stu_class = {}, {}
        if class_ids:
            for cid, cnt in db.execute(select(StudentProfile.class_id, func.count()).where(
                    StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                    StudentProfile.class_id.in_(class_ids)).group_by(StudentProfile.class_id)).all():
                stu_count[cid] = cnt
            for sid, cid in db.execute(select(StudentProfile.id, StudentProfile.class_id).where(
                    StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                    StudentProfile.class_id.in_(class_ids))).all():
                stu_class[sid] = cid
        leave_by_class, risk_by_class = {}, {}
        if stu_class:
            all_sids = list(stu_class.keys())
            for (sid,) in db.execute(select(CsLeave.student_id).where(
                    CsLeave.tenant_id == _tid(), CsLeave.is_deleted.is_(False),
                    CsLeave.student_id.in_(all_sids), CsLeave.affairs_status.in_(_LEAVE_ACTIVE))).all():
                leave_by_class[stu_class.get(sid)] = leave_by_class.get(stu_class.get(sid), 0) + 1
            for (sid,) in db.execute(select(AffairsRiskRecord.student_id).where(
                    AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.is_deleted.is_(False),
                    AffairsRiskRecord.student_id.in_(all_sids),
                    AffairsRiskRecord.status.notin_(["CLOSED"]))).all():
                risk_by_class[stu_class.get(sid)] = risk_by_class.get(stu_class.get(sid), 0) + 1
        out = []
        for c in rows:
            m = majors.get(c.major_id)
            out.append({
                "classId": str(c.id), "className": c.class_name, "grade": c.grade or "",
                "majorId": str(c.major_id), "majorName": m.major_name if m else "",
                "collegeName": colleges.get(m.college_id, "") if m else "",
                "counselorName": _teacher_name(db, c.counselor_id),
                "headTeacherName": _teacher_name(db, c.head_teacher_id),
                "studentCount": stu_count.get(c.id, 0),
                "currentLeave": leave_by_class.get(c.id, 0),
                "riskOpen": risk_by_class.get(c.id, 0),
            })
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


# ═══════════ 班级画像（360 聚合）═══════════

def class_profile(class_id, user) -> dict:
    from app.models import (AffairsClassCadre, AffairsClassMaterial, AffairsRiskRecord, AidApply,
                            CsLeave, DisciplineCase, StudentProfile)
    with session() as db:
        c = _class_in_scope_or_403(db, class_id, user)
        majors, colleges = _college_major_maps(db)
        m = majors.get(c.major_id)
        students = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
            StudentProfile.class_id == int(class_id))).all()
        sids = [s.id for s in students]
        male = sum(1 for s in students if (s.gender or "") in ("男", "MALE", "M"))
        female = sum(1 for s in students if (s.gender or "") in ("女", "FEMALE", "F"))

        def _cnt(model, extra=None):
            if not sids:
                return 0
            cond = [model.tenant_id == _tid(), model.is_deleted.is_(False), model.student_id.in_(sids)]
            if extra is not None:
                cond.append(extra)
            return db.scalar(select(func.count()).select_from(model).where(*cond)) or 0

        cur_leave = _cnt(CsLeave, CsLeave.affairs_status.in_(_LEAVE_ACTIVE))
        overdue_leave = _cnt(CsLeave, CsLeave.affairs_status == "OVERDUE")
        risk_open = _cnt(AffairsRiskRecord, AffairsRiskRecord.status.notin_(["CLOSED"]))
        difficult = _cnt(AidApply, AidApply.status == "APPROVED")
        discipline = _cnt(DisciplineCase, DisciplineCase.status.notin_(["CANCELLED", "REJECTED", "REMOVED"]))
        cadre_cnt = db.scalar(select(func.count()).select_from(AffairsClassCadre).where(
            AffairsClassCadre.tenant_id == _tid(), AffairsClassCadre.class_id == int(class_id),
            AffairsClassCadre.status == "ACTIVE", AffairsClassCadre.is_deleted.is_(False))) or 0
        material_cnt = db.scalar(select(func.count()).select_from(AffairsClassMaterial).where(
            AffairsClassMaterial.tenant_id == _tid(), AffairsClassMaterial.class_id == int(class_id),
            AffairsClassMaterial.status == "ACTIVE", AffairsClassMaterial.is_deleted.is_(False))) or 0
        return {
            "classId": str(c.id), "className": c.class_name, "grade": c.grade or "",
            "majorName": m.major_name if m else "", "collegeName": colleges.get(m.college_id, "") if m else "",
            "counselorName": _teacher_name(db, c.counselor_id),
            "headTeacherName": _teacher_name(db, c.head_teacher_id),
            "metrics": [
                {"key": "studentCount", "label": "班级人数", "value": len(students), "unit": "人"},
                {"key": "male", "label": "男生", "value": male, "unit": "人"},
                {"key": "female", "label": "女生", "value": female, "unit": "人"},
                {"key": "currentLeave", "label": "当前请假", "value": cur_leave, "unit": "人次"},
                {"key": "overdueLeave", "label": "逾期未销", "value": overdue_leave, "unit": "件"},
                {"key": "riskOpen", "label": "在办风险", "value": risk_open, "unit": "件"},
                {"key": "difficult", "label": "困难认定", "value": difficult, "unit": "人"},
                {"key": "discipline", "label": "有效处分", "value": discipline, "unit": "件"},
                {"key": "cadre", "label": "班干部", "value": cadre_cnt, "unit": "人"},
                {"key": "material", "label": "班级材料", "value": material_cnt, "unit": "件"},
            ],
        }


def class_students(class_id, user, keyword=None, page=1, page_size=20):
    from app.models import StudentProfile
    with session() as db:
        _class_in_scope_or_403(db, class_id, user)
        rows = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
            StudentProfile.class_id == int(class_id)).order_by(StudentProfile.student_no)).all()
        out = []
        for s in rows:
            if keyword and keyword not in (s.real_name or "") and keyword not in (s.student_no or ""):
                continue
            out.append({
                "studentId": str(s.id), "studentNo": s.student_no, "realName": s.real_name,
                "gender": s.gender or "", "studentStatus": s.student_status or "",
                "phoneMasked": _mask_phone(getattr(s, "phone", "") or ""),
            })
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


# ═══════════ 班级材料 ═══════════

def _material_row(x) -> dict:
    return {
        "id": str(x.id), "classId": str(x.class_id), "materialType": x.material_type,
        "materialTypeLabel": MATERIAL_TYPES.get(x.material_type or "", x.material_type or ""),
        "title": x.title, "fileId": x.file_id or "", "fileName": x.file_name or "",
        "materialAt": _iso(x.material_at), "remark": x.remark or "", "uploader": x.uploader or "",
        "status": x.status, "createdAt": _iso(x.created_at),
    }


def list_materials(class_id, user, material_type=None, page=1, page_size=20):
    from app.models import AffairsClassMaterial
    with session() as db:
        _class_in_scope_or_403(db, class_id, user)
        q = select(AffairsClassMaterial).where(
            AffairsClassMaterial.tenant_id == _tid(), AffairsClassMaterial.class_id == int(class_id),
            AffairsClassMaterial.status == "ACTIVE", AffairsClassMaterial.is_deleted.is_(False))
        if material_type:
            q = q.where(AffairsClassMaterial.material_type == material_type)
        rows = db.scalars(q.order_by(AffairsClassMaterial.id.desc())).all()
        out = [_material_row(x) for x in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def add_material(class_id, user, body) -> dict:
    from app.models import AffairsClassMaterial
    mtype = (body.materialType or "OTHER").upper()
    if mtype not in MATERIAL_TYPES:
        raise AppException("VALIDATION_ERROR", "材料类型非法")
    if not body.title or not body.title.strip():
        raise AppException("VALIDATION_ERROR", "材料标题必填")
    file_id, file_name = (body.fileId or ""), (body.fileName or "")
    with session() as db:
        _class_in_scope_or_403(db, class_id, user)
        # 附件校验：给了 file_id 则必须是本租户有效文件
        if file_id:
            from app.services import file_service
            meta = file_service.get_file_meta(file_id)
            if not meta:
                raise AppException("VALIDATION_ERROR", "附件不存在或无权访问")
            if not file_name:
                file_name = meta.get("fileName", "")
        from app.core.context import get_current_user_ctx
        uploader = (get_current_user_ctx() or {}).get("realName") or ""
        x = AffairsClassMaterial(
            tenant_id=_tid(), class_id=int(class_id), material_type=mtype, title=body.title.strip(),
            file_id=file_id or None, file_name=file_name or None, material_at=_parse_dt(body.materialAt),
            remark=(body.remark or None), uploader=uploader, status="ACTIVE")
        db.add(x)
        db.flush()
        _audit(db, "CLASS_MATERIAL", x.id, "ADD", f"class={class_id},type={mtype},title={body.title.strip()}")
        db.commit()
        db.refresh(x)
        return _material_row(x)


def void_material(material_id, user, reason="") -> dict:
    from app.models import AffairsClassMaterial
    with session() as db:
        x = db.get(AffairsClassMaterial, int(material_id))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("班级材料不存在")
        _class_in_scope_or_403(db, x.class_id, user)
        x.status = "VOIDED"
        x.is_deleted = True
        x.version += 1
        _audit(db, "CLASS_MATERIAL", x.id, "VOID", reason)
        db.commit()
        return {"id": str(x.id), "status": "VOIDED"}


# ═══════════ 辅导员考评（周期 + 自动工作量指标 + 学院评分 + 排名）═══════════
# 13A-04.5：系统留痕自动生成工作量（带班/学生/办结请假/风险处置/班级材料）+ 学院打分。
# 申诉/发布工作流为简化版（PUBLISHED 一步发布），见历史欠账。

_L_PERIOD = {"DRAFT": "草稿", "COLLECTED": "已生成", "SCORING": "评分中", "PUBLISHED": "已发布"}
_L_ASSESS = {"PENDING": "待评分", "SCORED": "已评分"}


def _period_row(p) -> dict:
    return {"id": str(p.id), "periodName": p.period_name, "semester": p.semester or "",
            "status": p.status, "statusLabel": _L_PERIOD.get(p.status or "", p.status or ""),
            "remark": p.remark or "", "createdAt": _iso(p.created_at)}


def _assess_row(a) -> dict:
    metrics = {}
    if a.metrics_json:
        try:
            metrics = json.loads(a.metrics_json)
        except (ValueError, TypeError):
            metrics = {}
    return {
        "id": str(a.id), "periodId": str(a.period_id),
        "counselorId": str(a.counselor_id or ""), "counselorName": a.counselor_name or "",
        "classCount": a.class_count, "studentCount": a.student_count, "metrics": metrics,
        "autoScore": float(a.auto_score) if a.auto_score is not None else None,
        "collegeScore": float(a.college_score) if a.college_score is not None else None,
        "totalScore": float(a.total_score) if a.total_score is not None else None,
        "rankNo": a.rank_no, "status": a.status, "statusLabel": _L_ASSESS.get(a.status or "", a.status or ""),
        "scoredBy": a.scored_by or "", "scoredAt": _iso(a.scored_at),
    }


def create_period(user, period_name, semester=None, remark=None) -> dict:
    from app.models import AffairsCounselorAssessmentPeriod
    if not period_name or not period_name.strip():
        raise AppException("VALIDATION_ERROR", "考评周期名称必填")
    with session() as db:
        p = AffairsCounselorAssessmentPeriod(
            tenant_id=_tid(), period_name=period_name.strip(), semester=semester, remark=remark,
            status="DRAFT")
        db.add(p)
        db.flush()
        _audit(db, "COUNSELOR_EVAL", p.id, "PERIOD_CREATE", period_name.strip())
        db.commit()
        db.refresh(p)
        return _period_row(p)


def list_periods(user, page=1, page_size=20):
    from app.models import AffairsCounselorAssessmentPeriod
    with session() as db:
        rows = db.scalars(select(AffairsCounselorAssessmentPeriod).where(
            AffairsCounselorAssessmentPeriod.tenant_id == _tid(),
            AffairsCounselorAssessmentPeriod.is_deleted.is_(False)).order_by(
            AffairsCounselorAssessmentPeriod.id.desc())).all()
        out = [_period_row(p) for p in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def _auto_score(metrics: dict) -> float:
    """工作量折算自动分（基线60 + 工作量，封顶100）。透明可解释，非黑箱。"""
    load = (metrics.get("classCount", 0) * 5 + metrics.get("closedLeave", 0) * 2
            + metrics.get("riskClosed", 0) * 3 + metrics.get("materialCount", 0) * 1)
    return round(min(100.0, 60.0 + min(40, load)), 1)


def collect_assessments(period_id, user) -> dict:
    """按数据范围内班级的辅导员自动生成考评行（幂等：已存在则更新指标）。"""
    from app.models import (AffairsClassMaterial, AffairsCounselorAssessment,
                            AffairsCounselorAssessmentPeriod, AffairsRiskRecord, CsLeave,
                            SchoolClass, StudentProfile)
    with session() as db:
        p = db.get(AffairsCounselorAssessmentPeriod, int(period_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("考评周期不存在")
        if p.status == "PUBLISHED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "考评已发布，不可重新生成")
        allowed, _ = _allowed_class_ids(db, user)
        q = select(SchoolClass).where(SchoolClass.tenant_id == _tid(),
                                      SchoolClass.is_deleted.is_(False),
                                      SchoolClass.counselor_id.is_not(None))
        if allowed is not None:
            q = q.where(SchoolClass.id.in_(allowed or {-1}))
        classes = db.scalars(q).all()
        # 按辅导员分组
        by_counselor: dict = {}
        for c in classes:
            by_counselor.setdefault(c.counselor_id, []).append(c)
        count = 0
        for counselor_id, cls in by_counselor.items():
            cids = [c.id for c in cls]
            sids = [s for (s,) in db.execute(select(StudentProfile.id).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                StudentProfile.class_id.in_(cids))).all()]
            closed_leave = 0
            risk_closed = 0
            if sids:
                closed_leave = db.scalar(select(func.count()).select_from(CsLeave).where(
                    CsLeave.tenant_id == _tid(), CsLeave.is_deleted.is_(False),
                    CsLeave.student_id.in_(sids), CsLeave.affairs_status == "CLOSED")) or 0
                risk_closed = db.scalar(select(func.count()).select_from(AffairsRiskRecord).where(
                    AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.is_deleted.is_(False),
                    AffairsRiskRecord.student_id.in_(sids), AffairsRiskRecord.status == "CLOSED")) or 0
            material_cnt = db.scalar(select(func.count()).select_from(AffairsClassMaterial).where(
                AffairsClassMaterial.tenant_id == _tid(), AffairsClassMaterial.class_id.in_(cids),
                AffairsClassMaterial.status == "ACTIVE", AffairsClassMaterial.is_deleted.is_(False))) or 0
            metrics = {"classCount": len(cids), "studentCount": len(sids),
                       "closedLeave": closed_leave, "riskClosed": risk_closed,
                       "materialCount": material_cnt}
            auto = _auto_score(metrics)
            row = db.scalars(select(AffairsCounselorAssessment).where(
                AffairsCounselorAssessment.tenant_id == _tid(),
                AffairsCounselorAssessment.period_id == int(period_id),
                AffairsCounselorAssessment.counselor_id == counselor_id,
                AffairsCounselorAssessment.is_deleted.is_(False))).first()
            if row:
                row.class_count, row.student_count = len(cids), len(sids)
                row.metrics_json, row.auto_score = json.dumps(metrics, ensure_ascii=False), auto
                if row.college_score is not None:
                    row.total_score = round(float(auto) * 0.6 + float(row.college_score) * 0.4, 1)
                row.version += 1
            else:
                db.add(AffairsCounselorAssessment(
                    tenant_id=_tid(), period_id=int(period_id), counselor_id=counselor_id,
                    counselor_name=_teacher_name(db, counselor_id), class_count=len(cids),
                    student_count=len(sids), metrics_json=json.dumps(metrics, ensure_ascii=False),
                    auto_score=auto, status="PENDING"))
            count += 1
        if p.status == "DRAFT":
            p.status = "COLLECTED"
            p.version += 1
        _recompute_ranks(db, int(period_id))
        _audit(db, "COUNSELOR_EVAL", p.id, "COLLECT", f"counselors={count}")
        db.commit()
        return {"periodId": str(period_id), "counselors": count}


def _recompute_ranks(db, period_id):
    from app.models import AffairsCounselorAssessment
    rows = db.scalars(select(AffairsCounselorAssessment).where(
        AffairsCounselorAssessment.tenant_id == _tid(),
        AffairsCounselorAssessment.period_id == period_id,
        AffairsCounselorAssessment.is_deleted.is_(False))).all()

    def _key(a):
        return float(a.total_score if a.total_score is not None else (a.auto_score or 0))

    for i, a in enumerate(sorted(rows, key=_key, reverse=True), start=1):
        a.rank_no = i


def list_assessments(period_id, user):
    from app.models import AffairsCounselorAssessment
    with session() as db:
        rows = db.scalars(select(AffairsCounselorAssessment).where(
            AffairsCounselorAssessment.tenant_id == _tid(),
            AffairsCounselorAssessment.period_id == int(period_id),
            AffairsCounselorAssessment.is_deleted.is_(False)).order_by(
            AffairsCounselorAssessment.rank_no.is_(None), AffairsCounselorAssessment.rank_no)).all()
        return [_assess_row(a) for a in rows]


def score_assessment(assessment_id, user, college_score) -> dict:
    from app.models import AffairsCounselorAssessment, AffairsCounselorAssessmentPeriod
    try:
        cs = float(college_score)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "学院评分必须为数字")
    if cs < 0 or cs > 100:
        raise AppException("VALIDATION_ERROR", "学院评分范围 0-100")
    with session() as db:
        a = db.get(AffairsCounselorAssessment, int(assessment_id))
        if not a or a.is_deleted or a.tenant_id != _tid():
            raise not_found("考评记录不存在")
        p = db.get(AffairsCounselorAssessmentPeriod, int(a.period_id))
        if p and p.status == "PUBLISHED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "考评已发布，不可再评分")
        from app.core.context import get_current_user_ctx
        a.college_score = cs
        a.total_score = round(float(a.auto_score or 0) * 0.6 + cs * 0.4, 1)
        a.status = "SCORED"
        a.scored_by = (get_current_user_ctx() or {}).get("realName") or ""
        a.scored_at = datetime.utcnow()
        a.version += 1
        if p and p.status == "COLLECTED":
            p.status = "SCORING"
            p.version += 1
        _recompute_ranks(db, int(a.period_id))
        _audit(db, "COUNSELOR_EVAL", a.id, "SCORE", f"college={cs},total={a.total_score}")
        db.commit()
        db.refresh(a)
        return _assess_row(a)


def publish_period(period_id, user) -> dict:
    from app.models import AffairsCounselorAssessmentPeriod
    with session() as db:
        p = db.get(AffairsCounselorAssessmentPeriod, int(period_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("考评周期不存在")
        if p.status not in ("COLLECTED", "SCORING"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已生成/评分中的考评可发布")
        p.status = "PUBLISHED"
        p.version += 1
        _recompute_ranks(db, int(period_id))
        _audit(db, "COUNSELOR_EVAL", p.id, "PUBLISH")
        db.commit()
        db.refresh(p)
        return _period_row(p)
