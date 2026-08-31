"""岗位实习域真实数据服务（DB_ENABLED=true 走本模块）。租户过滤 + is_deleted + 脱敏 + 审计留痕。"""
from __future__ import annotations

from app.core.tenant_scoped import tenant_get

import json
from datetime import datetime, timedelta

from sqlalchemy import case, func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (AttendanceException, InternshipAuditTrail, InternshipBatch,
                        InternshipCheckin, InternshipRecord, RiskRecord, StudentContact,
                        StudentProfile, WeeklyReport)
from app.modules.internship.schemas.internship import RulesConfig, StageItem
from app.core.field_crypto import mask_phone_encrypted
from app.services.db_service import _as_id, _iso, _tid, session

STATUS_LABEL = {"PREPARING": "准备中", "READY": "待上岗", "ONBOARD": "在岗中",
                "ASSESSING": "考核中", "ARCHIVED": "已归档"}
RISK_LABEL = {"NONE": "无", "LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}
RISK_TONE = {"HIGH": "danger", "MEDIUM": "warning", "LOW": "default", "NONE": "default"}
EXC_TYPE_LABEL = {"OUT_OF_RANGE": "超范围", "MOCK_LOCATION": "模拟定位", "MISSING": "缺卡"}
EXC_STATUS_LABEL = {"PENDING_HANDLE": "待核实", "COMPLETED": "已处理"}
REPORT_STATUS_LABEL = {"PENDING_REVIEW": "待批阅", "APPROVED": "已通过",
                       "RETURNED": "已退回", "OVERDUE": "逾期未交"}
RISK_STATUS_LABEL = {"PENDING_HANDLE": "待处理", "PROCESSING": "跟进中",
                     "RESOLVED": "已解决", "CLOSED": "已关闭"}
BATCH_STATUS_LABEL = {"DRAFT": "草稿", "RUNNING": "进行中", "CLOSED": "已结束",
                      "ARCHIVED": "已归档", "VOIDED": "已作废"}
DEFAULT_STAGES = [
    {"code": "PREP", "name": "岗前准备", "startDate": "", "endDate": ""},
    {"code": "ONBOARD", "name": "在岗实习", "startDate": "", "endDate": ""},
    {"code": "REVIEW", "name": "总结考核", "startDate": "", "endDate": ""},
]
DEFAULT_RULES = {
    "checkin": {"requireDaily": True, "geofenceRadiusM": 500,
                "allowedExceptionTypes": ["OUT_OF_RANGE", "MOCK_LOCATION", "MISSING"]},
    "weeklyReport": {"frequency": "WEEKLY", "minWordCount": 800, "deadlineWeekday": 7},
    "guidance": {"minVisitsPerTerm": 2, "minCommunicationsPerMonth": 2},
    "evaluation": {"enterpriseWeight": 0.4, "teacherWeight": 0.4, "selfWeight": 0.2},
    "score": {"passThreshold": 60.0, "components": [
        {"name": "企业评价", "weight": 0.4}, {"name": "教师评价", "weight": 0.4},
        {"name": "考核成绩", "weight": 0.2}]},
    # 上岗前置（BUG-010）：学校可按批次关闭其中某项，默认全部要求。
    "onboard": {"requireAgreement": True, "requireInsurance": True, "requireAdvisor": True},
    "compliance": __import__(
        "app.modules.internship.services.internship_compliance_rules", fromlist=["DEFAULT_COMPLIANCE_RULES"]
    ).DEFAULT_COMPLIANCE_RULES,
}


def _op_name() -> str:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统"


def _trail(db, target_id: int, target_type: str, action: str, detail: dict | None = None):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=target_id, target_type=target_type,
                                action=action, operator_name=_op_name(), detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def notify_counselor_for_student(db, student, title: str, content: str,
                                 source_biz_id=None, message_type="INTERNSHIP") -> bool:
    """向学生所在班级辅导员发真实站内信（t_unified_message）。

    解析路径：student.class_id → t_class.counselor_id（辅导员 user_id）。班级未配置
    辅导员或学生无班级时静默跳过（返回 False，不伪造）。用于指导转风险 / 请假等提醒。
    """
    from app.models import SchoolClass
    from app.services.message_event_outbox_service import emit_receiver_notice
    if not student or not getattr(student, "class_id", None):
        return False
    cls = tenant_get(db, SchoolClass, student.class_id)
    if not cls or not getattr(cls, "counselor_id", None):
        return False
    emit_receiver_notice(
        db,
        event_code="INTERNSHIP.COUNSELOR_NOTICE",
        source_module="internship",
        source_biz_type="internship",
        source_biz_id=int(source_biz_id) if source_biz_id else 0,
        receiver_id=int(cls.counselor_id),
        title=title[:500],
        content=(content or "")[:2000],
        receiver_as="user",
    )
    return True


def _parse_dt(v, label: str = "日期"):
    if v in (None, ""):
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
            raise AppException("VALIDATION_ERROR", f"{label}格式不正确，请使用 YYYY-MM-DD") from None


def _parse_nonnegative_int(v, label: str) -> int:
    try:
        value = int(v or 0)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", f"{label}必须为非负整数") from None
    if value < 0:
        raise AppException("VALIDATION_ERROR", f"{label}必须为非负整数")
    return value


def _students_map(db, ids: list[int]) -> dict:
    if not ids:
        return {}
    rows = db.scalars(select(StudentProfile).where(StudentProfile.id.in_(ids))).all()
    return {s.id: s for s in rows}


# ═══════════ 数据范围（P0-D：管理端按教师范围收敛，不仅租户） ═══════════
# 与 internship_student_service 同一机制：user 由 API 层显式传入（FastAPI 同步端点 contextvar 不可靠）。

def _current_scope(user: dict | None = None) -> dict:
    from app.services.mobile_teacher_service import resolve_teacher_scope
    return resolve_teacher_scope(user or get_current_user_ctx() or {})


def resolve_student_class_college_names(db, stu) -> tuple[str | None, str | None]:
    """解析学生班级名与学院名。主档缺 college_id 时沿 班级→专业→学院 推导（IX-BUG-002）。"""
    if stu is None:
        return None, None
    from app.models import College, Major, SchoolClass
    class_name = college_name = None
    cls = tenant_get(db, SchoolClass, stu.class_id) if getattr(stu, "class_id", None) else None
    if cls:
        class_name = cls.class_name
    college_id = getattr(stu, "college_id", None)
    if not college_id and getattr(stu, "major_id", None):
        maj = tenant_get(db, Major, stu.major_id)
        college_id = maj.college_id if maj else None
    if not college_id and cls is not None:
        maj = tenant_get(db, Major, cls.major_id)
        college_id = maj.college_id if maj else None
    if college_id:
        col = tenant_get(db, College, college_id)
        college_name = col.college_name if col else None
    return class_name, college_name


def _rec_in_scope(scope: dict, db, r: "InternshipRecord | None", stu) -> bool:
    """实习记录是否在教师数据范围内。非 SCOPED（管理员全校 / 无范围豁免）一律放行；
    SCOPED 按 指导教师账号 / 学号 / 班级 / 学院 收敛（记录缺失关键上下文时 SCOPED 下不放行）。

    IX-E2E：学生可能仅有 class_id/major_id，沿 班级→专业→学院 推导学院名。
    """
    if scope.get("mode") != "SCOPED":
        return True
    if r is None:
        return False
    from app.services.mobile_teacher_service import scope_match_row
    class_name, college_name = resolve_student_class_college_names(db, stu)
    return scope_match_row(scope, student_no=(stu.student_no if stu else None),
                           class_name=class_name, advisor_name=r.advisor_name,
                           college_name=college_name, advisor_user_id=r.advisor_user_id)


def assert_admin_tenant(user, action: str = "该操作") -> None:
    """批量/全校级写操作守卫：仅 ADMIN_TENANT（校级管理员）可执行；SCOPED（学院负责人/
    指导教师）一律拒绝。用于自动匹配、批量导入、逾期批处理等会横跨全校数据的作业——
    避免受限范围角色借这些入口触发全租户批量改写。"""
    if _current_scope(user).get("mode") != "ADMIN_TENANT":
        from app.core.exceptions import no_permission
        raise no_permission(f"{action}为全校级操作，仅校级管理员可执行")


def assert_record_in_scope(db, rec, stu, user, msg: str = "该实习学生不在你的数据范围内") -> None:
    """单条写操作数据范围守卫（记录型实体）：越出教师数据范围 → 403。ADMIN_TENANT 恒放行。"""
    if not _rec_in_scope(_current_scope(user), db, rec, stu):
        from app.core.exceptions import no_permission
        raise no_permission(msg)


def assert_student_in_scope(db, student_id, user, msg: str = "该学生不在你的数据范围内") -> None:
    """按学生的写操作数据范围守卫。ADMIN_TENANT 恒放行；SCOPED 与 _rec_in_scope 对齐：
    指导角色必须存在本人指导的实习记录（排他），不得仅凭班级/学院扩大写权限。"""
    scope = _current_scope(user)
    if scope.get("mode") != "SCOPED":
        return
    if not student_id:
        return
    from app.models import StudentProfile
    from app.services.mobile_teacher_service import _ADVISOR_ROLES, can_teacher_view_student
    stu = db.get(StudentProfile, _as_id(student_id))
    if stu is None:
        from app.core.exceptions import no_permission
        raise no_permission(msg)
    role = (scope.get("roleCode") or "").upper()
    if role in _ADVISOR_ROLES:
        recs = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.student_id == stu.id,
            InternshipRecord.is_deleted.is_(False))).all()
        if not any(_rec_in_scope(scope, db, r, stu) for r in recs):
            from app.core.exceptions import no_permission
            raise no_permission(msg)
        return
    if not can_teacher_view_student(user, stu, scope=scope, db=db):
        from app.core.exceptions import no_permission
        raise no_permission(msg)


