"""13B-P7 多端收口：教务中心学生自视图 + 教师课表（mobile 前缀）。

学生端本人只读：我的课表(最新已发布批次·按行政班)/我的成绩单/我的学籍+异动/我的毕业进度；
学生唯一写入口=异动申请(本人)。教师端：我的课表。全部经 resolve_student/身份解析，只见本人。
"""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission
from app.services.db_service import _iso, _tid, session
from app.services.mobile_student_service import _require_student, resolve_student


def _me(db, user):
    stu = resolve_student(db, _require_student(user))
    if not stu:
        raise no_permission("尚未建立你的学生档案")
    return stu


def _ns(body):
    """移动端路由传入原始 dict；本模块复用的 PC 域服务函数按对象属性取值（body.xxx），此处做薄转换。"""
    return SimpleNamespace(**(body or {}))


def _teacher_key(user) -> str:
    u = user or {}
    uid = str(u.get("userId") or "")
    ctx = str(u.get("activeContextId") or "")
    if uid.startswith("u_"):
        return uid[2:]
    if ctx.startswith("ctx_"):
        return ctx[4:]
    return uid or (u.get("realName") or "")


def _latest_published_batch(db):
    from app.models import AaScheduleBatch
    return db.scalars(select(AaScheduleBatch).where(
        AaScheduleBatch.tenant_id == _tid(), AaScheduleBatch.status == "PUBLISHED",
        AaScheduleBatch.is_deleted.is_(False)).order_by(AaScheduleBatch.id.desc())).first()


# ═══════════ 学生自视图 ═══════════

def schedule_my(user) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_schedule_service as sched
    with session() as db:
        stu = _me(db, user)
        b = _latest_published_batch(db)
        sid = stu.id
    if not b:
        return {"batchId": "", "items": [], "note": "暂无已发布课表"}
    data = sched.student_view(b.id, user, sid)
    return {"batchId": str(b.id), **data}


def transcript_my(user) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade
    with session() as db:
        stu = _me(db, user)
        sid = stu.id
    return grade.transcript(sid, user)


def status_my(user) -> dict:
    """我的学籍状态 + 我的异动记录。"""
    from app.models import AaStatusChange
    from app.modules.academic_affairs.services.academic_affairs_status_service import is_enrolled
    with session() as db:
        stu = _me(db, user)
        rows = db.scalars(select(AaStatusChange).where(
            AaStatusChange.tenant_id == _tid(), AaStatusChange.student_id == stu.id,
            AaStatusChange.change_type.notin_(["ENROLL_REGISTER", "ANNUAL_REGISTER"]),
            AaStatusChange.is_deleted.is_(False)).order_by(AaStatusChange.id.desc())).all()
        return {
            "studentStatus": stu.student_status, "enrolled": is_enrolled(stu.student_status),
            "changes": [{"changeId": str(x.id), "changeType": x.change_type, "toStatus": x.to_status,
                         "status": x.status, "effectiveDate": _iso(x.effective_date)} for x in rows],
        }


def submit_status_change_my(user, body) -> dict:
    """学生本人发起异动申请（唯一学生写入口，只能给自己）。"""
    from app.modules.academic_affairs.services import academic_affairs_change_service as change
    with session() as db:
        stu = _me(db, user)
        sid = stu.id

    class _B:
        studentId = str(sid)
        changeType = getattr(body, "changeType", None) or (body.get("changeType") if isinstance(body, dict) else None)
        reason = getattr(body, "reason", None) or (body.get("reason") if isinstance(body, dict) else None)
        toMajorId = getattr(body, "toMajorId", None) or (body.get("toMajorId") if isinstance(body, dict) else None)
        toClassId = getattr(body, "toClassId", None) or (body.get("toClassId") if isinstance(body, dict) else None)
        toCollegeId = getattr(body, "toCollegeId", None) or (body.get("toCollegeId") if isinstance(body, dict) else None)
    return change.submit(_B(), user)


def graduation_progress_my(user) -> dict:
    """我的毕业进度（最新预审结果七项）。"""
    import json

    from app.models import AaGraduationAuditResult
    with session() as db:
        stu = _me(db, user)
        r = db.scalars(select(AaGraduationAuditResult).where(
            AaGraduationAuditResult.tenant_id == _tid(), AaGraduationAuditResult.student_id == stu.id,
            AaGraduationAuditResult.is_deleted.is_(False)).order_by(
            AaGraduationAuditResult.id.desc())).first()
        if not r:
            return {"hasAudit": False, "note": "尚未纳入毕业预审"}
        return {"hasAudit": True, "overall": r.overall, "conclusion": r.conclusion,
                "status": r.status,
                "items": json.loads(r.item_results_json) if r.item_results_json else []}


