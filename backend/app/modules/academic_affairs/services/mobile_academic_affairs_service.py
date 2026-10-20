"""13B-P7 多端收口：教务中心学生自视图 + 教师课表（mobile 前缀）。

学生端本人只读：我的课表(最新已发布批次·按行政班)/我的成绩单/我的学籍+异动/我的毕业进度；
学生唯一写入口=异动申请(本人)。教师端：我的课表。全部经 resolve_student/身份解析，只见本人。
"""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import and_, func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
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


def transcript_my(user, page=None, page_size=20, term=None) -> dict:
    """本人正式成绩单；移动读取必须走分页，打印/兼容读取可显式保留全量文档。"""
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade
    with session() as db:
        stu = _me(db, user)
        sid = stu.id
    if page is None:
        return grade.transcript(sid, user)
    return grade.transcript(sid, user, page=page, page_size=page_size, term=term)


def status_my(user, page=None, page_size=20) -> dict:
    """我的学籍状态 + 我的异动记录。

    ``page is None`` keeps the established student-PC read contract.  The mobile
    route always supplies a bounded page: do the count and ordering in MySQL
    before resolving workflow reviews, rather than loading a student's entire
    history and slicing it in the handset.
    """
    from app.models import AaStatusChange, WorkflowTask
    from app.modules.academic_affairs.services.academic_affairs_service import REGISTRATION_CHANGE_TYPES
    from app.modules.academic_affairs.services.academic_affairs_status_service import is_enrolled
    if page is not None:
        try:
            page = int(page)
            page_size = int(page_size)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "异动记录页码非法") from exc
        if page < 1 or page > 100000 or page_size < 1 or page_size > 50:
            raise AppException("VALIDATION_ERROR", "异动记录分页参数超出范围")
    with session() as db:
        stu = _me(db, user)
        filters = (
            AaStatusChange.tenant_id == _tid(),
            AaStatusChange.student_id == stu.id,
            AaStatusChange.change_type.notin_(REGISTRATION_CHANGE_TYPES),
            AaStatusChange.is_deleted.is_(False),
        )
        query = select(AaStatusChange).where(*filters).order_by(AaStatusChange.id.desc())
        total = None
        if page is None:
            rows = db.scalars(query).all()
        else:
            total = int(db.scalar(select(func.count()).select_from(AaStatusChange).where(*filters)) or 0)
            rows = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
        instance_ids = {int(x.workflow_instance_id) for x in rows if x.workflow_instance_id}
        latest_reviews = {}
        if instance_ids:
            tasks = db.scalars(select(WorkflowTask).where(
                WorkflowTask.tenant_id == _tid(),
                WorkflowTask.instance_id.in_(instance_ids),
                WorkflowTask.acted_at.is_not(None),
                WorkflowTask.is_deleted.is_(False),
            ).order_by(WorkflowTask.id.desc())).all()
            for task in tasks:
                latest_reviews.setdefault(int(task.instance_id), task)

        def _change_row(x):
            review = latest_reviews.get(int(x.workflow_instance_id)) if x.workflow_instance_id else None
            expose_review = x.status in {"RETURNED", "REJECTED"} and review is not None
            return {"changeId": str(x.id), "changeType": x.change_type,
                    "fromStatus": x.from_status, "toStatus": x.to_status,
                    "reason": x.reason or "", "status": x.status,
                    "currentNode": x.current_node or "",
                    "version": int(x.version or 0),
                    "decisionVersion": int(x.decision_version or 0),
                    "reviewNote": (review.action_reason or "") if expose_review else "",
                    "reviewedAt": _iso(review.acted_at) if expose_review else None,
                    "createdAt": _iso(x.created_at),
                    "effectiveDate": _iso(x.effective_date)}
        result = {
            "studentStatus": stu.student_status, "enrolled": is_enrolled(stu.student_status),
            "changes": [_change_row(x) for x in rows],
        }
        if page is not None:
            result.update({
                "total": total,
                "page": page,
                "pageSize": page_size,
                "hasMore": page * page_size < total,
            })
        return result


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


