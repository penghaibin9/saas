"""13B-P5/R1 成绩录入+审核发布更正（平时+期末按比例合成）。

9 态状态机（SM-11，project_rule）：NOT_STARTED/INPUTTING/SUBMITTED/COLLEGE_REVIEW/
ACADEMIC_REVIEW/PUBLISHED/RETURNED/CHANGE_REVIEW(record级)/ARCHIVED。
发布(PUBLISHED)原子四件事：回写 t_acad_grade(source=PUBLISH)+刷新 t_acad_student 台账+
预警扫描+RISK_ALERT。更正(CHANGE_REVIEW)两级审：学院初审→教务处终审，原值 append-only 留痕。
数据范围：COURSE(任课教师，按 teacher_key 归属)/COLLEGE(学院教务员，复用 build_affairs_context)/
TENANT_ALL(教务处/学校管理员)。成绩发布/退回/归档超高危动作，permission key 通配之外
端点内额外校验角色 ∈ {ACADEMIC_ADMIN, SCHOOL_ADMIN}。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.services.db_service import _iso, _tid, session

_REVIEW_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}  # 教务处终审/退回/归档超高危角色白名单
_WF_SUBMIT = "AC_GRADE_REVIEW"
_WF_CHANGE = "AC_GRADE_CHANGE"


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or "").upper(), str(u.get("userId") or "")


def _audit(db, biz_type, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


def _acad_student_id(db, student_id, name=""):
    """全局学生 → 学业过程台账；无则建一行（投影落点）。返回台账对象（供台账刷新复用）。"""
    from app.models import AcademicStudent, StudentProfile
    a = db.scalars(select(AcademicStudent).where(
        AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == int(student_id),
        AcademicStudent.is_deleted.is_(False))).first()
    if a:
        return a
    s = db.get(StudentProfile, int(student_id))
    a = AcademicStudent(tenant_id=_tid(), student_id=int(student_id), student_no=(s.student_no if s else None),
                        name=(s.real_name if s else name), class_id=(str(s.class_id) if s and s.class_id else None))
    db.add(a)
    db.flush()
    return a


# ═══════════ 数据范围（COURSE/COLLEGE/TENANT_ALL） ═══════════

def _user_keys(user) -> set[str]:
    """派生当前用户可能的教师标识键（userId/登录名/姓名），用于 COURSE 归属比对。"""
    uid = str(user.get("userId") or "")
    login = user.get("loginName") or ""
    name = user.get("realName") or ""
    return {k for k in (uid, login, name, uid[2:] if uid.startswith("u_") else "") if k}


def _check_course_scope(task, user):
    """任课教师仅能操作本人 teacher_key 归属的录入任务；TENANT_ALL/COLLEGE 角色不受此收敛（另有各自校验）。"""
    role = (user.get("currentRoleCode") or "").upper()
    if role in _REVIEW_ROLES or role == "COLLEGE_ADMIN":
        return
    if not task.teacher_key:
        return  # 未建立归属（历史数据/未接入教学任务）时不做收敛，已知欠账，见施工记录
    if task.teacher_key not in _user_keys(user):
        raise AppException("NO_DATA_SCOPE", "该录入任务不在您的授课范围内")


def _check_college_scope(db, task, user):
    """学院教务员仅能审核本学院教学班的任务，复用学工中心已验证的 build_affairs_context/COLLEGE 解析。"""
    role = (user.get("currentRoleCode") or "").upper()
    if role in _REVIEW_ROLES:
        return
    from app.core.affairs_security import build_affairs_context
    ctx = build_affairs_context(user, db)
    allowed = ctx.allowed_class_ids(db)
    if allowed is None:
        return
    if task.class_id and task.class_id not in allowed:
        raise AppException("NO_DATA_SCOPE", "该录入任务不在您的学院范围内")


def _require_review_role(user):
    role = (user.get("currentRoleCode") or "").upper()
    if role not in _REVIEW_ROLES and user.get("userType") != "PLATFORM_SUPER_ADMIN":
        raise no_permission("仅教务处可执行该操作")


# ═══════════ 成绩录入任务 ═══════════

def create_grade_task(body, user) -> dict:
    usual = int(getattr(body, "usualRatio", 30) or 30)
    final = int(getattr(body, "finalRatio", 70) or 70)
    if usual + final != 100:
        raise AppException("VALIDATION_ERROR", "平时占比+期末占比必须=100")
    with session() as db:
        from app.models import AaGradeTask, AaTeachingTask
        teaching_task_id = int(body.teachingTaskId) if getattr(body, "teachingTaskId", None) else None
        teacher_key = None
        if teaching_task_id:
            tt = db.get(AaTeachingTask, teaching_task_id)
            if tt:
                teacher_key = tt.teacher_key
        if not teacher_key:
            teacher_key = next(iter(_user_keys(user)), None)
        t = AaGradeTask(tenant_id=_tid(), teaching_task_id=teaching_task_id,
                        term_id=(int(body.termId) if getattr(body, "termId", None) else None),
                        term_code=getattr(body, "termCode", None), course_name=getattr(body, "courseName", None),
                        class_id=(int(body.classId) if getattr(body, "classId", None) else None),
                        teacher_key=teacher_key,
                        credit=getattr(body, "credit", None), usual_ratio=usual, final_ratio=final,
                        pass_line=int(getattr(body, "passLine", 60) or 60), status="NOT_STARTED")
        db.add(t)
        db.flush()
        _audit(db, "AA_GRADE_TASK", t.id, "CREATE", getattr(body, "courseName", "") or "")
        db.commit()
        db.refresh(t)
        return {"gradeTaskId": str(t.id), "courseName": t.course_name or "", "usualRatio": t.usual_ratio,
                "finalRatio": t.final_ratio, "status": t.status}


def _task_row(t) -> dict:
    return {"gradeTaskId": str(t.id), "courseName": t.course_name or "", "termCode": t.term_code or "",
            "classId": str(t.class_id or ""), "teacherKey": t.teacher_key or "",
            "usualRatio": t.usual_ratio, "finalRatio": t.final_ratio, "passLine": t.pass_line,
            "status": t.status, "returnReason": t.return_reason or "", "publishAt": _iso(t.publish_at)}


def list_tasks(user, status=None, page=1, page_size=20):
    """成绩录入任务列表（学院审核/教务发布工作台的队列来源；按状态筛选）。数据范围：
    TENANT_ALL/COLLEGE 角色不收敛列表（学院教务员看不同状态的跨学院任务仍需自行核实每条详情时才会被
    _check_college_scope 拦截，列表本身按状态供选，未做逐条隐藏——已知欠账，见施工记录）。"""
    from app.models import AaGradeTask
    with session() as db:
        conds = [AaGradeTask.tenant_id == _tid(), AaGradeTask.is_deleted.is_(False)]
        if status:
            conds.append(AaGradeTask.status == status)
        rows = db.scalars(select(AaGradeTask).where(*conds).order_by(AaGradeTask.id.desc())).all()
        out = [_task_row(t) for t in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def roster(task_id, user) -> dict:
    """教学班学生名单（供录入圈定）。V1 无选课，按 task.class_id 推导行政班全员。"""
    with session() as db:
        from app.models import AaGradeTask, StudentProfile
        t = db.get(AaGradeTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("成绩录入任务不存在")
        _check_course_scope(t, user)
        if not t.class_id:
            return {"items": [], "note": "任务未关联行政班，无法自动圈定名单"}
        rows = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.class_id == t.class_id,
            StudentProfile.is_deleted.is_(False))).all()
        return {"items": [{"studentId": str(s.id), "studentNo": s.student_no, "realName": s.real_name}
                          for s in rows]}


def list_records(task_id, user) -> dict:
    """成绩录入表当前已录状态（供录入页刷新/批量导入后回显真实落库结果，零推导、直读 t_aa_grade_record）。"""
    with session() as db:
        from app.models import AaGradeRecord, AaGradeTask, StudentProfile
        t = db.get(AaGradeTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("成绩录入任务不存在")
        _check_course_scope(t, user)
        recs = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _tid(), AaGradeRecord.task_id == t.id,
            AaGradeRecord.is_deleted.is_(False))).all()
        stus = {s.id: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_([r.student_id for r in recs] or [-1]))).all()}
        items = []
        for r in recs:
            s = stus.get(r.student_id)
            items.append({"studentId": str(r.student_id), "realName": (s.real_name if s else ""),
                         "studentNo": (s.student_no if s else ""), "usualScore": r.usual_score,
                         "finalScore": r.final_score, "totalScore": r.total_score,
                         "passStatus": r.pass_status, "exceptionFlag": r.exception_flag or "NORMAL"})
        return {"items": items}


def _write_score_row(db, t, sid, usual, final, exception_flag):
    """录入/批量导入共用的落库逻辑：合成总评 + upsert AaGradeRecord。
    不做 audit/commit（由调用方负责，供批量导入整批一次提交）。"""
    from app.models import AaGradeRecord
    exception_flag = (exception_flag or "NORMAL").upper()
    total = None
    if exception_flag == "NORMAL" and usual is not None and final is not None:
        total = round(usual * t.usual_ratio / 100 + final * t.final_ratio / 100)
    elif exception_flag != "NORMAL":
        usual = final = None  # 缺考/缓考/免修与正常分互斥
    rec = db.scalars(select(AaGradeRecord).where(
        AaGradeRecord.tenant_id == _tid(), AaGradeRecord.task_id == t.id,
        AaGradeRecord.student_id == sid, AaGradeRecord.is_deleted.is_(False))).first()
    if not rec:
        rec = AaGradeRecord(tenant_id=_tid(), task_id=t.id, student_id=sid)
        db.add(rec)
    rec.usual_score, rec.final_score, rec.total_score = usual, final, total
    rec.exception_flag = exception_flag
    rec.pass_status = ("PASSED" if (total is not None and total >= t.pass_line) else
                       ("FAILED" if total is not None else None))
    if t.status == "NOT_STARTED":
        t.status = "INPUTTING"
    db.flush()
    return rec


def enter_score(task_id, user, body) -> dict:
    """录入某生平时/期末分，实时合成总评（NOT_STARTED/INPUTTING/RETURNED 可写）。"""
    with session() as db:
        from app.models import AaGradeTask
        t = db.get(AaGradeTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("成绩录入任务不存在")
        _check_course_scope(t, user)
        if t.status not in ("NOT_STARTED", "INPUTTING", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可录入（已提交/已发布，如需修改请走成绩更正）")
        sid = int(body.studentId)
        usual = getattr(body, "usualScore", None)
        final = getattr(body, "finalScore", None)
        exception_flag = (getattr(body, "exceptionFlag", None) or "NORMAL").upper()
        if exception_flag not in ("NORMAL", "ABSENT", "DEFERRED", "EXEMPT"):
            raise AppException("VALIDATION_ERROR", "异常标记非法")
        rec = _write_score_row(db, t, sid, usual, final, exception_flag)
        _audit(db, "AA_GRADE_TASK", t.id, "ENTER", f"student={sid}")
        db.commit()
        return {"recordId": str(rec.id), "studentId": str(sid), "usualScore": rec.usual_score,
                "finalScore": rec.final_score, "totalScore": rec.total_score, "passStatus": rec.pass_status,
                "exceptionFlag": exception_flag}


# ═══════════ 成绩批量导入（学号/平时分/期末分/异常标记；dry-run 逐行零写入 → 确认整批事务） ═══════════

def _resolve_exception_flag(raw):
    """中文/英文异常标记 → 内部枚举 (NORMAL/ABSENT/DEFERRED/EXEMPT)。
    返回 (flag, bad_raw)：合法时 bad_raw=None；非法时 flag=None、bad_raw=原始输入供报错回显。"""
    v = (raw or "").strip()
    if not v:
        return "NORMAL", None
    cn_map = {"正常": "NORMAL", "缺考": "ABSENT", "缓考": "DEFERRED", "免修": "EXEMPT"}
    if v in cn_map:
        return cn_map[v], None
    if v.upper() in ("NORMAL", "ABSENT", "DEFERRED", "EXEMPT"):
        return v.upper(), None
    return None, v


def _parse_score(raw):
    """空值→None；合法 0-100 整数字符串/数字→int；非法格式或越界→False（哨兵，区分「未填」与「格式错」）。"""
    s = raw.strip() if isinstance(raw, str) else raw
    if s in (None, ""):
        return None
    try:
        v = int(float(s))
    except (TypeError, ValueError):
        return False
    if v < 0 or v > 100:
        return False
    return v


def grade_import_dry_run(task_id, user, rows) -> dict:
    """成绩批量导入预校验（学号必填且匹配本校学生、文件内学号不重复、平时/期末分 0-100、异常标记合法）。
    仅任务处于可写状态（NOT_STARTED/INPUTTING/RETURNED）才允许导入，零写入。"""
    with session() as db:
        from app.models import AaGradeTask, StudentProfile
        t = db.get(AaGradeTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("成绩录入任务不存在")
        _check_course_scope(t, user)
        if t.status not in ("NOT_STARTED", "INPUTTING", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可导入（已提交/已发布，如需修改请走成绩更正）")
        profiles = {s.student_no: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))).all()}
        errors, seen, valid = [], set(), 0
        for i, r in enumerate(rows or []):
            row_no = i + 1
            no = (r.get("studentNo") or "").strip()
            if not no:
                errors.append({"rowNo": row_no, "field": "studentNo", "message": "学号必填"})
                continue
            if no not in profiles:
                errors.append({"rowNo": row_no, "field": "studentNo", "message": f"未匹配到学生：{no}"})
                continue
            if no in seen:
                errors.append({"rowNo": row_no, "field": "studentNo", "message": f"文件内学号重复：{no}"})
                continue
            flag, bad_raw = _resolve_exception_flag(r.get("exceptionFlag"))
            if flag is None:
                errors.append({"rowNo": row_no, "field": "exceptionFlag", "message": f"异常标记非法：{bad_raw}"})
                continue
            usual = _parse_score(r.get("usualScore"))
            if usual is False:
                errors.append({"rowNo": row_no, "field": "usualScore", "message": "平时分须为 0-100 整数"})
                continue
            final = _parse_score(r.get("finalScore"))
            if final is False:
                errors.append({"rowNo": row_no, "field": "finalScore", "message": "期末分须为 0-100 整数"})
                continue
            seen.add(no)
            valid += 1
        return {"total": len(rows or []), "validRows": valid, "invalidRows": len(errors), "errors": errors}


def grade_import_confirm(task_id, user, rows) -> dict:
    """确认导入：预校验通过后逐行落库（复用 enter_score 同一合成/落库逻辑 _write_score_row），
    整批一次事务提交 + 单条汇总审计（不逐行审计，避免刷屏）。"""
    pre = grade_import_dry_run(task_id, user, rows)
    if pre["invalidRows"] > 0:
        raise AppException("DATA_CONFLICT", "存在未通过预校验的行，禁止确认导入")
    with session() as db:
        from app.models import AaGradeTask, StudentProfile
        t = db.get(AaGradeTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("成绩录入任务不存在")
        _check_course_scope(t, user)
        if t.status not in ("NOT_STARTED", "INPUTTING", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可导入（已提交/已发布，如需修改请走成绩更正）")
        profiles = {s.student_no: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))).all()}
        created = 0
        for r in rows or []:
            stu = profiles.get((r.get("studentNo") or "").strip())
            if not stu:
                continue  # 已在 dry_run 校验过，理论不会命中；防御式跳过而非整批失败
            flag, _bad = _resolve_exception_flag(r.get("exceptionFlag"))
            usual = _parse_score(r.get("usualScore"))
            final = _parse_score(r.get("finalScore"))
            # 此处 usual/final 已在 dry_run 校验为 None 或合法 0-100 整数（非 False 哨兵）；
            # 直接传递，禁止 `usual or None` 写法——0 分是合法分数，`or` 会把 0 误判成"未填"。
            _write_score_row(db, t, stu.id, usual, final, flag)
            created += 1
        _audit(db, "AA_GRADE_TASK", t.id, "IMPORT", f"imported={created}")
        db.commit()
        return {"created": created, "imported": created}


# 导入模板 5 列（表头文字 → 行字段 key）。正式交付以 Excel/xlsx 为准（CLAUDE.md §6.1）。
IMPORT_HEADERS = ["学号", "姓名", "平时分", "期末分", "异常标记"]
IMPORT_REQUIRED = ["学号"]
IMPORT_HEADER_MAP = {"学号": "studentNo", "姓名": "studentName", "平时分": "usualScore",
                     "期末分": "finalScore", "异常标记": "exceptionFlag"}
IMPORT_SAMPLE = ["2023115001", "赵一凡", "85", "90", ""]
IMPORT_NOTES = ["学号必填，且必须是本校已建档学生（未匹配到学生该行报错）。",
                "平时分/期末分为 0-100 整数，留空表示未录（可稍后在录入表补录）。",
                "异常标记留空默认「正常」；可填「缺考/缓考/免修」，填后当行平时分/期末分将被忽略。",
                "同一学号在同一份文件内不可重复；已存在的成绩记录会被本次导入覆盖，请谨慎核对。",
                "仅任务处于「未开始/录入中/已退回」状态时可导入；已提交/已发布任务需走「成绩更正」流程。",
                "仅导入「导入模板」页。"]


def _row_values_for_error(r: dict) -> list:
    return [r.get(IMPORT_HEADER_MAP[h], "") for h in IMPORT_HEADERS]


def submit_task(task_id, user) -> dict:
    """提交进入学院审核：全员有值或有互斥标记才可提交。"""
    with session() as db:
        from app.models import AaGradeRecord, AaGradeTask, StudentProfile
        t = db.get(AaGradeTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("成绩录入任务不存在")
        _check_course_scope(t, user)
        if t.status not in ("INPUTTING", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可提交")
        roster_count = 0
        if t.class_id:
            roster_count = db.scalar(select(func.count()).select_from(StudentProfile).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.class_id == t.class_id,
                StudentProfile.is_deleted.is_(False))) or 0
        recs = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _tid(), AaGradeRecord.task_id == t.id,
            AaGradeRecord.is_deleted.is_(False))).all()
        incomplete = [r for r in recs if r.total_score is None and (r.exception_flag or "NORMAL") == "NORMAL"]
        if roster_count and len(recs) < roster_count:
            raise AppException("DATA_CONFLICT", f"名单 {roster_count} 人，仅录入 {len(recs)} 人，未录全不可提交")
        if incomplete:
            raise AppException("DATA_CONFLICT", f"仍有 {len(incomplete)} 名学生成绩未录全，不可提交")
        n, r, uid = _op()
        first_node = "COLLEGE_REVIEW"
        from app.models import WorkflowInstance, WorkflowTask
        inst = WorkflowInstance(tenant_id=_tid(), workflow_code=_WF_SUBMIT, source_module="academic-affairs",
                                source_biz_type="AA_GRADE_TASK", source_biz_id=t.id,
                                applicant_id=int(uid) if uid.isdigit() else 0,
                                title=f"{t.course_name or ''} 成绩审核", status="RUNNING", current_node=first_node)
        db.add(inst)
        db.flush()
        db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=first_node, assignee_id=0,
                            status="PENDING"))
        t.workflow_instance_id = inst.id
        t.submitted_at = datetime.utcnow()
        t.status = "SUBMITTED"
        _audit(db, "AA_GRADE_TASK", t.id, "SUBMIT")
        db.commit()
        db.refresh(t)
        return {"gradeTaskId": str(t.id), "status": t.status}


def college_review(task_id, user, action, reason="") -> dict:
    """学院审核：通过→ACADEMIC_REVIEW；退回→RETURNED（原因≥5字）。"""
    action = (action or "").upper()
    with session() as db:
        from app.models import AaGradeTask, WorkflowInstance, WorkflowTask
        t = db.get(AaGradeTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("成绩录入任务不存在")
        _check_college_scope(db, t, user)
        if t.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "当前状态不可学院审核")
        n, r, uid = _op()
        inst = db.get(WorkflowInstance, int(t.workflow_instance_id)) if t.workflow_instance_id else None
        wtask = db.scalars(select(WorkflowTask).where(
            WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == (inst.id if inst else 0),
            WorkflowTask.node_code == "COLLEGE_REVIEW", WorkflowTask.status == "PENDING",
            WorkflowTask.is_deleted.is_(False))).first() if inst else None
        if action == "RETURN":
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "退回原因必填且不少于5字")
            if wtask:
                wtask.status, wtask.action_reason, wtask.acted_at = "TRANSFERRED", reason.strip(), datetime.utcnow()
            if inst:
                inst.status = "RETURNED"
            t.status, t.return_reason = "RETURNED", reason.strip()
            _audit(db, "AA_GRADE_TASK", t.id, "COLLEGE_RETURN", reason.strip())
        elif action == "APPROVE":
            if wtask:
                wtask.status, wtask.acted_at = "APPROVED", datetime.utcnow()
            next_node = "ACADEMIC_REVIEW"
            if inst:
                inst.current_node = next_node
                db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=next_node,
                                    assignee_id=0, status="PENDING"))
            t.college_reviewed_at = datetime.utcnow()
            t.college_reviewer_id = int(uid) if uid.isdigit() else None
            t.status = "ACADEMIC_REVIEW"
            _audit(db, "AA_GRADE_TASK", t.id, "COLLEGE_APPROVE")
        else:
            raise AppException("VALIDATION_ERROR", "无效操作")
        db.commit()
        db.refresh(t)
        return {"gradeTaskId": str(t.id), "status": t.status}


def publish_grades(task_id, user) -> dict:
    """教务处终审发布：合成总评原子回写 t_acad_grade + 刷新学生台账 + 预警扫描 + 不及格生成 RISK_ALERT。"""
    _require_review_role(user)
    with session() as db:
        from app.models import AaGradeRecord, AaGradeTask, AcademicGrade, AffairsRiskRecord, StudentProfile
        t = db.get(AaGradeTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("成绩录入任务不存在")
        if t.status == "PUBLISHED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "成绩已发布")
        if t.status != "ACADEMIC_REVIEW":
            raise AppException("DATA_CONFLICT", "仅学院审核通过（教务终审中）的任务可发布")
        recs = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _tid(), AaGradeRecord.task_id == t.id,
            AaGradeRecord.is_deleted.is_(False))).all()
        incomplete = [r for r in recs if r.total_score is None and (r.exception_flag or "NORMAL") == "NORMAL"]
        if not recs or incomplete:
            raise AppException("DATA_CONFLICT", f"仍有 {len(incomplete)} 名学生成绩未录全，不可发布")
        projected, fail_count = 0, 0
        for r in recs:
            s = db.get(StudentProfile, int(r.student_id))
            a = _acad_student_id(db, r.student_id, s.real_name if s else "")
            g = AcademicGrade(tenant_id=_tid(), acad_student_id=a.id, course_name=t.course_name or "",
                              term=t.term_code, nature="REQUIRED", credit_value=(t.credit or 0),
                              score=r.total_score, pass_status=(r.pass_status or "PENDING"), exam_type="FINAL",
                              record_status="ACTIVE", source="PUBLISH")
            db.add(g)
            db.flush()
            r.acad_grade_id = g.id
            r.source = "PUBLISH"
            projected += 1
            all_g = db.scalars(select(AcademicGrade).where(
                AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == a.id,
                AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False))).all()
            scored = [x for x in all_g if x.score is not None]
            a.avg_score = round(sum(x.score for x in scored) / len(scored)) if scored else 0
            a.failed_count = sum(1 for x in all_g if x.pass_status == "FAILED")
            a.obtained_credits = sum(float(x.credit_value or 0) for x in all_g if x.pass_status == "PASSED")
            a.gpa = round(sum((x.score or 0) / 100 * 4 for x in scored) / len(scored), 2) if scored else 0
            if r.pass_status == "FAILED":
                fail_count += 1
                dup = db.scalars(select(AffairsRiskRecord).where(
                    AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.source == "ACADEMIC_WARNING",
                    AffairsRiskRecord.source_ref_id == r.id)).first()
                if not dup:
                    db.add(AffairsRiskRecord(tenant_id=_tid(), student_id=r.student_id, source="ACADEMIC_WARNING",
                                             source_ref_id=r.id, risk_level="MEDIUM",
                                             title=f"{t.course_name or ''} 课程不及格",
                                             detail=f"总评 {r.total_score}，及格线 {t.pass_line}", status="NEW"))
        t.status, t.publish_at = "PUBLISHED", datetime.utcnow()
        t.academic_reviewed_at = datetime.utcnow()
        n, r2, uid = _op()
        t.academic_reviewer_id = int(uid) if uid.isdigit() else None
        _audit(db, "AA_GRADE_TASK", t.id, "PUBLISH", f"projected={projected},fail={fail_count}")
        db.commit()
    try:
        from app.modules.academic_affairs.services.academic_affairs_warning_service import scan_warnings
        scan_warnings(user)
    except Exception:
        pass  # 预警扫描失败不阻塞发布主流程
    return {"gradeTaskId": str(task_id), "status": "PUBLISHED", "projected": projected, "failCount": fail_count}


def return_task(task_id, user, reason="") -> dict:
    """教务处退回（教务终审阶段）。"""
    _require_review_role(user)
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于5字")
    with session() as db:
        from app.models import AaGradeTask
        t = db.get(AaGradeTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("成绩录入任务不存在")
        if t.status != "ACADEMIC_REVIEW":
            raise AppException("DATA_CONFLICT", "当前状态不可退回")
        t.status, t.return_reason = "RETURNED", reason.strip()
        _audit(db, "AA_GRADE_TASK", t.id, "ACADEMIC_RETURN", reason.strip())
        db.commit()
        db.refresh(t)
        return {"gradeTaskId": str(t.id), "status": t.status}


def archive_task(task_id, user) -> dict:
    """学期归档：仅 PUBLISHED 可归档。"""
    _require_review_role(user)
    with session() as db:
        from app.models import AaGradeTask
        t = db.get(AaGradeTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("成绩录入任务不存在")
        if t.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅已发布任务可归档")
        t.status = "ARCHIVED"
        _audit(db, "AA_GRADE_TASK", t.id, "ARCHIVE")
        db.commit()
        db.refresh(t)
        return {"gradeTaskId": str(t.id), "status": t.status}


# ═══════════ 成绩更正（record 级，两级审：学院初审→教务处终审） ═══════════

def change_request(task_id, record_id, user, body) -> dict:
    """教师发起成绩更正：仅 PUBLISHED 任务下的记录可发起；ARCHIVED 拒绝。"""
    with session() as db:
        from app.models import AaGradeRecord, AaGradeTask, WorkflowInstance, WorkflowTask
        t = db.get(AaGradeTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("成绩录入任务不存在")
        _check_course_scope(t, user)
        rec = db.get(AaGradeRecord, int(record_id))
        if not rec or rec.is_deleted or rec.tenant_id != _tid() or rec.task_id != t.id:
            raise not_found("成绩明细不存在")
        if t.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档学期，成绩更正需线下特批（本轮暂未开放线上入口）")
        if t.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅已发布成绩可申请更正")
        reason = (getattr(body, "reason", "") or "").strip()
        if len(reason) < 5:
            raise AppException("VALIDATION_ERROR", "更正原因必填且不少于5字")
        existing = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.tenant_id == _tid(), WorkflowInstance.source_module == "academic-affairs",
            WorkflowInstance.source_biz_type == "AA_GRADE_CHANGE", WorkflowInstance.source_biz_id == rec.id,
            WorkflowInstance.status == "RUNNING", WorkflowInstance.is_deleted.is_(False))).first()
        if existing:
            raise AppException("DATA_CONFLICT", "该成绩已有在途更正申请，不可重复发起")
        n, r, uid = _op()
        rec.prev_usual_score, rec.prev_final_score, rec.prev_total_score = (
            rec.usual_score, rec.final_score, rec.total_score)
        new_usual = getattr(body, "newUsualScore", None)
        new_final = getattr(body, "newFinalScore", None)
        if new_usual is not None:
            rec.usual_score = new_usual
        if new_final is not None:
            rec.final_score = new_final
        rec.change_reason = reason
        first_node = "COLLEGE_REVIEW"
        inst = WorkflowInstance(tenant_id=_tid(), workflow_code=_WF_CHANGE, source_module="academic-affairs",
                                source_biz_type="AA_GRADE_CHANGE", source_biz_id=rec.id,
                                applicant_id=int(uid) if uid.isdigit() else 0,
                                title=f"{t.course_name or ''} 成绩更正", status="RUNNING", current_node=first_node)
        db.add(inst)
        db.flush()
        db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=first_node, assignee_id=0,
                            status="PENDING"))
        _audit(db, "AA_GRADE_RECORD", rec.id, "CHANGE_APPLY", reason)
        db.commit()
        return {"recordId": str(rec.id), "workflowInstanceId": str(inst.id), "status": "CHANGE_REVIEW"}


def _change_review(record_id, user, action, reason, node, next_node_or_final):
    action = (action or "").upper()
    with session() as db:
        from app.models import AaGradeRecord, WorkflowInstance, WorkflowTask
        rec = db.get(AaGradeRecord, int(record_id))
        if not rec or rec.is_deleted or rec.tenant_id != _tid():
            raise not_found("成绩明细不存在")
        inst = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.tenant_id == _tid(), WorkflowInstance.source_module == "academic-affairs",
            WorkflowInstance.source_biz_type == "AA_GRADE_CHANGE", WorkflowInstance.source_biz_id == rec.id,
            WorkflowInstance.status == "RUNNING", WorkflowInstance.is_deleted.is_(False))).first()
        if not inst or inst.current_node != node:
            raise AppException("APPROVAL_VERSION_CONFLICT", "当前更正申请不在此审核节点")
        wtask = db.scalars(select(WorkflowTask).where(
            WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == inst.id,
            WorkflowTask.node_code == node, WorkflowTask.status == "PENDING",
            WorkflowTask.is_deleted.is_(False))).first()
        if action == "REJECT":
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于5字")
            if wtask:
                wtask.status, wtask.action_reason, wtask.acted_at = "REJECTED", reason.strip(), datetime.utcnow()
            inst.status = "REJECTED"
            if rec.prev_usual_score is not None or rec.prev_final_score is not None:
                rec.usual_score, rec.final_score, rec.total_score = (
                    rec.prev_usual_score, rec.prev_final_score, rec.prev_total_score)
            rec.prev_usual_score = rec.prev_final_score = rec.prev_total_score = None
            _audit(db, "AA_GRADE_RECORD", rec.id, "CHANGE_REJECT", reason.strip())
            db.commit()
            return {"recordId": str(rec.id), "status": "PUBLISHED"}
        if action != "APPROVE":
            raise AppException("VALIDATION_ERROR", "无效操作")
        if wtask:
            wtask.status, wtask.acted_at = "APPROVED", datetime.utcnow()
        if next_node_or_final == "FINAL":
            inst.status = "APPROVED"
            _audit(db, "AA_GRADE_RECORD", rec.id, "CHANGE_APPROVE")
            db.commit()
            return {"recordId": str(rec.id), "status": "PUBLISHED", "final": True}
        inst.current_node = next_node_or_final
        db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=next_node_or_final,
                            assignee_id=0, status="PENDING"))
        _audit(db, "AA_GRADE_RECORD", rec.id, "CHANGE_STEP", f"->{next_node_or_final}")
        db.commit()
        return {"recordId": str(rec.id), "status": "CHANGE_REVIEW"}


def change_college_review(record_id, user, action, reason="") -> dict:
    """更正学院初审：通过→教务处终审节点；驳回→原值不变、更正流程终止。"""
    with session() as db:
        from app.models import AaGradeRecord, AaGradeTask
        rec = db.get(AaGradeRecord, int(record_id))
        if rec and not rec.is_deleted and rec.tenant_id == _tid():
            t = db.get(AaGradeTask, int(rec.task_id))
            if t:
                _check_college_scope(db, t, user)
    return _change_review(record_id, user, action, reason, "COLLEGE_REVIEW", "ACADEMIC_REVIEW")


def change_academic_review(record_id, user, action, reason="") -> dict:
    """更正教务处终审：通过则重算 pass_status、投影回写 t_acad_grade(source=CHANGE)、
    联动预警、学生收通知；驳回原值不变（已在 _change_review 回滚）。"""
    action = (action or "").upper()
    _require_review_role(user)
    if action == "APPROVE":
        with session() as db:
            from app.models import AaGradeRecord, AaGradeTask, AcademicGrade, UnifiedMessage
            rec = db.get(AaGradeRecord, int(record_id))
            if not rec or rec.is_deleted or rec.tenant_id != _tid():
                raise not_found("成绩明细不存在")
            t = db.get(AaGradeTask, int(rec.task_id)) if rec.task_id else None
            new_total = None
            if rec.usual_score is not None and rec.final_score is not None and t:
                new_total = round(rec.usual_score * t.usual_ratio / 100 + rec.final_score * t.final_ratio / 100)
            rec.total_score = new_total
            rec.pass_status = "PASSED" if (new_total is not None and t and new_total >= t.pass_line) else "FAILED"
            rec.source = "CHANGE"
            n, r, uid = _op()
            rec.change_by = int(uid) if uid.isdigit() else None
            rec.change_at = datetime.utcnow()
            rec.version_no = (rec.version_no or 1) + 1
            if rec.acad_grade_id:
                g = db.get(AcademicGrade, int(rec.acad_grade_id))
                if g:
                    g.score, g.pass_status, g.source = new_total, rec.pass_status, "CHANGE"
            db.add(UnifiedMessage(tenant_id=_tid(), receiver_id=int(rec.student_id), source_module="academic-affairs",
                                  source_biz_id=rec.id, title="成绩已更正",
                                  content=f"{t.course_name if t else ''} 成绩已更正为 {new_total}",
                                  message_type="WORKFLOW_RESULT", status="UNREAD"))
            db.commit()
    result = _change_review(record_id, user, action, reason, "ACADEMIC_REVIEW", "FINAL")
    if action == "APPROVE":
        try:
            from app.modules.academic_affairs.services.academic_affairs_warning_service import scan_warnings
            scan_warnings(user)
        except Exception:
            pass
    return result


# ═══════════ 成绩读侧视图（零写入） ═══════════

def transcript(student_id, user) -> dict:
    """学生成绩单（读 t_acad_grade，仅已投影记录，即 PUBLISHED 及以后）。"""
    from app.models import AcademicGrade, AcademicStudent
    with session() as db:
        a = db.scalars(select(AcademicStudent).where(
            AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == int(student_id),
            AcademicStudent.is_deleted.is_(False))).first()
        if not a:
            return {"items": [], "totalCredits": 0, "gpa": None, "note": "无学业记录"}
        rows = db.scalars(select(AcademicGrade).where(
            AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == a.id,
            AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False))
            .order_by(AcademicGrade.term)).all()
        items = [{"courseName": g.course_name, "term": g.term or "", "credit": float(g.credit_value or 0),
                  "score": g.score, "passStatus": g.pass_status, "source": g.source or "LEGACY"} for g in rows]
        earned = sum(float(g.credit_value or 0) for g in rows if g.pass_status == "PASSED")
        return {"items": items, "earnedCredits": earned, "gpa": float(a.gpa or 0),
                "failCount": sum(1 for g in rows if g.pass_status in ("FAIL", "FAILED"))}


def export_transcript_xlsx(user, student_id, purpose="") -> bytes:
    """导出学生成绩单 .xlsx（首行水印 + 用途必填 + 审计，V1 同步下载，与既有「未注册学生导出」
    export_unregistered_xlsx 同一模式，未新建异步 t_export_task 通道，如实登记为简化差异）。"""
    purpose = (purpose or "").strip()
    if len(purpose) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    from app.services.xlsx_util import build_ledger_xlsx
    data = transcript(student_id, user)
    with session() as db:
        from app.models import StudentProfile
        stu = db.get(StudentProfile, int(student_id))
        stu_label = f"{stu.real_name}（学号 {stu.student_no}）" if stu else f"学生ID {student_id}"
    n, r, uid = _op()
    watermark = (f"{stu_label} 成绩单  导出人：{n or '-'}  "
                 f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose}")
    headers = ["课程名称", "学期", "学分", "成绩", "结果", "来源"]
    result_label = {"PASSED": "及格", "FAILED": "不及格", "FAIL": "不及格", "PENDING": "待定"}
    rows = [[it["courseName"], it["term"] or "", it["credit"], (it["score"] if it["score"] is not None else ""),
             result_label.get(it["passStatus"], it["passStatus"] or "—"), it["source"] or "LEGACY"]
            for it in data["items"]]
    content = build_ledger_xlsx("学生成绩单", headers, rows, watermark=watermark)
    with session() as db:
        _audit(db, "AA_GRADE_TRANSCRIPT", int(student_id), "EXPORT", f"用途={purpose[:100]}")
        db.commit()
    return content


def fail_list(user, term=None, page=1, page_size=50):
    """挂科清单（下钻，读侧）。与 t_acad_student 一次性 JOIN 取数 + DB 级分页，
    避免逐行 db.get(AcademicStudent) 的 N+1 与全量加载后内存切片。"""
    from app.models import AcademicGrade, AcademicStudent
    with session() as db:
        join = and_(AcademicStudent.id == AcademicGrade.acad_student_id,
                    AcademicStudent.tenant_id == AcademicGrade.tenant_id)
        conds = [AcademicGrade.tenant_id == _tid(), AcademicGrade.pass_status.in_(("FAIL", "FAILED")),
                 AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False)]
        if term:
            conds.append(AcademicGrade.term == term)
        total = db.scalar(select(func.count()).select_from(AcademicGrade)
                          .outerjoin(AcademicStudent, join).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.execute(select(AcademicGrade, AcademicStudent)
                          .outerjoin(AcademicStudent, join).where(*conds)
                          .order_by(AcademicGrade.id.desc()).offset(offset).limit(page_size)).all()
        out = [{"studentName": a.name if a else "", "studentId": str(a.student_id or "") if a else "",
                "courseName": g.course_name, "term": g.term or "", "score": g.score} for g, a in rows]
        return out, total


def grade_analysis(user, term=None):
    """成绩分析：分数段分布 + 及格率（读侧聚合）。"""
    from app.models import AcademicGrade
    with session() as db:
        conds = [AcademicGrade.tenant_id == _tid(), AcademicGrade.score.is_not(None),
                 AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False)]
        if term:
            conds.append(AcademicGrade.term == term)
        rows = db.scalars(select(AcademicGrade).where(*conds)).all()
        buckets = {"90-100": 0, "80-89": 0, "70-79": 0, "60-69": 0, "0-59": 0}
        passed = 0
        for g in rows:
            sc = g.score or 0
            if sc >= 90:
                buckets["90-100"] += 1
            elif sc >= 80:
                buckets["80-89"] += 1
            elif sc >= 70:
                buckets["70-79"] += 1
            elif sc >= 60:
                buckets["60-69"] += 1
            else:
                buckets["0-59"] += 1
            if g.pass_status == "PASSED":
                passed += 1
        total = len(rows)
        return {"total": total, "passRate": round(passed / total, 3) if total else 0.0,
                "distribution": [{"range": k, "count": v} for k, v in buckets.items()]}
