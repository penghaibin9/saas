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
    from app.modules.academic_affairs.services.academic_affairs_service import REGISTRATION_CHANGE_TYPES
    from app.modules.academic_affairs.services.academic_affairs_status_service import is_enrolled
    with session() as db:
        stu = _me(db, user)
        rows = db.scalars(select(AaStatusChange).where(
            AaStatusChange.tenant_id == _tid(), AaStatusChange.student_id == stu.id,
            AaStatusChange.change_type.notin_(REGISTRATION_CHANGE_TYPES),
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

    def _g(key):
        return getattr(body, key, None) or (body.get(key) if isinstance(body, dict) else None)

    change_type = str(_g("changeType") or "").strip()
    reason = str(_g("reason") or "").strip()
    if not change_type:
        raise AppException("VALIDATION_ERROR", "异动类型（changeType）必填")
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "异动事由至少 5 个字")
    if change_type == "TRANSFER_MAJOR" and not _g("toMajorId"):
        raise AppException("VALIDATION_ERROR", "转专业需指定目标专业")
    if change_type == "TRANSFER_CLASS" and not _g("toClassId"):
        raise AppException("VALIDATION_ERROR", "转班需指定目标班级")

    class _B:
        studentId = str(sid)
        changeType = change_type
        reason = reason
        toMajorId = _g("toMajorId")
        toClassId = _g("toClassId")
        toCollegeId = _g("toCollegeId")
    return change.submit(_B(), user)


def transfer_options_my(user) -> dict:
    """学生异动可选目标：可转专业清单 + 同专业可转班清单 + 各目标专业下可选班（本人当前专业/班级自动排除）。"""
    from app.models import College, Major, SchoolClass
    with session() as db:
        stu = _me(db, user)
        majors = db.scalars(select(Major).where(
            Major.tenant_id == _tid(), Major.is_deleted.is_(False)).order_by(Major.id)).all()
        colleges = {c.id: c for c in db.scalars(select(College).where(
            College.tenant_id == _tid(), College.is_deleted.is_(False))).all()}
        major_items = []
        target_major_ids = []
        for m in majors:
            if stu.major_id and int(m.id) == int(stu.major_id):
                continue
            col = colleges.get(m.college_id)
            major_items.append({
                "majorId": str(m.id), "majorName": m.major_name,
                "collegeId": str(m.college_id or ""), "collegeName": col.college_name if col else "",
            })
            target_major_ids.append(int(m.id))
        class_items = []
        if stu.major_id:
            classes = db.scalars(select(SchoolClass).where(
                SchoolClass.tenant_id == _tid(), SchoolClass.major_id == int(stu.major_id),
                SchoolClass.is_deleted.is_(False), SchoolClass.class_status == "NORMAL",
                SchoolClass.status == "ACTIVE").order_by(SchoolClass.id)).all()
            for c in classes:
                if stu.class_id and int(c.id) == int(stu.class_id):
                    continue
                class_items.append({
                    "classId": str(c.id), "className": c.class_name, "grade": c.grade or "",
                    "majorId": str(c.major_id),
                })
        # 转专业可选目标班：按目标专业分组（可不选班，由教务编班）
        major_classes = {str(mid): [] for mid in target_major_ids}
        if target_major_ids:
            t_classes = db.scalars(select(SchoolClass).where(
                SchoolClass.tenant_id == _tid(), SchoolClass.major_id.in_(target_major_ids),
                SchoolClass.is_deleted.is_(False), SchoolClass.class_status == "NORMAL",
                SchoolClass.status == "ACTIVE").order_by(SchoolClass.id)).all()
            for c in t_classes:
                major_classes.setdefault(str(c.major_id), []).append({
                    "classId": str(c.id), "className": c.class_name, "grade": c.grade or "",
                    "majorId": str(c.major_id),
                })
        return {
            "currentMajorId": str(stu.major_id or ""),
            "currentClassId": str(stu.class_id or ""),
            "majors": major_items,
            "classes": class_items,
            "majorClasses": major_classes,
        }


def transcript_print_my(user, body=None) -> dict:
    """成绩单打印留痕（移动端；与门户同一审计口径）。"""
    from app.student_portal.services import common_service as common
    body = body or {}
    doc = transcript_my(user)
    log = common.print_log(user, {
        "bizType": "TRANSCRIPT",
        "bizId": str(body.get("bizId") or "self"),
        "docName": "成绩单",
        "reason": str(body.get("reason") or "个人成绩单"),
    })
    return {**log, "docName": "成绩单", "printReason": body.get("reason") or "个人成绩单", "document": doc}


def schedule_print_my(user, body=None) -> dict:
    """课表打印留痕（移动端；与门户同一审计口径）。"""
    from app.student_portal.services import common_service as common
    body = body or {}
    doc = schedule_my(user)
    log = common.print_log(user, {
        "bizType": "SCHEDULE",
        "bizId": str(body.get("bizId") or "self"),
        "docName": "个人课表",
        "reason": str(body.get("reason") or "个人课表"),
    })
    return {**log, "docName": "个人课表", "printReason": body.get("reason") or "个人课表", "document": doc}


def teacher_attendance_class_options(user) -> dict:
    """考勤可选行政班：辅导员/班主任班 + 本人教学任务绑定班（去重）。"""
    from app.models import AaTeachingTask, SchoolClass
    if (user or {}).get("userType") == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    keys = {_teacher_key(user)}
    uid = str((user or {}).get("userId") or "")
    login = (user or {}).get("loginName") or ""
    name = (user or {}).get("realName") or ""
    keys |= {k for k in (uid, login, name, uid[2:] if uid.startswith("u_") else "") if k}
    with session() as db:
        by_id = {}
        # 教学任务班
        tasks = db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
            AaTeachingTask.teacher_key.in_(list(keys) or ["__none__"]),
            AaTeachingTask.class_id.is_not(None))).all()
        for t in tasks:
            c = db.get(SchoolClass, int(t.class_id))
            if c and not c.is_deleted and c.tenant_id == _tid():
                by_id[c.id] = {"classId": str(c.id), "className": c.class_name,
                               "grade": c.grade or "", "source": "TEACHING_TASK"}
        # 辅导员/班主任班
        from app.services.mobile_teacher_service import my_classes as _mc
        mine = _mc(user) or {}
        for it in (mine.get("items") or []):
            cid = int(it.get("classId") or 0)
            if cid and cid not in by_id:
                by_id[cid] = {"classId": str(cid), "className": it.get("className") or "",
                              "grade": it.get("grade") or "", "source": "MY_CLASS"}
        items = sorted(by_id.values(), key=lambda x: x["classId"])
        return {"items": items, "hasData": bool(items)}