def transfer_options_page_my(
    user,
    *,
    target: str = "major",
    major_id=None,
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """移动端学籍异动候选项分页读取。

    ``transfer_options_my`` 是学生 PC 已发布的全量兼容合同，不能为了小程序分页
    直接改掉它。移动端在这里按本人、租户和目标类型查询：专业/班级都在 MySQL
    完成关键词过滤、计数、排序与分页，绝不把整校组织数据下发到手机再过滤。
    """
    from app.models import College, Major, SchoolClass

    normalized_target = str(target or "").strip().lower()
    if normalized_target not in {"major", "class"}:
        raise AppException("VALIDATION_ERROR", "异动候选类型仅支持专业或班级")
    try:
        page = int(page)
        page_size = int(page_size)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "异动候选分页参数非法") from exc
    if page < 1 or page > 100000 or page_size < 1 or page_size > 50:
        raise AppException("VALIDATION_ERROR", "异动候选分页参数超出范围")

    keyword = str(keyword or "").strip()
    if len(keyword) > 60:
        raise AppException("VALIDATION_ERROR", "搜索关键词不能超过60个字")
    # 用户输入中的 LIKE 通配符必须按普通文字处理，避免一个 "%" 意外扫出整校数据。
    pattern = "%" + keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"

    def _page_result(items, total, *, selected_major_id=""):
        return {
            "target": normalized_target,
            "majorId": str(selected_major_id or ""),
            "currentMajorId": str(stu.major_id or ""),
            "currentClassId": str(stu.class_id or ""),
            "items": items,
            "page": page,
            "pageSize": page_size,
            "total": int(total),
            "hasMore": page * page_size < int(total),
        }

    with session() as db:
        stu = _me(db, user)
        tenant_id = _tid()
        offset = (page - 1) * page_size

        if normalized_target == "major":
            college_join = and_(
                College.id == Major.college_id,
                College.tenant_id == tenant_id,
                College.is_deleted.is_(False),
            )
            filters = [
                Major.tenant_id == tenant_id,
                Major.is_deleted.is_(False),
            ]
            if stu.major_id:
                filters.append(Major.id != int(stu.major_id))
            if keyword:
                filters.append(or_(
                    Major.major_name.like(pattern, escape="\\"),
                    func.coalesce(Major.code, "").like(pattern, escape="\\"),
                    func.coalesce(College.college_name, "").like(pattern, escape="\\"),
                    func.coalesce(College.code, "").like(pattern, escape="\\"),
                ))
            total = int(db.scalar(
                select(func.count()).select_from(Major).outerjoin(College, college_join).where(*filters)
            ) or 0)
            rows = db.execute(
                select(Major.id, Major.major_name, Major.college_id, College.college_name)
                .select_from(Major)
                .outerjoin(College, college_join)
                .where(*filters)
                .order_by(Major.major_name.asc(), Major.id.asc())
                .offset(offset)
                .limit(page_size)
            ).all()
            return _page_result([
                {
                    "majorId": str(row.id),
                    "majorName": row.major_name,
                    "collegeId": str(row.college_id or ""),
                    "collegeName": row.college_name or "",
                }
                for row in rows
            ], total)

        selected_major_id = None
        if major_id not in (None, ""):
            try:
                selected_major_id = int(major_id)
            except (TypeError, ValueError) as exc:
                raise AppException("VALIDATION_ERROR", "目标专业标识非法") from exc
            exists = db.scalar(select(Major.id).where(
                Major.id == selected_major_id,
                Major.tenant_id == tenant_id,
                Major.is_deleted.is_(False),
            ))
            if not exists:
                # 不能仅按主键查后再暴露“属于另一所学校”的事实。
                raise not_found("目标专业不存在")
        elif stu.major_id:
            selected_major_id = int(stu.major_id)

        if not selected_major_id:
            return _page_result([], 0)

        filters = [
            SchoolClass.tenant_id == tenant_id,
            SchoolClass.major_id == selected_major_id,
            SchoolClass.is_deleted.is_(False),
            SchoolClass.class_status == "NORMAL",
            SchoolClass.status == "ACTIVE",
        ]
        if stu.class_id and int(selected_major_id) == int(stu.major_id or 0):
            filters.append(SchoolClass.id != int(stu.class_id))
        if keyword:
            filters.append(or_(
                SchoolClass.class_name.like(pattern, escape="\\"),
                func.coalesce(SchoolClass.class_code, "").like(pattern, escape="\\"),
                func.coalesce(SchoolClass.grade, "").like(pattern, escape="\\"),
            ))
        total = int(db.scalar(select(func.count()).select_from(SchoolClass).where(*filters)) or 0)
        rows = db.execute(
            select(SchoolClass.id, SchoolClass.class_name, SchoolClass.grade, SchoolClass.major_id)
            .where(*filters)
            .order_by(SchoolClass.grade.desc(), SchoolClass.class_name.asc(), SchoolClass.id.asc())
            .offset(offset)
            .limit(page_size)
        ).all()
        return _page_result([
            {
                "classId": str(row.id),
                "className": row.class_name,
                "grade": row.grade or "",
                "majorId": str(row.major_id),
            }
            for row in rows
        ], total, selected_major_id=selected_major_id)


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


