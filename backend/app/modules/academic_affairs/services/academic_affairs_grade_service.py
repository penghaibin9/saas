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


def effective_grade_rows(rows):
    """按 (acad_student_id, course_name) 取分数最高的一行作为该生该课程的「有效成绩」。

    同一门课可能存在多条历史 t_acad_grade 行（正常考试 PUBLISH / 补考 MAKEUP / 清考 CLEARANCE /
    成绩更正 CHANGE），补考通过后应以补考行覆盖原挂科结论，而不是让毕业资格审核、学业预警等
    只读扫描直接把原始 FAILED 行也算作一门未通过——那会导致已补考合格的学生被系统持续误判为
    「未达标」。凡是按学生汇总挂科/统计课程通过情况，一律先经本函数去重，不要直接扫原始行。
    """
    best: dict = {}
    for g in rows:
        key = (g.acad_student_id, g.course_name)
        cur = best.get(key)
        if cur is None or (g.score if g.score is not None else -1) > (cur.score if cur.score is not None else -1):
            best[key] = g
    return list(best.values())


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


def _compose_total(t, usual, mid, final):
    """按任务平时/期中/期末占比合成总评。期中占比=0 时退化为「平时+期末」，与旧任务结果完全一致。"""
    return round((usual or 0) * (t.usual_ratio or 0) / 100
                 + (mid or 0) * (getattr(t, "midterm_ratio", 0) or 0) / 100
                 + (final or 0) * (t.final_ratio or 0) / 100)


def _scores_complete(t, usual, mid, final):
    """占比>0 的分项都已录入才算录全（可合成总评）；占比=0 的分项不要求录入。"""
    if (t.usual_ratio or 0) > 0 and usual is None:
        return False
    if (getattr(t, "midterm_ratio", 0) or 0) > 0 and mid is None:
        return False
    if (t.final_ratio or 0) > 0 and final is None:
        return False
    return True


# ═══════════ 成绩录入任务 ═══════════

def create_grade_task(body, user) -> dict:
    usual = int(getattr(body, "usualRatio", 30) or 30)
    final = int(getattr(body, "finalRatio", 70) or 70)
    midterm = int(getattr(body, "midtermRatio", 0) or 0)
    if usual + midterm + final != 100:
        raise AppException("VALIDATION_ERROR", "平时+期中+期末占比之和必须=100")
    with session() as db:
        from app.models import AaGradeTask, AaTeachingTask
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        guard_term_writable(db, getattr(body, "termId", None))  # 归档11卡§6.2：已归档学期不应新建成绩任务
        teaching_task_id = int(body.teachingTaskId) if getattr(body, "teachingTaskId", None) else None
        teacher_key = None
        if teaching_task_id:
            # 租户隔离收口：教学任务必须属本租户，否则拒绝——此前 db.get 不校验 tenant_id，
            # 传他租户 teachingTaskId 会把他租户 teacher_key 带进本租户新成绩任务。
            tt = db.get(AaTeachingTask, teaching_task_id)
            if not tt or tt.is_deleted or tt.tenant_id != _tid():
                raise not_found("教学任务不存在或不在当前数据范围内")
            teacher_key = tt.teacher_key
        if not teacher_key:
            teacher_key = next(iter(_user_keys(user)), None)
        t = AaGradeTask(tenant_id=_tid(), teaching_task_id=teaching_task_id,
                        term_id=(int(body.termId) if getattr(body, "termId", None) else None),
                        term_code=getattr(body, "termCode", None), course_name=getattr(body, "courseName", None),
                        class_id=(int(body.classId) if getattr(body, "classId", None) else None),
                        teacher_key=teacher_key,
                        credit=getattr(body, "credit", None), usual_ratio=usual, midterm_ratio=midterm,
                        final_ratio=final,
                        pass_line=int(getattr(body, "passLine", 60) or 60), status="NOT_STARTED")
        db.add(t)
        db.flush()
        _audit(db, "AA_GRADE_TASK", t.id, "CREATE", getattr(body, "courseName", "") or "")
        db.commit()
        db.refresh(t)
        return {"gradeTaskId": str(t.id), "courseName": t.course_name or "", "usualRatio": t.usual_ratio,
                "midtermRatio": t.midterm_ratio, "finalRatio": t.final_ratio, "status": t.status}