def graduation_progress_my(user) -> dict:
    """我的毕业进度（最新预审结果，供数维度以 precheck `_run_items` 为准，现 11 项）。"""
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
    """我的考试安排（已发布课程中本人座位/准考证；无数据时返回空列表而非永久占位）。"""
    from app.modules.academic_affairs.services import academic_affairs_exam_service as exam_svc
    with session() as db:
        stu = _me(db, user)
        sid = stu.id
    return exam_svc.my_exam_schedule(user, sid)


# ═══════════ 缓考申请（考务管理二级模块·SM-10 8态四级审批，学生自助，本人只读+申请） ═══════════
# 直接复用 academic_affairs_exam_service 的缓考函数（唯一实现，不重开一套业务逻辑）；
# get_current_user_ctx() 在 get_current_user 依赖解析时已按 JWT 落好 studentNo，PC/移动端共用同一份 service。

def exam_defer_options_my(user) -> dict:
    """本人已排考且未开考的课程（供缓考申请选择，不展示完整考试安排/座位——那属于 03/08 号卡范围）。"""
    from app.modules.academic_affairs.services import academic_affairs_exam_service as exam_svc
    with session() as db:
        stu = _me(db, user)
        sid = stu.id
    return {"items": exam_svc.my_deferrable_courses(user, sid)}


def exam_defer_my(user, status=None) -> dict:
    """本人的缓考申请列表。"""
    from app.modules.academic_affairs.services import academic_affairs_exam_service as exam_svc
    items, total = exam_svc.defer_list(user, status, student_only=True)
    return {"items": items, "total": total}


def exam_defer_apply_my(user, body) -> dict:
    """本人发起缓考申请（唯一学生写入口之一）。"""
    from app.modules.academic_affairs.services import academic_affairs_exam_service as exam_svc
    return exam_svc.defer_apply(user, _ns(body))


def exam_defer_resubmit_my(user, defer_id) -> dict:
    """本人退回后补材料重提。"""
    from app.modules.academic_affairs.services import academic_affairs_exam_service as exam_svc
    return exam_svc.defer_resubmit(user, defer_id)


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


def exemption_apply_my(user, body) -> dict:
    """学生本人发起免修申请。此前学生门户"免修申请"页误接了重修接口（examTab 未参与实际
    分支，两个入口提交的全是 AaRetakeApply 记录），修复为真正调用免修服务。"""
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as makeup
    if not (body or {}).get("courseName"):
        raise AppException("VALIDATION_ERROR", "课程名必填")
    return makeup.exemption_apply(user, _ns(body))


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


def workload_my(user):
    """教师本人工作量申报记录。"""
    from app.modules.academic_affairs.services import academic_affairs_workload_service as wl
    return {"items": wl.my(user)}


def workload_submit_my(user, body) -> dict:
    """教师本人工作量申报(教学/监考/阅卷/出卷/其他)。"""
    from app.modules.academic_affairs.services import academic_affairs_workload_service as wl
    return wl.submit(user, body or {})