def exam_defer_resubmit_my(user, defer_id, body=None) -> dict:
    """本人退回后补材料重提。"""
    from app.modules.academic_affairs.services import academic_affairs_exam_service as exam_svc
    payload = body or {}
    expected_version = payload.get("expectedVersion") if isinstance(payload, dict) else getattr(payload, "expectedVersion", None)
    return exam_svc.defer_resubmit(user, defer_id, expected_version)


def _acad_student(db, stu):
    """全局学生档案(StudentProfile) → 学业过程台账(AcademicStudent)；无台账返回 None。"""
    from app.models import AcademicStudent
    return db.scalars(select(AcademicStudent).where(
        AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == stu.id,
        AcademicStudent.is_deleted.is_(False))).first()


def credits_my(user, page=None, page_size=20) -> dict:
    """我的学分修读；培养方案无法唯一解析时必须返回UNRESOLVED，不伪造应修学分。"""
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade
    with session() as db:
        stu = _me(db, user)
        sid = stu.id
        acad = _acad_student(db, stu)
        obtained = float(acad.obtained_credits) if acad and acad.obtained_credits is not None else None
        gpa = float(acad.gpa) if acad and acad.gpa is not None else None
    # 小程序只取已通过课程的一页，不能先拉取完整成绩单再在服务端内存筛选。
    # ``page is None`` 仅保留给现有 PC 兼容读取；移动路由始终传入有界页码。
    t = (grade.transcript(sid, user) if page is None
         else grade.passed_courses_page(sid, user, page=page, page_size=page_size))
    earned = obtained if obtained is not None else float(t.get("earnedCredits") or 0)
    from app.modules.academic_affairs.services.student_program_resolution_service import credit_requirement_payload
    with session() as db:
        stu = _me(db, user)
        credit = credit_requirement_payload(db, stu, tenant_id=_tid(), earned_credits=earned)
    passed = ([it for it in t.get("items", []) if it.get("passStatus") == "PASSED"]
              if page is None else list(t.get("items") or []))
    return {
        **credit,
        "gpa": gpa if gpa is not None else t.get("gpa"),
        "failCount": t.get("failCount", 0),
        "passedCourses": passed,
        "passedCoursesTotal": int(t.get("total") if page is not None else len(passed)),
        "page": t.get("page") if page is not None else None,
        "pageSize": t.get("pageSize") if page is not None else None,
        "hasMore": bool(t.get("hasMore")) if page is not None else False,
    }