def _task_row(t) -> dict:
    return {"gradeTaskId": str(t.id), "courseName": t.course_name or "", "termCode": t.term_code or "",
            "classId": str(t.class_id or ""), "teacherKey": t.teacher_key or "",
            "usualRatio": t.usual_ratio, "midtermRatio": t.midterm_ratio, "finalRatio": t.final_ratio,
            "passLine": t.pass_line,
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
    """成绩录入表当前已录状态（供录入页刷新/批量导入后回显真实落库结果，零推导、直读 t_aa_grade_record）。
    同时供「成绩复核」只读工作台复用（07 号三级卡补建）：额外返回 recordId/source/更正前值/更正原因/
    更正时间/版本号，供学院教务员、教务处管理员（不受 COURSE 范围收敛）以及任课教师本人（COURSE 范围）
    在通过/发布前，或事后核对更正留痕时逐行核对。不新增端点，纯字段扩展，向后兼容既有调用方
    （成绩录入页刷新/导入回显）。"""
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
            items.append({"recordId": str(r.id), "studentId": str(r.student_id),
                         "realName": (s.real_name if s else ""), "studentNo": (s.student_no if s else ""),
                         "usualScore": r.usual_score, "finalScore": r.final_score, "totalScore": r.total_score,
                         "passStatus": r.pass_status, "exceptionFlag": r.exception_flag or "NORMAL",
                         "source": r.source or "LEGACY", "prevUsualScore": r.prev_usual_score,
                         "prevFinalScore": r.prev_final_score, "prevTotalScore": r.prev_total_score,
                         "changeReason": r.change_reason or "", "changeAt": _iso(r.change_at),
                         "versionNo": r.version_no})
        return {"items": items}


def _write_score_row(db, t, sid, usual, final, exception_flag, mid=None):
    """录入/批量导入共用的落库逻辑：合成总评 + upsert AaGradeRecord。
    不做 audit/commit（由调用方负责，供批量导入整批一次提交）。
    与 enter_score 同款：按 平时/期中/期末 占比合成；占比>0 的分项未录全 → total=None，
    发布门禁会拦为「未录全」，绝不产出缺权重的错误总评（批量导入模板无期中列时 mid 恒 None）。"""
    from app.models import AaGradeRecord
    exception_flag = (exception_flag or "NORMAL").upper()
    total = None
    if exception_flag == "NORMAL":
        if _scores_complete(t, usual, mid, final):
            total = _compose_total(t, usual, mid, final)
    else:
        usual = mid = final = None  # 缺考/缓考/免修与正常分互斥
    rec = db.scalars(select(AaGradeRecord).where(
        AaGradeRecord.tenant_id == _tid(), AaGradeRecord.task_id == t.id,
        AaGradeRecord.student_id == sid, AaGradeRecord.is_deleted.is_(False))).first()
    if not rec:
        rec = AaGradeRecord(tenant_id=_tid(), task_id=t.id, student_id=sid)
        db.add(rec)
    rec.usual_score, rec.midterm_score, rec.final_score, rec.total_score = usual, mid, final, total
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
        from app.models import AaGradeRecord, AaGradeTask
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        t = db.get(AaGradeTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("成绩录入任务不存在")
        guard_term_writable(db, t.term_id)  # 归档11卡§6.2：已归档学期的成绩不应再录入
        _check_course_scope(t, user)
        if t.status not in ("NOT_STARTED", "INPUTTING", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可录入（已提交/已发布，如需修改请走成绩更正）")
        sid = int(body.studentId)
        usual = getattr(body, "usualScore", None)
        mid = getattr(body, "midtermScore", None)
        final = getattr(body, "finalScore", None)
        exception_flag = (getattr(body, "exceptionFlag", None) or "NORMAL").upper()
        if exception_flag not in ("NORMAL", "ABSENT", "DEFERRED", "EXEMPT"):
            raise AppException("VALIDATION_ERROR", "异常标记非法")
        total = None
        if exception_flag == "NORMAL":
            if _scores_complete(t, usual, mid, final):
                total = _compose_total(t, usual, mid, final)
        else:
            usual = mid = final = None  # 缺考/缓考/免修与正常分互斥
        rec = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _tid(), AaGradeRecord.task_id == t.id,
            AaGradeRecord.student_id == sid, AaGradeRecord.is_deleted.is_(False))).first()
        if not rec:
            rec = AaGradeRecord(tenant_id=_tid(), task_id=t.id, student_id=sid)
            db.add(rec)
        rec.usual_score, rec.midterm_score, rec.final_score, rec.total_score = usual, mid, final, total
        rec.exception_flag = exception_flag
        rec.pass_status = ("PASSED" if (total is not None and total >= t.pass_line) else
                           ("FAILED" if total is not None else None))
        if t.status == "NOT_STARTED":
            t.status = "INPUTTING"
        db.flush()
        _audit(db, "AA_GRADE_TASK", t.id, "ENTER", f"student={sid}")
        db.commit()
        return {"recordId": str(rec.id), "studentId": str(sid), "usualScore": usual,
                "midtermScore": mid, "finalScore": final, "totalScore": total,
                "passStatus": rec.pass_status, "exceptionFlag": exception_flag}


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
        from app.services.runtime_preset_install_service import ensure_workflow_enabled
        ensure_workflow_enabled(db, _tid(), _WF_SUBMIT)
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


def _course_point(score) -> float:
    """百分制课程绩点：≥60 → (成绩-50)/10（60→1.0，100→5.0），<60 → 0。
    高校百分制绩点的通行映射（designSource=project_rule；各校如有自定义档位，后续参数化）。"""
    s = float(score or 0)
    return round((s - 50) / 10, 2) if s >= 60 else 0.0


def _refresh_aggregates(db, a) -> None:
    """刷新学生学业台账四项汇总（均分/未通过门数/已得学分/绩点）。

    口径（对齐商业教务系统的学分绩点计算）：
    - 同课程多条记录（重修/补考回写）按"取最高分"去重，只计一条——
      否则重修学生的学分会算两遍、挂科记录洗不掉；
    - failed_count = "最优记录仍不及格"的课程数（即至今未通过的课程数，供学业预警）；
    - GPA = Σ(课程绩点×学分) / Σ学分（学分加权）；全部课程零学分时退化为绩点简单平均。
    """
    from app.models import AcademicGrade
    all_g = db.scalars(select(AcademicGrade).where(
        AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == a.id,
        AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False))).all()
    best = {}
    for x in all_g:
        key = (x.course_name or "").strip() or f"__id_{x.id}"
        cur = best.get(key)
        if cur is None or (x.score or -1) > (cur.score or -1) or \
                ((x.score or -1) == (cur.score or -1) and x.id > cur.id):
            best[key] = x
    rows = list(best.values())
    scored = [x for x in rows if x.score is not None]
    a.avg_score = round(sum(x.score for x in scored) / len(scored)) if scored else 0
    a.failed_count = sum(1 for x in rows if x.pass_status in ("FAIL", "FAILED"))
    a.obtained_credits = sum(float(x.credit_value or 0) for x in rows if x.pass_status == "PASSED")
    if scored:
        total_credit = sum(float(x.credit_value or 0) for x in scored)
        if total_credit > 0:
            a.gpa = round(sum(_course_point(x.score) * float(x.credit_value or 0)
                              for x in scored) / total_credit, 2)
        else:
            a.gpa = round(sum(_course_point(x.score) for x in scored) / len(scored), 2)
    else:
        a.gpa = 0