def _bulk_context(db, rows, id_attr: str = "internship_id"):
    """批量加载列表 rows 关联的 InternshipRecord / StudentProfile / SchoolClass 名 / College 名，
    返回 (rec_map, stu_map, class_name_map, college_name_map, stu_college_name_map)。
    stu_college_name_map 含缺 college_id 时按 班级→专业→学院 推导后的学院名，与 _rec_in_scope 口径一致。"""
    from app.models import College, Major, SchoolClass
    intern_ids = {getattr(x, id_attr) for x in rows if getattr(x, id_attr, None)}
    rec_map = {}
    if intern_ids:
        rec_map = {r.id: r for r in db.scalars(
            select(InternshipRecord).where(InternshipRecord.id.in_(intern_ids))).all()}
    stu_ids = {r.student_id for r in rec_map.values() if r.student_id}
    stu_map = {}
    if stu_ids:
        stu_map = {s.id: s for s in db.scalars(
            select(StudentProfile).where(StudentProfile.id.in_(stu_ids))).all()}
    class_ids = {getattr(s, "class_id", None) for s in stu_map.values() if getattr(s, "class_id", None)}
    major_ids = {getattr(s, "major_id", None) for s in stu_map.values() if getattr(s, "major_id", None)}
    class_name_map, class_major_map = {}, {}
    if class_ids:
        class_rows = db.scalars(select(SchoolClass).where(SchoolClass.id.in_(class_ids))).all()
        class_name_map = {c.id: c.class_name for c in class_rows}
        class_major_map = {c.id: c.major_id for c in class_rows if c.major_id}
        major_ids |= set(class_major_map.values())
    major_college_map = {}
    if major_ids:
        major_college_map = {m.id: m.college_id for m in db.scalars(
            select(Major).where(Major.id.in_(major_ids))).all() if m.college_id}
    stu_college_id_map = {}
    for s in stu_map.values():
        cid = getattr(s, "college_id", None)
        if not cid and getattr(s, "major_id", None):
            cid = major_college_map.get(s.major_id)
        if not cid and getattr(s, "class_id", None):
            mid = class_major_map.get(s.class_id)
            cid = major_college_map.get(mid) if mid else None
        if cid:
            stu_college_id_map[s.id] = cid
    college_ids = set(stu_college_id_map.values())
    college_name_map = {}
    if college_ids:
        college_name_map = {c.id: c.college_name for c in db.scalars(
            select(College).where(College.id.in_(college_ids))).all()}
    stu_college_name_map = {sid: college_name_map.get(cid)
                            for sid, cid in stu_college_id_map.items()}
    return rec_map, stu_map, class_name_map, college_name_map, stu_college_name_map


def _rec_in_scope_pre(scope: dict, rec, stu, class_name_map, college_name_map,
                      stu_college_name_map=None) -> bool:
    """与 _rec_in_scope 等价，但用 _bulk_context 预加载的班级/学院名映射，不再逐行 db.get。"""
    if scope.get("mode") != "SCOPED":
        return True
    if rec is None:
        return False
    from app.services.mobile_teacher_service import scope_match_row
    class_name = college_name = None
    if stu is not None:
        if getattr(stu, "class_id", None):
            class_name = class_name_map.get(stu.class_id)
        if stu_college_name_map is not None:
            college_name = stu_college_name_map.get(stu.id)
        elif getattr(stu, "college_id", None):
            college_name = college_name_map.get(stu.college_id)
    return scope_match_row(scope, student_no=(stu.student_no if stu else None),
                           class_name=class_name, advisor_name=rec.advisor_name,
                           college_name=college_name, advisor_user_id=rec.advisor_user_id)


def _record_row(r: InternshipRecord, stu: StudentProfile | None, class_name: str | None = None) -> dict:
    return {
        "id": str(r.id), "studentId": str(r.student_id),
        "name": stu.real_name if stu else "-",
        "studentNo": stu.student_no if stu else "-",
        "className": class_name or "-",
        "classId": str(stu.class_id) if stu and stu.class_id else "",
        "enterpriseName": r.enterprise_name or "", "positionName": r.position_name or "",
        "advisorName": r.advisor_name or "", "enterpriseMentor": r.enterprise_mentor_name or "",
        "status": r.status, "statusLabel": STATUS_LABEL.get(r.status, r.status),
        "riskLevel": r.risk_level, "riskLabel": RISK_LABEL.get(r.risk_level, r.risk_level),
        "internRange": (f"{_iso(r.intern_start_date)[:10]} ~ {_iso(r.intern_end_date)[:10]}"
                        if r.intern_start_date and r.intern_end_date else ""),
    }


# ═══ 实习学生列表 / 详情 ═══

def list_internship_students(page, page_size, keyword=None, class_id=None,
                             status=None, risk_level=None, batch_id=None, user=None):
    """兼容入口：强制走 intern-students 批次/范围门禁，禁止无 batchId 全表扫描。"""
    from app.modules.internship.services import internship_student_service as student_svc
    return student_svc.list_students(
        page, page_size, keyword=keyword, class_id=class_id, status=status,
        risk_level=risk_level, batch_id=batch_id, user=user)


def get_internship_student_detail(record_id, user=None) -> dict:
    with session() as db:
        r = db.get(InternshipRecord, _as_id(record_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("实习记录不存在或不在当前数据范围内")
        stu = db.get(StudentProfile, r.student_id)
        if not _rec_in_scope(_current_scope(user), db, r, stu):  # P0-D：越范围 → 403
            from app.core.exceptions import no_permission
            raise no_permission("该实习学生不在你的数据范围内")
        phone = db.scalars(select(StudentContact).where(
            StudentContact.tenant_id == _tid(), StudentContact.student_id == r.student_id,
            StudentContact.contact_type == "PHONE")).first()
        checkins = db.scalars(select(AttendanceException).where(
            AttendanceException.tenant_id == _tid(),
            AttendanceException.internship_id == r.id).order_by(
            AttendanceException.exception_date.desc()).limit(6)).all()
        reports = db.scalars(select(WeeklyReport).where(
            WeeklyReport.tenant_id == _tid(), WeeklyReport.internship_id == r.id,
            WeeklyReport.is_deleted.is_(False)).order_by(WeeklyReport.week_number.desc())).all()
        risks = db.scalars(select(RiskRecord).where(
            RiskRecord.tenant_id == _tid(), RiskRecord.internship_id == r.id,
            RiskRecord.is_deleted.is_(False)).order_by(RiskRecord.id.desc())).all()
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(),
            InternshipAuditTrail.target_type == "INTERN_STUDENT",
            InternshipAuditTrail.target_id == r.id).order_by(
            InternshipAuditTrail.id.desc()).limit(8)).all()
        base = _record_row(r, stu)
        base.update({
            "phone": mask_phone_encrypted(phone.contact_value_encrypted if phone else None),
            "insurance": r.insurance_info or "", "agreement": r.agreement_info or "",
            "checkins": [{"id": str(c.id), "date": _iso(c.exception_date)[:16] if c.exception_date else "",
                          "result": EXC_TYPE_LABEL.get(c.exception_type, c.exception_type),
                          "tone": "danger" if c.status == "PENDING_HANDLE" else "success",
                          "note": c.student_note or "",
                          "handle": EXC_STATUS_LABEL.get(c.status, c.status)} for c in checkins],
            "reports": [{"id": str(w.id), "week": f"第 {w.week_number} 周", "status": w.status,
                         "statusLabel": REPORT_STATUS_LABEL.get(w.status, w.status),
                         "submitAt": _iso(w.submitted_at) or "",
                         "version": f"v{w.report_version}"} for w in reports],
            "risks": [{"id": str(k.id), "code": k.risk_code, "title": k.risk_title,
                       "level": k.risk_level, "status": RISK_STATUS_LABEL.get(k.status, k.status),
                       "owner": k.owner_name or ""} for k in risks],
            "auditTrail": [{"who": t.operator_name or "系统", "time": _iso(t.occurred_at),
                            "action": t.action,
                            "affected": json.dumps(t.detail_json or {}, ensure_ascii=False)}
                           for t in trail],
        })
        return base


# ═══ 打卡异常 ═══

def _exc_row(c: AttendanceException, rec: InternshipRecord | None, stu: StudentProfile | None,
             class_name: str | None = None) -> dict:
    missing_facts = []
    if not c.exception_date:
        missing_facts.append("异常时间")
    if c.exception_type == "OUT_OF_RANGE":
        if c.distance_km is None:
            missing_facts.append("距打卡点")
        if c.gps_accuracy is None:
            missing_facts.append("定位精度")
        if not c.address:
            missing_facts.append("打卡地址")
    elif c.exception_type == "MOCK_LOCATION":
        if not c.device_risk_flag or str(c.device_risk_flag).lower() == "normal":
            missing_facts.append("设备风险信号")
    elif c.exception_type not in EXC_TYPE_LABEL:
        missing_facts.append("异常类型")
    return {
        "id": str(c.id), "internId": str(c.internship_id),
        "studentName": stu.real_name if stu else "-",
        "className": class_name or "-",
        "enterpriseName": rec.enterprise_name if rec else "",
        "positionName": rec.position_name if rec else "",
        "date": _iso(c.exception_date)[:16] if c.exception_date else "",
        "type": c.exception_type, "typeLabel": EXC_TYPE_LABEL.get(c.exception_type, c.exception_type),
        "distance": f"{c.distance_km} km" if c.distance_km else "—",
        "accuracy": f"±{c.gps_accuracy} m" if c.gps_accuracy else "—",
        "address": c.address or "",
        "deviceRisk": c.device_risk_flag or "正常", "note": c.student_note or "",
        "streak": f"连续 {c.streak_days} 天" if c.streak_days else "",
        "appealStatus": c.appeal_status or "", "appealNote": c.appeal_note or "",
        "appealFileId": c.appeal_file_id or "", "appealedAt": _iso(c.appealed_at),
        "status": c.status, "statusLabel": EXC_STATUS_LABEL.get(c.status, c.status),
        "version": int(c.version or 0),
        "decisionFactsComplete": not missing_facts,
        "missingDecisionFacts": missing_facts,
    }


# ═══ 打卡台账（PC 管理端只读，over t_internship_checkin；移动端学生写入，按数据范围收敛） ═══

CHECKIN_RESULT_LABEL = {"RECORDED": "已记录", "NORMAL": "正常", "OUT_OF_RANGE": "超范围",
                        "NO_LOCATION": "无定位", "LEAVE": "请假"}

CHECKIN_RESULT_LABEL["MOCK_LOCATION"] = "设备/模拟定位风险"


