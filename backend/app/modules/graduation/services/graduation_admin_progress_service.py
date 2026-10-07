"""毕设管理员的“开工检查”和“中期检查按导师看”（只读）。

- setup_check：首次使用向导的 5 项自动检查。重点是“导师账号能不能登录看到学生”——
  老师的毕设身份按 工号 = 登录账号 自动生效，台账工号对不上账号的导师登录后什么也看不到。
- midterm_by_mentor：按导师汇总中期检查进度，管理员一眼看出哪位导师还没检查。

两者都按当前身份的数据范围（student_scope_select）收敛：学院管理员只看本院，专业负责人只看本专业。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.models import GraduationBatch, GraduationMentor, GraduationMidterm, GraduationStudent
from app.modules.graduation.services.graduation_proposal_read_service import student_scope_select
from app.services.db_service import _iso, _tid, session

# 学生/导师在主流程里必须提交的材料；批次的材料规则里缺任何一项，学生走到那一步都会提交失败。
FLOW_MATERIALS = (
    ("TASKBOOK", "任务书"), ("PROPOSAL_REPORT", "开题报告"), ("MIDTERM_REPORT", "中期检查材料"),
    ("THESIS_DRAFT", "论文初稿"), ("THESIS_FINAL", "论文定稿"),
)
BATCH_STATUS_LABEL = {"DRAFT": "未发布", "RUNNING": "进行中", "CLOSED": "已结束", "ARCHIVED": "已归档", "VOIDED": "已作废"}
NAME_LIMIT = 10


def _batch(db, tenant_id: int, batch_id) -> GraduationBatch | None:
    row = db.get(GraduationBatch, int(batch_id)) if batch_id not in (None, "") else None
    if row is None or row.is_deleted or int(row.tenant_id) != int(tenant_id):
        return None
    return row


def _scoped_students(db, tenant_id: int, batch_id: int) -> list:
    return [
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
        GraduationStudent.batch_id == int(batch_id),
        GraduationStudent.id.in_(student_scope_select(db, tenant_id, batch_id=batch_id)),
    ]


def _material_rule_state(db, batch_id: int) -> tuple[str, list[str]]:
    """批次启用的材料规则是否覆盖主流程必需材料：OK / NONE（没有）/ CONFLICT（多个）/ MISSING（缺项）。"""
    from app.core.exceptions import AppException
    from app.modules.graduation.materials.rule_service import active_rule, rule_items

    try:
        rule = active_rule(db, int(batch_id))
    except AppException as exc:
        return ("CONFLICT" if getattr(exc, "code", "") == "MATERIAL_RULE_CONFLICT" or "多个" in str(exc) else "NONE"), []
    have = {str(item.material_code or "").upper() for item in rule_items(db, int(rule.id))}
    missing = [name for code, name in FLOW_MATERIALS if code not in have]
    return ("MISSING" if missing else "OK"), missing


def setup_check(batch_id) -> dict:
    """首次使用向导：批次 → 学生 → 导师 → 导师账号 → 发布，逐项给出是否完成与下一步。"""
    from app.models import User

    tenant_id = _tid()
    with session() as db:
        batch = _batch(db, tenant_id, batch_id)
        if batch is None:
            return {"batch": None, "steps": [], "allDone": False, "doneCount": 0, "total": 5}
        where = _scoped_students(db, tenant_id, batch.id)
        student_total = int(db.scalar(select(func.count(GraduationStudent.id)).where(*where)) or 0)
        without_mentor = int(db.scalar(select(func.count(GraduationStudent.id)).where(
            *where, GraduationStudent.mentor_id.is_(None))) or 0)
        mentor_ids = select(GraduationStudent.mentor_id).where(*where, GraduationStudent.mentor_id.is_not(None))
        mentors = db.scalars(select(GraduationMentor).where(
            GraduationMentor.tenant_id == tenant_id, GraduationMentor.is_deleted.is_(False),
            GraduationMentor.id.in_(mentor_ids),
        ).order_by(GraduationMentor.teacher_name)).all()
        logins = {str(x) for x in db.scalars(select(User.login_name).where(
            User.tenant_id == tenant_id, User.is_deleted.is_(False), User.status == "ACTIVE",
            User.login_name.in_([m.teacher_no for m in mentors if m.teacher_no] or ["\x00"]),
        )).all()}
        no_account = [m for m in mentors if not m.teacher_no or m.teacher_no not in logins]
        blocked = [m for m in mentors if str(m.qualification_status or "").upper() in {"DISABLED", "ARCHIVED", "REJECTED"}]
        stages = batch.stage_config if isinstance(batch.stage_config, list) else []
        dated = [s for s in stages if isinstance(s, dict) and (s.get("startDate") or s.get("endDate"))]
        published = str(batch.status or "").upper() in {"RUNNING", "CLOSED", "ARCHIVED"}
        rule_state, missing_materials = _material_rule_state(db, batch.id)

    def names(rows):
        return [f"{m.teacher_name or '未命名'}（工号 {m.teacher_no or '未填'}）" for m in rows[:NAME_LIMIT]]

    steps = [
        {"key": "timeline", "title": "建好批次和时间节点", "done": bool(dated),
         "detail": f"已设置 {len(dated)} 个阶段的时间" if dated else "还没有设置各阶段的开始/截止日期，老师和学生看不到截止时间",
         "action": "batch"},
        {"key": "students", "title": "导入学生", "done": student_total > 0,
         "detail": f"已导入 {student_total} 名学生" if student_total else "还没有学生，可用 Excel 一次导入",
         "action": "students"},
        {"key": "mentors", "title": "给每名学生分配导师", "done": student_total > 0 and without_mentor == 0,
         "detail": (f"还有 {without_mentor} 名学生没有导师" if without_mentor
                    else (f"{len(mentors)} 位导师已分配完" if student_total else "先导入学生")),
         "action": "mentors"},
        {"key": "accounts", "title": "导师能登录看到自己的学生", "done": bool(mentors) and not no_account and not blocked,
         "detail": ("导师台账的工号必须和他的登录账号一致，老师登录后才会自动看到自己的学生" if not mentors
                    else "全部导师账号正常" if not no_account and not blocked
                    else "；".join(filter(None, [
                        f"{len(no_account)} 位导师的工号找不到登录账号：{'、'.join(names(no_account))}" if no_account else "",
                        f"{len(blocked)} 位导师台账已停用：{'、'.join(names(blocked))}" if blocked else "",
                    ]))),
         "action": "mentors", "names": names(no_account) + names(blocked)},
        {"key": "publish", "title": "发布批次", "done": published,
         "detail": "已发布，老师和学生都能看到" if published else "发布后老师工作台和学生手机上才会出现毕业设计",
         "action": "publish"},
        {"key": "materials", "title": "材料规则覆盖全流程", "done": rule_state == "OK",
         "detail": ("任务书、开题、中期、初稿、定稿的材料规则都已配置" if rule_state == "OK"
                    else "发布批次时系统会自动生成标准材料规则" if not published and rule_state == "NONE"
                    else "批次还没有启用的材料规则，学生提交材料会失败，请到「材料规则」页面创建并启用" if rule_state == "NONE"
                    else "批次材料规则有多个启用版本，请联系技术支持处理" if rule_state == "CONFLICT"
                    else f"材料规则缺少：{'、'.join(missing_materials)}。学生走到这些环节会提交失败，请到「材料规则」页面补全并启用"),
         "action": "materials", "names": list(missing_materials)},
    ]
    done = sum(1 for s in steps if s["done"])
    return {
        "batch": {"id": str(batch.id), "name": batch.batch_name, "status": batch.status,
                  "statusLabel": BATCH_STATUS_LABEL.get(str(batch.status or "").upper(), batch.status)},
        "steps": steps, "doneCount": done, "total": len(steps), "allDone": done == len(steps),
        "counts": {"students": student_total, "withoutMentor": without_mentor, "mentors": len(mentors),
                   "mentorsWithoutAccount": len(no_account), "mentorsBlocked": len(blocked)},
    }


CHECKED_STATUSES = {"CHECKED_PASS", "RECTIFIED_PASS", "CHECKED_FAIL", "RECTIFYING", "RECTIFY_SUBMITTED"}
PENDING_LIMIT = 20


def midterm_by_mentor(batch_id) -> dict:
    """中期检查按导师看：每位导师 学生数 / 已检查 / 待检查 / 整改待复核 / 学生整改中 / 未到中期。"""
    from app.modules.graduation.services import graduation_process_consistency as process

    tenant_id = _tid()
    with session() as db:
        batch = _batch(db, tenant_id, batch_id)
        if batch is None:
            return {"rows": [], "summary": {}, "batchId": None}
        where = _scoped_students(db, tenant_id, batch.id)
        students = db.execute(select(
            GraduationStudent.id, GraduationStudent.name, GraduationStudent.student_no,
            GraduationStudent.class_name, GraduationStudent.mentor_id,
        ).where(*where).order_by(GraduationStudent.id)).all()
        eligible_without_row = {int(x) for x in db.scalars(select(GraduationStudent.id).where(
            *where, process._midterm_eligible_clause(), process._no_midterm_row())).all()}
        midterms: dict[int, tuple] = {}
        for sid, status, checked_at in db.execute(select(
            GraduationMidterm.gd_student_id, GraduationMidterm.status, GraduationMidterm.checked_at,
        ).where(
            GraduationMidterm.tenant_id == tenant_id, GraduationMidterm.is_deleted.is_(False),
            GraduationMidterm.gd_student_id.in_(select(GraduationStudent.id).where(*where)),
        ).order_by(GraduationMidterm.id)).all():
            midterms[int(sid)] = (str(status or "").upper(), checked_at)  # 同一学生多条时以最新一条为准
        mentor_ids = {int(row.mentor_id) for row in students if row.mentor_id is not None}
        mentors = {m.id: m for m in db.scalars(select(GraduationMentor).where(
            GraduationMentor.tenant_id == tenant_id, GraduationMentor.id.in_(mentor_ids or [-1]))).all()}

    groups: dict = {}
    for row in students:
        key = int(row.mentor_id) if row.mentor_id is not None else None
        g = groups.setdefault(key, {"total": 0, "checked": 0, "pendingCheck": 0, "pendingReview": 0,
                                    "rectifying": 0, "notReady": 0, "lastCheckedAt": None, "pendingStudents": []})
        g["total"] += 1
        status, checked_at = midterms.get(int(row.id), ("", None))
        if status in CHECKED_STATUSES:
            g["checked"] += 1
        if checked_at and (g["lastCheckedAt"] is None or checked_at > g["lastCheckedAt"]):
            g["lastCheckedAt"] = checked_at
        if status == "RECTIFY_SUBMITTED":
            g["pendingReview"] += 1
            label = "整改待复核"
        elif status == "RECTIFYING":
            g["rectifying"] += 1
            label = ""
        elif status == "PENDING" or (not status and int(row.id) in eligible_without_row):
            g["pendingCheck"] += 1
            label = "待检查"
        else:
            if not status:
                g["notReady"] += 1
            label = ""
        if label and len(g["pendingStudents"]) < PENDING_LIMIT:
            g["pendingStudents"].append({"gdStudentId": str(row.id), "studentName": row.name,
                                         "studentNo": row.student_no or "", "className": row.class_name or "",
                                         "statusLabel": label})

    rows = []
    for key, g in groups.items():
        mentor = mentors.get(key) if key is not None else None
        rows.append({
            "mentorId": str(key) if key is not None else None,
            "mentorName": (mentor.teacher_name if mentor else "") or ("未分配导师" if key is None else "导师台账已删除"),
            "teacherNo": (mentor.teacher_no if mentor else "") or "",
            **{k: v for k, v in g.items() if k != "lastCheckedAt"},
            "lastCheckedAt": _iso(g["lastCheckedAt"]),
        })
    # 待处理多的排前面，方便管理员先提醒；没有待处理的按姓名
    rows.sort(key=lambda r: (-(r["pendingCheck"] + r["pendingReview"]), r["mentorId"] is None, r["mentorName"]))
    summary = {k: sum(r[k] for r in rows) for k in ("total", "checked", "pendingCheck", "pendingReview", "rectifying", "notReady")}
    summary["mentorsWithPending"] = sum(1 for r in rows if r["pendingCheck"] + r["pendingReview"] > 0 and r["mentorId"])
    return {"batchId": str(batch.id), "rows": rows, "summary": summary}
