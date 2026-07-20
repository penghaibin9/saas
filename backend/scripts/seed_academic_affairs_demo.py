"""教务中心销售演示数据种子（sandbox-school，仅本租户）。

目标：让 admin2/123456 登录后，教务中心每个三级页面都能看到贯通、真实、可讲述的
完整业务链条（学院→专业→培养方案→课程→教学任务→排课→选课→考勤→考务→成绩→
评教→学籍事务→教材→教学质量→归档→毕业预审→资源），而不是空表或随机凑数。

约定：
- 只写 tenant_id=SANDBOX；不碰其它租户，不删除任何既有数据（含 E2E 测试残留）。
- 幂等：所有写入前先按业务唯一键查重，重复执行不产生重复行。
- 时间线：2025-2026学年第一学期（已归档，历史数据）/ 第二学期（本学期，刚结课，
  绝大多数流程在此学期跑满全流程）/ 2026-2027学年第一学期（下学期，筹备中）。
- 25级班级=2025年9月入学（在校第二学年），26级班级=2026年9月即将入学的新生班
  （提前建班未正式入学，故本学期几乎无教学数据，仅少量占位，符合真实开学前状态）。

运行：backend 目录下 `..\\.venv\\Scripts\\python.exe scripts\\seed_academic_affairs_demo.py`
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

os.environ.setdefault("DB_ENABLED", "true")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.core.context import set_tenant  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402

TID = 1000000000000000004
REAL_COLLEGE_IDS = [20, 21, 22, 23]  # 排除 24=CC-E2E 测试学院
MAJOR_BY_COLLEGE = {20: [22], 21: [23, 24], 22: [25, 26], 23: [27, 28]}
CLASS_BY_MAJOR = {
    22: [34],
    23: [35, 36], 24: [37, 38],
    25: [39, 40], 26: [41, 42],
    27: [43, 44], 28: [45, 46],
}
GRADE25_CLASSES = [35, 37, 39, 41, 43, 45]   # 2025级：在校第二学年
GRADE26_CLASSES = [36, 38, 40, 42, 44, 46]   # 2026级：即将开学新生（少量占位数据）
EXP_CLASS = 34  # 体验2601班（"体验"演示专用行政班）

report: dict[str, int] = {}


def bump(key: str, n: int = 1):
    report[key] = report.get(key, 0) + n


def get(db, model, **where):
    conds = [getattr(model, k) == v for k, v in where.items()]
    return db.scalars(select(model).where(model.tenant_id == TID, *conds)).first()


# ═══════════════════════ Phase 1：教师团队 + 角色 ═══════════════════════

TEACHER_SEED = [
    # (login, real_name, college_id, roles)
    ("t_dong_kejian", "董克建", 21, ["ACADEMIC_ADMIN"]),       # 教务处长（教务处管理员）
    ("t_luo_yaqin", "罗雅琴", None, ["ACADEMIC_ADMIN"]),        # 教务处教师
    ("t_wu_zhigang", "吴志刚", 20, ["COLLEGE_ADMIN", "ACADEMIC_TEACHER"]),   # 体验学院院长
    ("t_he_xiaoyan", "何晓燕", 20, ["ACADEMIC_TEACHER"]),
    ("t_zhou_bin", "周斌", 21, ["COLLEGE_ADMIN", "ACADEMIC_TEACHER"]),      # 智能制造学院院长
    ("t_tan_weiguo", "谭伟国", 21, ["ACADEMIC_TEACHER"]),
    ("t_peng_lina", "彭丽娜", 21, ["ACADEMIC_TEACHER"]),
    ("t_liu_zhiqiang", "刘志强", 22, ["COLLEGE_ADMIN", "ACADEMIC_TEACHER"]),  # 信息工程学院院长
    ("t_chen_xiaoli", "陈晓丽", 22, ["ACADEMIC_TEACHER"]),
    ("t_huang_junfeng", "黄军峰", 22, ["ACADEMIC_TEACHER"]),
    ("t_zeng_fang", "曾芳", 22, ["ACADEMIC_TEACHER"]),
    ("t_liang_shuqin", "梁淑琴", 23, ["COLLEGE_ADMIN", "ACADEMIC_TEACHER"]),  # 健康服务学院院长
    ("t_xie_yumei", "谢玉梅", 23, ["ACADEMIC_TEACHER"]),
    ("t_deng_haiyan", "邓海燕", 23, ["ACADEMIC_TEACHER"]),
    ("t_lin_xiaofeng", "林晓峰", None, ["ACADEMIC_TEACHER"]),   # 公共课教师（不挂学院）
    ("t_ma_yuling", "马玉玲", None, ["ACADEMIC_TEACHER"]),      # 公共课教师
]


def seed_teachers(db) -> dict[str, int]:
    from app.services.saas_role_service import ensure_builtin_roles, ensure_user_roles
    from app.models import User

    ensure_builtin_roles(db, TID)
    db.commit()

    name_to_id: dict[str, int] = {}
    for login, name, college_id, roles in TEACHER_SEED:
        u = get(db, User, login_name=login)
        if u is None:
            u = User(tenant_id=TID, login_name=login, real_name=name,
                     password_hash="pbkdf2_sha256$200000$demo$demo-not-a-real-login",
                     user_type="TEACHER", status="ACTIVE")
            db.add(u)
            db.flush()
            bump("t_user(teacher)")
        name_to_id[name] = u.id
        ensure_user_roles(db, TID, u.id, roles)
    db.commit()

    # 已有 teacher2(王老师)/demo_intern_mentor(刘强) 也纳入教师池，补 ACADEMIC_TEACHER 角色
    for login in ("teacher2",):
        u = get(db, User, login_name=login)
        if u:
            ensure_user_roles(db, TID, u.id, ["ACADEMIC_TEACHER"])
            name_to_id[u.real_name] = u.id
    db.commit()
    return name_to_id


# ═══════════════════════ Phase 2：学年学期 / 校历 / 培养方案 / 课程库 ═══════════════════════

MAJOR_NAME = {22: "电子商务", 23: "机电一体化技术", 24: "工业机器人技术",
             25: "软件技术", 26: "大数据技术", 27: "护理", 28: "康复治疗技术"}

# 每个专业的核心课程清单：(课程代码后缀, 课程名, 类别, 性质, 学分, 总学时, 考核方式)
MAJOR_COURSES = {
    22: [("001", "电子商务概论", "MAJOR_CORE", "REQUIRED", 3, 48, "EXAM"),
         ("002", "网络营销实务", "MAJOR_CORE", "REQUIRED", 3, 48, "EXAM"),
         ("003", "跨境电商实务", "MAJOR_ELECTIVE", "ELECTIVE", 2, 32, "CHECK")],
    23: [("001", "机械制图与CAD", "DISCIPLINE_BASIC", "REQUIRED", 4, 64, "EXAM"),
         ("002", "机电一体化系统设计", "MAJOR_CORE", "REQUIRED", 4, 64, "EXAM"),
         ("003", "PLC应用技术", "MAJOR_CORE", "REQUIRED", 3, 48, "EXAM")],
    24: [("001", "工业机器人操作与编程", "MAJOR_CORE", "REQUIRED", 4, 64, "EXAM"),
         ("002", "机器人工作站集成", "MAJOR_CORE", "REQUIRED", 3, 48, "EXAM"),
         ("003", "液压与气动技术", "DISCIPLINE_BASIC", "REQUIRED", 3, 48, "CHECK")],
    25: [("001", "Java程序设计", "MAJOR_CORE", "REQUIRED", 4, 64, "EXAM"),
         ("002", "Web前端开发", "MAJOR_CORE", "REQUIRED", 3, 48, "EXAM"),
         ("003", "数据库原理与应用", "DISCIPLINE_BASIC", "REQUIRED", 3, 48, "EXAM"),
         ("004", "软件测试技术", "MAJOR_ELECTIVE", "ELECTIVE", 2, 32, "CHECK")],
    26: [("001", "Python数据分析", "MAJOR_CORE", "REQUIRED", 4, 64, "EXAM"),
         ("002", "大数据技术基础", "MAJOR_CORE", "REQUIRED", 3, 48, "EXAM"),
         ("003", "数据可视化", "MAJOR_ELECTIVE", "ELECTIVE", 2, 32, "CHECK")],
    27: [("001", "基础护理学", "MAJOR_CORE", "REQUIRED", 4, 72, "EXAM"),
         ("002", "内科护理学", "MAJOR_CORE", "REQUIRED", 4, 64, "EXAM"),
         ("003", "健康评估", "DISCIPLINE_BASIC", "REQUIRED", 3, 48, "EXAM")],
    28: [("001", "康复评定技术", "MAJOR_CORE", "REQUIRED", 3, 56, "EXAM"),
         ("002", "运动治疗技术", "MAJOR_CORE", "REQUIRED", 3, 48, "EXAM"),
         ("003", "作业治疗技术", "DISCIPLINE_BASIC", "REQUIRED", 3, 48, "CHECK")],
}
PUBLIC_COURSES = [
    ("PUB001", "思想道德与法治", "PUBLIC_BASIC", "REQUIRED", 2, 32, "CHECK"),
    ("PUB002", "大学英语", "PUBLIC_BASIC", "REQUIRED", 3, 48, "EXAM"),
    ("PUB003", "体育与健康", "PUBLIC_BASIC", "REQUIRED", 1, 32, "CHECK"),
    ("PUB004", "计算机应用基础", "PUBLIC_BASIC", "REQUIRED", 2, 32, "EXAM"),
]


def seed_terms(db) -> dict[str, int]:
    from app.models import AaTerm
    terms = [
        ("2025-2026", 1, "2025-2026学年第一学期", "2025-09-01", "2026-01-16", 18, 17, False, "ARCHIVED"),
        ("2025-2026", 2, "2025-2026学年第二学期", "2026-02-23", "2026-07-10", 18, 17, True, "PUBLISHED"),
        ("2026-2027", 1, "2026-2027学年第一学期", "2026-09-01", "2027-01-15", 18, 17, False, "DRAFT"),
    ]
    ids: dict[str, int] = {}
    for year_code, term_no, name, start, end, weeks, exam_start, is_current, status in terms:
        t = get(db, AaTerm, year_code=year_code, term_no=term_no)
        if t is None:
            t = AaTerm(tenant_id=TID, year_code=year_code, term_no=term_no, term_name=name,
                       start_date=datetime.strptime(start, "%Y-%m-%d"),
                       end_date=datetime.strptime(end, "%Y-%m-%d"),
                       teaching_weeks=weeks, exam_week_start=exam_start,
                       is_current=is_current, status=status)
            db.add(t)
            db.flush()
            bump("t_aa_term")
        elif t.term_name != name or t.is_current != is_current:
            # 该学期唯一键(年份+学期号)已被占用(如 E2E 测试脏数据)，把内容纠正为
            # 真实演示叙事，不新建重复行、不删除——只把名字/当前学期标记改对，
            # 避免测试用语("CC-E2E-...")或错误的 is_current 冲突出现在演示页面。
            t.term_name = name
            t.start_date = datetime.strptime(start, "%Y-%m-%d")
            t.end_date = datetime.strptime(end, "%Y-%m-%d")
            t.teaching_weeks = weeks
            t.exam_week_start = exam_start
            t.is_current = is_current
            t.status = status
            bump("t_aa_term(corrected)")
        ids[f"{year_code}-{term_no}"] = t.id
    db.commit()
    return ids


def seed_calendar(db, term_ids: dict[str, int]):
    from app.models import AaCalendarEvent
    cur_term = term_ids["2025-2026-2"]
    events = [
        ("TEACHING", "2026-02-23", "2026-06-19", None, "第二学期正常教学周"),
        ("EXAM", "2026-06-22", "2026-07-03", None, "期末考试周"),
        ("HOLIDAY", "2026-04-04", "2026-04-06", None, "清明节放假"),
        ("HOLIDAY", "2026-05-01", "2026-05-05", None, "五一劳动节放假"),
    ]
    for etype, start, end, swap, remark in events:
        exists = db.scalars(select(AaCalendarEvent).where(
            AaCalendarEvent.tenant_id == TID, AaCalendarEvent.term_id == cur_term,
            AaCalendarEvent.event_type == etype, AaCalendarEvent.remark == remark)).first()
        if exists:
            continue
        db.add(AaCalendarEvent(tenant_id=TID, term_id=cur_term, event_type=etype,
                               start_date=datetime.strptime(start, "%Y-%m-%d"),
                               end_date=datetime.strptime(end, "%Y-%m-%d"),
                               swap_to_date=datetime.strptime(swap, "%Y-%m-%d") if swap else None,
                               remark=remark))
        bump("t_aa_calendar_event")
    db.commit()


def seed_time_slots(db) -> dict[int, int]:
    from app.models import AaTimeSlot, AaClassTimeBand
    slots = [
        (1, "第1节", "08:00", "08:45"), (2, "第2节", "08:55", "09:40"),
        (3, "第3节", "10:00", "10:45"), (4, "第4节", "10:55", "11:40"),
        (5, "第5节", "14:00", "14:45"), (6, "第6节", "14:55", "15:40"),
        (7, "第7节", "16:00", "16:45"), (8, "第8节", "16:55", "17:40"),
    ]
    slot_ids: dict[int, int] = {}
    for no, name, st, et in slots:
        s = get(db, AaTimeSlot, slot_no=no)
        if s is None:
            s = AaTimeSlot(tenant_id=TID, slot_no=no, slot_name=name, start_time=st, end_time=et,
                          enabled=True, status="ENABLED")
            db.add(s)
            db.flush()
            bump("t_aa_time_slot")
        slot_ids[no] = s.id
    db.commit()
    band = get(db, AaClassTimeBand, band_name="标准作息")
    if band is None:
        band = AaClassTimeBand(tenant_id=TID, slot_id=slot_ids[1], band_name="标准作息",
                               effective_start=datetime(2025, 9, 1), effective_end=datetime(2027, 7, 1),
                               start_time="08:00", end_time="17:40", status="ENABLED")
        db.add(band)
        bump("t_aa_class_time_band")
    db.commit()
    return slot_ids


def seed_courses(db, teachers: dict[str, int]) -> dict[str, int]:
    """课程库：4 门公共课（全校通用）+ 每专业 2~4 门专业课。返回 course_code -> course_id。"""
    from app.models import AaCourse
    course_ids: dict[str, int] = {}
    owner_pool = list(teachers.values())

    def _upsert(code, name, category, nature, credit, hours, exam_mode, owner_college, owner_teacher, applicable):
        c = get(db, AaCourse, course_code=code, version=1)
        if c is None:
            c = AaCourse(tenant_id=TID, course_code=code, course_name=name, category=category,
                        nature=nature, credit=Decimal(str(credit)), hours_total=hours,
                        hours_theory=int(hours * 0.6), hours_practice=hours - int(hours * 0.6),
                        exam_mode=exam_mode, owner_college_id=owner_college, owner_teacher_id=owner_teacher,
                        is_core=(category == "MAJOR_CORE"), version=1, status="ENABLED",
                        applicable_majors_json=json.dumps(applicable) if applicable else None,
                        is_all_major=not applicable,
                        description=f"{name}课程简介：面向{('全校' if not applicable else '本专业')}学生开设，"
                                   f"培养岗位核心技能。")
            db.add(c)
            db.flush()
            bump("t_aa_course")
        course_ids[code] = c.id

    for code, name, category, nature, credit, hours, exam_mode in PUBLIC_COURSES:
        _upsert(code, name, category, nature, credit, hours, exam_mode, None,
               owner_pool[0] if owner_pool else None, None)

    for major_id, courses in MAJOR_COURSES.items():
        college_id = next((cid for cid, majors in MAJOR_BY_COLLEGE.items() if major_id in majors), None)
        college_teachers = [uid for name, uid in teachers.items()]
        for suffix, name, category, nature, credit, hours, exam_mode in courses:
            code = f"M{major_id}{suffix}"
            _upsert(code, name, category, nature, credit, hours, exam_mode, college_id,
                   college_teachers[major_id % len(college_teachers)] if college_teachers else None,
                   [major_id])
    db.commit()
    return course_ids


def seed_programs(db, course_ids: dict[str, int]) -> dict[int, int]:
    """每专业一份 2025 级培养方案（ENABLED），绑定核心课程 + 毕业要求 + 实践环节。返回 major_id -> program_id。"""
    from app.models import (AaProgram, AaProgramBinding, AaProgramCourse,
                            AaProgramGraduationRequirement, AaProgramPracticeSegment)
    program_ids: dict[int, int] = {}
    for major_id, name in MAJOR_NAME.items():
        pname = f"{name}专业2025级人才培养方案"
        p = get(db, AaProgram, program_name=pname)
        if p is None:
            p = AaProgram(tenant_id=TID, program_name=pname, major_id=major_id, grade_year="2025",
                         total_credits=140, version=1, status="ENABLED",
                         requirement_json=json.dumps({"公共课": 30, "专业课": 80, "实践环节": 30}, ensure_ascii=False))
            db.add(p)
            db.flush()
            bump("t_aa_program")

            for code, *_ in PUBLIC_COURSES:
                db.add(AaProgramCourse(tenant_id=TID, program_id=p.id, course_id=course_ids[code],
                                       course_name=next(c[1] for c in PUBLIC_COURSES if c[0] == code),
                                       open_term_no=1, module="公共", credit_snapshot=2))
            for suffix, cname, category, *_ in MAJOR_COURSES[major_id]:
                code = f"M{major_id}{suffix}"
                db.add(AaProgramCourse(tenant_id=TID, program_id=p.id, course_id=course_ids[code],
                                       course_name=cname, open_term_no=3, module="专业", credit_snapshot=3))
            bump("t_aa_program_course", len(PUBLIC_COURSES) + len(MAJOR_COURSES[major_id]))

            db.add(AaProgramBinding(tenant_id=TID, program_id=p.id, major_id=major_id, grade_year="2025",
                                    bound_at=datetime(2025, 8, 20), status="ACTIVE"))
            bump("t_aa_program_binding")

            for cat, content in [("KNOWLEDGE", f"掌握{name}专业必备的基础理论知识与专业核心知识"),
                                 ("ABILITY", f"具备{name}岗位群所需的实际操作与问题解决能力"),
                                 ("QUALITY", "具有良好的职业道德、敬业精神与团队协作意识"),
                                 ("CERTIFICATE", "鼓励并支持学生考取与本专业对应的职业技能等级证书")]:
                db.add(AaProgramGraduationRequirement(tenant_id=TID, program_id=p.id, category=cat,
                                                      content=content, status="ACTIVE"))
            bump("t_aa_program_graduation_requirement", 4)

            for seg_name, seg_type, term_no, weeks, credit in [
                ("认识实习", "COGNITION_INTERNSHIP", 2, 1, 1), ("课程设计", "COURSE_DESIGN", 4, 2, 2),
                ("顶岗实习", "POST_INTERNSHIP", 6, 16, 16), ("毕业设计(论文)", "GRADUATION_PROJECT", 6, 8, 8),
            ]:
                db.add(AaProgramPracticeSegment(tenant_id=TID, program_id=p.id, segment_name=seg_name,
                                                segment_type=seg_type, open_term_no=term_no,
                                                weeks=Decimal(str(weeks)), credit=Decimal(str(credit)),
                                                org_mode="CENTRALIZED", assessment_mode="CHECK", status="ACTIVE"))
            bump("t_aa_program_practice_segment", 4)
        program_ids[major_id] = p.id
    db.commit()
    return program_ids


def seed_course_materials(db, course_ids: dict[str, int], teachers: dict[str, int]):
    from app.models import AaCourseMaterial
    names = list(teachers.keys())
    for i, (code, cid) in enumerate(list(course_ids.items())[:6]):
        exists = db.scalars(select(AaCourseMaterial).where(
            AaCourseMaterial.tenant_id == TID, AaCourseMaterial.course_id == cid)).first()
        if exists:
            continue
        db.add(AaCourseMaterial(tenant_id=TID, course_id=cid, material_type="SYLLABUS",
                                title=f"{code} 教学大纲（2025版）", uploader=names[i % len(names)],
                                status="ACTIVE"))
        bump("t_aa_course_material")
    db.commit()


# ═══════════════════════ Phase 3：教学资源（教室/实训室/设备） ═══════════════════════

def seed_resources(db, teachers: dict[str, int]) -> dict[str, list[int]]:
    from app.models import AaClassroom, AaEquipment, AaLabResource
    names = list(teachers.keys())
    classroom_ids: list[int] = []
    for building_code, building_name, room_no, cap, rtype in [
        ("A", "教学楼A栋", "101", 60, "LECTURE"), ("A", "教学楼A栋", "102", 60, "LECTURE"),
        ("A", "教学楼A栋", "201", 80, "MULTIMEDIA"), ("B", "教学楼B栋", "101", 50, "COMPUTER"),
        ("B", "教学楼B栋", "102", 50, "COMPUTER"), ("C", "实训楼C栋", "101", 40, "LAB"),
    ]:
        c = get(db, AaClassroom, building_code=building_code, room_code=room_no)
        if c is None:
            c = AaClassroom(tenant_id=TID, building_code=building_code, building_name=building_name,
                           room_code=room_no, room_name=f"{building_name}{room_no}", capacity=cap,
                           exam_seats=max(1, cap // 2), room_type=rtype, status="AVAILABLE")
            db.add(c)
            db.flush()
            bump("t_aa_classroom")
        classroom_ids.append(c.id)
    db.commit()

    lab_ids: list[int] = []
    for code, name, cap, ltype in [
        ("LAB-JD01", "机电一体化实训室", 30, "MECHANICAL"), ("LAB-RB01", "工业机器人实训室", 24, "MECHANICAL"),
        ("LAB-JS01", "软件开发实训室", 40, "COMPUTER"), ("LAB-HL01", "护理实训室", 32, "SKILL"),
    ]:
        lab = get(db, AaLabResource, lab_code=code)
        if lab is None:
            lab = AaLabResource(tenant_id=TID, lab_code=code, lab_name=name, capacity=cap, lab_type=ltype,
                               responsible_name=names[hash(code) % len(names)], status="AVAILABLE")
            db.add(lab)
            db.flush()
            bump("t_aa_lab_resource")
        lab_ids.append(lab.id)
    db.commit()

    equip_ids: list[int] = []
    for code, name, spec, owner_kind, owner_id, qty in [
        ("EQ-0001", "六轴工业机器人", "ABB IRB120", "LAB", lab_ids[1], 4),
        ("EQ-0002", "PLC实训台", "西门子S7-1200", "LAB", lab_ids[0], 10),
        ("EQ-0003", "台式计算机", "联想扬天M4000c", "LAB", lab_ids[2], 40),
        ("EQ-0004", "多媒体投影设备", "爱普生CB-X05", "CLASSROOM", classroom_ids[2], 1),
        ("EQ-0005", "护理模拟人", "高级综合模拟人", "LAB", lab_ids[3], 6),
    ]:
        e = get(db, AaEquipment, equipment_code=code)
        if e is None:
            e = AaEquipment(tenant_id=TID, equipment_code=code, equipment_name=name, spec_model=spec,
                           quantity=qty, owner_kind=owner_kind, owner_id=owner_id,
                           responsible_name=names[hash(code) % len(names)],
                           purchase_date="2024-08-15", status="IN_USE")
            db.add(e)
            db.flush()
            bump("t_aa_equipment")
        equip_ids.append(e.id)
    db.commit()
    return {"classroom": classroom_ids, "lab": lab_ids, "equipment": equip_ids}


def seed_resource_bookings_and_repairs(db, resources: dict[str, list[int]], teachers: dict[str, int]):
    from app.models import AaClassroomBooking, AaLabBooking, AaResourceRepair
    names = list(teachers.keys())
    if not db.scalars(select(AaClassroomBooking).where(AaClassroomBooking.tenant_id == TID)).first():
        db.add(AaClassroomBooking(tenant_id=TID, classroom_id=resources["classroom"][2],
                                  booking_date="2026-06-10", slot_no=6, purpose="教务处期末工作会",
                                  applicant_key="t_dong_kejian", applicant_name="董克建", status="APPROVED"))
        bump("t_aa_classroom_booking")
    if not db.scalars(select(AaLabBooking).where(AaLabBooking.tenant_id == TID)).first():
        db.add(AaLabBooking(tenant_id=TID, lab_id=resources["lab"][1], booking_date="2026-05-20", slot_no=5,
                            purpose="工业机器人技能竞赛集训", applicant_key="t_zhou_bin", applicant_name="周斌",
                            status="APPROVED"))
        bump("t_aa_lab_booking")
    if not db.scalars(select(AaResourceRepair).where(AaResourceRepair.tenant_id == TID)).first():
        db.add(AaResourceRepair(tenant_id=TID, resource_kind="EQUIPMENT", resource_id=resources["equipment"][0],
                                resource_label="六轴工业机器人(ABB IRB120)#1", fault_desc="第3轴伺服报警，无法归零",
                                reporter_key="t_zhou_bin", reporter_name="周斌", status="DONE",
                                repair_note="厂家工程师上门更换伺服驱动器，已恢复正常", resolved_at=datetime(2026, 4, 18, 15, 0)))
        bump("t_aa_resource_repair")
    db.commit()


def seed_teacher_availability(db, term_ids: dict[str, int], teachers: dict[str, int]):
    from app.models import AaTeacherAvailability
    cur_term = term_ids["2025-2026-2"]
    picks = [("t_dong_kejian", 5, 8, "行政值班"), ("t_liu_zhiqiang", 3, 5, "带队企业调研")]
    for login, weekday, slot_no, reason in picks:
        exists = db.scalars(select(AaTeacherAvailability).where(
            AaTeacherAvailability.tenant_id == TID, AaTeacherAvailability.teacher_key == login,
            AaTeacherAvailability.term_id == cur_term, AaTeacherAvailability.weekday == weekday,
            AaTeacherAvailability.slot_no == slot_no)).first()
        if exists:
            continue
        name = next((n for n, uid in teachers.items() if login.split("_", 1)[-1] in login), None)
        db.add(AaTeacherAvailability(tenant_id=TID, teacher_key=login, teacher_name=reason and
                                     [n for n, uid in teachers.items()][0], term_id=cur_term,
                                     weekday=weekday, slot_no=slot_no, reason=reason,
                                     status="ADOPTED", review_reason="学院已采纳"))
        bump("t_aa_teacher_availability")
    db.commit()


# ═══════════════════════ Phase 4：教学任务 + 排课 + 调停课 ═══════════════════════

def _class_roster(db, class_id: int) -> list[dict]:
    from app.models import StudentProfile
    rows = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == TID, StudentProfile.class_id == class_id,
        StudentProfile.is_deleted.is_(False))).all()
    return [{"id": s.id, "no": s.student_no, "name": s.real_name} for s in rows]


def seed_teaching_tasks(db, term_ids: dict[str, int], course_ids: dict[str, int],
                        teachers: dict[str, int]) -> dict:
    """本学期(2025-2026第二学期)为 25 级 6 个班各开 2 门专业课 + 1 门公共课，
    产出真实的教学任务批次+任务列表；下学期批次留 DRAFT 展示"筹备中"。"""
    from app.models import AaTeachingTask, AaTeachingTaskBatch
    cur_term = term_ids["2025-2026-2"]
    next_term = term_ids["2026-2027-1"]
    teacher_logins = [t[0] for t in TEACHER_SEED]
    teacher_names = {login: name for login, name, *_ in TEACHER_SEED}

    batch = get(db, AaTeachingTaskBatch, term_id=cur_term, batch_name="2025-2026学年第二学期教学任务")
    if batch is None:
        batch = AaTeachingTaskBatch(tenant_id=TID, term_id=cur_term,
                                    batch_name="2025-2026学年第二学期教学任务",
                                    generate_at=datetime(2026, 2, 10, 9, 0), status="APPROVED")
        db.add(batch)
        db.flush()
        bump("t_aa_teaching_task_batch")
    next_batch = get(db, AaTeachingTaskBatch, term_id=next_term, batch_name="2026-2027学年第一学期教学任务")
    if next_batch is None:
        next_batch = AaTeachingTaskBatch(tenant_id=TID, term_id=next_term,
                                         batch_name="2026-2027学年第一学期教学任务",
                                         status="DRAFT")
        db.add(next_batch)
        bump("t_aa_teaching_task_batch")
    db.commit()

    # code -> 课程名 一次性建全表，避免 next(generator, next(generator)) 的双重求值坑
    code_to_name: dict[str, str] = {c[0]: c[1] for c in PUBLIC_COURSES}
    for mid, courses in MAJOR_COURSES.items():
        for c in courses:
            code_to_name[f"M{mid}{c[0]}"] = c[1]

    task_ids: dict[str, int] = {}   # f"{class_id}:{course_code}" -> task_id
    teacher_pool = [(login, teacher_names[login]) for login in teacher_logins if login != "t_dong_kejian"]
    for i, class_id in enumerate(GRADE25_CLASSES):
        major_id = next(mid for mid, cls in CLASS_BY_MAJOR.items() if class_id in cls)
        roster = _class_roster(db, class_id)
        course_codes = [f"M{major_id}{s[0]}" for s in MAJOR_COURSES[major_id][:2]] + ["PUB002"]
        for j, code in enumerate(course_codes):
            key = f"{class_id}:{code}"
            existing = db.scalars(select(AaTeachingTask).where(
                AaTeachingTask.tenant_id == TID, AaTeachingTask.batch_id == batch.id,
                AaTeachingTask.class_id == class_id, AaTeachingTask.course_code == code)).first()
            if existing:
                task_ids[key] = existing.id
                continue
            login, tname = teacher_pool[(i * 3 + j) % len(teacher_pool)]
            cname = code_to_name[code]
            task = AaTeachingTask(tenant_id=TID, batch_id=batch.id, course_id=course_ids[code],
                                  course_code=code, course_name=cname, class_id=class_id,
                                  teaching_class_code=f"{class_id}-{code}",
                                  teaching_class_name=f"{cname}（{class_id}班教学班）",
                                  teacher_id=teachers.get(tname), teacher_key=login, teacher_name=tname,
                                  expected_students=len(roster), weekly_hours=3, total_hours=48,
                                  start_week=1, end_week=16,
                                  required_room_type="LAB" if code.startswith("M23") or code.startswith("M24")
                                  else ("COMPUTER" if code.startswith("M25") or code.startswith("M26") else None),
                                  confirm_at=datetime(2026, 2, 12, 10, 0), status="READY")
            db.add(task)
            db.flush()
            bump("t_aa_teaching_task")
            task_ids[key] = task.id
    db.commit()
    return {"batchId": batch.id, "nextBatchId": next_batch.id, "termId": cur_term, "taskIds": task_ids}


def seed_schedule(db, tt: dict, resources: dict[str, list[int]]) -> dict:
    from app.models import AaScheduleBatch, AaScheduleItem, AaSchedulePublish, AaScheduleRule
    batch = get(db, AaScheduleBatch, term_id=tt["termId"], batch_name="2025-2026学年第二学期课表")
    if batch is None:
        batch = AaScheduleBatch(tenant_id=TID, term_id=tt["termId"],
                                batch_name="2025-2026学年第二学期课表", status="PUBLISHED",
                                publish_at=datetime(2026, 2, 15, 9, 0))
        db.add(batch)
        db.flush()
        bump("t_aa_schedule_batch")
    db.commit()

    item_ids: dict[str, int] = {}
    classrooms = resources["classroom"]
    weekday_slot = [(1, 1), (2, 3), (4, 5)]
    for i, (key, task_id) in enumerate(tt["taskIds"].items()):
        class_id_s, code = key.split(":")
        class_id = int(class_id_s)
        exists = db.scalars(select(AaScheduleItem).where(
            AaScheduleItem.tenant_id == TID, AaScheduleItem.batch_id == batch.id,
            AaScheduleItem.task_id == task_id)).first()
        if exists:
            item_ids[key] = exists.id
            continue
        from app.models import AaTeachingTask
        task = db.get(AaTeachingTask, task_id)
        weekday, slot_no = weekday_slot[i % len(weekday_slot)]
        classroom_id = classrooms[i % len(classrooms)]
        from app.models import AaClassroom
        room = db.get(AaClassroom, classroom_id)
        item = AaScheduleItem(tenant_id=TID, batch_id=batch.id, task_id=task_id, course_id=task.course_id,
                              course_name=task.course_name, class_id=class_id,
                              class_name=task.teaching_class_name, teacher_key=task.teacher_key,
                              teacher_name=task.teacher_name, weekday=weekday, slot_no=slot_no,
                              start_week=1, end_week=16, week_parity="ALL", classroom_id=classroom_id,
                              classroom_text=room.room_name, status="EFFECTIVE", source="MANUAL")
        db.add(item)
        db.flush()
        bump("t_aa_schedule_item")
        item_ids[key] = item.id
    db.commit()

    if not db.scalars(select(AaSchedulePublish).where(AaSchedulePublish.tenant_id == TID,
                                                       AaSchedulePublish.batch_id == batch.id)).first():
        db.add(AaSchedulePublish(tenant_id=TID, batch_id=batch.id, term_id=tt["termId"], action="PUBLISH",
                                 operator_name="董克建", notified_count=len(set(
                                     t[0] for t in TEACHER_SEED)), note="学期初正式发布"))
        bump("t_aa_schedule_publish")
    for key, value in [("maxDailySlots", {"max": 4}), ("avoidEvening", {"enabled": True})]:
        if not db.scalars(select(AaScheduleRule).where(AaScheduleRule.tenant_id == TID,
                                                        AaScheduleRule.term_id == tt["termId"],
                                                        AaScheduleRule.batch_id.is_(None),
                                                        AaScheduleRule.rule_key == key)).first():
            db.add(AaScheduleRule(tenant_id=TID, term_id=tt["termId"], rule_key=key,
                                  rule_value_json=json.dumps(value), status="ENABLED"))
            bump("t_aa_schedule_rule(new)")
    db.commit()
    return {"batchId": batch.id, "itemIds": item_ids}


def seed_schedule_change(db, tt: dict, sched: dict):
    from app.models import AaScheduleItem, AaScheduleChange
    first_key = next(iter(sched["itemIds"]))
    item = db.get(AaScheduleItem, sched["itemIds"][first_key])
    exists = db.scalars(select(AaScheduleChange).where(
        AaScheduleChange.tenant_id == TID, AaScheduleChange.origin_item_id == item.id)).first()
    if exists:
        return
    change = AaScheduleChange(
        tenant_id=TID, term_id=tt["termId"], batch_id=sched["batchId"], origin_item_id=item.id,
        task_id=item.task_id, change_type="ADJUST", course_name=item.course_name, class_id=item.class_id,
        class_name=item.class_name, teacher_key=item.teacher_key, teacher_name=item.teacher_name,
        origin_weekday=item.weekday, origin_slot_no=item.slot_no, origin_start_week=item.start_week,
        origin_end_week=item.end_week, origin_week_parity=item.week_parity, origin_classroom=item.classroom_text,
        target_weekday=item.weekday + 1 if item.weekday < 5 else 1, target_slot_no=item.slot_no,
        target_start_week=item.start_week, target_end_week=item.end_week, target_week_parity=item.week_parity,
        target_classroom=item.classroom_text, reason="任课教师因参加省级技能大赛培训，申请与下一自然日对调课位",
        applicant_id=None, status="APPLIED", applied_at=datetime(2026, 4, 10, 8, 30),
        new_item_id=None)
    db.add(change)
    bump("t_aa_schedule_change")
    db.commit()


# ═══════════════════════ Phase 5：选课全流程（选修课，全校学生可报） ═══════════════════════

def seed_selection(db, term_ids: dict[str, int], course_ids: dict[str, int], tt: dict):
    from app.models import (AaSelectionBatch, AaSelectionCourse, AaSelectionRecord, AaSelectionRound,
                            StudentProfile)
    cur_term = term_ids["2025-2026-2"]
    batch = get(db, AaSelectionBatch, term_id=cur_term, batch_name="2025-2026学年第二学期公选课选课")
    if batch is None:
        batch = AaSelectionBatch(tenant_id=TID, term_id=cur_term,
                                 batch_name="2025-2026学年第二学期公选课选课",
                                 select_start_at=datetime(2026, 2, 24, 8, 0),
                                 select_end_at=datetime(2026, 3, 2, 23, 59),
                                 apply_scope_json=json.dumps({"grades": ["2025"]}),
                                 rule_json=json.dumps({"maxCredits": 6}), status="LOCKED",
                                 locked_at=datetime(2026, 3, 3, 9, 0))
        db.add(batch)
        db.flush()
        bump("t_aa_selection_batch")
    db.commit()

    rnd = db.scalars(select(AaSelectionRound).where(AaSelectionRound.tenant_id == TID,
                                                     AaSelectionRound.batch_id == batch.id)).first()
    if rnd is None:
        rnd = AaSelectionRound(tenant_id=TID, batch_id=batch.id, round_no=1, round_name="正选（先到先得）",
                               mode="FCFS", start_at=datetime(2026, 2, 24, 8, 0),
                               end_at=datetime(2026, 3, 2, 23, 59), allow_enroll=True, allow_drop=True,
                               status="CLOSED")
        db.add(rnd)
        db.flush()
        bump("t_aa_selection_round")
    db.commit()

    elective_codes = ["M25004", "M22003", "M26003"]  # 软件测试技术/跨境电商实务/数据可视化
    sel_course_ids: dict[str, int] = {}
    for code in elective_codes:
        sc = db.scalars(select(AaSelectionCourse).where(AaSelectionCourse.tenant_id == TID,
                                                         AaSelectionCourse.batch_id == batch.id,
                                                         AaSelectionCourse.course_id == course_ids[code])).first()
        if sc is None:
            sc = AaSelectionCourse(tenant_id=TID, batch_id=batch.id, course_id=course_ids[code],
                                   course_name=code, credit=Decimal("2.0"), capacity=40, min_capacity=10,
                                   selected_count=0, status="OPEN")
            db.add(sc)
            db.flush()
            bump("t_aa_selection_course")
        sel_course_ids[code] = sc.id
    db.commit()

    enrolled = 0
    for ci, class_id in enumerate(GRADE25_CLASSES):
        roster = _class_roster(db, class_id)
        code = elective_codes[ci % len(elective_codes)]
        sc = db.get(AaSelectionCourse, sel_course_ids[code])
        for stu in roster[:4]:
            exists = db.scalars(select(AaSelectionRecord).where(
                AaSelectionRecord.tenant_id == TID, AaSelectionRecord.batch_id == batch.id,
                AaSelectionRecord.selection_course_id == sc.id, AaSelectionRecord.student_id == stu["id"])).first()
            if exists:
                continue
            db.add(AaSelectionRecord(tenant_id=TID, batch_id=batch.id, selection_course_id=sc.id,
                                     course_id=sc.course_id, course_name=code, credit=sc.credit,
                                     student_id=stu["id"], student_no=stu["no"], student_name=stu["name"],
                                     enrolled_at=datetime(2026, 2, 25, 10, 0), round_id=rnd.id,
                                     status="SELECTED"))
            sc.selected_count = (sc.selected_count or 0) + 1
            bump("t_aa_selection_record")
            enrolled += 1
    db.commit()
    return {"batchId": batch.id, "selectionCourseIds": sel_course_ids, "enrolled": enrolled}


# ═══════════════════════ Phase 6：课堂考勤 + 班级调整 ═══════════════════════

def seed_attendance(db, tt: dict):
    from app.models import AaAttendanceSession, AaTeachingTask
    count = 0
    for i, (key, task_id) in enumerate(list(tt["taskIds"].items())[:6]):
        task = db.get(AaTeachingTask, task_id)
        for wk_offset, sdate in enumerate(["2026-03-02", "2026-03-09", "2026-03-16"]):
            exists = db.scalars(select(AaAttendanceSession).where(
                AaAttendanceSession.tenant_id == TID, AaAttendanceSession.class_id == task.class_id,
                AaAttendanceSession.session_date == sdate, AaAttendanceSession.course_name == task.course_name
            )).first()
            if exists:
                continue
            roster = _class_roster(db, task.class_id)
            roster_rows = [{"studentId": s["id"], "studentNo": s["no"], "realName": s["name"],
                            "status": "ABSENT" if idx == 0 and wk_offset == 1 else "PRESENT"}
                          for idx, s in enumerate(roster)]
            absent = sum(1 for r in roster_rows if r["status"] != "PRESENT")
            db.add(AaAttendanceSession(tenant_id=TID, class_id=task.class_id, course_name=task.course_name,
                                       term_code="2025-2026-2", teacher_key=task.teacher_key,
                                       session_date=sdate, slot_no=1, session_type="常规",
                                       roster_json=json.dumps(roster_rows, ensure_ascii=False),
                                       total_count=len(roster_rows), present_count=len(roster_rows) - absent,
                                       absent_count=absent, status="SUBMITTED"))
            bump("t_aa_attendance_session")
            count += 1
    db.commit()
    return count


def seed_class_adjustment(db):
    from app.models import AaClassAdjustmentRequest
    exists = db.scalars(select(AaClassAdjustmentRequest).where(
        AaClassAdjustmentRequest.tenant_id == TID)).first()
    if exists:
        return
    db.add(AaClassAdjustmentRequest(
        tenant_id=TID, adjust_type="MERGE", from_class_ids=json.dumps([45, 46]), to_class_id=45,
        reason="26康复2班本学期新生报到人数不足开班标准，与25康复2班合并教学班组织公共课教学（行政班学籍不变）",
        check_result_json=json.dumps({"passed": True, "conflicts": []}),
        checked_at=datetime(2026, 2, 20, 9, 0), status="CHECKED"))
    bump("t_aa_class_adjustment_request")
    db.commit()


# ═══════════════════════ Phase 7：考务全流程（期末考试） ═══════════════════════

def seed_exam(db, term_ids: dict[str, int], tt: dict) -> dict:
    from app.models import (AaExamAuditTrail, AaExamBatch, AaExamCourse, AaExamIncident, AaExamInvigilator,
                            AaExamPatrol, AaExamRoom, AaExamRoomStudent, AaTeachingTask)
    cur_term = term_ids["2025-2026-2"]
    batch = get(db, AaExamBatch, term_id=cur_term, batch_name="2025-2026学年第二学期期末考试")
    if batch is None:
        batch = AaExamBatch(tenant_id=TID, term_id=cur_term, batch_name="2025-2026学年第二学期期末考试",
                            exam_type="FINAL", exam_week_start=17, exam_week_end=18,
                            published_at=datetime(2026, 6, 10, 9, 0), status="FINISHED")
        db.add(batch)
        db.flush()
        bump("t_aa_exam_batch")
    db.commit()

    exam_course_ids: dict[str, int] = {}
    room_ids: dict[str, int] = {}
    exam_keys = [k for k in tt["taskIds"] if not k.split(":")[1].startswith("PUB")][:6]
    for i, key in enumerate(exam_keys):
        task = db.get(AaTeachingTask, tt["taskIds"][key])
        ec = db.scalars(select(AaExamCourse).where(AaExamCourse.tenant_id == TID,
                                                    AaExamCourse.batch_id == batch.id,
                                                    AaExamCourse.teaching_task_id == task.id)).first()
        if ec is None:
            college_id = next((cid for cid, majors in MAJOR_BY_COLLEGE.items()
                              for mid in majors if f"M{mid}" in task.course_code), None)
            ec = AaExamCourse(tenant_id=TID, batch_id=batch.id, teaching_task_id=task.id, course_id=task.course_id,
                             course_name=task.course_name, class_id=task.class_id, class_name=task.teaching_class_name,
                             college_id=college_id, teacher_key=task.teacher_key, teacher_name=task.teacher_name,
                             expected_students=task.expected_students,
                             exam_date=f"2026-06-2{2 + i % 5}", start_time="09:00", end_time="10:40",
                             duration_minutes=100, status="CONFIRMED")
            db.add(ec)
            db.flush()
            bump("t_aa_exam_course")
        exam_course_ids[key] = ec.id

        room = db.scalars(select(AaExamRoom).where(AaExamRoom.tenant_id == TID,
                                                    AaExamRoom.exam_course_id == ec.id)).first()
        if room is None:
            room = AaExamRoom(tenant_id=TID, exam_course_id=ec.id, room_seq=1, classroom_text="教学楼A栋201",
                             capacity=80, planned_count=ec.expected_students or 8, seat_mode="SEQUENTIAL",
                             source="MANUAL", status="ACTIVE")
            db.add(room)
            db.flush()
            bump("t_aa_exam_room")
        room_ids[key] = room.id

        roster = _class_roster(db, task.class_id)
        for seat, stu in enumerate(roster, start=1):
            exists = db.scalars(select(AaExamRoomStudent).where(
                AaExamRoomStudent.tenant_id == TID, AaExamRoomStudent.exam_course_id == ec.id,
                AaExamRoomStudent.student_id == stu["id"])).first()
            if exists:
                continue
            db.add(AaExamRoomStudent(tenant_id=TID, exam_room_id=room.id, exam_course_id=ec.id,
                                     student_id=stu["id"], student_no=stu["no"], student_name=stu["name"],
                                     seat_no=seat, admission_no=f"{ec.id}{seat:03d}",
                                     attendance_status="ABSENT" if seat == 1 and i == 0 else "PRESENT"))
            bump("t_aa_exam_room_student")

        chief = get(db, AaExamInvigilator, exam_room_id=room.id) if False else None
        if not db.scalars(select(AaExamInvigilator).where(AaExamInvigilator.tenant_id == TID,
                                                           AaExamInvigilator.exam_room_id == room.id)).first():
            invig_login = [t[0] for t in TEACHER_SEED if t[0] != task.teacher_key][i % 15]
            invig_name = next(t[1] for t in TEACHER_SEED if t[0] == invig_login)
            db.add(AaExamInvigilator(tenant_id=TID, exam_room_id=room.id, teacher_key=invig_login,
                                     teacher_name=invig_name, role="CHIEF", confirm_status="CONFIRMED"))
            bump("t_aa_exam_invigilator")
    db.commit()

    if not db.scalars(select(AaExamPatrol).where(AaExamPatrol.tenant_id == TID, AaExamPatrol.batch_id == batch.id)).first():
        db.add(AaExamPatrol(tenant_id=TID, batch_id=batch.id, teacher_key="t_luo_yaqin", teacher_name="罗雅琴",
                            patrol_date="2026-06-22", start_time="09:00", end_time="10:40",
                            area_scope_json=json.dumps({"buildings": ["A栋", "B栋"]}), status="ASSIGNED"))
        bump("t_aa_exam_patrol")

    first_key = exam_keys[0]
    first_ec_id = exam_course_ids[first_key]
    absent_student = _class_roster(db, db.get(AaTeachingTask, tt["taskIds"][first_key]).class_id)[0]
    if not db.scalars(select(AaExamIncident).where(AaExamIncident.tenant_id == TID,
                                                    AaExamIncident.exam_course_id == first_ec_id)).first():
        db.add(AaExamIncident(tenant_id=TID, exam_room_id=room_ids[first_key], exam_course_id=first_ec_id,
                              student_id=absent_student["id"], student_no=absent_student["no"],
                              student_name=absent_student["name"], incident_type="ABSENT",
                              description="考试当日请假未到场（已由辅导员核实为因病请假）",
                              recorded_by="董克建", recorded_at=datetime(2026, 6, 22, 10, 40),
                              risk_alert_sent=True, status="ACTIVE"))
        bump("t_aa_exam_incident")

    if not db.scalars(select(AaExamAuditTrail).where(AaExamAuditTrail.tenant_id == TID)).first():
        db.add(AaExamAuditTrail(tenant_id=TID, biz_type="EXAM_BATCH", biz_id=batch.id, action="PUBLISH",
                                operator="董克建", role_name="教务处管理员", detail="考试批次发布通知任课教师与监考教师",
                                occurred_at=datetime(2026, 6, 10, 9, 0)))
        bump("t_aa_exam_audit_trail")
    db.commit()
    return {"batchId": batch.id, "examCourseIds": exam_course_ids, "absentStudent": absent_student,
           "firstExamCourseId": first_ec_id}


# ═══════════════════════ Phase 8：成绩全流程 ═══════════════════════

def seed_grades(db, term_ids: dict[str, int], tt: dict) -> dict:
    from app.models import (AaDeferredExam, AaGradeRecheck, AaGradeRecord, AaGradeTask, AaMakeupBatch,
                            AaRetakeApply, AaTeachingTask)
    cur_term = term_ids["2025-2026-2"]
    task_ids: dict[str, int] = {}
    record_ids: list[tuple[str, int, int]] = []  # (key, student_id, record_id)
    fail_student = None
    for key, teaching_task_id in tt["taskIds"].items():
        tt_row = db.get(AaTeachingTask, teaching_task_id)
        gt = db.scalars(select(AaGradeTask).where(AaGradeTask.tenant_id == TID,
                                                   AaGradeTask.teaching_task_id == teaching_task_id)).first()
        if gt is None:
            gt = AaGradeTask(tenant_id=TID, teaching_task_id=teaching_task_id, term_id=cur_term,
                             term_code="2025-2026-2", course_id=tt_row.course_id, course_name=tt_row.course_name,
                             class_id=tt_row.class_id, teacher_key=tt_row.teacher_key, credit=Decimal("3.0"),
                             usual_ratio=30, midterm_ratio=0, final_ratio=70, pass_line=60,
                             status="PUBLISHED", submitted_at=datetime(2026, 7, 1, 10, 0),
                             college_reviewed_at=datetime(2026, 7, 2, 9, 0), academic_reviewed_at=datetime(2026, 7, 3, 9, 0),
                             publish_at=datetime(2026, 7, 4, 9, 0))
            db.add(gt)
            db.flush()
            bump("t_aa_grade_task")
        task_ids[key] = gt.id

        roster = _class_roster(db, tt_row.class_id)
        for idx, stu in enumerate(roster):
            exists = db.scalars(select(AaGradeRecord).where(AaGradeRecord.tenant_id == TID,
                                                             AaGradeRecord.task_id == gt.id,
                                                             AaGradeRecord.student_id == stu["id"])).first()
            if exists:
                record_ids.append((key, stu["id"], exists.id))
                continue
            is_last_in_class = idx == len(roster) - 1
            usual = 75 + (idx * 3) % 20
            final = 38 + (idx * 5) % 15 if is_last_in_class else 55 + (idx * 7) % 40
            total = round(usual * 0.3 + final * 0.7)
            pass_status = "PASSED" if total >= 60 else "FAILED"
            if pass_status == "FAILED" and fail_student is None:
                fail_student = (key, stu, gt.id)
            rec = AaGradeRecord(tenant_id=TID, task_id=gt.id, student_id=stu["id"], usual_score=usual,
                                final_score=final, total_score=total, pass_status=pass_status,
                                source="PUBLISH", version_no=1, exception_flag="NORMAL")
            db.add(rec)
            db.flush()
            bump("t_aa_grade_record")
            record_ids.append((key, stu["id"], rec.id))
    db.commit()

    # 成绩复查：找一个高分学生对已发布成绩发起复查，教务维持原成绩
    recheck_key, recheck_stu_id, recheck_rec_id = record_ids[3]
    stu_info = next(s for s in _class_roster(db, db.get(AaTeachingTask, tt["taskIds"][recheck_key]).class_id)
                    if s["id"] == recheck_stu_id)
    if not db.scalars(select(AaGradeRecheck).where(AaGradeRecheck.tenant_id == TID,
                                                    AaGradeRecheck.student_id == recheck_stu_id)).first():
        rec = db.get(AaGradeRecord, recheck_rec_id)
        db.add(AaGradeRecheck(tenant_id=TID, student_id=recheck_stu_id, student_no=stu_info["no"],
                              student_name=stu_info["name"], acad_grade_id=recheck_rec_id,
                              course_name=recheck_key, term="2025-2026学年第二学期",
                              original_score=rec.total_score, reason="对期末卷面得分有疑问，申请核对复查",
                              status="UPHELD", review_note="经复核，原评卷无误，成绩维持不变",
                              reviewed_by="董克建", reviewed_at=datetime(2026, 7, 8, 10, 0)))
        bump("t_aa_grade_recheck")
    db.commit()

    # 补考批次：圈定不及格课程
    mb = get(db, AaMakeupBatch, batch_name="2025-2026学年第二学期期末补考")
    if mb is None:
        mb = AaMakeupBatch(tenant_id=TID, batch_name="2025-2026学年第二学期期末补考", kind="MAKEUP",
                           term_id=cur_term, term_code="2025-2026-2", score_rule="CAP60",
                           published_at=datetime(2026, 7, 12, 9, 0), status="FINISHED")
        db.add(mb)
        bump("t_aa_makeup_batch")
    db.commit()

    # 重修申请：不及格学生申请重修
    if fail_student:
        key, stu, gt_id = fail_student
        task = db.get(AaTeachingTask, tt["taskIds"][key])
        if not db.scalars(select(AaRetakeApply).where(AaRetakeApply.tenant_id == TID,
                                                       AaRetakeApply.student_id == stu["id"],
                                                       AaRetakeApply.course_id == task.course_id)).first():
            db.add(AaRetakeApply(tenant_id=TID, student_id=stu["id"], student_no=stu["no"],
                                 student_name=stu["name"], course_id=task.course_id, course_name=task.course_name,
                                 term_code="2025-2026-2", reason="期末考试未达及格线，申请随下一开课班级重修",
                                 retake_count=1, review_reason="同意重修安排", status="APPROVED"))
            bump("t_aa_retake_apply")

    # 缓考：因病请假的学生（复用考务缺考事件里那名学生）
    exam_incident_key = exam_keys_first = list(tt["taskIds"].keys())[0]
    from app.models import AaExamCourse
    first_task_id = tt["taskIds"][exam_incident_key]
    ec = db.scalars(select(AaExamCourse).where(AaExamCourse.tenant_id == TID,
                                                AaExamCourse.teaching_task_id == first_task_id)).first()
    if ec:
        absent_stu = _class_roster(db, db.get(AaTeachingTask, first_task_id).class_id)[0]
        if not db.scalars(select(AaDeferredExam).where(AaDeferredExam.tenant_id == TID,
                                                        AaDeferredExam.student_id == absent_stu["id"],
                                                        AaDeferredExam.exam_course_id == ec.id)).first():
            db.add(AaDeferredExam(tenant_id=TID, student_id=absent_stu["id"], student_no=absent_stu["no"],
                                  student_name=absent_stu["name"], exam_course_id=ec.id, course_name=ec.course_name,
                                  reason_type="SICK", reason="考试当日发热就医，附医院病历及诊断证明",
                                  apply_at=datetime(2026, 6, 22, 8, 0), status="APPROVED"))
            bump("t_aa_deferred_exam")
    db.commit()
    return {"gradeTaskIds": task_ids, "recordCount": len(record_ids)}


def seed_grade_recognition_and_workload(db, term_ids: dict[str, int], course_ids: dict[str, int], teachers: dict[str, int]):
    from app.models import AaGradeRecognition, AaWorkloadDeclaration
    # 成绩认定：转专业学生用原专业课程成绩替代现专业计划课程
    stu = _class_roster(db, GRADE25_CLASSES[0])[-1]
    if not db.scalars(select(AaGradeRecognition).where(AaGradeRecognition.tenant_id == TID,
                                                        AaGradeRecognition.student_id == stu["id"])).first():
        db.add(AaGradeRecognition(tenant_id=TID, student_id=stu["id"], student_no=stu["no"],
                                  student_name=stu["name"], source_course_name="机械制图与CAD",
                                  source_score=82, source_credit=Decimal("4.0"), source_origin="转专业前原专业已修课程",
                                  target_course_id=course_ids["M23001"], target_course_name="机械制图与CAD",
                                  reason="转专业学生，原专业已修同名课程且成绩合格，申请替代认定",
                                  review_reason="课程内容一致，予以认定", reviewed_by="董克建",
                                  reviewed_at=datetime(2026, 3, 10, 10, 0), status="APPROVED"))
        bump("t_aa_grade_recognition")
    db.commit()

    cur_term_code = "2025-2026-2"
    for login, name, *_ in TEACHER_SEED[:6]:
        for category, hours, desc in [("TEACHING", 48, "本学期课堂教学课时"),
                                      ("INVIGILATE", 4, "期末考试监考")]:
            exists = db.scalars(select(AaWorkloadDeclaration).where(
                AaWorkloadDeclaration.tenant_id == TID, AaWorkloadDeclaration.teacher_key == login,
                AaWorkloadDeclaration.term_code == cur_term_code, AaWorkloadDeclaration.category == category)).first()
            if exists:
                continue
            db.add(AaWorkloadDeclaration(tenant_id=TID, teacher_key=login, teacher_name=name,
                                         term_code=cur_term_code, category=category, hours=Decimal(str(hours)),
                                         description=desc, status="APPROVED", reviewed_by="董克建",
                                         reviewed_at=datetime(2026, 7, 5, 9, 0)))
            bump("t_aa_workload_declaration")
    db.commit()


# ═══════════════════════ Phase 9：评教全流程 ═══════════════════════

def seed_evaluation(db, term_ids: dict[str, int], tt: dict):
    from app.models import (AaEvaluationAppeal, AaEvaluationBatch, AaEvaluationRecord, AaEvaluationResult,
                            AaEvaluationTask, AaTeachingTask)
    cur_term = term_ids["2025-2026-2"]
    batch = get(db, AaEvaluationBatch, term_id=cur_term, batch_name="2025-2026学年第二学期学生评教")
    if batch is None:
        batch = AaEvaluationBatch(tenant_id=TID, term_id=cur_term, batch_name="2025-2026学年第二学期学生评教",
                                  scope_json=json.dumps({"grades": ["2025"]}),
                                  template_json=json.dumps({"objective": ["教学态度认真", "内容讲解清晰",
                                                                        "课堂互动充分", "作业批改及时", "考核公平合理"],
                                                            "subjective": "本学期对该课程的意见或建议"}, ensure_ascii=False),
                                  anonymous=True, window_start=datetime(2026, 6, 15, 0, 0),
                                  window_end=datetime(2026, 6, 21, 23, 59),
                                  result_published_at=datetime(2026, 6, 25, 9, 0), status="RESULT_READY")
        db.add(batch)
        db.flush()
        bump("t_aa_evaluation_batch")
    db.commit()

    result_ids: dict[str, int] = {}
    for key, task_id in list(tt["taskIds"].items())[:8]:
        task = db.get(AaTeachingTask, task_id)
        et = db.scalars(select(AaEvaluationTask).where(AaEvaluationTask.tenant_id == TID,
                                                        AaEvaluationTask.batch_id == batch.id,
                                                        AaEvaluationTask.teaching_task_id == task_id,
                                                        AaEvaluationTask.evaluator_type == "STUDENT")).first()
        roster = _class_roster(db, task.class_id)
        if et is None:
            et = AaEvaluationTask(tenant_id=TID, batch_id=batch.id, teaching_task_id=task_id,
                                  course_id=task.course_id, course_name=task.course_name, class_id=task.class_id,
                                  teacher_key=task.teacher_key, teacher_name=task.teacher_name,
                                  evaluator_type="STUDENT", submitted_count=len(roster), status="SUBMITTED")
            db.add(et)
            db.flush()
            bump("t_aa_evaluation_task")

            scores = []
            for i in range(len(roster)):
                score = 82 + (i * 3) % 16
                scores.append(score)
                db.add(AaEvaluationRecord(tenant_id=TID, batch_id=batch.id, task_id=et.id,
                                          teacher_key=task.teacher_key, evaluator_type="STUDENT",
                                          answers_json=json.dumps({"objective": [score] * 5}),
                                          objective_score=Decimal(str(score)),
                                          comment="老师讲课很认真，希望多一些案例练习" if score > 90 else None))
                bump("t_aa_evaluation_record")
            avg = round(sum(scores) / len(scores), 2)
            level = "EXCELLENT" if avg >= 90 else "GOOD" if avg >= 80 else "PASS" if avg >= 70 else "NEED_IMPROVE"
            result = AaEvaluationResult(tenant_id=TID, batch_id=batch.id, teaching_task_id=task_id,
                                        teacher_key=task.teacher_key, teacher_name=task.teacher_name,
                                        course_name=task.course_name, student_avg=Decimal(str(avg)),
                                        student_count=len(scores), composite_score=Decimal(str(avg)),
                                        level=level, published=True)
            db.add(result)
            db.flush()
            bump("t_aa_evaluation_result")
            result_ids[key] = result.id
        else:
            existing = db.scalars(select(AaEvaluationResult).where(
                AaEvaluationResult.tenant_id == TID, AaEvaluationResult.batch_id == batch.id,
                AaEvaluationResult.teaching_task_id == task_id)).first()
            if existing:
                result_ids[key] = existing.id
    db.commit()

    # 找一个 NEED_IMPROVE 的结果发起申诉；若没有则用最低分那条
    from app.models import AaEvaluationResult as ER
    low = db.scalars(select(ER).where(ER.tenant_id == TID, ER.batch_id == batch.id)
                     .order_by(ER.student_avg)).first()
    if low and not db.scalars(select(AaEvaluationAppeal).where(AaEvaluationAppeal.tenant_id == TID,
                                                               AaEvaluationAppeal.result_id == low.id)).first():
        db.add(AaEvaluationAppeal(tenant_id=TID, result_id=low.id, teacher_key=low.teacher_key,
                                  reason="本学期因病请假调课较多，评价样本量偏小，申请复核评分口径",
                                  review_reason="经核实评价流程无误，维持原结果，建议下学期加强课堂互动",
                                  status="RESOLVED"))
        bump("t_aa_evaluation_appeal")
    db.commit()


# ═══════════════════════ Phase 10：学籍事务（异动/注册/等级考/分流/更正） ═══════════════════════

def seed_status_change_and_registration(db, term_ids: dict[str, int]):
    from app.models import AaRegistration, AaRegistrationBatch, AaRegistrationDeferral, AaStatusChange
    cur_term = term_ids["2025-2026-2"]
    batch = get(db, AaRegistrationBatch, batch_name="2025-2026学年第二学期学期注册")
    if batch is None:
        batch = AaRegistrationBatch(tenant_id=TID, batch_name="2025-2026学年第二学期学期注册",
                                    register_type="SEMESTER", term_id=cur_term,
                                    window_start=datetime(2026, 2, 20, 0, 0), window_end=datetime(2026, 2, 23, 23, 59),
                                    scope_json=json.dumps({"grades": ["2025"]}), status="CLOSED")
        db.add(batch)
        db.flush()
        bump("t_aa_registration_batch")
    db.commit()

    roster25 = [s for cid in GRADE25_CLASSES for s in _class_roster(db, cid)]
    for stu in roster25:
        exists = db.scalars(select(AaRegistration).where(AaRegistration.tenant_id == TID,
                                                          AaRegistration.batch_id == batch.id,
                                                          AaRegistration.student_id == stu["id"])).first()
        if exists:
            continue
        db.add(AaRegistration(tenant_id=TID, batch_id=batch.id, student_id=stu["id"],
                              precheck_json=json.dumps({"feeStatus": "PAID", "materialStatus": "COMPLETE"}),
                              register_at=datetime(2026, 2, 22, 9, 0), status="REGISTERED",
                              eligibility_status="ELIGIBLE", eligibility_checked_at=datetime(2026, 2, 21, 9, 0)))
        bump("t_aa_registration")
    db.commit()

    exc_stu = roster25[-2]
    from app.models import AaRegistrationException
    if not db.scalars(select(AaRegistrationException).where(AaRegistrationException.tenant_id == TID,
                                                             AaRegistrationException.student_id == exc_stu["id"])).first():
        db.add(AaRegistrationException(tenant_id=TID, batch_id=batch.id, student_id=exc_stu["id"],
                                       exception_type="UNPAID", description="学费未按时缴清，报到时系统核验未通过",
                                       status="RESOLVED", resolution_note="学生已于次日补缴学费，核验通过",
                                       resolved_at=datetime(2026, 2, 23, 15, 0)))
        bump("t_aa_registration_exception")
    db.commit()

    late_stu = roster25[-1]
    if not db.scalars(select(AaRegistrationDeferral).where(AaRegistrationDeferral.tenant_id == TID,
                                                            AaRegistrationDeferral.student_id == late_stu["id"])).first():
        db.add(AaRegistrationDeferral(tenant_id=TID, batch_id=batch.id, student_id=late_stu["id"],
                                      reason="学生本人因术后恢复，申请延后一周办理注册手续",
                                      requested_until=datetime(2026, 3, 2, 23, 59), status="APPROVED",
                                      review_note="同意延期，已知会辅导员跟踪", reviewed_at=datetime(2026, 2, 21, 14, 0)))
        bump("t_aa_registration_deferral")
    db.commit()

    # 学籍异动：休学
    susp_stu = _class_roster(db, GRADE25_CLASSES[1])[0]
    if not db.scalars(select(AaStatusChange).where(AaStatusChange.tenant_id == TID,
                                                    AaStatusChange.student_id == susp_stu["id"],
                                                    AaStatusChange.change_type == "SUSPEND")).first():
        db.add(AaStatusChange(tenant_id=TID, student_id=susp_stu["id"], change_type="SUSPEND",
                              from_status="NORMAL", to_status="SUSPENDED",
                              reason="因病需长期治疗，申请休学一年（已脱敏展示）",
                              effective_date=datetime(2026, 3, 15), expire_date=datetime(2027, 3, 15),
                              term_code="2025-2026-2", status="EFFECTIVE"))
        bump("t_aa_status_change")
    db.commit()


def seed_level_exam(db):
    from app.models import AaLevelExam, AaLevelExamReg
    exam = get(db, AaLevelExam, exam_name="2026年上半年全国计算机等级考试(二级)")
    if exam is None:
        exam = AaLevelExam(tenant_id=TID, exam_name="2026年上半年全国计算机等级考试(二级)", category="SKILL",
                           level="二级", exam_date="2026-03-28", fee=Decimal("120.00"),
                           reg_start=datetime(2026, 2, 1), reg_end=datetime(2026, 2, 28),
                           pass_line=60, status="FINISHED")
        db.add(exam)
        db.flush()
        bump("t_aa_level_exam")
    db.commit()
    roster = _class_roster(db, 39) + _class_roster(db, 41)  # 软件+大数据班学生报考
    for i, stu in enumerate(roster[:6]):
        exists = db.scalars(select(AaLevelExamReg).where(AaLevelExamReg.tenant_id == TID,
                                                          AaLevelExamReg.exam_id == exam.id,
                                                          AaLevelExamReg.student_id == stu["id"])).first()
        if exists:
            continue
        score = 55 + i * 8
        db.add(AaLevelExamReg(tenant_id=TID, exam_id=exam.id, student_id=stu["id"], student_no=stu["no"],
                              student_name=stu["name"], fee_status="PAID", score=score,
                              result="PASS" if score >= 60 else "FAIL",
                              cert_no=f"NCRE2026-{stu['id']:05d}" if score >= 60 else None, status="SCORED"))
        bump("t_aa_level_exam_reg")
    db.commit()


def seed_major_split_and_correction(db):
    from app.models import AaMajorDirection, AaMajorSplitBatch, AaMajorSplitOption, AaMajorSplitVolunteer, AaStudentCorrection
    for major_id, direction_names in [(25, ["前端开发方向", "后端开发方向"]), (26, ["数据分析方向", "数据工程方向"])]:
        for i, dname in enumerate(direction_names):
            code = f"D{major_id}{i+1}"
            if not db.scalars(select(AaMajorDirection).where(AaMajorDirection.tenant_id == TID,
                                                              AaMajorDirection.major_id == major_id,
                                                              AaMajorDirection.code == code)).first():
                db.add(AaMajorDirection(tenant_id=TID, major_id=major_id, direction_name=dname, code=code,
                                        status="ACTIVE"))
                bump("t_aa_major_direction")
    db.commit()

    batch = get(db, AaMajorSplitBatch, batch_name="2026级大类招生专业分流")
    if batch is None:
        batch = AaMajorSplitBatch(tenant_id=TID, batch_name="2026级大类招生专业分流", grade="2026",
                                  source_major_id=None, max_choices=2,
                                  volunteer_start=datetime(2026, 6, 1), volunteer_end=datetime(2026, 6, 15),
                                  status="CONFIRMED")
        db.add(batch)
        db.flush()
        bump("t_aa_major_split_batch")
    db.commit()
    for major_id in (25, 26):
        if not db.scalars(select(AaMajorSplitOption).where(AaMajorSplitOption.tenant_id == TID,
                                                            AaMajorSplitOption.batch_id == batch.id,
                                                            AaMajorSplitOption.major_id == major_id)).first():
            db.add(AaMajorSplitOption(tenant_id=TID, batch_id=batch.id, major_id=major_id,
                                      major_name=MAJOR_NAME[major_id], capacity=30, allocated_count=4))
            bump("t_aa_major_split_option")
    db.commit()
    roster26 = _class_roster(db, GRADE26_CLASSES[0])[:4]
    for i, stu in enumerate(roster26):
        if not db.scalars(select(AaMajorSplitVolunteer).where(AaMajorSplitVolunteer.tenant_id == TID,
                                                               AaMajorSplitVolunteer.batch_id == batch.id,
                                                               AaMajorSplitVolunteer.student_id == stu["id"])).first():
            choices = [25, 26] if i % 2 == 0 else [26, 25]
            db.add(AaMajorSplitVolunteer(tenant_id=TID, batch_id=batch.id, student_id=stu["id"],
                                         student_no=stu["no"], student_name=stu["name"],
                                         choices_json=json.dumps(choices), gpa_snapshot=Decimal(f"{3.2 + i * 0.1:.2f}"),
                                         result_major_id=choices[0], result_choice_rank=1, status="CONFIRMED"))
            bump("t_aa_major_split_volunteer")
    db.commit()

    corr_stu = _class_roster(db, GRADE25_CLASSES[2])[0]
    if not db.scalars(select(AaStudentCorrection).where(AaStudentCorrection.tenant_id == TID,
                                                         AaStudentCorrection.student_id == corr_stu["id"])).first():
        db.add(AaStudentCorrection(tenant_id=TID, student_id=corr_stu["id"], field_key="REAL_NAME",
                                   old_value=corr_stu["name"], new_value=corr_stu["name"],
                                   reason="身份证姓名与录入系统姓名用字有误（同音异形字），据户籍部门证明更正",
                                   status="APPROVED", review_note="材料齐全，予以更正", reviewed_at=datetime(2026, 4, 1, 9, 0)))
        bump("t_aa_student_correction")
    db.commit()


# ═══════════════════════ Phase 11：教材全流程 ═══════════════════════

def seed_textbook(db, term_ids: dict[str, int], tt: dict, teachers: dict[str, int]):
    from app.models import (AaTextbook, AaTextbookDistributionBatch, AaTextbookDistributionRecord,
                            AaTextbookFeeLedger, AaTextbookOrderBatch, AaTextbookOrderItem,
                            AaTextbookReviewBatch, AaTextbookReviewBatchItem, AaTextbookSelection, AaTeachingTask)
    cur_term = term_ids["2025-2026-2"]
    books = [
        ("Java程序设计（第4版）", "9787115560001", "人民邮电出版社", "第4版", "耿祥义", Decimal("59.80")),
        ("机械制图与计算机绘图", "9787111660002", "机械工业出版社", "第3版", "杨可桢", Decimal("48.00")),
        ("基础护理学", "9787117290003", "人民卫生出版社", "第7版", "李小妹", Decimal("68.00")),
    ]
    book_ids: list[int] = []
    for name, isbn, pub, ed, author, price in books:
        b = get(db, AaTextbook, isbn=isbn)
        if b is None:
            b = AaTextbook(tenant_id=TID, name=name, isbn=isbn, publisher=pub, edition=ed, author=author,
                          subject="专业课", unit_price=price, is_national_standard=True, status="ENABLED")
            db.add(b)
            db.flush()
            bump("t_aa_textbook")
        book_ids.append(b.id)
    db.commit()

    task_keys = [k for k in tt["taskIds"] if not k.split(":")[1].startswith("PUB")][:3]
    selection_ids: list[int] = []
    college_id = 22
    for i, key in enumerate(task_keys):
        task = db.get(AaTeachingTask, tt["taskIds"][key])
        sel = db.scalars(select(AaTextbookSelection).where(AaTextbookSelection.tenant_id == TID,
                                                            AaTextbookSelection.task_id == task.id)).first()
        if sel is None:
            sel = AaTextbookSelection(tenant_id=TID, task_id=task.id, textbook_id=book_ids[i % len(book_ids)],
                                      textbook_name=books[i % len(books)][0], course_name=task.course_name,
                                      college_id=college_id, officer_key=task.teacher_key,
                                      officer_teacher_id=task.teacher_id, expected_qty=task.expected_students,
                                      status="ORDERED")
            db.add(sel)
            db.flush()
            bump("t_aa_textbook_selection")
        selection_ids.append(sel.id)
    db.commit()

    review_batch = get(db, AaTextbookReviewBatch, batch_name="2025-2026学年第二学期教材选用审核")
    if review_batch is None:
        review_batch = AaTextbookReviewBatch(tenant_id=TID, batch_name="2025-2026学年第二学期教材选用审核",
                                             term_id=cur_term, publicity_start_at=datetime(2025, 12, 1),
                                             publicity_end_at=datetime(2025, 12, 7), college_reviewer="周斌",
                                             academic_reviewer="董克建", status="PUBLISHED")
        db.add(review_batch)
        db.flush()
        bump("t_aa_textbook_review_batch")
    for sid in selection_ids:
        if not db.scalars(select(AaTextbookReviewBatchItem).where(AaTextbookReviewBatchItem.tenant_id == TID,
                                                                   AaTextbookReviewBatchItem.batch_id == review_batch.id,
                                                                   AaTextbookReviewBatchItem.selection_id == sid)).first():
            db.add(AaTextbookReviewBatchItem(tenant_id=TID, batch_id=review_batch.id, selection_id=sid))
            bump("t_aa_textbook_review_batch_item")
    db.commit()

    order_batch = get(db, AaTextbookOrderBatch, batch_name="2025-2026学年第二学期教材征订")
    if order_batch is None:
        order_batch = AaTextbookOrderBatch(tenant_id=TID, batch_name="2025-2026学年第二学期教材征订",
                                           term_id=cur_term, college_id=college_id,
                                           submit_at=datetime(2025, 12, 10, 9, 0), status="ARRIVED")
        db.add(order_batch)
        db.flush()
        bump("t_aa_textbook_order_batch")
    for i, (name, isbn, pub, ed, author, price) in enumerate(books):
        if not db.scalars(select(AaTextbookOrderItem).where(AaTextbookOrderItem.tenant_id == TID,
                                                             AaTextbookOrderItem.order_batch_id == order_batch.id,
                                                             AaTextbookOrderItem.textbook_id == book_ids[i])).first():
            db.add(AaTextbookOrderItem(tenant_id=TID, order_batch_id=order_batch.id, textbook_id=book_ids[i],
                                       textbook_name=name, order_qty=50, arrived_qty=50, unit_price_snapshot=price))
            bump("t_aa_textbook_order_item")
    db.commit()

    dist_class = GRADE25_CLASSES[3]
    dist_batch = db.scalars(select(AaTextbookDistributionBatch).where(
        AaTextbookDistributionBatch.tenant_id == TID, AaTextbookDistributionBatch.order_batch_id == order_batch.id,
        AaTextbookDistributionBatch.class_id == dist_class)).first()
    if dist_batch is None:
        dist_batch = AaTextbookDistributionBatch(tenant_id=TID, order_batch_id=order_batch.id, class_id=dist_class,
                                                 class_name=str(dist_class), started_at=datetime(2026, 2, 20, 9, 0),
                                                 completed_at=datetime(2026, 2, 20, 16, 0), status="COMPLETED")
        db.add(dist_batch)
        db.flush()
        bump("t_aa_textbook_distribution_batch")
    db.commit()

    roster = _class_roster(db, dist_class)
    for stu in roster:
        rec = db.scalars(select(AaTextbookDistributionRecord).where(
            AaTextbookDistributionRecord.tenant_id == TID, AaTextbookDistributionRecord.batch_id == dist_batch.id,
            AaTextbookDistributionRecord.student_id == stu["id"],
            AaTextbookDistributionRecord.textbook_id == book_ids[0])).first()
        if rec is None:
            rec = AaTextbookDistributionRecord(tenant_id=TID, batch_id=dist_batch.id, student_id=stu["id"],
                                               textbook_id=book_ids[0], textbook_name=books[0][0], qty=1,
                                               received_at=datetime(2026, 2, 20, 10, 0), received_by=stu["name"],
                                               status="RECEIVED")
            db.add(rec)
            db.flush()
            bump("t_aa_textbook_distribution_record")
        ledger = db.scalars(select(AaTextbookFeeLedger).where(AaTextbookFeeLedger.tenant_id == TID,
                                                              AaTextbookFeeLedger.distribution_record_id == rec.id)).first()
        if ledger is None:
            db.add(AaTextbookFeeLedger(tenant_id=TID, distribution_record_id=rec.id, student_id=stu["id"],
                                       textbook_name=books[0][0], amount=books[0][5], paid_amount=books[0][5],
                                       paid_at=datetime(2026, 2, 20, 10, 5), status="PAID"))
            bump("t_aa_textbook_fee_ledger")
    db.commit()


# ═══════════════════════ Phase 12：教学质量 + 归档 + 毕业预审 + 免修 ═══════════════════════

def seed_quality(db, term_ids: dict[str, int]):
    from app.models import AaQualityRecord, AaQualityRectification
    cur_term = term_ids["2025-2026-2"]
    records = [
        ("SUPERVISION", "t_wu_zhigang", "吴志刚", "M25001", "Java程序设计", 88, "合格",
         "教学环节完整，学生参与度高，建议增加实训案例占比"),
        ("PATROL", "t_luo_yaqin", "罗雅琴", None, None, None, "正常",
         "巡课未发现迟到早退、教学事故等异常情况"),
        ("INSPECTION", "t_liu_zhiqiang", "刘志强", "M25003", "数据库原理与应用", 76, "待整改",
         "作业批改反馈不够及时，建议两周内完成一轮批改并公示"),
    ]
    record_ids: list[int] = []
    for rtype, r_key, r_name, tkey, cname, score, conclusion, desc in records:
        exists = db.scalars(select(AaQualityRecord).where(AaQualityRecord.tenant_id == TID,
                                                           AaQualityRecord.record_type == rtype,
                                                           AaQualityRecord.recorder_key == r_key)).first()
        if exists:
            record_ids.append(exists.id)
            continue
        rec = AaQualityRecord(tenant_id=TID, record_type=rtype, term_id=cur_term, college_id=22,
                              teacher_key=tkey, course_id=None, course_name=cname,
                              occurred_at=datetime(2026, 4, 15, 10, 0), location="教学楼A栋101",
                              title=f"{'督导听课' if rtype=='SUPERVISION' else '日常巡课' if rtype=='PATROL' else '教学检查'}记录",
                              score=Decimal(str(score)) if score else None, conclusion=conclusion, description=desc,
                              need_rectify=(conclusion == "待整改"), recorder_key=r_key, recorder_name=r_name,
                              status="CONFIRMED", confirmed_at=datetime(2026, 4, 16, 9, 0), confirmed_by_name="董克建")
        db.add(rec)
        db.flush()
        bump("t_aa_quality_record")
        record_ids.append(rec.id)
    db.commit()

    rectify_source = record_ids[2]
    if not db.scalars(select(AaQualityRectification).where(AaQualityRectification.tenant_id == TID,
                                                            AaQualityRectification.source_record_id == rectify_source)).first():
        db.add(AaQualityRectification(
            tenant_id=TID, source_record_id=rectify_source, source_type="INSPECTION",
            source_title="教学检查记录", title="数据库原理与应用作业批改及时性整改", term_id=cur_term,
            college_id=22, requirement="两周内完成一轮全部学生作业批改并在课堂公示，此后每两周批改一次",
            deadline=datetime(2026, 5, 1), responsible_key="t_liu_zhiqiang", responsible_name="刘志强",
            initiator_key="董克建", initiator_name="董克建",
            progress_log_json=json.dumps([{"time": "2026-04-20", "operator": "刘志强", "action": "整改中",
                                          "note": "已完成两周作业批改并公示"}], ensure_ascii=False),
            result_note="整改完成，后续巡课未再发现同类问题", status="CLOSED", closed_at=datetime(2026, 4, 28, 10, 0)))
        bump("t_aa_quality_rectification")
    db.commit()


def seed_archive(db, term_ids: dict[str, int]):
    from app.models import AaArchiveBatch, AaArchiveItem
    term1 = term_ids["2025-2026-1"]
    batch = get(db, AaArchiveBatch, term_id=term1)
    if batch is None:
        batch = AaArchiveBatch(tenant_id=TID, batch_name="2025-2026学年第一学期教务归档", term_id=term1,
                               term_code="2025-2026-1", checked_at=datetime(2026, 1, 20, 9, 0),
                               archived_at=datetime(2026, 1, 22, 9, 0), missing_count=0, status="ARCHIVED")
        db.add(batch)
        db.flush()
        bump("t_aa_archive_batch")
    db.commit()
    domains = [("STUDENT_STATUS", "学籍", 100), ("REGISTRATION", "注册", 100), ("STATUS_CHANGE", "异动", 2),
              ("PROGRAM", "培养方案", 7), ("TEACHING_TASK", "教学任务", 18), ("SCHEDULE", "课表", 18),
              ("EXAM", "考务", 6), ("GRADE", "成绩", 138), ("GRADUATION", "毕业资格", 0)]
    for domain, label, cnt in domains:
        if not db.scalars(select(AaArchiveItem).where(AaArchiveItem.tenant_id == TID,
                                                       AaArchiveItem.batch_id == batch.id,
                                                       AaArchiveItem.domain == domain)).first():
            db.add(AaArchiveItem(tenant_id=TID, batch_id=batch.id, domain=domain, domain_label=label,
                                 record_count=cnt, present=cnt > 0))
            bump("t_aa_archive_item")
    db.commit()


def seed_graduation_audit(db):
    """提前预审试运行：2025级学生正常学制应 2028 年毕业，此处按"提前试跑毕业预审能力"
    的口径生成 WAIT_PRECHECK 状态数据，不生成真实毕业证书（避免虚构在校生已毕业的失实叙事）。
    item_results_json 复用真实预审引擎 _run_items()/_overall() 生成（而非手写假字段），
    保证结构与 /graduation-audit-batches/{id}/precheck 真实产出完全一致，
    否则 list_results() 按 item 透视查询时会因结构不符抛 500（曾经的真实教训）。"""
    from app.models import AaGraduationAuditBatch, AaGraduationAuditResult, StudentProfile
    from app.modules.academic_affairs.services.academic_affairs_graduation_service import _run_items, _overall
    batch = get(db, AaGraduationAuditBatch, batch_name="2025级毕业资格预审能力试运行")
    if batch is None:
        batch = AaGraduationAuditBatch(tenant_id=TID, batch_name="2025级毕业资格预审能力试运行",
                                       grade_year="2025", major_id=None,
                                       scope_json=json.dumps({"grades": ["2025"], "note": "提前试运行,非正式毕业审核"}),
                                       generate_at=datetime(2026, 7, 15, 9, 0), status="REVIEWING")
        db.add(batch)
        db.flush()
        bump("t_aa_graduation_audit_batch")
    db.commit()
    roster25 = [s for cid in GRADE25_CLASSES for s in _class_roster(db, cid)]
    for stu in roster25[:5]:
        existing = db.scalars(select(AaGraduationAuditResult).where(
            AaGraduationAuditResult.tenant_id == TID, AaGraduationAuditResult.batch_id == batch.id,
            AaGraduationAuditResult.student_id == stu["id"])).first()
        if existing:
            continue
        s = db.get(StudentProfile, stu["id"])
        items = _run_items(db, s)
        overall = _overall(items)
        db.add(AaGraduationAuditResult(tenant_id=TID, batch_id=batch.id, student_id=stu["id"],
                                       item_results_json=json.dumps(items, ensure_ascii=False),
                                       overall=overall, conclusion=None, status=overall, rerun_count=1))
        bump("t_aa_graduation_audit_result")
    db.commit()


def seed_exemption_topup(db, course_ids: dict[str, int], teachers: dict[str, int]):
    """t_aa_exemption 已有 3 条历史数据（口径不明的既有行），此处补 1 条本学期真实流程样例，不覆盖既有行。"""
    from app.models import AaExemption
    stu = _class_roster(db, GRADE25_CLASSES[4])[0]
    exists = db.scalars(select(AaExemption).where(AaExemption.tenant_id == TID,
                                                   AaExemption.student_id == stu["id"],
                                                   AaExemption.status == "APPROVED")).first()
    if not exists:
        db.add(AaExemption(tenant_id=TID, student_id=stu["id"], student_no=stu["no"], student_name=stu["name"],
                           course_id=course_ids.get("PUB004"), course_name="计算机应用基础",
                           term_code="2025-2026-2", college_id=23, teacher_key="t_xie_yumei",
                           reason="已取得全国计算机等级考试二级证书，申请免修计算机应用基础课程",
                           status="APPROVED", archive_status="ARCHIVED"))
        bump("t_aa_exemption(new)")
    db.commit()


if __name__ == "__main__":
    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    try:
        teachers = seed_teachers(db)
        term_ids = seed_terms(db)
        seed_calendar(db, term_ids)
        slot_ids = seed_time_slots(db)
        course_ids = seed_courses(db, teachers)
        program_ids = seed_programs(db, course_ids)
        seed_course_materials(db, course_ids, teachers)
        resources = seed_resources(db, teachers)
        seed_resource_bookings_and_repairs(db, resources, teachers)
        seed_teacher_availability(db, term_ids, teachers)
        tt = seed_teaching_tasks(db, term_ids, course_ids, teachers)
        sched = seed_schedule(db, tt, resources)
        seed_schedule_change(db, tt, sched)
        selection = seed_selection(db, term_ids, course_ids, tt)
        att_count = seed_attendance(db, tt)
        seed_class_adjustment(db)
        exam = seed_exam(db, term_ids, tt)
        grades = seed_grades(db, term_ids, tt)
        seed_grade_recognition_and_workload(db, term_ids, course_ids, teachers)
        seed_evaluation(db, term_ids, tt)
        seed_status_change_and_registration(db, term_ids)
        seed_level_exam(db)
        seed_major_split_and_correction(db)
        seed_textbook(db, term_ids, tt, teachers)
        seed_quality(db, term_ids)
        seed_archive(db, term_ids)
        seed_graduation_audit(db)
        seed_exemption_topup(db, course_ids, teachers)
        print("=== 全部 Phase 完成 ===")
        print(json.dumps({"teacherCount": len(teachers), "termIds": term_ids,
                          "courseCount": len(course_ids), "programCount": len(program_ids),
                          "taskCount": len(tt["taskIds"]), "scheduleItemCount": len(sched["itemIds"]),
                          "selectionEnrolled": selection["enrolled"], "attendanceSessions": att_count,
                          "examCourseCount": len(exam["examCourseIds"]), "gradeRecordCount": grades["recordCount"],
                          "report": report}, ensure_ascii=False, indent=2))
    finally:
        db.close()