def _checkin_row(c: InternshipCheckin, rec, stu) -> dict:
    return {
        "id": str(c.id), "internId": str(c.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": rec.advisor_name if rec else "", "enterpriseName": rec.enterprise_name if rec else "",
        "date": c.checkin_date, "at": _iso(c.checkin_at) or "",
        "result": c.result, "resultLabel": CHECKIN_RESULT_LABEL.get(c.result, c.result),
        "tone": "danger" if c.result in ("OUT_OF_RANGE", "NO_LOCATION", "MOCK_LOCATION") else "success",
        "address": c.address or "", "note": c.note or "",
    }


def list_checkins(page, page_size, result=None, keyword=None, internship_id=None, batch_id=None, user=None):
    with session() as db:
        from app.modules.internship.services.internship_batch_context import batch_record_ids
        _, record_ids = batch_record_ids(db, batch_id)
        if not record_ids:
            return [], 0
        q = select(InternshipCheckin).where(InternshipCheckin.tenant_id == _tid(),
                                            InternshipCheckin.is_deleted.is_(False),
                                            InternshipCheckin.internship_id.in_(record_ids))
        if result:
            q = q.where(InternshipCheckin.result == result)
        if internship_id:
            q = q.where(InternshipCheckin.internship_id == int(internship_id))
        rows = db.scalars(q.order_by(InternshipCheckin.checkin_date.desc(),
                                     InternshipCheckin.id.desc())).all()
        scope = _current_scope(user)
        rec_map, stu_map, class_name_map, college_name_map, stu_college_name_map = _bulk_context(db, rows)
        items = []
        for c in rows:
            rec = rec_map.get(c.internship_id)
            stu = stu_map.get(rec.student_id) if rec else None
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            # BUG-012：关联不到实习记录/学生的孤儿打卡不进台账——整行学号姓名都是「-」，
            # 教师无法据此核对，展示出来只会污染台账与导出。
            if rec is None or rec.is_deleted or stu is None:
                continue
            if not _rec_in_scope_pre(scope, rec, stu, class_name_map, college_name_map,
                                     stu_college_name_map):  # P0-D 数据范围
                continue
            items.append(_checkin_row(c, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def export_checkins(result=None, keyword=None, batch_id=None, user=None) -> dict:
    from app.services import xlsx_util
    from app.modules.internship.services.internship_export_util import load_export_rows
    items, total = load_export_rows(
        list_checkins, result=result, keyword=keyword, batch_id=batch_id, user=user)
    from app.modules.internship.services.internship_export_util import pack_export_meta, require_exportable
    require_exportable(total)
    headers = ["学号", "姓名", "校内指导教师", "企业", "打卡日期", "打卡时间", "结果", "地址", "备注"]
    data_rows = [[it["studentNo"], it["studentName"], it["advisorName"], it["enterpriseName"],
                  it["date"], it["at"], it["resultLabel"], it["address"], it["note"]] for it in items]
    wm = (f"岗位实习中心·打卡台账 · 导出人：{(get_current_user_ctx() or {}).get('realName', '-')} · "
          f"{datetime.now():%Y-%m-%d %H:%M} · 导出留痕")
    content = xlsx_util.build_ledger_xlsx("打卡台账", headers, data_rows, watermark=wm)
    packed = xlsx_util.pack_xlsx_result(content, "打卡台账.xlsx", len(items))
    packed.update(pack_export_meta(total, len(items)))
    return packed


def export_exceptions(type=None, status=None, keyword=None, batch_id=None, user=None) -> dict:
    from app.services import xlsx_util
    from app.modules.internship.services.internship_export_util import load_export_rows
    items, _ = load_export_rows(
        list_attendance_exceptions, type=type, status=status, keyword=keyword,
        batch_id=batch_id, user=user)
    headers = ["姓名", "班级", "企业", "异常类型", "异常时间", "距离", "连续", "设备", "处理状态"]
    data_rows = [[it["studentName"], it["className"], it["enterpriseName"], it["typeLabel"],
                  it["date"], it["distance"], it["streak"], it["deviceRisk"], it["statusLabel"]]
                 for it in items]
    wm = (f"岗位实习中心·打卡异常台账 · 导出人：{(get_current_user_ctx() or {}).get('realName', '-')} · "
          f"{datetime.now():%Y-%m-%d %H:%M} · 导出留痕")
    content = xlsx_util.build_ledger_xlsx("打卡异常台账", headers, data_rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "打卡异常台账.xlsx", len(items))


def _exc_ctx(db, c: AttendanceException):
    rec = tenant_get(db, InternshipRecord, c.internship_id)
    stu = tenant_get(db, StudentProfile, rec.student_id) if rec else None
    return rec, stu


def list_attendance_exceptions(page, page_size, type=None, status=None, keyword=None, batch_id=None, user=None):
    with session() as db:
        from app.models import SchoolClass
        from app.modules.internship.services.internship_batch_context import resolve_batch
        from app.modules.internship.services.internship_scope import apply_internship_record_scope

        batch = resolve_batch(db, batch_id)
        q = select(
            AttendanceException, InternshipRecord, StudentProfile, SchoolClass.class_name,
        ).join(
            InternshipRecord, InternshipRecord.id == AttendanceException.internship_id,
        ).join(
            StudentProfile, StudentProfile.id == InternshipRecord.student_id,
        ).outerjoin(
            SchoolClass, SchoolClass.id == StudentProfile.class_id,
        ).where(
            AttendanceException.tenant_id == _tid(),
            AttendanceException.is_deleted.is_(False),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.is_deleted.is_(False),
        )
        q = apply_internship_record_scope(q, user)
        if type:
            q = q.where(AttendanceException.exception_type == type)
        if status:
            q = q.where(AttendanceException.status == status)
        if keyword:
            value = f"%{keyword.strip()}%"
            q = q.where(or_(
                StudentProfile.real_name.like(value), StudentProfile.student_no.like(value),
            ))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        if int(page_size or 0) <= 0:
            return [], total
        rows = db.execute(q.order_by(
            AttendanceException.exception_date.desc(), AttendanceException.id.desc(),
        ).offset(
            (max(1, int(page)) - 1) * int(page_size),
        ).limit(int(page_size))).all()
        return [_exc_row(c, rec, stu, class_name=class_name)
                for c, rec, stu, class_name in rows], total


def get_exception_detail(exception_id, user=None) -> dict:
    with session() as db:
        c = db.get(AttendanceException, _as_id(exception_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("打卡异常不存在")
        rec, stu = _exc_ctx(db, c)
        if not _rec_in_scope(_current_scope(user), db, rec, stu):  # P0-D
            from app.core.exceptions import no_permission
            raise no_permission("该打卡异常不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(),
            InternshipAuditTrail.target_id == c.id,
            InternshipAuditTrail.target_type == "EXCEPTION").order_by(
            InternshipAuditTrail.id)).all()
        row = _exc_row(c, rec, stu)
        row.update({
            "positionName": rec.position_name if rec else "", "address": c.address or "",
            "accuracy": f"±{c.gps_accuracy} m" if c.gps_accuracy else "—",
            "studentNote": c.student_note or "", "handleComment": c.handle_comment or "",
            "trail": [{"title": t.action, "desc": json.dumps(t.detail_json or {}, ensure_ascii=False),
                       "time": _iso(t.occurred_at), "tone": "processing"} for t in trail],
        })
        return row


def handle_attendance_exception(exception_id, action: str, comment: str, user=None, *, expected_version=None) -> dict:
    if action not in ("REASONABLE", "ABNORMAL", "TO_RISK"):
        raise AppException("VALIDATION_ERROR", "action 必须是 REASONABLE/ABNORMAL/TO_RISK")
    if not comment or len(comment.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "处理意见必填且不少于 5 字")
    with session() as db:
        c = db.get(AttendanceException, _as_id(exception_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("打卡异常不存在")
        rec, stu = _exc_ctx(db, c)
        if not _rec_in_scope(_current_scope(user), db, rec, stu):  # P1：owner 级写校验
            from app.core.exceptions import no_permission
            raise no_permission("只能处理本人指导学生的打卡异常")
        if c.status == "COMPLETED":
            raise AppException("DATA_CONFLICT", "该异常已处理，请刷新")
        from app.modules.internship.services.internship_version import (
            extract_expected_version, versioned_update,
        )
        ver = extract_expected_version({"expectedVersion": expected_version})
        values = {"status": "COMPLETED", "handle_action": action, "handle_comment": comment.strip(),
                  "handled_by_name": _op_name(), "handled_at": datetime.utcnow()}
        if c.appeal_status == "PENDING":
            values["appeal_status"] = "ACCEPTED" if action == "REASONABLE" else "REJECTED"
        new_ver = versioned_update(db, AttendanceException, entity_id=c.id, tenant_id=_tid(),
                                   expected_version=ver, values=values,
                                   extra_where=(AttendanceException.status != "COMPLETED",))
        # 转风险：自动生成风险单
        if action == "TO_RISK":
            db.add(RiskRecord(tenant_id=_tid(), internship_id=c.internship_id,
                              risk_code="INT-R07", risk_title="打卡异常转风险跟进",
                              risk_level="HIGH", source_module="system", owner_name=_op_name(),
                              deadline_at=datetime.utcnow() + timedelta(days=3),
                              status="PENDING_HANDLE"))
            rec = tenant_get(db, InternshipRecord, c.internship_id)
            if rec:
                rec.risk_level = "HIGH"
        _trail(db, c.id, "EXCEPTION", f"HANDLE_{action}", {"comment": comment.strip()})
        from app.modules.internship.services import internship_todo_helper as ix_todo
        ix_todo.todo_done(db, biz_id=c.id, todo_type=ix_todo.TODO_EXCEPTION)
        db.commit()
        return {"id": str(c.id), "status": "COMPLETED", "version": new_ver,
                "statusLabel": {"REASONABLE": "已标记合理", "ABNORMAL": "已记为异常",
                                "TO_RISK": "已转风险"}[action]}


# ═══ 周报 ═══

def _report_snapshot(w: WeeklyReport) -> dict:
    """周报某一版的正文快照（写入留痕 detail_json，作为版本记录的真实数据源）。"""
    return {"version": int(w.report_version or 1), "wordCount": int(w.word_count or 0),
            "submittedAt": _iso(w.submitted_at) or "",
            "work": w.work_content or "", "harvest": w.harvest_content or "",
            "plan": w.plan_content or ""}


def _report_versions(trail, w: WeeklyReport) -> list[dict]:
    """版本记录（BUG-014）：从留痕中还原历史版本正文 + 当前版本，按版本号升序。
    历史退回快照来自 REVIEW_RETURN 留痕；无快照的老数据只呈现事件、不伪造正文。"""
    items = []
    for t in trail:
        snap = (t.detail_json or {}).get("snapshot")
        if not snap:
            continue
        cmt = (t.detail_json or {}).get("comment") or ""
        items.append({"version": f"v{snap.get('version', 1)}", "tone": "warning",
                      "title": f"v{snap.get('version', 1)} 已退回",
                      "desc": f"{snap.get('wordCount', 0)} 字 · 退回人 {t.operator_name or '系统'}"
                              + (f" · 意见：{cmt}" if cmt else ""),
                      "time": snap.get("submittedAt") or _iso(t.occurred_at) or "",
                      "operator": t.operator_name or "系统",
                      "comment": cmt,
                      "wordCount": snap.get("wordCount", 0),
                      "content": {"work": snap.get("work", ""), "harvest": snap.get("harvest", ""),
                                  "plan": snap.get("plan", "")}})
    cur = _report_snapshot(w)
    items.append({"version": f"v{cur['version']}", "tone": "processing" if w.status == "PENDING_REVIEW" else "success",
                  "title": f"v{cur['version']} {REPORT_STATUS_LABEL.get(w.status, w.status)}（当前版本）",
                  "desc": f"{cur['wordCount']} 字"
                          + (f" · 批阅人 {w.reviewed_by_name}" if w.reviewed_by_name else "")
                          + (f" · 意见：{w.review_comment}" if w.review_comment else ""),
                  "time": cur["submittedAt"], "operator": w.reviewed_by_name or "",
                  "comment": w.review_comment or "", "wordCount": cur["wordCount"],
                  "content": {"work": cur["work"], "harvest": cur["harvest"], "plan": cur["plan"]}})
    return items


def _report_row(w: WeeklyReport, rec: InternshipRecord | None, stu: StudentProfile | None,
                class_name: str | None = None) -> dict:
    return {
        "id": str(w.id), "internId": str(w.internship_id),
        "studentName": stu.real_name if stu else "-",
        "className": class_name or "-",
        "enterpriseName": rec.enterprise_name if rec else "",
        "week": f"第 {w.week_number} 周", "submitAt": _iso(w.submitted_at) or "",
        "version": int(w.version or 0), "reportVersion": f"v{w.report_version}",
        "isResubmit": w.report_version > 1,
        "wordCount": w.word_count, "riskFlag": w.risk_flag or "",
        "status": w.status, "statusLabel": REPORT_STATUS_LABEL.get(w.status, w.status),
    }


def list_weekly_reports(page, page_size, status=None, keyword=None, batch_id=None, user=None):
    with session() as db:
        from app.models import SchoolClass
        from app.modules.internship.services.internship_batch_context import resolve_batch
        from app.modules.internship.services.internship_scope import apply_internship_record_scope

        batch = resolve_batch(db, batch_id)
        q = select(
            WeeklyReport, InternshipRecord, StudentProfile, SchoolClass.class_name,
        ).join(
            InternshipRecord, InternshipRecord.id == WeeklyReport.internship_id,
        ).join(
            StudentProfile, StudentProfile.id == InternshipRecord.student_id,
        ).outerjoin(
            SchoolClass, SchoolClass.id == StudentProfile.class_id,
        ).where(
            WeeklyReport.tenant_id == _tid(), WeeklyReport.is_deleted.is_(False),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.is_deleted.is_(False),
        )
        q = apply_internship_record_scope(q, user)
        if status:
            q = q.where(WeeklyReport.status == status)
        if keyword:
            value = f"%{keyword.strip()}%"
            q = q.where(or_(
                StudentProfile.real_name.like(value), StudentProfile.student_no.like(value),
            ))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        if int(page_size or 0) <= 0:
            return [], total
        rows = db.execute(q.order_by(
            WeeklyReport.submitted_at.is_(None), WeeklyReport.submitted_at.desc(),
            WeeklyReport.id.desc(),
        ).offset(
            (max(1, int(page)) - 1) * int(page_size),
        ).limit(int(page_size))).all()
        return [_report_row(w, rec, stu, class_name=class_name)
                for w, rec, stu, class_name in rows], total


def get_weekly_report_detail(report_id, user=None) -> dict:
    with session() as db:
        w = db.get(WeeklyReport, _as_id(report_id))
        if not w or w.is_deleted or w.tenant_id != _tid():
            raise not_found("周报不存在")
        rec = db.get(InternshipRecord, w.internship_id)
        stu = db.get(StudentProfile, rec.student_id) if rec else None
        if not _rec_in_scope(_current_scope(user), db, rec, stu):  # P0-D
            from app.core.exceptions import no_permission
            raise no_permission("该周报不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_id == w.id,
            InternshipAuditTrail.target_type == "REPORT").order_by(InternshipAuditTrail.id)).all()
        row = _report_row(w, rec, stu)
        row.update({
            "positionName": rec.position_name if rec else "",
            "content": {"work": w.work_content or "", "harvest": w.harvest_content or "",
                        "plan": w.plan_content or ""},
            "reviewComment": w.review_comment or "",
            "versions": _report_versions(trail, w),
            "trail": [{"who": t.operator_name or "系统", "time": _iso(t.occurred_at),
                       "action": t.action,
                       "affected": json.dumps(t.detail_json or {}, ensure_ascii=False)} for t in trail],
        })
        return row


def review_weekly_report(report_id, action: str, comment: str, user=None, *, expected_version=None) -> dict:
    if action not in ("APPROVE", "RETURN"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/RETURN")
    if action == "RETURN" and (not comment or len(comment.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        w = db.get(WeeklyReport, _as_id(report_id))
        if not w or w.is_deleted or w.tenant_id != _tid():
            raise not_found("周报不存在")
        rec = tenant_get(db, InternshipRecord, w.internship_id)
        stu = tenant_get(db, StudentProfile, rec.student_id) if rec else None
        if not _rec_in_scope(_current_scope(user), db, rec, stu):  # P1：owner 级写校验
            from app.core.exceptions import no_permission
            raise no_permission("只能批阅本人指导学生的周报")
        if w.status in ("APPROVED", "RETURNED"):
            raise AppException("DATA_CONFLICT", "该周报已批阅，请刷新")
        from app.modules.internship.services.internship_version import (
            extract_expected_version, versioned_update,
        )
        ver = extract_expected_version({"expectedVersion": expected_version})
        status = "APPROVED" if action == "APPROVE" else "RETURNED"
        new_ver = versioned_update(
            db, WeeklyReport, entity_id=w.id, tenant_id=_tid(), expected_version=ver,
            expected_status=w.status, values={"status": status, "review_action": action,
                                               "review_comment": (comment or "").strip(),
                                               "reviewed_by_name": _op_name(), "reviewed_at": datetime.utcnow()})
        detail = {"comment": (comment or "").strip()}
        if action == "RETURN":
            # BUG-014：退回即冻结本版正文快照，学生重交后教师仍可逐版对比（版本记录数据源）
            detail["snapshot"] = _report_snapshot(w)
        _trail(db, w.id, "REPORT", f"REVIEW_{action}", detail)
        from app.modules.internship.services import internship_todo_helper as ix_todo
        ix_todo.todo_done(db, biz_id=w.id, todo_type=ix_todo.TODO_WEEKLY)
        db.commit()
        return {"id": str(w.id), "status": status, "version": new_ver,
                "statusLabel": REPORT_STATUS_LABEL.get(status, status)}


def batch_review_weekly_reports(body, user=None) -> dict:
    """批量通过/退回：每条必须自带 expectedVersion，禁止先查版本再无条件更新。"""
    b = body or {}
    action = (b.get("action") or "APPROVE").strip().upper()
    comment = (b.get("comment") or "").strip()
    items = b.get("items")
    if not items:
        # 兼容：ids + versions 并行数组；禁止仅传 ids
        ids = b.get("ids") or []
        versions = b.get("versions") or b.get("expectedVersions") or []
        if ids and not versions:
            raise AppException("VALIDATION_ERROR", "批量批阅必须为每条提供 expectedVersion")
        if len(versions) != len(ids):
            raise AppException("VALIDATION_ERROR", "ids 与 expectedVersion 数量不一致")
        items = [{"id": i, "expectedVersion": v} for i, v in zip(ids, versions)]
    if not items:
        raise AppException("VALIDATION_ERROR", "请选择要批阅的周报")
    if action == "RETURN" and len(comment) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    approved = skipped = 0
    failures = []
    for it in items:
        rid = (it or {}).get("id")
        ver = (it or {}).get("expectedVersion", (it or {}).get("version"))
        try:
            review_weekly_report(rid, action, comment, user=user, expected_version=ver)
            approved += 1
        except AppException as e:
            if e.code in ("DATA_CONFLICT", "VALIDATION_ERROR", "NOT_FOUND", "NO_PERMISSION", "FORBIDDEN"):
                skipped += 1
                failures.append({"id": str(rid), "code": e.code, "message": e.message})
            else:
                raise
    return {
        "approvedCount": approved if action == "APPROVE" else 0,
        "returnedCount": approved if action == "RETURN" else 0,
        "skippedCount": skipped,
        "failures": failures,
    }


def remind_weekly_report(report_id, channel="站内消息", user=None) -> dict:
    """向周报所属学生发送真实站内提醒；无账号映射时明确失败，不伪造成功。"""
    from app.models import UnifiedMessage, User
    with session() as db:
        w = db.get(WeeklyReport, _as_id(report_id))
        if not w or w.is_deleted or w.tenant_id != _tid():
            raise not_found("周报不存在")
        rec = db.get(InternshipRecord, w.internship_id)
        stu = db.get(StudentProfile, rec.student_id) if rec else None
        if not _rec_in_scope(_current_scope(user), db, rec, stu):
            from app.core.exceptions import no_permission
            raise no_permission("只能提醒本人指导学生")
        if w.status == "APPROVED":
            raise AppException("DATA_CONFLICT", "周报已通过，无需催交")
        # 经账号绑定解析（阶段 C），绑定缺失时按学号兜底
        from app.services import student_account_link_service as link_svc
        acct_id = link_svc.resolve_user_id_for_student(
            db, tenant_id=_tid(),
            student_id=(getattr(stu, "student_id", None) or getattr(stu, "id", None)),
            student_no=(stu.student_no if stu else None))
        account = db.get(User, acct_id) if acct_id else None
        if not account:
            raise AppException("DATA_NOT_FOUND", "学生账号未建立，无法发送提醒")
        recent = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_id == w.id,
            InternshipAuditTrail.target_type == "REPORT", InternshipAuditTrail.action == "REMIND",
            InternshipAuditTrail.occurred_at >= datetime.utcnow() - timedelta(minutes=5))).first()
        if recent:
            raise AppException("DATA_CONFLICT", "5 分钟内已提醒，请勿重复操作")
        from app.services.message_event_outbox_service import emit_receiver_notice
        emit_receiver_notice(
            db,
            event_code="INTERNSHIP.WEEKLY_REMIND",
            source_module="internship",
            source_biz_type="weekly_report",
            source_biz_id=w.id,
            receiver_id=account.id,
            title=f"第 {w.week_number} 周实习周报提醒",
            content=f"请及时查看并完成第 {w.week_number} 周实习周报。",
            receiver_as="user",
        )
        _trail(db, w.id, "REPORT", "REMIND", {"channel": channel or "站内消息",
                                                "receiverId": str(account.id)})
        db.commit()
        from app.services.message_event_outbox_service import try_process_pending_outbox
        try_process_pending_outbox(worker_id="internship-inline")
        return {"id": str(w.id), "reminded": True, "channel": channel or "站内消息"}


def export_weekly_reports(status=None, keyword=None, batch_id=None, user=None) -> dict:
    from app.services import xlsx_util
    from app.modules.internship.services.internship_export_util import load_export_rows
    items, total = load_export_rows(
        list_weekly_reports, status=status, keyword=keyword, batch_id=batch_id, user=user)
    from app.modules.internship.services.internship_export_util import pack_export_meta, require_exportable
    require_exportable(total)
    headers = ["学生", "班级", "企业", "周次", "提交时间", "版本", "字数", "风险", "状态"]
    rows = [[it["studentName"], it["className"], it["enterpriseName"], it["week"],
             it["submitAt"], it["version"], it["wordCount"], it["riskFlag"],
             it["statusLabel"]] for it in items]
    wm = f"岗位实习中心·周报台账 · 导出人：{_op_name()} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("周报台账", headers, rows, watermark=wm)
    packed = xlsx_util.pack_xlsx_result(content, "周报台账.xlsx", len(items))
    packed.update(pack_export_meta(total, len(items)))
    return packed


# ═══ 风险学生 ═══

def list_risk_students(page, page_size, level=None, status=None, keyword=None,
                       risk_code=None, batch_id=None, user=None):
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_risk_service import _source_truth
    with session() as db:
        batch = resolve_batch(db, batch_id, for_write=False)
        rec_ids = db.scalars(select(InternshipRecord.id).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False),
            InternshipRecord.batch_id == batch.id,
        )).all()
        scoped_rec_ids = list(rec_ids) or [0]
        q = select(RiskRecord).where(
            RiskRecord.tenant_id == _tid(),
            RiskRecord.is_deleted.is_(False),
            RiskRecord.internship_id.in_(scoped_rec_ids),
        )
        if level:
            q = q.where(RiskRecord.risk_level == level)
        if status:
            q = q.where(RiskRecord.status == status)
        if risk_code:
            q = q.where(RiskRecord.risk_code == risk_code)
        rows = db.scalars(q.order_by(RiskRecord.id.desc())).all()
        scope = _current_scope(user)
        kw = (keyword or "").strip()
        items = []
        for k in rows:
            rec = tenant_get(db, InternshipRecord, k.internship_id)
            stu = tenant_get(db, StudentProfile, rec.student_id) if rec else None
            if not _rec_in_scope(scope, db, rec, stu):
                continue
            if kw and kw not in (stu.real_name or "") and kw not in (stu.student_no or ""):
                continue
            cn, _ = resolve_student_class_college_names(db, stu)
            source = _source_truth(db, k)
            items.append({
                "id": str(k.id), "internId": str(k.internship_id),
                "studentName": stu.real_name if stu else "-",
                "studentNo": stu.student_no if stu else "-",
                "className": cn or "-",
                "source": f"{k.risk_code} {k.risk_title}",
                "sourceDetail": k.source_module or "",
                "sourceType": source.get("sourceType", ""),
                "sourceId": source.get("sourceId", ""),
                "sourceIntegrity": source.get("sourceIntegrity", "LEGACY_UNSCOPED"),
                "sourceStatus": source.get("sourceStatus", ""),
                "sourceStatusLabel": source.get("sourceStatusLabel", ""),
                "latestEvent": source.get("latestEvent", k.last_follow_note or "风险单已创建"),
                "currentAction": source.get("currentAction", "受理并核实风险来源"),
                "closeAllowed": bool(source.get("closeAllowed", True)),
                "closeBlockers": source.get("closeBlockers", []),
                "level": k.risk_level, "riskLevel": k.risk_level,
                "owner": k.owner_name or "", "ownerName": k.owner_name or "",
                "deadline": _iso(k.deadline_at)[:10] if k.deadline_at else "",
                "deadlineAt": _iso(k.deadline_at) or "",
                "lastFollow": k.last_follow_note or "—",
                "lastFollowNote": k.last_follow_note or "",
                "status": k.status, "statusLabel": RISK_STATUS_LABEL.get(k.status, k.status),
                "version": int(k.version or 0),
                "batchId": str(batch.id),
            })
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


# ═══ 实习批次（组织时间轴 + 规则骨架 + 状态机 DRAFT→RUNNING→CLOSED→ARCHIVED；VOIDED 仅草稿可达） ═══

def _batch_actual_count(db, batch_id: int) -> int:
    return db.scalar(select(func.count()).select_from(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(), InternshipRecord.batch_id == batch_id,
        InternshipRecord.is_deleted.is_(False))) or 0


def _batch_row(db, b: InternshipBatch) -> dict:
    return {
        "id": str(b.id), "batchName": b.batch_name, "batchNo": b.batch_no,
        "academicYear": b.academic_year or "", "term": b.term or "",
        "startDate": _iso(b.start_date) or "", "endDate": _iso(b.end_date) or "",
        "signupStartDate": _iso(b.signup_start_date) or "", "signupEndDate": _iso(b.signup_end_date) or "",
        "plannedCount": int(b.planned_count or 0), "actualCount": _batch_actual_count(db, b.id),
        "status": b.status, "statusLabel": BATCH_STATUS_LABEL.get(b.status, b.status),
        "archiveStatus": b.archive_status or "NOT_ARCHIVED",
        "rulesVersion": int(b.rules_version or 1),
        "version": int(b.version or 0),
        "remark": b.remark or "", "updateTime": _iso(b.updated_at),
        "createTime": _iso(b.created_at) or "",
    }


def _batch_detail_row(db, b: InternshipBatch) -> dict:
    row = _batch_row(db, b)
    trail = db.scalars(select(InternshipAuditTrail).where(
        InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_id == b.id,
        InternshipAuditTrail.target_type == "BATCH").order_by(InternshipAuditTrail.id.desc())).all()
    row.update({
        "stages": b.stage_config or DEFAULT_STAGES,
        "rules": b.rules_config or DEFAULT_RULES,
        "rulesVersion": int(b.rules_version or 1),
        "previousStatus": b.previous_status or "",
        "lastTransitionAt": _iso(b.last_transition_at) or "",
        "lastTransitionBy": b.last_transition_by or "",
        "transitionReason": b.transition_reason or "",
        "archivedAt": _iso(b.archived_at) or "", "archivedBy": b.archived_by or "",
        "archiveBatchNo": b.archive_batch_no or "",
        "auditTrail": [{"id": str(t.id), "action": t.action, "operator": t.operator_name or "系统",
                        "time": _iso(t.occurred_at),
                        "detail": json.dumps(t.detail_json or {}, ensure_ascii=False)} for t in trail],
    })
    return row


def _pick_current_batch(db):
    """已废弃静默选批：多 RUNNING 时不得自动取第一条。
    保留函数仅供内部诊断；业务入口必须显式传入 batchId。
    返回：唯一 RUNNING → 该批次；0 个 RUNNING → None；多个 RUNNING → None。
    """
    rows = db.scalars(select(InternshipBatch).where(
        InternshipBatch.tenant_id == _tid(),
        InternshipBatch.is_deleted.is_(False),
        InternshipBatch.status == "RUNNING",
    ).order_by(InternshipBatch.id.desc())).all()
    if len(rows) == 1:
        return rows[0]
    return None


def _get_batch(db, bid) -> InternshipBatch:
    b = db.get(InternshipBatch, _as_id(bid))
    if not b or b.is_deleted or b.tenant_id != _tid():
        raise not_found("实习批次不存在或不在当前数据范围内")
    return b


def _deep_merge(base: dict, patch: dict) -> dict:
    """按 key 递归合并：patch 中未出现的分组/字段保留 base 原值，避免局部提交冲掉整段配置。"""
    out = dict(base or {})
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _merge_rules(base: dict | None, patch: dict | None) -> dict:
    """合并规则配置并回灌 RulesConfig 做一次类型/范围校验，返回校验后的标准 dict。"""
    merged = _deep_merge(base or DEFAULT_RULES, patch or {})
    try:
        return RulesConfig(**merged).model_dump()
    except Exception as e:  # noqa: BLE001 — pydantic ValidationError 统一转业务校验错误
        raise AppException("VALIDATION_ERROR", f"规则配置格式不正确：{e}") from e


def _dump_stages(stages) -> list:
    try:
        return [StageItem(**s).model_dump() if isinstance(s, dict) else s.model_dump() for s in stages]
    except Exception as e:  # noqa: BLE001
        raise AppException("VALIDATION_ERROR", f"阶段时间轴格式不正确：{e}") from e


def list_batches(page, page_size, keyword=None, status=None):
    with session() as db:
        q = select(InternshipBatch).where(InternshipBatch.tenant_id == _tid(),
                                          InternshipBatch.is_deleted.is_(False))
        if status:
            q = q.where(InternshipBatch.status == status)
        rows = db.scalars(q.order_by(InternshipBatch.id.desc())).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.batch_name or "") or kw in (r.batch_no or "")]
        items = [_batch_row(db, r) for r in rows]
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_batch(bid) -> dict:
    with session() as db:
        return _batch_detail_row(db, _get_batch(db, bid))


def _assert_batch_dates(start, end, signup_start, signup_end) -> None:
    """批次日期区间校验（BUG-008）：起止不得颠倒，报名期不得晚于实习结束。"""
    if start and end and start > end:
        raise AppException("VALIDATION_ERROR",
                           f"实习开始日期不能晚于结束日期（{_iso(start)[:10]} > {_iso(end)[:10]}）")
    if signup_start and signup_end and signup_start > signup_end:
        raise AppException("VALIDATION_ERROR",
                           f"报名开始日期不能晚于报名截止日期（{_iso(signup_start)[:10]} > {_iso(signup_end)[:10]}）")
    if signup_end and end and signup_end > end:
        raise AppException("VALIDATION_ERROR", "报名截止日期不能晚于实习结束日期")


def create_batch(body: dict, user=None) -> dict:
    assert_admin_tenant(user or get_current_user_ctx() or {}, "创建实习批次")
    name = str(body.get("batchName") or "").strip()
    no = str(body.get("batchNo") or "").strip()
    if not name or not no:
        raise AppException("VALIDATION_ERROR", "批次名称与批次编号必填")
    start = _parse_dt(body.get("startDate"), "实习开始日期")
    end = _parse_dt(body.get("endDate"), "实习结束日期")
    signup_start = _parse_dt(body.get("signupStartDate"), "报名开始日期")
    signup_end = _parse_dt(body.get("signupEndDate"), "报名截止日期")
    _assert_batch_dates(start, end, signup_start, signup_end)
    planned_count = _parse_nonnegative_int(body.get("plannedCount"), "计划人数")
    with session() as db:
        dup = db.scalars(select(InternshipBatch).where(
            InternshipBatch.tenant_id == _tid(), InternshipBatch.batch_no == no,
            InternshipBatch.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", f"批次编号 {no} 已存在")
        stages = _dump_stages(body.get("stages")) if body.get("stages") else list(DEFAULT_STAGES)
        rules = _merge_rules(DEFAULT_RULES, body.get("rules"))
        template_id = body.get("complianceTemplateId")
        template_version = None
        if template_id:
            from app.modules.internship.services.internship_compliance_template_service import get_active
            active = get_active(db)
            if not active or active.id != _as_id(template_id):
                raise AppException("VALIDATION_ERROR", "指定合规模板不是当前有效模板")
            rules["compliance"] = active.config or rules["compliance"]
            template_version = active.template_version
        b = InternshipBatch(
            tenant_id=_tid(), batch_name=name, batch_no=no,
            academic_year=body.get("academicYear"), term=body.get("term"),
            start_date=start, end_date=end,
            signup_start_date=signup_start, signup_end_date=signup_end,
            planned_count=planned_count, remark=body.get("remark"),
            status="DRAFT", stage_config=stages, rules_config=rules, archive_status="NOT_ARCHIVED",
            compliance_template_id=_as_id(template_id) if template_id else None,
            compliance_template_version=template_version)
        db.add(b)
        db.flush()
        _trail(db, b.id, "BATCH", "CREATE", {"batchName": name, "batchNo": no})
        db.commit()
        return {"id": str(b.id), "version": int(b.version or 0)}


def update_batch(bid, body: dict, user=None) -> dict:
    from app.modules.internship.services.internship_version import (
        extract_expected_version, versioned_update,
    )
    from app.models import InternshipBatch
    assert_admin_tenant(user or get_current_user_ctx() or {}, "编辑实习批次")
    ver = extract_expected_version(body)
    with session() as db:
        b = _get_batch(db, bid)
        if b.status in ("CLOSED", "ARCHIVED", "VOIDED"):
            raise AppException("INVALID_STATE", "已结束/已归档/已作废的批次不可编辑")
        values = {}
        for k, col in {"batchName": "batch_name", "academicYear": "academic_year",
                       "term": "term", "remark": "remark"}.items():
            if body.get(k) is not None:
                values[col] = body[k]
        for k, col, label in (
            ("startDate", "start_date", "实习开始日期"),
            ("endDate", "end_date", "实习结束日期"),
            ("signupStartDate", "signup_start_date", "报名开始日期"),
            ("signupEndDate", "signup_end_date", "报名截止日期"),
        ):
            if body.get(k) is not None:
                values[col] = _parse_dt(body[k], label)
        start = values.get("start_date", b.start_date)
        end = values.get("end_date", b.end_date)
        ss = values.get("signup_start_date", b.signup_start_date)
        se = values.get("signup_end_date", b.signup_end_date)
        _assert_batch_dates(start, end, ss, se)
        if body.get("plannedCount") is not None:
            values["planned_count"] = _parse_nonnegative_int(body["plannedCount"], "计划人数")
        if body.get("stages") is not None:
            values["stage_config"] = _dump_stages(body["stages"])
        rules_version = int(b.rules_version or 1)
        if body.get("rules") is not None:
            if b.status != "DRAFT":
                raise AppException("DATA_CONFLICT", "批次启用后规则不可原地修改，请新建批次版本")
            values["rules_config"] = _merge_rules(b.rules_config, body["rules"])
            rules_version = rules_version + 1
            values["rules_version"] = rules_version
        if not values:
            raise AppException("VALIDATION_ERROR", "没有可更新的字段")
        new_ver = versioned_update(
            db, InternshipBatch, entity_id=b.id, tenant_id=_tid(),
            expected_version=ver, values=values)
        _trail(db, b.id, "BATCH", "UPDATE", {"rulesVersion": rules_version})
        db.commit()
        return {"id": str(b.id), "version": new_ver}


def activate_batch(bid, user=None, *, expected_version=None) -> dict:
    from app.modules.internship.services.internship_version import (
        extract_expected_version, versioned_update,
    )
    from app.models import InternshipBatch
    assert_admin_tenant(user or get_current_user_ctx() or {}, "启用实习批次")
    ver = extract_expected_version({"expectedVersion": expected_version})
    with session() as db:
        b = _get_batch(db, bid)
        now = datetime.utcnow()
        frozen_rules = dict(b.rules_config or {})
        if b.compliance_template_id:
            from app.models import InternshipComplianceTemplate
            t = db.get(InternshipComplianceTemplate, b.compliance_template_id)
            if not t or t.tenant_id != _tid():
                raise AppException("DATA_CONFLICT", "关联合规模板不存在")
            frozen_rules["compliance"] = t.config or frozen_rules.get("compliance", {})
            frozen_rules["compliance_template_version"] = t.template_version
        frozen_rules["_complianceFrozen"] = True
        frozen_rules["_frozenAt"] = now.isoformat()
        new_ver = versioned_update(
            db, InternshipBatch, entity_id=b.id, tenant_id=_tid(), expected_version=ver,
            values={
                "previous_status": "DRAFT", "status": "RUNNING",
                "last_transition_at": now, "last_transition_by": _op_name(),
                "rules_config": frozen_rules,
                "compliance_template_version": frozen_rules.get("compliance_template_version", b.compliance_template_version),
            },
            expected_status="DRAFT")
        _trail(db, b.id, "BATCH", "ACTIVATE", {"before": "DRAFT", "after": "RUNNING"})
        db.commit()
        return {"id": str(b.id), "status": "RUNNING", "statusLabel": BATCH_STATUS_LABEL["RUNNING"],
                "version": new_ver}


def _batch_compliance_report(db, batch_id, user) -> dict:
    from collections import defaultdict
    from app.modules.internship.services.internship_compliance_service import (
        evaluate_internship_compliance)
    records = db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.batch_id == _as_id(batch_id),
        InternshipRecord.is_deleted.is_(False))).all()
    missing = defaultdict(list)
    blocked_students = []
    rule_version = None
    for rec in records:
        result = evaluate_internship_compliance(
            rec.id, "BATCH_CLOSE", user=user, db=db)
        rule_version = rule_version or result["ruleVersion"]
        codes = []
        for item in result["blockers"]:
            missing[item["code"]].append(str(rec.id))
            codes.append(item["code"])
        if codes:
            blocked_students.append({
                "internshipId": str(rec.id), "studentId": str(rec.student_id),
                "codes": codes})
    return {
        "total": len(records), "blocked": len(blocked_students),
        "passed": len(records) - len(blocked_students),
        "missingByCode": {code: {"count": len(ids), "internshipIds": ids}
                          for code, ids in missing.items()},
        "blockedStudents": blocked_students,
        "ruleVersion": rule_version,
        "evaluatedAt": datetime.utcnow().isoformat() + "Z",
    }


def close_batch(bid, user=None, *, force: bool = False, force_reason: str = "",
                expected_version=None) -> dict:
    """结束批次：先生成就绪报告；存在阻断项时拒绝，除非管理员强制结束并写审计。"""
    from app.modules.internship.services.internship_version import (
        extract_expected_version, versioned_update,
    )
    from app.models import InternshipBatch
    assert_admin_tenant(user or get_current_user_ctx() or {}, "结束实习批次")
    ver = extract_expected_version({"expectedVersion": expected_version})
    with session() as db:
        b = _get_batch(db, bid)
        if b.status != "RUNNING":
            raise AppException("INVALID_STATE", "仅进行中批次可结束")
        report = _batch_compliance_report(db, b.id, user)
        if report["blocked"] and not force:
            raise AppException(
                "DATA_CONFLICT",
                "批次结束前置检查未通过，请先处理阻断项或使用强制结束",
                details={"compliance": report},
            )
        reason = ""
        if force:
            reason = (force_reason or "").strip()
            if len(reason) < 5:
                raise AppException("VALIDATION_ERROR", "强制结束必须填写原因（不少于 5 字）")
        now = datetime.utcnow()
        values = {
            "previous_status": "RUNNING", "status": "CLOSED",
            "last_transition_at": now, "last_transition_by": _op_name(),
        }
        if force:
            values["transition_reason"] = reason
        new_ver = versioned_update(
            db, InternshipBatch, entity_id=b.id, tenant_id=_tid(), expected_version=ver,
            values=values, expected_status="RUNNING")
        detail = {"before": "RUNNING", "after": "CLOSED", "compliance": report}
        if force:
            detail["force"] = True
            detail["forceReason"] = reason
        _trail(db, b.id, "BATCH", "CLOSE", detail)
        db.commit()
        return {
            "id": str(b.id), "status": "CLOSED", "statusLabel": BATCH_STATUS_LABEL["CLOSED"],
            "compliance": report, "forced": bool(force), "version": new_ver,
        }


def archive_batch(bid, user=None, *, force: bool = False, force_reason: str = "",
                  expected_version=None) -> dict:
    from app.modules.internship.services.internship_version import (
        extract_expected_version, versioned_update,
    )
    from app.models import InternshipBatch
    assert_admin_tenant(user or get_current_user_ctx() or {}, "归档实习批次")
    ver = extract_expected_version({"expectedVersion": expected_version})
    with session() as db:
        b = _get_batch(db, bid)
        if b.status != "CLOSED":
            raise AppException("INVALID_STATE", "仅已结束批次可归档")
        report = _batch_compliance_report(db, b.id, user)
        not_archived_ids = [str(x.id) for x in db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.batch_id == b.id,
            InternshipRecord.status != "ARCHIVED",
            InternshipRecord.is_deleted.is_(False))).all()]
        if (report["blocked"] or not_archived_ids) and not force:
            raise AppException(
                "DATA_CONFLICT",
                "仍有学生未完成归档，请先完成学生归档或强制归档批次",
                details={"compliance": report, "notArchivedIds": not_archived_ids},
            )
        reason = ""
        if force:
            reason = (force_reason or "").strip()
            if len(reason) < 5:
                raise AppException("VALIDATION_ERROR", "强制归档必须填写原因（不少于 5 字）")
        now = datetime.utcnow()
        values = {
            "previous_status": "CLOSED", "status": "ARCHIVED",
            "archive_status": "ARCHIVED", "archived_at": now, "archived_by": _op_name(),
            "archive_batch_no": b.batch_no, "last_transition_at": now,
            "last_transition_by": _op_name(),
        }
        if force:
            values["transition_reason"] = reason
        new_ver = versioned_update(
            db, InternshipBatch, entity_id=b.id, tenant_id=_tid(), expected_version=ver,
            values=values, expected_status="CLOSED")
        detail = {"before": "CLOSED", "after": "ARCHIVED",
                  "compliance": report, "notArchivedIds": not_archived_ids}
        if force:
            detail["force"] = True
            detail["forceReason"] = reason
        _trail(db, b.id, "BATCH", "ARCHIVE", detail)
        db.commit()
        return {
            "id": str(b.id), "status": "ARCHIVED", "statusLabel": BATCH_STATUS_LABEL["ARCHIVED"],
            "compliance": report, "notArchivedIds": not_archived_ids,
            "forced": bool(force), "version": new_ver,
        }


