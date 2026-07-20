"""老系统数据迁移（21 域全量）——竞品替换历史数据导入。

设计依据：docs/03-业务模块设计/跨模块融合/13A-13B-历史数据导入与迁移设计.md 21 域清单。
本文件：管线 + P1 6 域（B1 学年学期 / B2 校历 / B3 作息 / B4 学籍名册 / B5 学籍异动历史 /
B10 历史成绩）；其余 15 域（学工 A1-A10 + 教务 B6-B9/B11）见 migration_domains_p2.py。

口径（与现有管线一致，禁止绕开）：
- 两步导入：dry_run（行级错误，行号从 2 起）→ confirm（整批一个事务，失败回滚）；
- 批次绑定 tenant_id，跨租户凭 batchNo 确认一律按"不存在"处理；
- 批次落 t_student_import_batch，remark 前缀 "migration:<domain>"（零 DDL，草案裁定）；
- 学籍状态写入唯一经 change_student_status()（红线：不得直写 t_student_profile.student_status）；
- 模板/错误行 xlsx 复用 xlsx_util（红线 R14：不自写 openpyxl 落库通道）。

重复策略（设计文档 §1.2）：
- OVERWRITE（字典/资源域：B1/B2/B3）：命中唯一键按白名单字段覆盖；B1 仅 DRAFT 可覆盖，
  PUBLISHED/FROZEN 报 STATE_LOCKED；
- ERROR（单据域：B4/B10）：命中唯一键报 DUP_IN_DB；
- SKIP（补录域：B5）：命中唯一键跳过计入 skippedRows，幂等重跑。
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, time as dt_time

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import db_enabled, get_sessionmaker
from app.services import xlsx_util

_REMARK_PREFIX = "migration:"


def _tid() -> int:
    try:
        return int(current_tenant_id() or 1000000000000000001)
    except (TypeError, ValueError):
        return 1000000000000000001


def _require_db():
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "数据迁移仅在真实数据库模式下可用（MySQL）")


# ═══════════ 通用取值/解析 ═══════════

# 厂商字段别名（金智 wisedu=大写拼音缩写 / 新版正方 jwglxt=小写拼音缩写 / 强智=中文列名）。
# 证据：docs/03-业务模块设计/系统管理中心/施工包/外部对标证据/
#       2026-07-18-数据迁移-厂商导出字段命名证据包.md（EV-JZ-01/02、EV-ZF-01/02、EV-QZ-01）。
# 注意：来源为接口逆向一手代码，≠ 各厂商官方导出模板列标题；实施时以学校真实导出样例二次校准。
_VENDOR_ALIASES: dict[str, list[str]] = {
    "studentNo": ["XH", "xh", "学 号"],
    "courseName": ["KCM", "kcmc", "课程", "课程名"],
    "score": ["ZCJ", "cj", "总评成绩", "总成绩"],
    "term": ["XNXQDM", "xnxq01id", "学年学期", "初修学期"],
    "credit": ["XF", "xf"],
    "examType": ["KSLXDM_DISPLAY", "ksxz", "考试性质"],
    "nature": ["KCXZDM_DISPLAY", "kcxzmc", "课程属性"],
}


def _cell(row: dict, key: str, title: str) -> str:
    """三层表头兼容：驼峰 key → 中文表头 → 厂商字段别名（金智/正方/强智）。"""
    v = row.get(key)
    if v is None or str(v).strip() == "":
        v = row.get(title)
    if v is None or str(v).strip() == "":
        for alias in _VENDOR_ALIASES.get(key, ()):
            v = row.get(alias)
            if v is not None and str(v).strip() != "":
                break
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S") if (v.hour or v.minute or v.second) else v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, dt_time):
        return v.strftime("%H:%M")
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v).strip() if v is not None else ""


def _parse_date(v: str):
    """兼容常见老系统日期格式：2026-07-05 / 2026/7/5 / 2026.07.05（§4.3 坑 2）。"""
    if not v:
        return None
    s = str(v).strip().replace("/", "-").replace(".", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


_HHMM = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


def _err(row_no: int, field: str, code: str, raw, message: str) -> dict:
    return {"rowNo": row_no, "rowIndex": row_no, "errorCode": code,
            "field": field, "rawValue": "" if raw is None else str(raw), "message": message}


# ═══════════ 域配置 ═══════════
# columns: (key, 中文表头, 必填, 示例, 说明)

_DOMAINS: dict[str, dict] = {
    "aa-term": {
        "label": "学年学期",
        "order": 1, "dependsOn": [], "dupPolicy": "OVERWRITE",
        "targetTable": "t_aa_term",
        "uniqueKey": "学年+学期号",
        "columns": [
            ("yearCode", "学年", True, "2024-2025", "格式 YYYY-YYYY"),
            ("termNo", "学期号", True, "1", "1 或 2"),
            ("termName", "学期名称", False, "2024-2025学年第一学期", ""),
            ("startDate", "开始日期", True, "2024-09-02", "YYYY-MM-DD"),
            ("endDate", "结束日期", True, "2025-01-17", "YYYY-MM-DD"),
            ("teachingWeeks", "教学周数", True, "18", "1-30"),
            ("examWeekStart", "考试周开始", False, "17", "第 N 教学周"),
            ("isCurrent", "是否当前学期", False, "否", "是/否，全校仅 1 个学期为是"),
        ],
    },
    "aa-calendar": {
        "label": "校历事件",
        "order": 2, "dependsOn": ["aa-term"], "dupPolicy": "OVERWRITE",
        "targetTable": "t_aa_calendar_event",
        "uniqueKey": "学期+事件类型+开始日期",
        "columns": [
            ("yearCode", "学年", True, "2024-2025", "须为已导入学期"),
            ("termNo", "学期号", True, "1", ""),
            ("eventType", "事件类型", True, "假期", "教学/考试/实习/假期/调休"),
            ("startDate", "开始日期", True, "2024-10-01", ""),
            ("endDate", "结束日期", False, "2024-10-07", ""),
            ("swapToDate", "调休至", False, "", "事件类型为调休时必填"),
            ("remark", "备注", False, "国庆假期", ""),
        ],
    },
    "aa-time-slot": {
        "label": "作息节次",
        "order": 3, "dependsOn": [], "dupPolicy": "OVERWRITE",
        "targetTable": "t_aa_time_slot",
        "uniqueKey": "节次号+校区编码",
        "columns": [
            ("slotNo", "节次号", True, "1", "从 1 起"),
            ("slotName", "节次名称", False, "第一节", ""),
            ("startTime", "开始时间", True, "08:00", "HH:MM"),
            ("endTime", "结束时间", True, "08:45", "HH:MM"),
            ("campusCode", "校区编码", False, "", "多校区时填写"),
        ],
    },
    "aa-student-status": {
        "label": "学籍名册（状态初始化）",
        "order": 4, "dependsOn": ["student-profile"], "dupPolicy": "ERROR",
        "targetTable": "t_student_profile.student_status + t_aa_status_change",
        "uniqueKey": "学号（每生一行）",
        "columns": [
            ("studentNo", "学号", True, "2023010001", "须已在学生主档"),
            ("studentStatus", "学籍状态", True, "休学",
             "在籍/注册/休学/保留学籍/留级/退学/转学/毕业/结业"),
            ("effectiveDate", "状态生效日期", True, "2024-09-01", ""),
            ("reason", "异动原因", False, "因病休学", "休学/退学必填"),
        ],
    },
    "aa-status-change-history": {
        "label": "学籍异动历史",
        "order": 5, "dependsOn": ["aa-student-status"], "dupPolicy": "SKIP",
        "targetTable": "t_aa_status_change",
        "uniqueKey": "学号+异动类型+生效日期",
        "columns": [
            ("studentNo", "学号", True, "2023010001", ""),
            ("changeType", "异动类型", True, "转专业",
             "入学注册/学年注册/转专业/转班/休学/复学/退学/留级/转学/毕业/结业"),
            ("reason", "原因", True, "个人申请转入软件技术专业", ""),
            ("effectiveDate", "生效日期", True, "2024-02-26", ""),
            ("termCode", "学期", False, "2023-2024-2", ""),
            ("fromOrg", "原院系专业班级", False, "信息学院/计算机应用/计应2301", "查不到组织时原文留档"),
            ("toOrg", "新院系专业班级", False, "信息学院/软件技术/软件2301", ""),
        ],
    },
    "aa-grade-history": {
        "label": "历史成绩",
        "order": 6, "dependsOn": ["student-profile"], "dupPolicy": "ERROR",
        "targetTable": "t_acad_grade（成绩唯一权威表）",
        "uniqueKey": "学号+课程名称+学期",
        "columns": [
            ("studentNo", "学号", True, "2023010001", "须已在学生主档"),
            ("courseName", "课程名称", True, "高等数学", ""),
            ("term", "学期", True, "2023-2024-1", "格式 YYYY-YYYY-N"),
            ("score", "成绩", True, "78", "0-100；等级制填 优/良/中/及格/不及格"),
            ("credit", "学分", False, "4", ""),
            ("nature", "课程性质", False, "必修", "必修/选修"),
            ("examType", "成绩性质", False, "正考", "正考/补考/重修，缺省正考"),
        ],
    },
}

# 学籍状态中文 → 枚举（B4；见 academic_affairs_status_service.STATUSES）
_STATUS_CN = {
    "在籍": "NORMAL", "正常": "NORMAL", "在读": "NORMAL",
    "注册": "REGISTERED", "已注册": "REGISTERED",
    "休学": "SUSPENDED", "保留学籍": "PRESERVED", "留级": "RETAINED",
    "退学": "WITHDRAWN", "转学": "TRANSFER_SCHOOL",
    "毕业": "GRADUATED", "结业": "COMPLETED",
}
# 目标状态 → 异动流水 change_type
_STATUS_CHANGE_TYPE = {
    "REGISTERED": "ANNUAL_REGISTER", "SUSPENDED": "SUSPEND", "PRESERVED": "PRESERVE",
    "RETAINED": "RETAIN", "WITHDRAWN": "WITHDRAW", "TRANSFER_SCHOOL": "TRANSFER_SCHOOL",
    "GRADUATED": "GRADUATE", "COMPLETED": "COMPLETE",
}

_CHANGE_TYPE_CN = {
    "入学注册": "ENROLL_REGISTER", "学年注册": "ANNUAL_REGISTER", "学期注册": "SEMESTER_REGISTER",
    "转专业": "TRANSFER_MAJOR", "转班": "TRANSFER_CLASS", "休学": "SUSPEND", "复学": "RESUME",
    "退学": "WITHDRAW", "留级": "RETAIN", "转学": "TRANSFER_SCHOOL",
    "毕业": "GRADUATE", "结业": "COMPLETE",
}

_EVENT_TYPE_CN = {"教学": "TEACHING", "考试": "EXAM", "实习": "INTERNSHIP",
                  "假期": "HOLIDAY", "调休": "SWAP"}

_GRADE_CN = {"优": 95, "优秀": 95, "良": 85, "良好": 85, "中": 75, "中等": 75,
             "及格": 65, "合格": 65, "不及格": 50, "不合格": 50}

_EXAM_TYPE_CN = {"正考": "FINAL", "补考": "MAKEUP", "重修": "RETAKE"}


def domain_meta(domain: str) -> dict:
    if domain not in _DOMAINS:
        raise AppException("VALIDATION_ERROR", f"未知迁移域：{domain}（支持 {'/'.join(_DOMAINS)}）")
    return _DOMAINS[domain]


def build_template(domain: str) -> bytes:
    meta = domain_meta(domain)
    headers = [c[1] for c in meta["columns"]]
    required = [c[1] for c in meta["columns"] if c[2]]
    samples = [[c[3] for c in meta["columns"]]]
    notes = [f"1. 老系统数据迁移·{meta['label']}模板；带 * 为必填列，请勿修改表头。",
             f"2. 租户内唯一键：{meta['uniqueKey']}；重复策略：{meta['dupPolicy']}。",
             "3. 先在老系统导出 Excel，按本模板列改写后上传；日期支持 2026-07-05 / 2026/7/5 / 2026.07.05。"]
    notes += [f"· {c[1]}：{c[4]}" for c in meta["columns"] if c[4]]
    return xlsx_util.build_template_xlsx(headers, samples=samples, required=required, notes=notes)


# ═══════════ 各域 dry-run 校验 ═══════════
# 返回 (ok_rows, errors, skipped)；ok_rows 为规范化行（confirm 直接落库）。

def _rows_iter(meta, rows):
    for i, raw in enumerate(rows, start=2):
        yield i, {c[0]: _cell(raw, c[0], c[1]) for c in meta["columns"]}


def _check_required(meta, row, i, errors) -> bool:
    ok = True
    for key, title, required, *_ in meta["columns"]:
        if required and not row.get(key):
            errors.append(_err(i, key, "REQUIRED_MISSING", "", f"{title} 必填"))
            ok = False
    return ok


def _validate_term(db, meta, rows):
    from sqlalchemy import select
    from app.models import AaTerm
    existing = {(t.year_code, t.term_no): t for t in db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == _tid(), AaTerm.is_deleted.is_(False)))}
    ok, errors, seen, ranges = [], [], set(), []
    for t in existing.values():
        if t.start_date and t.end_date:
            ranges.append((t.start_date, t.end_date, f"{t.year_code}-{t.term_no}"))
    for i, r in _rows_iter(meta, rows):
        if not _check_required(meta, r, i, errors):
            continue
        if not re.match(r"^\d{4}-\d{4}$", r["yearCode"]):
            errors.append(_err(i, "yearCode", "FORMAT_INVALID", r["yearCode"], "学年格式须为 YYYY-YYYY"))
            continue
        if r["termNo"] not in ("1", "2"):
            errors.append(_err(i, "termNo", "ENUM_INVALID", r["termNo"], "学期号须为 1 或 2"))
            continue
        start, end = _parse_date(r["startDate"]), _parse_date(r["endDate"])
        if not start or not end or end <= start:
            errors.append(_err(i, "startDate", "RANGE_INVALID", f"{r['startDate']}~{r['endDate']}",
                               "起止日期无法解析或结束不晚于开始"))
            continue
        try:
            weeks = int(float(r["teachingWeeks"]))
        except ValueError:
            weeks = 0
        if not 1 <= weeks <= 30:
            errors.append(_err(i, "teachingWeeks", "RANGE_INVALID", r["teachingWeeks"], "教学周数须为 1-30"))
            continue
        key = (r["yearCode"], int(r["termNo"]))
        if key in seen:
            errors.append(_err(i, "yearCode", "DUP_IN_FILE", f"{key[0]}-{key[1]}", "学年+学期号在文件内重复"))
            continue
        hit = existing.get(key)
        if hit and hit.status not in ("DRAFT",):
            errors.append(_err(i, "yearCode", "STATE_LOCKED", f"{key[0]}-{key[1]}",
                               f"学期已{hit.status}，不允许覆盖（改课走业务流程）"))
            continue
        overlap = next((label for (s0, e0, label) in ranges
                        if not hit and s0 and e0 and start <= e0 and end >= s0), None)
        if overlap:
            errors.append(_err(i, "startDate", "RANGE_OVERLAP", r["startDate"], f"与已有学期 {overlap} 日期重叠"))
            continue
        seen.add(key)
        ranges.append((start, end, f"{key[0]}-{key[1]}"))
        ok.append({"yearCode": r["yearCode"], "termNo": int(r["termNo"]), "termName": r["termName"] or None,
                   "startDate": start, "endDate": end, "teachingWeeks": weeks,
                   "examWeekStart": int(float(r["examWeekStart"])) if r["examWeekStart"] else None,
                   "isCurrent": r["isCurrent"] in ("是", "true", "True", "1")})
    return ok, errors, 0


def _persist_term(db, rows) -> dict:
    from sqlalchemy import select
    from app.models import AaTerm
    created = updated = 0
    for r in rows:
        hit = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == _tid(), AaTerm.year_code == r["yearCode"],
            AaTerm.term_no == r["termNo"], AaTerm.is_deleted.is_(False))).first()
        if hit:
            hit.term_name, hit.start_date, hit.end_date = r["termName"], r["startDate"], r["endDate"]
            hit.teaching_weeks, hit.exam_week_start = r["teachingWeeks"], r["examWeekStart"]
            hit.version = (hit.version or 0) + 1
            updated += 1
            target = hit
        else:
            target = AaTerm(tenant_id=_tid(), year_code=r["yearCode"], term_no=r["termNo"],
                            term_name=r["termName"], start_date=r["startDate"], end_date=r["endDate"],
                            teaching_weeks=r["teachingWeeks"], exam_week_start=r["examWeekStart"],
                            status="DRAFT")
            db.add(target)
            created += 1
        if r["isCurrent"]:
            db.flush()
            from app.models import AaTerm as _T
            for other in db.scalars(select(_T).where(
                    _T.tenant_id == _tid(), _T.is_current.is_(True), _T.id != target.id)):
                other.is_current = False
            target.is_current = True
    return {"created": created, "updated": updated}


def _validate_calendar(db, meta, rows):
    from sqlalchemy import select
    from app.models import AaTerm
    terms = {(t.year_code, str(t.term_no)): t for t in db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == _tid(), AaTerm.is_deleted.is_(False)))}
    ok, errors, seen = [], [], set()
    for i, r in _rows_iter(meta, rows):
        if not _check_required(meta, r, i, errors):
            continue
        term = terms.get((r["yearCode"], r["termNo"]))
        if not term:
            errors.append(_err(i, "yearCode", "REF_NOT_FOUND", f"{r['yearCode']}/{r['termNo']}",
                               f"学期 {r['yearCode']} 第 {r['termNo']} 学期未导入（先导学年学期）"))
            continue
        etype = _EVENT_TYPE_CN.get(r["eventType"], r["eventType"])
        if etype not in _EVENT_TYPE_CN.values():
            errors.append(_err(i, "eventType", "ENUM_INVALID", r["eventType"],
                               "事件类型须为：教学/考试/实习/假期/调休"))
            continue
        start = _parse_date(r["startDate"])
        if not start:
            errors.append(_err(i, "startDate", "FORMAT_INVALID", r["startDate"], "开始日期无法解析"))
            continue
        end = _parse_date(r["endDate"]) if r["endDate"] else None
        swap = _parse_date(r["swapToDate"]) if r["swapToDate"] else None
        if etype == "SWAP" and not swap:
            errors.append(_err(i, "swapToDate", "REQUIRED_MISSING", "", "调休事件必须填写「调休至」"))
            continue
        if term.start_date and term.end_date and not (term.start_date <= start <= term.end_date):
            errors.append(_err(i, "startDate", "RANGE_INVALID", r["startDate"],
                               f"日期不在学期 {r['yearCode']}-{r['termNo']} 区间内"))
            continue
        key = (term.id, etype, start)
        if key in seen:
            errors.append(_err(i, "startDate", "DUP_IN_FILE", r["startDate"], "学期+事件类型+开始日期在文件内重复"))
            continue
        seen.add(key)
        ok.append({"termId": term.id, "eventType": etype, "startDate": start,
                   "endDate": end, "swapToDate": swap, "remark": r["remark"] or None})
    return ok, errors, 0


def _persist_calendar(db, rows) -> dict:
    from sqlalchemy import select
    from app.models import AaCalendarEvent
    created = updated = 0
    for r in rows:
        hit = db.scalars(select(AaCalendarEvent).where(
            AaCalendarEvent.tenant_id == _tid(), AaCalendarEvent.term_id == r["termId"],
            AaCalendarEvent.event_type == r["eventType"], AaCalendarEvent.start_date == r["startDate"],
            AaCalendarEvent.is_deleted.is_(False))).first()
        if hit:
            hit.end_date, hit.swap_to_date, hit.remark = r["endDate"], r["swapToDate"], r["remark"]
            hit.version = (hit.version or 0) + 1
            updated += 1
        else:
            db.add(AaCalendarEvent(tenant_id=_tid(), term_id=r["termId"], event_type=r["eventType"],
                                   start_date=r["startDate"], end_date=r["endDate"],
                                   swap_to_date=r["swapToDate"], remark=r["remark"]))
            created += 1
    return {"created": created, "updated": updated}


def _validate_time_slot(db, meta, rows):
    ok, errors, seen = [], [], set()
    for i, r in _rows_iter(meta, rows):
        if not _check_required(meta, r, i, errors):
            continue
        try:
            slot_no = int(float(r["slotNo"]))
        except ValueError:
            errors.append(_err(i, "slotNo", "FORMAT_INVALID", r["slotNo"], "节次号须为数字"))
            continue
        if not (_HHMM.match(r["startTime"]) and _HHMM.match(r["endTime"])):
            errors.append(_err(i, "startTime", "FORMAT_INVALID", f"{r['startTime']}/{r['endTime']}",
                               "时间格式须为 HH:MM"))
            continue
        if r["endTime"] <= r["startTime"]:
            errors.append(_err(i, "endTime", "RANGE_INVALID", r["endTime"], "结束时间须晚于开始时间"))
            continue
        key = (slot_no, r["campusCode"])
        if key in seen:
            errors.append(_err(i, "slotNo", "DUP_IN_FILE", r["slotNo"], "节次号+校区在文件内重复"))
            continue
        seen.add(key)
        ok.append({"slotNo": slot_no, "slotName": r["slotName"] or f"第{slot_no}节",
                   "startTime": r["startTime"], "endTime": r["endTime"],
                   "campusCode": r["campusCode"] or None})
    return ok, errors, 0


def _persist_time_slot(db, rows) -> dict:
    from sqlalchemy import select
    from app.models import AaTimeSlot
    created = updated = 0
    for r in rows:
        hit = db.scalars(select(AaTimeSlot).where(
            AaTimeSlot.tenant_id == _tid(), AaTimeSlot.slot_no == r["slotNo"],
            AaTimeSlot.campus_code.is_(None) if r["campusCode"] is None
            else AaTimeSlot.campus_code == r["campusCode"],
            AaTimeSlot.is_deleted.is_(False))).first()
        if hit:
            hit.slot_name, hit.start_time, hit.end_time = r["slotName"], r["startTime"], r["endTime"]
            hit.version = (hit.version or 0) + 1
            updated += 1
        else:
            db.add(AaTimeSlot(tenant_id=_tid(), slot_no=r["slotNo"], slot_name=r["slotName"],
                              start_time=r["startTime"], end_time=r["endTime"],
                              campus_code=r["campusCode"], enabled=True, status="ENABLED"))
            created += 1
    return {"created": created, "updated": updated}


def _student_map(db) -> dict:
    from sqlalchemy import select
    from app.models import StudentProfile
    return {s.student_no: s for s in db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False)))}


def _validate_student_status(db, meta, rows):
    from app.modules.academic_affairs.services.academic_affairs_status_service import can_transition
    students = _student_map(db)
    ok, errors, seen, skipped = [], [], set(), 0
    for i, r in _rows_iter(meta, rows):
        if not _check_required(meta, r, i, errors):
            continue
        target = _STATUS_CN.get(r["studentStatus"], r["studentStatus"])
        if target not in set(_STATUS_CN.values()):
            errors.append(_err(i, "studentStatus", "ENUM_INVALID", r["studentStatus"],
                               "学籍状态须为：在籍/注册/休学/保留学籍/留级/退学/转学/毕业/结业"))
            continue
        s = students.get(r["studentNo"])
        if not s:
            errors.append(_err(i, "studentNo", "REF_NOT_FOUND", r["studentNo"],
                               f"学号 {r['studentNo']} 不在学生主档（先导学生主档）"))
            continue
        if r["studentNo"] in seen:
            errors.append(_err(i, "studentNo", "DUP_IN_FILE", r["studentNo"], "每个学生只允许一行"))
            continue
        seen.add(r["studentNo"])
        eff = _parse_date(r["effectiveDate"])
        if not eff:
            errors.append(_err(i, "effectiveDate", "FORMAT_INVALID", r["effectiveDate"], "生效日期无法解析"))
            continue
        if s.student_status == target:
            skipped += 1  # 现状即目标状态：按 SKIP 计数不报错（设计 B4）
            continue
        if target == "NORMAL":
            errors.append(_err(i, "studentStatus", "VALIDATION_ERROR", r["studentStatus"],
                               f"学生现状为 {s.student_status}，历史迁移不支持迁回「在籍」"))
            continue
        if target in ("SUSPENDED", "WITHDRAWN") and not r["reason"]:
            errors.append(_err(i, "reason", "REQUIRED_MISSING", "", "休学/退学必须填写异动原因"))
            continue
        if not can_transition(s.student_status, target):
            errors.append(_err(i, "studentStatus", "VALIDATION_ERROR", r["studentStatus"],
                               f"学籍状态不允许 {s.student_status} → {target}"))
            continue
        ok.append({"studentId": s.id, "studentNo": r["studentNo"], "toStatus": target,
                   "changeType": _STATUS_CHANGE_TYPE[target], "reason": r["reason"] or "历史数据迁移",
                   "effectiveDate": eff})
    return ok, errors, skipped


def _persist_student_status(db, rows) -> dict:
    from sqlalchemy import select
    from app.models import AaStatusChange
    from app.modules.academic_affairs.services.academic_affairs_status_service import change_student_status
    for r in rows:
        change_student_status(db, r["studentId"], r["toStatus"], r["changeType"],
                              reason=r["reason"], operator="migration")
        # 唯一入口写入后，把流水生效日期改为老系统真实日期（历史留痕，不绕开入口）
        row = db.scalars(select(AaStatusChange).where(
            AaStatusChange.tenant_id == _tid(), AaStatusChange.student_id == r["studentId"],
            AaStatusChange.change_type == r["changeType"]).order_by(AaStatusChange.id.desc())).first()
        if row:
            row.effective_date = r["effectiveDate"]
    return {"created": len(rows)}


def _validate_status_history(db, meta, rows):
    from sqlalchemy import select
    from app.models import AaStatusChange
    students = _student_map(db)
    existing = {(c.student_id, c.change_type, c.effective_date.date() if c.effective_date else None)
                for c in db.scalars(select(AaStatusChange).where(
                    AaStatusChange.tenant_id == _tid(), AaStatusChange.is_deleted.is_(False)))}
    ok, errors, seen, skipped = [], [], set(), 0
    for i, r in _rows_iter(meta, rows):
        if not _check_required(meta, r, i, errors):
            continue
        ctype = _CHANGE_TYPE_CN.get(r["changeType"], r["changeType"])
        if ctype not in _CHANGE_TYPE_CN.values():
            errors.append(_err(i, "changeType", "ENUM_INVALID", r["changeType"],
                               f"异动类型须为：{'/'.join(_CHANGE_TYPE_CN)}"))
            continue
        s = students.get(r["studentNo"])
        if not s:
            errors.append(_err(i, "studentNo", "REF_NOT_FOUND", r["studentNo"],
                               f"学号 {r['studentNo']} 不在学生主档"))
            continue
        eff = _parse_date(r["effectiveDate"])
        if not eff:
            errors.append(_err(i, "effectiveDate", "FORMAT_INVALID", r["effectiveDate"], "生效日期无法解析"))
            continue
        if eff > datetime.utcnow():
            errors.append(_err(i, "effectiveDate", "RANGE_INVALID", r["effectiveDate"], "生效日期不能晚于今天"))
            continue
        key = (s.id, ctype, eff.date())
        if key in existing or key in seen:
            skipped += 1  # SKIP 策略：已存在/文件内重复的行跳过，幂等重跑
            continue
        seen.add(key)
        reason = r["reason"]
        if r["fromOrg"] or r["toOrg"]:
            reason = f"{reason}（原：{r['fromOrg'] or '-'} → 新：{r['toOrg'] or '-'}）"
        ok.append({"studentId": s.id, "changeType": ctype, "reason": reason[:500],
                   "effectiveDate": eff, "termCode": r["termCode"] or None})
    return ok, errors, skipped


def _persist_status_history(db, rows) -> dict:
    from app.models import AaStatusChange
    for r in rows:
        db.add(AaStatusChange(tenant_id=_tid(), student_id=r["studentId"], change_type=r["changeType"],
                              reason=r["reason"], effective_date=r["effectiveDate"],
                              term_code=r["termCode"], status="EFFECTIVE"))
    return {"created": len(rows)}


def _validate_grade(db, meta, rows):
    from sqlalchemy import select
    from app.models import AcademicGrade, AcademicStudent
    students = _student_map(db)
    acad = {a.student_no: a for a in db.scalars(select(AcademicStudent).where(
        AcademicStudent.tenant_id == _tid(), AcademicStudent.is_deleted.is_(False)))}
    existing = set()
    if acad:
        id2no = {a.id: no for no, a in acad.items()}
        for g in db.scalars(select(AcademicGrade).where(
                AcademicGrade.tenant_id == _tid(), AcademicGrade.is_deleted.is_(False))):
            no = id2no.get(g.acad_student_id)
            if no:
                existing.add((no, g.course_name, g.term or ""))
    ok, errors, seen = [], [], set()
    for i, r in _rows_iter(meta, rows):
        if not _check_required(meta, r, i, errors):
            continue
        if r["studentNo"] not in students:
            errors.append(_err(i, "studentNo", "REF_NOT_FOUND", r["studentNo"],
                               f"学号 {r['studentNo']} 不在学生主档（先导学生主档）"))
            continue
        if not re.match(r"^\d{4}-\d{4}-[12]$", r["term"]):
            errors.append(_err(i, "term", "FORMAT_INVALID", r["term"], "学期格式须为 YYYY-YYYY-N（N=1/2）"))
            continue
        raw_score = r["score"]
        if raw_score in _GRADE_CN:
            score = _GRADE_CN[raw_score]
        else:
            try:
                score = int(float(raw_score))
            except ValueError:
                errors.append(_err(i, "score", "FORMAT_INVALID", raw_score,
                                   f"成绩「{raw_score}」无法解析（0-100 或 优/良/中/及格/不及格）"))
                continue
            if not 0 <= score <= 100:
                errors.append(_err(i, "score", "RANGE_INVALID", raw_score, "成绩须在 0-100"))
                continue
        key = (r["studentNo"], r["courseName"], r["term"])
        if key in seen:
            errors.append(_err(i, "courseName", "DUP_IN_FILE", "/".join(key), "学号+课程+学期在文件内重复"))
            continue
        if key in existing:
            errors.append(_err(i, "courseName", "DUP_IN_DB", "/".join(key),
                               "该生该课该学期成绩已存在（历史成绩不可覆盖）"))
            continue
        seen.add(key)
        try:
            credit = float(r["credit"]) if r["credit"] else 0
        except ValueError:
            credit = 0
        ok.append({"studentNo": r["studentNo"], "courseName": r["courseName"], "term": r["term"],
                   "score": score, "credit": credit,
                   "nature": "ELECTIVE" if r["nature"] in ("选修", "ELECTIVE") else "REQUIRED",
                   "examType": _EXAM_TYPE_CN.get(r["examType"], "FINAL")})
    return ok, errors, 0


def _persist_grade(db, rows) -> dict:
    from sqlalchemy import select
    from app.models import AcademicGrade, AcademicStudent, StudentProfile
    acad = {a.student_no: a for a in db.scalars(select(AcademicStudent).where(
        AcademicStudent.tenant_id == _tid(), AcademicStudent.is_deleted.is_(False)))}
    created = 0
    for r in rows:
        a = acad.get(r["studentNo"])
        if not a:
            s = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.student_no == r["studentNo"],
                StudentProfile.is_deleted.is_(False))).first()
            a = AcademicStudent(tenant_id=_tid(), student_no=r["studentNo"],
                                student_id=(s.id if s else None), name=(s.real_name if s else r["studentNo"]),
                                grade=(s.grade if s else None))
            db.add(a)
            db.flush()
            acad[r["studentNo"]] = a
        db.add(AcademicGrade(tenant_id=_tid(), acad_student_id=a.id, course_name=r["courseName"],
                             term=r["term"], nature=r["nature"], credit_value=r["credit"],
                             score=r["score"], pass_status="PASS" if r["score"] >= 60 else "FAIL",
                             exam_type=r["examType"], source="LEGACY"))
        created += 1
    return {"created": created}


_VALIDATORS = {"aa-term": _validate_term, "aa-calendar": _validate_calendar,
               "aa-time-slot": _validate_time_slot, "aa-student-status": _validate_student_status,
               "aa-status-change-history": _validate_status_history, "aa-grade-history": _validate_grade}
_PERSISTERS = {"aa-term": _persist_term, "aa-calendar": _persist_calendar,
               "aa-time-slot": _persist_time_slot, "aa-student-status": _persist_student_status,
               "aa-status-change-history": _persist_status_history, "aa-grade-history": _persist_grade}

# ── P2 · 15 域注册（学工 A1-A10 + 教务 B6-B9/B11；配置与实现见 migration_domains_p2） ──
from app.services import migration_domains_p2 as _p2  # noqa: E402

_DOMAINS.update(_p2.P2_DOMAINS)
_VALIDATORS.update(_p2.P2_VALIDATORS)
_PERSISTERS.update(_p2.P2_PERSISTERS)
_PREVIEW_MASKS = dict(_p2.P2_PREVIEW_MASKS)


# ═══════════ 两步管线 ═══════════

def dry_run(domain: str, rows: list[dict]) -> dict:
    meta = domain_meta(domain)
    _require_db()
    from app.services.import_export_service import _rule
    max_rows = int(_rule("import", "importMaxRows") or 5000)
    if len(rows) > max_rows:
        raise AppException("VALIDATION_ERROR",
                           f"单次导入不能超过 {max_rows} 行（平台规则中心配置），当前 {len(rows)} 行")
    db = get_sessionmaker()()
    try:
        ok_rows, errors, skipped = _VALIDATORS[domain](db, meta, rows)
    finally:
        db.close()
    batch_no = f"MIG{datetime.now():%Y%m%d%H%M%S}{uuid.uuid4().hex[:4]}"
    status = "DRY_RUN_PASSED" if not errors else "DRY_RUN_FAILED"
    actor_key = (get_current_user_ctx() or {}).get("userId")
    db2 = get_sessionmaker()()
    try:
        from app.models import StudentImportBatch
        db2.add(StudentImportBatch(tenant_id=_tid(), batch_no=batch_no, total_rows=len(rows),
                                   success_rows=0, error_rows=len(errors), status=status,
                                   remark=f"{_REMARK_PREFIX}{domain} ok={len(ok_rows)} skip={skipped}"))
        db2.commit()
    finally:
        db2.close()
    from app.services import shared_import_batch_service as shared_batches
    shared_batches.create(_tid(), f"MIGRATION:{domain}", batch_no, status,
                          {"domain": domain, "rows": ok_rows}, errors=errors,
                          operator_key=actor_key)
    mask = _PREVIEW_MASKS.get(domain)
    preview = [mask(r) for r in ok_rows[:200]] if mask else ok_rows[:200]
    return {"batchNo": batch_no, "domain": domain, "status": status,
            "totalRows": len(rows), "okRows": len(ok_rows), "errorRows": len(errors),
            "skippedRows": skipped, "errors": errors[:50],
            # 预览行（前端预校验表格用；敏感域已脱敏；确认写入以服务端批次内容为准，不回传超 200 行）
            "rows": preview}


def confirm(batch_no: str) -> dict:
    _require_db()
    from sqlalchemy import select
    from app.models import StudentImportBatch
    lookup = get_sessionmaker()()
    try:
        ledger = lookup.scalars(select(StudentImportBatch).where(
            StudentImportBatch.tenant_id == _tid(),
            StudentImportBatch.batch_no == batch_no,
            StudentImportBatch.remark.like(f"{_REMARK_PREFIX}%"))).first()
        if not ledger:
            raise not_found("导入批次不存在或已过期，请重新校验")
        domain = (ledger.remark or "").removeprefix(_REMARK_PREFIX).split(" ")[0]
    finally:
        lookup.close()
    from app.services import shared_import_batch_service as shared_batches
    payload, claim_token, already_done = shared_batches.claim(
        _tid(), f"MIGRATION:{domain}", batch_no, required_status="DRY_RUN_PASSED")
    if already_done:
        return payload
    db = get_sessionmaker()()
    try:
        result = _PERSISTERS[domain](db, payload["rows"])
        b = db.scalars(select(StudentImportBatch).where(
            StudentImportBatch.tenant_id == _tid(),
            StudentImportBatch.batch_no == batch_no)).first()
        if b:
            b.status = "SUCCESS"
            b.success_rows = len(payload["rows"])
        db.commit()  # 整批一个事务：任一行失败自动回滚
    except Exception as exc:
        db.rollback()
        from sqlalchemy import select as _sel
        db_fail = get_sessionmaker()()
        try:
            from app.models import StudentImportBatch
            b = db_fail.scalars(_sel(StudentImportBatch).where(
                StudentImportBatch.tenant_id == _tid(),
                StudentImportBatch.batch_no == batch_no)).first()
            if b:
                b.status = "CONFIRM_FAILED"
                db_fail.commit()
        finally:
            db_fail.close()
        shared_batches.fail(_tid(), f"MIGRATION:{domain}", batch_no,
                            claim_token, str(exc), retryable=True)
        raise
    finally:
        db.close()
    public_result = {"batchNo": batch_no, "domain": domain, "status": "SUCCESS",
                     "insertedRows": len(payload["rows"]), **result}
    shared_batches.finish(_tid(), f"MIGRATION:{domain}", batch_no, claim_token, public_result)
    return public_result


# ═══════════ 总览 / 对账 / 批次 ═══════════

def _counts(db) -> dict:
    from sqlalchemy import func, select
    from app.models import (AaCalendarEvent, AaCourse, AaGraduationAuditResult, AaProgram,
                            AaScheduleItem, AaStatusChange, AaTeachingTask, AaTerm, AaTimeSlot,
                            AcademicGrade, AffairsClassCadre, AffairsRiskRecord, AidLevelHistory,
                            CsLeave, DisciplineCase, DormBed, DormRoom, FundingApplication,
                            StudentContact, StudentProfile)

    def _cnt(model, *conds):
        return db.scalar(select(func.count()).select_from(model).where(
            model.tenant_id == _tid(), model.is_deleted.is_(False), *conds)) or 0

    return {
        "student-profile": _cnt(StudentProfile),
        "aa-term": _cnt(AaTerm),
        "aa-calendar": _cnt(AaCalendarEvent),
        "aa-time-slot": _cnt(AaTimeSlot),
        "aa-student-status": _cnt(AaStatusChange, AaStatusChange.status == "EFFECTIVE"),
        "aa-status-change-history": _cnt(AaStatusChange, AaStatusChange.status == "EFFECTIVE"),
        "aa-grade-history": _cnt(AcademicGrade, AcademicGrade.source == "LEGACY"),
        # P2 学工域
        "affairs-family-contact": _cnt(StudentContact, StudentContact.contact_type.in_(
            ("GUARDIAN_PHONE", "EMERGENCY_PHONE"))),
        "affairs-class-cadre": _cnt(AffairsClassCadre),
        "affairs-dorm-building": _cnt(DormRoom),
        "affairs-dorm-assign": _cnt(DormBed, DormBed.status == "OCCUPIED"),
        "affairs-leave-history": _cnt(CsLeave, CsLeave.student_id.isnot(None)),
        "affairs-aid-history": db.scalar(select(func.count()).select_from(AidLevelHistory).where(
            AidLevelHistory.tenant_id == _tid())) or 0,  # append-only 表无 is_deleted
        "affairs-funding-history": _cnt(FundingApplication, FundingApplication.status == "GRANTED"),
        "affairs-discipline-history": _cnt(DisciplineCase),
        "affairs-talk-history": _cnt(_p2_model("TalkRecord")),
        "affairs-risk-manual": _cnt(AffairsRiskRecord, AffairsRiskRecord.source == "MANUAL"),
        # P2 教务域
        "aa-course": _cnt(AaCourse),
        "aa-program": _cnt(AaProgram),
        "aa-teaching-task": _cnt(AaTeachingTask),
        "aa-schedule": _cnt(AaScheduleItem, AaScheduleItem.source == "IMPORT"),
        "aa-graduation-history": _cnt(AaGraduationAuditResult),
    }


def _p2_model(name):
    import app.models as _m
    return getattr(_m, name)


def overview() -> dict:
    """迁移地图：6 域的依赖、当前库内数量、最近批次状态。"""
    _require_db()
    db = get_sessionmaker()()
    try:
        counts = _counts(db)
        from sqlalchemy import select
        from app.models import StudentImportBatch
        latest: dict[str, dict] = {}
        for b in db.scalars(select(StudentImportBatch).where(
                StudentImportBatch.tenant_id == _tid(),
                StudentImportBatch.remark.like(f"{_REMARK_PREFIX}%")).order_by(StudentImportBatch.id.desc())):
            dom = (b.remark or "").removeprefix(_REMARK_PREFIX).split(" ")[0]
            if dom and dom not in latest:
                latest[dom] = {"batchNo": b.batch_no, "status": b.status,
                               "totalRows": b.total_rows, "successRows": b.success_rows,
                               "errorRows": b.error_rows}
        domains = []
        for code, meta in sorted(_DOMAINS.items(), key=lambda kv: kv[1]["order"]):
            deps = meta["dependsOn"]
            deps_met = all(counts.get(d, 0) > 0 for d in deps)
            domains.append({
                "domain": code, "label": meta["label"], "order": meta["order"],
                "targetTable": meta["targetTable"], "uniqueKey": meta["uniqueKey"],
                "dupPolicy": meta["dupPolicy"],
                "dependsOn": deps, "dependsMet": deps_met,
                "recordCount": counts.get(code, 0),
                "lastBatch": latest.get(code),
                "columns": [{"key": c[0], "title": c[1], "required": c[2],
                             "example": c[3], "help": c[4]} for c in meta["columns"]],
            })
        return {"studentCount": counts["student-profile"], "domains": domains}
    finally:
        db.close()


def list_batches(domain: str | None = None, limit: int = 50) -> list[dict]:
    _require_db()
    from sqlalchemy import select
    from app.models import StudentImportBatch
    db = get_sessionmaker()()
    try:
        rows = db.scalars(select(StudentImportBatch).where(
            StudentImportBatch.tenant_id == _tid(),
            StudentImportBatch.remark.like(
                f"{_REMARK_PREFIX}{domain} %" if domain else f"{_REMARK_PREFIX}%"))
            .order_by(StudentImportBatch.id.desc()).limit(limit)).all()
        out = []
        for b in rows:
            dom = (b.remark or "").removeprefix(_REMARK_PREFIX).split(" ")[0]
            out.append({"batchNo": b.batch_no, "domain": dom,
                        "domainLabel": _DOMAINS.get(dom, {}).get("label", dom),
                        "status": b.status, "totalRows": b.total_rows,
                        "successRows": b.success_rows, "errorRows": b.error_rows,
                        "createdAt": b.created_at.isoformat(timespec="seconds") if b.created_at else None})
        return out
    finally:
        db.close()


def platform_overview() -> list[dict]:
    """平台运营：全部租户迁移进度（仅平台侧权限调用；只读聚合，不返回业务数据）。"""
    _require_db()
    from sqlalchemy import select
    from app.models import StudentImportBatch, Tenant
    db = get_sessionmaker()()
    try:
        tenants = {t.id: t for t in db.scalars(select(Tenant).where(Tenant.is_deleted.is_(False)))}
        stats: dict[int, dict] = {}
        for b in db.scalars(select(StudentImportBatch).where(
                StudentImportBatch.remark.like(f"{_REMARK_PREFIX}%")).order_by(StudentImportBatch.id.asc())):
            s = stats.setdefault(b.tenant_id, {"batches": 0, "successBatches": 0,
                                               "rows": 0, "domains": set(), "lastAt": None})
            dom = (b.remark or "").removeprefix(_REMARK_PREFIX).split(" ")[0]
            s["batches"] += 1
            if b.status == "SUCCESS":
                s["successBatches"] += 1
                s["rows"] += b.success_rows or 0
                s["domains"].add(dom)
            if b.created_at:
                s["lastAt"] = b.created_at.isoformat(timespec="seconds")
        out = []
        for tid, s in stats.items():
            t = tenants.get(tid)
            out.append({"tenantId": str(tid), "tenantName": (t.tenant_name if t else str(tid)),
                        "batches": s["batches"], "successBatches": s["successBatches"],
                        "importedRows": s["rows"], "domainsDone": sorted(s["domains"]),
                        "domainsTotal": len(_DOMAINS), "lastActivityAt": s["lastAt"]})
        out.sort(key=lambda x: x["lastActivityAt"] or "", reverse=True)
        return out
    finally:
        db.close()
