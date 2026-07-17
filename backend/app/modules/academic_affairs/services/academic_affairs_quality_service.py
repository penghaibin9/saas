"""13B 教学质量 service（零新表；R9 冻结范围仅"质量统计看板 + 质量报告导出"两项）。

施工卡 D-03/D-06：不建任何 t_aa_quality* 表。质量指标全部实时聚合既有表；
报告导出复用 xlsx_util，导出历史用 AffairsAuditTrail(biz_type=AA_QUALITY_REPORT) 记录。
其余 7 项三级（督导听课/巡课/教学检查/教学事故/质量整改/整改跟进/质量归档）本轮范围外(planned)。
"""
from __future__ import annotations

from datetime import datetime

from app.core.affairs_security import _derive_keys, build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.services.db_service import _iso, _tid, session


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("userId") or ctx.get("loginName") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_QUALITY_REPORT", biz_id=None, action=action,
                             operator=_op(), role_name=_role(), detail=detail[:990], occurred_at=datetime.utcnow()))


def _rate(num, den):
    return round(num / den * 100, 2) if den else 0.0


def _ind(key, label, value, unit="", num=None, den=None, rate=None, drill=None, applied=None):
    """applied: 本指标真实生效的筛选维度列表（term/college/major）——
    未生效的维度前端必须提示"该指标不支持按X筛选"，禁止让用户以为筛选过了。"""
    return {"key": key, "label": label, "value": value, "unit": unit,
            "numerator": num, "denominator": den, "rate": rate, "drillRoute": drill,
            "appliedFilters": applied or []}


def _class_ids(db, college_id=None, major_id=None):
    """学院/专业 → 行政班 id 集合（班级→专业→学院链）。无筛选返回 None（不过滤）。"""
    from app.models import Major, SchoolClass
    if not college_id and not major_id:
        return None
    q = db.query(SchoolClass.id).join(Major, SchoolClass.major_id == Major.id).filter(
        SchoolClass.tenant_id == _tid())
    if major_id:
        q = q.filter(Major.id == int(major_id))
    if college_id:
        q = q.filter(Major.college_id == int(college_id))
    return [cid for (cid,) in q.all()]


def _profile_ids(db, college_id=None, major_id=None):
    """学院/专业 → 学生主档 id 集合。无筛选返回 None。"""
    from app.models import StudentProfile
    if not college_id and not major_id:
        return None
    q = db.query(StudentProfile.id).filter(StudentProfile.tenant_id == _tid(),
                                           StudentProfile.is_deleted.is_(False))
    if college_id:
        q = q.filter(StudentProfile.college_id == int(college_id))
    if major_id:
        q = q.filter(StudentProfile.major_id == int(major_id))
    return [pid for (pid,) in q.all()]


def _acad_ids(db, profile_ids):
    """学生主档 id → 学业台账(t_acad_student) id 集合（AcademicGrade/Warning 挂在台账上）。"""
    from app.models import AcademicStudent
    if profile_ids is None:
        return None
    if not profile_ids:
        return []
    return [aid for (aid,) in db.query(AcademicStudent.id).filter(
        AcademicStudent.tenant_id == _tid(),
        AcademicStudent.student_id.in_(profile_ids)).all()]