def batch_readiness(bid, user=None) -> dict:
    """只读：批次结束/归档前置检查报告。"""
    with session() as db:
        b = _get_batch(db, bid)
        report = _batch_compliance_report(db, b.id, user)
        report["batchId"] = str(b.id)
        report["batchStatus"] = b.status
        return report


def _batch_readiness_report(db, batch_id: int) -> dict:
    """生成批次就绪报告（结束/归档共用）。"""
    from app.models import (InternshipAgreement, InternshipEnterpriseEval, InternshipFinalScore,
                            InternshipInsurance, InternshipStudentEval, WeeklyReport)

    recs = db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False),
        InternshipRecord.batch_id == batch_id)).all()
    ids = [r.id for r in recs] or [0]

    def _cnt(model, *conds):
        return int(db.scalar(select(func.count()).select_from(model).where(
            model.tenant_id == _tid(), model.is_deleted.is_(False),
            model.internship_id.in_(ids), *conds)) or 0)

    no_position = sum(1 for r in recs if not r.position_id and r.status != "ARCHIVED")
    open_high_risk = _cnt(RiskRecord, RiskRecord.status.in_(["PENDING_HANDLE", "PROCESSING"]),
                          RiskRecord.risk_level == "HIGH")
    pending_weekly = _cnt(WeeklyReport, WeeklyReport.status == "PENDING_REVIEW")
    # 协议未生效：无 EFFECTIVE 协议的学生数（近似：记录 agreement_info 非生效且未归档）
    uneffective_agreement = 0
    unverified_insurance = 0
    missing_ent_eval = 0
    missing_stu_eval = 0
    unpublished_score = 0
    not_archived = sum(1 for r in recs if r.status != "ARCHIVED")
    for r in recs:
        if r.status == "ARCHIVED":
            continue
        agr = db.scalars(select(InternshipAgreement).where(
            InternshipAgreement.tenant_id == _tid(), InternshipAgreement.internship_id == r.id,
            InternshipAgreement.is_deleted.is_(False)).order_by(InternshipAgreement.id.desc())).first()
        if not agr or agr.status not in ("EFFECTIVE", "ARCHIVED"):
            uneffective_agreement += 1
        ins = db.scalars(select(InternshipInsurance).where(
            InternshipInsurance.tenant_id == _tid(), InternshipInsurance.internship_id == r.id,
            InternshipInsurance.is_deleted.is_(False)).order_by(InternshipInsurance.id.desc())).first()
        if not ins or ins.status != "VERIFIED":
            unverified_insurance += 1
        ee = db.scalars(select(InternshipEnterpriseEval).where(
            InternshipEnterpriseEval.tenant_id == _tid(), InternshipEnterpriseEval.internship_id == r.id,
            InternshipEnterpriseEval.is_deleted.is_(False),
            InternshipEnterpriseEval.submit_status == "SUBMITTED")).first()
        if not ee:
            missing_ent_eval += 1
        se = db.scalars(select(InternshipStudentEval).where(
            InternshipStudentEval.tenant_id == _tid(), InternshipStudentEval.internship_id == r.id,
            InternshipStudentEval.is_deleted.is_(False),
            InternshipStudentEval.submit_status == "SUBMITTED")).first()
        if not se:
            missing_stu_eval += 1
        sc = db.scalars(select(InternshipFinalScore).where(
            InternshipFinalScore.tenant_id == _tid(), InternshipFinalScore.internship_id == r.id,
            InternshipFinalScore.is_deleted.is_(False),
            InternshipFinalScore.status == "PUBLISHED")).first()
        if not sc:
            unpublished_score += 1

    checks = [
        {"key": "noPosition", "label": "未落实岗位", "count": no_position, "blocking": True},
        {"key": "uneffectiveAgreement", "label": "未生效协议", "count": uneffective_agreement, "blocking": False},
        {"key": "unverifiedInsurance", "label": "未核验保险", "count": unverified_insurance, "blocking": True},
        {"key": "openHighRisk", "label": "开放高风险", "count": open_high_risk, "blocking": True},
        {"key": "pendingWeekly", "label": "待批周报", "count": pending_weekly, "blocking": True},
        {"key": "missingEval", "label": "未完成评价", "count": missing_ent_eval + missing_stu_eval, "blocking": False},
        {"key": "unpublishedScore", "label": "未发布成绩", "count": unpublished_score, "blocking": True},
        {"key": "notArchived", "label": "未完成学生归档", "count": not_archived, "blocking": False},
    ]
    return {
        "totalStudents": len(recs),
        "checks": checks,
        "blockingCount": sum(1 for c in checks if c["blocking"] and c["count"] > 0),
        "warningCount": sum(1 for c in checks if (not c["blocking"]) and c["count"] > 0),
    }