def publish_grades(task_id, user) -> dict:
    """教务处终审发布：合成总评原子回写 t_acad_grade + 刷新学生台账 + 预警扫描 + 不及格生成 RISK_ALERT。"""
    _require_review_role(user)
    with session() as db:
        from app.models import AaGradeRecord, AaGradeTask, AcademicGrade, AffairsRiskRecord, StudentProfile
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        t = db.get(AaGradeTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("成绩录入任务不存在")
        guard_term_writable(db, t.term_id)  # 归档11卡§6.2：已归档学期的成绩不应再发布
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
        # 条件更新抢占发布权：仅一个并发请求能把状态从 ACADEMIC_REVIEW 转为 PUBLISHED，
        # 防止双击/网络重试并发触发两次下方插入循环，在正式成绩单里产生重复行
        claim = db.query(AaGradeTask).filter(
            AaGradeTask.id == t.id, AaGradeTask.tenant_id == _tid(),
            AaGradeTask.status == "ACADEMIC_REVIEW").update(
            {AaGradeTask.status: "PUBLISHED"}, synchronize_session=False)
        if not claim:
            db.rollback()
            raise AppException("APPROVAL_VERSION_CONFLICT", "成绩已发布")
        t.status = "PUBLISHED"
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
            _refresh_aggregates(db, a)
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
        t.publish_at = datetime.utcnow()
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
        rec.prev_usual_score, rec.prev_midterm_score, rec.prev_final_score, rec.prev_total_score = (
            rec.usual_score, rec.midterm_score, rec.final_score, rec.total_score)
        new_usual = getattr(body, "newUsualScore", None)
        new_mid = getattr(body, "newMidtermScore", None)
        new_final = getattr(body, "newFinalScore", None)
        if new_usual is not None:
            rec.usual_score = new_usual
        if new_mid is not None:
            rec.midterm_score = new_mid
        if new_final is not None:
            rec.final_score = new_final
        rec.change_reason = reason
        first_node = "COLLEGE_REVIEW"
        from app.services.runtime_preset_install_service import ensure_workflow_enabled
        ensure_workflow_enabled(db, _tid(), _WF_CHANGE)
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
            if (rec.prev_usual_score is not None or rec.prev_midterm_score is not None
                    or rec.prev_final_score is not None):
                rec.usual_score, rec.midterm_score, rec.final_score, rec.total_score = (
                    rec.prev_usual_score, rec.prev_midterm_score, rec.prev_final_score, rec.prev_total_score)
            rec.prev_usual_score = rec.prev_midterm_score = rec.prev_final_score = rec.prev_total_score = None
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
            from app.models import (AaGradeRecord, AaGradeTask, AcademicGrade,
                                     AcademicStudent, UnifiedMessage)
            rec = db.get(AaGradeRecord, int(record_id))
            if not rec or rec.is_deleted or rec.tenant_id != _tid():
                raise not_found("成绩明细不存在")
            t = db.get(AaGradeTask, int(rec.task_id)) if rec.task_id else None
            new_total = None
            if t and _scores_complete(t, rec.usual_score, rec.midterm_score, rec.final_score):
                new_total = _compose_total(t, rec.usual_score, rec.midterm_score, rec.final_score)
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
                    a = db.get(AcademicStudent, int(g.acad_student_id)) if g.acad_student_id else None
                    if a:
                        _refresh_aggregates(db, a)  # 更正终审后即时重算 GPA/学分/挂科聚合（与 publish/复查一致）
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


# ═══════════ 成绩操作审计（08 号三级卡补建，读侧，t_affairs_audit_trail biz_type=AA_GRADE_*） ═══════════

def list_grade_audit(user, biz_type=None, page=1, page_size=50):
    """成绩操作审计：读 t_affairs_audit_trail，biz_type ∈ {AA_GRADE_TASK, AA_GRADE_RECORD,
    AA_GRADE_TRANSCRIPT}（覆盖创建/录入/导入/提交/学院审/教务发布/退回/归档/更正申请与两级审/成绩单导出，
    均已由本文件各写操作调用 _audit() 落库，见 create_grade_task/enter_score/grade_import_confirm/
    submit_task/college_review/publish_grades/return_task/archive_task/change_request/_change_review/
    change_academic_review/export_transcript_xlsx）。

    角色分层（成绩明细属高敏感数据，不可与 08-成绩审核发布更正 §11 的分级口径冲突）：
    - ACADEMIC_ADMIN/SCHOOL_ADMIN/平台超管：本校全量（TENANT_ALL）；
    - COLLEGE_ADMIN：本校全量（学院级逐条收敛到具体教学班待补，与 list_tasks 同一已知简化——学院教务员
      目前看得到跨学院审计行，但写操作本身仍受 _check_college_scope 拦截，不构成越权写，只是只读展示未
      收窄，已记入施工记录，非阻断项）；
    - ACADEMIC_TEACHER：仅能查看操作人=本人的记录（COURSE 自查留痕，不得浏览其他教师的操作历史）；
    - 其余角色（含 STUDENT/STAFF 空权限）：拒绝。
    """
    role = (user.get("currentRoleCode") or "").upper()
    from app.models import AffairsAuditTrail
    with session() as db:
        conds = [AffairsAuditTrail.tenant_id == _tid(), AffairsAuditTrail.biz_type.like("AA_GRADE%")]
        if biz_type:
            conds.append(AffairsAuditTrail.biz_type == biz_type)
        if role in _REVIEW_ROLES or role == "COLLEGE_ADMIN" or user.get("userType") == "PLATFORM_SUPER_ADMIN":
            pass  # 校级/院级：本校全量，见上方角色分层说明
        elif role == "ACADEMIC_TEACHER":
            keys = _user_keys(user) or {"__none__"}
            conds.append(AffairsAuditTrail.operator.in_(keys))
        else:
            raise no_permission("无权限查看成绩操作审计")
        total = db.scalar(select(func.count()).select_from(AffairsAuditTrail).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.scalars(select(AffairsAuditTrail).where(*conds)
                          .order_by(AffairsAuditTrail.id.desc()).offset(offset).limit(page_size)).all()
        items = [{"id": str(a.id), "bizType": a.biz_type, "bizId": str(a.biz_id) if a.biz_id else None,
                  "action": a.action, "operator": a.operator, "roleName": a.role_name,
                  "detail": a.detail, "occurredAt": a.occurred_at.isoformat() if a.occurred_at else None}
                 for a in rows]
        return items, total


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
        items = [{"gradeId": str(g.id), "courseName": g.course_name, "term": g.term or "",
                  "credit": float(g.credit_value or 0), "score": g.score,
                  "passStatus": g.pass_status, "source": g.source or "LEGACY"} for g in rows]
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


def exception_list(user, term=None, exception_flag=None, page=1, page_size=50):
    """成绩异常清单（读侧，跨录入任务汇总缺考/缓考/免修标记学生，供教务/学院巡查）。
    数据源：t_aa_grade_record.exception_flag——该标记只在成绩明细表保留；发布时投影到
    t_acad_grade 只写 score/pass_status（PENDING），异常类型本身不下沉，故只能从本表读，
    不能从已发布台账反查（与 fail_list 数据源刻意不同，各自读各自权威源）。
    未做角色数据范围收敛（与同组 fail_list/grade_analysis 同一简化口径，见二者注释），
    仅 require_staff 门禁，已知简化见施工记录。"""
    from app.models import AaGradeRecord, AaGradeTask, StudentProfile
    with session() as db:
        join_task = and_(AaGradeTask.id == AaGradeRecord.task_id, AaGradeTask.tenant_id == AaGradeRecord.tenant_id)
        join_stu = and_(StudentProfile.id == AaGradeRecord.student_id,
                        StudentProfile.tenant_id == AaGradeRecord.tenant_id)
        conds = [AaGradeRecord.tenant_id == _tid(), AaGradeRecord.is_deleted.is_(False),
                 AaGradeRecord.exception_flag.is_not(None), AaGradeRecord.exception_flag != "NORMAL"]
        if exception_flag:
            conds.append(AaGradeRecord.exception_flag == exception_flag.upper())
        if term:
            conds.append(AaGradeTask.term_code == term)
        total = db.scalar(select(func.count()).select_from(AaGradeRecord)
                          .join(AaGradeTask, join_task).outerjoin(StudentProfile, join_stu)
                          .where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.execute(select(AaGradeRecord, AaGradeTask, StudentProfile)
                          .join(AaGradeTask, join_task).outerjoin(StudentProfile, join_stu)
                          .where(*conds).order_by(AaGradeRecord.id.desc())
                          .offset(offset).limit(page_size)).all()
        out = [{"recordId": str(r.id), "gradeTaskId": str(t.id), "studentId": str(r.student_id),
                "studentName": (s.real_name if s else ""), "studentNo": (s.student_no if s else ""),
                "courseName": t.course_name or "", "term": t.term_code or "",
                "exceptionFlag": r.exception_flag, "taskStatus": t.status} for r, t, s in rows]
        return out, total


_BUCKET_KEYS = ("90-100", "80-89", "70-79", "60-69", "0-59")


def _bucket_of(sc):
    if sc >= 90:
        return "90-100"
    if sc >= 80:
        return "80-89"
    if sc >= 70:
        return "70-79"
    if sc >= 60:
        return "60-69"
    return "0-59"


def _score_stats(scores, passed):
    """一组分数 → 分数段分布 / 及格率 / 优秀率 / 良好率 / 平均分 / 最高最低（正方式成绩分析统计口径）。"""
    total = len(scores)
    buckets = {k: 0 for k in _BUCKET_KEYS}
    for sc in scores:
        buckets[_bucket_of(sc)] += 1
    if not total:
        return {"total": 0, "passRate": 0.0, "excellentRate": 0.0, "goodRate": 0.0,
                "avgScore": 0.0, "maxScore": 0, "minScore": 0,
                "distribution": [{"range": k, "count": 0} for k in _BUCKET_KEYS]}
    return {"total": total, "passRate": round(passed / total, 3),
            "excellentRate": round(buckets["90-100"] / total, 3),
            "goodRate": round(buckets["80-89"] / total, 3),
            "avgScore": round(sum(scores) / total, 1),
            "maxScore": max(scores), "minScore": min(scores),
            "distribution": [{"range": k, "count": buckets[k]} for k in _BUCKET_KEYS]}


def grade_analysis(user, term=None, dimension=None):
    """成绩分析统计表（正方对标）：总体分数段分布+及格率+优秀率+平均分+最高最低；
    dimension=course/class 时追加「按课程 / 按班级」分组统计表（读侧聚合，已发布成绩口径，全租户）。
    向后兼容：不传 dimension 时返回结构在旧字段(total/passRate/distribution)上仅新增指标字段。"""
    from app.models import AcademicGrade, AcademicStudent
    with session() as db:
        conds = [AcademicGrade.tenant_id == _tid(), AcademicGrade.score.is_not(None),
                 AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False)]
        if term:
            conds.append(AcademicGrade.term == term)
        groups: dict[str, list] = {}
        if dimension == "class":
            join = and_(AcademicStudent.id == AcademicGrade.acad_student_id,
                        AcademicStudent.tenant_id == AcademicGrade.tenant_id)
            recs = db.execute(select(AcademicGrade.score, AcademicGrade.pass_status,
                                     AcademicStudent.class_id)
                              .outerjoin(AcademicStudent, join).where(*conds)).all()
            for sc, ps, cid in recs:
                groups.setdefault(str(cid) if cid else "未分班", []).append((int(sc), ps))
        else:
            recs = db.execute(select(AcademicGrade.score, AcademicGrade.pass_status,
                                     AcademicGrade.course_name).where(*conds)).all()
            if dimension == "course":
                for sc, ps, cn in recs:
                    groups.setdefault(cn or "未命名课程", []).append((int(sc), ps))
        all_scores = [int(r[0]) for r in recs]
        passed_all = sum(1 for r in recs if r[1] == "PASSED")
        result = _score_stats(all_scores, passed_all)
        if dimension in ("course", "class"):
            rows = []
            for name, pairs in groups.items():
                st = _score_stats([p[0] for p in pairs], sum(1 for p in pairs if p[1] == "PASSED"))
                st["name"] = name
                rows.append(st)
            rows.sort(key=lambda x: (-x["total"], x["name"]))
            result["dimension"] = dimension
            result["rows"] = rows
        return result


def export_grade_analysis_xlsx(user, term=None, dimension="course", purpose="") -> bytes:
    """成绩分析统计表导出 xlsx（水印+审计，同步下载；正方「课程/班级成绩分析统计表」业务对标）。"""
    if not (purpose or "").strip() or len((purpose or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    if dimension not in ("course", "class"):
        dimension = "course"
    data = grade_analysis(user, term, dimension)
    from app.services.xlsx_util import build_ledger_xlsx
    u = get_current_user_ctx() or {}
    watermark = (f"导出人：{u.get('realName') or u.get('loginName') or '-'}  "
                 f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose.strip()}")
    dim_label = "按课程" if dimension == "course" else "按班级"
    title = f"成绩分析统计表（{dim_label}{('·' + term) if term else ''}）"
    headers = ["名称", "记录数", "平均分", "最高分", "最低分", "及格率(%)", "优秀率(%)",
               "90-100", "80-89", "70-79", "60-69", "0-59"]
    rows = []
    for r in data.get("rows", []):
        dist = {d["range"]: d["count"] for d in r["distribution"]}
        rows.append([r["name"], r["total"], r["avgScore"], r["maxScore"], r["minScore"],
                     round(r["passRate"] * 100, 1), round(r["excellentRate"] * 100, 1),
                     dist["90-100"], dist["80-89"], dist["70-79"], dist["60-69"], dist["0-59"]])
    content = build_ledger_xlsx(title, headers, rows, watermark=watermark)
    with session() as db:
        _audit(db, "AC_GRADE_ANALYSIS", None, "GRADE_ANALYSIS_EXPORT",
               f"{title} 用途={purpose.strip()[:100]}")
        db.commit()
    return content