def textbook_my(user):
    """学生本人教材领用记录 + 费用汇总（正方学生端6.13/6.14 对标）。"""
    from app.modules.academic_affairs.services import academic_affairs_textbook_service as tb
    with session() as db:
        sid = _me(db, user).id
    return {"distributions": tb.my_distributions(user, sid), "fees": tb.my_fees(user, sid)}


def textbook_sign_my(user, record_id):
    """学生本人签收自己的教材发放记录。"""
    from app.modules.academic_affairs.services import academic_affairs_textbook_service as tb
    with session() as db:
        sid = _me(db, user).id
    return tb.sign_receipt_my(user, sid, record_id)


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
    """名单 + 已录分数回显（合并 roster 与 records，供移动端重进不丢分）。"""
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade
    base = grade.roster(task_id, user)
    rec = grade.list_records(task_id, user)
    by = {str(r.get("studentId")): r for r in (rec.get("items") or [])}
    items = []
    for s in (base.get("items") or []):
        row = dict(s)
        r = by.get(str(s.get("studentId")))
        if r:
            row["usualScore"] = r.get("usualScore")
            row["midtermScore"] = r.get("midtermScore")
            row["finalScore"] = r.get("finalScore")
            row["totalScore"] = r.get("totalScore")
            row["exceptionFlag"] = r.get("exceptionFlag") or "NORMAL"
        items.append(row)
    return {
        "items": items,
        "usualRatio": rec.get("usualRatio"),
        "midtermRatio": rec.get("midtermRatio"),
        "finalRatio": rec.get("finalRatio"),
        "status": rec.get("status") or base.get("status"),
    }


def teacher_grade_records(task_id, user) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade
    return grade.list_records(task_id, user)


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


# ═══════════ 学生评教（匿名提交，复用 PC evaluation_service）═══════════

def evaluation_tasks_my(user) -> dict:
    """开放窗口内、与本人行政班匹配的学生评教任务（匿名槽位，不回传他人身份）。"""
    from app.models import AaEvaluationBatch, AaEvaluationTask
    with session() as db:
        stu = _me(db, user)
        class_id = getattr(stu, "class_id", None)
        if not class_id:
            return {"list": [], "total": 0, "note": "学籍未绑定行政班"}
        open_batches = db.scalars(select(AaEvaluationBatch).where(
            AaEvaluationBatch.tenant_id == _tid(),
            AaEvaluationBatch.status == "OPEN",
            AaEvaluationBatch.is_deleted.is_(False),
        )).all()
        if not open_batches:
            return {"list": [], "total": 0}
        batch_ids = [b.id for b in open_batches]
        batch_name = {b.id: (b.batch_name or "") for b in open_batches}
        rows = db.scalars(select(AaEvaluationTask).where(
            AaEvaluationTask.tenant_id == _tid(),
            AaEvaluationTask.batch_id.in_(batch_ids),
            AaEvaluationTask.evaluator_type == "STUDENT",
            AaEvaluationTask.class_id == int(class_id),
            AaEvaluationTask.is_deleted.is_(False),
        ).order_by(AaEvaluationTask.id)).all()
        items = [{
            "taskId": str(t.id),
            "batchId": str(t.batch_id),
            "batchName": batch_name.get(t.batch_id, ""),
            "courseName": t.course_name or "",
            "teacherName": t.teacher_name or "",
            "submittedCount": int(t.submitted_count or 0),
            "anonymous": True,
        } for t in rows]
        return {"list": items, "total": len(items)}


def evaluation_submit_my(user, body) -> dict:
    """学生匿名提交评教。窗口/任务类型校验在 evaluation_service.submit_evaluation。"""
    from app.models import AaEvaluationTask
    from app.modules.academic_affairs.services import academic_affairs_evaluation_service as eval_svc
    task_id = (body or {}).get("taskId")
    if not task_id or not str(task_id).isdigit():
        raise AppException("VALIDATION_ERROR", "taskId 必填")
    score = (body or {}).get("objectiveScore")
    if score is None:
        raise AppException("VALIDATION_ERROR", "objectiveScore 必填")
    try:
        score_f = float(score)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "objectiveScore 须为数字") from exc
    if score_f < 0 or score_f > 100:
        raise AppException("VALIDATION_ERROR", "objectiveScore 须在 0-100")
    # 确认学生身份+本班任务，再交给域服务（匿名不落学生身份）
    with session() as db:
        stu = _me(db, user)
        class_id = getattr(stu, "class_id", None)
        if not class_id:
            raise AppException("VALIDATION_ERROR", "学籍未绑定行政班，无法评教")
        t = db.get(AaEvaluationTask, int(task_id))
        if (not t or t.is_deleted or t.tenant_id != _tid()
                or t.evaluator_type != "STUDENT"
                or int(t.class_id or 0) != int(class_id)):
            raise AppException("NO_PERMISSION", "仅可评本班开放中的评教任务")
    return eval_svc.submit_evaluation(
        user, int(task_id),
        (body or {}).get("answers") or {},
        score_f,
        (body or {}).get("comment"),
    )