def void_batch(bid, reason: str, user=None, *, expected_version=None) -> dict:
    from app.modules.internship.services.internship_version import (
        extract_expected_version, versioned_update,
    )
    from app.models import InternshipBatch
    assert_admin_tenant(user or get_current_user_ctx() or {}, "作废实习批次")
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    ver = extract_expected_version({"expectedVersion": expected_version})
    with session() as db:
        b = _get_batch(db, bid)
        if b.status != "DRAFT":
            raise AppException("INVALID_STATE", "仅草稿批次可作废；进行中/已结束请先按流程结束再归档")
        now = datetime.utcnow()
        reason_s = reason.strip()
        new_ver = versioned_update(
            db, InternshipBatch, entity_id=b.id, tenant_id=_tid(),
            expected_version=ver, expected_status="DRAFT",
            values={
                "previous_status": "DRAFT",
                "status": "VOIDED",
                "transition_reason": reason_s,
                "last_transition_at": now,
                "last_transition_by": _op_name(),
            },
        )
        _trail(db, b.id, "BATCH", "VOID", {"reason": reason_s})
        db.commit()
        return {
            "id": str(b.id), "status": "VOIDED",
            "statusLabel": BATCH_STATUS_LABEL["VOIDED"], "version": new_ver,
        }


def export_batches(keyword=None, status=None) -> dict:
    """导出实习批次 Excel 台账（按当前筛选）。"""
    from app.core.context import get_current_user_ctx
    from app.services import xlsx_util

    items, _total = list_batches(1, 10000, keyword=keyword, status=status)
    headers = ["批次名称", "批次编号", "学年", "学期", "开始时间", "结束时间", "状态",
               "是否当前批次", "规则摘要", "创建时间"]
    data_rows = []
    for r in items:
        rule_summary = (r.get("remark") or "")[:120]
        is_current = "是" if r.get("status") == "RUNNING" else "否"
        data_rows.append([
            r["batchName"], r["batchNo"], r["academicYear"], r["term"],
            (r["startDate"] or "")[:10], (r["endDate"] or "")[:10],
            r["statusLabel"], is_current, rule_summary,
            (r.get("createTime") or r.get("updateTime") or "")[:19]])
    user = get_current_user_ctx() or {}
    wm = (f"岗位实习中心·实习批次台账 · 导出人：{user.get('realName', '-')} · "
          f"{datetime.now():%Y-%m-%d %H:%M}")
    content = xlsx_util.build_ledger_xlsx("实习批次台账", headers, data_rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "实习批次台账.xlsx", len(items))


