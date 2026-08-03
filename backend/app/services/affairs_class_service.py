"""13A 学工中心 · 班级与辅导员（班级列表/班级画像/班级学生/班级材料 + 辅导员考评）。

数据范围复用 affairs_dashboard_service 的 `_allowed_class_ids` / `_class_in_scope_or_403`；
审计复用其 `_audit`（AffairsAuditTrail，biz_type=CLASS_MATERIAL / COUNSELOR_EVAL）。
不新建教师账号体系；辅导员/班主任来自 t_class.counselor_id/head_teacher_id（读 t_user 取姓名）。
辅导员绑定调整（#12，需院/处角色 + scope 同步）本轮不做，见历史欠账。
"""

from app.core.optimistic_lock import atomic_claim_version

import json
from datetime import datetime

from sqlalchemy import and_, func, select

from app.core.exceptions import AppException, check_version, not_found
from app.services.affairs_dashboard_service import (_allowed_class_ids, _audit,
                                                    _class_in_scope_or_403)
from app.core.field_crypto import mask_phone_encrypted
from app.services.db_service import _iso, _tid, session

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
    from app.models import AffairsRiskRecord, College, CsLeave, Major, SchoolClass, StudentProfile, User

    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 200))
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        conds = [SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False)]
        if allowed is not None:
            conds.append(SchoolClass.id.in_(allowed or {-1}))
        if major_id:
            conds.append(SchoolClass.major_id == int(major_id))
        if grade:
            conds.append(SchoolClass.grade == grade)
        if keyword:
            conds.append(SchoolClass.class_name.ilike(f"%{str(keyword).strip()}%"))
        if college_id:
            conds.append(Major.college_id == int(college_id))

        base = select(SchoolClass, Major, College).outerjoin(
            Major,
            and_(Major.id == SchoolClass.major_id, Major.tenant_id == _tid()),
        ).outerjoin(
            College,
            and_(College.id == Major.college_id, College.tenant_id == _tid()),
        ).where(*conds)
        total = int(db.scalar(select(func.count()).select_from(
            base.with_only_columns(SchoolClass.id).order_by(None).subquery()
        )) or 0)
        rows = db.execute(base.order_by(SchoolClass.id).offset(
            (page - 1) * page_size).limit(page_size)).all()
        classes = [row[0] for row in rows]
        class_ids = [int(row.id) for row in classes]
        teacher_ids = {
            int(uid) for row in classes for uid in (row.counselor_id, row.head_teacher_id) if uid
        }
        teacher_names = {
            int(uid): (name or "")
            for uid, name in db.execute(select(User.id, User.real_name).where(
                User.tenant_id == _tid(), User.id.in_(teacher_ids or {-1}), User.is_deleted.is_(False),
            )).all()
        }
        student_count = {}
        student_class = {}
        if class_ids:
            student_count = {
                int(cid): int(count or 0)
                for cid, count in db.execute(select(StudentProfile.class_id, func.count()).where(
                    StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                    StudentProfile.class_id.in_(class_ids),
                ).group_by(StudentProfile.class_id)).all()
            }
            student_class = {
                int(sid): int(cid)
                for sid, cid in db.execute(select(StudentProfile.id, StudentProfile.class_id).where(
                    StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                    StudentProfile.class_id.in_(class_ids),
                )).all()
            }
        leave_by_class = {}
        risk_by_class = {}
        if student_class:
            student_ids = list(student_class)
            for student_id, count in db.execute(select(CsLeave.student_id, func.count()).where(
                CsLeave.tenant_id == _tid(), CsLeave.is_deleted.is_(False),
                CsLeave.student_id.in_(student_ids), CsLeave.affairs_status.in_(_LEAVE_ACTIVE),
            ).group_by(CsLeave.student_id)).all():
                cid = student_class.get(int(student_id))
                leave_by_class[cid] = leave_by_class.get(cid, 0) + int(count or 0)
            for student_id, count in db.execute(select(AffairsRiskRecord.student_id, func.count()).where(
                AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.is_deleted.is_(False),
                AffairsRiskRecord.student_id.in_(student_ids), AffairsRiskRecord.status != "CLOSED",
            ).group_by(AffairsRiskRecord.student_id)).all():
                cid = student_class.get(int(student_id))
                risk_by_class[cid] = risk_by_class.get(cid, 0) + int(count or 0)
        result = []
        for school_class, major, college in rows:
            result.append({
                "classId": str(school_class.id), "className": school_class.class_name,
                "grade": school_class.grade or "", "majorId": str(school_class.major_id or ""),
                "majorName": major.major_name if major else "",
                "collegeName": college.college_name if college else "",
                "counselorName": teacher_names.get(int(school_class.counselor_id), "") if school_class.counselor_id else "",
                "headTeacherName": teacher_names.get(int(school_class.head_teacher_id), "") if school_class.head_teacher_id else "",
                "studentCount": student_count.get(int(school_class.id), 0),
                "currentLeave": leave_by_class.get(int(school_class.id), 0),
                "riskOpen": risk_by_class.get(int(school_class.id), 0),
            })
        return result, total


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
    from app.models import StudentContact, StudentProfile
    with session() as db:
        _class_in_scope_or_403(db, class_id, user)
        rows = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
            StudentProfile.class_id == int(class_id)).order_by(StudentProfile.student_no)).all()
        # 手机号在 StudentContact，StudentProfile 上没有 phone 属性（旧写法 getattr 恒取空）
        pmap: dict[int, str] = {}
        for ctc in db.scalars(select(StudentContact).where(
                StudentContact.tenant_id == _tid(),
                StudentContact.student_id.in_([s.id for s in rows] or [0]),
                StudentContact.contact_type == "PHONE",
                StudentContact.is_deleted.is_(False))).all():
            pmap.setdefault(ctc.student_id, ctc.contact_value_encrypted or "")
        out = []
        for s in rows:
            if keyword and keyword not in (s.real_name or "") and keyword not in (s.student_no or ""):
                continue
            out.append({
                "studentId": str(s.id), "studentNo": s.student_no, "realName": s.real_name,
                "gender": s.gender or "", "studentStatus": s.student_status or "",
                "phoneMasked": mask_phone_encrypted(pmap.get(s.id, "")),
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
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 200))
    with session() as db:
        _class_in_scope_or_403(db, class_id, user)
        conds = [
            AffairsClassMaterial.tenant_id == _tid(),
            AffairsClassMaterial.class_id == int(class_id),
            AffairsClassMaterial.status == "ACTIVE", AffairsClassMaterial.is_deleted.is_(False),
        ]
        if material_type:
            conds.append(AffairsClassMaterial.material_type == material_type)
        total = int(db.scalar(select(func.count()).select_from(AffairsClassMaterial).where(*conds)) or 0)
        rows = db.scalars(select(AffairsClassMaterial).where(*conds).order_by(
            AffairsClassMaterial.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        return [_material_row(row) for row in rows], total


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
            "remark": p.remark or "", "createdAt": _iso(p.created_at), "version": p.version}


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
        "scoredBy": a.scored_by or "", "scoredAt": _iso(a.scored_at), "version": a.version,
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


def _allowed_counselor_ids(db, user):
    from app.models import SchoolClass
    allowed, _ = _allowed_class_ids(db, user)
    if allowed is None:
        return None
    return {
        int(value)
        for value in db.scalars(select(SchoolClass.counselor_id).where(
            SchoolClass.tenant_id == _tid(), SchoolClass.id.in_(allowed or {-1}),
            SchoolClass.counselor_id.is_not(None), SchoolClass.is_deleted.is_(False),
        )).all()
    }


def collect_assessments(period_id, user, expected_version=None) -> dict:
    """按数据范围生成辅导员考评行；所有工作量指标按辅导员批量聚合。"""
    from app.models import (
        AffairsClassMaterial,
        AffairsCounselorAssessment,
        AffairsCounselorAssessmentPeriod,
        AffairsRiskRecord,
        CsLeave,
        SchoolClass,
        StudentProfile,
        User,
    )

    with session() as db:
        p = db.get(AffairsCounselorAssessmentPeriod, int(period_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("考评周期不存在")
        if p.status == "PUBLISHED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "考评已发布，不可重新生成")
        if expected_version is None:
            expected_version = int(p.version or 0)
        atomic_claim_version(db, p, expected_version)

        allowed, _ = _allowed_class_ids(db, user)
        class_conditions = [
            SchoolClass.tenant_id == _tid(),
            SchoolClass.is_deleted.is_(False),
            SchoolClass.counselor_id.is_not(None),
        ]
        if allowed is not None:
            class_conditions.append(SchoolClass.id.in_(allowed or {-1}))
        classes = db.execute(select(SchoolClass.id, SchoolClass.counselor_id).where(*class_conditions)).all()
        counselor_ids = {int(counselor_id) for _, counselor_id in classes if counselor_id is not None}
        class_ids = [int(class_id) for class_id, _ in classes]
        class_count = {}
        for _, counselor_id in classes:
            counselor_id = int(counselor_id)
            class_count[counselor_id] = class_count.get(counselor_id, 0) + 1

        student_count = {}
        closed_leave = {}
        risk_closed = {}
        material_count = {}
        if class_ids:
            student_count = {
                int(counselor_id): int(count or 0)
                for counselor_id, count in db.execute(
                    select(SchoolClass.counselor_id, func.count(StudentProfile.id))
                    .join(
                        StudentProfile,
                        and_(
                            StudentProfile.class_id == SchoolClass.id,
                            StudentProfile.tenant_id == _tid(),
                            StudentProfile.is_deleted.is_(False),
                        ),
                    )
                    .where(*class_conditions)
                    .group_by(SchoolClass.counselor_id)
                ).all()
            }
            closed_leave = {
                int(counselor_id): int(count or 0)
                for counselor_id, count in db.execute(
                    select(SchoolClass.counselor_id, func.count(CsLeave.id))
                    .join(
                        StudentProfile,
                        and_(
                            StudentProfile.class_id == SchoolClass.id,
                            StudentProfile.tenant_id == _tid(),
                            StudentProfile.is_deleted.is_(False),
                        ),
                    )
                    .join(
                        CsLeave,
                        and_(
                            CsLeave.student_id == StudentProfile.id,
                            CsLeave.tenant_id == _tid(),
                            CsLeave.is_deleted.is_(False),
                            CsLeave.affairs_status == "CLOSED",
                        ),
                    )
                    .where(*class_conditions)
                    .group_by(SchoolClass.counselor_id)
                ).all()
            }
            risk_closed = {
                int(counselor_id): int(count or 0)
                for counselor_id, count in db.execute(
                    select(SchoolClass.counselor_id, func.count(AffairsRiskRecord.id))
                    .join(
                        StudentProfile,
                        and_(
                            StudentProfile.class_id == SchoolClass.id,
                            StudentProfile.tenant_id == _tid(),
                            StudentProfile.is_deleted.is_(False),
                        ),
                    )
                    .join(
                        AffairsRiskRecord,
                        and_(
                            AffairsRiskRecord.student_id == StudentProfile.id,
                            AffairsRiskRecord.tenant_id == _tid(),
                            AffairsRiskRecord.is_deleted.is_(False),
                            AffairsRiskRecord.status == "CLOSED",
                        ),
                    )
                    .where(*class_conditions)
                    .group_by(SchoolClass.counselor_id)
                ).all()
            }
            material_count = {
                int(counselor_id): int(count or 0)
                for counselor_id, count in db.execute(
                    select(SchoolClass.counselor_id, func.count(AffairsClassMaterial.id))
                    .join(
                        AffairsClassMaterial,
                        and_(
                            AffairsClassMaterial.class_id == SchoolClass.id,
                            AffairsClassMaterial.tenant_id == _tid(),
                            AffairsClassMaterial.status == "ACTIVE",
                            AffairsClassMaterial.is_deleted.is_(False),
                        ),
                    )
                    .where(*class_conditions)
                    .group_by(SchoolClass.counselor_id)
                ).all()
            }

        existing = {
            int(row.counselor_id): row
            for row in db.scalars(select(AffairsCounselorAssessment).where(
                AffairsCounselorAssessment.tenant_id == _tid(),
                AffairsCounselorAssessment.period_id == int(period_id),
                AffairsCounselorAssessment.counselor_id.in_(counselor_ids or {-1}),
                AffairsCounselorAssessment.is_deleted.is_(False),
            ).with_for_update()).all()
        }
        counselor_names = {
            int(uid): (name or "")
            for uid, name in db.execute(select(User.id, User.real_name).where(
                User.tenant_id == _tid(), User.id.in_(counselor_ids or {-1}),
                User.is_deleted.is_(False),
            )).all()
        }

        for counselor_id in sorted(counselor_ids):
            metrics = {
                "classCount": class_count.get(counselor_id, 0),
                "studentCount": student_count.get(counselor_id, 0),
                "closedLeave": closed_leave.get(counselor_id, 0),
                "riskClosed": risk_closed.get(counselor_id, 0),
                "materialCount": material_count.get(counselor_id, 0),
            }
            auto = _auto_score(metrics)
            row = existing.get(counselor_id)
            if row:
                row.class_count = metrics["classCount"]
                row.student_count = metrics["studentCount"]
                row.metrics_json = json.dumps(metrics, ensure_ascii=False)
                row.auto_score = auto
                if row.college_score is not None:
                    row.total_score = round(float(auto) * 0.6 + float(row.college_score) * 0.4, 1)
                row.version = int(row.version or 0) + 1
            else:
                db.add(AffairsCounselorAssessment(
                    tenant_id=_tid(), period_id=int(period_id), counselor_id=counselor_id,
                    counselor_name=counselor_names.get(counselor_id, ""),
                    class_count=metrics["classCount"], student_count=metrics["studentCount"],
                    metrics_json=json.dumps(metrics, ensure_ascii=False), auto_score=auto,
                    status="PENDING",
                ))
        if p.status == "DRAFT":
            p.status = "COLLECTED"
            p.version = int(p.version or 0) + 1
        _recompute_ranks(db, int(period_id))
        _audit(db, "COUNSELOR_EVAL", p.id, "COLLECT", f"counselors={len(counselor_ids)}")
        db.commit()
        return {"periodId": str(period_id), "counselors": len(counselor_ids), "version": p.version}


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
        permitted = _allowed_counselor_ids(db, user)
        conds = [
            AffairsCounselorAssessment.tenant_id == _tid(),
            AffairsCounselorAssessment.period_id == int(period_id),
            AffairsCounselorAssessment.is_deleted.is_(False),
        ]
        if permitted is not None:
            conds.append(AffairsCounselorAssessment.counselor_id.in_(permitted or {-1}))
        rows = db.scalars(select(AffairsCounselorAssessment).where(*conds).order_by(
            AffairsCounselorAssessment.rank_no.is_(None),
            AffairsCounselorAssessment.rank_no,
        )).all()
        return [_assess_row(row) for row in rows]


def score_assessment(assessment_id, user, college_score, expected_version=None) -> dict:
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
        permitted = _allowed_counselor_ids(db, user)
        if permitted is not None and int(a.counselor_id or 0) not in permitted:
            raise AppException("NO_DATA_SCOPE", "该辅导员不在您的学院或班级数据范围内")
        p = db.get(AffairsCounselorAssessmentPeriod, int(a.period_id))
        if p and p.status == "PUBLISHED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "考评已发布，不可再评分")
        atomic_claim_version(db, a, expected_version)
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


def publish_period(period_id, user, expected_version=None) -> dict:
    from app.core.affairs_security import build_affairs_context
    from app.models import AffairsCounselorAssessment, AffairsCounselorAssessmentPeriod
    with session() as db:
        if build_affairs_context(user, db).scope_type != "TENANT_ALL":
            raise AppException("NO_PERMISSION", "仅学校/学工处全域管理员可发布全校辅导员考评")
        p = db.get(AffairsCounselorAssessmentPeriod, int(period_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("考评周期不存在")
        if p.status not in ("COLLECTED", "SCORING"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已生成/评分中的考评可发布")
        rows = db.scalars(select(AffairsCounselorAssessment).where(
            AffairsCounselorAssessment.tenant_id == _tid(),
            AffairsCounselorAssessment.period_id == int(period_id),
            AffairsCounselorAssessment.is_deleted.is_(False),
        ).with_for_update()).all()
        if not rows:
            raise AppException("DATA_CONFLICT", "考评周期尚未生成任何辅导员记录")
        pending = [row for row in rows if row.status != "SCORED" or row.college_score is None]
        if pending:
            raise AppException("DATA_CONFLICT", f"仍有{len(pending)}名辅导员未完成学院评分，不能发布")
        atomic_claim_version(db, p, expected_version)
        p.status = "PUBLISHED"
        p.version = int(p.version or 0) + 1
        _recompute_ranks(db, int(period_id))
        _audit(db, "COUNSELOR_EVAL", p.id, "PUBLISH")
        db.commit(); db.refresh(p)
        return _period_row(p)
