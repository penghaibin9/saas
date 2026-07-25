"""老系统数据迁移 P2 · 15 域（学工 A1-A10 + 教务 B6-B9/B11）。

设计依据：docs/03-业务模块设计/跨模块融合/13A-13B-历史数据导入与迁移设计.md §二/§三。
注册进 migration_import_service 同一管线（dry-run → 行级错误 → confirm 整批事务）。

与设计文档的已声明偏差（实现口径，均在对应域注释说明）：
- B7 培养方案：单 sheet 分组行（每行=方案信息+一门课程），替代双 sheet 模板——现有解析底座按首个
  工作表读行，双 sheet 需扩底座；分组行语义等价且错误定位更直接。
- B9 课表：周次用 起始周/结束周/单双周 三列，替代 "1,3,5-9" 复合语法——t_aa_schedule_item 本身
  只存 start_week/end_week/week_parity，复合语法落库前也须拆解为该三元组。
- A7 谈话：t_affairs_talk_record 无 teacher_key 列，教师匹配不上时在 topic 保留原文（"历史迁移·教师:X"）。
- A9 风险：source_ref_id 为整型列，无法存 "legacy-批次-行号" 合成键；SKIP 幂等改按
  (student, source=MANUAL, title) 判重。待办仅在责任人可解析到账号时生成（UnifiedTodo 需 assignee_id）。
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from app.core.field_crypto import encrypt_field


# ═══════════ 中文 → 枚举映射 ═══════════

GENDER_LIMIT_CN = {"男": "MALE", "男寝": "MALE", "女": "FEMALE", "女寝": "FEMALE",
                   "混合": "MIXED", "M": "MALE", "F": "FEMALE", "MIXED": "MIXED"}
CONTACT_TYPE_CN = {"监护人": ("GUARDIAN_PHONE", "监护人"), "父亲": ("GUARDIAN_PHONE", "父亲"),
                   "母亲": ("GUARDIAN_PHONE", "母亲"), "紧急联系人": ("EMERGENCY_PHONE", "紧急联系人")}
CADRE_POSITION_CN = {"班长": "MONITOR", "团支书": "LEAGUE_SECRETARY", "学习委员": "STUDY",
                     "生活委员": "LIFE", "体育委员": "SPORTS", "其他": "OTHER"}
LEAVE_TYPE_CN = {"病假": "SICK", "事假": "PERSONAL", "其他": "OTHER",
                 "SICK": "SICK", "PERSONAL": "PERSONAL", "OTHER": "OTHER"}
LEAVE_STATUS_CN = {"已批准": "APPROVED", "已驳回": "REJECTED", "已销假": "CLOSED", "已逾期": "OVERDUE",
                   "APPROVED": "APPROVED", "REJECTED": "REJECTED", "CLOSED": "CLOSED", "OVERDUE": "OVERDUE"}
AID_LEVEL_CN = {"特别困难": "SPECIAL", "困难": "DIFFICULT", "一般困难": "GENERAL"}
FUNDING_TYPE_CN = {"奖学金": "SCHOLARSHIP", "助学金": "GRANT", "勤工助学": "WORK_STUDY",
                   "助学贷款": "LOAN", "学费减免": "TUITION_REDUCTION",
                   "临时困难补助": "TEMPORARY_AID", "绿色通道": "GREEN_CHANNEL"}
DISC_TYPE_CN = {"警告": "WARNING", "严重警告": "SERIOUS_WARNING", "记过": "DEMERIT",
                "留校察看": "PROBATION", "开除": "EXPEL"}
TALK_TOPIC_CN = {"日常": "DAILY", "学业": "ACADEMIC", "心理": "MENTAL", "违纪": "DISCIPLINE",
                 "就业": "EMPLOYMENT", "实习": "INTERNSHIP", "困难帮扶": "AID_HELP", "宿舍异常": "DORM_ABNORMAL"}
RISK_LEVEL_CN = {"低": "LOW", "中": "MEDIUM", "高": "HIGH", "极高": "CRITICAL",
                 "LOW": "LOW", "MEDIUM": "MEDIUM", "HIGH": "HIGH", "CRITICAL": "CRITICAL"}
RISK_STATUS_CN = {"在管": "NEW", "已关闭": "CLOSED", "NEW": "NEW", "CLOSED": "CLOSED"}
COURSE_CATEGORY_CN = {"公共基础": "PUBLIC_BASIC", "学科基础": "DISCIPLINE_BASIC", "专业核心": "MAJOR_CORE",
                      "专业选修": "MAJOR_ELECTIVE", "集中实践": "PRACTICE"}
COURSE_NATURE_CN = {"必修": "REQUIRED", "选修": "ELECTIVE", "限选": "LIMITED_ELECTIVE", "公选": "PUBLIC_ELECTIVE"}
WEEK_PARITY_CN = {"全周": "ALL", "全": "ALL", "单周": "ODD", "单": "ODD", "双周": "EVEN", "双": "EVEN", "": "ALL"}
CONCLUSION_CN = {"毕业": "GRADUATED", "结业": "COMPLETED", "延毕": "DELAYED"}

_PHONE = re.compile(r"^\d{7,12}$")

MIGRATION_BATCH_NAME = "历史迁移批次"


def _mask_phone(v: str) -> str:
    v = v or ""
    return v[:3] + "****" + v[-4:] if len(v) >= 7 else "***"


# 域配置：columns=(key, 中文表头, 必填, 示例, 说明)
P2_DOMAINS: dict[str, dict] = {
    "affairs-family-contact": {
        "label": "家庭联系人", "order": 7, "dependsOn": ["student-profile"], "dupPolicy": "OVERWRITE",
        "targetTable": "t_student_contact（加密入库，出口恒脱敏）", "uniqueKey": "学号+联系人类型",
        "columns": [
            ("studentNo", "学号", True, "2023010001", ""),
            ("contactType", "联系人类型", True, "监护人", "监护人/父亲/母亲/紧急联系人"),
            ("contactName", "联系人姓名", True, "张建国", ""),
            ("phone", "联系电话", True, "13800001234", "手机 11 位；座机 7-12 位"),
            ("remark", "备注", False, "", ""),
        ],
    },
    "affairs-class-cadre": {
        "label": "班干部任免", "order": 8, "dependsOn": ["student-profile"], "dupPolicy": "SKIP",
        "targetTable": "t_affairs_class_cadre", "uniqueKey": "班级+学号+职务+学期",
        "columns": [
            ("className", "班级名称", True, "软件2301班", "须与系统班级名一致"),
            ("studentNo", "学号", True, "2023010001", ""),
            ("position", "职务", True, "班长", "班长/团支书/学习委员/生活委员/体育委员/其他"),
            ("termCode", "学期", True, "2024-2025-1", ""),
            ("appointedAt", "任职日期", True, "2024-09-10", ""),
            ("removedAt", "离任日期", False, "", "已离任才填"),
        ],
    },
    "affairs-dorm-building": {
        "label": "宿舍房源（楼/房/床）", "order": 9, "dependsOn": [], "dupPolicy": "OVERWRITE",
        "targetTable": "t_affairs_dorm_building/room/bed（覆盖不清占用）", "uniqueKey": "楼栋编码+房号",
        "columns": [
            ("buildingCode", "楼栋编码", True, "B01", ""),
            ("buildingName", "楼栋名称", True, "梅苑1栋", ""),
            ("genderLimit", "性别限制", True, "女", "男/女/混合"),
            ("managerTeacherKey", "宿管工号", False, "dorm001", ""),
            ("floorNo", "楼层", True, "3", ""),
            ("roomNo", "房号", True, "302", ""),
            ("capacity", "床位数", True, "4", "1-12，按数生成床位 1..N"),
            ("roomType", "房间类型", False, "四人间", ""),
        ],
    },
    "affairs-dorm-assign": {
        "label": "住宿分配", "order": 10, "dependsOn": ["student-profile", "affairs-dorm-building"],
        "dupPolicy": "ERROR", "targetTable": "t_affairs_dorm_bed + 回写 t_cs_dorm_record",
        "uniqueKey": "学号（一生一床）",
        "columns": [
            ("studentNo", "学号", True, "2023010001", ""),
            ("buildingCode", "楼栋编码", True, "B01", ""),
            ("roomNo", "房号", True, "302", ""),
            ("bedNo", "床号", True, "2", ""),
            ("occupiedAt", "入住日期", False, "2024-09-01", ""),
        ],
    },
    "affairs-leave-history": {
        "label": "请假历史", "order": 11, "dependsOn": ["student-profile"], "dupPolicy": "ERROR",
        "targetTable": "t_cs_leave（只进终态，零待办）", "uniqueKey": "学号+开始时间+请假类型",
        "columns": [
            ("studentNo", "学号", True, "2023010001", ""),
            ("leaveType", "请假类型", True, "病假", "病假/事假/其他"),
            ("startTime", "开始时间", True, "2025-03-02 08:00", ""),
            ("endTime", "结束时间", True, "2025-03-05 08:00", ""),
            ("days", "天数", False, "3", "缺省按起止计算"),
            ("reason", "原因", True, "流感发热就医", ""),
            ("finalStatus", "最终状态", True, "已销假", "已批准/已驳回/已销假/已逾期（过程态拒收）"),
            ("actualReturnAt", "实际返校时间", False, "2025-03-05 09:00", "已销假必填"),
        ],
    },
    "affairs-aid-history": {
        "label": "困难认定历史", "order": 12, "dependsOn": ["student-profile"], "dupPolicy": "ERROR",
        "targetTable": "t_affairs_aid_apply + t_affairs_aid_level_history（不含家庭经济明细）",
        "uniqueKey": "学号+学年",
        "columns": [
            ("studentNo", "学号", True, "2023010001", ""),
            ("yearCode", "学年", True, "2024-2025", "格式 YYYY-YYYY"),
            ("finalLevel", "认定等级", True, "困难", "特别困难/困难/一般困难"),
            ("identifiedAt", "认定日期", True, "2024-10-15", ""),
            ("remark", "备注", False, "", ""),
        ],
    },
    "affairs-funding-history": {
        "label": "奖助获得记录", "order": 13, "dependsOn": ["student-profile"], "dupPolicy": "ERROR",
        "targetTable": "t_affairs_funding_application（项目/批次自动预建）", "uniqueKey": "学号+项目名称+学年",
        "columns": [
            ("studentNo", "学号", True, "2023010001", ""),
            ("projectName", "项目名称", True, "国家奖学金", ""),
            ("projectType", "项目类型", True, "奖学金",
             "奖学金/助学金/勤工助学/助学贷款/学费减免/临时困难补助/绿色通道"),
            ("yearCode", "学年", True, "2024-2025", ""),
            ("amount", "金额", True, "8000", "大于 0"),
            ("resultAt", "获得日期", True, "2024-12-01", ""),
        ],
    },
    "affairs-discipline-history": {
        "label": "处分历史", "order": 14, "dependsOn": ["student-profile"], "dupPolicy": "ERROR",
        "targetTable": "t_affairs_discipline_case + 投影 t_cs_discipline", "uniqueKey": "学号+文号",
        "columns": [
            ("studentNo", "学号", True, "2023010001", ""),
            ("discType", "处分类型", True, "警告", "警告/严重警告/记过/留校察看/开除"),
            ("docNo", "文号", True, "校学字〔2024〕12号", ""),
            ("decideDate", "处分日期", True, "2024-05-20", ""),
            ("reason", "事由", True, "考试作弊", ""),
            ("removed", "是否已解除", True, "否", "是/否"),
            ("removedAt", "解除日期", False, "", "已解除必填且晚于处分日期"),
        ],
    },
    "affairs-talk-history": {
        "label": "谈心谈话历史", "order": 15, "dependsOn": ["student-profile"], "dupPolicy": "SKIP",
        "targetTable": "t_affairs_talk_record（直录 CLOSED）", "uniqueKey": "学号+谈话时间+主题类型",
        "columns": [
            ("studentNo", "学号", True, "2023010001", ""),
            ("teacherKey", "教师工号/姓名", True, "T0012", ""),
            ("topicType", "主题类型", True, "学业", "日常/学业/心理/违纪/就业/实习/困难帮扶/宿舍异常"),
            ("talkAt", "谈话时间", True, "2024-11-05 15:00", ""),
            ("content", "内容摘要", True, "期中多科不及格，约谈制定补习计划", "5-2000 字"),
            ("result", "结果", False, "", ""),
        ],
    },
    "affairs-risk-manual": {
        "label": "风险学生名单", "order": 16, "dependsOn": ["student-profile"], "dupPolicy": "SKIP",
        "targetTable": "t_affairs_risk_record（source=MANUAL）", "uniqueKey": "学号+风险描述",
        "columns": [
            ("studentNo", "学号", True, "2023010001", ""),
            ("riskLevel", "风险等级", True, "高", "低/中/高/极高"),
            ("description", "风险描述", True, "多门课程不及格且旷课频繁", "涉心理内容请改走心理渠道"),
            ("ownerKey", "责任人工号", False, "T0012", "在管状态建议填写"),
            ("riskStatus", "状态", True, "在管", "在管/已关闭"),
        ],
    },
    "aa-course": {
        "label": "课程库", "order": 17, "dependsOn": [], "dupPolicy": "OVERWRITE",
        "targetTable": "t_aa_course", "uniqueKey": "课程编码+版本",
        "columns": [
            ("courseCode", "课程编码", True, "C010203", ""),
            ("courseName", "课程名称", True, "数据库原理", ""),
            ("category", "类别", True, "专业核心", "公共基础/学科基础/专业核心/专业选修/集中实践"),
            ("nature", "性质", True, "必修", "必修/选修/限选/公选"),
            ("credit", "学分", True, "3.5", "0.5-20，步长 0.5"),
            ("hoursTheory", "理论学时", True, "48", ""),
            ("hoursPractice", "实践学时", True, "16", ""),
            ("examMode", "考核方式", False, "考试", "考试/考查"),
            ("version", "版本", False, "1", "缺省 1"),
        ],
    },
    "aa-program": {
        "label": "培养方案", "order": 18, "dependsOn": ["aa-course"], "dupPolicy": "ERROR",
        "targetTable": "t_aa_program/_course/_binding（分组行：每行=方案+一门课程）",
        "uniqueKey": "专业+年级+版本",
        "columns": [
            ("programName", "方案名称", True, "软件技术2024级培养方案", ""),
            ("majorName", "专业名称", True, "软件技术", "须与系统专业名一致"),
            ("gradeYear", "适用年级", True, "2024", ""),
            ("totalCredits", "总学分", True, "152", ""),
            ("courseCode", "课程编码", True, "C010203", "须已在课程库"),
            ("openTermNo", "开课学期", True, "3", "第 N 学期，1-10"),
            ("module", "课程模块", True, "专业", "公共/专业/实践…"),
            ("version", "版本", False, "1", "缺省 1；重导走新版本"),
        ],
    },
    "aa-teaching-task": {
        "label": "教学任务", "order": 19, "dependsOn": ["aa-term", "aa-course"], "dupPolicy": "ERROR",
        "targetTable": "t_aa_teaching_task（历史迁移批次自动预建）", "uniqueKey": "学期+课程+班级",
        "columns": [
            ("yearCode", "学年", True, "2024-2025", ""),
            ("termNo", "学期号", True, "1", ""),
            ("courseCode", "课程编码", True, "C010203", ""),
            ("className", "班级名称", True, "软件2301班", ""),
            ("teacherKey", "教师工号/姓名", True, "T0012", "重名请用工号"),
            ("expectedStudents", "预计人数", False, "45", ""),
            ("weeklyHours", "周学时", True, "4", "1-20"),
        ],
    },
    "aa-schedule": {
        "label": "课表", "order": 20, "dependsOn": ["aa-time-slot", "aa-teaching-task"], "dupPolicy": "ERROR",
        "targetTable": "t_aa_schedule_item（历史迁移课表批次 DRAFT，人工核对后发布）",
        "uniqueKey": "班级+星期+节次+周次",
        "columns": [
            ("yearCode", "学年", True, "2024-2025", ""),
            ("termNo", "学期号", True, "1", ""),
            ("courseCode", "课程编码", True, "C010203", "须已有对应教学任务"),
            ("className", "班级名称", True, "软件2301班", ""),
            ("weekday", "星期", True, "3", "1-7"),
            ("slotNo", "节次", True, "2", "须已在作息节次"),
            ("startWeek", "起始周", True, "1", ""),
            ("endWeek", "结束周", True, "16", ""),
            ("weekParity", "单双周", False, "全周", "全周/单周/双周"),
            ("classroom", "教室", False, "实训楼301", "自由文本"),
        ],
    },
    "aa-graduation-history": {
        "label": "历届毕业结论", "order": 21, "dependsOn": ["student-profile"], "dupPolicy": "ERROR",
        "targetTable": "t_aa_graduation_audit_result（ARCHIVED）+ StageEvent", "uniqueKey": "毕业年份+学号",
        "columns": [
            ("studentNo", "学号", True, "2020010001", ""),
            ("graduateYear", "毕业年份", True, "2023", ""),
            ("conclusion", "结论", True, "毕业", "毕业/结业/延毕"),
            ("concludedAt", "结论日期", True, "2023-06-30", ""),
            ("remark", "备注", False, "", ""),
        ],
    },
}


# ═══════════ 公共 helpers（由 migration_import_service 注入 _tid/_err/_parse_date 等） ═══════════

def _find_teacher(db, tid, key):
    """按 登录名→精确姓名 匹配教师账号；返回 (user 或 None, 歧义?)。"""
    from sqlalchemy import select
    from app.models import User
    if not key:
        return None, False
    u = db.scalars(select(User).where(User.tenant_id == tid, User.login_name == key,
                                      User.is_deleted.is_(False))).all()
    if len(u) == 1:
        return u[0], False
    hits = db.scalars(select(User).where(User.tenant_id == tid, User.real_name == key,
                                         User.user_type != "STUDENT",
                                         User.is_deleted.is_(False))).all()
    if len(hits) > 1:
        return None, True
    return (hits[0] if hits else None), False


def _class_map(db, tid):
    from sqlalchemy import select
    from app.models import SchoolClass
    return {c.class_name: c for c in db.scalars(select(SchoolClass).where(
        SchoolClass.tenant_id == tid, SchoolClass.is_deleted.is_(False)))}


def _ensure_cs_student(db, tid, profile):
    """在校服务台账行（t_cs_service_student）：缺失则按主档补建，返回 cs_student_id。"""
    from sqlalchemy import select
    from app.models import CsServiceStudent
    row = db.scalars(select(CsServiceStudent).where(
        CsServiceStudent.tenant_id == tid, CsServiceStudent.student_no == profile.student_no,
        CsServiceStudent.is_deleted.is_(False))).first()
    if row:
        return row.id
    row = CsServiceStudent(tenant_id=tid, student_no=profile.student_no, student_id=profile.id,
                           name=profile.real_name, gender=profile.gender, grade=profile.grade)
    db.add(row)
    db.flush()
    return row.id


# ═══════════ 校验/落库（base=migration_import_service，运行期引用避免循环导入） ═══════════

def _base():
    from app.services import migration_import_service as base
    return base


# ── A8 家庭联系人 ──

def validate_family_contact(db, meta, rows):
    b = _base()
    students = b._student_map(db)
    ok, errors, seen = [], [], set()
    for i, r in b._rows_iter(meta, rows):
        if not b._check_required(meta, r, i, errors):
            continue
        ct = CONTACT_TYPE_CN.get(r["contactType"])
        if not ct:
            errors.append(b._err(i, "contactType", "ENUM_INVALID", r["contactType"],
                                 "联系人类型须为：监护人/父亲/母亲/紧急联系人"))
            continue
        s = students.get(r["studentNo"])
        if not s:
            errors.append(b._err(i, "studentNo", "REF_NOT_FOUND", r["studentNo"],
                                 f"学号 {r['studentNo']} 不在学生主档"))
            continue
        phone = r["phone"].replace(" ", "").replace("-", "")
        if not _PHONE.match(phone):
            errors.append(b._err(i, "phone", "FORMAT_INVALID", _mask_phone(phone),
                                 "联系电话须为 7-12 位数字（手机 11 位）"))
            continue
        key = (r["studentNo"], r["contactType"])
        if key in seen:
            errors.append(b._err(i, "contactType", "DUP_IN_FILE", r["contactType"],
                                 f"学号 {r['studentNo']} 同类型联系人在文件内重复"))
            continue
        seen.add(key)
        ok.append({"studentId": s.id, "contactType": ct[0], "relation": ct[1],
                   "contactName": r["contactName"], "phone": phone, "remark": r["remark"] or None})
    return ok, errors, 0


def mask_family_contact_preview(row):
    return {**row, "phone": _mask_phone(row.get("phone") or "")}


def persist_family_contact(db, rows):
    from sqlalchemy import select
    from app.models import StudentContact
    b = _base()
    tid = b._tid()
    created = updated = 0
    for r in rows:
        hit = db.scalars(select(StudentContact).where(
            StudentContact.tenant_id == tid, StudentContact.student_id == r["studentId"],
            StudentContact.contact_type == r["contactType"],
            StudentContact.remark == r["relation"],
            StudentContact.is_deleted.is_(False))).first()
        if hit:
            # OVERWRITE：联系方式以最新导入为准。必须经 encrypt_field 落密文列——
            # 此前直接写 r["phone"]，明文入库，出口脱敏只是把明文遮住，掩盖了裸存问题。
            hit.contact_value_encrypted = encrypt_field(r["phone"])
            hit.contact_name = r["contactName"]
            hit.version = (hit.version or 0) + 1
            updated += 1
        else:
            db.add(StudentContact(tenant_id=tid, student_id=r["studentId"], contact_type=r["contactType"],
                                  contact_value_encrypted=encrypt_field(r["phone"]),
                                  contact_name=r["contactName"],
                                  remark=r["relation"], verified_status="UNVERIFIED"))
            created += 1
    return {"created": created, "updated": updated}


# ── A10 班干部 ──

def validate_class_cadre(db, meta, rows):
    b = _base()
    from sqlalchemy import select
    from app.models import AffairsClassCadre
    students = b._student_map(db)
    classes = _class_map(db, b._tid())
    existing = {(c.class_id, c.student_id, c.position, c.term_code or "")
                for c in db.scalars(select(AffairsClassCadre).where(
                    AffairsClassCadre.tenant_id == b._tid(), AffairsClassCadre.is_deleted.is_(False)))}
    ok, errors, seen, skipped = [], [], set(), 0
    for i, r in b._rows_iter(meta, rows):
        if not b._check_required(meta, r, i, errors):
            continue
        pos = CADRE_POSITION_CN.get(r["position"])
        if not pos:
            errors.append(b._err(i, "position", "ENUM_INVALID", r["position"],
                                 "职务须为：班长/团支书/学习委员/生活委员/体育委员/其他"))
            continue
        cls = classes.get(r["className"])
        if not cls:
            cand = next((n for n in classes if r["className"][:4] and r["className"][:4] in n), None)
            errors.append(b._err(i, "className", "REF_NOT_FOUND", r["className"],
                                 f"班级「{r['className']}」不存在" + (f"，请核对为「{cand}」" if cand else "")))
            continue
        s = students.get(r["studentNo"])
        if not s:
            errors.append(b._err(i, "studentNo", "REF_NOT_FOUND", r["studentNo"],
                                 f"学号 {r['studentNo']} 不在学生主档"))
            continue
        appointed = b._parse_date(r["appointedAt"])
        if not appointed:
            errors.append(b._err(i, "appointedAt", "FORMAT_INVALID", r["appointedAt"], "任职日期无法解析"))
            continue
        key = (cls.id, s.id, pos, r["termCode"])
        if key in existing or key in seen:
            skipped += 1
            continue
        seen.add(key)
        removed = b._parse_date(r["removedAt"]) if r["removedAt"] else None
        ok.append({"classId": cls.id, "studentId": s.id, "position": pos, "termCode": r["termCode"],
                   "appointedAt": appointed, "removedAt": removed,
                   "status": "REMOVED" if removed else "ACTIVE"})
    return ok, errors, skipped


def persist_class_cadre(db, rows):
    from app.models import AffairsClassCadre
    b = _base()
    for r in rows:
        db.add(AffairsClassCadre(tenant_id=b._tid(), class_id=r["classId"], student_id=r["studentId"],
                                 position=r["position"], term_code=r["termCode"],
                                 appointed_at=r["appointedAt"], removed_at=r["removedAt"],
                                 status=r["status"]))
    return {"created": len(rows)}


# ── A1 宿舍房源 ──

def validate_dorm_building(db, meta, rows):
    b = _base()
    from sqlalchemy import select
    from app.models import DormBed, DormBuilding, DormRoom
    tid = b._tid()
    buildings = {x.building_code: x for x in db.scalars(select(DormBuilding).where(
        DormBuilding.tenant_id == tid, DormBuilding.is_deleted.is_(False))) if x.building_code}
    rooms = {}
    for room in db.scalars(select(DormRoom).where(DormRoom.tenant_id == tid, DormRoom.is_deleted.is_(False))):
        rooms[(room.building_id, room.room_no)] = room
    occupied = {}
    for bed in db.scalars(select(DormBed).where(DormBed.tenant_id == tid, DormBed.status == "OCCUPIED",
                                                DormBed.is_deleted.is_(False))):
        occupied[bed.room_id] = occupied.get(bed.room_id, 0) + 1
    ok, errors, seen, gender_by_building = [], [], set(), {}
    for i, r in b._rows_iter(meta, rows):
        if not b._check_required(meta, r, i, errors):
            continue
        gl = GENDER_LIMIT_CN.get(r["genderLimit"])
        if not gl:
            errors.append(b._err(i, "genderLimit", "ENUM_INVALID", r["genderLimit"], "性别限制须为：男/女/混合"))
            continue
        prev_gl = gender_by_building.setdefault(r["buildingCode"], gl)
        if prev_gl != gl:
            errors.append(b._err(i, "genderLimit", "VALIDATION_ERROR", r["genderLimit"],
                                 f"楼栋 {r['buildingCode']} 在文件内性别限制前后不一致"))
            continue
        try:
            capacity, floor_no = int(float(r["capacity"])), int(float(r["floorNo"]))
        except ValueError:
            errors.append(b._err(i, "capacity", "FORMAT_INVALID", f"{r['capacity']}/{r['floorNo']}",
                                 "楼层/床位数须为数字"))
            continue
        if not 1 <= capacity <= 12:
            errors.append(b._err(i, "capacity", "RANGE_INVALID", r["capacity"], "床位数须为 1-12"))
            continue
        key = (r["buildingCode"], r["roomNo"])
        if key in seen:
            errors.append(b._err(i, "roomNo", "DUP_IN_FILE", f"{key[0]}-{key[1]}", "楼栋+房号在文件内重复"))
            continue
        seen.add(key)
        bld = buildings.get(r["buildingCode"])
        room = rooms.get((bld.id, r["roomNo"])) if bld else None
        occ = occupied.get(room.id, 0) if room else 0
        if occ > capacity:
            errors.append(b._err(i, "capacity", "BED_OCCUPIED_SHRINK", r["capacity"],
                                 f"{key[0]}-{key[1]} 现有 {occ} 个已占用床位，容量不能缩为 {capacity}"))
            continue
        ok.append({"buildingCode": r["buildingCode"], "buildingName": r["buildingName"],
                   "genderLimit": gl, "managerTeacherKey": r["managerTeacherKey"] or None,
                   "floorNo": floor_no, "roomNo": r["roomNo"], "capacity": capacity,
                   "roomType": r["roomType"] or None})
    return ok, errors, 0


def persist_dorm_building(db, rows):
    from sqlalchemy import select
    from app.models import DormBed, DormBuilding, DormRoom
    b = _base()
    tid = b._tid()
    created = updated = 0
    for r in rows:
        bld = db.scalars(select(DormBuilding).where(
            DormBuilding.tenant_id == tid, DormBuilding.building_code == r["buildingCode"],
            DormBuilding.is_deleted.is_(False))).first()
        if not bld:
            bld = DormBuilding(tenant_id=tid, building_code=r["buildingCode"],
                               building_name=r["buildingName"], gender_limit=r["genderLimit"],
                               manager_teacher_key=r["managerTeacherKey"])
            db.add(bld)
            db.flush()
        else:
            bld.building_name, bld.gender_limit = r["buildingName"], r["genderLimit"]
            bld.manager_teacher_key = r["managerTeacherKey"] or bld.manager_teacher_key
        room = db.scalars(select(DormRoom).where(
            DormRoom.tenant_id == tid, DormRoom.building_id == bld.id,
            DormRoom.room_no == r["roomNo"], DormRoom.is_deleted.is_(False))).first()
        if not room:
            room = DormRoom(tenant_id=tid, building_id=bld.id, floor_no=r["floorNo"],
                            room_no=r["roomNo"], capacity=r["capacity"], room_type=r["roomType"])
            db.add(room)
            db.flush()
            created += 1
        else:
            room.floor_no, room.capacity, room.room_type = r["floorNo"], r["capacity"], r["roomType"]
            room.version = (room.version or 0) + 1
            updated += 1
        beds = {x.bed_no: x for x in db.scalars(select(DormBed).where(
            DormBed.tenant_id == tid, DormBed.room_id == room.id, DormBed.is_deleted.is_(False)))}
        for n in range(1, r["capacity"] + 1):
            if str(n) not in beds:
                db.add(DormBed(tenant_id=tid, building_id=bld.id, room_id=room.id,
                               bed_no=str(n), status="VACANT"))
        for bed_no, bed in beds.items():  # 容量缩减：多余空床锁定（不删、不清占用）
            if bed_no.isdigit() and int(bed_no) > r["capacity"] and bed.status == "VACANT":
                bed.status = "LOCKED"
    return {"created": created, "updated": updated}


# ── A2 住宿分配 ──

def validate_dorm_assign(db, meta, rows):
    b = _base()
    from sqlalchemy import select
    from app.models import DormBed, DormBuilding, DormRoom
    tid = b._tid()
    students = b._student_map(db)
    buildings = {x.building_code: x for x in db.scalars(select(DormBuilding).where(
        DormBuilding.tenant_id == tid, DormBuilding.is_deleted.is_(False))) if x.building_code}
    rooms = {(x.building_id, x.room_no): x for x in db.scalars(select(DormRoom).where(
        DormRoom.tenant_id == tid, DormRoom.is_deleted.is_(False)))}
    beds = {(x.room_id, x.bed_no): x for x in db.scalars(select(DormBed).where(
        DormBed.tenant_id == tid, DormBed.is_deleted.is_(False)))}
    occupied_students = {x.student_id for x in beds.values() if x.student_id}
    ok, errors, seen_students, seen_beds = [], [], set(), set()
    for i, r in b._rows_iter(meta, rows):
        if not b._check_required(meta, r, i, errors):
            continue
        s = students.get(r["studentNo"])
        if not s:
            errors.append(b._err(i, "studentNo", "REF_NOT_FOUND", r["studentNo"],
                                 f"学号 {r['studentNo']} 不在学生主档"))
            continue
        if s.student_status in ("WITHDRAWN", "GRADUATED", "TRANSFER_SCHOOL"):
            errors.append(b._err(i, "studentNo", "VALIDATION_ERROR", r["studentNo"],
                                 f"学生学籍状态为 {s.student_status}，不能分配床位"))
            continue
        bld = buildings.get(r["buildingCode"])
        room = rooms.get((bld.id, r["roomNo"])) if bld else None
        bed = beds.get((room.id, r["bedNo"])) if room else None
        loc = f"{r['buildingCode']}-{r['roomNo']}-{r['bedNo']}"
        if not bed:
            errors.append(b._err(i, "bedNo", "REF_NOT_FOUND", loc, f"床位 {loc} 不存在（先导宿舍房源）"))
            continue
        if bed.status != "VACANT" or (room.id, r["bedNo"]) in seen_beds:
            errors.append(b._err(i, "bedNo", "BED_OCCUPIED", loc, f"床位 {loc} 已被占用或在文件内重复分配"))
            continue
        if s.id in occupied_students or s.id in seen_students:
            errors.append(b._err(i, "studentNo", "DUP_IN_DB", r["studentNo"],
                                 f"学生 {r['studentNo']} 已有床位（调宿走业务流程不走导入）"))
            continue
        if bld.gender_limit in ("MALE", "FEMALE") and s.gender in ("男", "女"):
            want = "男" if bld.gender_limit == "MALE" else "女"
            if s.gender != want:
                errors.append(b._err(i, "buildingCode", "VALIDATION_ERROR", loc,
                                     f"学生性别({s.gender})与楼栋限制({want}寝)不符"))
                continue
        seen_students.add(s.id)
        seen_beds.add((room.id, r["bedNo"]))
        ok.append({"studentId": s.id, "studentNo": r["studentNo"], "bedId": bed.id,
                   "building": bld.building_name, "room": r["roomNo"], "bedNo": r["bedNo"],
                   "occupiedAt": b._parse_date(r["occupiedAt"]) or datetime.utcnow()})
    return ok, errors, 0


def persist_dorm_assign(db, rows):
    from app.models import CsDormRecord, DormBed, StudentProfile
    b = _base()
    tid = b._tid()
    for r in rows:
        profile = db.get(StudentProfile, r["studentId"])
        cs_id = _ensure_cs_student(db, tid, profile)
        rec = CsDormRecord(tenant_id=tid, cs_student_id=cs_id, building=r["building"],
                           room=r["room"], bed=r["bedNo"], checkin_date=r["occupiedAt"], status="IN")
        db.add(rec)
        db.flush()
        bed = db.get(DormBed, r["bedId"])
        bed.student_id, bed.status = r["studentId"], "OCCUPIED"
        bed.occupied_at, bed.cs_dorm_record_id = r["occupiedAt"], rec.id
    return {"created": len(rows)}


# ── A3 请假历史 ──

def validate_leave_history(db, meta, rows):
    b = _base()
    from sqlalchemy import select
    from app.models import CsLeave
    students = b._student_map(db)
    existing = {(x.student_id, x.start_time, x.leave_type)
                for x in db.scalars(select(CsLeave).where(
                    CsLeave.tenant_id == b._tid(), CsLeave.student_id.isnot(None),
                    CsLeave.is_deleted.is_(False)))}
    ok, errors, seen = [], [], set()
    for i, r in b._rows_iter(meta, rows):
        if not b._check_required(meta, r, i, errors):
            continue
        lt = LEAVE_TYPE_CN.get(r["leaveType"])
        st = LEAVE_STATUS_CN.get(r["finalStatus"])
        if not lt or not st:
            errors.append(b._err(i, "leaveType" if not lt else "finalStatus", "ENUM_INVALID",
                                 r["leaveType"] if not lt else r["finalStatus"],
                                 "请假类型须为 病假/事假/其他；最终状态须为 已批准/已驳回/已销假/已逾期"))
            continue
        s = students.get(r["studentNo"])
        if not s:
            errors.append(b._err(i, "studentNo", "REF_NOT_FOUND", r["studentNo"],
                                 f"学号 {r['studentNo']} 不在学生主档"))
            continue
        start, end = b._parse_date(r["startTime"]), b._parse_date(r["endTime"])
        if not start or not end or end <= start:
            errors.append(b._err(i, "startTime", "RANGE_INVALID", f"{r['startTime']}~{r['endTime']}",
                                 "起止时间无法解析或结束不晚于开始"))
            continue
        ret = b._parse_date(r["actualReturnAt"]) if r["actualReturnAt"] else None
        if st == "CLOSED" and not ret:
            errors.append(b._err(i, "actualReturnAt", "REQUIRED_MISSING", "", "已销假必须填写实际返校时间"))
            continue
        key = (s.id, start, lt)
        if key in existing or key in seen:
            errors.append(b._err(i, "startTime", "DUP_IN_DB" if key in existing else "DUP_IN_FILE",
                                 r["startTime"], "学号+开始时间+请假类型已存在"))
            continue
        seen.add(key)
        try:
            days = float(r["days"]) if r["days"] else round((end - start).total_seconds() / 86400, 1)
        except ValueError:
            days = round((end - start).total_seconds() / 86400, 1)
        ok.append({"studentId": s.id, "leaveType": lt, "start": start, "end": end, "days": days,
                   "reason": r["reason"], "status": st, "actualReturnAt": ret})
    return ok, errors, 0


def persist_leave_history(db, rows):
    from app.models import CsLeave, StudentProfile
    b = _base()
    tid = b._tid()
    for r in rows:
        profile = db.get(StudentProfile, r["studentId"])
        cs_id = _ensure_cs_student(db, tid, profile)
        db.add(CsLeave(tenant_id=tid, cs_student_id=cs_id, student_id=r["studentId"],
                       leave_type=r["leaveType"], start_time=r["start"], end_time=r["end"],
                       days=r["days"], duration=f"{r['days']}天", reason=r["reason"],
                       status=r["status"], affairs_status=r["status"],
                       apply_time=r["start"], actual_return_at=r["actualReturnAt"]))
    return {"created": len(rows)}


# ── A4 困难认定历史 ──

def _get_or_create_year_batch(db, tid, model, year_code, **extra):
    from sqlalchemy import select
    hit = db.scalars(select(model).where(model.tenant_id == tid, model.year_code == year_code,
                                         model.batch_name == f"{MIGRATION_BATCH_NAME}-{year_code}",
                                         model.is_deleted.is_(False))).first()
    if hit:
        return hit
    hit = model(tenant_id=tid, batch_name=f"{MIGRATION_BATCH_NAME}-{year_code}",
                year_code=year_code, status="ARCHIVED", **extra)
    db.add(hit)
    db.flush()
    return hit


def validate_aid_history(db, meta, rows):
    b = _base()
    from sqlalchemy import select
    from app.models import AidLevelHistory
    students = b._student_map(db)
    existing = {(x.student_id, x.year_code) for x in db.scalars(select(AidLevelHistory).where(
        AidLevelHistory.tenant_id == b._tid(), AidLevelHistory.change_type == "IDENTIFY"))}
    ok, errors, seen = [], [], set()
    for i, r in b._rows_iter(meta, rows):
        if not b._check_required(meta, r, i, errors):
            continue
        level = AID_LEVEL_CN.get(r["finalLevel"])
        if not level:
            errors.append(b._err(i, "finalLevel", "ENUM_INVALID", r["finalLevel"],
                                 "认定等级须为：特别困难/困难/一般困难"))
            continue
        if not re.match(r"^\d{4}-\d{4}$", r["yearCode"]):
            errors.append(b._err(i, "yearCode", "FORMAT_INVALID", r["yearCode"], "学年格式须为 YYYY-YYYY"))
            continue
        s = students.get(r["studentNo"])
        if not s:
            errors.append(b._err(i, "studentNo", "REF_NOT_FOUND", r["studentNo"],
                                 f"学号 {r['studentNo']} 不在学生主档"))
            continue
        at = b._parse_date(r["identifiedAt"])
        if not at:
            errors.append(b._err(i, "identifiedAt", "FORMAT_INVALID", r["identifiedAt"], "认定日期无法解析"))
            continue
        key = (s.id, r["yearCode"])
        if key in existing or key in seen:
            errors.append(b._err(i, "yearCode", "DUP_IN_DB" if key in existing else "DUP_IN_FILE",
                                 r["yearCode"], f"学生 {r['studentNo']} 学年 {r['yearCode']} 已有认定记录"))
            continue
        seen.add(key)
        ok.append({"studentId": s.id, "yearCode": r["yearCode"], "level": level,
                   "identifiedAt": at, "remark": r["remark"] or None})
    return ok, errors, 0


def persist_aid_history(db, rows):
    from app.models import AidApply, AidBatch, AidLevelHistory
    b = _base()
    tid = b._tid()
    for r in rows:
        batch = _get_or_create_year_batch(db, tid, AidBatch, r["yearCode"])
        apply = AidApply(tenant_id=tid, batch_id=batch.id, student_id=r["studentId"],
                         final_level=r["level"], status="ARCHIVED", result_at=r["identifiedAt"],
                         statement=r["remark"])
        db.add(apply)
        db.flush()
        db.add(AidLevelHistory(tenant_id=tid, student_id=r["studentId"], to_level=r["level"],
                               change_type="IDENTIFY", apply_id=apply.id, batch_id=batch.id,
                               year_code=r["yearCode"], effective_at=r["identifiedAt"]))
    return {"created": len(rows)}


# ── A5 奖助获得记录 ──

def validate_funding_history(db, meta, rows):
    b = _base()
    from sqlalchemy import select
    from app.models import FundingApplication, FundingBatch, FundingProject
    tid = b._tid()
    students = b._student_map(db)
    projects = {p.project_name: p for p in db.scalars(select(FundingProject).where(
        FundingProject.tenant_id == tid, FundingProject.is_deleted.is_(False)))}
    batch_year = {x.id: x.year_code for x in db.scalars(select(FundingBatch).where(
        FundingBatch.tenant_id == tid, FundingBatch.is_deleted.is_(False)))}
    batch_project = {x.id: x.project_id for x in db.scalars(select(FundingBatch).where(
        FundingBatch.tenant_id == tid, FundingBatch.is_deleted.is_(False)))}
    project_name_by_id = {p.id: p.project_name for p in projects.values()}
    existing = set()
    for a in db.scalars(select(FundingApplication).where(
            FundingApplication.tenant_id == tid, FundingApplication.is_deleted.is_(False))):
        pname = project_name_by_id.get(batch_project.get(a.batch_id))
        if pname:
            existing.add((a.student_id, pname, batch_year.get(a.batch_id, "")))
    ok, errors, seen = [], [], set()
    for i, r in b._rows_iter(meta, rows):
        if not b._check_required(meta, r, i, errors):
            continue
        ptype = FUNDING_TYPE_CN.get(r["projectType"])
        if not ptype:
            errors.append(b._err(i, "projectType", "ENUM_INVALID", r["projectType"],
                                 f"项目类型须为：{'/'.join(FUNDING_TYPE_CN)}"))
            continue
        s = students.get(r["studentNo"])
        if not s:
            errors.append(b._err(i, "studentNo", "REF_NOT_FOUND", r["studentNo"],
                                 f"学号 {r['studentNo']} 不在学生主档"))
            continue
        try:
            amount = float(r["amount"])
        except ValueError:
            amount = -1
        if not 0 < amount <= 99999999.99:
            errors.append(b._err(i, "amount", "RANGE_INVALID", r["amount"], "金额必须大于 0"))
            continue
        at = b._parse_date(r["resultAt"])
        if not at or at > datetime.utcnow():
            errors.append(b._err(i, "resultAt", "RANGE_INVALID", r["resultAt"],
                                 "获得日期无法解析或晚于今天"))
            continue
        key = (s.id, r["projectName"], r["yearCode"])
        if key in existing or key in seen:
            errors.append(b._err(i, "projectName", "DUP_IN_DB" if key in existing else "DUP_IN_FILE",
                                 r["projectName"], f"学生 {r['studentNo']} 该项目该学年已有获得记录"))
            continue
        seen.add(key)
        ok.append({"studentId": s.id, "projectName": r["projectName"], "projectType": ptype,
                   "yearCode": r["yearCode"], "amount": amount, "resultAt": at})
    return ok, errors, 0


def persist_funding_history(db, rows):
    from sqlalchemy import select
    from app.models import FundingApplication, FundingBatch, FundingProject, StudentStageEvent
    b = _base()
    tid = b._tid()
    for r in rows:
        project = db.scalars(select(FundingProject).where(
            FundingProject.tenant_id == tid, FundingProject.project_name == r["projectName"],
            FundingProject.is_deleted.is_(False))).first()
        if not project:
            project = FundingProject(tenant_id=tid, project_name=r["projectName"],
                                     project_type=r["projectType"], status="ENABLED")
            db.add(project)
            db.flush()
        batch = db.scalars(select(FundingBatch).where(
            FundingBatch.tenant_id == tid, FundingBatch.project_id == project.id,
            FundingBatch.year_code == r["yearCode"], FundingBatch.is_deleted.is_(False))).first()
        if not batch:
            batch = FundingBatch(tenant_id=tid, project_id=project.id, project_type=r["projectType"],
                                 year_code=r["yearCode"], status="ARCHIVED")
            db.add(batch)
            db.flush()
        db.add(FundingApplication(tenant_id=tid, batch_id=batch.id, student_id=r["studentId"],
                                  project_type=r["projectType"], amount=r["amount"],
                                  status="GRANTED", result_at=r["resultAt"],
                                  check_snapshot_json=json.dumps({"legacy": True})))
        db.add(StudentStageEvent(tenant_id=tid, student_id=r["studentId"],
                                 from_stage=None, to_stage="FUNDING_GRANTED",
                                 reason=f"获得{r['projectName']}（{r['yearCode']}，历史迁移）",
                                 source_module="student-affairs"))
    return {"created": len(rows)}


# ── A6 处分历史 ──

def validate_discipline_history(db, meta, rows):
    b = _base()
    from sqlalchemy import select
    from app.models import DisciplineCase
    students = b._student_map(db)
    existing = {(x.student_id, x.doc_no) for x in db.scalars(select(DisciplineCase).where(
        DisciplineCase.tenant_id == b._tid(), DisciplineCase.is_deleted.is_(False)))}
    ok, errors, seen = [], [], set()
    for i, r in b._rows_iter(meta, rows):
        if not b._check_required(meta, r, i, errors):
            continue
        dt = DISC_TYPE_CN.get(r["discType"])
        if not dt:
            errors.append(b._err(i, "discType", "ENUM_INVALID", r["discType"],
                                 "处分类型须为：警告/严重警告/记过/留校察看/开除"))
            continue
        s = students.get(r["studentNo"])
        if not s:
            errors.append(b._err(i, "studentNo", "REF_NOT_FOUND", r["studentNo"],
                                 f"学号 {r['studentNo']} 不在学生主档"))
            continue
        decide = b._parse_date(r["decideDate"])
        if not decide:
            errors.append(b._err(i, "decideDate", "FORMAT_INVALID", r["decideDate"], "处分日期无法解析"))
            continue
        removed = r["removed"] in ("是", "true", "True", "1")
        removed_at = b._parse_date(r["removedAt"]) if r["removedAt"] else None
        if removed and (not removed_at or removed_at <= decide):
            errors.append(b._err(i, "removedAt", "REQUIRED_MISSING", r["removedAt"],
                                 "已解除的处分必须填写解除日期且晚于处分日期"))
            continue
        key = (s.id, r["docNo"])
        if key in existing or key in seen:
            errors.append(b._err(i, "docNo", "DUP_IN_DB" if key in existing else "DUP_IN_FILE",
                                 r["docNo"], f"学生 {r['studentNo']} 文号 {r['docNo']} 已存在"))
            continue
        seen.add(key)
        ok.append({"studentId": s.id, "discType": dt, "docNo": r["docNo"], "decideDate": decide,
                   "reason": r["reason"], "removed": removed, "removedAt": removed_at})
    return ok, errors, 0


def persist_discipline_history(db, rows):
    from app.models import CsDiscipline, DisciplineCase, StudentProfile
    b = _base()
    tid = b._tid()
    for r in rows:
        profile = db.get(StudentProfile, r["studentId"])
        cs_id = _ensure_cs_student(db, tid, profile)
        proj = CsDiscipline(tenant_id=tid, cs_student_id=cs_id, disc_type=r["discType"],
                            reason=r["reason"], decide_date=r["decideDate"], doc_no=r["docNo"],
                            status="REMOVED" if r["removed"] else "EFFECTIVE",
                            revoke_date=r["removedAt"],
                            record_status="REMOVED" if r["removed"] else "ACTIVE")
        db.add(proj)
        db.flush()
        case = DisciplineCase(tenant_id=tid, student_id=r["studentId"], disc_type=r["discType"],
                              reason=r["reason"], doc_no=r["docNo"], decide_date=r["decideDate"],
                              effective_at=r["decideDate"], removed_at=r["removedAt"],
                              status="REMOVED" if r["removed"] else "EFFECTIVE",
                              cs_discipline_id=proj.id)
        db.add(case)
        db.flush()
        proj.source_case_id = case.id
    return {"created": len(rows)}


# ── A7 谈心谈话历史 ──

def validate_talk_history(db, meta, rows):
    b = _base()
    from sqlalchemy import select
    from app.models import TalkRecord
    tid = b._tid()
    students = b._student_map(db)
    existing = {(x.student_id, x.talk_at, x.topic_type) for x in db.scalars(select(TalkRecord).where(
        TalkRecord.tenant_id == tid, TalkRecord.is_deleted.is_(False)))}
    ok, errors, seen, skipped = [], [], set(), 0
    for i, r in b._rows_iter(meta, rows):
        if not b._check_required(meta, r, i, errors):
            continue
        topic = TALK_TOPIC_CN.get(r["topicType"])
        if not topic:
            errors.append(b._err(i, "topicType", "ENUM_INVALID", r["topicType"],
                                 f"主题类型须为 8 类编码之一：{'/'.join(TALK_TOPIC_CN)}"))
            continue
        s = students.get(r["studentNo"])
        if not s:
            errors.append(b._err(i, "studentNo", "REF_NOT_FOUND", r["studentNo"],
                                 f"学号 {r['studentNo']} 不在学生主档"))
            continue
        at = b._parse_date(r["talkAt"])
        if not at or at > datetime.utcnow():
            errors.append(b._err(i, "talkAt", "RANGE_INVALID", r["talkAt"], "谈话时间无法解析或晚于今天"))
            continue
        if not 5 <= len(r["content"]) <= 2000:
            errors.append(b._err(i, "content", "RANGE_INVALID", r["content"][:20], "内容摘要须为 5-2000 字"))
            continue
        key = (s.id, at, topic)
        if key in existing or key in seen:
            skipped += 1
            continue
        seen.add(key)
        teacher, ambiguous = _find_teacher(db, tid, r["teacherKey"])
        if ambiguous:
            errors.append(b._err(i, "teacherKey", "REF_AMBIGUOUS", r["teacherKey"],
                                 f"教师「{r['teacherKey']}」在租户内匹配到多个账号，请改用工号"))
            continue
        ok.append({"studentId": s.id, "teacherId": teacher.id if teacher else None,
                   "teacherKey": r["teacherKey"], "topicType": topic, "talkAt": at,
                   "content": r["content"], "result": r["result"] or None})
    return ok, errors, skipped


def mask_talk_preview(row):
    if row.get("topicType") == "MENTAL":  # 心理类主题预览打码（草案 §3.7）
        return {**row, "content": "（心理类内容，仅授权角色可见）"}
    return row


def persist_talk_history(db, rows):
    from app.models import TalkRecord
    b = _base()
    for r in rows:
        topic_note = "历史迁移" if r["teacherId"] else f"历史迁移·教师:{r['teacherKey']}"
        db.add(TalkRecord(tenant_id=b._tid(), student_id=r["studentId"], teacher_id=r["teacherId"],
                          topic_type=r["topicType"], topic=topic_note, talk_at=r["talkAt"],
                          content=r["content"], result=r["result"], status="CLOSED"))
    return {"created": len(rows)}


# ── A9 风险学生名单 ──

def validate_risk_manual(db, meta, rows):
    b = _base()
    from sqlalchemy import select
    from app.models import AffairsRiskRecord
    tid = b._tid()
    students = b._student_map(db)
    existing = {(x.student_id, x.title) for x in db.scalars(select(AffairsRiskRecord).where(
        AffairsRiskRecord.tenant_id == tid, AffairsRiskRecord.source == "MANUAL",
        AffairsRiskRecord.is_deleted.is_(False)))}
    ok, errors, seen, skipped = [], [], set(), 0
    for i, r in b._rows_iter(meta, rows):
        if not b._check_required(meta, r, i, errors):
            continue
        level = RISK_LEVEL_CN.get(r["riskLevel"])
        status = RISK_STATUS_CN.get(r["riskStatus"])
        if not level or not status:
            errors.append(b._err(i, "riskLevel" if not level else "riskStatus", "ENUM_INVALID",
                                 r["riskLevel"] if not level else r["riskStatus"],
                                 "风险等级须为 低/中/高/极高；状态须为 在管/已关闭"))
            continue
        s = students.get(r["studentNo"])
        if not s:
            errors.append(b._err(i, "studentNo", "REF_NOT_FOUND", r["studentNo"],
                                 f"学号 {r['studentNo']} 不在学生主档"))
            continue
        title = r["description"][:200]
        key = (s.id, title)
        if key in existing or key in seen:
            skipped += 1
            continue
        seen.add(key)
        teacher, _amb = _find_teacher(db, tid, r["ownerKey"])
        ok.append({"studentId": s.id, "studentNo": r["studentNo"], "riskLevel": level,
                   "title": title, "detail": r["description"][:1000],
                   "ownerId": teacher.id if teacher else None, "status": status})
    return ok, errors, skipped


def persist_risk_manual(db, rows):
    from app.models import AffairsRiskRecord, UnifiedTodo
    b = _base()
    tid = b._tid()
    for r in rows:
        risk = AffairsRiskRecord(tenant_id=tid, student_id=r["studentId"], source="MANUAL",
                                 risk_level=r["riskLevel"], title=r["title"], detail=r["detail"],
                                 owner_id=r["ownerId"], status=r["status"],
                                 closed_reason="历史迁移导入即关闭" if r["status"] == "CLOSED" else None)
        db.add(risk)
        db.flush()
        # 学工导入中唯一允许生成待办的域（设计 A9）；责任人未解析到账号时不生成（无 assignee 不造空待办）
        if r["status"] == "NEW" and r["ownerId"]:
            db.add(UnifiedTodo(tenant_id=tid, source_module="student-affairs", source_biz_id=risk.id,
                               todo_type="RISK", assignee_id=r["ownerId"],
                               title=f"处理风险学生（{r['studentNo']}，历史迁移）", status="PENDING"))
    return {"created": len(rows)}


# ── B6 课程库 ──

def validate_course(db, meta, rows):
    b = _base()
    from sqlalchemy import select
    from app.models import AaCourse
    existing = {(x.course_code, x.version): x for x in db.scalars(select(AaCourse).where(
        AaCourse.tenant_id == b._tid(), AaCourse.is_deleted.is_(False)))}
    ok, errors, seen = [], [], set()
    for i, r in b._rows_iter(meta, rows):
        if not b._check_required(meta, r, i, errors):
            continue
        category = COURSE_CATEGORY_CN.get(r["category"])
        nature = COURSE_NATURE_CN.get(r["nature"])
        if not category or not nature:
            errors.append(b._err(i, "category" if not category else "nature", "ENUM_INVALID",
                                 r["category"] if not category else r["nature"],
                                 "类别须为 公共基础/学科基础/专业核心/专业选修/集中实践；性质须为 必修/选修/限选/公选"))
            continue
        try:
            credit = float(r["credit"])
            h_theory, h_practice = int(float(r["hoursTheory"])), int(float(r["hoursPractice"]))
        except ValueError:
            errors.append(b._err(i, "credit", "FORMAT_INVALID",
                                 f"{r['credit']}/{r['hoursTheory']}/{r['hoursPractice']}",
                                 "学分/学时须为数字"))
            continue
        if not (0.5 <= credit <= 20) or (credit * 2) % 1 != 0:
            errors.append(b._err(i, "credit", "RANGE_INVALID", r["credit"], "学分须为 0.5-20，步长 0.5"))
            continue
        version = int(float(r["version"])) if r["version"] else 1
        key = (r["courseCode"], version)
        if key in seen:
            errors.append(b._err(i, "courseCode", "DUP_IN_FILE", r["courseCode"], "课程编码+版本在文件内重复"))
            continue
        hit = existing.get(key)
        if hit and hit.status not in ("DRAFT",):
            errors.append(b._err(i, "courseCode", "STATE_LOCKED", r["courseCode"],
                                 f"课程已{hit.status}，不允许覆盖（改课走新版本）"))
            continue
        seen.add(key)
        ok.append({"courseCode": r["courseCode"], "courseName": r["courseName"], "category": category,
                   "nature": nature, "credit": credit, "hoursTheory": h_theory,
                   "hoursPractice": h_practice,
                   "examMode": "CHECK" if r["examMode"] == "考查" else "EXAM", "version": version})
    return ok, errors, 0


def persist_course(db, rows):
    from sqlalchemy import select
    from app.models import AaCourse
    b = _base()
    tid = b._tid()
    created = updated = 0
    for r in rows:
        hit = db.scalars(select(AaCourse).where(
            AaCourse.tenant_id == tid, AaCourse.course_code == r["courseCode"],
            AaCourse.version == r["version"], AaCourse.is_deleted.is_(False))).first()
        if hit:
            hit.course_name, hit.category, hit.nature = r["courseName"], r["category"], r["nature"]
            hit.credit, hit.hours_theory, hit.hours_practice = r["credit"], r["hoursTheory"], r["hoursPractice"]
            hit.hours_total, hit.exam_mode = r["hoursTheory"] + r["hoursPractice"], r["examMode"]
            updated += 1
        else:
            db.add(AaCourse(tenant_id=tid, course_code=r["courseCode"], course_name=r["courseName"],
                            category=r["category"], nature=r["nature"], credit=r["credit"],
                            hours_theory=r["hoursTheory"], hours_practice=r["hoursPractice"],
                            hours_total=r["hoursTheory"] + r["hoursPractice"],
                            exam_mode=r["examMode"], version=r["version"], status="DRAFT"))
            created += 1
    return {"created": created, "updated": updated}


# ── B7 培养方案（分组行） ──

def validate_program(db, meta, rows):
    b = _base()
    from sqlalchemy import select
    from app.models import AaCourse, AaProgram, Major
    tid = b._tid()
    majors = {m.major_name: m for m in db.scalars(select(Major).where(
        Major.tenant_id == tid, Major.is_deleted.is_(False)))}
    courses = {}
    for c in db.scalars(select(AaCourse).where(AaCourse.tenant_id == tid, AaCourse.is_deleted.is_(False))):
        cur = courses.get(c.course_code)
        if not cur or (c.status == "ENABLED" and cur.status != "ENABLED") or c.version > cur.version:
            courses[c.course_code] = c
    existing = {(p.major_id, p.grade_year, p.version) for p in db.scalars(select(AaProgram).where(
        AaProgram.tenant_id == tid, AaProgram.is_deleted.is_(False)))}
    ok, errors, seen_course, program_credits = [], [], set(), {}
    for i, r in b._rows_iter(meta, rows):
        if not b._check_required(meta, r, i, errors):
            continue
        major = majors.get(r["majorName"])
        if not major:
            errors.append(b._err(i, "majorName", "REF_NOT_FOUND", r["majorName"],
                                 f"专业「{r['majorName']}」不存在"))
            continue
        course = courses.get(r["courseCode"])
        if not course:
            errors.append(b._err(i, "courseCode", "REF_NOT_FOUND", r["courseCode"],
                                 f"课程 {r['courseCode']} 不在课程库（先导课程库）"))
            continue
        version = int(float(r["version"])) if r["version"] else 1
        pkey = (major.id, r["gradeYear"], version)
        if pkey in existing:
            errors.append(b._err(i, "gradeYear", "DUP_IN_DB", f"{r['majorName']}/{r['gradeYear']}/v{version}",
                                 "该专业该年级该版本方案已存在（方案版本化，重导走新版本）"))
            continue
        try:
            total = float(r["totalCredits"])
            term_no = int(float(r["openTermNo"]))
        except ValueError:
            errors.append(b._err(i, "totalCredits", "FORMAT_INVALID",
                                 f"{r['totalCredits']}/{r['openTermNo']}", "总学分/开课学期须为数字"))
            continue
        if not 1 <= term_no <= 10:
            errors.append(b._err(i, "openTermNo", "RANGE_INVALID", r["openTermNo"], "开课学期须为 1-10"))
            continue
        prev_total = program_credits.setdefault(pkey, total)
        if prev_total != total:
            errors.append(b._err(i, "totalCredits", "VALIDATION_ERROR", r["totalCredits"],
                                 f"方案 {r['programName']} 各行总学分不一致（{prev_total} vs {total}）"))
            continue
        ckey = pkey + (r["courseCode"],)
        if ckey in seen_course:
            errors.append(b._err(i, "courseCode", "DUP_IN_FILE", r["courseCode"], "同方案课程重复"))
            continue
        seen_course.add(ckey)
        ok.append({"programKey": pkey, "programName": r["programName"], "majorId": major.id,
                   "gradeYear": r["gradeYear"], "totalCredits": total, "version": version,
                   "courseId": course.id, "courseName": course.course_name,
                   "credit": float(course.credit or 0), "openTermNo": term_no, "module": r["module"]})
    return ok, errors, 0


def persist_program(db, rows):
    from app.models import AaProgram, AaProgramBinding, AaProgramCourse
    b = _base()
    tid = b._tid()
    groups: dict = {}
    for r in rows:
        # Validation results are serialized into the shared import-batch JSON
        # before confirmation, so tuple keys come back as JSON arrays. Normalize
        # them before grouping instead of attempting to use a list as a dict key.
        key = tuple(r["programKey"]) if isinstance(r.get("programKey"), list) else r["programKey"]
        groups.setdefault(key, []).append(r)
    for pkey, items in groups.items():
        head = items[0]
        program = AaProgram(tenant_id=tid, program_name=head["programName"], major_id=head["majorId"],
                            grade_year=head["gradeYear"], total_credits=head["totalCredits"],
                            version=head["version"], status="DRAFT")
        db.add(program)
        db.flush()
        for it in items:
            db.add(AaProgramCourse(tenant_id=tid, program_id=program.id, course_id=it["courseId"],
                                   course_name=it["courseName"], open_term_no=it["openTermNo"],
                                   module=it["module"], credit_snapshot=it["credit"]))
        db.add(AaProgramBinding(tenant_id=tid, program_id=program.id, major_id=head["majorId"],
                                grade_year=head["gradeYear"], bound_at=datetime.utcnow(), status="ACTIVE"))
    return {"created": len(groups), "courseRows": len(rows)}


# ── B8 教学任务 ──

def _term_map(db, tid):
    from sqlalchemy import select
    from app.models import AaTerm
    return {(t.year_code, str(t.term_no)): t for t in db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == tid, AaTerm.is_deleted.is_(False)))}


def validate_teaching_task(db, meta, rows):
    b = _base()
    from sqlalchemy import select
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch
    tid = b._tid()
    terms = _term_map(db, tid)
    classes = _class_map(db, tid)
    courses = {c.course_code: c for c in db.scalars(select(AaCourse).where(
        AaCourse.tenant_id == tid, AaCourse.is_deleted.is_(False)))}
    batch_term = {x.id: x.term_id for x in db.scalars(select(AaTeachingTaskBatch).where(
        AaTeachingTaskBatch.tenant_id == tid))}
    existing = {(batch_term.get(t.batch_id), t.course_code, t.class_id)
                for t in db.scalars(select(AaTeachingTask).where(
                    AaTeachingTask.tenant_id == tid, AaTeachingTask.is_deleted.is_(False)))}
    ok, errors, seen = [], [], set()
    for i, r in b._rows_iter(meta, rows):
        if not b._check_required(meta, r, i, errors):
            continue
        term = terms.get((r["yearCode"], r["termNo"]))
        if not term:
            errors.append(b._err(i, "yearCode", "REF_NOT_FOUND", f"{r['yearCode']}/{r['termNo']}",
                                 "学期未导入（先导学年学期）"))
            continue
        course = courses.get(r["courseCode"])
        if not course:
            errors.append(b._err(i, "courseCode", "REF_NOT_FOUND", r["courseCode"],
                                 f"课程 {r['courseCode']} 不在课程库"))
            continue
        cls = classes.get(r["className"])
        if not cls:
            errors.append(b._err(i, "className", "REF_NOT_FOUND", r["className"],
                                 f"班级「{r['className']}」不存在"))
            continue
        try:
            weekly = int(float(r["weeklyHours"]))
        except ValueError:
            weekly = 0
        if not 1 <= weekly <= 20:
            errors.append(b._err(i, "weeklyHours", "RANGE_INVALID", r["weeklyHours"], "周学时须为 1-20"))
            continue
        teacher, ambiguous = _find_teacher(db, tid, r["teacherKey"])
        if ambiguous:
            errors.append(b._err(i, "teacherKey", "REF_AMBIGUOUS", r["teacherKey"],
                                 f"教师「{r['teacherKey']}」在租户内匹配到多个账号，请改用工号"))
            continue
        key = (term.id, r["courseCode"], cls.id)
        if key in existing or key in seen:
            errors.append(b._err(i, "courseCode", "DUP_IN_DB" if key in existing else "DUP_IN_FILE",
                                 f"{r['courseCode']}/{r['className']}", "学期+课程+班级任务已存在"))
            continue
        seen.add(key)
        ok.append({"termId": term.id, "courseId": course.id, "courseCode": r["courseCode"],
                   "courseName": course.course_name, "classId": cls.id, "className": r["className"],
                   "teacherId": teacher.id if teacher else None,
                   "teacherName": teacher.real_name if teacher else None,
                   "teacherKey": r["teacherKey"],
                   "expected": int(float(r["expectedStudents"])) if r["expectedStudents"] else None,
                   "weeklyHours": weekly})
    return ok, errors, 0


def _get_or_create_task_batch(db, tid, term_id):
    from sqlalchemy import select
    from app.models import AaTeachingTaskBatch
    hit = db.scalars(select(AaTeachingTaskBatch).where(
        AaTeachingTaskBatch.tenant_id == tid, AaTeachingTaskBatch.term_id == term_id,
        AaTeachingTaskBatch.batch_name == MIGRATION_BATCH_NAME)).first()
    if hit:
        return hit
    hit = AaTeachingTaskBatch(tenant_id=tid, term_id=term_id, batch_name=MIGRATION_BATCH_NAME,
                              status="APPROVED", generate_at=datetime.utcnow())
    db.add(hit)
    db.flush()
    return hit


def persist_teaching_task(db, rows):
    from app.models import AaTeachingTask
    b = _base()
    tid = b._tid()
    for r in rows:
        batch = _get_or_create_task_batch(db, tid, r["termId"])
        db.add(AaTeachingTask(tenant_id=tid, batch_id=batch.id, course_id=r["courseId"],
                              course_code=r["courseCode"], course_name=r["courseName"],
                              class_id=r["classId"], teaching_class_name=r["className"],
                              teacher_id=r["teacherId"], teacher_key=r["teacherKey"],
                              teacher_name=r["teacherName"], expected_students=r["expected"],
                              weekly_hours=r["weeklyHours"], status="READY"))
    return {"created": len(rows)}


# ── B9 课表 ──

def _weeks_overlap(a, bb):
    """(start,end,parity) 周次重叠判定；ODD 与 EVEN 不相交，ALL 与任意相交。"""
    (s1, e1, p1), (s2, e2, p2) = a, bb
    if e1 < s2 or e2 < s1:
        return False
    if {p1, p2} == {"ODD", "EVEN"}:
        return False
    return True


def validate_schedule(db, meta, rows):
    b = _base()
    from sqlalchemy import select
    from app.models import AaScheduleBatch, AaScheduleItem, AaTeachingTask, AaTimeSlot
    tid = b._tid()
    terms = _term_map(db, tid)
    classes = _class_map(db, tid)
    slots = {x.slot_no for x in db.scalars(select(AaTimeSlot).where(
        AaTimeSlot.tenant_id == tid, AaTimeSlot.is_deleted.is_(False)))}
    tasks = {}
    for t in db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == tid, AaTeachingTask.is_deleted.is_(False))):
        tasks[(t.batch_id, t.course_code, t.class_id)] = t
    from app.models import AaTeachingTaskBatch
    task_batches = {x.id: x.term_id for x in db.scalars(select(AaTeachingTaskBatch).where(
        AaTeachingTaskBatch.tenant_id == tid))}
    sched_batches = {x.id: x.term_id for x in db.scalars(select(AaScheduleBatch).where(
        AaScheduleBatch.tenant_id == tid, AaScheduleBatch.is_deleted.is_(False)))}
    db_items = []
    for it in db.scalars(select(AaScheduleItem).where(
            AaScheduleItem.tenant_id == tid, AaScheduleItem.is_deleted.is_(False),
            AaScheduleItem.status == "EFFECTIVE")):
        db_items.append({"termId": sched_batches.get(it.batch_id), "classId": it.class_id,
                         "teacherKey": it.teacher_key, "weekday": it.weekday, "slotNo": it.slot_no,
                         "weeks": (it.start_week, it.end_week, it.week_parity)})
    ok, errors = [], []
    file_items = []
    for i, r in b._rows_iter(meta, rows):
        if not b._check_required(meta, r, i, errors):
            continue
        term = terms.get((r["yearCode"], r["termNo"]))
        if not term:
            errors.append(b._err(i, "yearCode", "REF_NOT_FOUND", f"{r['yearCode']}/{r['termNo']}",
                                 "学期未导入"))
            continue
        cls = classes.get(r["className"])
        if not cls:
            errors.append(b._err(i, "className", "REF_NOT_FOUND", r["className"],
                                 f"班级「{r['className']}」不存在"))
            continue
        task = next((t for (bid, code, cid), t in tasks.items()
                     if code == r["courseCode"] and cid == cls.id and task_batches.get(bid) == term.id), None)
        if not task:
            errors.append(b._err(i, "courseCode", "REF_NOT_FOUND",
                                 f"{r['courseCode']}/{r['className']}",
                                 "该学期无对应教学任务（先导教学任务）"))
            continue
        try:
            weekday, slot_no = int(float(r["weekday"])), int(float(r["slotNo"]))
            sw, ew = int(float(r["startWeek"])), int(float(r["endWeek"]))
        except ValueError:
            errors.append(b._err(i, "weekday", "FORMAT_INVALID",
                                 f"{r['weekday']}/{r['slotNo']}/{r['startWeek']}-{r['endWeek']}",
                                 "星期/节次/周次须为数字"))
            continue
        if not 1 <= weekday <= 7:
            errors.append(b._err(i, "weekday", "RANGE_INVALID", r["weekday"], "星期须为 1-7"))
            continue
        if slot_no not in slots:
            errors.append(b._err(i, "slotNo", "REF_NOT_FOUND", r["slotNo"],
                                 f"节次 {slot_no} 不在作息节次（先导作息节次）"))
            continue
        max_week = term.teaching_weeks or 30
        if not 1 <= sw <= ew <= max_week:
            errors.append(b._err(i, "startWeek", "RANGE_INVALID", f"{sw}-{ew}",
                                 f"周次须满足 1≤起始≤结束≤{max_week}（教学周数）"))
            continue
        parity = WEEK_PARITY_CN.get(r["weekParity"], None)
        if parity is None:
            errors.append(b._err(i, "weekParity", "ENUM_INVALID", r["weekParity"], "单双周须为：全周/单周/双周"))
            continue
        weeks = (sw, ew, parity)
        conflict = None
        for other in file_items + db_items:
            if other["termId"] != term.id or other["weekday"] != weekday or other["slotNo"] != slot_no:
                continue
            if not _weeks_overlap(weeks, other["weeks"]):
                continue
            if other["classId"] == cls.id:
                conflict = ("CONFLICT_CLASS", f"班级 {r['className']} 周{weekday}第{slot_no}节已有课")
                break
            if task.teacher_key and other.get("teacherKey") == task.teacher_key:
                conflict = ("CONFLICT_TEACHER", f"教师 {task.teacher_key} 周{weekday}第{slot_no}节已有课")
                break
        if conflict:
            errors.append(b._err(i, "slotNo", conflict[0], f"周{weekday}第{slot_no}节", conflict[1]))
            continue
        item = {"termId": term.id, "taskId": task.id, "courseId": task.course_id,
                "courseName": task.course_name, "classId": cls.id, "className": r["className"],
                "teacherKey": task.teacher_key, "teacherName": task.teacher_name,
                "weekday": weekday, "slotNo": slot_no, "weeks": weeks,
                "classroom": r["classroom"] or None}
        file_items.append(item)
        ok.append(item)
    return ok, errors, 0


def persist_schedule(db, rows):
    from sqlalchemy import select
    from app.models import AaScheduleBatch, AaScheduleItem
    b = _base()
    tid = b._tid()
    batches = {}
    for r in rows:
        batch = batches.get(r["termId"])
        if not batch:
            batch = db.scalars(select(AaScheduleBatch).where(
                AaScheduleBatch.tenant_id == tid, AaScheduleBatch.term_id == r["termId"],
                AaScheduleBatch.batch_name == "历史迁移课表", AaScheduleBatch.is_deleted.is_(False))).first()
            if not batch:
                batch = AaScheduleBatch(tenant_id=tid, term_id=r["termId"],
                                        batch_name="历史迁移课表", status="DRAFT")
                db.add(batch)
                db.flush()
            batches[r["termId"]] = batch
        sw, ew, parity = r["weeks"]
        db.add(AaScheduleItem(tenant_id=tid, batch_id=batch.id, task_id=r["taskId"],
                              course_id=r["courseId"], course_name=r["courseName"],
                              class_id=r["classId"], class_name=r["className"],
                              teacher_key=r["teacherKey"], teacher_name=r["teacherName"],
                              weekday=r["weekday"], slot_no=r["slotNo"], start_week=sw, end_week=ew,
                              week_parity=parity, classroom_text=r["classroom"],
                              status="EFFECTIVE", source="IMPORT"))
    return {"created": len(rows), "batches": len(batches)}


# ── B11 历届毕业结论 ──

def validate_graduation_history(db, meta, rows):
    b = _base()
    from sqlalchemy import select
    from app.models import AaGraduationAuditBatch, AaGraduationAuditResult
    tid = b._tid()
    students = b._student_map(db)
    batches = {x.grade_year: x for x in db.scalars(select(AaGraduationAuditBatch).where(
        AaGraduationAuditBatch.tenant_id == tid,
        AaGraduationAuditBatch.batch_name.like(f"{MIGRATION_BATCH_NAME}%"),
        AaGraduationAuditBatch.is_deleted.is_(False)))}
    existing = set()
    for x in db.scalars(select(AaGraduationAuditResult).where(
            AaGraduationAuditResult.tenant_id == tid, AaGraduationAuditResult.is_deleted.is_(False))):
        existing.add((x.batch_id, x.student_id))
    ok, errors, seen = [], [], set()
    for i, r in b._rows_iter(meta, rows):
        if not b._check_required(meta, r, i, errors):
            continue
        conclusion = CONCLUSION_CN.get(r["conclusion"])
        if not conclusion:
            errors.append(b._err(i, "conclusion", "ENUM_INVALID", r["conclusion"], "结论须为：毕业/结业/延毕"))
            continue
        s = students.get(r["studentNo"])
        if not s:
            errors.append(b._err(i, "studentNo", "REF_NOT_FOUND", r["studentNo"],
                                 f"学号 {r['studentNo']} 不在学生主档"))
            continue
        if conclusion == "GRADUATED" and s.student_status == "WITHDRAWN":
            errors.append(b._err(i, "conclusion", "CROSS_CHECK_FAILED", r["conclusion"],
                                 f"该生主档学籍状态为 WITHDRAWN（退学），不能导入毕业结论"))
            continue
        at = b._parse_date(r["concludedAt"])
        if not at:
            errors.append(b._err(i, "concludedAt", "FORMAT_INVALID", r["concludedAt"], "结论日期无法解析"))
            continue
        bkey = batches.get(r["graduateYear"])
        key = (bkey.id if bkey else f"new-{r['graduateYear']}", s.id)
        if key in existing or key in seen:
            errors.append(b._err(i, "studentNo", "DUP_IN_DB" if key in existing else "DUP_IN_FILE",
                                 r["studentNo"], f"{r['graduateYear']} 届该生已有毕业结论"))
            continue
        seen.add(key)
        ok.append({"studentId": s.id, "graduateYear": r["graduateYear"], "conclusion": conclusion,
                   "concludedAt": at, "remark": r["remark"] or None})
    return ok, errors, 0


def persist_graduation_history(db, rows):
    from sqlalchemy import select
    from app.models import AaGraduationAuditBatch, AaGraduationAuditResult, StudentStageEvent
    b = _base()
    tid = b._tid()
    for r in rows:
        batch = db.scalars(select(AaGraduationAuditBatch).where(
            AaGraduationAuditBatch.tenant_id == tid,
            AaGraduationAuditBatch.batch_name == f"{MIGRATION_BATCH_NAME}-{r['graduateYear']}届",
            AaGraduationAuditBatch.is_deleted.is_(False))).first()
        if not batch:
            batch = AaGraduationAuditBatch(tenant_id=tid,
                                           batch_name=f"{MIGRATION_BATCH_NAME}-{r['graduateYear']}届",
                                           grade_year=r["graduateYear"], status="ARCHIVED")
            db.add(batch)
            db.flush()
        db.add(AaGraduationAuditResult(tenant_id=tid, batch_id=batch.id, student_id=r["studentId"],
                                       conclusion=r["conclusion"], overall="SYSTEM_PASSED",
                                       item_results_json=json.dumps({"legacy": True}),
                                       review_note=r["remark"], status="ARCHIVED"))
        db.add(StudentStageEvent(tenant_id=tid, student_id=r["studentId"], from_stage=None,
                                 to_stage=r["conclusion"],
                                 reason=f"{r['graduateYear']}届毕业结论（历史迁移）",
                                 source_module="academic-affairs"))
    return {"created": len(rows)}


P2_VALIDATORS = {
    "affairs-family-contact": validate_family_contact,
    "affairs-class-cadre": validate_class_cadre,
    "affairs-dorm-building": validate_dorm_building,
    "affairs-dorm-assign": validate_dorm_assign,
    "affairs-leave-history": validate_leave_history,
    "affairs-aid-history": validate_aid_history,
    "affairs-funding-history": validate_funding_history,
    "affairs-discipline-history": validate_discipline_history,
    "affairs-talk-history": validate_talk_history,
    "affairs-risk-manual": validate_risk_manual,
    "aa-course": validate_course,
    "aa-program": validate_program,
    "aa-teaching-task": validate_teaching_task,
    "aa-schedule": validate_schedule,
    "aa-graduation-history": validate_graduation_history,
}
P2_PERSISTERS = {
    "affairs-family-contact": persist_family_contact,
    "affairs-class-cadre": persist_class_cadre,
    "affairs-dorm-building": persist_dorm_building,
    "affairs-dorm-assign": persist_dorm_assign,
    "affairs-leave-history": persist_leave_history,
    "affairs-aid-history": persist_aid_history,
    "affairs-funding-history": persist_funding_history,
    "affairs-discipline-history": persist_discipline_history,
    "affairs-talk-history": persist_talk_history,
    "affairs-risk-manual": persist_risk_manual,
    "aa-course": persist_course,
    "aa-program": persist_program,
    "aa-teaching-task": persist_teaching_task,
    "aa-schedule": persist_schedule,
    "aa-graduation-history": persist_graduation_history,
}
P2_PREVIEW_MASKS = {
    "affairs-family-contact": mask_family_contact_preview,
    "affairs-talk-history": mask_talk_preview,
}