# ═══ 看板 ═══

def get_dashboard_summary(user=None, batch_id=None) -> dict:
    """工作台：标题与全部指标必须属于同一明确 batchId，禁止静默取第一条 RUNNING。"""
    from app.modules.internship.services.internship_batch_context import (
        batch_public_fields, resolve_batch)

    # permissionPatterns 简单匹配（与前端 matchPermission 同口径：* 通配）
    def _match(code: str) -> bool:
        patterns = list((user or {}).get("permissionPatterns") or [])
        if not patterns:
            return True
        for p in patterns:
            p = str(p)
            if p == code or p == "*":
                return True
            if p.endswith(".*") and code.startswith(p[:-1]):
                return True
        return False

    with session() as db:
        batch = resolve_batch(db, batch_id, for_write=False)
        batch_meta = batch_public_fields(batch)
        q = select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False),
            InternshipRecord.batch_id == batch.id,
        )
        # 20K Authority：数据范围必须下推 SQL，工作台只加载最终命中的 4/5 条对象，
        # 不能为了 8 条 Today First 在 Python 中装入整批学生再排序/过滤。
        from app.modules.internship.services.internship_scope import (
            apply_internship_record_scope,
        )
        scoped_query = apply_internship_record_scope(q, user).order_by(None)
        scoped_ids = scoped_query.with_only_columns(
            InternshipRecord.id, maintain_column_froms=True,
        ).subquery()
        scoped_id_select = select(scoped_ids.c.id)
        flow_map = {"PREPARING": 0, "READY": 0, "ONBOARD": 0, "ASSESSING": 0, "ARCHIVED": 0}
        progress_weights = {
            "PREPARING": 0.0, "READY": 0.25, "ONBOARD": 0.60, "ASSESSING": 0.85, "ARCHIVED": 1.0,
        }
        for status, count in db.execute(select(
            InternshipRecord.status, func.count(),
        ).where(
            InternshipRecord.id.in_(scoped_id_select),
        ).group_by(InternshipRecord.status)).all():
            flow_map[status] = int(count or 0)
        total_students = sum(flow_map.values())
        dest_none = int(db.scalar(select(func.count()).select_from(
            InternshipRecord,
        ).where(
            InternshipRecord.id.in_(scoped_id_select),
            func.coalesce(InternshipRecord.destination_type, "NONE") == "NONE",
        )) or 0)
        weight_sum = sum(
            progress_weights.get(status, 0.0) * count
            for status, count in flow_map.items()
        )
        preparing = flow_map["PREPARING"]
        ready = flow_map["READY"]
        onboard = flow_map["ONBOARD"]
        batch_progress = round(weight_sum / total_students * 100, 1) if total_students else 0
        onboard_rate = round(onboard / total_students * 100, 1) if total_students else 0

        def _cnt(model, *conds):
            q2 = select(func.count()).select_from(model).where(
                model.tenant_id == _tid(), model.is_deleted.is_(False),
                model.internship_id.in_(scoped_id_select), *conds)
            return db.scalar(q2) or 0

        pending_exc = _cnt(AttendanceException, AttendanceException.status == "PENDING_HANDLE")
        pending_rep = _cnt(WeeklyReport, WeeklyReport.status == "PENDING_REVIEW")
        risk_cnt = _cnt(RiskRecord, RiskRecord.status.in_(["PENDING_HANDLE", "PROCESSING"]))

        # 真实开放风险提醒（同批次 + 数据范围），按等级与更新时间排序，最多 5 条
        # 排序与截断下推 SQL：原来把全部开放风险装进内存再 Python 排序取前 5，
        # 风险表随多年历史增长时这条会越来越贵，而看板永远只用得上 5 条。
        # CASE 权重与原 level_rank 逐值对齐，未知等级同样排在最后。
        level_order = case(
            (RiskRecord.risk_level == "HIGH", 0),
            (RiskRecord.risk_level == "MEDIUM", 1),
            (RiskRecord.risk_level == "LOW", 2),
            else_=9,
        )
        risk_rows = db.scalars(
            select(RiskRecord).where(
                RiskRecord.tenant_id == _tid(), RiskRecord.is_deleted.is_(False),
                RiskRecord.status.in_(["PENDING_HANDLE", "PROCESSING"]),
                RiskRecord.internship_id.in_(scoped_id_select),
            ).order_by(level_order, RiskRecord.updated_at.desc(), RiskRecord.id.desc()).limit(5)
        ).all()
        # 这 5 条的记录与学生一次性取出，避免每条各查两次。
        alert_recs = {}
        alert_stus = {}
        if risk_rows:
            alert_recs = {r.id: r for r in db.scalars(select(InternshipRecord).where(
                InternshipRecord.id.in_({k.internship_id for k in risk_rows
                                         if k.internship_id}))).all()}
            alert_stu_ids = {r.student_id for r in alert_recs.values() if r.student_id}
            if alert_stu_ids:
                alert_stus = {s.id: s for s in db.scalars(select(StudentProfile).where(
                    StudentProfile.id.in_(alert_stu_ids))).all()}
        risk_alerts = []
        for k in risk_rows:
            rec = alert_recs.get(k.internship_id)
            stu = alert_stus.get(rec.student_id) if rec else None
            risk_alerts.append({
                "id": str(k.id),
                "internId": str(k.internship_id),
                "studentName": stu.real_name if stu else "-",
                "level": k.risk_level,
                "title": k.risk_title or k.risk_code or "风险",
                "status": k.status,
                "route": f"/admin/internship/risk-disposal?id={k.id}&batchId={batch.id}",
            })

        # Today First concrete objects.  This is a read projection over the existing
        # report / attendance / risk state machines; it deliberately does not create
        # another todo table or another workflow authority.  The dashboard returns a
        # bounded set of exact objects, and every command still executes on its owning
        # detail/workbench route with that route's permission and optimistic lock.
        report_rows = []
        if _match("internship.report.review"):
            report_rows = db.scalars(select(WeeklyReport).where(
                WeeklyReport.tenant_id == _tid(),
                WeeklyReport.is_deleted.is_(False),
                WeeklyReport.internship_id.in_(scoped_id_select),
                WeeklyReport.status == "PENDING_REVIEW",
            ).order_by(
                WeeklyReport.submitted_at.asc(), WeeklyReport.id.asc(),
            ).limit(4)).all()
        exception_rows = []
        if _match("internship.attendance.review"):
            exception_rows = db.scalars(select(AttendanceException).where(
                AttendanceException.tenant_id == _tid(),
                AttendanceException.is_deleted.is_(False),
                AttendanceException.internship_id.in_(scoped_id_select),
                AttendanceException.status == "PENDING_HANDLE",
            ).order_by(
                AttendanceException.streak_days.desc(),
                AttendanceException.exception_date.asc(),
                AttendanceException.id.asc(),
            ).limit(4)).all()

        work_internship_ids = {
            int(row.internship_id) for row in [*report_rows, *exception_rows, *risk_rows]
            if row.internship_id
        }
        work_rec_map = {}
        if work_internship_ids:
            work_rec_map = {int(row.id): row for row in db.scalars(select(
                InternshipRecord,
            ).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.id.in_(work_internship_ids),
                InternshipRecord.id.in_(scoped_id_select),
                InternshipRecord.is_deleted.is_(False),
            )).all()}
        work_student_ids = {int(row.student_id) for row in work_rec_map.values() if row.student_id}
        work_student_map = {}
        if work_student_ids:
            work_student_map = {int(row.id): row for row in db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(),
                StudentProfile.is_deleted.is_(False),
                StudentProfile.id.in_(work_student_ids),
            )).all()}

        def _work_subject(internship_id):
            record = work_rec_map.get(int(internship_id))
            student = work_student_map.get(int(record.student_id)) if record else None
            return record, student

        work_candidates = []
        if _match("internship.risk.handle"):
            for row in risk_rows:
                record, student = _work_subject(row.internship_id)
                student_name = student.real_name if student else "学生待核实"
                student_no = student.student_no if student else ""
                level_label = {"HIGH": "高风险", "MEDIUM": "中风险", "LOW": "低风险"}.get(
                    row.risk_level, "风险等级待核实")
                status_label = RISK_STATUS_LABEL.get(row.status, "状态待核实")
                work_candidates.append((
                    0 if row.risk_level == "HIGH" else 2,
                    row.deadline_at or row.updated_at or datetime.max,
                    {
                        "id": f"risk:{row.id}", "kind": "RISK", "objectId": str(row.id),
                        "internshipId": str(row.internship_id), "studentName": student_name,
                        "studentNo": student_no, "tone": "danger" if row.risk_level == "HIGH" else "warning",
                        "title": f"{student_name} · {row.risk_title or row.risk_code}",
                        "summary": f"{level_label} · {status_label}" +
                                   (f" · 责任人 {row.owner_name}" if row.owner_name else " · 尚未明确责任人"),
                        "whyHere": "风险单仍处于开放状态，需要核实事实、明确责任人与处置期限并持续留证。",
                        "recentChange": f"{_iso(row.updated_at) or '时间待核实'} · {status_label}",
                        "waitingOn": f"等待{row.owner_name}继续跟进" if row.owner_name else "等待领取并完成首次核实",
                        "nextActor": "办理后由责任人继续跟进；满足关闭条件后进入复核。",
                        "receipt": "动作会返回最新状态、版本和合法下一步，并写入风险审计时间线。",
                        "primaryActionLabel": "进入风险处置",
                        "route": f"/admin/internship/risk-disposal?id={row.id}&batchId={batch.id}",
                        "sourceVersion": int(row.version or 0),
                        "resumeKey": f"internship:risk:{row.id}:v{int(row.version or 0)}",
                    },
                ))
        for row in exception_rows:
            record, student = _work_subject(row.internship_id)
            student_name = student.real_name if student else "学生待核实"
            student_no = student.student_no if student else ""
            type_label = EXC_TYPE_LABEL.get(row.exception_type, "打卡异常")
            evidence = []
            if row.streak_days:
                evidence.append(f"连续 {row.streak_days} 天")
            if row.distance_km is not None:
                evidence.append(f"偏离 {row.distance_km:g} km")
            if row.device_risk_flag:
                evidence.append("设备信号待核实")
            work_candidates.append((
                1,
                row.exception_date or row.updated_at or datetime.max,
                {
                    "id": f"attendance:{row.id}", "kind": "ATTENDANCE_EXCEPTION",
                    "objectId": str(row.id), "internshipId": str(row.internship_id),
                    "studentName": student_name, "studentNo": student_no,
                    "tone": "danger" if (row.streak_days or 0) >= 3 else "warning",
                    "title": f"{student_name} · {type_label}待核实",
                    "summary": " · ".join(evidence) if evidence else "异常证据待人工核实",
                    "whyHere": "考勤规则命中风险信号；定位、设备和围栏信息只能辅助人工判断，不能自动定性。",
                    "recentChange": f"{_iso(row.exception_date) or '时间待核实'} · 系统标记待核实",
                    "waitingOn": "等待有处理权限的教师核对完整证据并作出判断",
                    "nextActor": "判定合理或异常后通知学生；转风险后由风险责任人继续跟进。",
                    "receipt": "提交后返回判定结果、版本和审计记录；冲突时保留当前输入并要求刷新事实。",
                    "primaryActionLabel": "核实异常",
                    "route": f"/admin/internship/exceptions/{row.id}?batchId={batch.id}",
                    "sourceVersion": int(row.version or 0),
                    "resumeKey": f"internship:attendance-exception:{row.id}:v{int(row.version or 0)}",
                },
            ))
        for row in report_rows:
            record, student = _work_subject(row.internship_id)
            student_name = student.real_name if student else "学生待核实"
            student_no = student.student_no if student else ""
            risk_hint = f" · 内容提示 {row.risk_flag}" if row.risk_flag else ""
            work_candidates.append((
                2 if row.risk_flag else 3,
                row.submitted_at or row.updated_at or datetime.max,
                {
                    "id": f"report:{row.id}", "kind": "WEEKLY_REPORT", "objectId": str(row.id),
                    "internshipId": str(row.internship_id), "studentName": student_name,
                    "studentNo": student_no, "tone": "danger" if row.risk_flag else "warning",
                    "title": f"{student_name} · 第 {row.week_number} 周周报",
                    "summary": f"v{row.report_version} · {row.word_count} 字{risk_hint}",
                    "whyHere": "学生已提交周报，等待指导教师核对正文、历史版本和风险提示后批阅。",
                    "recentChange": f"{_iso(row.submitted_at or row.updated_at) or '时间待核实'} · 学生提交 v{row.report_version}",
                    "waitingOn": "等待指导教师批阅",
                    "nextActor": "通过后学生收到结果；退回后学生按具体原因补充并重交。",
                    "receipt": "批阅结果、意见、版本和审计记录持久化；处理后可继续下一条。",
                    "primaryActionLabel": "批阅周报",
                    "route": f"/admin/internship/reports/{row.id}?batchId={batch.id}",
                    "sourceVersion": int(row.version or 0),
                    "resumeKey": f"internship:weekly-report:{row.id}:v{int(row.version or 0)}",
                },
            ))
        work_candidates.sort(key=lambda item: (item[0], item[1], item[2]["id"]))
        work_items = [item[2] for item in work_candidates[:8]]

        todos = []
        if pending_rep > 0 and _match("internship.report.review"):
            todos.append({"id": "todo-report", "label": "待批阅周报", "count": pending_rep,
                          "tone": "danger",
                          "route": f"/admin/internship/reports?batchId={batch.id}"})
        if pending_exc > 0 and _match("internship.attendance.review"):
            todos.append({"id": "todo-exc", "label": "待核实打卡异常", "count": pending_exc,
                          "tone": "warning",
                          "route": f"/admin/internship/exceptions?batchId={batch.id}"})
        if risk_cnt > 0 and _match("internship.risk.handle"):
            # 标签必须说明数的是「风险单张数」而不是「学生人数」：risk_cnt 是 RiskRecord
            # 行数，同一学生可同时挂多张开放风险单（如系统预警升级单 + 学生求助单），
            # 与统计页去重口径的「风险学生数」天然不等。这里跟随看板卡片已有的处理方式
            # ——保持口径、改正标签（见 test_internship_scope.py「已从风险学生改为开放风险」），
            # 且该待办点开的就是逐条列风险单的处置页，数字与落地页行数必须对得上。
            todos.append({"id": "todo-risk", "label": "开放风险待跟进", "count": risk_cnt,
                          "tone": "warning",
                          "route": f"/admin/internship/risk-disposal?batchId={batch.id}"})

        return {
            **batch_meta,
            "batchStatus": "进行中" if batch.status == "RUNNING" else batch_meta.get("batchStatusLabel") or "—",
            "batchProgress": batch_progress,
            "batchProgressLabel": "批次进度",
            "onboardRate": onboard_rate,
            "stats": [
                {"label": "本批学生", "value": str(total_students), "trend": "", "trendQuality": "neutral",
                 "route": f"/admin/internship/students?batchId={batch.id}"},
                {"label": "在岗学生", "value": str(onboard), "trend": "", "trendQuality": "neutral",
                 "route": f"/admin/internship/students?batchId={batch.id}&panel=status"},
                {"label": "去向待落实", "value": str(dest_none), "trend": "", "trendQuality": "neutral",
                 "route": f"/admin/internship/students?batchId={batch.id}&panel=destination"},
                {"label": "准备中", "value": str(preparing), "trend": "", "trendQuality": "neutral",
                 "route": f"/admin/internship/students?batchId={batch.id}&status=PREPARING"},
                {"label": "待上岗", "value": str(ready), "trend": "", "trendQuality": "neutral",
                 "route": f"/admin/internship/students?batchId={batch.id}&status=READY"},
                {"label": "待处理打卡异常", "value": str(pending_exc),
                 "trend": f"待核实 {pending_exc}", "trendQuality": "bad" if pending_exc else "good",
                 "route": f"/admin/internship/exceptions?batchId={batch.id}"},
                {"label": "待批阅周报", "value": str(pending_rep),
                 "trend": f"待批阅 {pending_rep}", "trendQuality": "bad" if pending_rep else "good",
                 "route": f"/admin/internship/reports?batchId={batch.id}"},
                {"label": "开放风险", "value": str(risk_cnt),
                 "trend": f"跟进中 {risk_cnt}", "trendQuality": "bad" if risk_cnt else "good",
                 "route": f"/admin/internship/risk-disposal?batchId={batch.id}"},
            ],
            "flow": [{"label": lbl, "value": flow_map[k], "active": k == "ONBOARD"}
                     for k, lbl in STATUS_LABEL.items()],
            "todos": todos,
            "workItems": work_items,
            "workItemTotal": pending_rep + pending_exc + risk_cnt,
            "workItemLimit": 8,
            "riskAlerts": risk_alerts,
        }