def warning_my(user, page=1, page_size=50) -> dict:
    """我的学业预警（本人，只读）。"""
    from app.modules.academic_affairs.services import academic_affairs_warning_service as warn
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    with session() as db:
        stu = _me(db, user)
        acad = _acad_student(db, stu)
        acad_id = acad.id if acad else None
    if not acad_id:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size, "hasMore": False}
    items, total = warn.list_warnings(user, acad_student_id=acad_id, page=page, page_size=page_size)
    return {"items": items, "total": total, "page": page, "pageSize": page_size,
            "hasMore": page * page_size < total}


def makeup_my(user) -> dict:
    """我的补考重修（本人重修申请 + 免修申请列表）。"""
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as makeup
    retakes, _ = makeup.retake_list(user, student_only=True, page=1, page_size=50)
    exemptions, _ = makeup.exemption_list(user, student_only=True, page=1, page_size=50)
    return {"retakes": retakes, "exemptions": exemptions}


def retake_apply_my(user, body) -> dict:
    """学生本人发起重修报名。优先 gradeId（挂科列表）；无 gradeId 时课程名须落在挂科候选内。"""
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as makeup
    from app.modules.academic_affairs.services import mobile_academic_gaps_service as gaps
    body = body or {}
    if not body.get("gradeId") and not body.get("courseName"):
        raise AppException("VALIDATION_ERROR", "请从挂科课程列表选择后再提交")
    if not body.get("gradeId"):
        opts = gaps.makeup_options_my(user).get("retakeOptions") or []
        names = {(x.get("courseName") or "").strip() for x in opts}
        if (body.get("courseName") or "").strip() not in names:
            raise AppException("VALIDATION_ERROR", "请从挂科课程列表选择，禁止纯手输未挂科课程")
    return makeup.retake_apply(user, _ns(body))


def exemption_apply_my(user, body) -> dict:
    """学生本人发起免修申请。课程须落在未及格/挂科候选列表。"""
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as makeup
    from app.modules.academic_affairs.services import mobile_academic_gaps_service as gaps
    body = body or {}
    if not (body.get("courseName") or "").strip():
        raise AppException("VALIDATION_ERROR", "请从课程列表选择后再提交")
    opts = gaps.makeup_options_my(user).get("exemptionOptions") or []
    names = {(x.get("courseName") or "").strip() for x in opts}
    if (body.get("courseName") or "").strip() not in names:
        raise AppException("VALIDATION_ERROR", "请从未及格课程列表选择，禁止纯手输为主入口")
    return makeup.exemption_apply(user, _ns(body))


def selection_courses_my(user, batch_id=None):
    """我的选课·可选课程（OPEN 批次 + 实时余量）。"""
    from app.modules.academic_affairs.services import academic_affairs_selection_service as sel
    # The canonical reader resolves a student profile, but historical bindings can
    # resolve a profile from a token-shaped user object.  Reject non-student mobile
    # identities here before any batch/course projection is queried.
    _require_student(user)
    return sel.student_courses(user, batch_id)


def selection_batches_page_my(user, page=1, page_size=20):
    """移动端选课批次目录：本人范围内、服务端分页。"""
    from app.modules.academic_affairs.services import academic_affairs_selection_service as sel
    _require_student(user)
    return sel.student_batch_catalog_page(user, page=page, page_size=page_size)


def selection_courses_page_my(user, batch_id, keyword="", page=1, page_size=20):
    """移动端当前批次课程：服务端搜索、分页和正式动作投影。"""
    from app.modules.academic_affairs.services import academic_affairs_selection_service as sel
    _require_student(user)
    return sel.student_courses_page(
        user, batch_id, keyword=keyword, page=page, page_size=page_size,
    )


def selection_preflight_my(user, body) -> dict:
    """本人选课纯读预检；移动端只代理 canonical SelectionPreflight，不复制规则。"""
    from app.modules.academic_affairs.services import academic_affairs_selection_service as sel
    _require_student(user)
    if not (body or {}).get("selectionCourseId"):
        raise AppException("VALIDATION_ERROR", "selectionCourseId 必填")
    return sel.student_preflight(user, _ns(body))