def exam_my(user) -> dict:
    """我的考试（V1 占位空态，考务未上线）。"""
    with session() as db:
        _me(db, user)
    return {"hasData": False, "note": "考试安排功能即将上线"}


def _acad_student(db, stu):
    """全局学生档案(StudentProfile) → 学业过程台账(AcademicStudent)；无台账返回 None。"""
    from app.models import AcademicStudent
    return db.scalars(select(AcademicStudent).where(
        AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == stu.id,
        AcademicStudent.is_deleted.is_(False))).first()


def credits_my(user) -> dict:
    """我的学分修读（真实汇总：已获/应修学分+均分+已通过课程清单；无分类占比，数据模型不支持类别拆分）。"""
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade
    with session() as db:
        stu = _me(db, user)
        sid = stu.id
        acad = _acad_student(db, stu)
        obtained = float(acad.obtained_credits) if acad else None
        required = float(acad.required_credits) if acad else 120.0
        gpa = float(acad.gpa or 0) if acad else None
    t = grade.transcript(sid, user)
    passed = [it for it in t.get("items", []) if it.get("passStatus") == "PASSED"]
    return {
        "obtainedCredits": obtained if obtained is not None else t.get("earnedCredits", 0),
        "requiredCredits": required,
        "gpa": gpa if gpa is not None else t.get("gpa"),
        "failCount": t.get("failCount", 0),
        "passedCourses": passed,
    }


def warning_my(user) -> dict:
    """我的学业预警（本人，只读）。"""
    from app.modules.academic_affairs.services import academic_affairs_warning_service as warn
    with session() as db:
        stu = _me(db, user)
        acad = _acad_student(db, stu)
        acad_id = acad.id if acad else None
    if not acad_id:
        return {"items": [], "total": 0}
    items, total = warn.list_warnings(user, acad_student_id=acad_id, page=1, page_size=50)
    return {"items": items, "total": total}


def makeup_my(user) -> dict:
    """我的补考重修（本人重修申请 + 免修申请列表）。"""
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as makeup
    retakes, _ = makeup.retake_list(user, student_only=True, page=1, page_size=50)
    exemptions, _ = makeup.exemption_list(user, student_only=True, page=1, page_size=50)
    return {"retakes": retakes, "exemptions": exemptions}


def retake_apply_my(user, body) -> dict:
    """学生本人发起重修报名。"""
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as makeup
    if not (body or {}).get("courseName"):
        raise AppException("VALIDATION_ERROR", "课程名必填")
    return makeup.retake_apply(user, _ns(body))


def selection_courses_my(user, batch_id=None):
    """我的选课·可选课程（OPEN 批次 + 实时余量）。"""
    from app.modules.academic_affairs.services import academic_affairs_selection_service as sel
    return sel.student_courses(user, batch_id)


