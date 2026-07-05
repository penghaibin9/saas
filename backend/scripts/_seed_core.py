"""演示种子数据（driver 无关：SQLite / MySQL 共用同一套逻辑）。
调用方先设置好 DATABASE_URL / DB_* + DB_ENABLED=true（见 _dev_env.py / _mysql_env.py），再 run()。

规模（幂等，已灌则跳过）：
  主租户 demo         : 1 租户 + 1 品牌 + 8 角色 + 20 用户 + 100 学生
                        + 20 审批 + 30 待办 + 20 消息 + 50 审计
                        + 文件/导入/导出各若干（全链路可点）
  演示租户 demo-school: 1 租户 + 1 品牌 + 4 个「密码 hash」账号 + 5 学生（行级隔离验收）
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.session import get_sessionmaker, reset_state
from app.models import (College, ExportTask, FileObject, Major, Role, SchoolClass,
                        SecurityAuditLog, StudentContact, StudentImportBatch, StudentProfile,
                        StudentStageEvent, Tenant, TenantBrandConfig, UnifiedMessage, UnifiedTodo,
                        User, WorkflowInstance, WorkflowTask)

TID = 1000000000000000001    # 主租户 demo
TID2 = 1000000000000000003   # 演示租户 demo-school

# 演示账号统一密码为 Demo@2026 —— 仓库与数据库只存 pbkdf2_sha256 哈希，绝不落明文。
DEMO_ACCOUNTS = [
    ("admin_demo", "陈演示", "SCHOOL_ADMIN",
     "pbkdf2_sha256$200000$e3328d353dcd6d6520ec9b30d015d5b6$d25a69f77bb417069675912c3976134c5be31dddb3d53697f632f5808cc2f1aa"),
    ("teacher_demo", "李导师", "TEACHER",
     "pbkdf2_sha256$200000$5a98601f0dfbdbcc01f4e2214972c72d$d4f8e6e2c16a533071705cbd9e8e0cfd379d5145bce6310899d56ea5edf9a015"),
    ("counselor_demo", "王辅导", "TEACHER",
     "pbkdf2_sha256$200000$888b4cd504e4020f52945b113906f938$c67b03274c490ba9c4730ba3c361f7a3e2244b623d38ff09f34e2a646a13b32c"),
    ("student_demo", "张同学", "STUDENT",
     "pbkdf2_sha256$200000$278669d15b64d435317fa81fa201714e$99ef4fd8f0ff515a2bc2a505de8b5b974d4b1864d622d8f64478dd33ad468757"),
]

ROLES = [
    ("STUDENT", "学生"), ("COUNSELOR", "辅导员"), ("GD_MENTOR", "指导教师"),
    ("EMPLOYMENT_TEACHER", "就业老师"), ("ACADEMIC_TEACHER", "教务老师"),
    ("COLLEGE_ADMIN", "学院管理员"), ("SCHOOL_ADMIN", "学校管理员"), ("SYS_ADMIN", "系统管理员"),
]


def run() -> int:
    now = datetime.now()
    rng = random.Random(20260704)  # 固定随机种子，结果可复现

    reset_state()
    db = get_sessionmaker()()

    if db.scalars(select(StudentProfile).where(StudentProfile.tenant_id == TID)).first():
        print("[seed] demo data already present, skip（先跑 reset_*_db.py 可重灌）")
        return 0

    # ── 主租户 + 品牌 ──
    if not db.get(Tenant, TID):
        db.add(Tenant(id=TID, tenant_code="demo", school_name="示范职业技术学院",
                      short_name="示范职院", status="ACTIVE"))
        db.add(TenantBrandConfig(tenant_id=TID, platform_name="高校学生全生命周期管理平台",
                                 browser_title="高校学生全生命周期管理平台",
                                 primary_color="#2563EB", default_theme="academy_blue",
                                 motto="厚德 精技 笃行", watermark_text="示范职院内部系统"))

    # ── 8 角色 ──
    for code, name in ROLES:
        db.add(Role(tenant_id=TID, role_code=code, role_name=name, role_type="SYSTEM", status="ACTIVE"))

    # ── 组织：2 学院 / 4 专业 / 8 班 ──
    org = {}
    for ci, cname in enumerate(["软件学院", "机电学院"], start=1):
        col = College(tenant_id=TID, college_name=cname, code=f"C{ci}")
        db.add(col); db.flush()
        for mi in range(2):
            mname = ["软件技术", "大数据技术", "机电一体化", "工业机器人"][(ci - 1) * 2 + mi]
            maj = Major(tenant_id=TID, college_id=col.id, major_name=mname, code=f"C{ci}M{mi+1}")
            db.add(maj); db.flush()
            for ki in range(2):
                cls = SchoolClass(tenant_id=TID, major_id=maj.id,
                                  class_name=f"{mname[:2]}23{ki+1:02d}", grade="2023")
                db.add(cls); db.flush()
                org[(col.id, maj.id, cls.id)] = (cname, mname, cls.class_name)
    org_keys = list(org)

    # ── 20 用户 ──
    SURNAMES = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许"
    GIVEN = ["伟", "芳", "娜", "敏", "静", "磊", "军", "洋", "勇", "艳",
             "杰", "娟", "涛", "明", "超", "秀英", "霞", "平", "刚", "桂英"]
    for i in range(20):
        role_code = ROLES[i % len(ROLES)][0]
        db.add(User(tenant_id=TID, login_name=f"user{i+1:02d}", real_name=SURNAMES[i] + GIVEN[i],
                    password_hash="mock-not-a-real-hash",
                    user_type="TEACHER" if role_code != "STUDENT" else "STUDENT", status="ACTIVE"))

    # ── 100 学生 ──
    STAGES = ["ORIENTATION", "ON_CAMPUS", "INTERNSHIP", "GRADUATION_DESIGN", "EMPLOYMENT"]
    RISKS = [None] * 7 + ["LOW", "MEDIUM", "HIGH"]
    student_ids = []
    for i in range(100):
        ck, mk, kk = org_keys[i % len(org_keys)]
        stage = STAGES[i % len(STAGES)]
        risk = rng.choice(RISKS)
        name = rng.choice(SURNAMES) + rng.choice(GIVEN) + (rng.choice("一二三四五六七八九") if i % 3 == 0 else "")
        s = StudentProfile(tenant_id=TID, student_no=f"20231{i+1:05d}", real_name=name,
                           gender=rng.choice(["男", "女"]), college_id=ck, major_id=mk, class_id=kk,
                           grade="2023", current_stage=stage, student_status="NORMAL",
                           status="ACTIVE", remark=risk)
        db.add(s); db.flush(); student_ids.append(s.id)
        db.add(StudentContact(tenant_id=TID, student_id=s.id, contact_type="PHONE",
                              contact_value_encrypted=f"138{rng.randint(10000000, 99999999)}",
                              is_primary=True, verified_status="VERIFIED"))
        db.add(StudentStageEvent(tenant_id=TID, student_id=s.id, from_stage=None, to_stage=stage,
                                 reason="种子数据初始化", source_module="student",
                                 occurred_at=now - timedelta(days=rng.randint(10, 300))))

    # ── 20 审批（实例 + 待审任务）──
    APPROVAL_KINDS = [
        ("student", "PROFILE_CORRECTION", "学籍信息变更", "COUNSELOR_REVIEW", "辅导员审核"),
        ("intern", "COMPANY_CHANGE", "实习单位变更", "MENTOR_REVIEW", "指导教师审核"),
        ("employment", "MATERIAL_VERIFY", "就业材料核验", "EMPLOYMENT_VERIFY", "就业老师核验"),
        ("campus", "LEAVE", "请假申请", "COUNSELOR_REVIEW", "辅导员审核"),
    ]
    for i in range(20):
        mod, biz, label, node, node_name = APPROVAL_KINDS[i % len(APPROVAL_KINDS)]
        sid = student_ids[i % len(student_ids)]
        stu = db.get(StudentProfile, sid)
        inst = WorkflowInstance(tenant_id=TID, workflow_code=f"wf_{mod}", source_module=mod,
                                source_biz_type=biz, source_biz_id=sid, applicant_id=1,
                                title=f"{stu.real_name} · {label}", status="RUNNING",
                                current_node=node, remark=stu.real_name)
        db.add(inst); db.flush()
        db.add(WorkflowTask(tenant_id=TID, instance_id=inst.id, node_code=node, assignee_id=1,
                            status="PENDING", remark=node_name,
                            deadline_at=now + timedelta(days=rng.randint(1, 5))))

    # ── 30 待办 ──
    TODO_KINDS = [("APPROVAL", "待审批"), ("REVIEW", "待批阅"), ("RISK", "风险跟进"),
                  ("SUBMIT", "待提交"), ("CONFIRM", "待确认")]
    for i in range(30):
        ttype, tlabel = TODO_KINDS[i % len(TODO_KINDS)]
        sid = student_ids[(i * 3) % len(student_ids)]
        stu = db.get(StudentProfile, sid)
        db.add(UnifiedTodo(tenant_id=TID, source_module="core", source_biz_type=ttype,
                           source_biz_id=2000 + i, todo_type=ttype, assignee_id=1, student_id=sid,
                           title=f"{tlabel}：{stu.real_name}（{stu.student_no}）",
                           status="PENDING" if i % 5 else "DONE",
                           due_at=now + timedelta(days=rng.randint(1, 7))))

    # ── 20 消息 ──
    MSG_KINDS = [("TODO_NOTICE", "您有新的待办需要处理"), ("ANNOUNCEMENT", "教务处通知"),
                 ("SYSTEM", "系统权限变更提醒")]
    for i in range(20):
        mtype, mtitle = MSG_KINDS[i % len(MSG_KINDS)]
        db.add(UnifiedMessage(tenant_id=TID, receiver_id=1, source_module="core",
                              title=f"{mtitle} #{i+1}", content=f"演示消息内容 {i+1}",
                              message_type=mtype, status="UNREAD" if i % 4 else "READ"))

    # ── 50 审计 ──
    ACTIONS = ["LOGIN", "EXPORT", "SENSITIVE_VIEW", "IMPORT", "APPROVAL"]
    for i in range(50):
        db.add(SecurityAuditLog(tenant_id=TID, operator_name=SURNAMES[i % 20] + "老师",
                                current_role=ROLES[i % len(ROLES)][0],
                                action=ACTIONS[i % len(ACTIONS)], resource="seed-demo",
                                resource_id=str(1000 + i), result="SUCCESS",
                                trace_id=f"seed-{i:04d}", detail_json={"seq": i},
                                created_at=now - timedelta(hours=rng.randint(1, 240))))

    # ── 文件 / 导入 / 导出 测试数据（让文件中心 / 导入 / 导出全链路可点）──
    f_import = FileObject(tenant_id=TID, file_key="import/seed_students_2023.xlsx",
                          file_name="2023级学生导入模板.xlsx", ext="xlsx",
                          mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                          size_bytes=20480, sha256="seedimporthash0001", biz_type="IMPORT",
                          status="STORED", remark="种子：导入样例文件")
    f_export = FileObject(tenant_id=TID, file_key="export/students_list_20260704.xlsx",
                          file_name="学生名册导出_20260704.xlsx", ext="xlsx",
                          mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                          size_bytes=40960, sha256="seedexporthash0001", biz_type="EXPORT",
                          status="STORED", remark="种子：导出样例文件")
    db.add_all([f_import, f_export]); db.flush()

    db.add(StudentImportBatch(tenant_id=TID, batch_no="IMP-20260704-0001", file_id=f_import.id,
                              total_rows=100, success_rows=98, error_rows=2, status="SUCCESS",
                              remark="种子：导入批次（98 成功 / 2 失败）"))
    db.add(StudentImportBatch(tenant_id=TID, batch_no="IMP-20260704-0002", file_id=f_import.id,
                              total_rows=50, success_rows=0, error_rows=0, status="DRY_RUN_PASSED",
                              remark="种子：Dry-Run 通过待确认"))
    db.add(ExportTask(tenant_id=TID, export_mode="DESENSITIZED", module_code="student",
                      condition_json={"grade": "2023"}, field_list_json={"cols": ["student_no", "real_name", "current_stage"]},
                      row_count=100, purpose="迎新工作学生名册（脱敏）", file_id=f_export.id,
                      file_hash="seedexporthash0001", status="SUCCESS", remark="种子：导出任务"))

    # ── 演示租户 demo-school（账号密码登录 · 行级隔离验收）──
    if not db.get(Tenant, TID2):
        db.add(Tenant(id=TID2, tenant_code="demo-school", school_name="演示职业技术学院",
                      short_name="演示职院", status="ACTIVE"))
        db.add(TenantBrandConfig(tenant_id=TID2, platform_name="高校学生全生命周期管理平台",
                                 browser_title="高校学生全生命周期管理平台",
                                 primary_color="#2563EB", default_theme="academy_blue",
                                 watermark_text="演示职院内部系统"))
    for login, name, utype, phash in DEMO_ACCOUNTS:
        db.add(User(tenant_id=TID2, login_name=login, real_name=name,
                    password_hash=phash, user_type=utype, status="ACTIVE"))
    # demo-school 只灌 5 名学生（证明隔离：demo 账号只见这 5 人，不见主租户 100 人）
    for i in range(5):
        s2 = StudentProfile(tenant_id=TID2, student_no=f"2026D{i+1:04d}", real_name=f"演示学生{i+1}",
                            gender="男" if i % 2 == 0 else "女", grade="2026",
                            current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE")
        db.add(s2); db.flush()
        db.add(StudentContact(tenant_id=TID2, student_id=s2.id, contact_type="PHONE",
                              contact_value_encrypted=f"1390000{i:04d}", is_primary=True,
                              verified_status="VERIFIED"))
    db.add(UnifiedTodo(tenant_id=TID2, source_module="core", source_biz_id=9001, todo_type="SUBMIT",
                       assignee_id=1, title="演示租户：完善学生名单", status="PENDING"))
    db.add(UnifiedMessage(tenant_id=TID2, receiver_id=1, title="欢迎使用演示租户",
                          message_type="SYSTEM", status="UNREAD"))

    db.commit()

    # ── P6：平台总控种子（可选；服务器旧版 ORM 无 PlatformConfig 时跳过）──
    try:
        from _seed_platform import seed_platform
        seed_platform(db)
    except Exception as e:  # noqa: BLE001
        print(f"[seed] platform seed skipped: {e}")

    main_students = db.scalars(select(StudentProfile).where(StudentProfile.tenant_id == TID)).all()
    demo_students = db.scalars(select(StudentProfile).where(StudentProfile.tenant_id == TID2)).all()
    # 岗位实习域种子（幂等；不改学生数，不影响 demo=5 / 主租户=100 基线）
    try:
        from _seed_internship import seed_internship
        seed_internship(db)
    except Exception as e:  # noqa: BLE001
        print(f"[seed] internship seed skipped: {e}")

    # 数字迎新域种子（幂等）
    try:
        from _seed_orientation import seed_orientation
        seed_orientation(db)
    except Exception as e:  # noqa: BLE001
        print(f"[seed] orientation seed skipped: {e}")

    # 在校服务域种子（幂等）
    try:
        from _seed_campus_service import seed_campus_service
        seed_campus_service(db)
    except Exception as e:  # noqa: BLE001
        print(f"[seed] campus_service seed skipped: {e}")

    # 学业过程域种子（幂等）
    try:
        from _seed_academic import seed_academic
        seed_academic(db)
    except Exception as e:  # noqa: BLE001
        print(f"[seed] academic seed skipped: {e}")

    # 毕业设计域种子（幂等）
    try:
        from _seed_graduation import seed_graduation
        seed_graduation(db)
    except Exception as e:  # noqa: BLE001
        print(f"[seed] graduation seed skipped: {e}")

    # 就业服务域种子（幂等）
    try:
        from _seed_employment import seed_employment
        seed_employment(db)
    except Exception as e:  # noqa: BLE001
        print(f"[seed] employment seed skipped: {e}")

    # 移动端演示学生（李晓萌）跨域记录（幂等；重命名首个学生，不新增，主租户仍=100）
    try:
        from _seed_mobile_demo import seed_mobile_demo
        seed_mobile_demo(db)
    except Exception as e:  # noqa: BLE001
        print(f"[seed] mobile_demo seed skipped: {e}")

    # 教师范围映射（teacher_student_scope 最小可用版，幂等）
    try:
        from _seed_teacher_scope import seed_teacher_scope
        seed_teacher_scope(db)
    except Exception as e:  # noqa: BLE001
        print(f"[seed] teacher_scope seed skipped: {e}")

    print("[seed] OK")
    print(f"[seed] 主租户 demo        : 学生={len(main_students)} 角色={len(ROLES)} 用户=20 "
          f"审批=20 待办=30 消息=20 审计=50 文件=2 导入批次=2 导出任务=1")
    print(f"[seed] 演示租户 demo-school: 账号={len(DEMO_ACCOUNTS)}（密码统一 Demo@2026，库内 hash） 学生={len(demo_students)}")
    return 0