def dashboard(user, term_id=None, college_id=None, major_id=None):
    """质量指标看板（实时聚合既有表，筛选真实生效）。

    每个指标底层表支持的筛选维度不同：能过滤的维度真过滤，不支持的维度在
    appliedFilters 中如实缺席（如挂科率的学期维度——成绩表的学期是自由文本，
    与学期 id 无可靠映射，宁可声明不支持也不给错数）。
    """
    from app.models import (AaCourse, AaGradeTask, AaGraduationAuditResult, AaProgram,
                            AaScheduleChange, AaTeachingTask, AaTeachingTaskBatch,
                            AcademicGrade, AcademicWarning, Major, SchoolClass)
    with session() as db:
        build_affairs_context(user, db)
        T = _tid()
        term_id = int(term_id) if term_id else None
        college_id = int(college_id) if college_id else None
        major_id = int(major_id) if major_id else None
        has_org = bool(college_id or major_id)
        org_dims = (["college"] if college_id else []) + (["major"] if major_id else [])

        class_ids = _class_ids(db, college_id, major_id)      # None=不过滤
        profile_ids = _profile_ids(db, college_id, major_id)
        acad_ids = _acad_ids(db, profile_ids)
        inds = []

        # 挂科率：按学生台账收敛学院/专业；学期为自由文本无法可靠映射 → 不支持
        gq = db.query(AcademicGrade).filter(AcademicGrade.tenant_id == T,
                                            AcademicGrade.record_status == "ACTIVE")
        if acad_ids is not None:
            gq = gq.filter(AcademicGrade.acad_student_id.in_(acad_ids or [0]))
        fail = gq.filter(AcademicGrade.pass_status.in_(["FAIL", "FAILED"])).count()
        total_g = gq.count()
        inds.append(_ind("failRate", "挂科率", _rate(fail, total_g), "%", fail, total_g,
                         _rate(fail, total_g), "aa-grades", applied=org_dims))

        # 在办学业预警：按学生台账收敛学院/专业
        wq = db.query(AcademicWarning).filter(AcademicWarning.tenant_id == T,
                                              AcademicWarning.status != "CLOSED",
                                              AcademicWarning.record_status == "ACTIVE")
        if acad_ids is not None:
            wq = wq.filter(AcademicWarning.acad_student_id.in_(acad_ids or [0]))
        inds.append(_ind("warningCount", "在办学业预警", wq.count(), "条",
                         drill="aa-warning", applied=org_dims))

        # 成绩任务发布率：term_id 直接支持；学院/专业经班级链
        tq = db.query(AaGradeTask).filter(AaGradeTask.tenant_id == T, AaGradeTask.is_deleted.is_(False))
        gt_dims = list(org_dims)
        if term_id:
            tq = tq.filter(AaGradeTask.term_id == term_id)
            gt_dims = ["term"] + gt_dims
        if class_ids is not None:
            tq = tq.filter(AaGradeTask.class_id.in_(class_ids or [0]))
        pub = tq.filter(AaGradeTask.status == "PUBLISHED").count()
        total_gt = tq.count()
        inds.append(_ind("gradePublishRate", "成绩任务发布率", _rate(pub, total_gt), "%",
                         pub, total_gt, _rate(pub, total_gt), "aa-grade-review", applied=gt_dims))

        # 毕业资格通过率：按学生主档收敛学院/专业
        grq = db.query(AaGraduationAuditResult).filter(AaGraduationAuditResult.tenant_id == T)
        if profile_ids is not None:
            grq = grq.filter(AaGraduationAuditResult.student_id.in_(profile_ids or [0]))
        grad_ok = grq.filter(AaGraduationAuditResult.status.in_(["GRADUATED", "COMPLETED"])).count()
        grad_total = grq.count()
        inds.append(_ind("gradPassRate", "毕业资格通过率", _rate(grad_ok, grad_total), "%",
                         grad_ok, grad_total, _rate(grad_ok, grad_total),
                         "aa-graduation-qual", applied=org_dims))

        # 培养方案发布率：major 直接支持，college 经专业链
        pq = db.query(AaProgram).filter(AaProgram.tenant_id == T, AaProgram.is_deleted.is_(False))
        if major_id:
            pq = pq.filter(AaProgram.major_id == major_id)
        elif college_id:
            mids = [m for (m,) in db.query(Major.id).filter(
                Major.tenant_id == T, Major.college_id == college_id).all()]
            pq = pq.filter(AaProgram.major_id.in_(mids or [0]))
        prog_pub = pq.filter(AaProgram.status.in_(["PUBLISHED", "ENABLED"])).count()
        prog_total = pq.count()
        inds.append(_ind("programPublishRate", "培养方案发布率", _rate(prog_pub, prog_total), "%",
                         prog_pub, prog_total, _rate(prog_pub, prog_total),
                         "aa-training", applied=org_dims))

        # 启用课程数：仅 college（课程归属学院）
        cq = db.query(AaCourse).filter(AaCourse.tenant_id == T, AaCourse.status == "ENABLED",
                                       AaCourse.is_deleted.is_(False))
        if college_id:
            cq = cq.filter(AaCourse.owner_college_id == college_id)
        inds.append(_ind("courseEnabled", "启用课程数", cq.count(), "门",
                         drill="aa-courses", applied=(["college"] if college_id else [])))

        # 教学任务确认率：term/college 经任务批次，major 经班级链
        ttq = db.query(AaTeachingTask).filter(AaTeachingTask.tenant_id == T,
                                              AaTeachingTask.is_deleted.is_(False))
        tt_dims = []
        if term_id or college_id:
            bq = db.query(AaTeachingTaskBatch.id).filter(AaTeachingTaskBatch.tenant_id == T)
            if term_id:
                bq = bq.filter(AaTeachingTaskBatch.term_id == term_id)
                tt_dims.append("term")
            if college_id:
                bq = bq.filter(AaTeachingTaskBatch.college_id == college_id)
                tt_dims.append("college")
            ttq = ttq.filter(AaTeachingTask.batch_id.in_([b for (b,) in bq.all()] or [0]))
        if major_id:
            major_classes = [c for (c,) in db.query(SchoolClass.id).filter(
                SchoolClass.tenant_id == T, SchoolClass.major_id == major_id).all()]
            ttq = ttq.filter(AaTeachingTask.class_id.in_(major_classes or [0]))
            tt_dims.append("major")
        task_done = ttq.filter(AaTeachingTask.status.in_(
            ["TEACHER_CONFIRMED", "READY", "APPROVED"])).count()
        task_total = ttq.count()
        inds.append(_ind("taskCompleteRate", "教学任务确认率", _rate(task_done, task_total), "%",
                         task_done, task_total, _rate(task_done, task_total),
                         "aa-teaching-tasks", applied=tt_dims))

        # 调停课单数：term 直接支持，学院/专业经班级链
        sq = db.query(AaScheduleChange).filter(AaScheduleChange.tenant_id == T,
                                               AaScheduleChange.is_deleted.is_(False))
        sc_dims = []
        if term_id:
            sq = sq.filter(AaScheduleChange.term_id == term_id)
            sc_dims.append("term")
        if class_ids is not None:
            sq = sq.filter(AaScheduleChange.class_id.in_(class_ids or [0]))
            sc_dims += org_dims
        inds.append(_ind("scheduleChangeCount", "调停课单数", sq.count(), "单",
                         drill="aa-schedule-change", applied=sc_dims))

        return {"termId": str(term_id) if term_id else None,
                "collegeId": str(college_id) if college_id else None,
                "majorId": str(major_id) if major_id else None,
                "indicators": inds, "generatedAt": datetime.utcnow().isoformat()}