def selection_drop_preflight_my(user, body) -> dict:
    """本人退课纯读核验，复用正式 DROP 门禁，不调用 ENROLL evaluator。"""
    from app.modules.academic_affairs.services import academic_affairs_selection_final_service as selection

    _require_student(user)
    course_id = (body or {}).get("selectionCourseId")
    if isinstance(course_id, bool) or not isinstance(course_id, (int, str)):
        raise AppException("VALIDATION_ERROR", "selectionCourseId 必须是正整数")
    value = str(course_id)
    if not value.isascii() or not value.isdecimal() or int(value) <= 0:
        raise AppException("VALIDATION_ERROR", "selectionCourseId 必须是正整数")
    return selection.student_drop_preflight(user, _ns({"selectionCourseId": value}))


def selection_enroll_my(user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_selection_service as sel
    _require_student(user)
    if not (body or {}).get("selectionCourseId"):
        raise AppException("VALIDATION_ERROR", "selectionCourseId 必填")
    return sel.student_enroll(user, _ns(body))


def selection_drop_my(user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_selection_service as sel
    _require_student(user)
    if not (body or {}).get("selectionCourseId"):
        raise AppException("VALIDATION_ERROR", "selectionCourseId 必填")
    return sel.student_drop(user, _ns(body))


def selection_records_my(user, batch_id=None):
    """我的选课·本人选课记录。"""
    from app.modules.academic_affairs.services import academic_affairs_selection_service as sel
    _require_student(user)
    return sel.my_selections(user, batch_id)


def selection_records_page_my(user, batch_id, page=1, page_size=20, selection_course_id=None):
    """移动端本人选课记录：按批次分页；可精确回读一门课程。"""
    from app.modules.academic_affairs.services import academic_affairs_selection_service as sel
    _require_student(user)
    return sel.student_selection_records_page(
        user, batch_id, page=page, page_size=page_size,
        selection_course_id=selection_course_id,
    )


# ═══════════ 成绩认定/课程替代（学生自助，对标正方 3.16/3.27）═══════════

def recognition_my(user, page=None, page_size=20):
    """我的成绩认定/课程替代申请：移动端用服务端分页，学生 PC 保留旧合同。"""
    from app.modules.academic_affairs.services import academic_affairs_recognition_service as recog
    _require_student(user)
    if page is None:
        return {"items": recog.my(user)}
    items, total = recog.my_page(user, page=page, page_size=page_size)
    return {
        "items": items,
        "total": total,
        "page": int(page),
        "pageSize": int(page_size),
        "hasMore": int(page) * int(page_size) < total,
    }


def recognition_submit_my(user, body) -> dict:
    """学生本人提交成绩认定申请（校外课程→校内计划课程）。"""
    from app.modules.academic_affairs.services import academic_affairs_recognition_service as recog
    _require_student(user)
    b = body or {}
    if not (b.get("sourceCourseName") and b.get("targetCourseName")):
        raise AppException("VALIDATION_ERROR", "原课程与目标课程必填")
    return recog.submit(user, _ns(b))


def grade_recheck_my(user, page=1, page_size=20):
    """我的成绩复查申请记录；页面与分页均由服务端权威返回。"""
    from app.modules.academic_affairs.services import academic_affairs_grade_recheck_service as rc
    items, total = rc.my(user, page=page, page_size=page_size)
    return {
        "items": items,
        "total": total,
        "page": int(page),
        "pageSize": int(page_size),
        "hasMore": int(page) * int(page_size) < total,
    }


def grade_recheck_eligible_my(user, acad_grade_id) -> dict:
    """从成绩单深链精确读取一门本人成绩，不扫描其它成绩分页。"""
    from app.modules.academic_affairs.services import academic_affairs_grade_recheck_service as rc
    return rc.eligible_grade(user, acad_grade_id)


def grade_recheck_submit_my(user, body) -> dict:
    """学生本人对已发布成绩(t_acad_grade)发起复查。"""
    from app.modules.academic_affairs.services import academic_affairs_grade_recheck_service as rc
    return rc.submit(user, body or {})


def workload_my(user, page=1, page_size=20):
    """教师本人工作量申报记录；列表由服务端分页。"""
    from app.modules.academic_affairs.services import academic_affairs_workload_service as wl
    items, total = wl.my(user, page=page, page_size=page_size)
    return {
        "items": items,
        "total": total,
        "page": int(page),
        "pageSize": int(page_size),
        "hasMore": int(page) * int(page_size) < total,
    }


def workload_submit_my(user, body) -> dict:
    """教师本人工作量申报(教学/监考/阅卷/出卷/其他)。"""
    from app.modules.academic_affairs.services import academic_affairs_workload_service as wl
    return wl.submit(user, body or {})


def workload_command_receipt_my(user, command_key: str) -> dict:
    """网络失败后的工作量命令只读核对，不重新执行写命令。"""
    from app.modules.academic_affairs.services import academic_affairs_workload_service as wl
    return wl.command_receipt(user, command_key)


def textbook_my(
    user,
    *,
    distribution_page=None,
    distribution_page_size=20,
    distribution_record_id=None,
    fee_page=None,
    fee_page_size=20,
):
    """学生本人教材领用记录 + 费用汇总。

    小程序传页码时，领用和费用各自在数据库分页；学生 PC 的兼容入口不传页码，
    继续维持既有完整结构，避免本次移动端收口破坏其它正式消费者。
    """
    from app.modules.academic_affairs.services import academic_affairs_textbook_service as tb
    with session() as db:
        sid = _me(db, user).id
    if distribution_page is None and fee_page is None:
        return {"distributions": tb.my_distributions(user, sid), "fees": tb.my_fees(user, sid)}
    from app.modules.academic_affairs.services import academic_affairs_textbook_read_service as textbook_read
    distributions = textbook_read.my_student_distributions(
        user, sid, page=distribution_page or 1, page_size=distribution_page_size,
        record_id=distribution_record_id,
    )
    fees = textbook_read.my_student_fees(
        user, sid, page=fee_page or 1, page_size=fee_page_size,
    )
    return {
        "distributions": distributions["items"],
        "distributionPagination": {
            key: distributions[key] for key in ("total", "page", "pageSize", "hasMore")
        },
        "fees": fees,
    }


def textbook_sign_my(user, record_id):
    """学生本人签收自己的教材发放记录。"""
    from app.modules.academic_affairs.services import academic_affairs_textbook_service as tb
    with session() as db:
        sid = _me(db, user).id
    return tb.sign_receipt_my(user, sid, record_id)


# ═══════════ 等级考务报名（学生自助，对标正方 3.13 考级项目报名）═══════════

def level_exam_my(
    user,
    *,
    open_page=None,
    open_page_size=20,
    registration_page=None,
    registration_page_size=20,
):
    """考级：开放考试和本人报名历史分别在服务端分页。

    ``None`` 保留学生 PC 的旧读取合同；移动路由始终传入明确页码，不能把
    全部开放考试或历史报名记录下发到手机后再裁切。
    """
    from app.modules.academic_affairs.services import academic_affairs_level_exam_service as lv

    _require_student(user)
    if open_page is None and registration_page is None:
        opens, _ = lv.list_exams(user, status="OPEN", page=1, page_size=50)
        return {"openExams": opens, "myRegs": lv.my_regs(user)}

    open_page = 1 if open_page is None else open_page
    registration_page = 1 if registration_page is None else registration_page
    opens, open_total = lv.list_exams(
        user, status="OPEN", page=open_page, page_size=open_page_size,
    )
    statuses = lv.my_registration_statuses(user, [row["examId"] for row in opens])
    opens = [
        {**row, "registrationStatus": statuses.get(str(row["examId"]))}
        for row in opens
    ]
    registrations, registration_total = lv.my_regs(
        user, page=registration_page, page_size=registration_page_size,
    )
    return {
        "openExams": opens,
        "openPagination": {
            "page": int(open_page), "pageSize": int(open_page_size),
            "total": open_total,
            "hasMore": int(open_page) * int(open_page_size) < open_total,
        },
        "myRegs": registrations,
        "registrationPagination": {
            "page": int(registration_page), "pageSize": int(registration_page_size),
            "total": registration_total,
            "hasMore": int(registration_page) * int(registration_page_size) < registration_total,
        },
    }


def level_register_my(user, exam_id) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_level_exam_service as lv
    _require_student(user)
    return lv.student_register(user, exam_id)


def level_cancel_my(user, exam_id) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_level_exam_service as lv
    _require_student(user)
    return lv.student_cancel(user, exam_id)


# ═══════════ 专业分流志愿(学生自助,对标正方转专业/分流) ═══════════

def major_split_my(
    user,
    *,
    open_page=None,
    open_page_size=20,
    volunteer_page=None,
    volunteer_page_size=20,
):
    """分流：移动端的批次、志愿历史各自分页，专业选项按批次另取。"""
    from app.modules.academic_affairs.services import academic_affairs_major_split_service as ms

    _require_student(user)
    # 学生 PC 的独立工作区仍消费其原合同；移动路由一律传入有界页码。
    if open_page is None and volunteer_page is None:
        return {"openBatches": ms.student_open_batches(user), "myVolunteers": ms.my_volunteer(user)}
    open_page = 1 if open_page is None else open_page
    volunteer_page = 1 if volunteer_page is None else volunteer_page
    open_batches, open_total = ms.student_open_batches_page(
        user, page=open_page, page_size=open_page_size,
    )
    volunteers, volunteer_total = ms.my_volunteer_page(
        user, page=volunteer_page, page_size=volunteer_page_size,
    )
    return {
        "openBatches": open_batches,
        "openPagination": {
            "page": int(open_page), "pageSize": int(open_page_size), "total": open_total,
            "hasMore": int(open_page) * int(open_page_size) < open_total,
        },
        "myVolunteers": volunteers,
        "volunteerPagination": {
            "page": int(volunteer_page), "pageSize": int(volunteer_page_size), "total": volunteer_total,
            "hasMore": int(volunteer_page) * int(volunteer_page_size) < volunteer_total,
        },
    }


def major_split_options_my(user, batch_id, *, page=1, page_size=20, keyword=None):
    from app.modules.academic_affairs.services import academic_affairs_major_split_service as ms

    _require_student(user)
    items, total = ms.student_options_page(
        user, batch_id, page=page, page_size=page_size, keyword=keyword,
    )
    return {
        "items": items, "page": int(page), "pageSize": int(page_size), "total": total,
        "hasMore": int(page) * int(page_size) < total,
    }


def major_split_submit_my(user, body) -> dict:
    """学生提交/修改分流志愿。"""
    from app.modules.academic_affairs.services import academic_affairs_major_split_service as ms
    _require_student(user)
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

def teacher_attendance_sessions(user, page=1, page_size=20):
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as att
    if (user or {}).get("userType") == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    if isinstance(page, bool) or isinstance(page_size, bool):
        raise AppException("VALIDATION_ERROR", "考勤场次页码格式不正确")
    try:
        page = int(page)
        page_size = int(page_size)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "考勤场次页码格式不正确") from exc
    if page < 1 or page > 100000 or page_size < 1 or page_size > 50:
        raise AppException("VALIDATION_ERROR", "考勤场次每页最多50条")
    items, total = att.list_sessions(user, page=page, page_size=page_size)
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "hasMore": page * page_size < total,
    }


def teacher_attendance_create(user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as att
    return att.create_session(user, body)


def teacher_attendance_detail(session_id, user, page=1, page_size=30) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as att
    return att.get_session(session_id, user, page=page, page_size=page_size)


def teacher_attendance_mark(session_id, user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as att
    # Mobile only needs the changed student plus full-session summary.  The PC
    # attendance route keeps the compatibility default that returns its full roster.
    return att.mark_attendance(session_id, user, body, include_roster=False)


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