def selection_enroll_my(user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_selection_service as sel
    if not (body or {}).get("selectionCourseId"):
        raise AppException("VALIDATION_ERROR", "selectionCourseId 必填")
    return sel.student_enroll(user, _ns(body))


def selection_drop_my(user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_selection_service as sel
    if not (body or {}).get("selectionCourseId"):
        raise AppException("VALIDATION_ERROR", "selectionCourseId 必填")
    return sel.student_drop(user, _ns(body))


def selection_records_my(user, batch_id=None):
    """我的选课·本人选课记录。"""
    from app.modules.academic_affairs.services import academic_affairs_selection_service as sel
    return sel.my_selections(user, batch_id)


# ═══════════ 成绩认定/课程替代（学生自助，对标正方 3.16/3.27）═══════════

def recognition_my(user):
    """我的成绩认定/课程替代申请记录。"""
    from app.modules.academic_affairs.services import academic_affairs_recognition_service as recog
    return {"items": recog.my(user)}


def recognition_submit_my(user, body) -> dict:
    """学生本人提交成绩认定申请（校外课程→校内计划课程）。"""
    from app.modules.academic_affairs.services import academic_affairs_recognition_service as recog
    b = body or {}
    if not (b.get("sourceCourseName") and b.get("targetCourseName")):
        raise AppException("VALIDATION_ERROR", "原课程与目标课程必填")
    return recog.submit(user, _ns(b))


def grade_recheck_my(user):
    """我的成绩复查申请记录。"""
    from app.modules.academic_affairs.services import academic_affairs_grade_recheck_service as rc
    return {"items": rc.my(user)}


def grade_recheck_submit_my(user, body) -> dict:
    """学生本人对已发布成绩(t_acad_grade)发起复查。"""
    from app.modules.academic_affairs.services import academic_affairs_grade_recheck_service as rc
    return rc.submit(user, body or {})


# ═══════════ 等级考务报名（学生自助，对标正方 3.13 考级项目报名）═══════════

def level_exam_my(user):
    """考级:可报名的开放考试 + 我的报名记录。"""
    from app.modules.academic_affairs.services import academic_affairs_level_exam_service as lv
    opens, _ = lv.list_exams(user, status="OPEN", page=1, page_size=50)
    return {"openExams": opens, "myRegs": lv.my_regs(user)}


def level_register_my(user, exam_id) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_level_exam_service as lv
    return lv.student_register(user, exam_id)


def level_cancel_my(user, exam_id) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_level_exam_service as lv
    return lv.student_cancel(user, exam_id)


# ═══════════ 专业分流志愿(学生自助,对标正方转专业/分流) ═══════════

def major_split_my(user):
    """分流:开放中的分流批次(含可选专业) + 我的志愿与录取结果。"""
    from app.modules.academic_affairs.services import academic_affairs_major_split_service as ms
    return {"openBatches": ms.student_open_batches(user), "myVolunteers": ms.my_volunteer(user)}


def major_split_submit_my(user, body) -> dict:
    """学生提交/修改分流志愿。"""
    from app.modules.academic_affairs.services import academic_affairs_major_split_service as ms
    b = body or {}
    batch_id = b.get("batchId")
    choices = b.get("choices") or []
    if not batch_id or not choices:
        raise AppException("VALIDATION_ERROR", "批次与志愿必填")
    return ms.submit_volunteer(user, batch_id, choices)


# ═══════════ 教师端·成绩录入（移动端简版：仅本人授课任务） ═══════════

def teacher_grade_tasks(user, status=None):
    """教师·我的成绩录入任务（按 teacher_key 归属过滤，教务处/学校管理员见全部）。"""
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade
    if (user or {}).get("userType") == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    role = (user.get("currentRoleCode") or "").upper()
    rows, total = grade.list_tasks(user, status=status, page=1, page_size=100)
    if role not in grade._REVIEW_ROLES and role != "COLLEGE_ADMIN":
        keys = grade._user_keys(user)
        rows = [r for r in rows if r.get("teacherKey") and r["teacherKey"] in keys]
    return {"items": rows, "total": len(rows)}


def teacher_grade_roster(task_id, user) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade
    return grade.roster(task_id, user)


def teacher_grade_enter_score(task_id, user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade
    if not (body or {}).get("studentId"):
        raise AppException("VALIDATION_ERROR", "studentId 必填")
    return grade.enter_score(task_id, user, _ns(body))


def teacher_grade_submit_task(task_id, user) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade
    return grade.submit_task(task_id, user)


# ═══════════ 教师端·课堂考勤（移动端首创） ═══════════

def teacher_attendance_sessions(user):
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as att
    if (user or {}).get("userType") == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    items, total = att.list_sessions(user, page=1, page_size=50)
    return {"items": items, "total": total}


def teacher_attendance_create(user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as att
    return att.create_session(user, body)


def teacher_attendance_detail(session_id, user) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as att
    return att.get_session(session_id, user)


def teacher_attendance_mark(session_id, user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as att
    return att.mark_attendance(session_id, user, body)


def teacher_attendance_submit(session_id, user) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as att
    return att.submit_session(session_id, user)


# ═══════════ 教师端 ═══════════

def teacher_schedule_my(user) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_schedule_service as sched
    if (user or {}).get("userType") == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    with session() as db:
        b = _latest_published_batch(db)
    if not b:
        return {"batchId": "", "items": [], "note": "暂无已发布课表"}
    data = sched.teacher_view(b.id, user, _teacher_key(user))
    return {"batchId": str(b.id), **data}