def export_report(user, term_id=None, college_id=None, major_id=None, purpose="") -> bytes:
    """导出教务运行质量报告 xlsx（水印+审计；复用 xlsx_util）。"""
    if not (purpose or "").strip() or len((purpose or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    from app.services.xlsx_util import build_ledger_xlsx
    data = dashboard(user, term_id, college_id, major_id)
    ctx = get_current_user_ctx() or {}
    watermark = (f"导出人：{ctx.get('realName') or ctx.get('loginName') or '-'}  "
                 f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose.strip()}")
    headers = ["质量指标", "值", "单位", "分子", "分母", "比率(%)"]
    rows = [[i["label"], i["value"], i["unit"], i["numerator"], i["denominator"], i["rate"]] for i in data["indicators"]]
    content = build_ledger_xlsx("教务运行质量报告", headers, rows, watermark=watermark)
    with session() as db:
        _audit(db, "QUALITY_REPORT_EXPORT", f"质量报告导出 用途={purpose.strip()[:100]}")
        db.commit()
    return content


def list_reports(user, page=1, page_size=20):
    """质量报告导出历史（读 AffairsAuditTrail 的导出事件）。"""
    from app.models import AffairsAuditTrail
    with session() as db:
        build_affairs_context(user, db)
        rows = db.query(AffairsAuditTrail).filter(AffairsAuditTrail.tenant_id == _tid(),
                                                  AffairsAuditTrail.biz_type == "AA_QUALITY_REPORT",
                                                  AffairsAuditTrail.action == "QUALITY_REPORT_EXPORT").order_by(
            AffairsAuditTrail.id.desc()).all()
        total = len(rows)
        items = [{"exportId": str(r.id), "operator": r.operator, "roleName": r.role_name,
                  "detail": r.detail, "occurredAt": r.occurred_at.isoformat() if r.occurred_at else None}
                 for r in rows[(page - 1) * page_size: page * page_size]]
        return items, total


# ═══════════════════════════════════════════════════════════════════════════
# 教学质量 R3 续工（01督导听课/02巡课记录/03教学检查/04教学事故/05质量整改/06整改跟进/09质量归档）
# 施工来源：docs/03-业务模块设计/教务中心/施工包/教学质量/三级施工卡/{01..06,09}-*.md（续工授权）。
# 01/02/03/04 共用 t_aa_quality_record（record_type 判别）；05/06 共用 t_aa_quality_rectification
# （同一任务表，"发起视角"与"跟进视角"只是前端不同默认筛选，见三级卡 §2 建议）；09 不新建表，
# 读侧聚合以上两表按学期归档查看+导出。
# 04 教学事故业务红线（对应三级卡 §1）：事故等级/处理规则属学校规章制度，AI 不代拟，本实现只提供
# 记录/认定/关闭的技术容器，category/conclusion/handling_note 全部自由文本，认定环节强制要求
# 操作者数据范围=scope.all（全校范围角色），复核关闭整改同样要求 scope.all，不开放给普通学院范围角色。
# ═══════════════════════════════════════════════════════════════════════════
_RECORD_TYPES = ("SUPERVISION", "PATROL", "INSPECTION", "INCIDENT")
_RECT_ACTIVE_STATUS = ("PENDING", "IN_PROGRESS")


def _scope(user, db):
    """复用教务统计已验证的 scope 解析器（不另造一套，CLAUDE.md §5.3/§6.1）。"""
    from app.modules.academic_affairs.services.academic_affairs_stats_service import _resolve_scope
    return _resolve_scope(user, db)


def _bad(m):
    return AppException("VALIDATION_ERROR", m)


def _conflict(m):
    return AppException("DATA_CONFLICT", m, http_status=409)


def _audit_biz(db, biz_type, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=biz_id, action=action,
                             operator=_op(), role_name=_role(), detail=(detail or "")[:990],
                             occurred_at=datetime.utcnow()))


def _parse_dt(s):
    if not s:
        return None
    from datetime import datetime as _dt
    try:
        return _dt.fromisoformat(str(s).replace("Z", ""))
    except Exception:
        return None


# ────────────────────── 01/02/03/04 问题记录 ──────────────────────

def _record_dto(r):
    return {
        "recordId": str(r.id), "recordType": r.record_type,
        "termId": str(r.term_id) if r.term_id else None,
        "collegeId": str(r.college_id) if r.college_id else None,
        "majorId": str(r.major_id) if r.major_id else None,
        "classId": str(r.class_id) if r.class_id else None,
        "teacherKey": r.teacher_key, "teacherName": r.teacher_name,
        "courseId": str(r.course_id) if r.course_id else None, "courseName": r.course_name,
        "occurredAt": _iso(r.occurred_at), "location": r.location, "title": r.title,
        "category": r.category, "score": float(r.score) if r.score is not None else None,
        "conclusion": r.conclusion, "description": r.description, "handlingNote": r.handling_note,
        "needRectify": bool(r.need_rectify), "recorderKey": r.recorder_key, "recorderName": r.recorder_name,
        "status": r.status, "confirmedAt": _iso(r.confirmed_at), "confirmedByName": r.confirmed_by_name,
        "createdAt": _iso(r.created_at),
    }


def _get_record(db, rid):
    from app.models import AaQualityRecord
    r = db.query(AaQualityRecord).filter(AaQualityRecord.id == rid, AaQualityRecord.tenant_id == _tid(),
                                         AaQualityRecord.is_deleted.is_(False)).first()
    if not r:
        raise not_found("质量记录不存在")
    return r


def _check_record_scope(scope, r):
    if scope.all:
        return
    if not r.college_id or r.college_id not in scope.college_ids:
        raise no_data_scope("该记录不在您的数据范围内")


def list_records(user, record_type=None, term_id=None, college_id=None, status=None,
                 teacher_key=None, page=1, page_size=20):
    from app.models import AaQualityRecord
    from app.modules.academic_affairs.services.academic_affairs_stats_service import _validate_college_param
    if record_type and record_type not in _RECORD_TYPES:
        raise _bad("非法 recordType")
    with session() as db:
        scope = _scope(user, db)
        q = db.query(AaQualityRecord).filter(AaQualityRecord.tenant_id == _tid(),
                                             AaQualityRecord.is_deleted.is_(False))
        if record_type:
            q = q.filter(AaQualityRecord.record_type == record_type)
        if term_id:
            q = q.filter(AaQualityRecord.term_id == int(term_id))
        if status:
            q = q.filter(AaQualityRecord.status == status)
        if teacher_key:
            q = q.filter(AaQualityRecord.teacher_key == teacher_key)
        if college_id:
            _validate_college_param(scope, college_id)
            q = q.filter(AaQualityRecord.college_id == int(college_id))
        elif not scope.all:
            if scope.college_ids:
                q = q.filter(AaQualityRecord.college_id.in_(scope.college_ids))
            else:
                return [], 0
        rows = q.order_by(AaQualityRecord.id.desc()).all()
        total = len(rows)
        items = [_record_dto(r) for r in rows[(page - 1) * page_size: page * page_size]]
        return items, total


def get_record(user, rid):
    with session() as db:
        scope = _scope(user, db)
        r = _get_record(db, rid)
        _check_record_scope(scope, r)
        return _record_dto(r)


def create_record(user, body):
    from app.models import AaQualityRecord
    from app.modules.academic_affairs.services.academic_affairs_stats_service import _validate_college_param
    rt = (getattr(body, "recordType", None) or "").strip().upper()
    if rt not in _RECORD_TYPES:
        raise _bad("recordType 必须是 SUPERVISION/PATROL/INSPECTION/INCIDENT 之一")
    title = (getattr(body, "title", None) or "").strip()
    if not title:
        raise _bad("标题必填")
    with session() as db:
        scope = _scope(user, db)
        college_id = getattr(body, "collegeId", None)
        if college_id:
            _validate_college_param(scope, college_id)
        elif not scope.all and scope.college_ids:
            college_id = next(iter(scope.college_ids))
        ctx = get_current_user_ctx() or {}
        r = AaQualityRecord(
            tenant_id=_tid(), record_type=rt,
            term_id=int(body.termId) if getattr(body, "termId", None) else None,
            college_id=int(college_id) if college_id else None,
            major_id=int(body.majorId) if getattr(body, "majorId", None) else None,
            class_id=int(body.classId) if getattr(body, "classId", None) else None,
            teacher_key=getattr(body, "teacherKey", None), teacher_name=getattr(body, "teacherName", None),
            course_id=int(body.courseId) if getattr(body, "courseId", None) else None,
            course_name=getattr(body, "courseName", None),
            occurred_at=_parse_dt(getattr(body, "occurredAt", None)), location=getattr(body, "location", None),
            title=title, category=getattr(body, "category", None), score=getattr(body, "score", None),
            conclusion=getattr(body, "conclusion", None), description=getattr(body, "description", None),
            handling_note=getattr(body, "handlingNote", None),
            need_rectify=bool(getattr(body, "needRectify", False)),
            recorder_key=str(ctx.get("userId") or ctx.get("loginName") or ""),
            recorder_name=ctx.get("realName") or ctx.get("loginName"),
            status="SUBMITTED")
        db.add(r); db.flush()
        _audit_biz(db, "AA_QUALITY_RECORD", r.id, f"{rt}_CREATE", title)
        db.commit()
        return _record_dto(r)


def update_record(user, rid, body):
    from app.modules.academic_affairs.services.academic_affairs_stats_service import _validate_college_param
    with session() as db:
        scope = _scope(user, db)
        r = _get_record(db, rid)
        _check_record_scope(scope, r)
        if r.status != "SUBMITTED":
            raise _conflict("仅 SUBMITTED 状态可编辑")
        if not (scope.all or r.recorder_key in _derive_keys(user)):
            raise no_permission("仅记录人本人或全校范围角色可编辑")
        for field, col in (("title", "title"), ("location", "location"), ("category", "category"),
                           ("conclusion", "conclusion"), ("description", "description"),
                           ("handlingNote", "handling_note"), ("teacherName", "teacher_name"),
                           ("courseName", "course_name")):
            v = getattr(body, field, None)
            if v is not None:
                setattr(r, col, v)
        if getattr(body, "score", None) is not None:
            r.score = body.score
        if getattr(body, "needRectify", None) is not None:
            r.need_rectify = bool(body.needRectify)
        if getattr(body, "collegeId", None):
            _validate_college_param(scope, body.collegeId)
            r.college_id = int(body.collegeId)
        db.flush()
        _audit_biz(db, "AA_QUALITY_RECORD", r.id, f"{r.record_type}_UPDATE", r.title)
        db.commit()
        return _record_dto(r)


def confirm_record(user, rid):
    with session() as db:
        scope = _scope(user, db)
        r = _get_record(db, rid)
        _check_record_scope(scope, r)
        if r.status != "SUBMITTED":
            raise _conflict("仅 SUBMITTED 状态可确认")
        if r.record_type == "INCIDENT" and not scope.all:
            raise no_permission("教学事故认定仅限全校范围教务管理角色")
        ctx = get_current_user_ctx() or {}
        r.status = "CONFIRMED"
        r.confirmed_at = datetime.utcnow()
        r.confirmed_by_name = ctx.get("realName") or ctx.get("loginName")
        db.flush()
        _audit_biz(db, "AA_QUALITY_RECORD", r.id, f"{r.record_type}_CONFIRM", r.title)
        db.commit()
        return _record_dto(r)


def close_record(user, rid):
    with session() as db:
        scope = _scope(user, db)
        r = _get_record(db, rid)
        _check_record_scope(scope, r)
        if r.status != "CONFIRMED":
            raise _conflict("仅 CONFIRMED 状态可关闭")
        r.status = "CLOSED"
        db.flush()
        _audit_biz(db, "AA_QUALITY_RECORD", r.id, f"{r.record_type}_CLOSE", r.title)
        db.commit()
        return _record_dto(r)


def cancel_record(user, rid):
    """撤销（仅 SUBMITTED 阶段允许，软删）。"""
    with session() as db:
        scope = _scope(user, db)
        r = _get_record(db, rid)
        _check_record_scope(scope, r)
        if r.status != "SUBMITTED":
            raise _conflict("仅 SUBMITTED 状态可撤销")
        if not (scope.all or r.recorder_key in _derive_keys(user)):
            raise no_permission("仅记录人本人或全校范围角色可撤销")
        r.is_deleted = True
        db.flush()
        _audit_biz(db, "AA_QUALITY_RECORD", r.id, f"{r.record_type}_CANCEL", r.title)
        db.commit()
        return {"recordId": str(r.id), "cancelled": True}


# ────────────────────── 05/06 质量整改（发起视角+跟进视角同表） ──────────────────────

def _rect_dto(r):
    import json
    log = json.loads(r.progress_log_json) if r.progress_log_json else []
    overdue = bool(r.deadline and r.status != "CLOSED" and r.deadline < datetime.utcnow())
    return {
        "rectId": str(r.id), "sourceRecordId": str(r.source_record_id) if r.source_record_id else None,
        "sourceType": r.source_type, "sourceTitle": r.source_title, "title": r.title,
        "termId": str(r.term_id) if r.term_id else None,
        "collegeId": str(r.college_id) if r.college_id else None,
        "majorId": str(r.major_id) if r.major_id else None, "classId": str(r.class_id) if r.class_id else None,
        "requirement": r.requirement, "deadline": _iso(r.deadline), "overdue": overdue,
        "responsibleKey": r.responsible_key, "responsibleName": r.responsible_name,
        "initiatorKey": r.initiator_key, "initiatorName": r.initiator_name,
        "progressLog": log, "resultNote": r.result_note, "status": r.status,
        "closedAt": _iso(r.closed_at), "createdAt": _iso(r.created_at),
    }


def _get_rect(db, rid):
    from app.models import AaQualityRectification
    r = db.query(AaQualityRectification).filter(AaQualityRectification.id == rid,
                                                 AaQualityRectification.tenant_id == _tid(),
                                                 AaQualityRectification.is_deleted.is_(False)).first()
    if not r:
        raise not_found("整改任务不存在")
    return r


def _check_rect_scope(scope, r):
    if scope.all:
        return
    if not r.college_id or r.college_id not in scope.college_ids:
        raise no_data_scope("该整改任务不在您的数据范围内")


def _append_progress(r, action, note, operator_name):
    import json
    log = json.loads(r.progress_log_json) if r.progress_log_json else []
    log.append({"time": datetime.utcnow().isoformat(), "operator": operator_name or "",
               "action": action, "note": (note or "")[:500]})
    r.progress_log_json = json.dumps(log, ensure_ascii=False)


def list_rectifications(user, status=None, term_id=None, college_id=None, source_type=None,
                        overdue=None, page=1, page_size=20):
    from app.models import AaQualityRectification
    from app.modules.academic_affairs.services.academic_affairs_stats_service import _validate_college_param
    with session() as db:
        scope = _scope(user, db)
        q = db.query(AaQualityRectification).filter(AaQualityRectification.tenant_id == _tid(),
                                                     AaQualityRectification.is_deleted.is_(False))
        if status:
            q = q.filter(AaQualityRectification.status == status)
        if term_id:
            q = q.filter(AaQualityRectification.term_id == int(term_id))
        if source_type:
            q = q.filter(AaQualityRectification.source_type == source_type)
        if college_id:
            _validate_college_param(scope, college_id)
            q = q.filter(AaQualityRectification.college_id == int(college_id))
        elif not scope.all:
            if scope.college_ids:
                q = q.filter(AaQualityRectification.college_id.in_(scope.college_ids))
            else:
                return [], 0
        rows = q.order_by(AaQualityRectification.id.desc()).all()
        if overdue:
            now = datetime.utcnow()
            rows = [r for r in rows if r.deadline and r.status != "CLOSED" and r.deadline < now]
        total = len(rows)
        items = [_rect_dto(r) for r in rows[(page - 1) * page_size: page * page_size]]
        return items, total


def get_rectification(user, rid):
    with session() as db:
        scope = _scope(user, db)
        r = _get_rect(db, rid)
        _check_rect_scope(scope, r)
        return _rect_dto(r)


def create_rectification(user, body):
    from app.models import AaQualityRecord, AaQualityRectification
    from app.modules.academic_affairs.services.academic_affairs_stats_service import _validate_college_param
    title = (getattr(body, "title", None) or "").strip()
    requirement = (getattr(body, "requirement", None) or "").strip()
    if not title:
        raise _bad("标题必填")
    if len(requirement) < 5:
        raise _bad("整改要求必填且不少于5字")
    with session() as db:
        scope = _scope(user, db)
        src = None
        source_record_id = getattr(body, "sourceRecordId", None)
        if source_record_id:
            src = db.query(AaQualityRecord).filter(AaQualityRecord.id == int(source_record_id),
                                                    AaQualityRecord.tenant_id == _tid(),
                                                    AaQualityRecord.is_deleted.is_(False)).first()
            if not src:
                raise not_found("来源质量记录不存在")
            _check_record_scope(scope, src)
        college_id = getattr(body, "collegeId", None) or (src.college_id if src else None)
        if college_id:
            _validate_college_param(scope, college_id)
        elif not scope.all and scope.college_ids:
            college_id = next(iter(scope.college_ids))
        ctx = get_current_user_ctx() or {}
        initiator_name = ctx.get("realName") or ctx.get("loginName")
        r = AaQualityRectification(
            tenant_id=_tid(), source_record_id=src.id if src else None,
            source_type=src.record_type if src else None, source_title=src.title if src else None,
            title=title,
            term_id=int(body.termId) if getattr(body, "termId", None) else (src.term_id if src else None),
            college_id=int(college_id) if college_id else None,
            major_id=int(body.majorId) if getattr(body, "majorId", None) else (src.major_id if src else None),
            class_id=int(body.classId) if getattr(body, "classId", None) else (src.class_id if src else None),
            requirement=requirement, deadline=_parse_dt(getattr(body, "deadline", None)),
            responsible_key=getattr(body, "responsibleKey", None) or (src.teacher_key if src else None),
            responsible_name=getattr(body, "responsibleName", None) or (src.teacher_name if src else None),
            initiator_key=str(ctx.get("userId") or ctx.get("loginName") or ""),
            initiator_name=initiator_name, status="PENDING")
        _append_progress(r, "CREATE", "发起整改任务", initiator_name)
        db.add(r); db.flush()
        if src:
            src.need_rectify = True
        _audit_biz(db, "AA_QUALITY_RECTIFICATION", r.id, "RECT_CREATE", title)
        db.commit()
        return _rect_dto(r)


def add_progress(user, rid, note):
    note = (note or "").strip()
    if len(note) < 2:
        raise _bad("跟进说明必填")
    with session() as db:
        scope = _scope(user, db)
        r = _get_rect(db, rid)
        _check_rect_scope(scope, r)
        if r.status not in _RECT_ACTIVE_STATUS:
            raise _conflict("仅待整改/整改中状态可记录跟进")
        ctx = get_current_user_ctx() or {}
        r.status = "IN_PROGRESS"
        _append_progress(r, "PROGRESS", note, ctx.get("realName") or ctx.get("loginName"))
        db.flush()
        _audit_biz(db, "AA_QUALITY_RECTIFICATION", r.id, "RECT_PROGRESS", note[:200])
        db.commit()
        return _rect_dto(r)


def submit_rectification(user, rid, note):
    note = (note or "").strip()
    if len(note) < 2:
        raise _bad("整改说明必填")
    with session() as db:
        scope = _scope(user, db)
        r = _get_rect(db, rid)
        _check_rect_scope(scope, r)
        if r.status not in _RECT_ACTIVE_STATUS:
            raise _conflict("仅待整改/整改中状态可提交复核")
        ctx = get_current_user_ctx() or {}
        r.status = "SUBMITTED"
        _append_progress(r, "SUBMIT", note, ctx.get("realName") or ctx.get("loginName"))
        db.flush()
        _audit_biz(db, "AA_QUALITY_RECTIFICATION", r.id, "RECT_SUBMIT", note[:200])
        db.commit()
        return _rect_dto(r)


def review_rectification(user, rid, action, reason=""):
    action = (action or "").strip().upper()
    if action not in ("APPROVE", "REJECT"):
        raise _bad("action 仅支持 APPROVE/REJECT")
    with session() as db:
        scope = _scope(user, db)
        r = _get_rect(db, rid)
        _check_rect_scope(scope, r)
        if r.status != "SUBMITTED":
            raise _conflict("仅待复核状态可复核")
        if not scope.all:
            raise no_permission("整改复核关闭仅限全校范围教务管理角色")
        ctx = get_current_user_ctx() or {}
        operator = ctx.get("realName") or ctx.get("loginName")
        if action == "APPROVE":
            r.status = "CLOSED"
            r.closed_at = datetime.utcnow()
            r.result_note = (reason or "复核通过").strip()
            _append_progress(r, "APPROVE", r.result_note, operator)
        else:
            reason = (reason or "").strip()
            if len(reason) < 5:
                raise _bad("驳回原因必填且不少于5字")
            r.status = "IN_PROGRESS"
            _append_progress(r, "REJECT", reason, operator)
        db.flush()
        _audit_biz(db, "AA_QUALITY_RECTIFICATION", r.id, f"RECT_{action}", (reason or "")[:200])
        db.commit()
        return _rect_dto(r)


# ────────────────────── 09 质量归档（读侧聚合，零新表） ──────────────────────

def archive_overview(user, term_id=None):
    from app.models import AaQualityRecord, AaQualityRectification
    with session() as db:
        scope = _scope(user, db)
        qr = db.query(AaQualityRecord).filter(AaQualityRecord.tenant_id == _tid(),
                                              AaQualityRecord.is_deleted.is_(False))
        qc = db.query(AaQualityRectification).filter(AaQualityRectification.tenant_id == _tid(),
                                                      AaQualityRectification.is_deleted.is_(False))
        if term_id:
            qr = qr.filter(AaQualityRecord.term_id == int(term_id))
            qc = qc.filter(AaQualityRectification.term_id == int(term_id))
        if not scope.all:
            if scope.college_ids:
                qr = qr.filter(AaQualityRecord.college_id.in_(scope.college_ids))
                qc = qc.filter(AaQualityRectification.college_id.in_(scope.college_ids))
            else:
                return {"termId": str(term_id) if term_id else None, "byType": {}, "rectification": {}, "total": 0}
        records = qr.all()
        by_type = {}
        for rt in _RECORD_TYPES:
            items = [r for r in records if r.record_type == rt]
            by_type[rt] = {"total": len(items),
                          "submitted": sum(1 for i in items if i.status == "SUBMITTED"),
                          "confirmed": sum(1 for i in items if i.status == "CONFIRMED"),
                          "closed": sum(1 for i in items if i.status == "CLOSED")}
        rects = qc.all()
        now = datetime.utcnow()
        rectification = {
            "total": len(rects),
            "pending": sum(1 for r in rects if r.status == "PENDING"),
            "inProgress": sum(1 for r in rects if r.status == "IN_PROGRESS"),
            "submitted": sum(1 for r in rects if r.status == "SUBMITTED"),
            "closed": sum(1 for r in rects if r.status == "CLOSED"),
            "overdue": sum(1 for r in rects if r.deadline and r.status != "CLOSED" and r.deadline < now),
        }
        return {"termId": str(term_id) if term_id else None, "byType": by_type,
               "rectification": rectification, "total": len(records)}


def archive_export(user, domain, term_id=None, purpose=""):
    purpose = (purpose or "").strip()
    if len(purpose) < 5:
        raise _bad("导出用途必填（≥5字）")
    if domain not in ("records", "rectifications"):
        raise _bad("非法导出域，仅支持 records/rectifications")
    from app.models import AaQualityRecord, AaQualityRectification
    from app.services.xlsx_util import build_ledger_xlsx
    with session() as db:
        scope = _scope(user, db)
        ctx = get_current_user_ctx() or {}
        watermark = (f"导出人：{ctx.get('realName') or ctx.get('loginName') or '-'}  "
                    f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose}")
        if domain == "records":
            q = db.query(AaQualityRecord).filter(AaQualityRecord.tenant_id == _tid(),
                                                 AaQualityRecord.is_deleted.is_(False))
            if term_id:
                q = q.filter(AaQualityRecord.term_id == int(term_id))
            if not scope.all:
                q = q.filter(AaQualityRecord.college_id.in_(scope.college_ids)) if scope.college_ids \
                    else q.filter(AaQualityRecord.id.is_(None))
            rows = q.order_by(AaQualityRecord.record_type, AaQualityRecord.id.desc()).all()
            headers = ["类型", "标题", "教师", "课程", "发生时间", "地点", "结论", "状态", "记录人"]
            data = [[r.record_type, r.title, r.teacher_name, r.course_name, _iso(r.occurred_at),
                    r.location, r.conclusion, r.status, r.recorder_name] for r in rows]
            content = build_ledger_xlsx("教学质量问题记录", headers, data, watermark=watermark)
            biz_type = "AA_QUALITY_RECORD"
        else:
            q = db.query(AaQualityRectification).filter(AaQualityRectification.tenant_id == _tid(),
                                                         AaQualityRectification.is_deleted.is_(False))
            if term_id:
                q = q.filter(AaQualityRectification.term_id == int(term_id))
            if not scope.all:
                q = q.filter(AaQualityRectification.college_id.in_(scope.college_ids)) if scope.college_ids \
                    else q.filter(AaQualityRectification.id.is_(None))
            rows = q.order_by(AaQualityRectification.id.desc()).all()
            headers = ["标题", "来源类型", "责任人", "整改要求", "期限", "状态", "复核结论"]
            data = [[r.title, r.source_type, r.responsible_name, r.requirement, _iso(r.deadline),
                    r.status, r.result_note] for r in rows]
            content = build_ledger_xlsx("质量整改任务", headers, data, watermark=watermark)
            biz_type = "AA_QUALITY_RECTIFICATION"
        _audit_biz(db, biz_type, None, f"{biz_type}_ARCHIVE_EXPORT", f"domain={domain} 用途={purpose[:100]}")
        db.commit()
        return content
